"""Only a new receiver's original typed sources, never a live owner patch."""
from pathlib import Path
from dataclasses import replace
import hashlib,json,os,stat
import gateway_pr1_v2 as GP
INDEX_PIN='fc5786144416a8b2e882dc7c3d42da56e344d508f54de8bc31fcbe5e491d5214'
SYSTEM_CHILD_PIN='d1b1f6fea69fd90fae229930d5f206669472732ca684f5141e8994438c19ff7c'

def need(ok,code):GP.need(ok,code)
def verify_children(home):
 home=Path(home);p=home/'PROVIDER_CHILD_TREES_PUBLIC.json'
 need(home.is_absolute()and home.resolve()==home and not home.is_symlink(),'FIXED_PRIVATE_CHILD_HOME')
 raw=p.read_bytes();need(hashlib.sha256(raw).hexdigest()==INDEX_PIN,'EXACT_PRIVATE_CHILD_INDEX')
 j=json.loads(raw)
 for n,r in j['files'].items():
  p=home/n;s=p.lstat()
  need(p.resolve()==p and not p.is_symlink()and stat.S_ISREG(s.st_mode)and s.st_nlink==1 and s.st_uid in(0,os.geteuid())and stat.S_IMODE(s.st_mode)==0o444 and s.st_size==r['bytes']and hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'],'FROZEN_PRIVATE_CHILD_SOURCE_METADATA_AND_SHA')
 return j

def select_typed(original,*,package_directory,typed_input_compiler):
 from native_system_health import SystemProbeSources
 need(type(original)is dict and type(original['system'])is SystemProbeSources,'ORIGINAL_TYPED_SYSTEM_SOURCE')
 verify_children(package_directory)
 from typed_transport_source import physical_factory_source
 physical,origin=physical_factory_source(typed_input_compiler,original['_original_create'])
 selected,proof=GP.select_transport_factory(original['transport'],contract=original['contract'],physical_factory_source=physical)
 proof['typed_prefix_physical_source_origin']=origin
 value=dict(original);value['transport']=selected
 value['system']=replace(original['system'],child=Path(package_directory)/'msg220-system/runtime-v1-msg237-held20-v1/native_system_probe_child.py',child_sha256=SYSTEM_CHILD_PIN)
 manifest=json.loads((Path(package_directory)/'MANIFEST_PUBLIC.json').read_bytes())
 source_q=dict(path=str(Path(package_directory)/'MINIMAL_QUALIFICATION_PUBLIC.json'),sha256=manifest['files']['MINIMAL_QUALIFICATION_PUBLIC.json'])
 import msg220_retirement_lineage as L
 return value,dict(proof,new_source_qualification_reference=source_q,current_source_STOP_qualification_reference=dict(source_q),prior_completed244_retirement_qualification_reference=dict(L.QUALIFICATION),old_factory_not_called=True,original_python_key_custody_and_other_typed_objects_retained=True)
