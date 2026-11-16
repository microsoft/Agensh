"""One formal six-track ORIGINAL FINAL controller, no new dispatcher/owner.

This WIP builds infrastructure only when an already-authorized real owner calls
preflight. It does not create an owner, activate production, or qualify 100M.
"""
import ast
import copy
from pathlib import Path
from common import need,digest,hash_file,publish,wire
from original_relay_core import OriginalRelayCore
import smoke_checkpoint_final_controller as smoke_controller
from smoke_checkpoint_final_controller import SmokeFinalController,FINAL_FIELDS
from formal_scope import FORMAL_CUTS,validate_contract
from formal_runtime import FormalFinalRuntimeScope,infrastructure_pins
from formal_ast import globals_clone,reversible


def publish_import_pins(destination):
    import formal_scope
    import smoke_checkpoint_final_scope
    import native_final_runtime
    import glm_session_header
    import dynteam_metadata
    roots=[]
    for module in (formal_scope,smoke_checkpoint_final_scope,native_final_runtime,glm_session_header,dynteam_metadata):
        root=Path(module.__file__).resolve().parent
        need(root.is_absolute() and root.resolve()==root and root.is_dir(),'FORMAL_PUBLIC_FRAMEWORK_SOURCE_ROOT')
        if root not in roots:roots.append(root)
    value={'schema':'count14-formal100m-final-frozen-imports-v1','roots':[
        {'path':str(root),'files':{p.name:hash_file(p)['sha256'] for p in sorted(root.glob('*.py'))}}
        for root in roots]}
    destination=Path(destination);publish(destination,wire(value),mode=0o400)
    return destination,hash_file(destination)['sha256']


class _ProfileMetadata(ast.NodeTransformer):
    def __init__(self,edits):self.edits=edits
    def visit_Constant(self,node):
        if node.value=='count14-smoke-final-derived-infrastructure-profile-v1':
            return self.edits.replace(node,ast.Constant('count14-formal100m-final-derived-infrastructure-profile-v1'),'formal_sidecar_schema')
        return node
    def visit_List(self,node):
        if [x.value for x in node.elts if isinstance(x,ast.Constant)]==[500000,1000000]:
            return self.edits.replace(node,ast.List(elts=[ast.Constant(c) for c in FORMAL_CUTS],ctx=ast.Load()),'formal_registered_cuts')
        if [x.value for x in node.elts if isinstance(x,ast.Constant)]==['s500000t','s1000000t']:
            return self.edits.replace(node,ast.List(elts=[ast.Constant('s'+str(c//1000000)+'m') for c in FORMAL_CUTS],ctx=ast.Load()),'original_regular_labels')
        return self.generic_visit(node)


derive_profile_registration=reversible(smoke_controller.derive_profile_registration,_ProfileMetadata,
    expected={'formal_sidecar_schema':1,'formal_registered_cuts':1,'original_regular_labels':1},
    bindings={'infrastructure_pins':infrastructure_pins})


_CONSTANTS={'smoke':'production',
 'count14-dynteam-smoke-final-controller-v1':'count14-dynteam-formal100m-final-controller-v1',
 'count14-smoke-final-scope-profile-registry-v1':'count14-formal100m-final-scope-profile-registry-v1',
 'count14-smoke-final-zero-model-import-v1':'count14-formal100m-final-zero-model-import-v1',
 'count14-smoke-final-static-profile-v1':'count14-formal100m-final-static-profile-v1',
 'smoke_checkpoint_final_child.py':'formal_final_child.py',
 '_smoke_scope_sha256':'_formal100m_scope_sha256'}
_KEYWORDS={name:name.replace('SMOKE','FORMAL') for name in (
 'COUNT14_SMOKE_FINAL_IMPORTS_PUBLIC','COUNT14_SMOKE_FINAL_IMPORTS_SHA256',
 'COUNT14_SMOKE_FINAL_PROFILE_PUBLIC','COUNT14_SMOKE_FINAL_PROFILE_SHA256')}


class _ControllerPrepare(ast.NodeTransformer):
    def __init__(self,edits):self.edits=edits
    def visit_Constant(self,node):
        if type(node.value) is str and node.value in _CONSTANTS:
            return self.edits.replace(node,ast.Constant(_CONSTANTS[node.value]),'constant:'+node.value)
        return node
    def visit_keyword(self,node):
        if node.arg in _KEYWORDS:
            value=copy.deepcopy(node);value.arg=_KEYWORDS[node.arg]
            return self.edits.replace(node,value,'keyword:'+node.arg)
        return self.generic_visit(node)
    def visit_Attribute(self,node):
        names={'smoke_final_scope_profiles':'formal_final_scope_profiles','_smoke_scope_sha256':'_formal100m_scope_sha256'}
        if node.attr in names:
            value=copy.deepcopy(node);value.attr=names[node.attr]
            return self.edits.replace(node,value,'attribute:'+node.attr)
        return self.generic_visit(node)
    def visit_Assign(self,node):
        if len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='baseline':
            need(isinstance(node.value,ast.SetComp),'FORMAL_ORIGINAL_BASELINE_ENUM_ASSIGNMENT_SITE')
            value=copy.deepcopy(node);value.value=ast.parse('set(core.rows)',mode='eval').body
            return self.edits.replace(node,value,'all_six_enabled_not_smoke_subset')
        return self.generic_visit(node)


_PREPARE_EXPECTED={'constant:smoke':1,'constant:count14-dynteam-smoke-final-controller-v1':1,
 'constant:count14-smoke-final-scope-profile-registry-v1':1,
 'constant:count14-smoke-final-zero-model-import-v1':1,'constant:count14-smoke-final-static-profile-v1':1,
 'constant:smoke_checkpoint_final_child.py':1,'constant:_smoke_scope_sha256':1,
 'keyword:COUNT14_SMOKE_FINAL_IMPORTS_PUBLIC':1,'keyword:COUNT14_SMOKE_FINAL_IMPORTS_SHA256':1,
 'keyword:COUNT14_SMOKE_FINAL_PROFILE_PUBLIC':1,'keyword:COUNT14_SMOKE_FINAL_PROFILE_SHA256':1,
 'attribute:smoke_final_scope_profiles':1,'attribute:_smoke_scope_sha256':1,
 'all_six_enabled_not_smoke_subset':1}


class FormalFinalController(SmokeFinalController):
    def public(self):
        value=SmokeFinalController.public(self)
        value.update(scope='FORMAL_100M_WIP',formal_cuts=list(FORMAL_CUTS),
                     expected_regular_points=24,expected_effective_K3_jobs=72,
                     actual_scope_qualified=False,formal_delivery_claimed=False)
        return value

    def close_after_drained(self):
        expected={digest({'trajectory':t,'target':target}) for t in self.core.rows for target in FORMAL_CUTS}
        need(self.core.queue.frontier()=={'COMPLETE':72} and set(self.dispatcher.points)==expected and
             all(p['audited'] is True for p in self.dispatcher.points.values()),
             'FORMAL_ONLY_ALL_SIX_FOUR_CUTS_ORIGINAL_EFFECTIVE_K3_COMPLETE')
        return SmokeFinalController.close_after_drained(self)


FormalFinalController._prepare=reversible(SmokeFinalController._prepare,_ControllerPrepare,
    expected=_PREPARE_EXPECTED,bindings={'SmokeFinalRuntimeScope':FormalFinalRuntimeScope,
        'derive_profile_registration':derive_profile_registration,'publish_import_pins':publish_import_pins,
        '__file__':__file__})


def create_formal_final_controller(core,config_path,config_sha256):
    need(type(core) is OriginalRelayCore and not core.qualification_only and
         not hasattr(core,'formal_final_controller') and not hasattr(core,'smoke_final_controller'),
         'FORMAL_ONE_SAME_ORIGINAL_CORE_FINAL_CONTROLLER')
    validate_contract(core.contract,digest(core.contract))
    result=FormalFinalController.__new__(FormalFinalController)
    result.core=core;result.state='CREATED_REQUIRES_PREFLIGHT';result.errors=[]
    result.config_path,result.config_sha256=config_path,config_sha256
    result.capacity=result.server=result.dispatcher=result.import_child=None
    core.formal_final_controller=result
    return result
