"""Explicit generation verifier ports across held/SYSTEM/archive/epoch/Q.

Original classes, seals and live registries are shared, never reconstructed.
Only fixed private function namespaces and expression sites are ported. No
original module/class/instance method is overwritten. No operation runs on
import or during graph construction. Public operations remain production-only
and re-enter original current-birth/thread/three-lock/physical custody guards.

The legacy archive still requires its original uniform-source history type.
The separate continuing-lineage type is NOT relabelled to satisfy that guard;
its later multi-generation binder remains a distinct required implementation.
"""
from pathlib import Path
from types import CodeType, FunctionType, SimpleNamespace
import copy
import hashlib
import importlib
import os
import stat
import sys

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
import generation_inert_cut as G
import generation_financial_runtime_source_v2 as GF
import generation_service_history_source_v3 as GS
import generation_continuing_service_source as X
import normal_held_financial_writer as N
import active_clock_method_runtime as AC
import staged_financial_runtime as ST
import retired_system_live_receiver as L
import stage_system_live_receiver_v2 as B
import resource_epoch_archive_v2 as A
import resource_epoch_transition_v3 as E
import resource_epoch_continuing_producer_v6 as Q
import held_resource_lineage_source as R

PINS = {
    'generation_inert_cut': '0d23b664bf8dcfae949c11877fd3a6160d134b1a3a1bcc7f00bd2c660e0d73c5',
    'generation_financial_runtime_source_v2': 'd30309aa7c29b6c61b550d9f3a463f0e33913d70bd96c2e1528d9c98e0bdc162',
    'generation_service_history_source_v3': '00c0e1885e7222248b74bd0c22e72cc9c83a98fa386c8646f861e89fe683a6a1',
    'generation_continuing_service_source': 'cd9f04bf4f02de38dec4132f6c67c1ec797241bbf2e169f52a8e14ec8f7fc3f0',
    'normal_held_financial_writer': '686247ad8d2ca768abf1dc0085ac4a18e58419f37e2bceb61b152d8f8b413261',
    'active_clock_method_runtime': 'c24b4168f0a4fe3dc88cda7a086e2cdf6a2f3249e864391c9f94abb653bd26be',
    'staged_financial_runtime': '62de21eed76372cbe6d6721da10891d0a86e4cfc65dbbdbbf22294b3e49baba5',
    'retired_system_live_receiver': '4c3df1b4ac22d3e30b2da12173058f1b11bf787ad271b9f71d4c3ecc767a81c1',
    'stage_system_live_receiver_v2': 'ccf677e105bf5ee1b61312782dcbb75f87c4d060778790b495bbec8d4f8e5032',
    'resource_epoch_archive_v2': 'aa54e75ce3af53d4d257082e6159792d5a32b9966554c245fec7f371ae7e60c9',
    'resource_epoch_transition_v3': 'a4efa66a5fb85a4611a56844dfd15f8398107671935238de510088021be98a7d',
    'resource_epoch_continuing_producer_v6': '7fc0a72de729068fd42ce35dd4e50d80e2b0af07ce4ceede661a45e710b7dc73',
    'held_resource_lineage_source': '62c754ed3c2e3e075f6b496c28ba165134242e9b731b1f6784cdb4adc2a28449',
}
_CACHE = None
_HISTORY_SEAL = object()
_HISTORY_READS = {}
_HISTORY_ATTEMPTS = {}


def _budget(value):
    M.need(type(value) is ReadBudget, 'GENERATION_RUNTIME_ORIGINAL_FINITE_METADATA_BUDGET')
    value.check()


def _production(own):
    M.need(own is False, 'GENERATION_RUNTIME_NEVER_RELABELS_OWN')


def _self_pin():
    p = Path(__file__); s = p.lstat()
    M.need(p.is_absolute() and p.resolve() == p and stat.S_ISREG(s.st_mode)
           and s.st_nlink == 1 and not s.st_mode & 0o022,
           'GENERATION_RUNTIME_CANONICAL_FROZEN_SELF')
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify_sources():
    for name, pin in PINS.items():
        p = Path(importlib.import_module(name).__file__); s = p.lstat()
        M.need(p.is_absolute() and p.resolve() == p and stat.S_ISREG(s.st_mode)
               and s.st_nlink == 1 and not s.st_mode & 0o022
               and hashlib.sha256(p.read_bytes()).hexdigest() == pin,
               'GENERATION_RUNTIME_EXACT_FROZEN_COMPONENTS')
    X.verify_sources(); B.verify_sources(); N.verify_sources(); AC.verify_sources()
    for module, names in (
        (N, ('prepare_registered_graph','_same','_private_make','_receiver_hook')),
        (AC, ('bind_original_active_clock_methods',)),
        (L, ('_restore','_financial','_registered','_guarded_poll')),
        (B, ('_registered_production','_current','_stage_poll','_restore_new_core','restore_registered')),
        (A, ('_history','_prepare','_verify','_closed_leaf')),
        (E, ('_guard','_observe','poll','_publish','_verify_complete','_registered','_result')),
        (Q, ('_production_graph','_anchor','_current','bind_registered','start','poll')),
        (R, ('_inspect','_same','_capture')),
        (X, ('_bound','_history_bindings','_capture_function','capture_registered',
             'verify_registered_source','publisher_function','history_publisher_function',
             '_read_lineage','read_resource_history','publish_for_owner'))):
        for name in names:
            if (module, name) in ((B, '_registered_production'), (E, '_registered')):
                _declared_default_function(module, name)
            else:
                GF._original_functions(module, (name,))
    _original_method(R, R.ResourceLineageSource, 'snapshot')
    _original_method(X, X.VerifiedContinuingResourceLineage, 'snapshot')
    _self_pin()
    return dict(PINS)


def _declared_default_function(module, name):
    # GF's original guard intentionally accepts only no-default functions.
    # These TWO exact original APIs have declared defaults. Preserve rather
    # than erase them; no arbitrary default/callback is accepted.
    M.need(type(name) is str and ((module is B and name == '_registered_production')
           or (module is E and name == '_registered')),
           'GENERATION_RUNTIME_ONLY_TWO_DECLARED_ORIGINAL_DEFAULT_APIS')
    fn = vars(module).get(name)
    M.need(type(fn) is FunctionType, 'GENERATION_RUNTIME_ORIGINAL_FUNCTION_TYPE_BEFORE_ATTRIBUTES')
    M.need(fn.__globals__ is vars(module) and type(fn.__module__) is type(module.__name__) is str
           and type(fn.__name__) is type(fn.__qualname__) is str
           and fn.__module__ == module.__name__ and fn.__name__ == fn.__qualname__ == name and fn.__closure__ is None
           and type(fn.__annotations__) is dict and not fn.__annotations__
           and type(fn.__dict__) is dict and not fn.__dict__,
           'GENERATION_RUNTIME_ORIGINAL_DEFAULT_FUNCTION_NAMESPACE')
    if module is B:
        kw = fn.__kwdefaults__
        M.need(fn.__defaults__ is None and type(kw) is dict
               and all(type(k) is str for k in kw) and set(kw) == {'before_restore'}
               and kw['before_restore'] is False,
               'GENERATION_RUNTIME_EXACT_BEFORE_RESTORE_FALSE_DEFAULT')
    else:
        M.need(GF._same_builtin(fn.__defaults__, (None,)) and fn.__kwdefaults__ is None,
               'GENERATION_RUNTIME_EXACT_REGISTERED_OWN_NONE_DEFAULT')
    path = Path(module.__file__)
    compiled = compile(path.read_bytes(), str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize)
    expected = {c.co_name:c for c in compiled.co_consts if type(c) is CodeType}
    M.need(type(fn.__code__) is CodeType and GF._builtin_constants(fn.__code__)
           and GF._same_builtin(fn.__code__, expected[name]),
           'GENERATION_RUNTIME_ALL_ORIGINAL_DEFAULT_FUNCTION_CODE_FIELDS')


def _original_method(module, cls, name):
    M.need(type(cls) is type and type(name) is str and vars(module).get(cls.__name__) is cls,
           'GENERATION_RUNTIME_ONLY_EXACT_ORIGINAL_SOURCE_CLASS')
    fn = vars(cls).get(name)
    M.need(type(fn) is FunctionType and fn.__globals__ is vars(module)
           and fn.__defaults__ is None and fn.__kwdefaults__ is None and fn.__closure__ is None
           and type(fn.__dict__) is dict and not fn.__dict__,
           'GENERATION_RUNTIME_ONLY_ORIGINAL_METHOD_AND_NAMESPACE')
    path = Path(module.__file__)
    code = compile(path.read_bytes(), str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize)
    original_class = next(c for c in code.co_consts if type(c) is CodeType and c.co_name == cls.__name__)
    expected = next(c for c in original_class.co_consts if type(c) is CodeType and c.co_name == name)
    M.need(type(fn.__code__) is CodeType and GF._builtin_constants(fn.__code__)
           and GF._same_builtin(fn.__code__, expected),
           'GENERATION_RUNTIME_ALL_ORIGINAL_METHOD_CODE_FIELDS')


def _clone(original, bindings):
    return X._clone(original, bindings)


def _copy_module(original):
    # Private namespace only. Original registry dictionaries/classes/seals are
    # the identical objects, not a forged or writable metadata replacement.
    return SimpleNamespace(**vars(original))


def _ticket(ticket, *, owner, read_budget):
    return G.verify_ticket(ticket, owner=owner, read_budget=read_budget, own=False)


def _history(reference, *, history_reference, owner, ticket, read_budget, own):
    _production(own)
    return GS.read_system_history(reference, history_reference=history_reference,
        owner=owner, ticket=ticket, read_budget=read_budget)


def _services_verifier(own):
    _production(own)
    return GS.verify_reference


def _resource_history(reference, *, owner, ticket, read_budget, own):
    _production(own)
    # This preserves the ORIGINAL legacy parser/type guard. A continuing
    # lineage reference requires the distinct public readonly verifier below,
    # never a legacy fallback or fabricated original history capability.
    return GS.read_resource_history(reference, owner=owner, ticket=ticket, read_budget=read_budget)


def _apis():
    global _CACHE
    verify_sources()
    if _CACHE is not None:
        return _CACHE
    n, a, e, q, r, b, x = (_copy_module(module) for module in (N,A,E,Q,R,B,X))
    clock = GS._ports(AC.bind_original_active_clock_methods,
        [('T.verify_inert_ticket(ticket, owner=owner, read_budget=read_budget)',
          '_generation_ticket(ticket, owner=owner, read_budget=read_budget)', 1)],
        dict(_generation_ticket=_ticket))
    hook = GS._ports(N._receiver_hook,
        [('A.bind_original_active_clock_methods(stage, owner=context.source_owner, ticket=context.source_ticket, read_budget=read_budget)',
          '_generation_clock(stage, owner=context.source_owner, ticket=context.source_ticket, read_budget=read_budget)', 1)],
        dict(_generation_clock=clock))
    n._private_make = _clone(N._private_make, dict(_receiver_hook=hook))
    n.prepare_registered_graph = GS._ports(N.prepare_registered_graph, [
        ('F.load_registered_source(owner, ticket=ticket, read_budget=read_budget)',
         '_generation_financial(owner, ticket=ticket, read_budget=read_budget)', 1),
        ('module.verify_reference(services_reference, owner=owner, ticket=ticket, read_budget=read_budget)',
         '_generation_services(services_reference, owner=owner, ticket=ticket, read_budget=read_budget)', 1),
        ('T.verify_inert_ticket(ticket, owner=owner, read_budget=read_budget)',
         '_generation_ticket(ticket, owner=owner, read_budget=read_budget)', 1)],
        dict(_generation_financial=GF.load_registered_source, _generation_services=GS.verify_reference,
             _generation_ticket=_ticket, _private_make=n._private_make))
    n._same = GS._ports(N._same, [
        ("T.verify_inert_ticket(record['ticket'], owner=record['owner'], read_budget=budget)",
         "_generation_ticket(record['ticket'], owner=record['owner'], read_budget=budget)", 1),
        ("_services_module().verify_reference(record['context'].services_reference, owner=record['owner'], ticket=record['ticket'], read_budget=budget)",
         "_generation_services(record['context'].services_reference, owner=record['owner'], ticket=record['ticket'], read_budget=budget)", 1)],
        dict(_generation_ticket=_ticket, _generation_services=GS.verify_reference))
    a._history = GS._ports(A._history,
        [('(R.read_OWN_history if own else R.read_history)(reference, owner=owner, ticket=ticket, read_budget=budget)',
          '_generation_resource_history(reference, owner=owner, ticket=ticket, read_budget=budget, own=own)', 1)],
        dict(_generation_resource_history=_resource_history))
    a._prepare = _clone(A._prepare, dict(_history=a._history))
    a._verify = _clone(A._verify, dict(_history=a._history))
    def archive_verify(value, *, owner, ticket, read_budget):
        return a._verify(value, owner=owner, ticket=ticket, read_budget=read_budget, own=False)
    a.verify_before_transition = archive_verify
    e._guard = GS._ports(E._guard,
        [("C.verify_OWN_reference if r['OWN'] else C.verify_reference",
          "_generation_services_verifier(r['OWN'])", 1)],
        dict(_generation_services_verifier=_services_verifier, A=a))
    for name in ('_observe','poll','_publish','_verify_complete'):
        setattr(e, name, _clone(getattr(E, name), dict(A=a, _guard=e._guard)))
    def epoch_verify(value, *, read_budget):
        return e._verify_complete(value, read_budget=read_budget, own=False)
    e.verify_complete = epoch_verify
    q._production_graph = GS._ports(Q._production_graph,
        [("h._same(stage, budget, own=False)", "_generation_held_same(stage, budget, own=False)", 1)],
        dict(_generation_held_same=n._same))
    q._anchor = _clone(Q._anchor, dict(E=e))
    q._current = _clone(Q._current, dict(E=e, _production_graph=q._production_graph, _anchor=q._anchor))
    q.bind_registered = _clone(Q.bind_registered, dict(E=e, _production_graph=q._production_graph))
    for name in ('start','poll'):
        setattr(q, name, _clone(getattr(Q, name), dict(_current=q._current)))
    financial = GS._ports(L._financial,
        [('F.load_registered_source(owner, ticket=ticket, read_budget=budget)',
          '_generation_financial(owner, ticket=ticket, read_budget=budget)', 1)],
        dict(_generation_financial=GF.load_registered_source))
    def private_restore(source_owner):
        return GS._ports(L._restore, [
            ('(H.read_OWN_history if own else H.read_history)(reference, history_reference=history_reference, owner=owner, ticket=ticket, read_budget=read_budget)',
             '_generation_history(reference, history_reference=history_reference, owner=_stage_source_owner, ticket=ticket, read_budget=read_budget, own=own)', 2),
            ('_financial(owner, ticket, history, budget=read_budget, own=own)',
             '_generation_financial(_stage_source_owner, ticket, history, budget=read_budget, own=own)', 1)],
            dict(_generation_history=_history, _stage_source_owner=source_owner,
                 _generation_financial=financial))
    production_pins = {name:PINS[name] for name in
        ('normal_held_financial_writer','staged_financial_runtime','resource_epoch_continuing_producer_v6')}
    def production_pin(name, pin):
        M.need(name in production_pins and production_pins[name] == pin,
               'GENERATION_RUNTIME_ONLY_EXACT_N_STAGE_AND_Q6_PRODUCTION_PIN_PORTS')
        actual = B._pin(name, pin)
        if actual is N: return n
        if actual is Q: return q
        M.need(actual is ST, 'GENERATION_RUNTIME_ONLY_ORIGINAL_STAGE_CLASS_MODULE')
        return actual
    b._registered_production = _clone(B._registered_production,
        dict(PRODUCTION_PINS=production_pins, _pin=production_pin))
    b._current = _clone(B._current, dict(_registered_production=b._registered_production))
    b._stage_poll = _clone(B._stage_poll, dict(_current=b._current))
    b._restore_new_core = _clone(B._restore_new_core, dict(_private_restore=private_restore,
        _current=b._current, _stage_poll=b._stage_poll))
    b.restore_registered = GS._ports(B.restore_registered, [
        ('home / K.LEAF_NAME', "_generation_history_leaf(home, record['ticket'], read_budget)", 2),
        ('K.load_reference', '_generation_history_reference', 1)],
        dict(_generation_history_leaf=GS._history_leaf,
             _generation_history_reference=GS.load_system_history_reference,
             _registered_production=b._registered_production, _restore_new_core=b._restore_new_core))
    def lineage_modules():
        modules = R.verify_sources()
        modules['resource_epoch_continuing_producer_v6'] = q
        modules['resource_epoch_transition_v3'] = e
        modules['resource_epoch_archive_v2'] = a
        return modules
    r._inspect = _clone(R._inspect, dict(verify_sources=lineage_modules))
    r._same = _clone(R._same, dict(_inspect=r._inspect))
    r._capture = _clone(R._capture, dict(_inspect=r._inspect))
    def capture_resource(bound, *, read_budget):
        return r._capture(bound, read_budget, False)
    r.capture_registered = capture_resource
    resource_snapshot = _clone(R.ResourceLineageSource.snapshot, dict(_same=r._same))
    x._bound = _clone(X._bound, dict(Q=q))
    x._history_bindings = GS._ports(X._history_bindings,
        [('resource_cap.snapshot(read_budget=budget)',
          '_generation_resource_snapshot(resource_cap, read_budget=budget)', 1)],
        dict(R=r, _generation_resource_snapshot=resource_snapshot, _self_pin=_self_pin))
    x._capture_function = _clone(X._capture_function, dict(_history_bindings=x._history_bindings))
    x.verify_registered_source = _clone(X.verify_registered_source,
        dict(Q=q, _capture_function=x._capture_function))
    x.capture_registered = _clone(X.capture_registered, dict(_bound=x._bound, R=r,
        _capture_function=x._capture_function, verify_registered_source=x.verify_registered_source))
    x.live_source_function = _clone(X.live_source_function,
        dict(verify_registered_source=x.verify_registered_source))
    x.publisher_function = _clone(X.publisher_function,
        dict(live_source_function=x.live_source_function))
    x.publish_source = _clone(X.publish_source, dict(publisher_function=x.publisher_function))
    x.history_publisher_function = _clone(X.history_publisher_function,
        dict(verify_registered_source=x.verify_registered_source))
    x.publish_system_history = _clone(X.publish_system_history,
        dict(live_source_function=x.live_source_function,
             history_publisher_function=x.history_publisher_function))
    x.publish_for_owner = _clone(X.publish_for_owner, dict(capture_registered=x.capture_registered,
        publish_source=x.publish_source, publish_system_history=x.publish_system_history))
    x._read_lineage = _clone(X._read_lineage, dict(_self_pin=_self_pin))
    history_globals = dict(VerifiedContinuingResourceLineage=VerifiedContinuingResourceLineage,
        _READS=_HISTORY_READS, _READ_ATTEMPTS=_HISTORY_ATTEMPTS, _SEAL=_HISTORY_SEAL,
        _read_lineage=x._read_lineage)
    x.read_resource_history = _clone(X.read_resource_history, history_globals)
    history_snapshot = _clone(X.VerifiedContinuingResourceLineage.snapshot, history_globals)
    _CACHE = SimpleNamespace(held=n, archive=a, epoch=e, resource=q, lineage=r, system=b, source=x,
        clock=clock, hook=hook, financial=financial, private_restore=private_restore,
        resource_snapshot=resource_snapshot, history_snapshot=history_snapshot)
    return _CACHE


class VerifiedContinuingResourceLineage:
    def __init__(self, *a, **k):
        raise M.PaidColdWait('GENERATION_RUNTIME_ONLY_TYPED_READONLY_CONTINUING_HISTORY')
    def snapshot(self, *, read_budget):
        return _apis().history_snapshot(self, read_budget=read_budget)
    @property
    def safe_to_TERM(self): return False
    @property
    def resource_sampler_restored(self): return False
    @property
    def paid_activation_authorized(self): return False
    @property
    def whole_runnable_ready(self): return False


def prepare_held_graph(ticket, *, owner, services_reference, read_budget):
    _budget(read_budget)
    return _apis().held.prepare_registered_graph(ticket, owner=owner,
        services_reference=services_reference, read_budget=read_budget)


def archive_before_transition(reference, *, owner, ticket, read_budget):
    _budget(read_budget)
    return _apis().archive._prepare(reference, owner=owner, ticket=ticket, read_budget=read_budget, own=False)


def observe(archive, *, owner, ticket, read_budget):
    _budget(read_budget)
    return _apis().epoch._observe(archive, owner=owner, ticket=ticket, read_budget=read_budget, own=False)


def poll_epoch(epoch, *, read_budget):
    _budget(read_budget); api = _apis()
    E._registered(epoch, False)
    return api.epoch.poll(epoch, read_budget=read_budget)


def publish_epoch(epoch, *, read_budget):
    _budget(read_budget)
    return _apis().epoch._publish(epoch, read_budget=read_budget, own=False)


def bind_resource(graph, *, epoch, read_budget):
    _budget(read_budget)
    return _apis().resource.bind_registered(graph, epoch=epoch, read_budget=read_budget)


def restore_SYSTEM(graph, *, resource_binding, read_budget):
    _budget(read_budget)
    return _apis().system.restore_registered(graph, resource_binding=resource_binding, read_budget=read_budget)


def start_resource(binding, *, read_budget):
    _budget(read_budget)
    M.need(type(binding) is Q.ContinuingResourceReceiver and binding.OWN is False,
           'GENERATION_RUNTIME_ONLY_ORIGINAL_PRODUCTION_RESOURCE_BINDING')
    return _apis().resource.start(binding, read_budget=read_budget)


def poll_resource(binding, *, read_budget):
    _budget(read_budget)
    M.need(type(binding) is Q.ContinuingResourceReceiver and binding.OWN is False,
           'GENERATION_RUNTIME_ONLY_ORIGINAL_PRODUCTION_RESOURCE_BINDING')
    return _apis().resource.poll(binding, read_budget=read_budget)


def publish_for_owner(owner):
    return _apis().source.publish_for_owner(owner)


def read_resource_history(reference, *, owner, ticket, read_budget):
    _budget(read_budget)
    return _apis().source.read_resource_history(reference, owner=owner, ticket=ticket, read_budget=read_budget)
