#!/usr/bin/python3
"""Trusted root-only, fixed-shape SDK startup. No RPC, credentials or model IO.

Use bwrap's existing privileged (real worker UID / effective root UID) setup,
not unprivileged uid mapping. A private *mount* namespace aliases exact approved
sources so neither Azure0700 ancestors nor worker0700 are made public. No
mount/sysctl/file-SUID change escapes this process's private namespace.
Standalone (-I); intentionally imports no experiment or third-party modules.
"""
import argparse,ctypes,hashlib,os,pathlib,signal,stat,subprocess,sys,tempfile
FLAGS=['--unshare-user','--unshare-pid','--unshare-uts','--unshare-ipc','--unshare-cgroup','--die-with-parent','--new-session']
class Denied(Exception):pass
def require(ok,code):
 if not ok:raise Denied(code)
def pin(path):
 h=hashlib.sha256()
 with open(path,'rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def geometry(argv,kind,uid,gid):
 require(type(argv)is list and argv[1:8]==FLAGS,'SDK_UID_FIXED_NAMESPACES')
 if kind=='gitea':
  require(len(argv)==24 and argv[8]=='--ro-bind'and argv[10]=='/gitea-mcp'and argv[11]=='--bind'and argv[13]=='/work'and argv[14:]==['--tmpfs','/tmp','--chdir','/work','--unsetenv','AGENSH_MCP_CONTROL_FD','--','/gitea-mcp','-t','stdio'],'SDK_UID_GITEA_FIXED_JAIL')
  # len checked below separately: retain the exact original Go stdio suffix.
  mounts=[(8,False),(11,True)]
 elif kind=='mattermost':
  require(argv[8:9]==['--ro-bind'],'SDK_UID_MM_FIXED_JAIL')
  dests=['/usr/bin/python3.11','/usr/lib/python3.11','/site-packages','/lib/x86_64-linux-gnu','/lib64']
  require(len(argv)==38 and all(argv[8+3*i]=='--ro-bind'and argv[10+3*i]==dest for i,dest in enumerate(dests))and argv[23:]==['--proc','/proc','--dev','/dev','--tmpfs','/tmp','--chdir','/tmp','--unsetenv','AGENSH_MCP_CONTROL_FD','--','/usr/bin/python3.11','-B','-m','mcp_server_mattermost'],'SDK_UID_MM_FIXED_JAIL')
  mounts=[(8+3*i,False)for i in range(5)]
 else:raise Denied('SDK_UID_FIXED_KIND')
 for i,writable in mounts:
  p=pathlib.Path(argv[i+1]);require(p.is_absolute(),'SDK_UID_ABSOLUTE_SOURCE');q=p.resolve(strict=True)
  s=q.stat();require(stat.S_ISREG(s.st_mode)or stat.S_ISDIR(s.st_mode),'SDK_UID_FILE_OR_DIRECTORY')
  if writable:require(p==q and not p.is_symlink()and stat.S_ISDIR(s.st_mode)and s.st_uid==uid and s.st_gid==gid and s.st_mode&0o777==0o700,'SDK_UID_EXACT_PRIVATE_WORKSPACE')
 return mounts
def native(lib,name,*args):
 require(getattr(lib,name)(*args)==0,'SDK_UID_'+name.upper()+'_FAILED')
def worker_setup(uid,gid):
 os.setgroups([]);os.setresgid(gid,gid,gid);os.setresuid(uid,0,0)
def execute(argv,*,kind,uid,gid,sandbox_sha256):
 require(os.getuid()==0 and os.geteuid()==0,'SDK_UID_TRUSTED_ROOT_CALLER')
 require(type(uid)is int and type(gid)is int and 0<uid<2**31 and 0<gid<2**31,'SDK_UID_NONROOT_TARGET')
 sandbox=pathlib.Path(argv[0]);require(sandbox.is_absolute()and sandbox.resolve()==sandbox and not sandbox.is_symlink(),'SDK_UID_EXACT_SANDBOX_PATH')
 s=sandbox.stat();require(stat.S_ISREG(s.st_mode)and s.st_uid==0 and s.st_mode&0o111 and not s.st_mode&0o7022,'SDK_UID_ROOTOWN_NONSETUID_SANDBOX');require(pin(sandbox)==sandbox_sha256,'SDK_UID_SANDBOX_PIN')
 mounts=geometry(argv,kind,uid,gid);lib=ctypes.CDLL(None,use_errno=True);parent=os.getppid();native(lib,'prctl',1,int(signal.SIGKILL),0,0,0);require(os.getppid()==parent,'SDK_UID_PARENT_CHANGED')
 # First isolate mount propagation; never mount/unmount into shared host state.
 native(lib,'unshare',0x00020000);native(lib,'mount',None,b'/',None,ctypes.c_ulong(0x4000|0x40000),None)
 root=pathlib.Path(tempfile.mkdtemp(prefix='OWN-native-sdk-uid-'));root.chmod(0o711);aliases=[];rewritten=list(argv)
 try:
  for index,writable in mounts:
   source=pathlib.Path(argv[index+1]).resolve(strict=True);fd=os.open(source,os.O_PATH|os.O_NOFOLLOW);original=os.fstat(fd);alias=root/('work'if writable else'public-'+str(index))
   try:
    if stat.S_ISDIR(original.st_mode):alias.mkdir(mode=0o700)
    else:alias.touch(mode=0o400)
    native(lib,'mount',os.fsencode('/proc/self/fd/'+str(fd)),os.fsencode(alias),None,ctypes.c_ulong(0x1000),None);aliases.append(alias)
    mounted=alias.stat();require((mounted.st_dev,mounted.st_ino)==(original.st_dev,original.st_ino),'SDK_UID_ALIAS_INODE_CHANGED')
    if not writable:native(lib,'mount',None,os.fsencode(alias),None,ctypes.c_ulong(0x1000|0x20|1),None)
   finally:os.close(fd)
   rewritten[index+1]=str(alias)
  # No custom uid-map, newuidmap, SUID files, sysctl or generic bwrap override.
  # bwrap's stock privileged path maps only the actual worker identity.
  child=subprocess.Popen(rewritten,stdin=None,stdout=None,stderr=None,close_fds=True,cwd='/',preexec_fn=lambda:worker_setup(uid,gid))
  def forward(sig,_frame):
   try:child.send_signal(sig)
   except ProcessLookupError:pass
  for sig in(signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,forward)
  result=child.wait();return result if result>=0 else 128-result
 finally:
  for alias in reversed(aliases):
   native(lib,'umount2',os.fsencode(alias),2)
  for path in root.iterdir():
   if path.is_dir():path.rmdir()
   else:path.unlink()
  root.rmdir()
def main():
 p=argparse.ArgumentParser(add_help=False);p.add_argument('--kind',choices=('gitea','mattermost'),required=True);p.add_argument('--uid',type=int,required=True);p.add_argument('--gid',type=int,required=True);p.add_argument('--sandbox-sha256',required=True);p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args();require(a.command[:1]==['--'],'SDK_UID_COMMAND_SEPARATOR');return execute(a.command[1:],kind=a.kind,uid=a.uid,gid=a.gid,sandbox_sha256=a.sandbox_sha256)
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception:
  # Fixed code only: never include exception repr, environment or SDK payload.
  sys.stderr.write('SDK_UID_TRUSTED_STARTUP_REFUSED\n');raise SystemExit(125)
