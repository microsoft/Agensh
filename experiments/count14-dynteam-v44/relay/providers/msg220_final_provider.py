"""One qualified new AUX child entry; all original controller/dispatcher code retained."""
from pathlib import Path
from types import FunctionType,MethodType
import ast,hashlib,inspect,os,stat,textwrap
CHILD_PIN='458af7d5a450674185565149bf10325b74eee890bb0f549c9abf83460838c283'
SELECTOR_PIN='d95469575e2ff34cc4ce5334c876605460f71bca55b84abe1b6491d16f6d3c67'
CONTROLLER_PIN='5a3197d12716e8ccf7072f52c3989e486fad15042e27d2458077738f6afe285c'
RUNTIME_PIN='4c6dc7435a33e669713851a2fa82530af5a85a9192afceaa99e89bd966bc292a'
def need(ok,code):
 if not ok:raise ValueError('MSG220_AUX_'+code)
def pin(path,sha):
 p=Path(path);s=p.lstat()
 need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and stat.S_ISREG(s.st_mode)and s.st_nlink==1 and not s.st_mode&0o022 and hashlib.sha256(p.read_bytes()).hexdigest()==sha,'CANONICAL_FROZEN_SOURCE_PIN')
 return p

def verify_sources(package_directory,*,selector,controller):
 home=Path(package_directory)
 child=pin(home/'msg220-final/smoke_checkpoint_final_child.py',CHILD_PIN)
 pin(selector.__file__,SELECTOR_PIN);pin(controller.__file__,CONTROLLER_PIN)
 original_scope=controller.SmokeFinalRuntimeScope
 dispatcher=original_scope.dispatcher
 pin(dispatcher.__code__.co_filename,RUNTIME_PIN)
 for fn in(controller.SmokeFinalController._prepare,dispatcher):
  tree=ast.parse(textwrap.dedent(inspect.getsource(fn)))
  need(sum(isinstance(n,ast.Name)and n.id=='__file__'for n in ast.walk(tree))==1,'ONE_ORIGINAL_CHILD_PATH_LOCATION_PER_FUNCTION')
 return child,original_scope

def final_controller_factory(selector,controller,*,package_directory):
 child,original_scope=verify_sources(package_directory,selector=selector,controller=controller)
 original_factory,proof=selector.final_controller_factory(controller)
 original_dispatch=original_scope.dispatcher
 def scope_constructor(*args,**kwargs):
  scope=original_scope(*args,**kwargs)
  selected=FunctionType(original_dispatch.__code__,dict(original_dispatch.__globals__,__file__=str(child)),original_dispatch.__name__,original_dispatch.__defaults__,original_dispatch.__closure__)
  selected.__kwdefaults__=original_dispatch.__kwdefaults__
  need(selected.__code__ is original_dispatch.__code__,'DISPATCH_ORIGINAL_COMPLETE_CODETYPE')
  scope.dispatcher=MethodType(selected,scope)
  return scope
 def create(core,config_path,config_sha256):
  obj=original_factory(core,config_path,config_sha256)
  original=obj._prepare.__func__
  need(original.__globals__['SmokeFinalRuntimeScope']is original_scope,'ORIGINAL_COLD_CONTROLLER_SCOPE_BEFORE_ONE_OVERLAY')
  selected=FunctionType(original.__code__,dict(original.__globals__,__file__=str(child),SmokeFinalRuntimeScope=scope_constructor),original.__name__,original.__defaults__,original.__closure__)
  selected.__kwdefaults__=original.__kwdefaults__
  need(selected.__code__ is original.__code__,'PREPARE_ORIGINAL_COMPLETE_CODETYPE')
  obj._prepare=MethodType(selected,obj)
  return obj
 return create,dict(proof,msg220_original_prepare_and_dispatch_CodeTypes_unchanged=True,registered_new_AUX_entry=dict(path=str(child),sha256=CHILD_PIN),old_framework_import_roots_and_scientific_profile_bytes_unmodified=True,original_request_seed_sampling_affinity_and_fees_retained=True,actual_target_AUX_request=None)
