"""Private same-owner Unix control; only apply-fix / status / drain.

No network exposure, worker mounts, credentials, signal handler, debugger or
arbitrary RPC argument/code/path. Only owner/root SO_PEERCRED may connect.
apply-fix loads the exact root-owned local approval at a fixed private location.
"""
from pathlib import Path
import hashlib,importlib.util,os,socket,stat,struct,threading,uuid
from common import need,private_dir,regular_fd,strict,wire,hash_file

class OwnerControl:
    def __init__(self,driver,directory):
        self.driver=driver;self.directory=private_dir(directory,create=True)
        self.approved=private_dir(self.directory/'approved-fix',create=True)
        self.path=self.directory/'owner.sock'
        need(len(os.fsencode(self.path))<=107,'R16_CONTROL_SHORT_PRIVATE_UDS_PATH')
        need(not self.path.exists()and not self.path.is_symlink(),'R16_CONTROL_FIRSTSTART_NO_REPLACE')
        self.owner_uid=os.geteuid();self.lock=threading.RLock();self.stop=threading.Event()
        self.socket=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.socket.bind(str(self.path));os.chmod(self.path,0o600)
        self.identity=(self.path.stat().st_dev,self.path.stat().st_ino)
        self.socket.listen(8);self.socket.settimeout(.25);self.thread=None
        self.applied=set();self.draining=False
        self.original_admit=driver.admit
        def admit(row,phase):
            if self.draining and phase in ('new-final-claims','new-trajectory','release-search'):return None
            return self.original_admit(row,phase)
        driver.admit=admit
    def _private_file(self,path,limit):
        with regular_fd(path)as fd:
            s=os.fstat(fd)
            need(s.st_uid==self.owner_uid and stat.S_IMODE(s.st_mode)==0o600 and s.st_nlink==1,
                 'R16_CONTROL_APPROVAL_PRIVATE_OWNER_MODE')
            raw=os.read(fd,limit+1);need(len(raw)<=limit,'R16_CONTROL_APPROVAL_BOUND')
            end=os.fstat(fd)
            need((s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)==
                 (end.st_dev,end.st_ino,end.st_size,end.st_mtime_ns,end.st_ctime_ns),
                 'R16_CONTROL_APPROVAL_CHANGED')
        return raw
    def command(self,value,uid):
        need(uid in (0,self.owner_uid),'R16_CONTROL_TRUSTED_PEERCRED_ONLY')
        need(value in ('apply-fix','status','drain'),'R16_CONTROL_FIXED_COMMAND_ONLY')
        with self.lock:
            if value=='status':
                return {'status':self.driver.status(),'drain_requested':self.draining,
                        'control_owner_pid':os.getpid()}
            if value=='drain':
                # ONLY seal new admissions. Do not trigger an artificial cut,
                # abort requests/children or convert real SENT to UNKNOWN.
                ledger=self.driver.ledger
                with ledger.capacity_changed:
                    with ledger.tx():
                        ledger.db.execute("UPDATE model_control SET paused=1,epoch=epoch+1,reason='OPS_LOCAL_CONTROL_DRAIN' WHERE singleton=1")
                        ledger.event('GLOBAL','R16_OWNER_CONTROL_DRAIN',{'cancel':False,'replay':False,'new_admissions_sealed':True})
                    self.draining=True;ledger.capacity_changed.notify_all()
                return {'status':'DRAIN_REQUESTED','new_admissions_sealed':True,'cancelled':0}
            approval=strict(self._private_file(self.approved/'APPROVED.json',4096))
            need(type(approval)is dict and set(approval)=={'schema','sha256'}
                 and approval['schema']=='r16-fixed-owner-approved-fix-v1','R16_CONTROL_EXACT_APPROVAL')
            code=self._private_file(self.approved/'fix.py',1048576)
            pin=hashlib.sha256(code).hexdigest()
            need(approval['sha256']==pin,'R16_CONTROL_APPROVED_FIX_PIN')
            need(pin not in self.applied,'R16_CONTROL_FIX_NO_AUTOMATIC_RETRY')
            # Record BEFORE execution; exception never permits automatic retry.
            self.applied.add(pin)
            module_name='_r16_owner_approved_fix_'+pin[:16]
            space={'__name__':module_name,'__file__':str(self.approved/'fix.py')}
            exec(compile(code,str(self.approved/'fix.py'),'exec'),space)
            need(callable(space.get('apply')),'R16_CONTROL_FIXED_APPLY_FUNCTION')
            space['apply'](self.driver)
            return {'status':'FIX_APPLIED','sha256':pin}
    def start(self):
        need(self.thread is None,'R16_CONTROL_START_ONCE')
        def serve():
            while not self.stop.is_set():
                try:conn,_=self.socket.accept()
                except socket.timeout:continue
                with conn:
                    try:
                        conn.settimeout(2)
                        _,uid,_=struct.unpack('3i',conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                        raw=bytearray()
                        while b'\n'not in raw and len(raw)<=128:
                            data=conn.recv(129-len(raw))
                            if not data:break
                            raw.extend(data)
                        need(len(raw)<=128 and raw.endswith(b'\n')and raw.count(b'\n')==1,
                             'R16_CONTROL_SINGLE_BOUNDED_COMMAND')
                        value=bytes(raw[:-1]).decode('ascii','strict')
                        result=self.command(value,uid)
                    except BaseException as exc:
                        result={'status':'REFUSED','exception_type':type(exc).__name__}
                    try:conn.sendall(wire(result)+b'\n')
                    except OSError:pass # Reply loss NEVER replays a command.
        self.thread=threading.Thread(target=serve,name='r16-private-owner-control',daemon=False)
        self.thread.start();return self
    def close(self):
        self.stop.set()
        if self.thread:self.thread.join(5)
        self.socket.close()
        if self.path.exists():
            s=self.path.lstat();need((s.st_dev,s.st_ino)==self.identity,'R16_CONTROL_SOCKET_REPLACED')
            self.path.unlink()

def install_owner_control(driver):
    old=getattr(driver,'_r16_local_control',None)
    if old is not None:
        need(old.thread.is_alive(),'R16_CONTROL_EXISTING_THREAD_NOT_LIVE');return old
    control=OwnerControl(driver,driver.root/'control');driver._r16_local_control=control
    return control.start()
