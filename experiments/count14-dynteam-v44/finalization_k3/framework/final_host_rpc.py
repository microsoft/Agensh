"""Fixed metadata-only host UDS for native FINAL ownership and model permits.

No candidate, task, model request/response/error text, URL, command or filesystem
path is accepted. Final children cannot register themselves. One supervisor owns
ModelCapacity and all SEARCH+AUX permits; exact PID/start/boot/UID/PIDns and a
per-child capability bind every call. RPC failures are fatal domain failures, not
upstream model errors to be hidden behind native FINAL fallback/retry.
"""
from dataclasses import dataclass
from pathlib import Path
import hmac,os,socket,socketserver,threading,uuid
from common import need,integer,ident,sha,strict,wire,private_dir,Refused
from bridge import peer_identity
from final_queue import process_identity
CAP=65536
class ControlFailure(BaseException):
    def __init__(self,code):self.code=code;super().__init__(code)

@dataclass(frozen=True)
class HostBinding:
    scope:str
    capability:str
    pid:int
    start:str
    boot_id:str
    uid:int
    pid_namespace_inode:int
    def verify(self,peer):
        need(peer['pid']==self.pid and peer['uid']==self.uid and peer['pid_namespace_inode']==self.pid_namespace_inode,'FINAL_RPC_PEER_SCOPE')
        actual=process_identity(self.pid);need(actual['start']==self.start and actual['boot_id']==self.boot_id,'FINAL_RPC_PROCESS_IDENTITY')

class HostServer:
    def __init__(self,path,capacity):
        self.path=Path(path);private_dir(self.path.parent);need(not self.path.exists()and not self.path.is_symlink(),'FINAL_RPC_SOCKET_NO_CLOBBER')
        self.capacity=capacity;self.bindings={};self.lock=threading.RLock();outer=self
        class Handler(socketserver.StreamRequestHandler):
            def handle(handler):
                nonce=None
                try:
                    handler.connection.settimeout(10);raw=handler.rfile.readline(CAP+1);need(len(raw)<=CAP and raw.endswith(b'\n'),'FINAL_RPC_FRAME_BOUND')
                    value=strict(raw);nonce=value.get('nonce')if type(value)is dict else None
                    result=outer.dispatch(peer_identity(handler.connection),value);response={'ok':True,'nonce':nonce,'result':result}
                except Refused as e:response={'ok':False,'nonce':nonce,'code':e.code}
                except Exception as e:response={'ok':False,'nonce':nonce,'code':'FINAL_HOST_CONTROL_ERROR','error_type':type(e).__name__}
                reply=wire(response)+b'\n'
                if len(reply)<=CAP:
                    try:handler.wfile.write(reply);handler.wfile.flush()
                    except OSError:pass # SENT/custody already durable, no release/replay.
        class Server(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):
            daemon_threads=True
        self.server=Server(str(self.path),Handler);os.chmod(self.path,0o600);self.inode=self.path.stat().st_ino;self.thread=None
    def register(self,binding):
        need(isinstance(binding,HostBinding),'FINAL_RPC_HOST_BINDING_REQUIRED');sha(binding.scope);need(type(binding.capability)is str and len(binding.capability)>=48,'FINAL_RPC_CAPABILITY')
        integer(binding.pid,'FINAL_RPC_PID',1);integer(binding.uid,'FINAL_RPC_UID');integer(binding.pid_namespace_inode,'FINAL_RPC_NAMESPACE',1)
        with self.lock:need(binding.scope not in self.bindings,'FINAL_RPC_DUPLICATE_SCOPE');self.bindings[binding.scope]=binding
    def dispatch(self,peer,value):
        fields={'schema','scope','capability','method','payload','nonce'};need(type(value)is dict and set(value)==fields and value['schema']=='count14-agensh-final-control-v1','FINAL_RPC_FIELDS');ident(value['nonce']);sha(value['scope'])
        with self.lock:binding=self.bindings.get(value['scope'])
        need(binding is not None and type(value['capability'])is str and hmac.compare_digest(binding.capability,value['capability']),'FINAL_RPC_CAPABILITY')
        binding.verify(peer);method=value['method'];p=value['payload'];need(type(p)is dict,'FINAL_RPC_PAYLOAD')
        scope=binding.scope;c=self.capacity
        if method in ('authorize','frontier','state'):
            need(p=={},'FINAL_RPC_METHOD_FIELDS')
            if method=='state':return c.state(scope)
            front=c.frontier(scope)
            return {'binding_sha256':scope,'current_native_owner_authorized':True}if method=='authorize'else front
        if method=='pause':return c.pause(scope,p)
        shapes={'acquire':{'permit_id'},'sent':{'permit_id','request_id'},'terminal':{'permit_id','proof'},'unknown':{'permit_id','proof_sha256'},'pregen':{'permit_id','proof'},'cancel_unsent':{'permit_id'}}
        need(method in shapes and set(p)==shapes[method],'FINAL_RPC_METHOD_FIELDS');ident(p['permit_id'])
        if method=='acquire':return c.acquire(scope,p['permit_id'])
        if method=='sent':
            sent=c.sent(scope,p['permit_id'],p['request_id']);return {'recorded':sent,'state':'SENT'if sent else'HELD_UNSENT_PAUSED'}
        elif method=='terminal':c.provider_terminal(scope,p['permit_id'],p['proof'])
        elif method=='unknown':c.unknown(scope,p['permit_id'],p['proof_sha256'])
        elif method=='pregen':c.pre_generation_rejected(scope,p['permit_id'],p['proof'])
        elif method=='cancel_unsent':c.cancel_unsent(scope,p['permit_id'])
        return {'recorded':True}
    def start(self):
        need(self.thread is None,'FINAL_RPC_ALREADY_STARTED');self.thread=threading.Thread(target=self.server.serve_forever,name='agensh-final-control',daemon=True);self.thread.start()
    def close(self):
        if self.thread is not None:self.server.shutdown();self.thread.join(10)
        self.server.server_close()
        need(self.path.is_socket()and self.path.stat().st_ino==self.inode,'FINAL_RPC_SOCKET_IDENTITY_CHANGED');self.path.unlink()

class HostClient:
    def __init__(self,path,*,scope,capability):
        self.path=Path(path);need(self.path.is_absolute()and self.path.resolve()==self.path,'FINAL_RPC_CANONICAL_SOCKET');self.scope=sha(scope);self.capability=capability
    def call(self,method,payload=None):
        value={'schema':'count14-agensh-final-control-v1','scope':self.scope,'capability':self.capability,'method':method,'payload':{}if payload is None else payload,'nonce':uuid.uuid4().hex};raw=wire(value)+b'\n'
        if len(raw)>CAP:raise ControlFailure('FINAL_RPC_FRAME_BOUND')
        try:
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)as client:
                client.settimeout(15);client.connect(str(self.path));client.sendall(raw)
                with client.makefile('rb')as f:reply=f.readline(CAP+1)
            need(len(reply)<=CAP and reply.endswith(b'\n'),'FINAL_RPC_REPLY_BOUND');response=strict(reply);need(response.get('nonce')==value['nonce'],'FINAL_RPC_REPLY_NONCE')
            need(response.get('ok')is True,response.get('code','FINAL_RPC_NO_RESULT'));return response['result']
        except Refused as e:raise ControlFailure(e.code)from None
        except Exception as e:raise ControlFailure('FINAL_RPC_IO_'+type(e).__name__)from None
    def authorize(self,binding):
        need(__import__('common').digest(binding)==self.scope,'FINAL_RPC_BINDING_SHA');return self.call('authorize')
