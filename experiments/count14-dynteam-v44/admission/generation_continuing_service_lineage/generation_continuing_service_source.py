"""Explicit continuing-resource source SNAPSHOT and readonly receiver ports.

Original service classes/seals, physical retirement, generation T/financial,
SOURCE/final_guard/ISSUED and original history parsers are retained. The one
resource history ingredient is an actual registered continuing Q capability,
not an adjusted counter or reconstructed old Popen. No module is patched.
The new receiver is deliberately NOT legacy VerifiedResourceHistory and grants
no constructor, scheduler, writer, science, TERM or whole-runtime authority.
"""
from dataclasses import asdict
from pathlib import Path
from types import FunctionType
import ast
import copy
import hashlib
import importlib
import inspect
import os
import stat
import textwrap
import threading

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
from native_peer_registry import process_birth
import source_services_controls as S
import durable_service_source_controls as D
import retired_system_history as H
import generation_service_history_source_v3 as GS
import generation_financial_runtime_source_v2 as GF
import held_resource_lineage_source as R
import held_resource_lineage_decoder as V
import resource_epoch_continuing_producer_v6 as Q
import resource_epoch_archive_v2 as A

PINS = {
    'source_services_controls': 'f7c72e41dc7df2940917ad664d582308ab936387c0b5190a21e2c07bac2d55db',
    'durable_service_source_controls': 'fe5cbbbb186e4d9049895f68c32529d8237d6ffbeda35d03b8ed15a0482f0b83',
    'generation_service_history_source_v3': '00c0e1885e7222248b74bd0c22e72cc9c83a98fa386c8646f861e89fe683a6a1',
    'held_resource_lineage_source': '62c754ed3c2e3e075f6b496c28ba165134242e9b731b1f6784cdb4adc2a28449',
    'held_resource_lineage_decoder': '9d2c8a7b4c6cff172754c73b74e018173db1084a3bc410f88cc0bb8424e0d93b',
    'resource_epoch_continuing_producer_v6': '7fc0a72de729068fd42ce35dd4e50d80e2b0af07ce4ceede661a45e710b7dc73',
}
SCHEMA = 'count14-explicit-registered-continuing-resource-history-bindings-v1'
_SEAL = object()
_ATTEMPTS = {}
_CAPS = {}
_READ_ATTEMPTS = {}
_READS = {}


def _budget(value):
    M.need(type(value) is ReadBudget, 'CONTINUING_SOURCE_ORIGINAL_FINITE_METADATA_BUDGET')
    value.check()


def _production(own):
    M.need(own is False, 'CONTINUING_SOURCE_PRODUCTION_NEVER_ACCEPTS_OWN')


def _self_pin():
    p = Path(__file__); s = p.lstat()
    M.need(p.is_absolute() and p.resolve() == p and stat.S_ISREG(s.st_mode)
           and s.st_nlink == 1 and not s.st_mode & 0o022,
           'CONTINUING_SOURCE_CANONICAL_FROZEN_SELF')
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify_sources():
    for name, pin in PINS.items():
        p = Path(importlib.import_module(name).__file__); s = p.lstat()
        M.need(p.is_absolute() and p.resolve() == p and stat.S_ISREG(s.st_mode)
               and s.st_nlink == 1 and not s.st_mode & 0o022
               and hashlib.sha256(p.read_bytes()).hexdigest() == pin,
               'CONTINUING_SOURCE_EXACT_FROZEN_SOURCE_CLOSURE')
    GS.verify_sources(); R.verify_sources(); V.verify_sources()
    GF._original_functions(S, ('resource_controls', 'capture_registered', 'verify_registered_source'))
    GF._original_functions(D, ('_live_source_cap', 'publish_source', '_validate_controls'))
    GF._original_functions(H, ('_publish', '_read_bound'))
    GF._original_functions(V, ('_semantic', '_ref', '_budget'))
    _self_pin()
    return dict(PINS)


def _clone(original, bindings):
    M.need(type(original) is FunctionType and type(bindings) is dict,
           'CONTINUING_SOURCE_EXACT_FUNCTION_AND_FIXED_GLOBAL_PORTS')
    fn = FunctionType(original.__code__, dict(original.__globals__, **bindings),
                      original.__name__, original.__defaults__, original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__
    return fn


def _bound(core, budget):
    from original_relay_core import OriginalRelayCore
    M.need(type(core) is OriginalRelayCore and core.qualification_only is False,
           'CONTINUING_SOURCE_ONLY_ACTUAL_PRODUCTION_ORIGINAL_CORE')
    found = []
    for value in Q._REG.values():
        budget.check()
        M.need(type(value) is Q.ContinuingResourceReceiver,
               'CONTINUING_SOURCE_ORIGINAL_Q_REGISTRY_TYPES')
        if value.producer.core is core:
            found.append(value)
    M.need(len(found) == 1 and found[0].OWN is False,
           'CONTINUING_SOURCE_UNIQUE_ACTUAL_REGISTERED_Q_FOR_THIS_CORE')
    Q._current(found[0], budget)  # Original T/stage/daemon/three-lock/real-Popen checks.
    return found[0]


def _history_bindings(resource_cap, service, budget):
    r = R._same(resource_cap, budget)
    M.need(r['OWN'] is False and r['bound'].producer is service,
           'CONTINUING_SOURCE_SAME_ACTUAL_REGISTERED_RESOURCE_NOT_CALLER_INDEX')
    body = resource_cap.snapshot(read_budget=budget)
    refs = [copy.deepcopy(ref) for _, ref in r['files'].values()]
    M.need(len({ref['path'] for ref in refs}) == len(refs),
           'CONTINUING_SOURCE_UNIQUE_ALL_REGISTERED_LINEAGE_CONTROLS')
    return dict(schema=SCHEMA, port_sha256=_self_pin(), lineage=body,
                original_control_references=refs,
                legacy_full_sequence_snapshot_not_claimed=True)


def _capture_function(resource_cap):
    def bindings(service, budget):
        return _history_bindings(resource_cap, service, budget)
    resource = _clone(S.resource_controls, dict(resource_history_bindings=bindings))
    return _clone(S.capture_registered, dict(resource_controls=resource))


def capture_registered(core, *, read_budget):
    _budget(read_budget); verify_sources()
    bound = _bound(core, read_budget)
    M.need(id(core) not in _ATTEMPTS, 'CONTINUING_SOURCE_ONE_CAPTURE_RETAIN_PARTIAL_NO_RETRY')
    attempt = dict(core=core, bound=bound, phase='CAPTURING_RETAIN_ALL_PARTIALS')
    _ATTEMPTS[id(core)] = attempt
    try:
        resource_cap = R.capture_registered(bound, read_budget=read_budget)
        value = _capture_function(resource_cap)(core, read_budget=read_budget)
        M.need(type(value) is S.RetiredServiceSourceControls and value.OWN is False
               and value.source_birth == process_birth(os.getpid()),
               'CONTINUING_SOURCE_ORIGINAL_SERVICE_TYPE_SEAL_AND_CURRENT_BIRTH')
        _CAPS[id(value)] = dict(value=value, seal=_SEAL, core=core, bound=bound,
            resource_cap=resource_cap, birth=process_birth(os.getpid()), thread=threading.get_ident())
        verify_registered_source(value, core=core, read_budget=read_budget)
        attempt['phase'] = 'CAPTURED_NOT_PUBLISHED'
        return value
    except BaseException as error:
        attempt.update(phase='PARTIAL_RETAINED_NO_RETRY', failure_type=type(error).__name__)
        raise


def verify_registered_source(value, *, core, read_budget):
    _budget(read_budget)
    M.need(type(value) is S.RetiredServiceSourceControls,
           'CONTINUING_SOURCE_EXACT_ORIGINAL_SERVICE_CAP_BEFORE_ATTRIBUTES')
    record = _CAPS.get(id(value))
    M.need(type(record) is dict and record['value'] is value and record['seal'] is _SEAL
           and record['core'] is core and record['birth'] == process_birth(os.getpid())
           and record['thread'] == threading.get_ident(),
           'CONTINUING_SOURCE_SAME_REGISTERED_REAL_BIRTH_THREAD_AND_SOURCE_CAP')
    Q._current(record['bound'], read_budget)
    fn = _clone(S.verify_registered_source,
                dict(capture_registered=_capture_function(record['resource_cap'])))
    return fn(value, core=core, read_budget=read_budget)


def live_source_function():
    return GS._ports(D._live_source_cap,
        [('S.verify_registered_source(source_cap, core=core, read_budget=budget)',
          '_continuing_verify(source_cap, core=core, read_budget=budget)', 1)],
        dict(_continuing_verify=verify_registered_source))


def publisher_function(owner, read_budget):
    verify_sources()
    original = GS.publisher_function(owner, read_budget)
    return _clone(original, dict(_live_source_cap=live_source_function()))


def publish_source(owner, *, source_cap, read_budget):
    _budget(read_budget)
    return publisher_function(owner, read_budget)(owner, source_cap=source_cap, read_budget=read_budget)


def history_publisher_function(ticket):
    verify_sources()
    # Original GS's four generation-expression ports, plus exactly the two
    # original source-verification calls. All H parser/None/600 guards remain.
    changes = [
        ('C._read_complete(service_reference, core.home, own=own, budget=read_budget)',
         '_generation_services(service_reference, core.home, own=own, budget=read_budget, ticket=_ticket)', 2),
        ('core.home / (OWN_LEAF_NAME if own else LEAF_NAME)',
         '_generation_leaf(core.home, _ticket, read_budget)', 1),
        ("save_candidate(leaf / 'SOURCE_PUBLIC.json', body)",
         "_generation_save_history(leaf / 'SOURCE_PUBLIC.json', body, ticket=_ticket, budget=read_budget)", 1),
        ('S.verify_registered_source(source_cap, core=core, read_budget=read_budget)',
         '_continuing_verify(source_cap, core=core, read_budget=read_budget)', 2)]
    return GS._ports(H._publish, changes, dict(_generation_services=GS._read_services_port,
        _generation_leaf=GS._prepare_history_leaf, _generation_save_history=GS._save_history_source,
        _ticket=ticket, _continuing_verify=verify_registered_source))


def publish_system_history(owner, *, source_cap, service_reference, read_budget):
    _budget(read_budget); verify_sources()
    issuer, _, _, _, _ = GF._source(owner, read_budget)
    live_source_function()(source_cap, owner.core, budget=read_budget, own=False)
    GS.read_service_complete(service_reference, owner.core.home, ticket=issuer.ticket, budget=read_budget)
    leaf = GS._history_leaf(owner.core.home, issuer.ticket, read_budget)
    result = history_publisher_function(issuer.ticket)(owner.core, source_cap=source_cap,
        service_reference=service_reference, read_budget=read_budget, own=False)
    fd = os.open(leaf.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return result


def resource_semantic_function():
    """Four namespace sites, including archive.OWN; exact full inverse AST.

    The older joint adapter ports only three and leaves archive.OWN=True.
    That conditional incompatibility is not a measured production failure.
    No caller controls the namespace and this parser grants no capability.
    """
    verify_sources()
    return GS._ports(V._semantic, [
        ("s['OWN'] is True", "s['OWN'] is False", 1),
        ("archive['OWN'] is True", "archive['OWN'] is False", 1),
        ("job['qualification_only'] is True", "job['qualification_only'] is False", 1),
        ("value['qualification_only'] is True", "value['qualification_only'] is False", 1)], {})


def _read_lineage(source, owner, budget):
    row = source.component('resource')
    closed = row['history_control_bindings']
    M.need(set(closed) == {'schema','port_sha256','lineage','original_control_references',
                         'legacy_full_sequence_snapshot_not_claimed'}
           and closed['schema'] == SCHEMA and closed['port_sha256'] == _self_pin()
           and closed['legacy_full_sequence_snapshot_not_claimed'] is True,
           'CONTINUING_HISTORY_ONLY_EXPLICIT_SOURCE_BINDING_NOT_LEGACY_OR_CALLER_INDEX')
    body = closed['lineage']; refs = closed['original_control_references']
    M.need(type(refs) is list and 0 < len(refs) <= 100000,
           'CONTINUING_HISTORY_FINITE_ORIGINAL_CONTROL_SET')
    raw = {}; total = 0
    for ref in refs:
        p = V._ref(ref)
        M.need(str(p) not in raw, 'CONTINUING_HISTORY_UNIQUE_ORIGINAL_CONTROL_REFERENCES')
        data, _ = A._read(p, mode=ref['identity'][4] & 0o777, limit=R.MAX_BYTES,
                          budget=budget, expected=ref)
        total += len(data)
        M.need(total <= R.MAX_BYTES, 'CONTINUING_HISTORY_TOTAL_REGISTERED_METADATA_BOUND')
        raw[str(p)] = data
    cfg = body['configuration']
    M.need(row['source_owner_birth'] == body['source_owner_birth'] == asdict(source.old_owner_birth)
           and row['configuration']['sequence'] == cfg['global_sequence']
           and row['configuration']['sourcehome'] == cfg['sourcehome']
           and row['configuration']['last_published'] == cfg['last_published']
           and row['configuration']['inventory_sha256'] == cfg['inventory_sha256']
           and row['configuration']['next_due'] == cfg['next_due']
           and row['original_public'] == cfg['original_public']
           and body['contract_sha256'] == source.contract_sha256,
           'CONTINUING_HISTORY_SOURCE_ROW_FULL_SEQUENCE_PLAN_OWNER_AND_PUBLIC_IDENTICAL')
    summaries = [dict(state=r['state'], child_handle_present=r['actual_child_pid'] is not None,
        child_returncode=r['actual_child_returncode'],
        intent_sha256=r['controls']['INTENT_PUBLIC.json']['sha256'],
        directory=str(Path(r['controls']['INTENT_PUBLIC.json']['path']).parent)) for r in body['records']]
    M.need(row['records'] == summaries,
           'CONTINUING_HISTORY_CURRENT_HANDLES_MATCH_LINEAGE_NO_OLD_POPEN_RECREATION')
    parsed = dict(body, publisher_module_sha256=PINS['held_resource_lineage_source'])
    expected = resource_semantic_function()(parsed, raw, owner.core.home,
        source.old_owner_birth, R, budget)
    M.need(expected == {r['path']: r for r in refs},
           'CONTINUING_HISTORY_ALL_AND_ONLY_ORIGINAL_LINEAGE_CONTROLS')
    for ref in refs:
        data, _ = A._read(Path(ref['path']), mode=ref['identity'][4] & 0o777,
                          limit=R.MAX_BYTES, budget=budget, expected=ref)
        M.need(data == raw[ref['path']], 'CONTINUING_HISTORY_CONTROL_DRIFT_DURING_SCAN')
    return copy.deepcopy(body), tuple(copy.deepcopy(refs))


class VerifiedContinuingResourceLineage:
    def __init__(self, *a, **k):
        raise M.PaidColdWait('CONTINUING_HISTORY_ONLY_TYPED_T_AND_SOURCE_VERIFIER')

    def snapshot(self, *, read_budget):
        _budget(read_budget)
        r = _READS.get(id(self))
        M.need(type(self) is VerifiedContinuingResourceLineage and type(r) is dict
               and r['value'] is self and r['seal'] is _SEAL and r['birth'] == process_birth(os.getpid())
               and r['thread'] == threading.get_ident(), 'CONTINUING_HISTORY_SAME_REAL_NEW_BIRTH_THREAD_CAP')
        current = GS.verify_reference(r['reference'], owner=r['owner'], ticket=r['ticket'], read_budget=read_budget)
        body, refs = _read_lineage(current, r['owner'], read_budget)
        M.need(current.snapshot() == r['source'].snapshot() and body == r['body'] and refs == r['refs'],
               'CONTINUING_HISTORY_TYPED_SOURCE_OR_CONTROL_DRIFT_RETAIN_FAILURE')
        return body

    @property
    def safe_to_TERM(self): return False
    @property
    def resource_sampler_restored(self): return False
    @property
    def paid_activation_authorized(self): return False
    @property
    def whole_runnable_ready(self): return False


def read_resource_history(reference, *, owner, ticket, read_budget):
    _budget(read_budget); verify_sources()
    source = GS.verify_reference(reference, owner=owner, ticket=ticket, read_budget=read_budget)
    M.need(type(source) is D.VerifiedRetiredServiceControls and source.OWN is False,
           'CONTINUING_HISTORY_ONLY_ORIGINAL_PRODUCTION_TYPED_T_PAIR_AND_SERVICES')
    body, refs = _read_lineage(source, owner, read_budget)
    key = (source._reference['sha256'], source.new_owner_birth)
    M.need(key not in _READ_ATTEMPTS, 'CONTINUING_HISTORY_ONCE_SAME_SOURCE_NEW_BIRTH_NO_RETRY')
    _READ_ATTEMPTS[key] = True
    value = object.__new__(VerifiedContinuingResourceLineage)
    _READS[id(value)] = dict(value=value, seal=_SEAL, birth=process_birth(os.getpid()),
        thread=threading.get_ident(), source=source, body=body, refs=refs,
        reference=reference, owner=owner, ticket=ticket)
    value.snapshot(read_budget=read_budget)
    return value


def publish_for_owner(owner):
    from native_cold_owner import NativeColdOwner
    M.need(type(owner) is NativeColdOwner, 'CONTINUING_SOURCE_ONLY_ORIGINAL_RETAINED_OWNER')
    budget = ReadBudget()
    cap = capture_registered(owner.core, read_budget=budget)
    service = publish_source(owner, source_cap=cap, read_budget=budget)
    reference = GS.load_service_reference(service['path'], service['sha256'])
    history = publish_system_history(owner, source_cap=cap, service_reference=reference, read_budget=budget)
    return dict(schema='count14-generation-continuing-services-source-command-v1',
        service_source_reference=service, system_history_source_reference=history,
        full_old_prefix_and_current_physical_terminals_preserved=True,
        original_T_finance_retirement_and_SOURCE_ISSUED_guards_unchanged=True,
        safe_to_TERM=False, paid_activation_authorized=False, resource_sampler_restored=False,
        whole_runnable_ready=False)
