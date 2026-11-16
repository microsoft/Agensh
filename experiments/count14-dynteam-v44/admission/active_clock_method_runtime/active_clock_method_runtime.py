"""Original active-clock method graph on a NEW held, unpublished receiver.

No constructor on paid history, elapsed-time inference, anchor reset, ledger
write, gate release, SDK operation or new process is performed. This supplies
the actual original tx/latch/fence observer wrappers missing from the first
INERT financial stage; it is not writer or paid-activation authority.
"""
from dataclasses import asdict
from pathlib import Path
from types import MethodType
import ast
import copy
import hashlib
import importlib
import time

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget, ram_lock
from native_peer_registry import process_birth

PINS = dict(
    native_active_clock='c95c9ef2ca03aa80774bf23ea78a9c05c0458b1aa48055b192de231815426849',
    clock_controls_cold='395a5ad1edaf8f622f5a88d87a2cffb2bef22003bcdcb28a08b03dc9835baa29',
    original_runtime_method_graph='d046c68d90fb81c54206a12cb4262772aeeff6ba569694b369a7308c53ef6ec8',
    staged_financial_runtime='62de21eed76372cbe6d6721da10891d0a86e4cfc65dbbdbbf22294b3e49baba5',
    normal_inert_cut='aac25e6b4f30c199a84d1ac7f5652283585f259f93a2d3f4a3e3134c9f203262',
    dynteam_membership_fence='2f6e13e919778c4dcfc985ca3338ddbb89b77cac98437f7adb19ff02bf192a51',
)


def verify_sources():
    for name, pin in PINS.items():
        path = Path(importlib.import_module(name).__file__)
        M.need(path.is_absolute() and path.resolve() == path and not path.is_symlink()
               and hashlib.sha256(path.read_bytes()).hexdigest() == pin,
               'ACTIVE_CLOCK_RUNTIME_FIXED_ORIGINAL_COMPONENT_PINS')
    return dict(PINS)


def _original_tail():
    from native_active_clock import NativeActiveClock
    from original_runtime_method_graph import _function, _compile
    verify_sources()
    body = _function(NativeActiveClock.__init__).body
    starts = [i for i, n in enumerate(body) if isinstance(n, ast.FunctionDef) and n.name == 'observed_tx']
    M.need(len(starts) == 1 and isinstance(body[-1], ast.For),
           'ACTIVE_CLOCK_RUNTIME_ORIGINAL_OBSERVER_TAIL_BOUNDARIES')
    nodes = body[starts[0]:]
    M.need(not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr in ('execute', 'executescript', '_observe_safely')
                   for statement in nodes if not isinstance(statement, ast.FunctionDef)
                   for n in ast.walk(statement) if not isinstance(statement, ast.For)),
           'ACTIVE_CLOCK_RUNTIME_BIND_TAIL_NO_EAGER_SQL_OR_CLOCK_OBSERVATION')
    return _compile(NativeActiveClock.__init__, nodes, ['self', 'core'],
                    'ACTIVE_CLOCK_ORIGINAL_OBSERVER_METHOD_TAIL_ONLY')


def _bind(core, controls, *, read_budget, own, monotonic_ns=None):
    from admission_gate import AdmissionGate
    from budget import Ledger
    from dynteam_membership_fence import MembershipFence
    from native_active_clock import NativeActiveClock
    from original_relay_core import OriginalRelayCore
    import clock_controls_cold as C
    M.need(type(read_budget) is ReadBudget, 'ACTIVE_CLOCK_RUNTIME_FINITE_READ_BUDGET')
    read_budget.check(); verify_sources()
    M.need(type(core) is OriginalRelayCore and type(core.ledger) is Ledger
           and core.qualification_only is own and not core.scientific_activation_qualified
           and not hasattr(core, 'active_clock') and not core.ledger.mutex._is_owned(),
           'ACTIVE_CLOCK_RUNTIME_ONLY_NEW_UNPUBLISHED_HELD_GRAPH')
    M.need(monotonic_ns is None or own, 'ACTIVE_CLOCK_RUNTIME_PRODUCTION_ORIGINAL_MONOTONIC_ONLY')
    M.need(type(getattr(core, 'gate', None)) is AdmissionGate
           and core.gate.ledger is core.ledger and core.gate.condition is core.ledger.capacity_changed
           and core.gate.condition._lock is core.ledger.mutex
           and set(core.gate.startup_held) == set(core.rows),
           'ACTIVE_CLOCK_RUNTIME_WAIT_SAME_ORIGINAL_FULLY_HELD_GATE')
    M.need(type(getattr(core, 'membership_fences', None)) is dict
           and set(core.membership_fences) == set(core.rows)
           and all(type(f) is MembershipFence for f in core.membership_fences.values()),
           'ACTIVE_CLOCK_RUNTIME_WAIT_REAL_ALL_ROLE_MEMBERSHIP_FENCES')
    M.need(type(controls) is dict and controls.get('schema') == C.SCHEMA
           and controls.get('source_pins') == C.PINS and controls.get('OWN') is own
           and set(controls.get('tracks', {})) == set(core.rows),
           'ACTIVE_CLOCK_RUNTIME_ORIGINAL_VERIFIED_COMPLETE_POST_CLOCK_CONTROLS')
    value = NativeActiveClock.__new__(NativeActiveClock)
    value.core, value.ledger = core, core.ledger
    value.now = time.monotonic_ns if monotonic_ns is None else monotonic_ns
    value.failure_type = None
    value.states = {}
    with ram_lock(core.ledger.mutex, read_budget):
        M.need(not core.ledger.db.in_transaction,
               'ACTIVE_CLOCK_RUNTIME_NO_EXISTING_TRANSACTION_OR_FINANCIAL_WRITES')
        for trajectory, row in controls['tracks'].items():
            state = row['active']
            M.need(type(state) is dict and set(state) == {'active_ns', 'observed_ns', 'mode'}
                   and C.uint(state['active_ns']) and C.uint(state['observed_ns'])
                   and state['mode'] in ('HOLD', 'FINAL'),
                   'ACTIVE_CLOCK_RUNTIME_NO_RUNNING_INTERVAL_OR_DEFAULT_TIME')
            # Keep BOTH original numbers exactly. The next ORIGINAL observation
            # updates its anchor while HOLD/FINAL and adds no downtime interval.
            value.states[trajectory] = dict(state)
        pauses = {}
        for row in controls['budget_pause']:
            key = row['trajectory'], row['role']
            M.need(key not in pauses and key[0] in core.rows and key[1] in core.rows[key[0]]['roles']
                   and C.uint(row['total_ns']) and row['since_ns'] is None,
                   'ACTIVE_CLOCK_RUNTIME_ORIGINAL_SHUTDOWN_SETTLED_PAUSE_COUNTERS')
            pauses[key] = dict(total_ns=row['total_ns'], since_ns=None)
        M.need(core.gate._budget_pause == pauses,
               'ACTIVE_CLOCK_RUNTIME_POST_SHUTDOWN_PAUSES_ALREADY_RESTORED_EXACTLY')
        value.original_tx = core.ledger.tx
        value.original_latch = core.ledger.latch_fault
        value.original_hold = core.gate.hold_startup
        value.original_release = core.gate.release_startup
    method, proof = _original_tail()
    # Pure method binding, outside scientific locks. Original class/module and
    # all original guards remain byte-for-byte unchanged.
    core.active_clock = value
    method(value, core)
    read_budget.check()
    return value, dict(proof, same_original_active_and_observed_ns=True,
        explicit_source_post_shutdown_pause_counters=True, constructor_called=False,
        new_clock_observation_or_SQL_executed_by_binding=False,
        gate_or_model_released=False, paid_activation_authorized=False,
        whole_runnable_ready=False, safe_to_TERM=False, OWN=own)


def bind_original_active_clock_methods(stage, *, owner, ticket, read_budget):
    """Fixed pre-quarantine hook for the new independent receiver factory."""
    import normal_inert_cut as T
    import staged_financial_runtime as S
    M.need(type(stage) is S.StagedFinancialRuntime and stage._seal is S._SEAL
           and stage.OWN is False and stage.OWN_writer_open is False
           and not stage.paid_activation_authorized,
           'ACTIVE_CLOCK_RUNTIME_EXACT_UNPUBLISHED_PRODUCTION_STAGE_NOT_WRITER_AUTHORITY')
    cap = T.verify_inert_ticket(ticket, owner=owner, read_budget=read_budget)
    M.need(type(cap) is T.VerifiedNormalInertCut and cap.OWN is False
           and cap.new_owner_birth == stage.new_owner_birth == process_birth(__import__('os').getpid())
           and cap.old_owner_birth == stage.old_owner_birth
           and cap.contract_sha256 == M.digest(stage.core.contract)
           and stage.core.home == owner.core.home
           and tuple(stage.context.lock_fds) == tuple(owner.core.metadata_inert_pair.lock_fds),
           'ACTIVE_CLOCK_RUNTIME_ORIGINAL_T_AND_STAGE_EXACT_NEW_BIRTH_HOME_CONTRACT_LOCKS')
    controls = cap._body['post_retirement_controls']['normal_clock_controls']
    M.need(controls['source_owner_birth'] == asdict(cap.old_owner_birth),
           'ACTIVE_CLOCK_RUNTIME_ORIGINAL_POST_SOURCE_BIRTH')
    clock, proof = _bind(stage.core, controls, read_budget=read_budget, own=False)
    stage.method_proofs.append(proof)
    return clock


def bind_OWN_original_active_clock_methods(core, controls, *, read_budget, monotonic_ns=None):
    M.need(core.qualification_only is True and all(t.startswith('OWN-') for t in core.rows),
           'ACTIVE_CLOCK_RUNTIME_ONLY_EXPLICIT_OWN_COMPONENT_PORT')
    return _bind(core, controls, read_budget=read_budget, own=True, monotonic_ns=monotonic_ns)
