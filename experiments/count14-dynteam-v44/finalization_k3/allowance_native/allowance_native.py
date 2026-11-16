"""Private native allowance guard ports, same original classes and formulas.

No global mutation, owner, job, request, assets or SQL operation. raw4 queue
installation and above4 domain are deliberately not inferred from guard code.
"""
import ast,copy,inspect
from pathlib import Path
from types import MethodType,SimpleNamespace
from common import need,digest,hash_file,publish,wire
from formal_ast import reversible,globals_clone
from final_binding import FinalBinding
from native_final_runtime import NativeFinalRuntime
import final_attempts,run_native_final_child
import smoke_checkpoint_final_scope as smoke_scope
import smoke_checkpoint_final_controller as smoke_controller
import formal_controller
from formal_runtime import FormalFinalRuntimeScope
from allowance_control import FormalAllowanceReader,FormalAllowanceControl


def native_ports(reader=None):
    need(reader is None or type(reader)is FormalAllowanceReader,'FORMAL_ALLOWANCE_EXACT_PUBLIC_READER')
    def allowed(point,k,a,**scope):
        need(type(a)is int and a>=1,'FORMAL_ALLOWANCE_ORIGINAL_ATTEMPT_TYPE')
        if a<=3:return True
        need(reader is not None,'FORMAL_ALLOWANCE_NO_HOST_PROOF_FOR_EXTRA_ATTEMPT')
        return reader.allowed(point,k,a,**scope)
    class BindingGuard(ast.NodeTransformer):
        def __init__(self,e):self.e=e
        def visit_Call(self,n):
            if isinstance(n.func,ast.Name)and n.func.id=='need'and len(n.args)>1 and isinstance(n.args[1],ast.Constant)and n.args[1].value=='FINAL_REPLICATE_ATTEMPT':
                v=copy.deepcopy(n);v.args[0]=ast.parse('_allowance_allowed(point_id,replicate_index,replicate_attempt,trajectory=trajectory,input_policy=input_policy_sha256)',mode='eval').body
                return self.e.replace(n,v,'same_host_attempt_guard')
            return self.generic_visit(n)
    init=reversible(FinalBinding.__init__,BindingGuard,expected={'same_host_attempt_guard':1},bindings={'_allowance_allowed':allowed})
    class RngGuard(ast.NodeTransformer):
        def __init__(self,e):self.e=e
        def visit_Call(self,n):
            if isinstance(n.func,ast.Name)and n.func.id=='need'and len(n.args)>1 and isinstance(n.args[1],ast.Constant)and n.args[1].value=='FINAL_REPLACEMENT_ATTEMPT':
                v=copy.deepcopy(n);v.args[0]=ast.parse('type(attempt)is int and attempt>1 and _allowance_allowed(point_id,replicate_id,attempt)',mode='eval').body
                return self.e.replace(n,v,'replacement_membership_only')
            return self.generic_visit(n)
    rng=reversible(final_attempts.request_rng,RngGuard,expected={'replacement_membership_only':1},bindings={'_allowance_allowed':allowed})
    class RequestImport(ast.NodeTransformer):
        def __init__(self,e):self.e=e
        def visit_ImportFrom(self,n):
            if n.module=='final_attempts'and len(n.names)==1 and n.names[0].name=='request_rng':
                return self.e.replace(n,ast.Assign(targets=[ast.Name('request_rng',ast.Store())],value=ast.Name('_allowance_request_rng',ast.Load())),'private_rng_lookup_only')
            return n
    bind_request=reversible(FinalBinding.bind_request,RequestImport,expected={'private_rng_lookup_only':1},bindings={'_allowance_request_rng':rng})
    class ConfigGuard(ast.NodeTransformer):
        def __init__(self,e):self.e=e
        def visit_Compare(self,n):
            if ast.unparse(n)=="config['replicate_attempt'] in (2, 3)":
                v=ast.parse("config['replicate_attempt']>1 and _allowance_allowed(config.get('point_id'),config.get('k'),config['replicate_attempt'])",mode='eval').body
                return self.e.replace(n,v,'exact_fields_same_host_attempt_guard')
            return self.generic_visit(n)
    fields=reversible(run_native_final_child.config_fields,ConfigGuard,
        expected={'exact_fields_same_host_attempt_guard':1},bindings={'_allowance_allowed':allowed})
    return SimpleNamespace(binding_init=init,request_rng=rng,bind_request=bind_request,
        config_fields=fields,allowed=allowed,original_binding_class=FinalBinding,
        original_runtime_class=NativeFinalRuntime,raw4_queue_installed=False)


def bind_scope(scope,reader=None):
    """Returns the EXACT original formal scope, retaining typed checkpoint ABI."""
    need(type(scope)is FormalFinalRuntimeScope and not hasattr(scope,'_formal_allowance_ports'),
         'FORMAL_ALLOWANCE_EXACT_ONCE_FORMAL_SCOPE')
    ports=native_ports(reader)
    class Factory(ast.NodeTransformer):
        def __init__(self,e):self.e=e
        def visit_alias(self,n):
            if n.name=='SMOKE_CUTS':return self.e.replace(n,ast.alias(name='FORMAL_CUTS',asname='SMOKE_CUTS'),'formal_cut_enumeration')
            return n
        def visit_Attribute(self,n):
            if isinstance(n.value,ast.Name)and n.value.id=='FinalBinding'and n.attr in('__init__','bind_request'):
                return self.e.replace(n,ast.Name('_allowance_'+('binding_init'if n.attr=='__init__'else'bind_request'),ast.Load()),'native_port:'+n.attr)
            return self.generic_visit(n)
    factory=reversible(smoke_scope.SmokeCheckpointFinalScope.final_binding,Factory,
        expected={'formal_cut_enumeration':1,'native_port:__init__':1,'native_port:bind_request':1},
        bindings={'_allowance_binding_init':ports.binding_init,'_allowance_bind_request':ports.bind_request})
    scope.final_binding=MethodType(factory,scope);scope._formal_allowance_ports=ports
    original_dispatcher=scope.dispatcher
    def dispatcher(this,*args,**kwargs):
        d=original_dispatcher(*args,**kwargs)
        d.entry=Path(__file__).with_name('allowance_final_child.py');d.entry_pin=hash_file(d.entry)
        return d
    scope.dispatcher=MethodType(dispatcher,scope)
    return scope


def publish_import_pins(destination):
    import formal_scope,smoke_checkpoint_final_scope,native_final_runtime,glm_session_header,dynteam_metadata
    roots=[]
    for root in [Path(__file__).resolve().parent,*[Path(m.__file__).resolve().parent for m in
        (formal_scope,smoke_checkpoint_final_scope,native_final_runtime,glm_session_header,dynteam_metadata)]]:
        if root not in roots:roots.append(root)
    value={'schema':'count14-formal100m-final-frozen-imports-v1','roots':[
        {'path':str(root),'files':{p.name:hash_file(p)['sha256']for p in sorted(root.glob('*.py'))}}for root in roots]}
    publish(destination,wire(value),mode=0o400);return Path(destination),hash_file(destination)['sha256']


def controller_prepare_body(control):
    """Compile/link only. A null control may compile, never authorize execution."""
    class Prepare(formal_controller._ControllerPrepare):
        def visit_Constant(self,n):
            if n.value=='smoke_checkpoint_final_child.py':
                return self.edits.replace(n,ast.Constant('allowance_final_child.py'),'constant:smoke_checkpoint_final_child.py')
            return super().visit_Constant(n)
        def visit_Assign(self,n):
            if len(n.targets)==1 and isinstance(n.targets[0],ast.Name)and n.targets[0].id=='env':
                v=copy.deepcopy(n)
                need(isinstance(v.value,ast.Call),'FORMAL_ALLOWANCE_ORIGINAL_ENV_ASSIGNMENT')
                for name,attribute in(('COUNT14_FORMAL_ALLOWANCE_CONTROL_PUBLIC','path'),('COUNT14_FORMAL_ALLOWANCE_CONTROL_SHA256','pin')):
                    expr='str(_allowance_control.path)'if attribute=='path'else'_allowance_control.reader.pin'
                    v.value.keywords.append(ast.keyword(arg=name,value=ast.parse(expr,mode='eval').body))
                # Apply all original formal keyword renames before replacing.
                v=self.generic_visit(v)
                return self.edits.replace(n,v,'same_host_control_environment')
            return super().visit_Assign(n)
    def scope_factory(*args,**kwargs):return bind_scope(FormalFinalRuntimeScope(*args,**kwargs),control.reader)
    expected=dict(formal_controller._PREPARE_EXPECTED,same_host_control_environment=1)
    return reversible(smoke_controller.SmokeFinalController._prepare,Prepare,expected=expected,
        bindings={'SmokeFinalRuntimeScope':scope_factory,'derive_profile_registration':formal_controller.derive_profile_registration,
                  'publish_import_pins':publish_import_pins,'_allowance_control':control,'__file__':__file__})


def create_allowance_final_controller(owner,config_path,config_sha256,*,control):
    """Explicit host hookup, not a second controller/owner or activation loop."""
    need(type(control)is FormalAllowanceControl and control.owner is owner and owner.core is control.core,
         'FORMAL_ALLOWANCE_SAME_OWNER_TYPED_CONTROL')
    control.fresh()
    c=formal_controller.create_formal_final_controller(owner.core,config_path,config_sha256)
    c._prepare=MethodType(controller_prepare_body(control),c)
    original_configuration=c.configuration
    def configuration(this,job):
        control.authorize_claim(job) # before any opaque copies/model launch
        return original_configuration(job)
    c.configuration=MethodType(configuration,c)
    c.allowance_control=control
    return c
