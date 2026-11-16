"""Reopen the registered live SDK's EXACT original anonymous pipes, never respawn.

OPS-only trusted host restoration primitive. All old authorized readers must be
physically ended and exclusive experiment owner locks acquired BEFORE use. The
caller verifies the original whole-team frozen kernel scope before/after. An
incomplete all-host fd scan is NOT treated as proof that no reader exists.
No bytes are consumed until the normal native protocol reader is installed.
"""
from pathlib import Path
import array,fcntl,os,re,select,stat,termios
from common import need,Refused
from bridge import process_identity

class AdoptedPipes:
 def __init__(self,identity,streams):
  self.pid=identity['pid'];self.identity=dict(identity);self.stdin,self.stdout,self.control=streams
  self.stderr=None;self.returncode=None;self.pidfd=os.pidfd_open(self.pid,0)
 def alive(self):
  if select.select([self.pidfd],[],[],0)[0]:return False
  try:return process_identity(self.pid)==self.identity
  except FileNotFoundError:return False
 def poll(self):
  if self.alive():return None
  raise Refused('DISK_SDK_NONPARENT_EXIT_STATUS_UNOBSERVABLE')
 def wait(self,*args,**kwargs):raise Refused('DISK_SDK_NOT_ORIGINAL_PARENT_NO_WAIT_RECEIPT')
 def close_handles(self):
  # Closing this adopter's duplicate fd is not process cancellation or a signal.
  for s in(self.stdin,self.stdout,self.control):s.close()
  os.close(self.pidfd)

def _inode(pid,fd):
 path=Path(f'/proc/{pid}/fd/{fd}');link=os.readlink(path)
 need(re.fullmatch(r'pipe:\[[1-9][0-9]*\]',link)is not None,'DISK_SDK_EXACT_ANONYMOUS_PIPE')
 st=path.stat();need(stat.S_ISFIFO(st.st_mode),'DISK_SDK_PIPE_NOT_REGULAR_PRIVATE_FILE')
 return st.st_ino

def pending_bytes(fd):
 value=array.array('i',[0]);fcntl.ioctl(fd,termios.FIONREAD,value,True)
 need(value[0]>=0,'DISK_SDK_PIPE_AVAILABLE_METADATA');return value[0]

def attach(identity,*,registered_fds,guard,old_readers_ended,exclusive_owner):
 """registered_fds fixed keys stdin/stdout/control -> fd + pipe inode.

 guard() validates exact original frozen cgroup identity, not merely a boolean
 stored from an old observation. Old reader exit + exclusive original flocks
 establishes authority, not a bounded system-wide holder scan.
 """
 need(set(identity)=={'pid','start_ticks','boot_id'}and type(identity['pid'])is int,'DISK_SDK_REGISTERED_IDENTITY')
 need(exclusive_owner()is True and old_readers_ended()is True,'DISK_SDK_EXCLUSIVE_SUCCESSOR_OLD_READERS_ENDED')
 guard();need(process_identity(identity['pid'])==identity,'DISK_SDK_ORIGINAL_LIVE_PID_START')
 need(type(registered_fds)is dict and set(registered_fds)=={'stdin','stdout','control'},'DISK_SDK_ALL_THREE_ORIGINAL_PIPES')
 need(registered_fds['stdin'].get('fd')==0 and registered_fds['stdout'].get('fd')==1
      and type(registered_fds['control'].get('fd'))is int and registered_fds['control']['fd']>=3,
      'DISK_SDK_STDIO_CONTROL_FDS_NOT_INTERCHANGEABLE')
 need(len({r.get('inode')for r in registered_fds.values()})==3,'DISK_SDK_THREE_DISTINCT_PIPE_INODES')
 handles=[];result=None
 try:
  for kind in('stdin','stdout','control'):
   row=registered_fds[kind]
   need(type(row)is dict and set(row)=={'fd','inode'}and type(row['fd'])is int and row['fd']>=0
        and type(row['inode'])is int and row['inode']>0,'DISK_SDK_FIXED_PIPE_METADATA')
   need(_inode(identity['pid'],row['fd'])==row['inode'],'DISK_SDK_ORIGINAL_PIPE_INODE')
   mode=os.O_WRONLY if kind=='stdin'else os.O_RDONLY
   fd=os.open(f"/proc/{identity['pid']}/fd/{row['fd']}",mode|os.O_NONBLOCK|os.O_CLOEXEC)
   try:
    st=os.fstat(fd);need(stat.S_ISFIFO(st.st_mode)and st.st_ino==row['inode'],'DISK_SDK_REOPEN_SAME_PIPE')
    if kind!='stdin':need(pending_bytes(fd)==0,'DISK_SDK_UNREAD_PROTOCOL_FRAME_RETAIN_NO_GUESS')
    os.set_blocking(fd,True);stream=os.fdopen(fd,'wb'if kind=='stdin'else'rb',buffering=0);fd=None
    handles.append(stream)
   finally:
    if fd is not None:os.close(fd)
  guard();need(exclusive_owner()is True and old_readers_ended()is True
      and process_identity(identity['pid'])==identity,'DISK_SDK_FRONTIER_CHANGED_DURING_ATTACH')
  result=AdoptedPipes(identity,handles)
  need(result.alive(),'DISK_SDK_ORIGINAL_PROCESS_ENDED_DURING_ATTACH');return result
 except BaseException:
  if result is not None:result.close_handles()
  else:
   for s in handles:s.close()
  raise
