"""SYSTEM receiver on the NEW held stage, with the original T/source owner.

Original history/financial verifiers receive the original registered metadata
owner. Original live resource/scheduler operations receive a distinct explicit
new-core view, never a forged T owner. Exactly THREE original restore call
sites change context; all original service/key/history/timer/probe guards stay.
Only resource READ/observation methods are exposed before the financial writer.
No constructor, fresh START, timer rebase, paid/SDK/scientific release or Popen.
"""
from dataclasses import dataclass
from pathlib import Path
from types import MethodType
import ast
import copy
import hashlib
import importlib
import inspect
import os
import textwrap
import threading

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
from native_peer_registry import process_birth
import retired_system_live_receiver as L
import retired_system_history as K
import normal_inert_cut as T
import metadata_inert_pair as P

PINS = {
    'retired_system_live_receiver': '4c3df1b4ac22d3e30b2da12173058f1b11bf787ad271b9f71d4c3ecc767a81c1',
    'retired_system_history': '448802312193a2ef4b5f3fe2b35ff2d65a3ffef8c3cc158c1f46b37b1a3d3ed5',
    'normal_inert_cut': 'aac25e6b4f30c199a84d1ac7f5652283585f259f93a2d3f4a3e3134c9f203262',
    'metadata_inert_pair': '83b2662daef394a6c3bb9cbfa46fc15a49c4382df7db5c963ec89a1f61b853da',
    'native_system_health': '9786f682727d02392ef53431b793df030525c4bac7ba5b0555ee75c5ecb37163',
    'native_cohort_resources': '26d1181e98dbf9972b517c1cb621f2b16d0d84780eef9bea83ab9eca7755ebb5',
}
PRODUCTION_PINS = {
    'normal_held_financial_writer': '686247ad8d2ca768abf1dc0085ac4a18e58419f37e2bceb61b152d8f8b413261',
    'staged_financial_runtime': '62de21eed76372cbe6d6721da10891d0a86e4cfc65dbbdbbf22294b3e49baba5',
    'resource_epoch_continuing_producer_v3': '4c8d354515fe46bcdfe5401905901b1b63793c1778da47631a7ba2131bac4a60',
}
READ_METHODS = ('_read', '_current', '_no_science_lock', 'refresh', 'maybe_refresh',
                '_fresh', 'system_open', 'experiment_open', 'public')
_SEAL = object()
_ATTEMPTS = {}
_REG = {}


def _pin(name, pin):
    module = importlib.import_module(name); p = Path(module.__file__)
    M.need(p.is_absolute() and p.resolve() == p and not p.is_symlink()
           and not p.stat().st_mode & 0o022 and hashlib.sha256(p.read_bytes()).hexdigest() == pin,
           'STAGE_SYSTEM_EXACT_FROZEN_ORIGINAL_COMPONENTS')
    return module


def verify_sources():
    for name, pin in PINS.items(): _pin(name, pin)
    L.verify_sources(); K.verify_sources()
    return dict(PINS)


def _budget(value):
    M.need(type(value) is ReadBudget, 'STAGE_SYSTEM_FINITE_METADATA_BUDGET')
    value.check()


@dataclass(frozen=True, repr=False)
class StageSystemOwnerView:
    """Live-core context ONLY. Never a NativeColdOwner or T/pair capability."""
    core: object
    source_owner: object


def _private_restore(source_owner):
    """Fixed original AST plus2 history owner keywords and1 financial owner."""
    verify_sources()
    original = ast.parse(textwrap.dedent(inspect.getsource(L._restore)))
    tree = copy.deepcopy(original); changes = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call): continue
        f = node.func
        history = (isinstance(f, ast.IfExp)
                   and isinstance(f.body, ast.Attribute) and f.body.attr == 'read_OWN_history'
                   and isinstance(f.orelse, ast.Attribute) and f.orelse.attr == 'read_history')
        if history:
            fields = [k for k in node.keywords if k.arg == 'owner']
            M.need(len(fields) == 1 and isinstance(fields[0].value, ast.Name)
                   and fields[0].value.id == 'owner', 'STAGE_SYSTEM_FIXED_ORIGINAL_HISTORY_OWNER_SITE')
            changes.append((fields[0], copy.deepcopy(fields[0])))
            fields[0].value = ast.Name(id='_stage_source_owner', ctx=ast.Load())
        elif isinstance(f, ast.Name) and f.id == '_financial':
            M.need(isinstance(node.args[0], ast.Name) and node.args[0].id == 'owner',
                   'STAGE_SYSTEM_FIXED_ORIGINAL_FINANCIAL_OWNER_SITE')
            changes.append((node, copy.deepcopy(node)))
            node.args[0] = ast.Name(id='_stage_source_owner', ctx=ast.Load())
    M.need(len(changes) == 3, 'STAGE_SYSTEM_EXACT_TWO_HISTORY_ONE_FINANCIAL_CONTEXT_EDITS')
    reverse = copy.deepcopy(tree)
    for changed, before in changes:
        hits = [n for n in ast.walk(reverse) if type(n) is type(changed)
                and getattr(n, 'lineno', None) == getattr(changed, 'lineno', None)
                and getattr(n, 'col_offset', None) == getattr(changed, 'col_offset', None)
                and ast.dump(n, include_attributes=False) == ast.dump(changed, include_attributes=False)]
        M.need(len(hits) == 1, 'STAGE_SYSTEM_UNIQUE_ORIGINAL_CONTEXT_INVERSE')
        hits[0].__dict__.update(copy.deepcopy(before.__dict__))
    M.need(ast.dump(reverse, include_attributes=False) == ast.dump(original, include_attributes=False),
           'STAGE_SYSTEM_ALL_OTHER_ORIGINAL_RESTORE_GUARDS_CODE_UNCHANGED')
    namespace = {}; globals_ = dict(vars(L), _stage_source_owner=source_owner)
    exec(compile(ast.fix_missing_locations(tree), __file__ + ':original-context-only-restore', 'exec'), globals_, namespace)
    return namespace['_restore']


def _read_ports(core):
    from native_cohort_resources import NativeCohortResources
    r = core.cohort_resources
    M.need(type(r) is NativeCohortResources and r.core is core and r.ledger is core.ledger,
           'STAGE_SYSTEM_SAME_ACTUAL_NEW_RESOURCE_MANAGER_NOT_POINTER_PORT')
    previous = {name: getattr(r, name) for name in READ_METHODS}
    for name in READ_METHODS:
        setattr(r, name, MethodType(getattr(NativeCohortResources, name), r))
    return r, previous


def _registered_production(graph, binding, budget, *, before_restore=False):
    h, staged, q = (_pin(name, pin) for name, pin in PRODUCTION_PINS.items())
    M.need(type(binding) is q.ContinuingResourceReceiver and binding.OWN is False
           and binding.graph is graph, 'STAGE_SYSTEM_ONLY_GENUINE_PRODUCTION_SAME_STAGE_RESOURCE_BINDING')
    epoch = q._current(binding, budget)
    record = h._same(graph.stage, budget, own=False)
    M.need(record['owner'] is binding.owner is epoch['owner'] and record['ticket'] is epoch['ticket']
           and graph.core is graph.stage.core and binding.producer.core is graph.core,
           'STAGE_SYSTEM_ORIGINAL_T_SOURCE_OWNER_DISTINCT_FROM_NEW_CORE')
    if before_restore:
        M.need(record['writer'] is None, 'STAGE_SYSTEM_NO_PREMATURE_FINANCIAL_WRITER')
        for name in h._FINANCIAL:
            method = getattr(graph.stage.ledger, name)
            M.need(type(method) is MethodType and method.__self__ is graph.stage.ledger
                   and method.__func__ is staged._refuse,
                   'STAGE_SYSTEM_ALL_FINANCIAL_METHODS_STILL_ORIGINAL_QUARANTINE')
        M.need(not binding.producer.accepting and binding.producer.physical_clear(),
               'STAGE_SYSTEM_CONTINUING_CADENCE_NOT_STARTED_BEFORE_SYSTEM_BIND')
    return record, epoch


def _current(service, budget):
    _budget(budget)
    record = _REG.get(id(service))
    M.need(type(record) is dict and record['service'] is service and record['seal'] is _SEAL
           and record['birth'] == process_birth(os.getpid()) and record['thread'] == threading.get_ident()
           and record['view'].core.system_health is service,
           'STAGE_SYSTEM_SAME_REGISTERED_REAL_SERVICE_NEW_CORE_BIRTH_AND_THREAD')
    runtime = L._registered(service)  # genuine original live runtime + real3 owned locks
    M.need(runtime is record['runtime'] and runtime.owner is record['view'],
           'STAGE_SYSTEM_ORIGINAL_LIVE_RECEIVER_REGISTRY_NOT_DATACLASS_SHAPE')
    if record['OWN']:
        proof = P.verify_OWN_registered_pair(record['source_owner'], read_budget=budget)
        M.need(proof.new_owner_birth == record['birth'] and proof.owner.core is not record['view'].core,
               'STAGE_SYSTEM_OWN_TRUE_PAIR_AND_DISTINCT_NEW_CORE')
    else:
        _registered_production(record['graph'], record['binding'], budget)
    return record


def _stage_poll(service):
    _current(service, ReadBudget())
    return L._guarded_poll(service)  # original real600s fence/cadence/key/body/child, no extra dispatcher


def _restore_new_core(source_owner, core, *, reference, history_reference, ticket,
                      graph, binding, read_budget, own):
    _budget(read_budget); verify_sources()
    M.need(id(core) not in _ATTEMPTS and source_owner.core is not core,
           'STAGE_SYSTEM_ONE_NEW_CORE_ATTEMPT_NOT_SOURCE_REPLACEMENT_OR_RETRY')
    pair = getattr(core, 'metadata_inert_pair', None)
    M.need(getattr(core, 'system_health', None) is None
           and (pair is None or pair is source_owner.core.metadata_inert_pair),
           'STAGE_SYSTEM_NO_EXISTING_SERVICE_OR_FOREIGN_PAIR_REPLACEMENT')
    view = StageSystemOwnerView(core, source_owner)
    record = dict(view=view, source_owner=source_owner, ticket=ticket, graph=graph, binding=binding,
                  birth=process_birth(os.getpid()), thread=threading.get_ident(), OWN=own,
                  phase='RESTORING_ORIGINAL_SYSTEM_NEW_CORE', runtime=None, service=None, seal=_SEAL)
    _ATTEMPTS[id(core)] = record  # retain every real partial before any new-core alias/epoch write
    resource, previous = None, {}
    try:
        core.metadata_inert_pair = source_owner.core.metadata_inert_pair
        core.system_health = None  # source already proved registered; not a scheduler or healthy-zero assertion
        resource, previous = _read_ports(core)
        runtime = _private_restore(source_owner)(reference, history_reference=history_reference,
            owner=view, ticket=ticket, read_budget=read_budget, own=own)
        service = runtime.service
        M.need(L._registered(service) is runtime and runtime.owner is view
               and service.core is core and source_owner.core.system_health is None,
               'STAGE_SYSTEM_REAL_ORIGINAL_RUNTIME_ON_NEW_NOT_SOURCE_CORE')
        record['runtime'], record['service'] = runtime, service
        _REG[id(service)] = record
        M.need(service.poll.__func__ is L._guarded_poll,
               'STAGE_SYSTEM_ORIGINAL_GUARDED_POLL_BEFORE_TYPED_NEW_STAGE_WRAPPER')
        service.poll = MethodType(_stage_poll, service)
        record['phase'] = 'REGISTERED_ORIGINAL_SYSTEM_REAL600_FENCE'
        _current(service, read_budget)
        return runtime
    except BaseException as error:
        record['phase'] = 'PARTIAL_RETAINED_NO_RETRY'; record['failure_type'] = type(error).__name__
        # A late original refusal may already have registered a real service.
        # Retain it and close admission normally, never signal or fake wait.
        service = getattr(core, 'system_health', None)
        if service is not None:
            record['service'] = service; record['runtime'] = L._REGISTERED.get(id(service))
            try: service.stop_admission()
            except Exception: pass
        for name, method in previous.items(): setattr(resource, name, method)
        raise


def restore_registered(graph, *, resource_binding, read_budget):
    _budget(read_budget)
    record, epoch = _registered_production(graph, resource_binding, read_budget, before_restore=True)
    source = record['services'].component('SYSTEM')
    M.need(source['registered'] is True and source['configuration']['started'] is True,
           'STAGE_SYSTEM_ONLY_ORIGINAL_REGISTERED_AND_STARTED_SYSTEM_NO_FRESH_START')
    home = graph.core.home
    marker, _ = M.private_read(home/K.LEAF_NAME/'ISSUED_PUBLIC.json', limit=262144)
    history = K.load_reference(home/K.LEAF_NAME/'SOURCE_PUBLIC.json', marker['source_sha256'])
    return _restore_new_core(record['owner'], graph.core,
        reference=epoch['archive']._reference, history_reference=history, ticket=record['ticket'],
        graph=graph, binding=resource_binding, read_budget=read_budget, own=False)


def restore_OWN_cross_core(source_owner, new_core, *, reference, history_reference, ticket, read_budget):
    """OWN context adaptation only. Not a production T/stage/provenance PASS."""
    _budget(read_budget); verify_sources()
    from original_relay_core import OriginalRelayCore
    from budget import Ledger
    from final_queue import FinalQueue
    proof = P.verify_OWN_registered_pair(source_owner, read_budget=read_budget)
    M.need(type(ticket) is T.OWNNormalInertTicket and proof.qualification_only is True
           and type(new_core) is OriginalRelayCore and new_core.qualification_only is True
           and new_core is not source_owner.core and new_core.home == source_owner.core.home
           and new_core.contract == source_owner.core.contract and new_core.rows == source_owner.core.rows
           and type(new_core.ledger) is Ledger and type(new_core.queue) is FinalQueue
           and new_core.ledger is not source_owner.core.ledger and new_core.queue is not source_owner.core.queue
           and new_core.ledger.db is source_owner.core.ledger.db and new_core.queue.db is source_owner.core.queue.db,
           'STAGE_SYSTEM_OWN_DISTINCT_CORE_AND_QUARANTINED_BORROWED_ORIGINAL_RO_HANDLES')
    for instance, cls in ((new_core.ledger, Ledger), (new_core.queue, FinalQueue)):
        for name in vars(cls):
            if name.startswith('__') or not callable(getattr(cls, name, None)): continue
            method = getattr(instance, name)
            M.need(type(method) is MethodType and method.__self__ is instance and method.__func__ is P._refuse,
                   'STAGE_SYSTEM_OWN_LEDGER_AND_QUEUE_ALL_METHODS_STILL_QUARANTINED')
    # Original OWN history verifier must prove registeredTrue before any alias.
    history = K.read_OWN_history(reference, history_reference=history_reference,
        owner=source_owner, ticket=ticket, read_budget=read_budget)
    M.need(history._source.component('SYSTEM')['registered'] is True,
           'STAGE_SYSTEM_OWN_ORIGINAL_SYSTEM_NOT_ABSENT_OR_HANDMADE')
    return _restore_new_core(source_owner, new_core, reference=reference, history_reference=history_reference,
        ticket=ticket, graph=None, binding=None, read_budget=read_budget, own=True)
