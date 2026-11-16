"""Fixed-repository Git and fixed-channel chat over per-worker UNIX sockets.

No general HTTP, URL, host path, shell or privileged API is exposed. Deploy each
socket as the only per-worker IPC mount. Broker backend paths/credentials stay
host-side. Git transport uses native smart-pack commands with hooks disabled;
OPS must verify Gitea's registered repository/API view in the real team gate.
"""
from dataclasses import dataclass
from pathlib import Path
import hmac,os,socket,socketserver,stat,struct,subprocess,threading,uuid
from common import need,Refused,wire,strict,private_dir,digest
HEADER_CAP=16384;PACK_CAP=512*2**20

def write_all(pipe,data):
    view=memoryview(data)
    while view:
        n=pipe.write(view);need(type(n)is int and 0<n<=len(view),'GIT_PIPE_SHORT_WRITE')
        view=view[n:]

def process_identity(pid):
    # Linux field 22, after the final ')' delimiting comm; metadata only.
    fields=Path(f'/proc/{pid}/stat').read_text().rsplit(') ',1)[1].split()
    return {'pid':pid,'start_ticks':int(fields[19]),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}

class ChildCustodian:
    """Own native child until a real wait terminal, including broken clients.

    Persistent STARTED/CUSTODY/TERMINAL events survive owner loss; an absent
    broker never converts an unfinished child to COMPLETE on restart.
    """
    def __init__(self,ledger,trajectory):
        self.ledger,self.trajectory=ledger,trajectory;self.lock=threading.Lock();self.children={}
    def register(self,op,child):
        identity=process_identity(child.pid)
        with self.ledger.tx():self.ledger.event(self.trajectory,'BRIDGE_CHILD_STARTED',{'operation_id':op,**identity})
        with self.lock:self.children[op]=(child,identity)
    def terminal(self,op,code):
        with self.lock:
            value=self.children.pop(op,None)
        if value is None:return
        with self.ledger.tx():self.ledger.event(self.trajectory,'BRIDGE_CHILD_TERMINAL',{'operation_id':op,**value[1],'exit_code':code if code>=0 else None,'signal':-code if code<0 else None})
        self.ledger.operation_end(op)
    def retain(self,op,child):
        # Keep strong ownership even after handler/transport exit. No signal,
        # timer-based release, retry, or second Git execution.
        with self.ledger.tx():self.ledger.event(self.trajectory,'BRIDGE_CHILD_CUSTODY_RETAINED',{'operation_id':op})
        def watch():
            code=child.wait();self.terminal(op,code)
            if child.stdout is not None:child.stdout.close()
        thread=threading.Thread(target=watch,name='native-git-custody',daemon=False);thread.start()

@dataclass(frozen=True)
class Binding:
    trajectory:str
    role:str
    generation:int
    uid:int
    pid_namespace_inode:int
    capability:str
    repository:Path
    channels:tuple

def peer_identity(sock):
    pid,uid,gid=struct.unpack('3i',sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
    return {'pid':pid,'uid':uid,'gid':gid,'pid_namespace_inode':os.stat(f'/proc/{pid}/ns/pid').st_ino}

def authorize(binding,peer,header):
    need(peer['uid']==binding.uid and peer['pid_namespace_inode']==binding.pid_namespace_inode,'BRIDGE_PEER_IDENTITY')
    need(type(header)is dict and set(header)=={'schema','method','capability','payload'},'BRIDGE_HEADER_FIELDS')
    need(header['schema']=='agensh-worker-bridge-v1' and isinstance(header['capability'],str) and len(binding.capability)>=32 and hmac.compare_digest(header['capability'],binding.capability),'BRIDGE_CAPABILITY')
    method=header['method'];p=header['payload'];need(type(p)is dict,'BRIDGE_PAYLOAD')
    if method in ('git-upload-pack','git-receive-pack'):need(p=={},'GIT_NO_USER_PATH_URL_OR_COMMAND')
    elif method=='chat.list':need(p=={},'CHAT_LIST_ARGUMENTS')
    elif method in ('chat.read','chat.post'):
        fields={'channel','limit'} if method=='chat.read' else {'channel','message'};need(set(p)==fields and p['channel']in binding.channels,'CHAT_CHANNEL_SCOPE')
        if method=='chat.read':need(type(p['limit'])is int and 1<=p['limit']<=100,'CHAT_READ_LIMIT')
        else:need(type(p['message'])is str and 0<len(p['message'].encode())<=8000,'CHAT_MESSAGE_BOUND')
    else:need(False,'BRIDGE_METHOD_FORBIDDEN')
    return method,p

class Broker:
    def __init__(self,binding,ledger,chat_backend=None):
        self.binding,self.ledger,self.chat_backend=binding,ledger,chat_backend
        self.lock=threading.RLock()
        self.custodian=ChildCustodian(ledger,binding.trajectory)
        p=binding.repository;need(p.is_absolute() and p.resolve()==p and p.is_dir() and not p.is_symlink(),'FIXED_REGISTERED_REPOSITORY')
        # Remote URLs, hooks and executable repo configuration never come from workers.
        self.command={'git-upload-pack':['git','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','upload-pack','--strict',str(p)],'git-receive-pack':['git','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','-c','receive.hideRefs=refs/tags/count14-bootstrap','receive-pack',str(p)]}
    def begin(self,method):
        with self.lock:return self._begin(method)
    def _begin(self,method):
        b=self.binding;op='bridge-'+uuid.uuid4().hex;kind={'git-upload-pack':'GIT_READ','git-receive-pack':'GIT_WRITE','chat.list':'CHAT_READ','chat.read':'CHAT_READ','chat.post':'CHAT_WRITE'}[method]
        # A tool accepted before closure may need to finish Git/chat after model
        # admission is closed. No unrelated bridge operation is admitted then.
        parent=None
        with self.ledger.mutex:
            f=self.ledger.frontier(b.trajectory)
            if f['state']=='DRAINING':
                r=self.ledger.db.execute("SELECT id FROM operations WHERE trajectory=? AND role=? AND generation=? AND kind='TOOL' AND state='ACTIVE' ORDER BY id LIMIT 1",(b.trajectory,b.role,b.generation)).fetchone();parent=r[0]if r else None
            self.ledger.operation_start(b.trajectory,b.role,b.generation,op,kind,parent_tool_operation=parent)
        return op
    def fail(self,op,code):
        with self.ledger.tx():
            self.ledger.event(self.binding.trajectory,'BRIDGE_FAILURE',{'operation_id':op,'code':code})
            self.ledger.db.execute("UPDATE accounts SET state='DRAINING' WHERE trajectory=? AND state='RUNNING'",(self.binding.trajectory,))
    def handle(self,connection):
        op=None;process=None
        try:
            connection.settimeout(120);header=bytearray()
            while not header.endswith(b'\n'):
                b=connection.recv(1);need(bool(b) and len(header)<HEADER_CAP,'BRIDGE_HEADER_BOUND');header.extend(b)
            method,p=authorize(self.binding,peer_identity(connection),strict(header));op=self.begin(method)
            if method.startswith('chat.'):
                need(self.chat_backend is not None,'CHAT_BACKEND_NOT_CONFIGURED')
                value=self.chat_backend(method,p,self.binding);raw=wire(value);need(len(raw)<=8*2**20,'CHAT_REPLY_BOUND')
                with self.ledger.tx():seq=self.ledger.event(self.binding.trajectory,'CHAT_RESULT',{'operation_id':op,'method':method,'response_sha256':digest(value)})
                self.ledger.operation_end(op);connection.sendall(wire({'ok':True,'sequence':seq,'result':value})+b'\n');return
            env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'HOME':'/nonexistent','LANG':'C','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_TERMINAL_PROMPT':'0'}
            process=subprocess.Popen(self.command[method],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=env,bufsize=0)
            self.custodian.register(op,process)
            connection.sendall(b'OK\n');errors=[]
            def inbound():
                n=0
                try:
                    while True:
                        block=connection.recv(65536)
                        if not block:break
                        n+=len(block);need(n<=PACK_CAP,'GIT_PACK_BYTE_CAP');write_all(process.stdin,block)
                except (OSError,Refused):errors.append('GIT_INPUT_TRANSPORT_FAILED')
                finally:
                    try:process.stdin.close()
                    except OSError:pass
            thread=threading.Thread(target=inbound,daemon=True);thread.start();n=0
            for block in iter(lambda:process.stdout.read(65536),b''):
                n+=len(block);need(n<=PACK_CAP,'GIT_PACK_BYTE_CAP');connection.sendall(block)
            code=process.wait(timeout=120)
            try:connection.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            thread.join(timeout=3);need(not thread.is_alive(),'GIT_INPUT_NOT_TERMINAL')
            # Releasing custody means physical Git terminal, not success of push.
            self.custodian.terminal(op,code)
            if code or errors:self.fail(op,'GIT_NATIVE_NONZERO' if code else errors[0])
        except (Refused,OSError,subprocess.TimeoutExpired) as e:
            code=e.code if isinstance(e,Refused) else 'BRIDGE_TRANSPORT_OR_PROCESS_UNKNOWN'
            if op:self.fail(op,code)
            if process is None:
                if op:self.ledger.operation_end(op)
                try:connection.sendall(wire({'ok':False,'code':code})+b'\n')
                except OSError:pass
            elif process.poll()is not None:self.custodian.terminal(op,process.returncode)
            else:self.custodian.retain(op,process)
            # A live child retains ACTIVE operation custody. Never claim terminal
            # or kill/retry a possibly-writing Git process just to pass a barrier.
        finally:
            if process is not None and process.poll()is not None and process.stdout is not None:process.stdout.close()
            connection.close()

class _Handler(socketserver.BaseRequestHandler):
    def handle(self):self.server.broker.handle(self.request)
class UnixServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads=False
    def __init__(self,path,broker):
        p=Path(path);private_dir(p.parent);need(not p.exists() and not p.is_symlink(),'BRIDGE_SOCKET_NO_CLOBBER');self.broker=broker
        super().__init__(str(p),_Handler);os.chmod(p,0o600)
        if p.stat().st_uid!=broker.binding.uid:os.chown(p,broker.binding.uid,-1)
