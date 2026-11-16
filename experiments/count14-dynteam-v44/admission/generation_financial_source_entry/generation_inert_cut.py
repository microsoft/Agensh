"""Explicit generation-scoped ports for ORIGINAL typed INERT tickets and pairs.

Old TICKET/ISSUED leaves never move, change or disappear. Original code is not
patched. Private clones change only the generation leaf expression and the
explicit inspection/pair ports; original class, namespace, source guards,
finance equations, true old-ended/new-birth and three-lock checks remain.

Production issuance STILL requires a real original NormalInertIssuer and its
complete six-source/pre/post/physical-retirement checks. OWN H publication is
separate and cannot prove SDK, whole runtime, production or paid authority.
"""
from dataclasses import asdict
from pathlib import Path
from types import FunctionType, SimpleNamespace
import ast
import copy
import hashlib
import importlib
import inspect
import os
import stat
import textwrap
import threading
import uuid

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget, ram_lock
from native_peer_registry import ProcessBirth, process_birth
import normal_inert_cut as T
import metadata_inert_pair as P

PINS = {
    'normal_inert_cut': 'aac25e6b4f30c199a84d1ac7f5652283585f259f93a2d3f4a3e3134c9f203262',
    'metadata_inert_pair': '83b2662daef394a6c3bb9cbfa46fc15a49c4382df7db5c963ec89a1f61b853da',
}
OWN_STAGE_PINS = {
    'own_held_stage_pair_v3': 'c455557d58b27e5d051c8e3f5fcaebc90dd9530089a61b5bc74686abe8e05f8d',
    'resource_epoch_continuing_producer_v6': '7fc0a72de729068fd42ce35dd4e50d80e2b0af07ce4ceede661a45e710b7dc73',
    'stage_system_live_receiver_v5': 'ab3cbae3c248e2a01e2f403be65b9fddb0321318b6ad6d652f44c123c36c29ed',
    'financial_runtime_source_control': '5d7aedc421df71583d55ec6ffc32cd80389c1f944ed93c3dcad99b433d38f906',
}
LEAF = 'normal-inert-cut-generations-v1'
OWN_LEAF = 'OWN-normal-inert-cut-generations-v1'
GENERATION = 'count14-original-typed-INERT-exact-source-generation-v1'
_SEAL = object()
_ISSUING = {}
_OWN_ATTEMPTS = {}


def _budget(value):
    M.need(type(value) is ReadBudget, 'GENERATION_T_ORIGINAL_FINITE_METADATA_BUDGET')
    value.check()


def _pin(name, pin):
    module = importlib.import_module(name)
    path = Path(module.__file__)
    s = path.lstat()
    M.need(path.is_absolute() and path.resolve() == path and stat.S_ISREG(s.st_mode)
           and not s.st_mode & 0o022 and s.st_nlink == 1
           and hashlib.sha256(path.read_bytes()).hexdigest() == pin,
           'GENERATION_T_FIXED_ORIGINAL_COMPONENT_PIN')
    return module


def verify_sources():
    for name, pin in PINS.items():
        _pin(name, pin)
    path = Path(__file__)
    s = path.lstat()
    M.need(path.is_absolute() and path.resolve() == path and stat.S_ISREG(s.st_mode)
           and not s.st_mode & 0o022 and s.st_nlink == 1,
           'GENERATION_T_CANONICAL_FROZEN_SELF')


def _source_key(birth):
    M.need(type(birth) is ProcessBirth and type(birth.pid) is int and birth.pid > 0
           and type(birth.start_ticks) is int and birth.start_ticks > 0
           and type(birth.boot_id) is str and str(uuid.UUID(birth.boot_id)) == birth.boot_id,
           'GENERATION_T_EXACT_REAL_SOURCE_BIRTH_KEY')
    return f'{birth.pid}-{birth.start_ticks}-{birth.boot_id}'


def _clone_expression(original, old, new, extra):
    """One exact expression only; inverse AST proves everything else unchanged."""
    old_node, new_node = ast.parse(old, mode='eval').body, ast.parse(new, mode='eval').body
    old_dump, new_dump = ast.dump(old_node), ast.dump(new_node)
    initial = ast.parse(textwrap.dedent(inspect.getsource(original)))
    hits = []

    class Replace(ast.NodeTransformer):
        def generic_visit(self, node):
            if ast.dump(node) == old_dump:
                hits.append(True)
                return ast.copy_location(copy.deepcopy(new_node), node)
            return super().generic_visit(node)

    tree = Replace().visit(copy.deepcopy(initial))
    M.need(len(hits) == 1, 'GENERATION_T_ONE_EXACT_ORIGINAL_EXPRESSION_SITE')
    reverse_hits = []

    class Reverse(ast.NodeTransformer):
        def generic_visit(self, node):
            if ast.dump(node) == new_dump:
                reverse_hits.append(True)
                return ast.copy_location(copy.deepcopy(old_node), node)
            return super().generic_visit(node)

    reverse = Reverse().visit(copy.deepcopy(tree))
    M.need(len(reverse_hits) == 1 and ast.dump(reverse) == ast.dump(initial),
           'GENERATION_T_ALL_OTHER_ORIGINAL_AST_PREDICATES_UNCHANGED')
    local = {}
    exec(compile(ast.fix_missing_locations(tree), __file__ + ':one-original-generation-expression', 'exec'),
         dict(original.__globals__, **extra), local)
    return local[original.__name__]


def _generation_leaf(home, body, own):
    meta = body.get('generation')
    M.need(type(meta) is dict and set(meta) == {
        'schema', 'source_birth', 'module_sha256', 'parent_identity', 'origin_T'},
        'GENERATION_T_COMPLETE_EXPLICIT_GENERATION_METADATA')
    M.need(meta['schema'] == GENERATION and meta['source_birth'] == body['old_owner_birth']
           and meta['module_sha256'] == hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'GENERATION_T_EXACT_SOURCE_BIRTH_AND_FROZEN_PORT_BINDING')
    birth = M.birth(meta['source_birth'])
    base = M.existing(meta['parent_identity'], directory=True, private=True)
    M.need(base == home / (OWN_LEAF if own else LEAF), 'GENERATION_T_EXACT_PRIVATE_PARENT_NOT_ALIAS')
    return base / _source_key(birth)


def _read_reference(ticket, *, own, read_budget):
    _budget(read_budget)
    verify_sources()
    fn = _clone_expression(T._read_reference, 'home / leaf',
                           '_generation_leaf(home, body, own)', dict(_generation_leaf=_generation_leaf))
    return fn(ticket, own=own, read_budget=read_budget)


def load_reference(path, sha256, *, own):
    M.need(type(own) is bool, 'GENERATION_T_EXPLICIT_TYPED_NAMESPACE')
    ticket = T._reference(path, sha256, T.OWNNormalInertTicket if own else T.NormalInertTicket)
    _read_reference(ticket, own=own, read_budget=ReadBudget())
    return ticket


def inspect_reference(ticket, *, read_budget):
    _budget(read_budget)
    verify_sources()
    original = T.inspect_inert_reference
    fn = FunctionType(original.__code__, dict(original.__globals__, _read_reference=_read_reference),
                      original.__name__, original.__defaults__, original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__
    return fn(ticket, read_budget=read_budget)


def attach_registered_pair(ticket, *, read_budget):
    _budget(read_budget)
    verify_sources()
    fn = _clone_expression(P.attach_inert_pair, 'T.inspect_inert_reference(ticket, read_budget=read_budget)',
        'generation_inspect(ticket, read_budget=read_budget)', dict(generation_inspect=inspect_reference))
    return fn(ticket, read_budget=read_budget)


def verify_registered_pair(owner, *, ticket, read_budget):
    _budget(read_budget)
    verify_sources()
    fn = _clone_expression(P.verify_registered_pair, 'T.inspect_inert_reference(ticket, read_budget=read_budget)',
        'generation_inspect(ticket, read_budget=read_budget)', dict(generation_inspect=inspect_reference))
    return fn(owner, ticket=ticket, read_budget=read_budget)


def _pair_api():
    verify_sources()
    return SimpleNamespace(VerifiedMetadataPair=P.VerifiedMetadataPair,
                           verify_registered_pair=verify_registered_pair)


def verify_ticket(ticket, *, owner, read_budget, own):
    _budget(read_budget)
    verify_sources()
    M.need(type(own) is bool, 'GENERATION_T_EXPLICIT_TYPED_NAMESPACE')
    original = T.verify_OWN_inert_ticket if own else T.verify_inert_ticket
    replacements = dict(_read_reference=_read_reference)
    if not own:
        replacements['_pair_api'] = _pair_api
    fn = FunctionType(original.__code__, dict(original.__globals__, **replacements),
                      original.__name__, original.__defaults__, original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__
    value = fn(ticket, owner=owner, read_budget=read_budget)
    M.need(type(value) is T.VerifiedNormalInertCut and value.OWN is own,
           'GENERATION_T_ORIGINAL_TYPED_CAPABILITY_NOT_DICT_OR_RELABELED_ORIGIN')
    return value


def _sync_generation_parent(parent):
    # T._save keeps its ORIGINAL home fsync; save_candidate syncs the birth
    # leaf. Also persist that birth leaf's entry in the new generation parent.
    M.existing(M.descriptor(parent), directory=True, private=True)
    fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _save(home, body, *, own):
    context = _ISSUING.get(threading.get_ident())
    current = process_birth(os.getpid())
    M.need(type(context) is dict and context['seal'] is _SEAL and context['birth'] == current
           and context['home'] == home and context['own'] is own and not context['written']
           and body['old_owner_birth'] == asdict(current),
           'GENERATION_T_ONLY_VERIFIED_LIVE_SOURCE_ONCE_NOT_CALLER_MATERIAL')
    context['written'] = True  # partial is retained; not automatically retried
    base = home / (OWN_LEAF if own else LEAF)
    if not os.path.lexists(base):
        base.mkdir(mode=0o700)
    M.existing(M.descriptor(base), directory=True, private=True)
    body = dict(body, generation=dict(schema=GENERATION, source_birth=asdict(current),
        module_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        parent_identity=M.descriptor(base), origin_T=context['origin_T']))
    fn = _clone_expression(T._save, 'home / (OWN_LEAF if own else LEAF)',
                           '_generation_leaf(home, body, own)', dict(_generation_leaf=_generation_leaf))
    ticket = fn(home, body, own=own)
    _sync_generation_parent(base)
    return ticket


def issue_registered(issuer, *, read_budget):
    """All ORIGINAL six-cut, transport, finance and pre/post guards still run."""
    _budget(read_budget)
    verify_sources()
    M.need(type(issuer) is T.NormalInertIssuer, 'GENERATION_T_ORIGINAL_REGISTERED_ISSUER_REQUIRED')
    issuer._current()
    current = process_birth(os.getpid())
    M.need(issuer.birth == current and threading.get_ident() not in _ISSUING,
           'GENERATION_T_ONE_ORIGINAL_SOURCE_THREAD')
    context = dict(seal=_SEAL, birth=current, home=issuer.core.home, own=False, written=False, origin_T=None)
    _ISSUING[threading.get_ident()] = context
    try:
        original = T.NormalInertIssuer.issue
        fn = FunctionType(original.__code__, dict(original.__globals__, _save=_save),
                          original.__name__, original.__defaults__, original.__closure__)
        fn.__kwdefaults__ = original.__kwdefaults__
        return fn(issuer, read_budget=read_budget)
    finally:
        _ISSUING.pop(threading.get_ident())


def publish_OWN_H_stage(stage, bound, *, read_budget):
    """Capture a NEW actual H source; never relabel the old pair's source birth."""
    _budget(read_budget)
    verify_sources()
    modules = {name: _pin(name, pin) for name, pin in OWN_STAGE_PINS.items()}
    port, Q, SX, F = (modules[name] for name in (
        'own_held_stage_pair_v3', 'resource_epoch_continuing_producer_v6',
        'stage_system_live_receiver_v5', 'financial_runtime_source_control'))
    record = port.current_OWN_stage(stage, read_budget=read_budget)
    Q._current(bound, read_budget)
    M.need(id(bound) in Q._OWN_STAGE_CORES and Q._OWN_STAGE_CORES[id(bound)]['stage'] is stage
           and bound.producer.core is stage.core and bound.owner is record['owner']
           and id(stage) not in _OWN_ATTEMPTS,
           'GENERATION_T_ACTUAL_REGISTERED_H_Q_SOURCE_SINGLE_PUBLICATION')
    _OWN_ATTEMPTS[id(stage)] = dict(stage=stage, phase='VERIFYING_ACTUAL_SOURCE_RETAIN_PARTIAL')
    core, producer = stage.core, bound.producer
    service = core.system_health
    runtime = SX._current(service, read_budget)['runtime']
    M.need(runtime.owner.core is core and runtime.owner.source_owner is record['owner']
           and service.accepting is False and service.physical_clear()
           and producer.accepting is False and producer.physical_clear() and not producer.failures
           and all(r['state'] == 'OBSERVATION_PUBLISHED' and r['child'].poll() == 0 for r in producer.records),
           'GENERATION_T_ONLY_TRUE_CLOSED_ORIGINAL_SERVICES_NOT_ZERO_BY_DEFAULT')
    proof = T._own_pair(record['owner'], read_budget)
    origin = T.verify_OWN_inert_ticket(record['ticket'], owner=record['owner'], read_budget=read_budget)
    current = process_birth(os.getpid())
    M.need(current == stage.new_owner_birth == proof.new_owner_birth == origin.new_owner_birth
           and current != proof.source_birth == origin.old_owner_birth,
           'GENERATION_T_NEW_ACTUAL_SOURCE_IS_NOT_ORIGIN_T_SOURCE')
    storage, locks = F._source_storage(core, stage.queue,
        Path(proof.material['full_used_directory']['path']), proof.full_used_fd)
    M.need([[k, r] for k, r in locks] == [list(r) for r in proof.material['locks']],
           'GENERATION_T_SAME_EXACT_ORIGINAL_THREE_SOURCE_LOCKS')
    with ram_lock(core.ledger.mutex, read_budget):
        clock = copy.deepcopy(core.active_clock.states)
        pauses = copy.deepcopy(core.gate._budget_pause)
    M.need(all(row['mode'] == 'HOLD' for row in clock.values()) and core.gate.closed
           and core.gate.startup_held == set(core.rows), 'GENERATION_T_ACTUAL_H_SOURCE_STILL_HELD')
    origin_ref = dict(path=record['ticket'].path, sha256=record['ticket'].sha256)
    controls = dict(normal_clock_controls=dict(schema='OWN_ACTUAL_ORIGINAL_H_CLOSED_SOURCE_CLOCK_CONTROL_V1',
        current_source_birth=asdict(current), origin_T=origin_ref, active=clock,
        budget_pause=[dict(trajectory=t, role=r, **v) for (t, r), v in sorted(pauses.items())],
        actual_original_resource=producer.public(), actual_original_SYSTEM=service.public(),
        SDK_or_paid_or_whole_restored=False))
    body = dict(contract=copy.deepcopy(core.contract), contract_sha256=M.digest(core.contract),
        old_owner_birth=asdict(current), **storage, locks=[[k, r] for k, r in locks],
        control_locks=[r for k, r in locks], financial_metadata=copy.deepcopy(proof.material['financial_metadata']),
        source_controls=controls, OWN_scope='OWN_NATIVE_METADATA_ONLY', allowed_components=sorted(controls),
        producer_scope='OWN_RECEIPT_COMPONENT_NOT_PRODUCTION_ISSUER', actual_production_six_source_guard_used=False)
    raw = dict(schema='OWN_NATIVE_METADATA_ONLY', OWN=True, owner_home=storage['owner_home'],
        old_owner_birth=asdict(current), contract=copy.deepcopy(core.contract), contract_sha256=M.digest(core.contract),
        full_used_directory=storage['full_used_directory'], source_controls=copy.deepcopy(controls),
        ledger=dict(home=storage['ledger_home'], database=storage['ledger_database'], lock=locks[0][1]),
        queue=dict(home=storage['queue_home'], database=storage['queue_database'], lock=locks[1][1]))
    M.need(threading.get_ident() not in _ISSUING, 'GENERATION_T_ONE_ORIGINAL_SOURCE_THREAD')
    _ISSUING[threading.get_ident()] = dict(seal=_SEAL, birth=current, home=core.home,
                                         own=True, written=False, origin_T=origin_ref)
    try:
        ticket = _save(core.home, body, own=True)
        _read_reference(ticket, own=True, read_budget=read_budget)
        port.current_OWN_stage(stage, read_budget=read_budget)
        _OWN_ATTEMPTS[id(stage)]['phase'] = 'PUBLISHED_NEW_OWN_SOURCE_NOT_PRODUCTION'
        return dict(ticket=dict(path=ticket.path, sha256=ticket.sha256), material=raw,
                    source_birth=asdict(current), origin_source_birth=asdict(proof.source_birth),
                    original_T_type=True, production_or_SDK_or_writer_authority=False)
    finally:
        _ISSUING.pop(threading.get_ident())
