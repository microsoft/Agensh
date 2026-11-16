"""Finite original RAM clock control candidate; no SQL, state body or authority.

No live clock observation is called under a scientific mutex. The original
checkpoint_control_state return fields are copied only once its source states
already say HOLD/FINAL at the six original committed cuts. No elapsed time is
inferred from a wall/monotonic difference. This is not a whole-graph seal.
"""
from dataclasses import asdict
import copy
import hashlib
import importlib
from pathlib import Path
import math
import threading
import time
from types import SimpleNamespace

import normal_cold_sealer as S
from bounded_metadata_ro import ReadBudget, ram_lock
from native_active_clock import NativeActiveClock
from racing_native_binding import BottleneckSchedule

SCHEMA = 'count14-normal-clocks-control-candidate-v1'
SCHEDULE_FIELDS = ('interval', 'last_progress', 'last_progress_at', 'last_round_at',
                   'open_round', 'ordinal', 'previous_time')
PINS = dict(
    native_active_clock='c95c9ef2ca03aa80774bf23ea78a9c05c0458b1aa48055b192de231815426849',
    formal_count14_tester='058bb70f38a073f8e71b3bee93752b95fafb840b47a8604e23d90b69c6bd4cde',
    native_idle_watchdog='bd35e62f6126778ee5c0c3d43a47c5a7aa04d992977088ce65ecb2efe6dd61e6',
    racing_native_binding='fac17e24a04d75b788daf27aa51995ad4daf172962f176825673a709ba1c8f5d',
    smoke_racing_tools_game_manager='cae89175eb99430c0b37a3dca1719b36b6f733eed7511e38ce0d6dcac0f56359',
    native_budget_park='2d906ac6ed892ead16abc2140b310920d8d2a8d9bdd2430e189716eb4588e93d',
    admission_gate='8504daf99a91a322add5338b55677218f2cb3d103bee401eaae720c9048a3821',
    budget='a05ca90afffb7c149766cf4b74126eb94ba79910afd72049a1ff54d2bc50df8f',
    original_relay_core='89ac900e66caa67887504522c574c1870f7a8faf51542fe248ca7f35b1541556',
    normal_cold_sealer='dd33e7a7a336c872086b3769f70e112942a466a18f52d099ce188ebe1e129e68',
    normal_cold_barrier='a778d6cde3bdb8840919231bb8336b4635762be9923cf1315d067461654f753e',
    native_cold_owner='22af3bfe52f711ee27bb4e523ed8ab13d375528b05f927afcb64c921095b5ddf',
    native_formal_cohort='7a38d82988e3c60181ece17e541c4c86c644ce160dfedba66fe235d5d03b7723')


def verify_sources():
    for name, pin in PINS.items():
        path = Path(importlib.import_module(name).__file__)
        S.need(path.is_absolute() and path.resolve() == path and not path.is_symlink() and
               hashlib.sha256(path.read_bytes()).hexdigest() == pin,
               'CLOCK_CONTROLS_EXACT_FROZEN_ORIGINAL_SOURCE')
    return dict(PINS)


def uint(value):
    return type(value) is int and value >= 0


def seconds(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def pin(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def schedule_controls(schedule):
    S.need(type(schedule) is BottleneckSchedule, 'CLOCK_CONTROLS_ORIGINAL_SCHEDULE_TYPE')
    row = {name: getattr(schedule, name) for name in SCHEDULE_FIELDS}
    S.need(row['interval'] == 600 and uint(row['ordinal']) and
           all(row[k] is None or seconds(row[k]) for k in
               ('last_progress_at', 'last_round_at', 'previous_time')) and
           (row['last_progress'] is None or uint(row['last_progress'])) and
           (row['open_round'] is None or type(row['open_round']) is int and
            1 <= row['open_round'] <= row['ordinal']), 'CLOCK_CONTROLS_TYPED_ORIGINAL_SCHEDULE_FIELDS')
    return row


def _project(core, tracks, idle, cut_refs, read_budget):
    """Shared projection only; production identity/cut guard is not an argument."""
    from formal_count14_tester import FormalCount14Tester, CADENCE_ACTIVE_SECONDS
    from native_budget_park import NativeBudgetParkProjection
    from native_idle_watchdog import NativeIdleWatchdog
    from smoke_racing_tools_game_manager import NativeRacingGameManager
    S.need(type(read_budget) is ReadBudget and type(idle) is NativeIdleWatchdog and
           idle.core is core and set(core.rows) == set(tracks) == set(cut_refs) == set(idle.rows) and
           len(core.rows) == 6 and not core.ledger.mutex._is_owned(),
           'CLOCK_CONTROLS_REGISTERED_SIX_AND_FINITE_CALLER_BUDGET')
    read_budget.check()
    active = core.active_clock
    S.need(type(active) is NativeActiveClock and active.core is core and active.ledger is core.ledger,
           'CLOCK_CONTROLS_EXACT_ORIGINAL_SOURCE_ACTIVE_CLOCK')
    with ram_lock(core.ledger.mutex, read_budget):
        S.need(active.failure_type is None and set(active.states) == set(core.rows),
               'CLOCK_CONTROLS_HEALTHY_COMPLETE_ORIGINAL_ACTIVE_STATE')
        active_rows = {}
        for t, row in active.states.items():
            S.need(type(row) is dict and set(row) == {'active_ns', 'observed_ns', 'mode'} and
                   uint(row['active_ns']) and uint(row['observed_ns']) and row['mode'] in ('HOLD', 'FINAL'),
                   'CLOCK_CONTROLS_NO_RUNNING_INTERVAL_OR_DEFAULT_ELAPSED')
            active_rows[t] = dict(row)  # Original checkpoint_control_state return shape; NO observe/SQL.
        pauses = []
        for (t, role), row in sorted(core.gate._budget_pause.items()):
            S.need(t in core.rows and role in core.rows[t]['roles'] and type(row) is dict and
                   set(row) == {'total_ns', 'since_ns'} and uint(row['total_ns']) and
                   (row['since_ns'] is None or uint(row['since_ns'])),
                   'CLOCK_CONTROLS_ORIGINAL_NUMERIC_BUDGET_PAUSE_ONLY')
            pauses.append(dict(trajectory=t, role=role, total_ns=row['total_ns'], since_ns=row['since_ns']))
    result = {}
    for t, track in sorted(tracks.items()):
        read_budget.check()
        host, cp = track['host'], track['checkpoint']
        tester = host.tester
        S.need(host.held and cp.core is core and cp.t == t and cp.writer is not None and
               cp.writer.writer_fence.state == 'PARKED' and cp.reference == cp.writer.reference and
               type(tester) is FormalCount14Tester and tester.core is core and tester.t == t,
               'CLOCK_CONTROLS_ORIGINAL_HELD_HOST_AND_LAST_CUT')
        with ram_lock(tester.lock, read_budget):
            S.need(tester.hold is True and tester.busy is False and
                   (tester.thread is None or not tester.thread.is_alive()) and
                   seconds(tester.start_active) and type(tester.next_number) is int and tester.next_number >= 1 and
                   type(tester.closed) is bool, 'CLOCK_CONTROLS_ACTIVATED_TESTER_DRAINED_CADENCE_NO_DEFAULT')
            tester_row = dict(start_active=tester.start_active, next_number=tester.next_number,
                              hold=tester.hold, closed=tester.closed,
                              cadence_active_seconds=CADENCE_ACTIVE_SECONDS)
        row = idle.rows[t]  # Same sole owner thread; no child body/SQL or callbacks.
        S.need(row['held'] is True and row['child'] is None and row['failure'] is None and
               row['host'] is host and uint(row['ordinal']) and uint(row['sequence']) and
               (row['last_active'] is None if row['ordinal'] == 0 else uint(row['last_active'])) and
               type(row['closed']) is bool, 'CLOCK_CONTROLS_IDLE_HELD_PHYSICAL_CLEAR_CONTROL_ONLY')
        idle_row = {k: row[k] for k in ('last_active', 'ordinal', 'sequence', 'held', 'closed')}
        projection = core.clocks[t]
        S.need(type(projection) is NativeBudgetParkProjection and projection.gate is core.gate and
               projection.t == t, 'CLOCK_CONTROLS_EXISTING_ORIGINAL_PAUSE_PROJECTION')
        with ram_lock(projection.lock, read_budget):
            S.need(not projection.closed and uint(projection.sequence) and
                   set(projection.bindings) == set(core.rows[t]['roles']),
                   'CLOCK_CONTROLS_COMPLETE_EXISTING_PAUSE_BINDINGS')
            # The existing publisher increments sequence every .5s even while
            # science is held. It is not a frozen timer value and must not make
            # sealer.before == sealer.after perpetually unstable. Future actual
            # publisher retirement/adoption must preserve its own final sequence.
            projection_row = dict(directory=str(projection.directory),
                directory_identity=list(projection.directory_identity),
                binding_sha256={r: S.digest(b) for r, b in sorted(projection.bindings.items())},
                live_publisher_sequence_retirement_not_qualified=True)
        manager = host.manager
        racing = None
        if core.rows[t]['arm'] == 'DYNTEAM_RACING':
            S.need(type(manager) is NativeRacingGameManager and manager.core is core and manager.t == t and
                   manager.failure is None, 'CLOCK_CONTROLS_ORIGINAL_REGISTERED_RACING_MANAGER')
            racing = dict(schedule=schedule_controls(manager.schedule), accepted_public=manager.accepted_public,
                          interval_active_seconds=600, guest_Game_or_PhaseClock_hydrated=False)
            S.need(uint(racing['accepted_public']),
                   'CLOCK_CONTROLS_RACING_PUBLIC_COUNTERS_ONLY')
        else:
            S.need(core.rows[t]['arm'] == 'DYNTEAM' and manager is None,
                   'CLOCK_CONTROLS_BASELINE_NO_INVENTED_RACING_CLOCK')
        result[t] = dict(active=active_rows[t], tester=tester_row, idle=idle_row,
                         budget_projection=projection_row, racing=racing,
                         original_last_cut=copy.deepcopy(cut_refs[t]))
    read_budget.check()
    return dict(tracks=result, budget_pause=pauses,
                formulas=dict(active_original='NativeActiveClock._observe_all_locked',
                              tester_active_seconds=1800, idle_active_seconds=60, racing_active_seconds=600))


def capture_registered(owner, *, read_budget):
    """Prospective metadata source only, from SAME original six-cut source graph."""
    from native_cold_owner import NativeColdOwner
    from original_relay_core import OriginalRelayCore
    from native_formal_cohort import NativeFormalCohort
    from normal_cold_barrier import NormalCheckpointBarrier
    pins = verify_sources()
    S.need(type(owner) is NativeColdOwner and type(owner.core) is OriginalRelayCore and
           type(owner.scientific_smoke) is NativeFormalCohort and
           type(owner.normal_cold_sealer) is S.NormalColdCandidateSealer,
           'CLOCK_CONTROLS_EXACT_REGISTERED_SOURCE_OWNER_GRAPH')
    sealer, core, cohort = owner.normal_cold_sealer, owner.core, owner.scientific_smoke
    sealer._current()
    barrier = owner.normal_cold_barrier
    S.need(type(barrier) is NormalCheckpointBarrier and barrier is sealer.barrier and
           barrier.cohort is cohort and barrier.core is core and not core.qualification_only and
           barrier.requested and barrier.failure is None and barrier.last_static_observation and
           set(barrier.observed) == set(barrier.checkpoints) == set(core.rows),
           'CLOCK_CONTROLS_ALREADY_OBSERVED_SIX_FROZEN_NORMAL_CUTS_ONLY')
    refs = {}
    for t, (cp, _, _) in sorted(barrier.checkpoints.items()):
        observed = barrier.observed[t]
        S.need(observed['original_frozen_checkpoint_verified'] is True and
               cp is cohort.tracks[t]['checkpoint'] and cp.state in ('COMMITTED', 'POINT_QUEUED', 'FINAL_PARKED') and
               observed['snapshot_sha256'] == cp.reference['sha256'] and pin(cp.writer.cut.cut_sha),
               'CLOCK_CONTROLS_CURRENT_ORIGINAL_REFERENCE_NOT_REPLACED')
        refs[t] = dict(snapshot_sha256=cp.reference['sha256'], original_cut_sha256=cp.writer.cut.cut_sha,
                       generation=observed['generation'], target=observed['target'], phase=cp.state)
    projection = _project(core, cohort.tracks, cohort.native_idle_watchdog, refs, read_budget)
    sealer._current()
    S.need(barrier.last_static_observation and all(
        cohort.tracks[t]['checkpoint'].reference['sha256'] == r['snapshot_sha256'] and
        cohort.tracks[t]['checkpoint'].state == r['phase'] for t, r in refs.items()),
        'CLOCK_CONTROLS_SOURCE_CUT_CHANGED_RETRY_OBSERVATION')
    return dict(schema=SCHEMA, contract_sha256=sealer.source_binding,
                source_owner_birth=asdict(sealer.birth), source_pins=pins,
                original_RAM_control_source=True, actual_six_source_guard_used=True,
                original_checkpoint_control_method_observe_called=False,
                whole_seal_or_production_restore_ready=False, candidate_notready=True,
                OWN=False, **projection)


def restore_paused_schedule(candidate, trajectory):
    """Restore original finite scheduler controls, NOT a guest Game/future."""
    verify_sources()
    S.need(candidate['schema'] == SCHEMA and candidate['source_pins'] == PINS and
           candidate['candidate_notready'] is True and
           candidate['whole_seal_or_production_restore_ready'] is False,
           'CLOCK_CONTROLS_CANDIDATE_CANNOT_BECOME_RUNTIME_AUTHORITY')
    row = candidate['tracks'][trajectory]['racing']
    S.need(type(row) is dict and row['guest_Game_or_PhaseClock_hydrated'] is False,
           'CLOCK_CONTROLS_ONLY_RESTORE_REAL_RACING_SCHEDULE')
    value = BottleneckSchedule.__new__(BottleneckSchedule)
    S.need(set(row['schedule']) == set(SCHEDULE_FIELDS), 'CLOCK_CONTROLS_COMPLETE_SCHEDULE_NO_DEFAULTS')
    for name in SCHEDULE_FIELDS:
        setattr(value, name, row['schedule'][name])
    schedule_controls(value)
    return value


def restore_OWN_paused_active_component(candidate, core):
    """OWN real parked original Ledger/Gate ONLY; no financial constructor/bind.

    Original _mode_locked/read/active_now/checkpoint_control_state stay intact.
    Rebase only the new paused observation anchor, never add downtime elapsed.
    The result is deliberately NOT attached to core.active_clock or ledger.tx.
    Production partial/quarantined graphs are refused, not made executable.
    """
    from budget import Ledger
    from admission_gate import AdmissionGate
    from original_relay_core import OriginalRelayCore
    verify_sources()
    S.need(candidate['schema'] == SCHEMA and candidate.get('OWN') is True and
           candidate['source_pins'] == PINS and core.qualification_only is True and
           type(core) is OriginalRelayCore and type(core.ledger) is Ledger and type(core.gate) is AdmissionGate and
           core.gate.ledger is core.ledger and not core.scientific_activation_qualified and
           not hasattr(core, 'active_clock') and set(core.gate.startup_held) == set(core.rows) and
           set(candidate['tracks']) == set(core.rows) and all(t.startswith('OWN-') for t in core.rows),
           'CLOCK_CONTROLS_OWN_UNPUBLISHED_PARKED_ORIGINAL_GRAPH_NOT_PRODUCTION')
    value = NativeActiveClock.__new__(NativeActiveClock)
    value.core, value.ledger, value.now = core, core.ledger, time.monotonic_ns
    value.failure_type, value.states = None, {}
    now = value.now()
    with ram_lock(core.ledger.mutex, ReadBudget()):
        S.need(core.ledger.account.__func__ is Ledger.account and core.ledger.frontier.__func__ is Ledger.frontier,
               'CLOCK_CONTROLS_ORIGINAL_OWN_LEDGER_METHODS_NOT_QUARANTINE_BYPASS')
        for t in core.rows:
            S.need(core.ledger.frontier(t)['state'] == 'COMMITTED_PARKED',
                   'CLOCK_CONTROLS_OWN_REAL_COMMITTED_PARKED_LEDGER')
            row = candidate['tracks'][t]['active']
            S.need(set(row) == {'active_ns', 'observed_ns', 'mode'} and uint(row['active_ns']) and
                   uint(row['observed_ns']) and row['mode'] in ('HOLD', 'FINAL') and
                   value._mode_locked(t) == row['mode'], 'CLOCK_CONTROLS_ORIGINAL_MODE_FORMULA_MUST_MATCH')
            value.states[t] = dict(active_ns=row['active_ns'], observed_ns=now, mode=row['mode'])
    return value
