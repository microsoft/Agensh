"""Production constructor scope returning EXACT original DynamicCheckpointPorts.

Original step/preflight/DynamicCutWriter/CAS/collector/thaw remain unmodified.
Only registered formal scope, both actual arms and per-core registry are bound.
"""
import ast
import copy
from common import need,digest
from original_relay_core import OriginalRelayCore
from native_dynamic_checkpoint import DynamicCheckpointPorts
from smoke_bootstrap_task_ports import NewRootSourceTaskPorts
from formal_scope import FormalCheckpointFinalScope,validate_contract,SETTINGS
from formal_runtime import FormalFinalRuntimeScope
from formal_ast import reversible


class _ConstructorScope(ast.NodeTransformer):
    def __init__(self,edits):self.edits=edits
    def visit_ImportFrom(self,node):
        if node.module=='smoke_checkpoint_final_scope':
            # Keep original ctor isinstance ABI via its private import alias.
            return self.edits.replace(node,ast.ImportFrom(module='formal_scope',
                names=[ast.alias(name='FormalCheckpointFinalScope',asname='SmokeCheckpointFinalScope')],level=0),'formal_scope_import')
        return node
    def visit_Compare(self,node):
        wanted=ast.parse("core.rows[trajectory]['arm']=='DYNTEAM'",mode='eval').body
        if ast.dump(node,include_attributes=False)==ast.dump(wanted,include_attributes=False):
            return self.edits.replace(node,ast.parse("core.rows[trajectory]['arm'] in _formal_settings",mode='eval').body,'registered_both_arms')
        return self.generic_visit(node)
    def visit_Constant(self,node):
        if node.value=='_smoke_scope_sha256':return self.edits.replace(node,ast.Constant('_formal100m_scope_sha256'),'formal_instance_marker')
        if node.value=='smoke_checkpoint_ports':return self.edits.replace(node,ast.Constant('formal_checkpoint_ports'),'formal_registry_name')
        return node
    def visit_Attribute(self,node):
        if node.attr=='smoke_checkpoint_ports':
            result=copy.deepcopy(node);result.attr='formal_checkpoint_ports'
            return self.edits.replace(node,result,'formal_registry_attribute')
        return self.generic_visit(node)


_INITIALIZER = reversible(DynamicCheckpointPorts.__init__,_ConstructorScope,
    expected={'formal_scope_import':1,'registered_both_arms':1,'formal_instance_marker':2,
              'formal_registry_name':1,'formal_registry_attribute':3},
    bindings={'_formal_settings':SETTINGS})


def create_formal_checkpoint_ports(core,trajectory,*,scope,source_ports,pins,
                                   registered_refs=('refs/heads/main',),member_cap=1000000):
    need(type(core) is OriginalRelayCore and not core.qualification_only and
         type(scope) in (FormalCheckpointFinalScope,FormalFinalRuntimeScope) and
         type(source_ports) is NewRootSourceTaskPorts and source_ports.core is core and
         core.contract==scope.contract and digest(core.contract)==scope.sha,
         'FORMAL_TYPED_ORIGINAL_CORE_SCOPE_SOURCE_GRAPH')
    validate_contract(core.contract,scope.sha)
    result=DynamicCheckpointPorts.__new__(DynamicCheckpointPorts)
    _INITIALIZER(result,core,trajectory,scope=scope,source_ports=source_ports,pins=pins,
                 registered_refs=registered_refs,member_cap=member_cap)
    need(type(result) is DynamicCheckpointPorts,'FORMAL_NO_REPLACEMENT_CHECKPOINT_CLASS')
    return result
