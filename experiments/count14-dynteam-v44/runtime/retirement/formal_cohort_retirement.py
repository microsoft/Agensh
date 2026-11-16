"""WIP six-from-zero final retirement, never a point-terminal producer.

Cold SAME-owner instance seam only. Missing typed terminal-source capability is
ordinary WAIT, with no thaw/stop/fee action. The existing pinned per-container
retirement protocol is reused without its two-point smoke acceptance or its
single-track/global close. No request cancellation/replay, rm, new dispatcher,
paid rebaseline, runtime hot patch or financial formula/schema change exists.
"""
from __future__ import annotations

from pathlib import Path
from types import MethodType
import copy
import hashlib
import inspect
import os
import time

from common import need, digest, private_dir, publish, wire
from native_peer_registry import process_birth
from smoke_checkpoint_final_retirement import SmokeFinalRetirement

ORIGINAL_RETIREMENT_SHA256 = 'b498a8b5f27b4074861f1d7214d0f1d8b98ce9047ea88c12b25851a363d7fde6'
WAIT_SOURCE = 'WAITING_VERIFIED_FORMAL_POINT_TERMINALS'
WAIT_PAID = 'WAITING_ORIGINAL_PHYSICAL_MODEL_AND_HOST_DRAIN'
THAWING = 'THAWING_ORIGINAL_FINAL_WRITERS_NO_SEARCH_RESUME'
STOPPING = 'STOPPING_ORIGINAL_EXACT_SIX_TRACK_SCOPES'
CLOSING = 'CLOSING_ORIGINAL_SHARED_FINAL_AND_CORE'
DONE = 'FORMAL_SIX_FULLY_RETIRED_RETAINED'
PARTIAL = 'PARTIAL_RETAINED_NO_RETRY'
FINAL_TARGET = 100000000
CUTS = (10000000, 20000000, 50000000, FINAL_TARGET)


def require_original_protocol():
    path = Path(inspect.getsourcefile(SmokeFinalRetirement)).resolve()
    need(path.is_file() and not path.is_symlink() and
        hashlib.sha256(path.read_bytes()).hexdigest() == ORIGINAL_RETIREMENT_SHA256,
        'FORMAL_RETIREMENT_EXACT_ORIGINAL_NORMAL_CONTAINER_PROTOCOL')


class FormalTrajectoryRetirement:
    """Original finite Docker/archive protocol on one real final parked cut.

Not an instance/proxy pretending to satisfy SmokeFinalRetirement's constructor.
Only the nine existing per-container methods are used verbatim, with their
original fresh CID/birth/domain/physical/END guards and retained Popen handles.
"""
    _stop_inventory = SmokeFinalRetirement._stop_inventory
    _check = SmokeFinalRetirement._check
    _empty_original_domain = SmokeFinalRetirement._empty_original_domain
    _remaining_router_clear = SmokeFinalRetirement._remaining_router_clear
    _role_clear = SmokeFinalRetirement._role_clear
    _start_action = SmokeFinalRetirement._start_action
    _retire_role_peer = SmokeFinalRetirement._retire_role_peer
    _original_stop_one = SmokeFinalRetirement._stop_one
    _launcher_terminal = SmokeFinalRetirement._launcher_terminal

    def __init__(self, parent, trajectory):
        self.parent, self.core, self.t = parent, parent.core, trajectory
        row = parent.cohort.tracks[trajectory]
        self.checkpoint, self.launch = row['checkpoint'], row['launch']
        self.writer = self.checkpoint.writer
        self.reference = copy.deepcopy(self.checkpoint.reference)
        self.owner = parent.owner_birth
        self.child = self.child_action = self.started_ns = None
        self.warning120, self.index, self.sequence = False, 0, 0
        self.action_history, self.stopped = [], []
        self.domain_by_name = dict(zip(sorted(self.writer.containers), self.writer.domains))
        self.items = self._stop_inventory()
        self.role_items = [r for r in self.items if r['component'] != 'infra']
        self.infra_items = [r for r in self.items if r['component'] == 'infra']
        self.phase = 'ORIGINAL_FINAL_CUT_PARKED'
        self.launcher_waited = self.manager_pool_closed = False
        self.manager = row['manager']

    def _paid_zero(self):
        return self.parent.paid_and_HTTP_clear()

    def _receipt(self, kind, **metadata):
        self.parent.receipt(kind, trajectory=self.t, **metadata)

    def games_terminal(self):
        if self.manager is None:
            return True
        # A registered Game PID, final logical point, or terminal fee alone is
        # NOT a physical Game/custodian terminal proof.
        return all(g['terminal'] is True and g['child'] is not None and
            g['child'].poll() == 0 for g in self.manager.games)

    def progress_existing_games(self):
        if self.manager is None:
            return
        need(self.manager.failure is None, 'FORMAL_RETIREMENT_FAILED_ORIGINAL_GAME_RETAINED')
        self.manager._control(force=True)  # original fresh FINAL/HOLD metadata
        for game in self.manager.games:
            if not game['terminal']:
                self.manager._game_step(game)  # ONLY existing original exec
            child = game['child']
            need(child is not None and child.poll() in (None, 0),
                'FORMAL_RETIREMENT_ORIGINAL_GAME_CUSTODIAN_FAILED_RETAIN')
        # Never manager.poll(), _new_game(), phase request or publication here.

    def _stop_one(self, item):
        if (item['component'] == 'agent' and item['role'] == 'racing-background-00' and
                not self.games_terminal()):
            return False
        return self._original_stop_one(item)

    def request_original_thaw(self):
        need(self.phase == 'ORIGINAL_FINAL_CUT_PARKED' and self._paid_zero(),
            'FORMAL_RETIREMENT_THAW_ONCE_AFTER_TRUE_PAID_HTTP_DRAIN')
        if self.manager is not None:
            self.manager._control(force=True)
        self.core.membership_fences[self.t].begin_final_retirement(
            original_snapshot_sha256=self.reference['sha256'],
            original_ledger_generation=self.writer.generation, original_models_closed=True)
        self.writer.writer_fence.request_final_retirement_thaw()
        self.phase = 'ORIGINAL_FINAL_THAW_REQUESTED'

    def poll_original_thaw(self):
        if self.phase == 'STOPPING_ORIGINAL_ROLES':
            return True
        need(self.phase == 'ORIGINAL_FINAL_THAW_REQUESTED', 'FORMAL_RETIREMENT_KEEP_SAME_ORIGINAL_THAW')
        if self.manager is not None:
            self.manager._control(force=True)
        if not self.writer.writer_fence.poll_final_retirement_thaw():
            return False
        self.phase = 'STOPPING_ORIGINAL_ROLES'
        return True

    def step(self):
        if self.phase == 'TRACK_FULLY_RETIRED_RETAINED':
            return True
        self.progress_existing_games()
        if self.phase == 'STOPPING_ORIGINAL_ROLES':
            if self.index < len(self.role_items):
                if self._stop_one(self.role_items[self.index]):
                    self.index += 1
                return False
            self.phase = 'WAITING_ORIGINAL_LAUNCHER_EXIT'
        if self.phase == 'WAITING_ORIGINAL_LAUNCHER_EXIT':
            if not self.launcher_waited:
                if not self._launcher_terminal():
                    return False
                self.launcher_waited = True
            self.phase, self.index = 'STOPPING_ORIGINAL_INFRA', 0
        if self.phase == 'STOPPING_ORIGINAL_INFRA':
            if self.index < len(self.infra_items):
                if self._stop_one(self.infra_items[self.index]):
                    self.index += 1
                return False
            if not self.games_terminal():
                return False
            if self.manager is not None and not self.manager_pool_closed:
                self.manager.pool.shutdown(wait=False)  # all original work terminal; no cancel_futures
                self.manager_pool_closed = True
            self.phase = 'TRACK_FULLY_RETIRED_RETAINED'
            self._receipt('FORMAL_TRACK_NORMAL_RETIREMENT_COMPLETE',
                containers_stopped_retained=len(self.stopped), normal_docker_actions=len(self.action_history))
            return True
        return False

    def public(self):
        return dict(state=self.phase, containers_stopped_retained=len(self.stopped),
            normal_docker_actions=len(self.action_history), control_child_retained=self.child is not None,
            games_physical_terminal=self.games_terminal(), launcher_waited=self.launcher_waited)


class FormalCohortRetirement:
    def __init__(self, cohort, *, terminal_source=None):
        from native_formal_cohort import NativeFormalCohort
        from original_relay_core import OriginalRelayCore
        from formal_scope import validate_contract
        need(type(cohort) is NativeFormalCohort and type(cohort.core) is OriginalRelayCore and
            cohort.owner.scientific_smoke is cohort and cohort.owner.core is cohort.core and
            not cohort.activation_attempted and set(cohort.core.gate.startup_held) == set(cohort.tracks) and
            len(cohort.tracks) == 6 and not cohort.core.qualification_only and not cohort.core.closed and
            not hasattr(cohort, 'formal_retirement') and not hasattr(cohort.core, 'formal_retirement'),
            'FORMAL_RETIREMENT_ONLY_NEW_COLD_SAME_SIX_HELD_COHORT')
        validate_contract(cohort.core.contract, digest(cohort.core.contract))
        require_original_protocol()
        self.cohort, self.core, self.terminal_source = cohort, cohort.core, terminal_source
        self.owner_birth, self.contract_sha256 = process_birth(os.getpid()), digest(cohort.core.contract)
        self.state, self.failure, self.evidence = WAIT_SOURCE, None, None
        self.tracks, self.index, self.sequence = {}, 0, 0
        self.thaw_requested, self.closed_host_admission = set(), set()
        self.cached_public = None
        self.original_poll, self.original_public = cohort.poll, cohort.public
        self.home = None
        if terminal_source is not None:
            self._require_source_type()
        cohort.formal_retirement = self
        self.core.formal_retirement = self
        cohort.poll = MethodType(lambda own: self.poll_cohort(), cohort)
        cohort.public = MethodType(lambda own: self.cohort_public(), cohort)

    def _outside(self):
        need(process_birth(os.getpid()) == self.owner_birth and
            self.cohort.formal_retirement is self and self.core.formal_retirement is self,
            'FORMAL_RETIREMENT_SAME_OWNER_EXACT_CUSTODY')
        need(not self.core.ledger.mutex._is_owned(), 'FORMAL_RETIREMENT_NO_IO_OR_WAIT_UNDER_SCIENCE_LOCK')

    def _require_source_type(self):
        # This producer is a separately qualified ROOT component, NOT supplied
        # as an arbitrary callback/dict/boolean. None never enables retirement.
        from formal_terminal_source import FormalPointTerminalSource
        need(type(self.terminal_source) is FormalPointTerminalSource and
            self.terminal_source.cohort is self.cohort and self.terminal_source.core is self.core,
            'FORMAL_RETIREMENT_ONLY_PINNED_TYPED_ORIGINAL_POINT_SOURCE')

    def _read_verified_evidence(self):
        if self.terminal_source is None:
            return None
        self._require_source_type()
        from formal_terminal_source import FormalPointTerminalEvidence
        evidence = self.terminal_source.read_verified_terminal_points(self.cohort)
        need(evidence is None or type(evidence) is FormalPointTerminalEvidence,
            'FORMAL_RETIREMENT_NO_CALLBACK_BOOLEAN_OR_UNVERIFIED_POINT_MAP')
        return evidence

    def receipt(self, kind, **metadata):
        need(self.home is not None, 'FORMAL_RETIREMENT_RECEIPT_HOME_AFTER_VERIFIED_POINT_SOURCE')
        self.sequence += 1
        value = dict(schema='count14-formal100m-same-owner-retirement-public-v1', sequence=self.sequence,
            kind=kind, state=self.state, at_monotonic_ns=time.monotonic_ns(), fees_changed=False,
            model_replays=0, force_cancel_rm_prune_or_root_deletion=False, **metadata)
        publish(self.home / (str(self.sequence).zfill(5) + '-' + kind + '.json'), wire(value), mode=0o400)

    def paid_and_HTTP_clear(self):
        core = self.core
        with core.ledger.mutex:
            if core.ledger.global_unresolved() != 0 or core.ledger.db.execute(
                    "SELECT COUNT(*) FROM aux_permits WHERE state IN ('RESERVED','SENT','UNKNOWN')").fetchone()[0] != 0:
                return False
        return all(server.trajectory_park_ready(t)['safe_to_park_writers'] and
            not server.lifecycle_storage_unknown for t, server in core.servers.items())

    def host_writers_clear(self):
        for t, row in self.cohort.tracks.items():
            tester, consumer = row['tester'], row['consumer']
            if tester is None or not tester.physical_clear():
                return False
            if consumer is not None:
                consumer.poll()  # only reaps an existing original bounded publication
                if consumer.failure is not None or not consumer.checkpoint_ready():
                    return False
        return True

    def actual_final_children_terminal(self):
        final = self.cohort.final
        return final is not None and all(record['child'] is not None and record['terminal'] is not None and
            record['child'].poll() is not None for record in final.dispatcher.children.values())

    def verify_original_final_cuts(self):
        core = self.core
        for t, row in self.cohort.tracks.items():
            cp = row['checkpoint']
            need(cp is not None and cp.core is core and cp.t == t and cp.state == 'FINAL_PARKED' and
                cp.writer is not None and cp.writer.writer_fence.state == 'PARKED' and
                [point['target_tokens'] for point in cp.points] == list(CUTS),
                'FORMAL_RETIREMENT_SIX_ORIGINAL_FOUR_CUTS_FINAL_PARKED')
            with core.ledger.mutex:
                frontier = core.ledger.frontier(t)
                account = core.ledger.account(t)
                need(frontier['state'] == 'COMMITTED_PARKED' and frontier['target'] == FINAL_TARGET and
                    account['stage'] == 3 and frontier['generation'] == cp.points[-1]['generation'] and
                    frontier['reserved'] == frontier['unresolved'] == frontier['active_operations'] == 0,
                    'FORMAL_RETIREMENT_ONLY_ACTUAL_SEALED_100M_FINAL_LEDGER_GENERATION')
            snap = core.cas.verify_snapshot(cp.reference, expected=frontier)
            need(cp.reference == cp.points[-1]['snapshot'] == cp.writer.reference and
                snap['pins']['native_writer_fence'] == cp.writer.writer_fence.receipt['sha256'] and
                cp.writer.cut.cut['generation'] == frontier['generation'],
                'FORMAL_RETIREMENT_EXACT_ORIGINAL_FINAL_CAS_CUT_AND_FENCE')

    def _begin(self, evidence):
        # Source verified all24 scientific point terminals. Physical custody is
        # a separate later WAIT, not inferred from that scientific certificate.
        self.verify_original_final_cuts()
        self.evidence = evidence
        self.home = private_dir(self.core.home / 'formal100m-retirement', create=True)
        need(not any(self.home.iterdir()), 'FORMAL_RETIREMENT_NEW_RECEIPT_HOME_NO_RETRY')
        self.state = WAIT_PAID
        for t, row in self.cohort.tracks.items():
            row['tester'].close_admission()
            if row['consumer'] is not None:
                row['consumer'].request_checkpoint_hold()
            self.closed_host_admission.add(t)
        # Original gate only wakes/rejects UNSENT waiters; accepted HTTP/model
        # children remain untouched and are naturally polled below.
        self.core.gate.shutdown()
        self.core.system_health.stop_admission()
        self.core.resource_producer.stop_admission()
        self.receipt('VERIFIED_FORMAL_POINTS_STOP_NEW_ADMISSION_NATURAL_DRAIN',
            source_is_typed_original_point_producer=True, point_count=24,
            smoke_acceptance_used=False, fixed_72_effective_success_gate_used=False)

    def step(self):
        if self.state in (DONE, PARTIAL):
            return self.public()
        self._outside()
        try:
            if self.state == WAIT_SOURCE:
                evidence = self._read_verified_evidence()
                if evidence is None:
                    return self.public()
                self._begin(evidence)
                return self.public()
            self.core.poll_native_control_once()
            if self.state == WAIT_PAID:
                if (not self.paid_and_HTTP_clear() or not self.actual_final_children_terminal() or
                    not self.host_writers_clear() or not self.core.system_health.physical_clear() or
                    not self.core.resource_producer.physical_clear()):
                    return self.public()
                self.terminal_source.verify(self.cohort, self.evidence)
                self.verify_original_final_cuts()
                self.tracks = {t: FormalTrajectoryRetirement(self, t) for t in self.cohort.tracks}
                self.state = THAWING
            if self.state == THAWING:
                for t, track in self.tracks.items():
                    if t not in self.thaw_requested:
                        track.request_original_thaw()
                        self.thaw_requested.add(t)
                        return self.public()  # each original thaw request once
                if not all(track.poll_original_thaw() for track in self.tracks.values()):
                    return self.public()
                self.state = STOPPING
            if self.state == STOPPING:
                keys = tuple(self.tracks)
                if self.index < len(keys):
                    if self.tracks[keys[self.index]].step():
                        self.index += 1
                    return self.public()
                self.state = CLOSING
            if self.state == CLOSING:
                if not (self.paid_and_HTTP_clear() and self.host_writers_clear() and
                    self.actual_final_children_terminal() and self.core.system_health.physical_clear() and
                    self.core.resource_producer.physical_clear()):
                    return self.public()
                with self.core.peers._lock:
                    if self.core.peers._peers:
                        return self.public()
                self._require_source_type()
                # This same separately-qualified source consumes its own exact
                # typed evidence. Future n<3 close cannot be fabricated here or
                # sent through the old smoke/strict72 close as if n3 succeeded.
                self.terminal_source.close_shared_final_after_drained(self.cohort.final, self.evidence)
                self.cached_public = self.public()
                self.core.formal_terminal_public = copy.deepcopy(self.cached_public)
                # Historical attribute name required by ORIGINAL owner entry's
                # closed path; value explicitly has FORMAL schema, not smoke PASS.
                self.core.smoke_terminal_public = copy.deepcopy(self.cached_public)
                self.core.close_original_transports_after_drained()
                self.state = DONE
                self.cohort.state = DONE
                self.cached_public.update(state=DONE, fully_retired=True)
                self.core.formal_terminal_public = copy.deepcopy(self.cached_public)
                self.core.smoke_terminal_public = copy.deepcopy(self.cached_public)
                self.receipt('FORMAL_SIX_NORMAL_RETIREMENT_COMPLETE', point_count=24,
                    all_original_roots_ledgers_sessions_snapshots_retained=True)
            return self.public()
        except Exception as error:
            locations, tb = [], error.__traceback__
            while tb:
                locations.append(dict(file=tb.tb_frame.f_code.co_filename, line=tb.tb_lineno,
                    function=tb.tb_frame.f_code.co_name))
                tb = tb.tb_next
            self.failure = dict(PUBLIC_code='FORMAL_RETIREMENT_ORIGINAL_CUSTODY_RETAINED_NO_RETRY',
                exception_type=type(error).__name__, phase=self.state, locations=locations)
            self.state = PARTIAL
            if self.home is not None:
                self.receipt('FAILED_RETAINED', **self.failure)
            return self.public()

    def poll_cohort(self):
        # A terminal-evidence observer failure before _begin has not retired
        # any science. Retain its first PARTIAL/no-retry, but keep the same
        # original six-track poll alive. Actual retirement behavior is intact.
        if (self.state == WAIT_SOURCE or
                (self.state == PARTIAL and self.evidence is None and self.home is None)):
            self.original_poll()
        self.step()
        return self.cohort_public()

    def cohort_public(self):
        if self.core.closed:
            return copy.deepcopy(self.cached_public)
        value = self.original_public()
        value['formal_retirement'] = self.public()
        value['six_track_retirement_implemented'] = True
        value['retirement_terminal_producer_bound'] = self.terminal_source is not None
        value['formal_delivery_claimed'] = False
        return value

    def public(self):
        if self.cached_public is not None and self.core.closed:
            return copy.deepcopy(self.cached_public)
        return dict(schema='count14-formal100m-six-track-retirement-wip-v1', state=self.state,
            terminal_producer_bound=self.terminal_source is not None,
            verified_scientific_point_evidence_retained=self.evidence is not None,
            physical_terminal_not_inferred_from_UNKNOWN_fee_or_point_terminal=True,
            tracks={t: track.public() for t, track in self.tracks.items()},
            source_missing_is_WAIT_not_blocked=True, fully_retired=self.state == DONE,
            smoke_acceptance_used=False, fixed_72_effective_success_gate_used=False,
            original_accounting_schema_formulas_unchanged=True, force_cancel_rm_or_model_replay=False,
            failure=copy.deepcopy(self.failure), actual_Dev4_or_100M_qualified=False,
            formal_delivery_claimed=False)


def install_formal_retirement(cohort, *, terminal_source=None):
    return FormalCohortRetirement(cohort, terminal_source=terminal_source)
