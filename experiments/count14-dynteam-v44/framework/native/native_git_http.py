"""Fixed native Gitea smart HTTP over peer-bound UDS, not an HTTP proxy.

Only four smart-Git exchanges are possible for the owner-bound org/repo. Native
Gitea authorization/hooks remain in the path. No worker URL, headers, credential,
CONNECT, SSH, arbitrary path or executable crosses this boundary. Raw Git bytes
are streamed without decoding/logging. Response truncation/timeout after dispatch
retains ACTIVE and closes shared admission; no resend or fabricated terminal.
"""
from dataclasses import dataclass
from pathlib import Path
import base64,hashlib,hmac,http.client,json,os,socket,socketserver,struct,tempfile,threading,urllib.parse,uuid
from common import need,Refused,ident,trajectory_id,sha,digest,wire,strict,private_dir,unix_socket_address
from bridge import peer_identity,HEADER_CAP,PACK_CAP
from native_control_custody import NativeAcceptedControls,require_control_drained
SCHEMA='agensh-native-git-http-v1'
ACTIONS={'info-upload':('GET','info/refs?service=git-upload-pack','application/x-git-upload-pack-advertisement'),
 'info-receive':('GET','info/refs?service=git-receive-pack','application/x-git-receive-pack-advertisement'),
 'upload':('POST','git-upload-pack','application/x-git-upload-pack-result'),
 'receive':('POST','git-receive-pack','application/x-git-receive-pack-result')}
BLOCK=65536

def read_exact(stream,n):
 result=bytearray()
 while len(result)<n:
  chunk=stream.read(n-len(result));need(bool(chunk),'GIT_HTTP_FRAME_TRUNCATED');result.extend(chunk)
 return bytes(result)

@dataclass(frozen=True)
class NativeGitHttpBinding:
 trajectory:str
 role:str
 generation:int
 uid:int
 pid_namespace_inode:int
 capability:str
 service_instance_sha256:str
 bootstrap_receipt_sha256:str
 service_origin:str
 organization:str
 repository:str
 native_username:str

class NativeGitHttp:
 def __init__(self,binding,ledger,private_home,*,token,parent_tool_provider):
  need(isinstance(binding,NativeGitHttpBinding),'GIT_HTTP_TRUSTED_BINDING');trajectory_id(binding.trajectory)
  for name in(binding.role,binding.organization,binding.repository,binding.native_username):ident(name)
  need(type(binding.generation)is int and binding.generation>=1 and type(binding.uid)is int and binding.uid>=0 and type(binding.pid_namespace_inode)is int and binding.pid_namespace_inode>0,'GIT_HTTP_PEER_BINDING')
  need(type(binding.capability)is str and len(binding.capability)>=48,'GIT_HTTP_CAPABILITY_BOUND');sha(binding.service_instance_sha256);sha(binding.bootstrap_receipt_sha256)
  url=urllib.parse.urlsplit(binding.service_origin)
  need(url.scheme in('http','https')and url.hostname and url.username is None and url.password is None and url.path in('','/')and not url.query and not url.fragment,'GIT_HTTP_FIXED_ORIGIN')
  need(type(token)is str and token and not any(x in token for x in '\x00\r\n')and callable(parent_tool_provider),'GIT_HTTP_PRIVATE_AUTHORITY')
  self.binding=binding;self.ledger=ledger;self.home=private_dir(private_home,create=True);self.origin=url;self.token=token;self.parent_tool_provider=parent_tool_provider;self.lock=threading.RLock();self.children={};self.closing=False;self.scope=digest({k:v for k,v in vars(binding).items()if k!='capability'})
  self.path='/'+binding.organization+'/'+binding.repository+'.git/'
  # Resource backpressure is pre-dispatch, not a scientific model concurrency
  # permission or a queue that could cross the checkpoint admission fence.
  self.slots=threading.BoundedSemaphore(2)
 def header(self,peer,value):
  b=self.binding
  need(peer['uid']==b.uid and peer['pid_namespace_inode']==b.pid_namespace_inode,'GIT_HTTP_PEER_IDENTITY')
  from native_model_tool_parent import NativeModelToolParents
  fields={'schema','capability','action','size','protocol','content_encoding'}
  need(type(value)is dict and set(value)in(fields,fields|{'cli_ticket'})and value['schema']==SCHEMA,'GIT_HTTP_FIXED_ENVELOPE')
  if 'cli_ticket'in value:
   need(type(self.parent_tool_provider)is NativeModelToolParents and self.parent_tool_provider.ledger is self.ledger,'GIT_HTTP_ORIGINAL_PARENT_CONTEXT_PORT')
   sha(value['cli_ticket'])
  need(type(value['capability'])is str and hmac.compare_digest(value['capability'],b.capability),'GIT_HTTP_PEER_CAPABILITY')
  action=value['action'];need(type(action)is str and action in ACTIONS,'GIT_HTTP_FIXED_ACTION_ONLY')
  n=value['size'];need(type(n)is int and 0<=n<=PACK_CAP and(action in('upload','receive')or n==0),'GIT_HTTP_BODY_BOUND')
  need(value['protocol']in('','version=1','version=2')and value['content_encoding']in('','gzip')and(action in('upload','receive')or value['content_encoding']==''),'GIT_HTTP_FIXED_GIT_HEADERS')
  return action,n
 def fault(self,code,op=None):
  if getattr(self.ledger,'native_unmanaged_cli',False):return
  self.ledger.latch_fault(self.binding.trajectory,code)
  try:
   with self.ledger.tx():
    self.ledger.db.execute("UPDATE accounts SET state='FAULT'WHERE trajectory=?",(self.binding.trajectory,));self.ledger.event(self.binding.trajectory,'NATIVE_GIT_HTTP_UNRESOLVED',{'scope':self.scope,'operation_id':op,'code':code})
  except Exception:pass
 def finish(self,op,status,response_sha,size):
  if getattr(self.ledger,'native_unmanaged_cli',False):return
  # Response EOF must be physically observed before this transaction. If this
  # commit fails, ACTIVE is not released and no successful IPC trailer is sent.
  with self.ledger.tx():
   self.ledger.event(self.binding.trajectory,'NATIVE_GIT_HTTP_PHYSICAL_TERMINAL',{'scope':self.scope,'operation_id':op,'status':status,'response_sha256':response_sha,'bytes':size})
   row=self.ledger.db.execute('SELECT state,kind FROM operations WHERE id=?',(op,)).fetchone()
   need(row is not None and row['state']=='ACTIVE'and row['kind']in('GIT_READ','GIT_WRITE'),'GIT_HTTP_OPERATION_IDENTITY')
   self.ledger.db.execute("UPDATE operations SET state='COMPLETE'WHERE id=?",(op,));self.ledger.event(self.binding.trajectory,'OPERATION_COMPLETE',{'operation_id':op})
 def accept_operation(self,value,action,request_sha,n):
  if getattr(self.ledger,'native_unmanaged_cli',False):
   # Already authenticated by unchanged header(); transport correlation only.
   need(not self.closing,'GIT_HTTP_OWNER_CLOSING_NO_DISPATCH')
   return None,self.binding
  # Whole-team mode authenticates the fixed role/UID/netns/capability exactly
  # as header() does. It does NOT require shell callback ancestry: all backend
  # and worker writers are frozen together at checkpoint. New Git exchanges
  # park pre-dispatch during DRAINING and resume once on the same connection.
  while True:
   wait=False
   with self.lock,self.ledger.mutex:
    need(not self.closing,'GIT_HTTP_OWNER_CLOSING_NO_DISPATCH');b=self.binding
    whole=getattr(self,'whole_team',None)
    if whole is not None:
     from native_whole_team import NativeWholeTeamRegistration
     need(type(whole)is NativeWholeTeamRegistration and whole.ledger is self.ledger
          and whole.t==b.trajectory and whole.owner.git.get(b.role)is self
          and whole.owner.writer_fence.whole_team is whole,'GIT_HTTP_WHOLE_TEAM_ORIGINAL_ROLE')
     need(not self.ledger.admission_fault(b.trajectory),'GIT_HTTP_WHOLE_TEAM_FAULT_NO_DISPATCH')
     state=self.ledger.frontier(b.trajectory)['state']
     if state=='DRAINING':
      # Let already-admitted same-role shell tools finish Git before freeze;
      # otherwise waiting for TOOL0 and parking its Git would deadlock.
      wait=self.ledger.db.execute("SELECT COUNT(*) FROM operations WHERE trajectory=? AND role=? AND generation=? AND kind='TOOL' AND state='ACTIVE'",(b.trajectory,b.role,b.generation)).fetchone()[0]==0
     elif state in ('CAPTURING','COMMITTED_PARKED'):wait=True
     else:need(state=='RUNNING','GIT_HTTP_WHOLE_TEAM_NOT_RUNNING')
     parent=None
    else:
     parent=self.parent_tool_provider.git_parent(b,cli_ticket=value['cli_ticket'])if 'cli_ticket'in value else self.parent_tool_provider(b)
    if not wait:
     op='native-git-'+uuid.uuid4().hex
     accepted=False
     try:
      self.ledger.operation_start(b.trajectory,b.role,b.generation,op,
        'GIT_WRITE'if action in('receive','info-receive')else'GIT_READ',
        parent_tool_operation=parent,whole_team_scope=whole)
      accepted=True;self.children[op]={'generation':b.generation,'action':action}
      with self.ledger.tx():self.ledger.event(b.trajectory,'NATIVE_GIT_HTTP_DISPATCH',
        {'scope':self.scope,'operation_id':op,'action':action,'request_sha256':request_sha,'bytes':n})
      return op,b
     except BaseException:
      if accepted:self.fault('GIT_HTTP_DISPATCH_METADATA_UNKNOWN_RETAIN_NO_RETRY',op)
      raise
   # Never hold port lock while parked: original same-live stage needs it.
   with self.ledger.capacity_changed:self.ledger.capacity_changed.wait(.25)
 def handle(self,connection):
  op=None;backend=None;slot=False;active=False;completed=False
  try:
   connection.settimeout(120);stream=connection.makefile('rb',buffering=0)
   with stream:
    raw=stream.readline(HEADER_CAP+1);need(len(raw)<=HEADER_CAP and raw.endswith(b'\n'),'GIT_HTTP_HEADER_BOUND')
    value=strict(raw);action,n=self.header(peer_identity(connection),value)
    slot=self.slots.acquire(blocking=False);need(slot,'GIT_HTTP_BACKPRESSURE_BEFORE_DISPATCH')
    # Complete the bounded IPC body before native dispatch. A malformed worker
    # transfer must not leave a possibly accepted HTTP mutation to guess about.
    with tempfile.TemporaryFile(dir=self.home)as body:
     remaining=n;request_hash=hashlib.sha256()
     while remaining:
      chunk=stream.read(min(BLOCK,remaining));need(bool(chunk),'GIT_HTTP_BODY_TRUNCATED_BEFORE_DISPATCH');remaining-=len(chunk);body.write(chunk);request_hash.update(chunk)
     need(stream.read(1)==b'','GIT_HTTP_NO_TRAILING_FRAME');body.seek(0)
     verb,suffix,expected_type=ACTIONS[action]
     op,b=self.accept_operation(value,action,request_hash.hexdigest(),n)
     active=True
     # Accepted exchanges still require real EOF; UNKNOWN never gains a retry.
     factory=http.client.HTTPSConnection if self.origin.scheme=='https'else http.client.HTTPConnection
     backend=factory(self.origin.hostname,self.origin.port,timeout=120)
     credential=base64.b64encode((b.native_username+':'+self.token).encode()).decode()
     headers={'Authorization':'Basic '+credential,'Connection':'close','Accept':expected_type,'Content-Length':str(n)}
     if verb=='POST':headers['Content-Type']='application/x-git-'+('receive'if action=='receive'else'upload')+'-pack-request'
     if value['protocol']:headers['Git-Protocol']=value['protocol']
     if value['content_encoding']:headers['Content-Encoding']=value['content_encoding']
     backend.request(verb,self.path+suffix,body=body if n else None,headers=headers)
     response=backend.getresponse();need(not 300<=response.status<400,'GIT_HTTP_REDIRECT_FORBIDDEN')
     content_type=response.getheader('Content-Type','').split(';',1)[0].strip()
     if response.status==200:need(content_type==expected_type,'GIT_HTTP_NATIVE_CONTENT_TYPE')
     # No backend headers/URL/cookies/challenge/token are forwarded to workers.
     delivery=True
     try:connection.sendall(wire({'ok':True,'status':response.status,'content_type':expected_type if response.status==200 else'text/plain'})+b'\n')
     except OSError:delivery=False;self.fault('GIT_HTTP_CLIENT_DELIVERY_UNKNOWN',op)
     total=0;hasher=hashlib.sha256()
     # A client disconnect never stops draining the one original response.
     while True:
      chunk=response.read(BLOCK)
      if not chunk:
       need(response.length in(None,0),'GIT_HTTP_RESPONSE_TRUNCATED');break
      total+=len(chunk);need(total<=PACK_CAP,'GIT_HTTP_RESPONSE_BOUND');hasher.update(chunk)
      if delivery:
       try:connection.sendall(struct.pack('!I',len(chunk))+chunk)
       except OSError:delivery=False;self.fault('GIT_HTTP_CLIENT_DELIVERY_UNKNOWN',op)
     response.close();self.finish(op,response.status,hasher.hexdigest(),total);active=False;completed=True
     if delivery:
      try:
       end={'ok':True}if getattr(self.ledger,'native_unmanaged_cli',False)else {'ok':True,'physical_terminal':True,'operation_id':op}
       connection.sendall(struct.pack('!I',0)+wire(end)+b'\n')
      except OSError:self.fault('GIT_HTTP_CLIENT_DELIVERY_UNKNOWN',op)
  except Refused as error:
   if active:self.fault(error.code,op)
   try:connection.sendall(wire({'ok':False,'code':error.code})+b'\n')
   except OSError:pass
  except Exception:
   if active:self.fault('GIT_HTTP_NATIVE_OR_CUSTODY_UNKNOWN',op)
   try:connection.sendall(wire({'ok':False,'code':'GIT_HTTP_CONTROL_UNKNOWN_NO_RETRY'})+b'\n')
   except OSError:pass
  finally:
   closed=True
   try:
    if backend is not None:backend.close()
   except Exception:closed=False;self.fault('GIT_HTTP_LOCAL_CLOSE_UNKNOWN',op)
   try:connection.close()
   except Exception:closed=False;self.fault('GIT_HTTP_LOCAL_CLOSE_UNKNOWN',op)
   if slot:self.slots.release()
   # Hold even a COMPLETE operation until its actual local descriptors closed.
   # An unsuccessful metadata commit or backend EOF never releases custody.
   if completed and closed:
    with self.lock:self.children.pop(op,None)

class NativeGitHttpServer:
 def __init__(self,path,broker,*,late_delivery=False):
  from native_delivery import delivery_dir
  self.path=Path(path);(delivery_dir if late_delivery else private_dir)(self.path.parent);need(not self.path.exists()and not self.path.is_symlink(),'GIT_HTTP_SOCKET_NO_CLOBBER');self.broker=broker;self.thread=None;owner=self
  class Handler(socketserver.BaseRequestHandler):
   def handle(self):owner.broker.handle(self.request)
  class Server(NativeAcceptedControls,socketserver.UnixStreamServer):pass
  with unix_socket_address(self.path)as address:self.server=Server(address,Handler,control_failure=lambda code:broker.ledger.latch_fault(broker.binding.trajectory,code),unmanaged_cli=getattr(broker.ledger,'native_unmanaged_cli',False))
  self.server.server_address=str(self.path);os.chmod(self.path,0o600)
  if broker.binding.uid!=os.geteuid():os.chown(self.path,broker.binding.uid,-1)
  self.inode=self.path.stat().st_ino
 def start(self):
  need(self.thread is None,'GIT_HTTP_ALREADY_STARTED');self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
 def close_listener(self):
  if self.thread:self.server.shutdown();self.thread.join()
  self.server.server_close();require_control_drained(self,'GIT_HTTP_ACCEPTED_CONTROL_RETAIN_CUSTODY');need(self.path.is_socket()and self.path.stat().st_ino==self.inode,'GIT_HTTP_SOCKET_CHANGED');self.path.unlink()
