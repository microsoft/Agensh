"""Continue the ORIGINAL finite producer after a verified cross-owner epoch.

No first-cold constructor, pointer restamp, fake old Popen, or old directory
replay. A genuine original archive/transition capability is mandatory. The
new epoch's real first child remains the SAME Popen. Old records remain in
their sealed history/archive, not relabelled as current-owner Python handles.

This does not issue the NEXT SOURCE: the legacy history capture intentionally
still rejects this multi-epoch record layout until its full lineage is closed.
It does not restore SYSTEM, enable resources/finance/SDK, or release science.
"""
from dataclasses import dataclass
from pathlib import Path
from types import MethodType
import copy
import hashlib
import importlib
import os
import subprocess
import threading

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
from native_peer_registry import process_birth
from native_resource_producer import NativeResourceProducer, ResourceSamplerSources
import resource_epoch_transition_v3 as E

PINS = {
    'resource_epoch_transition_v3': 'a4efa66a5fb85a4611a56844dfd15f8398107671935238de510088021be98a7d',
    'resource_epoch_archive_v2': 'aa54e75ce3af53d4d257082e6159792d5a32b9966554c245fec7f371ae7e60c9',
    'native_resource_producer': 'c1187cd5195a3b431a6eabd330578bd911ebe3fc4405a1358944d750df48be07',
    'native_resource_sampler': '880ae285ee18ad75e4aec3ccc4aa024f63a8423128834c6468b885606349cec3',
}
PRODUCTION_PINS = {
    'normal_held_financial_writer': '686247ad8d2ca768abf1dc0085ac4a18e58419f37e2bceb61b152d8f8b413261',
    'new_owner_host_control': 'dadf6ce97da5a7f57d239ac7f4bbbdd397308745c36fa9575d48c524c6ecfb85',
    'native_control_host_restore': '99a9b4a52a30edb345552fba52a6f65844f0c723c61a63315b43ddd07940761c',
}
_SEAL = object()
_REG = {}
_ATTEMPTS = {}
_OWN_DISTINCT_CORES = {}
_METHODS = ('_outside', '_publish', 'poll', 'public', 'stop_admission', 'physical_clear')


def _pin(name, pin):
    module = importlib.import_module(name); p = Path(module.__file__)
    M.need(p.is_absolute() and p.resolve() == p and not p.is_symlink()
           and not p.stat().st_mode & 0o022 and hashlib.sha256(p.read_bytes()).hexdigest() == pin,
           'CONTINUING_RESOURCE_EXACT_FROZEN_ORIGINAL_SOURCE')
    return module


def verify_sources():
    for name, pin in PINS.items(): _pin(name, pin)
    E._sources()
    return dict(PINS)


def _budget(value):
    M.need(type(value) is ReadBudget, 'CONTINUING_RESOURCE_FINITE_METADATA_BUDGET')
    value.check()


def _production_graph(graph, record, budget):
    h, c, s = (_pin(name, pin) for name, pin in PRODUCTION_PINS.items())
    stage = graph.stage
    M.need(c.registered_stage_host_graph(stage) is graph and stage.OWN is False
           and graph.core is stage.core and s.current_native_controls(graph).graph is graph,
           'CONTINUING_RESOURCE_ACTUAL_REGISTERED_HELD_NATIVE_STAGE_REQUIRED')
    original = h._same(stage, budget, own=False)
    from native_cohort_resources import NativeCohortResources
    from native_container_retirement import NativeContainerRegistry
    from native_docker_scope import ScopedDocker
    M.need(original['owner'] is record['owner'] and original['ticket'] is record['ticket']
           and graph.registration.source_owner is record['owner']
           and graph.registration.source_ticket is record['ticket']
           and stage.new_owner_birth == record['birth']
           and type(stage.resources) is NativeCohortResources and stage.resources.core is stage.core
           and stage.resources.ledger is stage.ledger
           and type(graph.core.native_containers) is NativeContainerRegistry
           and type(graph.core.native_containers.docker) is ScopedDocker
           and graph.core.native_containers.docker.route.qualification_only is False
           and original['services'].snapshot() == record['history']._source.snapshot(),
           'CONTINUING_RESOURCE_SAME_T_SERVICES_NATIVE_DAEMON_AND_ORIGINAL_ALLOCATION')
    M.need(graph.core.gate.closed and not graph.core.gate.waiters
           and set(graph.core.gate.startup_held) == set(graph.core.rows),
           'CONTINUING_RESOURCE_SCIENCE_REMAINS_STARTUP_HELD')
    return original


def _anchor(record, budget):
    """Immutable archive/transition; never pretend the current pointer is old."""
    E._guard(record, budget, before_pointer=False)
    M.need(E._result(record, budget) == (record['result'], record['refs']['result'], record['canonical']),
           'CONTINUING_RESOURCE_TRUE_ORIGINAL_EPOCH_RESULT_AND_CHILD_RETAINED')
    expected = {Path(v['path']).name for v in record['refs'].values()}
    for ref in record['refs'].values():
        E.A._read(Path(ref['path']), mode=0o600, limit=131072, budget=budget, expected=ref)
    M.need({p.name for p in record['root'].iterdir()} == expected,
           'CONTINUING_RESOURCE_NO_UNKNOWN_OR_MISSING_TRANSITION_CONTROL')


@dataclass(frozen=True, repr=False)
class OWNPointerOnlyPort:
    """Explicit OWN pointer path port. NOT a NativeCohortResources manager."""
    path: Path


@dataclass(frozen=True, repr=False)
class ContinuingResourceReceiver:
    producer: NativeResourceProducer
    epoch: object
    graph: object
    owner: object
    old_history: object
    birth: object
    thread: int
    OWN: bool
    _seal: object

    def public(self):
        _current(self, ReadBudget())
        return dict(schema='count14-continuing-original-resource-producer-v1', OWN=self.OWN,
                    original_producer=self.producer.public(), old_sequence=self.old_history._snapshot['configuration']['sequence'],
                    original_retired_history_and_archive_retained=True,
                    current_epoch_records=len(self.producer.records), old_records_relabelled=False,
                    original_producer_methods_unchanged=True, original20s_cadence_and55s_child=True,
                    SYSTEM_restored=_registered_SYSTEM(self), resource_admission_or_writer_enabled=False,
                    native_poll_or_SDK_or_scientific_release=False,
                    next_SOURCE_multi_epoch_lineage_qualified=False, whole_runnable_ready=False)


def _normalize_absent_SYSTEM(core, registered):
    """New receiver RAM only: original registered=False is not hasattr(None)."""
    M.need(type(registered) is bool, 'CONTINUING_RESOURCE_EXACT_SOURCE_SYSTEM_PRESENCE')
    if not registered and 'system_health' in vars(core):
        M.need(vars(core)['system_health'] is None,
               'CONTINUING_RESOURCE_NEVER_ERASE_AN_ACTUAL_SYSTEM_COMPONENT')
        del core.system_health


def _original_SYSTEM_ready(value):
    registered = value.old_history._source.component('SYSTEM')['registered']
    core = value.producer.core
    if not registered:
        M.need(not hasattr(core, 'system_health'),
               'CONTINUING_RESOURCE_SOURCE_ABSENT_SYSTEM_MUST_REMAIN_ABSENT')
        return True
    # Actual original registry, not merely a scheduler-shaped object.
    # This is NOT a fresh health result or authority to bypass the600 fence.
    return _registered_SYSTEM(value)


def _registered_SYSTEM(value):
    registered = value.old_history._source.component('SYSTEM')['registered']
    core = value.producer.core
    if not registered: return False
    service = getattr(core, 'system_health', None)
    if service is None: return False
    original = _pin('retired_system_live_receiver',
        '4c3df1b4ac22d3e30b2da12173058f1b11bf787ad271b9f71d4c3ecc767a81c1')
    runtime = original._registered(service)
    M.need(runtime.owner.core is core and runtime.resource is core.cohort_resources
           and runtime.birth == value.birth and service.started is True
           and service.contract_sha == value.producer.contract_sha
           and getattr(runtime.owner, 'source_owner', None) is value.owner,
           'CONTINUING_RESOURCE_SYSTEM_ACTUAL_REGISTERED_SAME_NEW_CORE_AND_SOURCE_OWNER')
    return True


def _OWN_distinct_core(owner, core, record, budget, *, retained=None):
    """Explicit OWN only: original real manager, borrowed RO pair, no H claim."""
    from original_relay_core import OriginalRelayCore
    from budget import Ledger
    from final_queue import FinalQueue
    from native_cohort_resources import NativeCohortResources
    from types import SimpleNamespace
    pair = _pin('metadata_inert_pair',
        '83b2662daef394a6c3bb9cbfa46fc15a49c4382df7db5c963ec89a1f61b853da')
    original = _pin('retired_system_live_receiver',
        '4c3df1b4ac22d3e30b2da12173058f1b11bf787ad271b9f71d4c3ecc767a81c1')
    original.verify_sources()
    proof = pair.verify_OWN_registered_pair(owner, read_budget=budget)
    M.need(record['OWN'] is True and record['owner'] is owner and proof.owner is owner
           and proof.qualification_only is True and proof.new_owner_birth == record['birth']
           and type(core) is OriginalRelayCore and core.qualification_only is True
           and core is not owner.core and core.home == owner.core.home
           and core.contract == owner.core.contract and core.rows == owner.core.rows
           and type(core.ledger) is Ledger and type(core.queue) is FinalQueue
           and core.ledger is not owner.core.ledger and core.queue is not owner.core.queue
           and core.ledger.db is owner.core.ledger.db and core.queue.db is owner.core.queue.db
           and getattr(core, 'gate', None) is None and getattr(core, 'native_containers', None) is None,
           'CONTINUING_RESOURCE_OWN_DISTINCT_CORE_REAL_SOURCE_PAIR_AND_BORROWED_RO_HANDLES')
    for instance, cls in ((core.ledger, Ledger), (core.queue, FinalQueue)):
        for name in vars(cls):
            if name.startswith('__') or not callable(getattr(cls, name, None)): continue
            method = getattr(instance, name)
            M.need(type(method) is MethodType and method.__self__ is instance and method.__func__ is pair._refuse,
                   'CONTINUING_RESOURCE_OWN_ALL_FINANCIAL_AND_QUEUE_METHODS_STILL_QUARANTINED')
    resource = core.cohort_resources
    M.need(type(resource) is NativeCohortResources and resource.core is core and resource.ledger is core.ledger,
           'CONTINUING_RESOURCE_OWN_ACTUAL_ORIGINAL_RESOURCE_MANAGER_NOT_POINTER_PORT')
    old, _ = original._financial(owner, record['ticket'], record['history'], budget=budget, own=True)
    original._original_resource(SimpleNamespace(core=core), old, refresh=False, require_open=False)
    M.need(resource.allocation.inventory_sha256 == record['history']._snapshot['configuration']['inventory_sha256']
           and resource.allocation.other_maximum_FP8_inflight == record['history']._snapshot['plan']['other_maximum_FP8_inflight'],
           'CONTINUING_RESOURCE_OWN_ORIGINAL_INDEPENDENT_ALLOCATION_UNCHANGED')
    if retained is not None:
        M.need(retained['core'] is core and retained['owner'] is owner and retained['resource'] is resource
               and retained['seal'] is _SEAL,
               'CONTINUING_RESOURCE_OWN_DISTINCT_CONTEXT_EXACT_RETAINED_OBJECTS')
    return resource


def bind_OWN_distinct_core(owner, core, *, epoch, read_budget):
    """Actual OWN epoch/manager integration; NEVER a production graph port."""
    _budget(read_budget); verify_sources(); record = E._registered(epoch, True)
    E.verify_OWN_complete(epoch, read_budget=read_budget)
    resource = _OWN_distinct_core(owner, core, record, read_budget)
    M.need(resource._read() == record['value'],
           'CONTINUING_RESOURCE_OWN_MANAGER_MUST_USE_EXACT_REAL_NEW_CHILD_NOT_NUMERIC_REPLACEMENT')
    value = _build(core, epoch, record, None, own=True, budget=read_budget)
    _OWN_DISTINCT_CORES[id(value)] = dict(value=value, core=core, owner=owner, resource=resource, seal=_SEAL)
    _current(value, read_budget)
    return value


def _build(core, epoch, record, graph, *, own, budget):
    key = (id(core), id(epoch))
    M.need(key not in _ATTEMPTS and not hasattr(core, 'resource_producer'),
           'CONTINUING_RESOURCE_SINGLE_BIND_RETAIN_PARTIAL_NO_RETRY')
    _ATTEMPTS[key] = dict(core=core, epoch=epoch, phase='BINDING_NEW_RAM_ONLY')
    cfg = record['history']._snapshot['configuration']
    M.need(core.home == record['owner'].core.home and core.qualification_only is own
           and record['birth'] == process_birth(os.getpid())
           and type(record['child']) is subprocess.Popen and record['child'].poll() == 0,
           'CONTINUING_RESOURCE_REAL_CURRENT_EPOCH_POPEN_NOT_OLD_HANDLE_OR_BOOLEAN')
    argv = record['argv']; python = E._checked_sampler_sources(cfg)
    args = dict(cfg['sources'])
    for key in ('python', 'child', 'factory_manifest'): args[key] = Path(args[key])
    sources = ResourceSamplerSources(**args)
    M.need(argv[:4] == [python, '-I', '-B', str(sources.child)],
           'CONTINUING_RESOURCE_EXACT_ORIGINAL_FINITE_CHILD_ARGV')
    _normalize_absent_SYSTEM(core, record['history']._source.component('SYSTEM')['registered'])
    p = NativeResourceProducer.__new__(NativeResourceProducer)
    p.core, p.owner, p.contract_sha = core, record['birth'], record['history']._source.contract_sha256
    p.plan, p.plan_path = copy.deepcopy(record['history']._snapshot['plan']), Path(cfg['plan_path'])
    p.sources, p.inventory_sha = sources, cfg['inventory_sha256']
    p.home = core.home/'resources/producer'; E.A._directory(p.home, budget)
    p.records = [dict(child=record['child'], state='OBSERVATION_PUBLISHED', directory=record['root'],
                      job=copy.deepcopy(record['job']), intent_sha256=record['refs']['intent']['sha256'])]
    # New records only: old physical terminal handles are NOT recreated. Full
    # old records remain in the sealed source/history/archive of this binding.
    p.failures = copy.deepcopy(record['history']._source.component('resource')['original_public']['failures'])
    p.sequence = record['sequence']; p.next_due = record['started_mono_ns'] + 20*10**9
    M.need(p.next_due >= cfg['next_due'], 'CONTINUING_RESOURCE_NO_ORIGINAL_NEXT_DUE_REBASE')
    p.last_published = record['pointer_ref']['sha256']; p.accepting = False
    p.argv = (python, '-I', '-B', str(sources.child))
    value = ContinuingResourceReceiver(p, epoch, graph, record['owner'], record['history'],
                                      record['birth'], threading.get_ident(), own, _SEAL)
    _REG[id(value)] = value
    core.resource_producer = p  # first publication of actual RAM; no constructor or filesystem mutation
    _ATTEMPTS[(id(core), id(epoch))]['phase'] = 'REGISTERED_NOT_STARTED'
    return value


def bind_registered(graph, *, epoch, read_budget):
    _budget(read_budget); verify_sources()
    record = E._registered(epoch, False)
    E.verify_complete(epoch, read_budget=read_budget)
    _production_graph(graph, record, read_budget)
    stage = graph.stage; core = graph.core
    M.need(getattr(core, 'cohort_resources', None) is None,
           'CONTINUING_RESOURCE_NO_EXISTING_MANAGER_ALIAS_REPLACEMENT')
    M.need(stage.resources.allocation.inventory_sha256 == record['history']._snapshot['configuration']['inventory_sha256']
           and stage.resources.allocation.other_maximum_FP8_inflight == record['history']._snapshot['plan']['other_maximum_FP8_inflight'],
           'CONTINUING_RESOURCE_ORIGINAL_INDEPENDENT_STAGE_ALLOCATION_UNCHANGED')
    value = _build(core, epoch, record, graph, own=False, budget=read_budget)
    core.cohort_resources = stage.resources  # alias SAME original restored manager; methods remain quarantined
    return value


def bind_OWN_pointer_mechanics(owner, *, epoch, read_budget):
    """Actual OWN epoch/T/pair only; explicitly NOT stage/manager qualification."""
    _budget(read_budget); verify_sources(); record = E._registered(epoch, True)
    E.verify_OWN_complete(epoch, read_budget=read_budget)
    import metadata_inert_pair as pair
    proof = pair.verify_OWN_registered_pair(owner, read_budget=read_budget)
    M.need(record['owner'] is owner and owner.core.qualification_only is True
           and proof.owner is owner and proof.new_owner_birth == record['birth']
           and owner.core.gate is None and owner.core.native_containers is None
           and owner.core.cohort_resources is None,
           'CONTINUING_RESOURCE_OWN_UNHYDRATED_PAIR_NOT_A_FAKE_READY_MANAGER')
    value = _build(owner.core, epoch, record, None, own=True, budget=read_budget)
    owner.core.cohort_resources = OWNPointerOnlyPort(owner.core.home/'resources/COHORT_RESOURCES_PUBLIC.json')
    return value


def _current(value, budget):
    _budget(budget)
    M.need(type(value) is ContinuingResourceReceiver and value._seal is _SEAL and _REG.get(id(value)) is value
           and value.birth == process_birth(os.getpid()) and value.thread == threading.get_ident(),
           'CONTINUING_RESOURCE_SAME_REGISTERED_REAL_BIRTH_AND_OWNER_THREAD')
    record = E._registered(value.epoch, value.OWN); p = value.producer
    M.need(p.core.resource_producer is p and p.owner == value.birth and p.core.qualification_only is value.OWN
           and not p.core.ledger.mutex._is_owned() and not p.core.queue.mutex._is_owned(),
           'CONTINUING_RESOURCE_EXACT_PRODUCER_AND_IO_OUTSIDE_SCIENCE_LOCKS')
    for name in _METHODS:
        method = getattr(p, name)
        M.need(type(method) is MethodType and method.__self__ is p
               and method.__func__ is getattr(NativeResourceProducer, name),
               'CONTINUING_RESOURCE_ALL_ORIGINAL_UNMODIFIED_PRODUCER_METHODS')
    if value.OWN:
        import metadata_inert_pair as pair
        pair.verify_OWN_registered_pair(value.owner, read_budget=budget)
        distinct = _OWN_DISTINCT_CORES.get(id(value))
        if distinct is not None:
            M.need(distinct['value'] is value,
                   'CONTINUING_RESOURCE_OWN_DISTINCT_REGISTERED_BINDING_REQUIRED')
            _OWN_distinct_core(value.owner, p.core, record, budget, retained=distinct)
        elif id(value) in _OWN_STAGE_CORES:
            staged = _OWN_STAGE_CORES[id(value)]
            M.need(staged['value'] is value and staged['seal'] is _SEAL,
                   'CONTINUING_RESOURCE_OWN_H_STAGE_REGISTERED_BINDING_REQUIRED')
            _OWN_stage(value.owner, staged['stage'], record, budget)
        else:
            M.need(type(p.core.cohort_resources) is OWNPointerOnlyPort,
                   'CONTINUING_RESOURCE_OWN_PATH_PORT_NOT_A_PRODUCTION_MANAGER')
    else:
        _production_graph(value.graph, record, budget)
        M.need(p.core.cohort_resources is value.graph.stage.resources,
               'CONTINUING_RESOURCE_SAME_ORIGINAL_STAGE_RESOURCE_MANAGER_ALIAS')
    _anchor(record, budget)
    return record


def start(value, *, read_budget):
    _current(value, read_budget)
    attempt = _ATTEMPTS[(id(value.producer.core), id(value.epoch))]
    M.need(attempt['phase'] == 'REGISTERED_NOT_STARTED' and not value.producer.accepting,
           'CONTINUING_RESOURCE_ONE_EXPLICIT_CADENCE_START')
    if not _original_SYSTEM_ready(value):
        return dict(started=False, WAIT_ORIGINAL_SYSTEM_RECEIVER=True, Popen_started=False)
    value.producer.accepting = True; attempt['phase'] = 'ORIGINAL_CADENCE_STARTED'
    return dict(started=True, original_cadence20s=True)


def poll(value, *, read_budget):
    _current(value, read_budget)
    M.need(_ATTEMPTS[(id(value.producer.core), id(value.epoch))]['phase'] == 'ORIGINAL_CADENCE_STARTED',
           'CONTINUING_RESOURCE_EXPLICIT_START_REQUIRED')
    M.need(_original_SYSTEM_ready(value), 'CONTINUING_RESOURCE_WAIT_REAL_SYSTEM_RECEIVER_BEFORE_CADENCE')
    return value.producer.poll()  # ORIGINAL owner-loop cadence/Popen/publisher; no second dispatcher


_OWN_STAGE_CORES = {}
OWN_STAGE_PAIR_PIN = 'c455557d58b27e5d051c8e3f5fcaebc90dd9530089a61b5bc74686abe8e05f8d'

def _OWN_stage(owner, stage, record, budget):
    port = _pin('own_held_stage_pair_v3', OWN_STAGE_PAIR_PIN)
    registration = port.current_OWN_stage(stage, read_budget=budget)
    from native_cohort_resources import NativeCohortResources
    M.need(registration['owner'] is owner and registration['ticket'] is record['ticket']
           and record['owner'] is owner and record['OWN'] is True
           and stage.old_owner_birth == record['history']._source.old_owner_birth
           and stage.new_owner_birth == record['birth'] and stage.core is not owner.core
           and stage.core.home == owner.core.home and stage.core.contract == owner.core.contract
           and stage.core.rows == owner.core.rows and type(stage.resources) is NativeCohortResources
           and stage.resources is stage.core.cohort_resources and stage.resources.ledger is stage.ledger
           and stage.capacity.ledger is stage.ledger and not stage.capacity.authorizers
           and stage.capacity.epoch == stage.controls['capacity']['epoch'],
           'CONTINUING_RESOURCE_OWN_ACTUAL_ORIGINAL_H_STAGE_AND_SOURCE_PAIR_REQUIRED')
    original = _pin('retired_system_live_receiver',
        '4c3df1b4ac22d3e30b2da12173058f1b11bf787ad271b9f71d4c3ecc767a81c1')
    raw, _ = original._financial(owner, record['ticket'], record['history'], budget=budget, own=True)
    resource = original._original_resource(__import__('types').SimpleNamespace(core=stage.core),
        raw, refresh=False, require_open=False)
    return resource

def bind_OWN_stage(owner, stage, *, epoch, read_budget):
    _budget(read_budget); verify_sources()
    port = _pin('own_held_stage_pair_v3', OWN_STAGE_PAIR_PIN)
    port.current_OWN_stage(stage, read_budget=read_budget)
    record = E._registered(epoch, True)
    E.verify_OWN_complete(epoch, read_budget=read_budget)
    from native_cohort_resources import NativeCohortResources
    resource = stage.resources
    # Original read-only ports only; financial/queue/capacity stay quarantined.
    for name in ('_read','_current','_no_science_lock','refresh','maybe_refresh',
                 '_fresh','system_open','experiment_open','public'):
        setattr(resource,name,MethodType(getattr(NativeCohortResources,name),resource))
    _OWN_stage(owner, stage, record, read_budget)
    M.need(resource._read()==record['value'],
           'CONTINUING_RESOURCE_OWN_H_STAGE_USES_ACTUAL_FIRST_FINITE_RESULT')
    value = _build(stage.core, epoch, record, None, own=True, budget=read_budget)
    _OWN_STAGE_CORES[id(value)] = dict(value=value,stage=stage,owner=owner,resource=resource,seal=_SEAL)
    _current(value,read_budget)
    return value
