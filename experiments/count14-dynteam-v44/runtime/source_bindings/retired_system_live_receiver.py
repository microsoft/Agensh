"""Independent SYSTEM rehydration, not a financial/native/scientific restore.

The original paid0/existing-dir constructor is UNCHANGED and is never called.
A real old-source closed history, original typed new-birth T/three-lock pair,
independent original financial allocation source and an ACTUAL freshly bound
original resource manager are mandatory. No metadata object or supplied bool
is a health source. No START is repeated; original poll/child/body are reused.

A separate real new-epoch monotonic fence delays admission at least 600s.
The old intent wall AND old monotonic values remain the exact source values.
No shortened clock, synthetic old-monotonic, HTTP replay or forced signal.
"""
from dataclasses import asdict
from pathlib import Path
from types import MethodType,FunctionType,CodeType
import copy, hashlib, importlib, json, os, stat, threading, time, marshal, math

PINS = {'retired_system_history': '448802312193a2ef4b5f3fe2b35ff2d65a3ffef8c3cc158c1f46b37b1a3d3ed5', 'financial_runtime_source_control': '5d7aedc421df71583d55ec6ffc32cd80389c1f944ed93c3dcad99b433d38f906', 'native_system_health': '9786f682727d02392ef53431b793df030525c4bac7ba5b0555ee75c5ecb37163', 'native_system_probe_child': '0b0435eaabc7bf65419c05e0ea33a4139e1978360c63b94bff74915bc56d4ebe', 'native_cohort_resources': '26d1181e98dbf9972b517c1cb621f2b16d0d84780eef9bea83ab9eca7755ebb5', 'normal_inert_cut': 'aac25e6b4f30c199a84d1ac7f5652283585f259f93a2d3f4a3e3134c9f203262', 'metadata_inert_pair': '83b2662daef394a6c3bb9cbfa46fc15a49c4382df7db5c963ec89a1f61b853da', 'native_resource_producer': 'c1187cd5195a3b431a6eabd330578bd911ebe3fc4405a1358944d750df48be07', 'native_resource_sampler': '880ae285ee18ad75e4aec3ccc4aa024f63a8423128834c6468b885606349cec3'}
_SEAL=object()
_REGISTERED={}
PARENT='system-live-receiver-epochs-v1'


def need(ok,code):
    if not ok:raise ValueError(code)

def verify_sources():
    need(bool(PINS),'SYSTEM_LIVE_WAIT_FROZEN_ORIGINAL_INPUT_PINS')
    for name,pin in PINS.items():
        p=Path(importlib.import_module(name).__file__);s=p.lstat()
        need(p.resolve()==p and stat.S_ISREG(s.st_mode)and s.st_nlink==1 and not s.st_mode&0o022 and
             s.st_uid in(0,os.geteuid())and hashlib.sha256(p.read_bytes()).hexdigest()==pin,
             'SYSTEM_LIVE_EXACT_ORIGINAL_SOURCE_MODULES')


def _same_code(actual,expected):
    # marshal rejects unsupported objects, instead of evaluating arbitrary
    # equality on attacker-selected CodeType constants.
    if type(actual)is not CodeType or type(expected)is not CodeType:return False
    try:return marshal.dumps(actual)==marshal.dumps(expected)
    except (TypeError,ValueError):return False


def _same_plain(actual,expected):
    kind=type(expected)
    if type(actual)is not kind:return False
    if kind in(type(None),bool,int,float,complex,str,bytes):
        if kind is float and(not math.isfinite(actual)or not math.isfinite(expected)):return False
        if kind is complex and(not math.isfinite(actual.real)or not math.isfinite(actual.imag)or
                             not math.isfinite(expected.real)or not math.isfinite(expected.imag)):return False
        return actual==expected
    if kind is dict:
        if not all(type(k)is str for k in actual)or not all(type(k)is str for k in expected):return False
        return set(actual)==set(expected)and all(_same_plain(actual[k],expected[k])for k in expected)
    if kind in(list,tuple):return len(actual)==len(expected)and all(_same_plain(a,b)for a,b in zip(actual,expected))
    return False


def _same_namespace(actual,expected):
    # Function globals are trusted only as exact builtin dict/string keys.
    # No dict override, custom key comparison, callable __eq__, module proxy,
    # or str/int subclass is ever invoked by this predicate.
    if type(actual)is not dict or type(expected)is not dict:return False
    if not all(type(k)is str for k in actual)or not all(type(k)is str for k in expected):return False
    if set(actual)!=set(expected):return False
    scalars=(type(None),bool,int,float,complex,str,bytes)
    for key,want in expected.items():
        if key=='__builtins__':
            # Same interpreter-owned dictionary, never a caller replacement.
            if actual[key]is not want:return False
            continue
        got=actual[key]
        if got is want:continue
        kind=type(want)
        if kind in scalars:
            if type(got)is not kind:return False
            if kind is float and(not math.isfinite(got)or not math.isfinite(want)):return False
            if kind is complex and(not math.isfinite(got.real)or not math.isfinite(got.imag)or
                                 not math.isfinite(want.real)or not math.isfinite(want.imag)):return False
            if got!=want:return False # both values have exact immutable builtin type
            continue
        if kind is FunctionType and want.__globals__ is expected:
            if type(got)is not FunctionType or got.__globals__ is not actual or not _same_code(got.__code__,want.__code__):return False
            continue
        # Trusted modules/classes/callables and every other object require
        # identity. Generated helpers are the sole closed-namespace exception.
        return False
    return True


def _original_resource(owner,raw,*,refresh,require_open=True):
    from native_cohort_resources import NativeCohortResources,CohortAllocation,compiled_original_validator,original_mem_available
    from native_peer_registry import process_birth
    import paid_cold_material as M
    core=owner.core;r=core.cohort_resources
    need(type(r)is NativeCohortResources and type(r.allocation)is CohortAllocation and
         r.core is core and r.ledger is core.ledger and r.owner==process_birth(os.getpid())and
         r.contract_sha==M.digest(core.contract)and asdict(r.allocation)==raw['allocation']and
         _same_plain(r.predicate_proof,raw['predicate_proof'])and r.path==core.home/'resources/COHORT_RESOURCES_PUBLIC.json',
         'SYSTEM_LIVE_ACTUAL_NEW_OWNER_ORIGINAL_RESOURCE_AND_SAME_SOURCE_ALLOCATION')
    r.allocation.checked()
    for name in ('_read','_current','_no_science_lock','refresh','maybe_refresh','_fresh','system_open'):
        method=getattr(r,name)
        need(type(method)is MethodType and method.__self__ is r and
             method.__func__ is getattr(NativeCohortResources,name),
             'SYSTEM_LIVE_NO_METADATA_BOOL_OR_REPLACED_RESOURCE_METHOD')
    validate,proof=compiled_original_validator(core.contract['arms'][0]['root'])
    need(type(r.validator)is FunctionType and _same_code(r.validator.__code__,validate.__code__)and
         _same_plain(r.predicate_proof,proof) and _same_namespace(r.validator.__globals__,validate.__globals__),
         'SYSTEM_LIVE_UNMODIFIED_ORIGINAL_NUMERIC_RESOURCE_PREDICATES')
    need(r.wall is time.time_ns and r.monotonic is time.monotonic_ns and
         (core.qualification_only or r.memory is original_mem_available),
         'SYSTEM_LIVE_REAL_NEW_EPOCH_CLOCKS_NOT_OLD_OBSERVATION_REBASE')
    if not core.qualification_only:
        from native_container_retirement import NativeContainerRegistry
        from native_docker_scope import ScopedDocker
        registry=core.native_containers
        need(type(registry)is NativeContainerRegistry and registry.core is core and
             type(registry.docker)is ScopedDocker and registry.docker.route.qualification_only is False,
             'SYSTEM_LIVE_REAL_ORIGINAL_NEW_OWNER_NATIVE_PRIVATE_DAEMON_BINDING_REQUIRED')
        registry.docker.verify_daemon()
    if refresh:r.refresh() # actual original reader/validator/daemon, never a caller health bool
    if not core.qualification_only:_sampler_provenance(owner,r,raw['producer_control'])
    need(not require_open or r.system_open(),'SYSTEM_LIVE_WAIT_GENUINE_FRESH_NEW_OWNER_RESOURCE_ADMISSION')
    return r


def _sampler_provenance(owner,resources,old_control):
    from native_resource_producer import NativeResourceProducer,ResourceSamplerSources
    from native_resource_sampler import read_public
    from native_system_probe_child import read_control
    from native_peer_registry import process_birth
    import subprocess
    need(old_control['registered']is True,'SYSTEM_LIVE_PRODUCTION_WAIT_ORIGINAL_REGISTERED_SAMPLER_SOURCE')
    old=old_control['configuration'];p=owner.core.resource_producer
    need(type(p)is NativeResourceProducer and type(p.sources)is ResourceSamplerSources and
         p.core is owner.core and p.owner==process_birth(os.getpid())and
         p.contract_sha==resources.contract_sha and p.inventory_sha==resources.allocation.inventory_sha256==old['inventory_sha256']and
         str(p.plan_path)==old['plan_path']and
         {k:str(v)if isinstance(v,Path)else v for k,v in asdict(p.sources).items()}==old['sources']and
         p._publish.__func__ is NativeResourceProducer._publish and p.poll.__func__ is NativeResourceProducer.poll,
         'SYSTEM_LIVE_PRODUCTION_ONLY_REAL_REGISTERED_NEW_OWNER_ORIGINAL_FINITE_SAMPLER')
    plan,raw=read_public(p.plan_path)
    need(hashlib.sha256(raw).hexdigest()==p.inventory_sha and plan==p.plan and plan['OWN_fixture']is None and
         plan['other_maximum_FP8_inflight']==resources.allocation.other_maximum_FP8_inflight,
         'SYSTEM_LIVE_PRODUCTION_COMPLETE_ORIGINAL_PLAN_NOT_HANDWRITTEN_GREEN_RECEIPT')
    completed=[x for x in p.records if x['state']=='OBSERVATION_PUBLISHED']
    need(bool(completed),'SYSTEM_LIVE_PRODUCTION_NEEDS_GENUINE_NEW_OWNER_SAMPLER_COMPLETION')
    record=completed[-1];child=record['child']
    need(type(child)is subprocess.Popen and child.poll()==0,
         'SYSTEM_LIVE_REAL_SAMPLER_POPEN_PHYSICAL_EXIT0_NOT_BOOLEAN')
    result=json.loads(read_control(record['directory']/'RESULT_PUBLIC.json',131072))
    published=json.loads(read_control(record['directory']/'PUBLISHED_PUBLIC.json',131072))
    value=result['value'];encoded=(json.dumps(value,sort_keys=True,allow_nan=False)+chr(10)).encode()
    need(result['owner']==asdict(p.owner)and result['intent_sha256']==record['intent_sha256']and
         result['factory_constructor_called']is False and value['qualification_only']is False and
         value['OWN_fixture_host_projection_used']is False and
         published['restamped']is False and published['source_observed_ns']==value['observed_ns']and
         published['value_sha256']==p.last_published==hashlib.sha256(encoded).hexdigest()and
         resources._read()==value,
         'SYSTEM_LIVE_PRODUCTION_RESOURCE_IS_ACTUAL_ORIGINAL_CHILD_RESULT_NOT_COPIED_OR_RESTAMPED')


def _financial(owner,ticket,history,*,budget,own):
    """Independent OLD allocation source, not a new caller's CohortAllocation."""
    import financial_runtime_source_control as F
    import paid_cold_material as M
    if not own:
        source=F.load_registered_source(owner,ticket=ticket,read_budget=budget)
        need(type(source)is F.VerifiedFinancialRuntimeSource and source._seal is F._SEAL and
             source.OWN is False and source.old_owner_birth==history._source.old_owner_birth and
             source.new_owner_birth==history._source.new_owner_birth and
             source.contract_sha256==history._source.contract_sha256,
             'SYSTEM_LIVE_INDEPENDENT_ORIGINAL_FINANCIAL_SOURCE_SAME_T_AND_BIRTHS')
        raw=source.controls['normal_financial_runtime_controls']
        ref=copy.deepcopy(source._reference)
    else:
        # Explicit OWN component decoder only. The history verifier already
        # owns the three REAL original FDs; do not acquire a second lock set.
        body,ref=F._read_complete(owner.core.home,own=True,budget=budget)
        need(body['OWN']is True and body['original_ticket']is None and
             body['old_owner_birth']==asdict(history._source.old_owner_birth)and
             body['contract_sha256']==history._source.contract_sha256 and
             body['storage']['owner_home']==M.descriptor(owner.core.home)and
             body['locks']==[[k,row]for k,row in owner.core.metadata_inert_pair.control_lock_records]and
             body['current_fixed_db_controls']==F._db_controls(
                 owner.core.ledger.home/'ledger.sqlite',owner.core.queue.home/'queue.sqlite',budget),
             'SYSTEM_LIVE_OWN_INDEPENDENT_ORIGINAL_ISSUED_FINANCIAL_SOURCE_SAME_THREE_LOCKS')
        raw=body['normal_financial_runtime_controls']
    need(raw['source_owner_birth']==asdict(history._source.old_owner_birth)and
         raw['contract_sha256']==history._source.contract_sha256 and type(raw['resources'])is dict and
         raw['resources']['current_observation_reused_for_new_owner_admission']is False,
         'SYSTEM_LIVE_SOURCE_ALLOCATION_IS_NOT_NEW_OWNER_ADMISSION')
    resource=copy.deepcopy(raw['resources']);resource['producer_control']=history._source.component('resource')
    return resource,ref


def _registered(service):
    from native_system_health import NativeSystemHealth
    from native_peer_registry import process_birth
    import normal_inert_cut as T
    value=_REGISTERED.get(id(service))
    need(type(service)is NativeSystemHealth and value is not None and value.service is service and
         value._seal is _SEAL and value.thread==threading.get_ident()and
         value.owner.core.system_health is service and value.owner.core.metadata_inert_pair is value.pair and
         not value.pair.closed and process_birth(os.getpid())==service.owner==value.birth,
         'SYSTEM_LIVE_SAME_REGISTERED_REAL_NEW_OWNER_THREAD_AND_SERVICE')
    service._outside()
    need(not value.owner.core.queue.mutex._is_owned(),'SYSTEM_LIVE_OUTSIDE_BOTH_ORIGINAL_SCIENTIFIC_LOCKS')
    T._validate_owned_locks(value.pair.lock_fds,[row for kind,row in value.pair.control_lock_records])
    return value


def _guarded_poll(service):
    from native_system_health import NativeSystemHealth
    runtime=_registered(service)
    # No alternate clock or extended TTL: manager methods/consumer remain original.
    runtime.resource.maybe_refresh()
    _original_resource(runtime.owner,runtime.resource_source,refresh=False,require_open=False)
    if time.monotonic_ns()<runtime.new_epoch_mono+600*10**9:
        need(not any(r['state']=='RUNNING'for r in service.records),
             'SYSTEM_LIVE_NO_REQUEST_CAN_PRECEDE_REAL_NEW_EPOCH_FENCE')
        return NativeSystemHealth.public(service)
    # Exact original poll enforces both its ORIGINAL wall and monotonic600s,
    # SYSTEM2 UNKNOWN occupancy and real resource TTL, and owns the real Popen.
    return NativeSystemHealth.poll(service)


class LiveSystemReceiver:
    def __init__(self,*a,**k):raise ValueError('SYSTEM_LIVE_ONLY_FIXED_ORIGINAL_TYPED_NEW_BIRTH_RESTORE')
    @property
    def paid_activation_authorized(self):return False
    @property
    def whole_runnable_ready(self):return False
    def poll(self):return self.service.poll()
    def stop_admission(self):
        _registered(self.service);self.service.stop_admission()
    def public(self):
        _registered(self.service)
        return dict(schema='count14-original-independent-SYSTEM-live-receiver-v1',
            original_system=self.service.public(),old_source_sequence=self.source_sequence,
            current_sequence=self.service.sequence,original_START_and_session_preserved=True,
            original_last_intent_wall_and_monotonic_not_rebased=True,
            new_epoch_mono=self.new_epoch_mono,new_epoch_wall=self.new_epoch_wall,
            real_new_epoch600s_elapsed=time.monotonic_ns()-self.new_epoch_mono>=600*10**9,
            old_source_owner=asdict(self.history._source.old_owner_birth),new_owner=asdict(self.birth),
            actual_original_poll_and_child_used=True,original_resource_manager_required=True,
            resource_source_is_not_fresh_admission=True,independent_SYSTEM_only=True,
            scientific_or_native_runtime_restored=False,paid_activation_authorized=False,whole_runnable_ready=False)


def _restore(reference,*,history_reference,owner,ticket,read_budget,own):
    verify_sources()
    import retired_system_history as H
    import paid_cold_material as M
    from native_system_health import NativeSystemHealth,SystemProbeSources,executable
    from native_system_probe_child import read_control,original,append
    from native_peer_registry import process_birth
    from bounded_metadata_ro import ReadBudget
    need(type(read_budget)is ReadBudget,'SYSTEM_LIVE_FINITE_ORIGINAL_METADATA_BUDGET')
    history=(H.read_OWN_history if own else H.read_history)(reference,history_reference=history_reference,
        owner=owner,ticket=ticket,read_budget=read_budget)
    need(type(history)is H.VerifiedSystemHistory and history._seal is H._SEAL and history.OWN is own,
         'SYSTEM_LIVE_ONLY_FRESH_ORIGINAL_CLOSED_HISTORY_VERIFIER')
    cfg=history._source.component('SYSTEM');data=history._snapshot
    need(cfg['registered']and cfg['configuration']['started']and data['records']and
         owner.core.system_health is None and not any(x.owner is owner for x in _REGISTERED.values()),
         'SYSTEM_LIVE_REQUIRES_ORIGINAL_EXPLICIT_START_AND_KEY_BOUND_INTENT_NO_SECOND_BIND')
    raw=cfg['configuration'];current=process_birth(os.getpid())
    need(current==history._source.new_owner_birth and current!=history._source.old_owner_birth and
         raw['home']==str(owner.core.home/'system-health')and raw['accepting']is False,
         'SYSTEM_LIVE_TRUE_NEW_BIRTH_EXISTING_EXACT_STOPPED_ORIGINAL_HOME')
    old_resources,financial_ref=_financial(owner,ticket,history,budget=read_budget,own=own)
    resource=_original_resource(owner,old_resources,refresh=True)
    # All key/endpoint choices derive from the OLD closed raw INTENT controls.
    # No key body/hash is emitted; credentials remain only original trusted RAM/child.
    intents=[]
    for record in data['records']:
        p=record['directory']/'INTENT_PUBLIC.json';intent,ref=H.control(p,read_budget)
        need(ref in history._references,'SYSTEM_LIVE_KEY_AND_ENDPOINT_ONLY_OLD_CLOSED_INTENT')
        intents.append(intent)
    need(len({r['key_path']for r in intents})==1 and (own or all(r['OWN_endpoint']is None for r in intents)),
         'SYSTEM_LIVE_NO_NEW_KEY_ENDPOINT_OR_HISTORICAL_AFFINITY_CHANGE')
    key=Path(intents[-1]['key_path']);read_control(key,4096) # original fixed trusted read, never export
    endpoint=intents[-1]['OWN_endpoint']
    sources=SystemProbeSources(**{k:Path(v)if k in('python','child')else v for k,v in raw['sources'].items()})
    argv=(executable(sources.python,sources.python_sha256),'-I','-B',
          executable(sources.child,sources.child_sha256,child=True))
    P=original();need(raw['unmeasured_upper']==len(json.dumps(P.BODY).encode())+8192+256+P.OUTPUT,
                      'SYSTEM_LIVE_ORIGINAL_FIXED_PROBE_BODY_AND_UPPER_UNCHANGED')
    # Refuse stale/detached history once again BEFORE the append-only epoch and RAM bind.
    again=(H.read_OWN_history if own else H.read_history)(reference,history_reference=history_reference,
        owner=owner,ticket=ticket,read_budget=read_budget)
    need(again._snapshot==history._snapshot and again._references==history._references,
         'SYSTEM_LIVE_SOURCE_DRIFT_BEFORE_FIRST_RESTORED_OBJECT_RETAIN_NO_RETRY')
    resource=_original_resource(owner,old_resources,refresh=True)
    epoch_mono,epoch_wall=time.monotonic_ns(),time.time_ns()
    parent=owner.core.home/PARENT
    if not parent.exists():parent.mkdir(mode=0o700)
    H.private_directory(parent)
    leaf=parent/(str(current.pid)+'-'+str(current.start_ticks));leaf.mkdir(mode=0o700)
    append(leaf/'RESTORE_PUBLIC.json',dict(schema='count14-original-SYSTEM-live-epoch-v1',
        old_owner=asdict(history._source.old_owner_birth),new_owner=asdict(current),
        contract_sha256=history._source.contract_sha256,source_sequence=raw['sequence'],
        new_epoch_mono=epoch_mono,new_epoch_wall=epoch_wall,minimum_new_epoch_seconds=600,
        history_source_sha256=history_reference._pin,financial_source=financial_ref,
        original_last_intent_wall=raw['last_intent_wall'],original_last_intent_mono=raw['last_intent_mono'],
        START_repeated=False,old_monotonic_rebased=False,paid_activation_authorized=False,whole_runnable_ready=False))
    service=object.__new__(NativeSystemHealth)
    service.core,service.sources,service.key_path=owner.core,sources,key
    service.argv,service.owner,service.contract_sha=argv,current,history._source.contract_sha256
    service.home,service.sequence,service.records=Path(raw['home']),raw['sequence'],copy.deepcopy(data['records'])
    service.last_intent_wall,service.last_intent_mono=raw['last_intent_wall'],raw['last_intent_mono']
    service.wall,service.monotonic=time.time_ns,time.monotonic_ns
    service.endpoint,service.accepting,service.started=endpoint,True,True
    service.unmeasured_upper,service.session_id=raw['unmeasured_upper'],data['session_id']
    runtime=object.__new__(LiveSystemReceiver)
    runtime.owner,runtime.pair,runtime.birth=owner,owner.core.metadata_inert_pair,current
    runtime.thread,runtime.history,runtime.service=threading.get_ident(),history,service
    runtime.resource,runtime.resource_source=resource,old_resources
    runtime.new_epoch_mono,runtime.new_epoch_wall=epoch_mono,epoch_wall
    runtime.source_sequence,runtime.epoch_directory,runtime.OWN=raw['sequence'],leaf,own
    runtime._seal=_SEAL
    _REGISTERED[id(service)]=runtime;service.poll=MethodType(_guarded_poll,service)
    owner.core.system_health=service
    need(service.public()==cfg['original_public']|{'accepting':True},
         'SYSTEM_LIVE_ORIGINAL_PUBLIC_TOTALS_NONE_UPPER_AND_EXPLICIT_START_PRESERVED')
    return runtime


def restore(reference,*,history_reference,owner,ticket,read_budget):
    return _restore(reference,history_reference=history_reference,owner=owner,ticket=ticket,read_budget=read_budget,own=False)

def restore_OWN(reference,*,history_reference,owner,ticket,read_budget):
    return _restore(reference,history_reference=history_reference,owner=owner,ticket=ticket,read_budget=read_budget,own=True)
