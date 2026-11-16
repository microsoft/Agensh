"""Private original native interfaces for the offline CONTROL carrier proposal."""
import ast,copy
from pathlib import Path
from types import MethodType,SimpleNamespace
from common import need,hash_file,publish,wire
from formal_ast import globals_clone,reversible
import allowance_native as first
import final_attempts,native_replicate_attempts
from queue_control import CarrierReader

# Only the typed control-reader port differs from the preceding private native
# adapter. Original binding/config/RNG body cloning and inverse proofs remain.
native_ports=globals_clone(first.native_ports,FormalAllowanceReader=CarrierReader)


def bind_scope(scope,reader=None):
    result=globals_clone(first.bind_scope,native_ports=native_ports)(scope,reader)
    previous=result.dispatcher
    def dispatcher(this,*args,**kwargs):
        value=previous(*args,**kwargs)
        value.entry=Path(__file__).with_name('queue_child.py');value.entry_pin=hash_file(value.entry)
        return value
    result.dispatcher=MethodType(dispatcher,result);return result


def original_dispose_without_enqueue():
    """Retain original proof/fee/PARTIAL bodies; separate control selection only.

    No proof relaxation or unknown cleanup. The original host proof must pass.
    Every next attempt is separately certified/registered by the original pure
    allowance policy, never automatically enqueued during a failed disposition.
    """
    class NoEnqueue(ast.NodeTransformer):
        def __init__(self,e):self.e=e
        def visit_If(self,n):
            if ast.unparse(n.test)=='attempt >= 3':
                value=copy.deepcopy(n);value.test=ast.Constant(True)
                return self.e.replace(n,value,'host_control_selects_next_not_dispose')
            return self.generic_visit(n)
    partial=reversible(final_attempts.partial_and_replace,NoEnqueue,
        expected={'host_control_selects_next_not_dispose':1})
    namespace=SimpleNamespace(**dict(vars(final_attempts),partial_and_replace=partial))
    class ExpectedNoEnqueue(ast.NodeTransformer):
        def __init__(self,e):self.e=e
        def visit_Call(self,n):
            if isinstance(n.func,ast.Name)and n.func.id=='need'and len(n.args)>1 and isinstance(n.args[1],ast.Constant)and n.args[1].value=='FINAL_REPLICATE_TWO_REPLACEMENTS_EXHAUSTED':
                value=copy.deepcopy(n);value.args[0]=ast.parse('new is None',mode='eval').body
                return self.e.replace(n,value,'control_requires_no_implicit_enqueue')
            return self.generic_visit(n)
    return reversible(native_replicate_attempts.dispose,ExpectedNoEnqueue,
        expected={'control_requires_no_implicit_enqueue':1},bindings={'final_attempts':namespace})


def publish_import_pins(destination):
    import formal_scope,smoke_checkpoint_final_scope,native_final_runtime,glm_session_header,dynteam_metadata
    roots=[]
    for root in [Path(__file__).resolve().parent,Path(first.__file__).resolve().parent,*[
        Path(m.__file__).resolve().parent for m in(formal_scope,smoke_checkpoint_final_scope,
            native_final_runtime,glm_session_header,dynteam_metadata)]]:
        if root not in roots:roots.append(root)
    value={'schema':'count14-formal100m-final-frozen-imports-v1','roots':[
        {'path':str(root),'files':{p.name:hash_file(p)['sha256']for p in sorted(root.glob('*.py'))}}for root in roots]}
    publish(destination,wire(value),mode=0o400);return Path(destination),hash_file(destination)['sha256']
