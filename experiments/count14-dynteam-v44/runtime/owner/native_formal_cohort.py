"""WIP six-track 100M cohort on ONE exact ORIGINAL cold owner/core/dispatcher.

No production qualification or smoke-retirement claim. Fresh native SDK epochs
must already be installed before any CLI/model. Only approved native scientific
runtime consumes task/test/source bytes; this module exposes control metadata.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
from types import MethodType
import copy
import os
import time

from common import need, digest
from native_peer_registry import process_birth
from smoke_bootstrap_task_ports import NewRootSourceTaskPorts
from formal_count14_tester import original_formal_tester_run, FormalCount14Tester
from formal_count14_tester_public import TesterPublicExecution
from formal_scope import validate_contract, FORMAL_CUTS
from formal_controller import create_formal_final_controller
from formal_checkpoint import create_formal_checkpoint_ports
from formal_owner_ports import formal_launcher, install_formal_initial_port, formal_activate_method
from formal_host_writers import FormalHostWriters
from native_racing_smoke import RacingGameSources, install_approved_helper_view, verify_actual_helper_views

PREPARED = 'PREPARED_ALL_SIX_ORIGINAL_OBJECTS_MODELS_HELD'
RUNNING = 'RUNNING_ORIGINAL_FORMAL_TRACK'
PARKED = 'FINAL_PARKED_K3_PENDING'
PARTIAL = 'PARTIAL_RETAINED_NO_RETRY'
COMPLETE = 'FORMAL_SEARCH_AND_K3_COMPLETE_RETAINED'


@dataclass(frozen=True)
class FormalCohortSources:
    original_task_host_source: Path
    native_pbench_source: Path
    native_tester_source: Path
    final_configuration: Path
    final_configuration_sha256: str


class NativeFormalCohort:
    def __init__(self, owner, *, sources, game_sources, tester_execution_ports=None):
        from native_cold_owner import NativeColdOwner
        from original_relay_core import OriginalRelayCore
        need(type(owner) is NativeColdOwner and type(sources) is FormalCohortSources and
             type(owner.core) is OriginalRelayCore and not owner.errors and
             not hasattr(owner, 'scientific_smoke'), 'FORMAL_COHORT_ONLY_ONE_ORIGINAL_NEW_VALID_COLD_OWNER')
        core = owner.core
        validate_contract(core.contract, digest(core.contract))
        need(not core.qualification_only and not core.closed and
             set(core.gate.startup_held) == set(core.rows) and not core.scientific_activation_qualified and
             all(hasattr(core, name) for name in ('system_health', 'resource_producer',
                 'native_kernel_tool_custody', 'native_sdk_startup_epochs')) and
             not owner.bootstrap.records, 'FORMAL_COHORT_ALL_SIX_HELD_WITH_NORMAL_SDK_EPOCH_CUSTODY')
        need(type(game_sources) is dict and set(game_sources) ==
             {t for t, row in core.rows.items() if row['arm'] == 'DYNTEAM_RACING'} and
             all(type(g) is RacingGameSources for g in game_sources.values()),
             'FORMAL_COHORT_THREE_EXACT_SEPARATE_RACING_GAME_BINDINGS')
        ports = {} if tester_execution_ports is None else tester_execution_ports
        need(type(ports) is dict and set(ports) <= set(core.rows) and
             all(type(row) is dict for row in ports.values()), 'FORMAL_TYPED_TESTER_EXECUTION_PORTS_BY_TRAJECTORY')
        with core.ledger.mutex:
            need(core.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0] == 0,
                 'FORMAL_COHORT_NEVER_ADOPTS_PAID_TRAJECTORY_AS_NEW')
        self.owner, self.core, self.sources = owner, core, sources
        self.game_sources, self.tester_ports = dict(game_sources), dict(ports)
        self.birth = process_birth(os.getpid())
        self.state, self.failure, self.final, self.source_ports = 'PREPARING_ORIGINAL_SIX_HELD', None, None, None
        self.final_failed, self.activation_attempted, self.cursor = False, False, 0
        self.tracks = {t: dict(state='BOUND_AWAIT_ORIGINAL_SOURCE', failure=None, tester=None,
            checkpoint=None, launch=None, manager=None, consumer=None, host=None, gate_released=False,
            task_attempted=False, tester_cadence_started=False, host_closed=False) for t in core.rows}
        owner.scientific_smoke = self
        install_formal_initial_port(owner, self)

    def _active(self, t):
        return self.core.active_clock.read(t)['active_ns'] / 1e9

    def _failure(self, error, phase):
        frames, tb = [], error.__traceback__
        while tb:
            frames.append(dict(file=tb.tb_frame.f_code.co_filename, line=tb.tb_lineno,
                               function=tb.tb_frame.f_code.co_name))
            tb = tb.tb_next
        return dict(PUBLIC_code='FORMAL_COHORT_PARTIAL_RETAINED_NO_RETRY', phase=phase,
                    exception_type=type(error).__name__, locations=frames)

    def _partial(self, t, error, phase):
        row = self.tracks[t]
        if row['failure'] is None:
            row['failure'] = self._failure(error, phase)
            row['state'] = PARTIAL
            self.core.ledger.latch_fault(t, 'FORMAL_COHORT_LOCAL_FRAMEWORK_PARTIAL_RETAINED')
            if row['tester'] is not None:
                row['tester'].checkpoint_hold()
            if row['consumer'] is not None:
                row['consumer'].request_checkpoint_hold()
        self.state = 'FORMAL_PARTIAL_RETAINED_OTHER_ACTIVE_TRACKS_CONTINUE'

    def _prepare_one(self, t):
        core, row = self.core, self.tracks[t]
        phase = row['state']
        if phase == 'BOUND_AWAIT_ORIGINAL_SOURCE':
            source = getattr(core, 'source_bootstraps', {}).get(t)
            if source is None or source['state'] != 'SOURCE_ONLY_READY':
                return
            self.owner.bootstrap.start(t)
            row['state'] = 'WAITING_ORIGINAL_INFRA'
        elif phase in ('WAITING_ORIGINAL_INFRA', 'WAITING_EXACT_HOST_PUBLISH_READY'):
            boot = self.owner.bootstrap.step(t)
            need(boot['failure_type'] is None, 'FORMAL_ORIGINAL_INFRA_PARTIAL_RETAINED')
            if boot['phase'] != 'INFRA_READY_AWAIT_SOURCE_PUBLICATION':
                return
            if self.source_ports is None:
                self.source_ports = NewRootSourceTaskPorts(core,
                    original_task_host_source=self.sources.original_task_host_source)
            result = self.source_ports.prepare(t)
            if result['state'] == 'WAITING_EXACT_HOST_PUBLISH_READY':
                row['state'] = result['state']
                return
            need(result['state'] == 'SOURCE_TASK_CHANNEL_READY', 'FORMAL_SOURCE_PORTS_TRUE_READY')
            row['state'] = 'SOURCE_TASK_CHANNEL_READY'
        elif phase == 'SOURCE_TASK_CHANNEL_READY':
            if self.final is None:
                self.final = create_formal_final_controller(core, self.sources.final_configuration,
                    self.sources.final_configuration_sha256)
                self.final.preflight()
                core.cohort_resources.bind_aux_capacity(self.final.capacity)
            need(self.final.state == 'PREPARED_ORIGINAL_FINAL_MODELS_PAUSED' and
                 len(self.final.profiles) == 6, 'FORMAL_SHARED_FINAL_PREPARED_EXACT_ALL_SIX')
            row['state'] = 'ORIGINAL_SHARED_FINAL_BOUND'
        elif phase == 'ORIGINAL_SHARED_FINAL_BOUND':
            reference = core.contract['v2_baseline_reference_protocol']
            pins = dict(manifest=digest(core.contract), protocol=self.final.scope.protocol_sha256(t),
                source=reference['source_bundle'], task_description=reference['task_description'])
            row['checkpoint'] = create_formal_checkpoint_ports(core, t, scope=self.final.scope,
                source_ports=self.source_ports, pins=pins)
            row['state'] = 'ORIGINAL_FORMAL_CHECKPOINT_BOUND'
        elif phase == 'ORIGINAL_FORMAL_CHECKPOINT_BOUND':
            run = original_formal_tester_run(core, t, self.source_ports,
                pbench_tester_source=self.sources.native_tester_source)
            active = lambda: self._active(t)
            execution = TesterPublicExecution(ports=self.tester_ports.get(t, {}), active_now=active)
            row['tester'] = FormalCount14Tester(core, t, run, active_now=active, public_execution=execution)
            row['tester'].prepare()
            row['state'] = 'TASK_AWARE_NATIVE_TESTER_CYCLE0_READY'
        elif phase == 'TASK_AWARE_NATIVE_TESTER_CYCLE0_READY':
            if core.rows[t]['arm'] == 'DYNTEAM_RACING':
                from smoke_racing_tools_game_manager import NativeRacingGameManager
                from native_racing_shared_tests import RacingSharedPublicTests
                g = self.game_sources[t]
                row['manager'] = NativeRacingGameManager(core, t, code_directory=g.code_directory,
                    code_map_sha256=g.code_map_sha256, custodian_path=g.custodian_path,
                    custodian_sha256=g.custodian_sha256, public_tool_scope=g.public_tool_scope)
                install_approved_helper_view(core, t, row['manager'], row['tester'].task_view)
                row['consumer'] = RacingSharedPublicTests(core, t, row['manager'])
                row['consumer'].bind_original_publisher(row['tester'])
                row['state'] = 'WAITING_EIGHT_ORIGINAL_HELPERS_ZERO_MODELS'
            else:
                if not self.owner.bootstrap.try_start_initial(t):
                    return  # Keep original phase; no initial effect consumed.
                row['state'] = 'WAITING_ORIGINAL_INITIAL_ROLES'
        elif phase == 'WAITING_EIGHT_ORIGINAL_HELPERS_ZERO_MODELS':
            result = row['manager'].poll()
            need(result['failure'] is None, 'FORMAL_RACING_HELPER_PREPARE_PARTIAL_RETAINED')
            if result['helpers_prepared'] != result['helpers_expected']:
                return
            need(result['helpers_prepared'] == 8 and not row['manager'].games,
                 'FORMAL_EIGHT_REAL_HELPERS_WITHOUT_FORCED_GAME')
            if not self.owner.bootstrap.try_start_initial(t):
                return  # Keep original phase; no initial effect consumed.
            row['state'] = 'WAITING_ORIGINAL_INITIAL_ROLES'
        elif phase == 'WAITING_ORIGINAL_INITIAL_ROLES':
            boot = self.owner.bootstrap.step(t)
            need(boot['failure_type'] is None, 'FORMAL_ORIGINAL_INITIAL_PARTIAL_RETAINED')
            discovery = boot.get('discovery')
            if (boot['phase'] != 'INITIAL_UP_COMMANDS_RETURNED_MODEL_HELD' or discovery is None or
                discovery['pending_components']):
                return
            # The original bootstrap.step() and launcher constructor may
            # block outside the owner loop. Retain one UNSTARTED launcher so
            # an unadmitted SOURCE wait cannot reconstruct/register it twice.
            if row['launch'] is None:
                row['launch'] = formal_launcher(core, t, self.source_ports, pbench_source=self.sources.native_pbench_source)
            # Same original producer: reap/publish a completed real SOURCE;
            # its existing RUNNING/20s-due/55s-child controls remain the only
            # sampling schedule. No SYSTEM probe, wait, clock or stamp here.
            core.resource_producer.poll()
            core.cohort_resources.maybe_refresh()
            if not (core.cohort_resources.system_open() and
                    core.cold_bootstrap._infra_ready(t)):
                return  # Keep original WAITING_INITIAL state, no .start().
            # Decide again at the actual original pre-effect boundary. A
            # false admission is HOLD, never a successful start or fault clear.
            # Structural infra errors and all post-admission failures propagate.
            if not row['launch'].try_start():
                return  # Keep the SAME cached unstarted launcher and phase.
            row['host'] = FormalHostWriters(row['checkpoint'], tester=row['tester'],
                consumer=row['consumer'], manager=row['manager'])
            self._preflight_track(t)
            row['state'] = 'PREPARED_ORIGINAL_TRACK_MODELS_HELD'

    def _preflight_track(self, t):
        row = self.tracks[t]
        row['checkpoint'].preflight()
        if row['consumer'] is not None:
            row['consumer'].verify_actual_readonly_mounts()
            verify_actual_helper_views(self.core, t, row['tester'].task_view)

    def prepare_tick(self):
        need(not self.activation_attempted, 'FORMAL_NO_REPREPARE_AFTER_ANY_ACTIVATION_ATTEMPT')
        if self.failure is not None:
            return self.public()
        keys = tuple(self.tracks)
        t = keys[self.cursor % len(keys)]
        self.cursor += 1
        row = self.tracks[t]
        if row['failure'] is None:
            try:
                self._prepare_one(t)
            except Exception as error:
                self._partial(t, error, row['state'])
        if all(r['state'] == 'PREPARED_ORIGINAL_TRACK_MODELS_HELD' for r in self.tracks.values()):
            self.state = PREPARED
        return self.public()

    def activate(self):
        need(self.state == PREPARED and not self.activation_attempted and
             process_birth(os.getpid()) == self.birth and
             set(self.core.gate.startup_held) == set(self.tracks) and
             all(r['state'] == 'PREPARED_ORIGINAL_TRACK_MODELS_HELD' and r['failure'] is None
                 for r in self.tracks.values()), 'FORMAL_UNIQUE_ACTIVATE_ONLY_TRUE_ALL_SIX_PREPARED_SAME_OWNER')
        self.activation_attempted = True  # never retry partial release/task POST
        current = None
        try:
            for current, row in self.tracks.items():
                row['launch'].validate_release_prefix()
                self._preflight_track(current)
            resources = self.core.cohort_resources
            # The serial six preflights may outlive the currently published TTL.
            # Reap/publish the same due sampler, then reread its original receipt.
            producer=getattr(self.core,'resource_producer',None)
            if producer is not None:producer.poll()
            resources.refresh()
            admission_deadline=time.monotonic()+45
            while not resources.experiment_open() and time.monotonic()<admission_deadline:
                time.sleep(min(.5,max(0,admission_deadline-time.monotonic())))
                if producer is not None:producer.poll()
                resources.refresh()
            need(resources.experiment_open(), 'FORMAL_FRESH_HEALTH_ALL_OWN_RELAY96_PER_TRACK13')
            evidence = dict(current_owner_authorized=True,
                gateway_health_sha256=resources.state['raw_public_receipt_sha256'],
                allocation_sha256=digest(asdict(resources.allocation)))
            self.final.release(owner_evidence=evidence)
            self.state = 'ACTIVATING_ORIGINAL_SIX_NO_RETRY'
            for current, row in self.tracks.items():
                self.core.gate.release_startup(current)
                row['gate_released'] = True
                row['state'] = 'ACTIVATED_ORIGINAL_TASK_PENDING'
                # Mark attempt before native task(): its own exact-once intent
                # retains ambiguous acceptance; no caller repeats a POST.
                row['task_attempted'] = True
                self.source_ports.task(current, row['launch'])
                row['tester'].start()
                row['tester_cadence_started'] = True
                row['state'] = RUNNING
            self.core.scientific_activation_qualified = True
            self.core.state = 'SAME_ORIGINAL_FORMAL_SIX_RUNNING'
            self.state = 'RUNNING_ORIGINAL_FORMAL_SIX'
        except Exception as error:
            if current is not None:
                self._partial(current, error, self.state)
            else:
                self.failure = self._failure(error, self.state)
                self.state = PARTIAL
            # Already released tracks remain true in metadata and keep normal
            # paid settlement/poll. Held tracks remain held, never shown ACTIVE.
            raise
        return self.public()

    def _retain_first_final_failure_public(self):
        """Optional fixed failure metadata, never a release/retry authority.

        Called only at the first FINAL catch, outside original science locks.
        _failure supplied type/phase/source locations, not error args, locals,
        model/tool data or native child configuration. No new live read occurs.
        """
        from common import publish, wire
        try:
            need(not self.core.ledger.mutex._is_owned() and
                 not self.core.queue.mutex._is_owned() and
                 not self.final.dispatcher.lock._is_owned(),
                 'FORMAL_FINAL_FAILURE_PUBLIC_OUTSIDE_ORIGINAL_LOCKS')
            value = dict(schema='count14-formal-first-final-failure-metadata-v1',
                failure=copy.deepcopy(self.failure),
                messages_args_locals_or_scientific_body_exported=False,
                financial_mutation_or_retry_authority=False)
            path = self.core.home / 'FINAL_FIRST_FAILURE_PUBLIC.json'
            publish(path, wire(value), mode=0o400)
            self.final_first_failure_public = dict(
                state='PUBLISHED_ORIGINAL_FIRST_FAILURE_METADATA',
                path=str(path), sha256=digest(value))
        except Exception as error:
            # Diagnostic storage failure cannot replace the original cause or
            # become a new science gate; retain only another fixed metadata row.
            self.final_first_failure_public = dict(
                state='DIAGNOSTIC_PUBLICATION_FAILED_NOT_A_SCIENCE_GATE',
                failure=self._failure(error, 'FIRST_FINAL_FAILURE_PUBLICATION'))

    def _poll_track(self, t):
        row = self.tracks[t]
        if row['consumer'] is not None:
            row['consumer'].poll()  # reaps a held original bounded RPC as well
            need(row['consumer'].failure is None, 'FORMAL_ORIGINAL_PUBLIC_CONSUMER_PARTIAL_RETAINED')
        if row['state'] not in (RUNNING, PARKED):
            return
        with self.core.ledger.mutex:
            search_running = self.core.ledger.frontier(t)['state'] == 'RUNNING'
        if (row['checkpoint'].state in ('BOUND_MODELS_HELD', 'RUNNING') and search_running and
            not row['host'].held):
            row['tester'].poll()  # both arms use identical 1800 ACTIVE seconds
            need(row['tester'].state != 'CYCLE_PARTIAL_RETAINED_NO_RETRY', 'FORMAL_TESTER_CYCLE_PARTIAL_RETAINED')
            if row['manager'] is not None:
                result = row['manager'].poll()
                need(result['failure'] is None, 'FORMAL_ORIGINAL_GAME_PARTIAL_RETAINED')
        row['checkpoint'].step()
        if row['checkpoint'].state == 'FINAL_PARKED':
            row['state'] = PARKED
            if not row['host_closed']:
                row['tester'].close_admission()
                if row['consumer'] is not None:
                    row['consumer'].close_after_drained()
                row['host_closed'] = True

    def _full_n3_complete(self):
        # Full-n3 path only, NOT a new scientific hard requirement. Existing
        # authorized n<3 terminal/exhaustion producer integration is remaining.
        expected = {digest(dict(trajectory=t, target=target)) for t in self.tracks for target in FORMAL_CUTS}
        return (all(r['state'] == PARKED for r in self.tracks.values()) and
            self.core.queue.frontier() == {'COMPLETE': 72} and
            set(self.final.dispatcher.points) == expected and
            all(p['audited'] is True for p in self.final.dispatcher.points.values()))

    def poll(self):
        if self.state == COMPLETE:
            return self.public()  # all custody retained; NO smoke retirement
        if not self.activation_attempted:
            return self.prepare_tick()
        if self.final is not None and self.final.state in ('PREPARED_ORIGINAL_FINAL_MODELS_PAUSED', 'RELEASED'):
            if self.final_failed:
                try:
                    self.final.dispatcher.poll()  # original retained handles only
                except Exception as error:
                    # No launch/retry/fault clear; preserve the FIRST failure.
                    # The original dispatcher may refuse its retained poll.
                    # This must not kill polling for the other trajectories.
                    if not hasattr(self, 'final_retained_poll_failure'):
                        self.final_retained_poll_failure = self._failure(
                            error, 'ORIGINAL_SHARED_FINAL_RETAINED_POLL')
            else:
                try:
                    self.final.poll()  # exactly ONCE for whole six-track tick
                except Exception as error:
                    self.final_failed = True
                    self.failure = self._failure(error, 'ORIGINAL_SHARED_FINAL_POLL')
                    self.state = 'FORMAL_PARTIAL_RETAINED_OTHER_ACTIVE_TRACKS_CONTINUE'
                    self._retain_first_final_failure_public()
        for t, row in self.tracks.items():
            if row['failure'] is not None:
                if row['consumer'] is not None:
                    row['consumer'].poll()
                continue
            if row['gate_released']:
                try:
                    self._poll_track(t)
                except Exception as error:
                    self._partial(t, error, row['state'])
        if not self.final_failed and self.final is not None and self._full_n3_complete():
            self.state = COMPLETE
        return self.public()

    def public(self):
        tracks = {}
        for t, row in self.tracks.items():
            with self.core.ledger.mutex:
                f = self.core.ledger.frontier(t)
                counter = {k: f[k] for k in ('generation', 'actual', 'reserved', 'unresolved', 'target', 'state')}
            tracks[t] = dict(state=row['state'], counter=counter,
                startup_held=t in self.core.gate.startup_held, gate_released=row['gate_released'],
                task_attempted=row['task_attempted'], periodic_tester_started=row['tester_cadence_started'],
                tester=None if row['tester'] is None else row['tester'].public(),
                checkpoint=None if row['checkpoint'] is None else row['checkpoint'].public(),
                racing=None if row['manager'] is None else row['manager'].public(),
                public_tests=None if row['consumer'] is None else row['consumer'].public(),
                failure=copy.deepcopy(row['failure']))
        return dict(schema='count14-formal100m-same-original-six-cohort-wip-v1', state=self.state,
            ready_tracks=sum(r['state'] == 'PREPARED_ORIGINAL_TRACK_MODELS_HELD' for r in self.tracks.values()),
            gates_released=sum(r['gate_released'] for r in self.tracks.values()),
            running_tracks=sum(r['state'] == RUNNING for r in self.tracks.values()),
            expected_tracks=6, tracks=tracks, final=None if self.final is None else self.final.public(),
            failure=copy.deepcopy(self.failure), same_original_owner_core_ledger_controller_dispatcher=True,
            final_retained_poll_failure=copy.deepcopy(getattr(self, 'final_retained_poll_failure', None)),
            final_first_failure_public=copy.deepcopy(getattr(self, 'final_first_failure_public', None)),
            periodic_tester_active_seconds=1800, preSEARCH_full_engine_loop_gate_added=False,
            cold_SDK_restore_qualified=False, formal_100M_actual_qualification=False,
            actual_public_program_binding_qualified=False, full_n3_terminal_path_only=True,
            n_lt3_terminal_producer_integration_remaining=True, six_track_retirement_implemented=False,
            formal_delivery_claimed=False)


def _formal_owner_public(owner):
    from native_cold_owner import NativeColdOwner
    value = NativeColdOwner.public(owner)
    cohort = owner.scientific_smoke
    need(type(cohort) is NativeFormalCohort and cohort.owner is owner,
         'FORMAL_PUBLIC_EXACT_SAME_ORIGINAL_COHORT')
    value.update(scientific_PREPARED=cohort.state == PREPARED,
        scientific_ACTIVATED=cohort.activation_attempted and all(r['gate_released'] and
            r['tester_cadence_started'] for r in cohort.tracks.values()),
        scientific_scope='FORMAL_SIX_100M_WIP_NOT_RUNTIME_QUALIFIED',
        formal_ready_tracks=sum(r['state'] == 'PREPARED_ORIGINAL_TRACK_MODELS_HELD' for r in cohort.tracks.values()),
        formal_gate_released_tracks=sum(r['gate_released'] for r in cohort.tracks.values()))
    return value


def bind_formal_cohort(owner, *, sources, game_sources, tester_execution_ports=None):
    """Cold-only same-instance bindings. Never patch original class/module."""
    from native_cold_owner import NativeColdOwner
    need(type(owner) is NativeColdOwner, 'FORMAL_NO_REPLACEMENT_OWNER_OR_PROXY')
    owner._validate_scientific_prefix()
    cohort = NativeFormalCohort(owner, sources=sources, game_sources=game_sources,
        tester_execution_ports=tester_execution_ports)
    owner.activate = MethodType(formal_activate_method(NativeColdOwner.activate), owner)
    owner.public = MethodType(_formal_owner_public, owner)
    return cohort
