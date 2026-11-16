"""Frozen exact18 selection, only in a new original finite sampler child."""
from pathlib import Path
import hashlib,importlib.util,os,stat,sys
PINS={'retired_health_roots.py': '5e886c83c2b94e4bc3eda736b048042b67589d43086ae63a5df4419e6e4ff9db', 'original_lifecycle_reader.py': '3838a5d98078026f6452ffa0f67cee77d76c1071f22724efef8c69fb15e0e9ae', 'private_sampler_selection.py': '9ae1a840574c93b69529d639091ec54a55c3679e1c34ccce1a6b101d892c2d7e'}
def select(original,job,plan):
 home=Path(__file__).resolve().parent
 for name,pin in PINS.items():
  p=home/name;s=p.lstat()
  if not(p.resolve()==p and stat.S_ISREG(s.st_mode)and s.st_nlink==1 and not s.st_mode&0o022 and s.st_uid in(0,os.geteuid())and hashlib.sha256(p.read_bytes()).hexdigest()==pin):
   raise ValueError('EXACT18_FINITE_PRIVATE_FROZEN_HELPER_PIN')
  key=p.stem
  if key in sys.modules:raise ValueError('EXACT18_ONLY_NEW_PRIVATE_HELPER_MODULES')
  spec=importlib.util.spec_from_file_location(key,p);m=importlib.util.module_from_spec(spec);sys.modules[key]=m;spec.loader.exec_module(m)
 return sys.modules['private_sampler_selection'].select_sample(original,job,plan,package_directory=home)
