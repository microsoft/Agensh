"""Prospective same-owner normal-checkpoint barrier, NOT whole-paid authority.

No financial state transition, early cut, model cancellation, transport close,
snapshot rewrite, candidate output, or paid restoration is implemented here.
Only the CURRENT final instance methods are privately wrapped before activation.
"""
from types import MethodType
import copy
import hashlib
import json
import os
import threading

HELD_PHASES = frozenset(('COMMITTED', 'POINT_QUEUED', 'FINAL_PARKED'))


class BarrierWait(RuntimeError):
    pass


def need(ok, code):
    if not ok:
        raise BarrierWait(code)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def checkpoint_step(barrier, checkpoint, current):
    """The only phase delta; RELEASING/PARKED/PARKING/partial keep current code."""
    barrier._current()
    if barrier.requested and checkpoint.state in HELD_PHASES:
        return checkpoint.public()
    return current()


def final_poll(barrier, final, current, dispatcher, original_dispatcher_poll):
    """Keep paid natural accounting/custody; stop only new job dispatch."""
    barrier._current()
    need(final.dispatcher is dispatcher, 'NORMAL_BARRIER_SAME_ORIGINAL_FINAL_DISPATCHER')
    if not barrier.requested:
        return current()
    need(final.state in ('PREPARED_ORIGINAL_FINAL_MODELS_PAUSED', 'RELEASED'),
         'NORMAL_BARRIER_ORIGINAL_FINAL_POLL_STATE_REQUIRED')
    original_dispatcher_poll()  # current approved/natural/allowance _poll graph
    return final.public()


class NormalCheckpointBarrier:
    def __init__(self, cohort):
        from native_formal_cohort import NativeFormalCohort
        from native_cold_owner import NativeColdOwner
        from original_relay_core import OriginalRelayCore
        from native_peer_registry import process_birth
        core, owner = cohort.core, cohort.owner
        need(type(cohort) is NativeFormalCohort and type(owner) is NativeColdOwner
             and type(core) is OriginalRelayCore and owner.core is core
             and owner.scientific_smoke is cohort and not core.qualification_only
             and not core.closed and core.contract['mode'] == 'production'
             and len(core.rows) == 6 and set(cohort.tracks) == set(core.rows),
             'NORMAL_BARRIER_EXACT_ORIGINAL_FORMAL_SIX_GRAPH')
        need(not cohort.activation_attempted and cohort.final is None
             and not core.scientific_activation_qualified
             and set(core.gate.startup_held) == set(core.rows)
             and not owner.bootstrap.records and not hasattr(core, 'normal_cold_barrier'),
             'NORMAL_BARRIER_INSTALL_ONLY_FIRST_COLD_BEFORE_NATIVE_AND_PAID')
        need(all(hasattr(cohort, n) for n in ('formal_full_used_domain',
             'formal_approved_carrier_domain', 'formal_sdk_restore'))
             and core.formal_full_used_domain is cohort.formal_full_used_domain
             and core.formal_sdk_restore is cohort.formal_sdk_restore,
             'NORMAL_BARRIER_AFTER_CURRENT_FULLUSED_APPROVED_SDK_BINDER')
        need(not core.ledger.mutex._is_owned(), 'NORMAL_BARRIER_NO_SCIENCE_LOCK_AT_INSTALL')
        with core.ledger.mutex:
            need(core.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0] == 0,
                 'NORMAL_BARRIER_INSTALL_NEVER_ADOPTS_PAID_GRAPH')
        self.owner, self.cohort, self.core = owner, cohort, core
        self.pid, self.thread = os.getpid(), threading.get_ident()
        self.birth, self.process_birth = process_birth(self.pid), process_birth
        self.source_binding = digest(core.contract)
        self.domain = core.formal_full_used_domain
        self.approved = cohort.formal_approved_carrier_domain
        self.sdk = core.formal_sdk_restore
        need(self.domain.pid == self.pid and self.domain.thread == self.thread,
             'NORMAL_BARRIER_SAME_FULLUSED_METADATA_OWNER_THREAD')
        self.requested = False
        self.state = 'COLD_INSTALLED_NOT_REQUESTED'
        self.checkpoints, self.final_record = {}, None
        self.failure = None
        self.observed = {}
        self.last_static_observation = False

    def _current(self):
        need(os.getpid() == self.pid and threading.get_ident() == self.thread
             and self.process_birth(self.pid) == self.birth and not self.core.closed
             and self.owner.core is self.core and self.owner.scientific_smoke is self.cohort
             and self.cohort.core is self.core and self.cohort.owner is self.owner
             and self.owner.normal_cold_barrier is self
             and self.core.normal_cold_barrier is self and self.cohort.normal_cold_barrier is self
             and self.core.formal_full_used_domain is self.domain
             and self.core.formal_sdk_restore is self.sdk
             and self.cohort.formal_approved_carrier_domain is self.approved
             and digest(self.core.contract) == self.source_binding
             and not self.core.ledger.mutex._is_owned(),
             'NORMAL_BARRIER_SAME_LIVE_GRAPH_METADATA_THREAD_OUTSIDE_SCIENCE_LOCK')

    def refresh_bindings(self):
        """Called AFTER current final _prepare_one returns, never before SDK4."""
        self._current()
        for t, row in self.cohort.tracks.items():
            cp, host = row['checkpoint'], row['host']
            if cp is None or host is None:
                continue
            if t not in self.checkpoints:
                need(cp.core is self.core and cp.t == t and cp.formal_host_writers is host
                     and cp.formal_full_used_domain is self.domain
                     and cp.formal_sdk_restore is self.sdk
                     and cp.state == 'BOUND_MODELS_HELD'
                     and not self.cohort.activation_attempted
                     and t in self.core.gate.startup_held,
                     'NORMAL_BARRIER_BIND_ONLY_FINAL_CURRENT_HELD_CHECKPOINT')
                current = cp.step
                need(current.__self__ is cp, 'NORMAL_BARRIER_ORIGINAL_BOUND_CHECKPOINT_STEP')
                def step(bound, _cp=cp, _current=current):
                    need(bound is _cp, 'NORMAL_BARRIER_SAME_BOUND_CHECKPOINT_INSTANCE')
                    return checkpoint_step(self, _cp, _current)
                cp.step = MethodType(step, cp)
                self.checkpoints[t] = (cp, current, step)
            else:
                previous, _, step = self.checkpoints[t]
                need(cp is previous and cp.step.__func__ is step,
                     'NORMAL_BARRIER_CURRENT_CHECKPOINT_WRAPPER_CUSTODY_RETAINED')
        final = self.cohort.final
        if final is not None and self.final_record is None:
            need(not self.cohort.activation_attempted and final.dispatcher is not None,
                 'NORMAL_BARRIER_FINAL_BIND_BEFORE_FIRST_PAID_ACTIVATION')
            current, dispatcher = final.poll, final.dispatcher
            original_dispatcher_poll = dispatcher.poll
            need(current.__self__ is final and original_dispatcher_poll.__self__ is dispatcher,
                 'NORMAL_BARRIER_CURRENT_FINAL_AND_DISPATCHER_BOUND_METHODS')
            def poll(bound):
                need(bound is final, 'NORMAL_BARRIER_SAME_FINAL_CONTROLLER_INSTANCE')
                return final_poll(self, final, current, dispatcher, original_dispatcher_poll)
            final.poll = MethodType(poll, final)
            self.final_record = (final, current, dispatcher, original_dispatcher_poll, poll)
        elif final is not None:
            need(final is self.final_record[0] and final.poll.__func__ is self.final_record[4],
                 'NORMAL_BARRIER_CURRENT_FINAL_WRAPPER_CUSTODY_RETAINED')

    def request_barrier(self):
        self._current()
        self.refresh_bindings()
        need(self.cohort.activation_attempted and len(self.checkpoints) == 6
             and self.final_record is not None and self.failure is None,
             'NORMAL_BARRIER_REQUEST_ONLY_SAME_ORIGINAL_ACTIVATED_SIX')
        if not self.requested:
            self.requested = True
            self.state = 'REQUESTED_WAIT_ORIGINAL_NORMAL_CHECKPOINTS'
        return self.public()

    def _track_observation(self, t, cp):
        row, core = self.cohort.tracks[t], self.core
        base = dict(phase=cp.state, held_phase=cp.state in HELD_PHASES,
                    original_frozen_checkpoint_verified=False)
        if cp.state not in HELD_PHASES:
            return base
        host, writer = row['host'], cp.writer
        need(writer is not None and writer.writer_fence.state == 'PARKED'
             and host.held and host.tester.physical_clear() and host.consumer_clear(),
             'NORMAL_BARRIER_TRUE_PARKED_WRITER_AND_NATURALLY_DRAINED_HOST')
        with core.ledger.mutex:
            frontier = dict(core.ledger.frontier(t))
        need(frontier['state'] == 'COMMITTED_PARKED'
             and frontier['reserved'] == frontier['unresolved'] == frontier['active_operations'] == 0,
             'NORMAL_BARRIER_ORIGINAL_COMMITTED_DRAINED_FRONTIER')
        http = core.servers[t]
        physical = http.trajectory_park_ready(t)
        need(physical['safe_to_park_writers'] and not http.lifecycle_storage_unknown,
             'NORMAL_BARRIER_ORIGINAL_PHYSICAL_HTTP_DELIVERY_CHECK')
        need(cp.reference == writer.reference, 'NORMAL_BARRIER_ORIGINAL_REFERENCE_NOT_REPLACED')
        writer.refresh_inventory()
        writer.writer_fence.verify_capture(writer.cut, writer.role_sources)
        core.membership_fences[t].verify_after_original_capture(writer.membership_token)
        core.cas.verify_snapshot(cp.reference, expected=frontier)
        base.update(original_frozen_checkpoint_verified=True, generation=frontier['generation'],
            target=frontier['target'], snapshot_sha256=cp.reference['sha256'],
            original_budget_waiters=physical['original_budget_waiters'])
        return base

    def poll(self):
        """Observation only; owner's existing sole loop keeps all original polls."""
        self._current()
        self.refresh_bindings()
        if not self.requested or self.failure is not None:
            return self.public()
        self.last_static_observation = False
        try:
            observed = {t: self._track_observation(t, record[0]) for t, record in self.checkpoints.items()}
            held = len(observed) == 6 and all(v['original_frozen_checkpoint_verified'] for v in observed.values())
            self.last_static_observation = False
            if held:
                # Same original producer lock protocol; no raw SID export,
                # financial backup, disk write or whole-cut authority here.
                with self.domain._operation():
                    self.domain._require_saved(self.domain._domain_values())
                    first = self.domain.public()
                again = {t: self._track_observation(t, record[0]) for t, record in self.checkpoints.items()}
                with self.domain._operation():
                    self.domain._require_saved(self.domain._domain_values())
                    need(first == self.domain.public() and again == observed,
                         'NORMAL_BARRIER_FULLUSED_AND_SIX_ORIGINAL_CUTS_STABLE_BETWEEN_OBSERVATIONS')
                self.last_static_observation = True
                self.state = 'SIX_FROZEN_CUTS_OBSERVED_NO_WHOLE_SEAL_AUTHORITY'
            else:
                self.state = 'REQUESTED_WAIT_ORIGINAL_NORMAL_CHECKPOINTS'
            self.observed = observed
        except Exception as error:
            self.failure = dict(PUBLIC_code='NORMAL_BARRIER_OBSERVATION_PARTIAL_RETAINED_NO_RETRY',
                                exception_type=type(error).__name__, locations=[])
            tb = error.__traceback__
            while tb:
                self.failure['locations'].append(dict(file=tb.tb_frame.f_code.co_filename,
                    line=tb.tb_lineno, function=tb.tb_frame.f_code.co_name))
                tb = tb.tb_next
            self.state = 'PARTIAL_RETAINED_NO_RETRY'
        return self.public()

    def public(self):
        return dict(schema='count14-formal-normal-checkpoint-barrier-wip-v1', state=self.state,
            requested=self.requested, checkpoint_methods_bound=len(self.checkpoints),
            current_FINAL_poll_bound=self.final_record is not None,
            observed_six_original_frozen_cut_stability=self.last_static_observation,
            tracks=copy.deepcopy(self.observed), failure=copy.deepcopy(self.failure),
            whole_cohort_cut_qualified=False, whole_paid_restore_qualified=False,
            whole_control_candidate_written=False, normal_handoff_authority_implemented=False,
            HTTP_budget_waiter_close_or_reconstruction_qualified=False,
            paid_FINAL_objects_closed_by_barrier=False,
            SYSTEM_health_or_resource_stop_called_by_barrier=False,
            financial_or_budget_rules_changed=False, model_replays=0,
            actual_Dev4_or_scientific_runtime_qualified=False, OPS_control_opcode_installed=False)


def install_after_current_formal_binder(cohort):
    """Exact last cold seam; does not replace cohort.poll/retirement/actual-n."""
    need(not hasattr(cohort, 'normal_cold_barrier'), 'NORMAL_BARRIER_INSTALL_EXACTLY_ONCE')
    barrier = NormalCheckpointBarrier(cohort)
    current_prepare = cohort._prepare_one
    need(current_prepare.__self__ is cohort, 'NORMAL_BARRIER_CURRENT_FINAL_BOUND_PREPARE')
    def prepare_one(bound, t):
        need(bound is cohort, 'NORMAL_BARRIER_SAME_CURRENT_COHORT')
        result = current_prepare(t)
        barrier.refresh_bindings()
        return result
    cohort._prepare_one = MethodType(prepare_one, cohort)
    cohort.normal_cold_barrier = cohort.core.normal_cold_barrier = cohort.owner.normal_cold_barrier = barrier
    cohort.owner.request_normal_cold_barrier = MethodType(lambda own: barrier.request_barrier(), cohort.owner)
    cohort.owner.poll_normal_cold_barrier = MethodType(lambda own: barrier.poll(), cohort.owner)
    return barrier
