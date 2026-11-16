"""Exact six-track production contract scope, original checkpoint/K3 functions.

No owner, queue, snapshot, evaluator or model is created by construction.
Only registered identity/roster/cut enumerations differ from the smoke adapter.
"""
import ast
import copy
import inspect
from types import MethodType
from common import need, digest, hash_file, strict
import smoke_checkpoint_final_scope as smoke
from smoke_checkpoint_final_scope import SmokeCheckpointFinalScope
from snapshot import CAS
from model_capacity import ModelCapacity
import v21_inputs
import native_k3
from formal_ast import globals_clone, reversible, infrastructure_transform

FORMAL_CUTS = (10_000_000,20_000_000,50_000_000,100_000_000)
SETTINGS = ('DYNTEAM','DYNTEAM_RACING')
PUBLIC_CONTRACT_FILE_SHA256 = '9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'
PUBLIC_CONTRACT_CANONICAL_SHA256 = '9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'
_formal_body = globals_clone(smoke._scoped_body, CUTS=FORMAL_CUTS)


def read_registered_contract(path, expected_file_sha256=PUBLIC_CONTRACT_FILE_SHA256):
    need(expected_file_sha256 == PUBLIC_CONTRACT_FILE_SHA256 and
         hash_file(path)['sha256'] == expected_file_sha256, 'FORMAL_REGISTERED_PRODUCTION_PUBLIC_FILE_PIN')
    contract = strict(open(path,'rb').read())
    validate_contract(contract, digest(contract));return contract


def validate_contract(contract, contract_sha256):
    need(type(contract) is dict and digest(contract) == contract_sha256 == PUBLIC_CONTRACT_CANONICAL_SHA256 and
         contract.get('schema') == 'count14-dynteam-two-arm-public-contract-v1' and
         contract.get('mode') == 'production', 'FORMAL_EXACT_REGISTERED_PRODUCTION_CONTRACT_NOT_SMOKE')
    rows=contract['trajectories']
    need(len(rows)==6 and len({r['trajectory_id'] for r in rows})==6 and
         {r['arm'] for r in rows}==set(SETTINGS) and
         all(sorted(r['block'] for r in rows if r['arm']==arm)==[1,2,3] for arm in SETTINGS) and
         all(r['checkpoints_tokens']==list(FORMAL_CUTS) and r['search_tokens']==FORMAL_CUTS[-1] and
             r['request_cap']==13 and r['fees_domain']=='SEARCH' and
             len(set(r['roles']))==len(r['roles']) and set(r['roles'])==set(r['role_kinds']) and
             len(r['roles'])==(34 if r['arm']=='DYNTEAM' else 42) and
             r['search_seed']==r['paired_v2_seed'] for r in rows),
         'FORMAL_SIX_PAIRED_FULL_ROLE_CATALOGUES_AND_100M_CUTS')
    need(contract['capacities']=={'AUX_total':16,'FINAL_jobs':12,'SEARCH_total':78,
         'SYSTEM_probe_reserved':2,'all_own_relay_physical':96,'per_track_SEARCH':13} and
         contract['finalization']['K']==3 and contract['finalization']['protocol']=='v2.1' and
         contract['finalization']['official_feedback_to_SEARCH'] is False and
         contract['finalization']['separate_AUX'] is True, 'FORMAL_ORIGINAL_CAPACITY_K3_NO_SEARCH_FEEDBACK')
    return True


def _formal_method(function):
    # Internal instance markers only; no scientific JSON/SQLite schema changes.
    source=inspect.getsource(function)
    constants={'_smoke_scope_sha256':'_formal100m_scope_sha256'} if "'_smoke_scope_sha256'" in source else {}
    attributes={'_smoke_scope_sha256':'_formal100m_scope_sha256'} if '._smoke_scope_sha256' in source else {}
    expected={}
    tree=ast.parse(__import__('textwrap').dedent(source))
    for node in ast.walk(tree):
        if isinstance(node,ast.Constant) and node.value in constants:
            key='constant:'+node.value;expected[key]=expected.get(key,0)+1
        if isinstance(node,ast.Attribute) and node.attr in attributes:
            key='attribute:'+node.attr;expected[key]=expected.get(key,0)+1
    bindings={'CUTS':FORMAL_CUTS,'_scoped_body':_formal_body}
    return reversible(function,infrastructure_transform(constants=constants,attributes=attributes),
                      expected=expected,bindings=bindings) if expected else globals_clone(function,**bindings)


class FormalCheckpointFinalScope(SmokeCheckpointFinalScope):
    def __init__(self,contract,*,contract_sha256):
        validate_contract(contract,contract_sha256)
        self.contract=copy.deepcopy(contract);self.sha=contract_sha256
        self.rows={r['trajectory_id']:r for r in self.contract['trajectories']}
        self._build=_formal_body(v21_inputs.build,cuts=True,roster=self._roster)
        self._verify=_formal_body(v21_inputs.verify_input,cuts=True)
        self._audit=_formal_body(native_k3.audit_three,settings=True,cuts=True,label=self.label)
        self._register=_formal_body(ModelCapacity.register_scope,settings=True,cuts=True)
        self._pause=_formal_body(ModelCapacity.pause,settings=True)
        from native_writer_fence import verify_sealed_writer_proof
        self._sealed=_formal_body(verify_sealed_writer_proof,participants=self._sealed_participants)
        self._snapshot_verify=_formal_body(CAS.verify_snapshot,
            snapshot_roster=self._snapshot_roster,sealed=self.verify_sealed_writer_proof)

    def label(self,target,natural_stop=None):
        need(type(target) is int and target in FORMAL_CUTS and natural_stop is None,
             'FORMAL_REGISTERED_REGULAR_POINT_NOT_SMOKE_OR_NATURAL')
        return 's'+str(target//1_000_000)+'m'

    def install_exact_label_abi(self,engine,code,*,target):
        # Original native regular parser already supports s10m/s20m/s50m/s100m.
        # Do NOT install the smoke exact-token/NATURAL_STOP engine expression.
        self.label(target);return None


for _name,_method in SmokeCheckpointFinalScope.__dict__.items():
    if inspect.isfunction(_method) and _name not in ('__init__','label','install_exact_label_abi','final_binding'):
        setattr(FormalCheckpointFinalScope,_name,_formal_method(_method))


class _FormalFinalRNGImport(ast.NodeTransformer):
    def __init__(self,edits):self.edits=edits
    def visit_alias(self,node):
        if node.name=='SMOKE_CUTS':
            return self.edits.replace(node,ast.alias(name='FORMAL_CUTS',asname='SMOKE_CUTS'),'formal_rng_enumeration')
        return node

FormalCheckpointFinalScope.final_binding = reversible(SmokeCheckpointFinalScope.final_binding,
    _FormalFinalRNGImport,expected={'formal_rng_enumeration':1},bindings={'CUTS':FORMAL_CUTS})
