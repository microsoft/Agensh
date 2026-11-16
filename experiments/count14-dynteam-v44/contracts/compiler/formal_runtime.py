"""Formal regular 100M ports around ORIGINAL FINAL runtime and dispatcher.

Fresh real job/input/native services remain mandatory for original construction.
No no-job engine entry, fake snapshot or new experiment dispatcher is supplied.
"""
import ast
import copy
import inspect
from pathlib import Path
from types import MethodType
from common import need,digest,hash_file
import smoke_checkpoint_final_runtime as smoke_runtime
import smoke_checkpoint_final_scope as smoke_scope
from smoke_checkpoint_final_runtime import SmokeFinalRuntimeScope
from formal_scope import FormalCheckpointFinalScope,FORMAL_CUTS,_formal_body
from formal_ast import globals_clone,reversible,infrastructure_transform


def infrastructure_pins():
    import glm_session_header
    root=Path(__file__).resolve().parent
    names=('formal_ast.py','formal_scope.py','formal_runtime.py','formal_controller.py',
           'formal_final_child.py','formal_checkpoint.py')
    value={name:hash_file(root/name)['sha256'] for name in names}
    for module in (smoke_scope,smoke_runtime,__import__('smoke_checkpoint_final_controller'),glm_session_header):
        value[module.__name__+'.py']=hash_file(Path(module.__file__).resolve())['sha256']
    value['native_dynamic_checkpoint.py']=hash_file(Path(smoke_scope.__file__).resolve().with_name('native_dynamic_checkpoint.py'))['sha256']
    return value


_formal_install_body=globals_clone(smoke_runtime._install_body,CUTS=FORMAL_CUTS)
_formal_poll_body=globals_clone(smoke_runtime._poll_body)


class FormalFinalRuntimeScope(FormalCheckpointFinalScope,SmokeFinalRuntimeScope):
    def __init__(self,contract,*,contract_sha256,profile_registry=None):
        FormalCheckpointFinalScope.__init__(self,contract,contract_sha256=contract_sha256)
        self.profile_registry=copy.deepcopy(profile_registry)
        self.profile_registry_sha256=None if profile_registry is None else digest(profile_registry)
        if profile_registry is not None:
            need(type(profile_registry) is dict and set(profile_registry)=={'schema','contract_sha256','trajectories'} and
                 profile_registry['schema']=='count14-formal100m-final-scope-profile-registry-v1' and
                 profile_registry['contract_sha256']==self.sha and set(profile_registry['trajectories'])==set(self.rows),
                 'FORMAL_EXACT_ALL_SIX_PROFILE_REGISTRY')
            for entry in profile_registry['trajectories'].values():
                need(set(entry)=={'original_profile_sha256','protocol_sha256','scope_profile'} and
                    (entry['scope_profile'] is None and entry['protocol_sha256']==entry['original_profile_sha256']==
                     self.contract['v2_baseline_reference_protocol']['final_v21'] or
                     entry['scope_profile'] is not None and digest(entry['scope_profile'])==entry['protocol_sha256'] and
                     entry['scope_profile']['contract_sha256']==self.sha and
                     entry['scope_profile']['original_profile_sha256']==entry['original_profile_sha256'] and
                     entry['scope_profile']['infrastructure_source_sha256']==infrastructure_pins()),
                     'FORMAL_REGISTERED_OR_EXPLICIT_DERIVED_ORIGINAL_PROFILE_PIN')


def _method(function):
    constants={'_smoke_scope_sha256':'_formal100m_scope_sha256',
               'smoke_checkpoint_final_child.py':'formal_final_child.py'}
    attributes={'_smoke_scope_sha256':'_formal100m_scope_sha256'}
    tree=ast.parse(__import__('textwrap').dedent(inspect.getsource(function)));expected={}
    for node in ast.walk(tree):
        if isinstance(node,ast.Constant) and type(node.value) is str and node.value in constants:
            key='constant:'+node.value;expected[key]=expected.get(key,0)+1
        if isinstance(node,ast.Attribute) and node.attr in attributes:
            key='attribute:'+node.attr;expected[key]=expected.get(key,0)+1
    bindings={'CUTS':FORMAL_CUTS,'_scoped_body':_formal_body,'_install_body':_formal_install_body,
              '_poll_body':_formal_poll_body,'__file__':__file__}
    return reversible(function,infrastructure_transform(constants=constants,attributes=attributes),
        expected=expected,bindings=bindings) if expected else globals_clone(function,**bindings)


for _name,_function in SmokeFinalRuntimeScope.__dict__.items():
    if inspect.isfunction(_function) and _name!='__init__':
        setattr(FormalFinalRuntimeScope,_name,_method(_function))
