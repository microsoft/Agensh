"""NEW exact-class financial method graph, INERT and permanently quarantined.

This leaf does NOT implement a production activation/writer grant. A normal
INERT ticket and a separately verified source receipt only stage methods and
control metadata. No schema/constructor, transaction, request reclassification,
clock reset, old AUX domain retag or fake native handle is involved.

The separate, explicitly OWN-only writer qualification lives in
own_financial_handoff.py; production tickets cannot be consumed by it.
"""
from dataclasses import asdict,dataclass
from pathlib import Path
from types import MethodType
import copy
import importlib
import os
import threading
import time

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
from native_peer_registry import process_birth
from original_runtime_method_graph import (verify_sources,bind_original_v2_methods,
    bind_original_resource_methods,bind_original_aux_capacity_methods)

SOURCE_MODULE_SHA256='5d7aedc421df71583d55ec6ffc32cd80389c1f944ed93c3dcad99b433d38f906'
_SEAL=object()
_STAGED={}


def _refuse(*args,**kwargs):
    raise M.PaidColdWait('STAGED_FINANCE_INERT_SOURCE_IS_NOT_NORMAL_RUNNABLE_WRITER_AUTHORITY')


def _quarantine(value,cls):
    methods={name:getattr(value,name) for name in vars(cls) if not name.startswith('__') and
        callable(getattr(cls,name,None))}
    for name in methods:setattr(value,name,MethodType(_refuse,value))
    return methods


@dataclass(frozen=True)
class UnboundNativeCustody:
    scope: str
    source_controls: dict
    runtime_handle_transferred: bool=False
    physical_terminal_asserted_by_receiver: bool=False


@dataclass(frozen=True)
class UnboundAuthorizer:
    scope: str
    source_accounting_epoch: str
    callback_transferred: bool=False
    new_owner_authorized: bool=False


class StagedFinancialRuntime:
    def __init__(self,*args,**kwargs):_refuse()
    @property
    def safe_to_TERM(self):return False
    @property
    def paid_activation_authorized(self):return False
    @property
    def whole_runnable_ready(self):return False
    def public(self):
        return dict(PUBLIC_code='STAGED_FINANCE_NEW_ORIGINAL_METHOD_GRAPH_QUARANTINED',
            OWN=self.OWN,old_owner_birth=asdict(self.old_owner_birth),new_owner_birth=asdict(self.new_owner_birth),
            exact_original_Ledger_and_FinalQueue_types=True,same_original_database_inodes_and_real_lock_FDs=True,
            original_schema_migrations_or_constructors_called=False,source_fault_count=len(self.ledger.memory_faults),
            source_native_service_scope_count=len(self.ledger.native_services),
            unbound_native_custody_count=len(self.unbound_native_services),
            original_capacity_accounting_epoch_preserved=self.capacity is None or
                self.capacity.epoch==self.controls['capacity']['epoch'],
            source_authorizer_scopes_retained=len(self.unbound_authorizers),old_callables_or_handles_transferred=False,
            new_original_carrier_method_graph_retained=self.carrier is not None,
            production_transaction_or_request_or_dispatch_authority_implemented=False,
            current_resource_metadata_is_not_new_owner_admission_authority=True,
            methods_quarantined=not self.OWN_writer_open,whole_runnable_ready=False,safe_to_TERM=False,
            paid_activation_authorized=False,requests_replayed=0,original_formula_or_history_rewritten=False,
            method_graph_proofs=copy.deepcopy(self.method_proofs))


def _controls(row,context):
    M.need(type(row)is dict and row.get('schema')=='count14-original-financial-runtime-control-source-v1' and
        row.get('OWN') is context.OWN and row.get('source_financial_rules_or_history_modified') is False and
        row.get('source_connection_in_transaction') is False and row.get('whole_runnable_ready') is False and
        row.get('safe_to_TERM') is False,'STAGED_FINANCE_COMPLETE_FIXED_SOURCE_CONTROL_NOT_AUTHORITY')
    M.need(M.birth(row['source_owner_birth'])==context.old_owner_birth and
        row['contract_sha256']==M.digest(context.contract) and
        row['ledger_database']==context.ledger_database,
        'STAGED_FINANCE_SAME_SOURCE_BIRTH_ORIGINAL_CONTRACT_AND_LEDGER_INODE')
    M.existing(row['owner_marker'],private=True)
    M.need(Path(row['owner_marker']['path'])==context.ledger_home/'owner.open',
        'STAGED_FINANCE_ORIGINAL_OWNER_MARKER_NOT_REWRITTEN')
    M.need(type(row['memory_faults'])is dict and type(row['native_services'])is dict and
        row['native_service_count']==len(row['native_services']) and
        row['catalogues']=={t:list(r['roles']) for t,r in context.rows.items()},
        'STAGED_FINANCE_COMPLETE_FAULT_CUSTODY_AND_ROLE_MAPS_NO_EMPTY_DEFAULT')
    attrs=row['ledger_attribute_controls']
    M.need(set(attrs)=={'native_unmanaged_cli','_dynteam_qualification_only',
        'model_capacity_global_cap','model_capacity_owner_epoch'} and
        all(type(v)is dict and set(v)=={'present','value'} and type(v['present'])is bool for v in attrs.values()),
        'STAGED_FINANCE_EXPLICIT_ORIGINAL_CAPACITY_ATTRIBUTE_PRESENCE')
    M.need(attrs['_dynteam_qualification_only']==dict(present=True,value=context.OWN),
        'STAGED_FINANCE_OWN_NAMESPACE_NEVER_PRODUCTION_CAPABILITY')
    M.need(row['resources'] is not None and row['capacity'] is not None,
        'STAGED_FINANCE_WAIT_COMPLETE_ORIGINAL_RESOURCE_AND_CAPACITY_CONTROLS')
    capacity=row['capacity'];resource=row['resources']
    M.need(capacity['callable_or_old_process_handle_serialized']is False and
        capacity['new_owner_binding_qualified']is False and
        capacity['global_cap']==96 and capacity['aux_cap']==16 and
        attrs['model_capacity_global_cap']==dict(present=True,value=capacity['global_cap']) and
        attrs['model_capacity_owner_epoch']==dict(present=True,value=capacity['epoch']) and
        capacity['authorizer_callable_count']==len(capacity['authorizer_scope_keys']) and
        resource['registered_capacity_count']==1 and resource['expected_capacity_is_registered']is True and
        resource['current_observation_reused_for_new_owner_admission']is False,
        'STAGED_FINANCE_ORIGINAL_CAPACITY_DOMAIN_AND_RESOURCE_RELATIONSHIPS')
    return copy.deepcopy(row)


def _make(context,controls,*,read_budget,final_controls=None):
    from budget import Ledger
    from final_queue import FinalQueue
    from model_capacity import ModelCapacity
    from original_relay_core import OriginalRelayCore
    from new_scope_ledger import compiled_register
    from native_v2_dispositions import NativeV2Dispositions,original_v2
    from native_cohort_resources import (NativeCohortResources,CohortAllocation,
        original_mem_available,compiled_original_validator)
    M.need(type(read_budget)is ReadBudget,'STAGED_FINANCE_FINITE_FIXED_READ_BUDGET')
    read_budget.check();verify_sources()
    current=process_birth(os.getpid())
    M.need(current==context.new_owner_birth and M.nonexecuting(context.old_owner_birth,current),
        'STAGED_FINANCE_REAL_OLD_ENDED_NEW_BIRTH_NOT_INERT_FLAG_WRITE_GRANT')
    controls=_controls(controls,context)
    stage=object.__new__(StagedFinancialRuntime);stage._seal=_SEAL
    stage.context=context;stage.controls=controls;stage.OWN=context.OWN;stage.OWN_writer_open=False
    stage.old_owner_birth,stage.new_owner_birth=context.old_owner_birth,current
    stage.unbound_native_services={scope:UnboundNativeCustody(scope,copy.deepcopy(value))
        for scope,value in controls['native_services'].items()}
    l=Ledger.__new__(Ledger);q=FinalQueue.__new__(FinalQueue);core=OriginalRelayCore.__new__(OriginalRelayCore)
    l.home,l.fd,l.db,l.mutex=context.ledger_home,context.lock_fds[0],context.ledger_db,threading.RLock()
    l.capacity_changed=threading.Condition(l.mutex);l.owner_marker=Path(controls['owner_marker']['path'])
    l.memory_faults=copy.deepcopy(controls['memory_faults']);l.native_services=dict(stage.unbound_native_services)
    l._dynteam_catalogues={t:tuple(r) for t,r in controls['catalogues'].items()}
    for name,row in controls['ledger_attribute_controls'].items():
        if row['present']:setattr(l,name,copy.deepcopy(row['value']))
    frozen=l._dynteam_catalogues
    def limit(this,t,roles):
        M.need(t in frozen,'DYNTEAM_ONLY_REGISTERED_NEW_TRAJECTORIES')
        return len(frozen[t]) if tuple(roles)==frozen[t] else 16
    l._dynteam_catalogue_limit=MethodType(limit,l);l.register=MethodType(compiled_register(),l)
    config=context.queue_db.execute('SELECT manifest,cap FROM config WHERE singleton=1').fetchone()
    M.need(config is not None and config['manifest']==M.digest(context.contract) and config['cap']==12,
        'STAGED_FINANCE_ORIGINAL_FINAL_QUEUE_CONFIG_AND_MANIFEST')
    q.home,q.fd,q.db,q.mutex=context.queue_home,context.lock_fds[1],context.queue_db,threading.RLock()
    q.manifest,q.cap=config['manifest'],config['cap']
    core.home,core.contract,core.rows=context.owner_home,copy.deepcopy(context.contract),copy.deepcopy(context.rows)
    core.ledger,core.queue,core.qualification_only=l,q,context.OWN
    core.state='STAGED_FINANCIAL_QUARANTINED_NO_SCIENTIFIC_ACTIVATION';core.scientific_activation_qualified=False
    dispositions=NativeV2Dispositions.__new__(NativeV2Dispositions)
    dispositions.ledger,dispositions.original=l,original_v2()
    proofs=[bind_original_v2_methods(dispositions,l)];core.v2_dispositions=dispositions
    raw=controls['capacity'];capacity=ModelCapacity.__new__(ModelCapacity)
    capacity.ledger,capacity.global_cap,capacity.aux_cap=l,raw['global_cap'],raw['aux_cap']
    capacity.epoch,capacity.transport_pin,capacity.classifier_pin=raw['epoch'],raw['transport_pin'],raw['classifier_pin']
    capacity.authorizers={}
    stage.unbound_authorizers={s:UnboundAuthorizer(s,capacity.epoch) for s in raw['authorizer_scope_keys']}
    raw=controls['resources'];resources=NativeCohortResources.__new__(NativeCohortResources)
    allocation=CohortAllocation(**raw['allocation']);allocation.checked()
    resources.core,resources.ledger,resources.allocation=core,l,allocation
    resources.owner=current;resources.source_owner_birth=stage.old_owner_birth
    resources.contract_sha=M.digest(core.contract);resources.path=core.home/'resources/COHORT_RESOURCES_PUBLIC.json'
    resources.memory,resources.wall,resources.monotonic=original_mem_available,time.time_ns,time.monotonic_ns
    resources.validator,resources.predicate_proof=compiled_original_validator(core.contract['arms'][0]['root'])
    M.need(resources.predicate_proof==raw['predicate_proof'],
        'STAGED_FINANCE_ORIGINAL_RESOURCE_PREDICATES_UNCHANGED')
    resources.state=copy.deepcopy(raw['state']);resources.next_refresh_mono=raw['next_refresh_mono']
    launches=raw['launch_reservations']
    # Older source format legitimately supports only its empty map. A nonempty
    # JSON list is lossless tuple-key source metadata, never an empty default.
    if type(launches)is list:
        resources.launch_reservations={(r['trajectory'],r['role']):r['forecast_bytes'] for r in launches}
        M.need(len(resources.launch_reservations)==len(launches),'STAGED_FINANCE_UNIQUE_SOURCE_LAUNCH_RESERVATIONS')
    else:
        M.need(type(launches)is dict and not launches,'STAGED_FINANCE_WAIT_LOSSLESS_NONEMPTY_LAUNCH_CONTROLS')
        resources.launch_reservations={}
    resources.failures=copy.deepcopy(raw['failures']) if 'failures'in raw else None
    resources.capacities=[]
    proofs.append(bind_original_resource_methods(resources,l))
    proofs.append(bind_original_aux_capacity_methods(resources,capacity))
    carrier=None
    if final_controls is not None:
        from queue_control import CarrierQueueDomain
        carrier=CarrierQueueDomain.__new__(CarrierQueueDomain)
        carrier.q,carrier.l=q,l
        carrier.owner=copy.deepcopy(final_controls['original_control_owner'])
        carrier.pin=final_controls['original_queue']['descriptor_sha256']
        carrier.control=carrier.boundary=None;carrier.offline_OWN=context.OWN
        carrier.fresh=MethodType(_refuse,carrier)
        carrier._bind_private_original_ports(_refuse)
        # Preserve the original overlay/claim code graph. It remains UNBOUND:
        # old metadata lineage is not a new domain/claim authorization.
    stage.core,stage.ledger,stage.queue=core,l,q
    stage.capacity,stage.resources,stage.dispositions,stage.carrier=capacity,resources,dispositions,carrier
    stage.method_proofs=proofs
    import financial_runtime_source_control as source
    observed=controls['original_method_graph']
    M.need(set(observed)==set(source.METHODS) and all(
        observed[name]['semantic_code_sha256']==source.semantic_code_sha256(getattr(l,name).__func__.__code__)
        for name in source.METHODS),
        'STAGED_FINANCE_SAME_SOURCE_ACTUAL_LEDGER_OPERATION_CONSTANT_NAME_AND_CLOSURE_GRAPH')
    stage.original_source_method_semantics_equal=True
    stage._ledger_methods=_quarantine(l,Ledger);stage._queue_methods=_quarantine(q,FinalQueue)
    stage._resource_methods=_quarantine(resources,NativeCohortResources)
    stage._capacity_methods=_quarantine(capacity,ModelCapacity)
    stage._disposition_methods=_quarantine(dispositions,NativeV2Dispositions)
    _quarantine(core,OriginalRelayCore)
    read_budget.check();_STAGED[id(stage)]=stage
    return stage


def prepare_staged_financial_runtime(ticket,*,owner,read_budget):
    """Production: exact independent verifier + metadata pair, always INERT."""
    import hashlib
    from types import SimpleNamespace
    import normal_inert_cut as T
    from native_cold_owner import NativeColdOwner
    from original_relay_core import OriginalRelayCore
    M.need(type(ticket)is T.NormalInertTicket,'STAGED_FINANCE_PRODUCTION_TYPED_NORMAL_INERT_REFERENCE_ONLY')
    M.need(type(owner)is NativeColdOwner and type(owner.core)is OriginalRelayCore and
        not owner.core.ledger.mutex._is_owned() and not owner.core.queue.mutex._is_owned(),
        'STAGED_FINANCE_METADATA_SOURCE_IO_OUTSIDE_SCIENCE_LOCKS')
    module=importlib.import_module('financial_runtime_source_control')
    expected=Path(__file__).resolve().parents[1]/'formal100m-financial-runtime-source-control-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/financial_runtime_source_control.py'
    M.need(SOURCE_MODULE_SHA256 is not None and Path(module.__file__)==expected and
        expected.resolve()==expected and not expected.is_symlink() and
        hashlib.sha256(expected.read_bytes()).hexdigest()==SOURCE_MODULE_SHA256,
        'STAGED_FINANCE_WAIT_FROZEN_INDEPENDENT_SOURCE_VERIFIER')
    source=module.load_registered_source(owner,ticket=ticket,read_budget=read_budget)
    M.need(type(source)is module.VerifiedFinancialRuntimeSource,
        'STAGED_FINANCE_EXACT_INDEPENDENT_VERIFIED_SOURCE_RECEIPT')
    cap=T.verify_inert_ticket(ticket,owner=owner,read_budget=read_budget)
    pair=owner.core.metadata_inert_pair
    context=SimpleNamespace(OWN=False,old_owner_birth=cap.old_owner_birth,new_owner_birth=cap.new_owner_birth,
        contract=pair.material['contract'],rows=owner.core.rows,owner_home=owner.core.home,
        ledger_home=owner.core.ledger.home,queue_home=owner.core.queue.home,
        ledger_database=cap.ledger_database,queue_database=cap.queue_database,
        ledger_db=owner.core.ledger.db,queue_db=owner.core.queue.db,lock_fds=tuple(pair.lock_fds))
    return _make(context,source.controls['normal_financial_runtime_controls'],read_budget=read_budget,
        final_controls=cap.component('paid_FINAL_controls'))
