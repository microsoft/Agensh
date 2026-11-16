"""Private same-CodeType sample/outside bindings; no original module mutation."""
from pathlib import Path
from types import FunctionType
import hashlib,inspect,json
from retired_health_roots import RetiredRoots,private_performance,PLAN_PIN
from original_lifecycle_reader import OriginalLifecycle,BINDINGS_PIN

PROJECTION_PIN='66ece9e044bdde4b0742941ae390a16c9eaaf18f38c61d342224007b86fbdf26'
SAMPLER_PIN='880ae285ee18ad75e4aec3ccc4aa024f63a8423128834c6468b885606349cec3'

def need(ok,code):
 if not ok:raise ValueError(code)
def pinned(p,pin):
 p=Path(p);need(p.resolve()==p and not p.is_symlink(),'EXACT18_SELECTION_CANONICAL_FROZEN_SOURCE')
 raw=p.read_bytes();need(hashlib.sha256(raw).hexdigest()==pin,'EXACT18_SELECTION_ORIGINAL_OR_METADATA_SHA');return raw

def select_outside(original,*,new_arm_root,registry_path,registry_sha256,package_directory):
 need(type(original)is FunctionType and original.__name__=='registered_outside_projection' and
      hashlib.sha256(Path(original.__code__.co_filename).read_bytes()).hexdigest()==PROJECTION_PIN,
      'EXACT18_SAME_ORIGINAL_OUTSIDE_PROJECTION_FUNCTION')
 home=Path(package_directory);plan=pinned(home/'APPROVED_PLAN_PUBLIC.json',PLAN_PIN)
 pinned(home/'LIFECYCLE_BINDINGS_PUBLIC.json',BINDINGS_PIN)
 life=OriginalLifecycle(home/'LIFECYCLE_BINDINGS_PUBLIC.json',original_registry_path=registry_path,
                        original_registry_sha256=registry_sha256)
 registry=json.loads(pinned(registry_path,registry_sha256));old_factory=original.__globals__['frozen_observer']
 def private_observer():
  observer,performance=old_factory() # preserve original aliases and all source SQL patches
  guard=RetiredRoots(plan,new_arm_root=new_arm_root,registered_roots=registry['scale_request_roots'],
       registered_books=registry['scale_reservation_books'],original_observer=observer,
       fresh_lifecycle_reader=life.read_one,lifecycle_source_sha256=life.reader_pin)
  return observer,private_performance(performance,guard)
 namespace=dict(original.__globals__,frozen_observer=private_observer)
 selected=FunctionType(original.__code__,namespace,original.__name__,original.__defaults__,original.__closure__)
 selected.__kwdefaults__=original.__kwdefaults__
 return selected,dict(original_outside_CodeType_identical=selected.__code__ is original.__code__,
        old_factory_alias_and_SQL_patch_assembly_retained=True,old_module_globals_not_modified=True,
        no_registered_roots_or_books_removed=True,actual_health_or_owner_qualified=False)

def select_sample(original,job,plan,*,package_directory):
 need(type(original)is FunctionType and original.__name__=='sample' and
      hashlib.sha256(Path(original.__code__.co_filename).read_bytes()).hexdigest()==SAMPLER_PIN,
      'EXACT18_SAME_ORIGINAL_SAMPLE_FUNCTION')
 need(job['qualification_only']is False and plan['OWN_fixture']is None and
      Path(job['core_home']).is_relative_to(Path(job['new_root'])),
      'EXACT18_ONLY_ACTUAL_NEW_ARM_PRIVATE_RESOURCE_CHILD')
 outside=original.__globals__['outside_with_deadline'];registry=plan['outside_registry']
 selected,proof=select_outside(outside.__globals__['registered_outside_projection'],
      new_arm_root=job['new_root'],registry_path=registry['path'],registry_sha256=registry['sha256'],
      package_directory=package_directory)
 outside_ns=dict(outside.__globals__,registered_outside_projection=selected)
 outside_clone=FunctionType(outside.__code__,outside_ns,outside.__name__,outside.__defaults__,outside.__closure__)
 outside_clone.__kwdefaults__=outside.__kwdefaults__
 sample_ns=dict(original.__globals__,outside_with_deadline=outside_clone)
 sample=FunctionType(original.__code__,sample_ns,original.__name__,original.__defaults__,original.__closure__)
 sample.__kwdefaults__=original.__kwdefaults__
 need(sample.__code__ is original.__code__ and outside_clone.__code__ is outside.__code__,
      'EXACT18_ORIGINAL_OWNER_PARENT55S25S_AND_ALL_SAMPLE_BODY_UNCHANGED')
 return sample,dict(proof,original_sample_and_deadline_CodeTypes_identical=True)
