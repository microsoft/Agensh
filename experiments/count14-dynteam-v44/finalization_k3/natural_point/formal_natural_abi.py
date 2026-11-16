"""Prospective typed first-natural ABI; original label/RNG/math, no runtime grant.

New contract authority is explicitly NOT the old v2 message-policy receipt.
No prompt, task, candidate, snapshot or private record is read at import time.
"""
import ast
import copy
from common import need,digest
from formal_ast import reversible,globals_clone
from formal_scope import PUBLIC_CONTRACT_CANONICAL_SHA256,FORMAL_CUTS
import r16_natural_contract as original

POLICY = {
    'schema':'count14-formal100m-first-natural-scope-proposal-v1',
    'contract_sha256':PUBLIC_CONTRACT_CANONICAL_SHA256,
    'first_only':True,'continuous_idle_active_seconds':600,
    'search_budget_tokens':FORMAL_CUTS[-1],
    'retain_regular_targets':list(FORMAL_CUTS),
    'native_source_commit':'70e2ca54c078597e3314755064d2ef1a83344c8e',
    'native_idle_template_opaque_unread':True,
    'native_idle_template_frozen_metadata_sha256':'d4715047d462de60a02f40105207ba3547e36653d7eae68a3d99cc36e2f22a58',
    'native_watchdog_source_sha256':'8b5da992d5eae47484d85267927054ddf6b63a8751f47b07475b43d8ea93653c',
    'old_v2_policy_sha256_is_not_current_authority':original.POLICY_SHA,
    'snapshot_and_K3_enqueue_before_original_neutral':True,
    'no_force_spawn_or_retired_identity_revival':True,
    'financial_formulas_and_schema_unchanged':True,
}
POLICY_SHA=digest(POLICY)
KIND=original.KIND
NATURAL_RNG_POLICY={**copy.deepcopy(original.NATURAL_RNG_POLICY),'policy_sha256':POLICY_SHA}

class _BudgetAuthority(ast.NodeTransformer):
    def __init__(self,edits):self.edits=edits
    def visit_Constant(self,node):
        if node.value==20000000:
            return self.edits.replace(node,ast.Constant(FORMAL_CUTS[-1]),'current_registered_budget_bound')
        if node.value=='NATURAL_BEFORE_20M':
            return self.edits.replace(node,ast.Constant('FORMAL_NATURAL_BEFORE_CURRENT_REGISTERED_100M'), 'bound_PUBLIC_code')
        return node

metadata=reversible(original.metadata,_BudgetAuthority,
    expected={'current_registered_budget_bound':1,'bound_PUBLIC_code':1},bindings={'POLICY_SHA':POLICY_SHA})
natural=globals_clone(original.natural,POLICY_SHA=POLICY_SHA,metadata=metadata)
_original_label=globals_clone(original.label,metadata=metadata)
final_rng=globals_clone(original.final_rng,metadata=metadata,NATURAL_RNG_POLICY=NATURAL_RNG_POLICY)
natural_binding=globals_clone(original.natural_binding,metadata=metadata,NATURAL_RNG_POLICY=NATURAL_RNG_POLICY)


def label(target,meta=None):
    if meta is not None:return _original_label(target,meta)
    need(type(target)is int and target in FORMAL_CUTS,'FORMAL_NATURAL_REGULAR_LABEL_NOT_RELABELLED')
    return 's'+str(target//1_000_000)+'m'


def install_exact_label_abi(engine,code,meta):
    return globals_clone(original.install_exact_label_abi,label=label)(engine,code,meta)
