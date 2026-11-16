"""Private fixed-command local control. Never handles requests under its lock."""
from pathlib import Path
import hashlib,os,socket,stat,struct,threading
from common import need,strict,wire,hash_file
class Control:
 def __init__(self,c):
  self.c=c;self.applied=set();self.lock=threading.Lock();self.path=c.home/'control.sock';self.approved=c.home/'approved';self.approved.mkdir(mode=0o700)
 def command(self,value,uid):
  need(uid==os.geteuid()==0,'DISK_CONTROL_ROOT_PEER');need(value in('status','drain','apply-fix'),'DISK_CONTROL_FIXED_COMMAND')
  if value=='status':return self.c.status()
  if value=='drain':self.c.operator_hold=True;return {'drain_requested':True,'inflight_cancelled':False}
  path=self.approved/'APPROVED.json';codepath=self.approved/'fix.py'
  def read(p,limit):
   fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
   try:
    s=os.fstat(fd);need(stat.S_ISREG(s.st_mode)and s.st_uid==0 and s.st_nlink==1 and s.st_mode&0o077==0 and s.st_size<=limit,'DISK_CONTROL_PRIVATE_APPROVAL')
    with os.fdopen(os.dup(fd),'rb')as f:return f.read(limit+1)
   finally:os.close(fd)
  approval=strict(read(path,4096));code=read(codepath,1048576);pin=hashlib.sha256(code).hexdigest()
  need(approval=={'schema':'r16-fixed-owner-approved-fix-v1','sha256':pin},'DISK_CONTROL_EXACT_APPROVAL')
  with self.lock:need(pin not in self.applied,'DISK_CONTROL_NO_RETRY');self.applied.add(pin)
  space={'__name__':'_disk_custodian_fix_'+pin[:16],'__file__':str(codepath)};exec(compile(code,str(codepath),'exec'),space);need(callable(space.get('apply')),'DISK_CONTROL_FIXED_APPLY');result=space['apply'](self.c)
  return {'status':'FIX_APPLIED','sha256':pin}
 def start(self):
  need(not self.path.exists()and len(os.fsencode(self.path))<104,'DISK_CONTROL_NEW_SHORT_SOCKET');self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.sock.bind(str(self.path));self.path.chmod(0o600);self.sock.listen(4)
  def run():
   while True:
    conn,_=self.sock.accept()
    def one(conn):
     with conn:
      try:
       conn.settimeout(30);_,uid,_=struct.unpack('3i',conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12));raw=conn.recv(1025);need(len(raw)<=1024,'DISK_CONTROL_FRAME_BOUND');a=strict(raw);need(type(a)is dict and set(a)=={'command'},'DISK_CONTROL_EXACT_FRAME');v=self.command(a['command'],uid)
      except BaseException as e:v={'status':'REFUSED','exception_type':type(e).__name__,'messages_locals_omitted':True}
      try:conn.sendall(wire(v))
      except OSError:pass # Never repeats an applied control command.
    threading.Thread(target=one,args=(conn,),daemon=True).start()
  threading.Thread(target=run,daemon=True,name='disk-final-local-control').start()
