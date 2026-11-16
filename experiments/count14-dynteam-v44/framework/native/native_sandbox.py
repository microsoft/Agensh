"""Trusted host-only exact sandbox executable relocation, no worker override.

The caller obtains path+SHA from existing OPS admission. Matching a caller's SHA
is not a new claim of semantic bwrap qualification; OPS separately proves its
origin/kernel flags. Defaults retain /usr/bin/bwrap. No env/PATH fallback,
installation, shell wrapper, namespace flag change or worker configuration input.
"""
from dataclasses import dataclass
from pathlib import Path
import os,stat
from common import need,sha,hash_file
@dataclass(frozen=True)
class SandboxBinary:
 path:Path
 sha256:str
 def verify(self):
  p=Path(self.path);sha(self.sha256);need(p.is_absolute()and p.resolve()==p and not p.is_symlink(),'SANDBOX_EXACT_CANONICAL_PATH')
  s=p.lstat();need(stat.S_ISREG(s.st_mode)and s.st_mode&0o111 and not s.st_mode&0o022,'SANDBOX_READONLY_EXECUTABLE')
  need(s.st_uid in(0,os.geteuid()),'SANDBOX_TRUSTED_HOST_OWNER');pin=hash_file(p);need(pin['sha256']==self.sha256,'SANDBOX_EXECUTABLE_PIN_CHANGED')
  return {'path':str(p),**pin}
 @classmethod
 def system(cls):
  p=Path('/usr/bin/bwrap');return cls(p,hash_file(p)['sha256'])
def admitted_sandbox(value=None):
 result=SandboxBinary.system()if value is None else value;need(type(result)is SandboxBinary,'SANDBOX_HOST_ADMISSION_OBJECT_REQUIRED');result.verify();return result

@dataclass(frozen=True)
class NativeSdkIdentity:
 """Host-only explicit admission; no env, worker dictionary or generic wrapper."""
 uid:int=10000
 gid:int=10000
 public_runtime:Path|None=None
 def verify(self):
  need(os.getuid()==0 and os.geteuid()==0,'SDK_UID_TRUSTED_ROOT_CALLER')
  need(type(self.uid)is int and type(self.gid)is int and 0<self.uid<2**31 and 0<self.gid<2**31,'SDK_UID_NONROOT_TARGET')
  launcher=Path(__file__).resolve().with_name('native_sdk_uid_launcher.py');s=launcher.stat()
  need(stat.S_ISREG(s.st_mode)and s.st_uid==0 and not s.st_mode&0o022,'SDK_UID_TRUSTED_LAUNCHER')
  from native_sdk_public_runtime import admitted_public_root
  public=admitted_public_root(self.public_runtime)
  return {'uid':self.uid,'gid':self.gid,'public_runtime':str(public),'launcher':{'path':str(launcher),**hash_file(launcher)},'host_mount_changes':False,'file_setuid_changes':False,'private_mount_namespace':True,'original_namespace_flags_preserved':True}
def sdk_uid_command(argv,identity,kind,sandbox):
 if identity is None:return argv,None
 need(type(identity)is NativeSdkIdentity,'SDK_UID_HOST_ADMISSION_OBJECT');receipt=identity.verify()
 # Same shape checked again in the root-only standalone launcher, before mounts.
 from native_sdk_uid_launcher import geometry
 geometry(argv,kind,identity.uid,identity.gid)
 return ['/usr/bin/python3','-I','-B',receipt['launcher']['path'],'--kind',kind,'--uid',str(identity.uid),'--gid',str(identity.gid),'--sandbox-sha256',sandbox.sha256,'--',*argv],receipt
