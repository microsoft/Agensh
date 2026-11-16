"""One actual RACING-only SYSTEM smoke on the exact ORIGINAL cold owner.

New cold package only. Baseline715, original classes and active roots are never
modified. Three private constructor/preflight clones change only their exact
arm enum; launcher/checkpoint/FINAL retain their original types and all model,
physical drain, budget, archive and K3 methods. No new model dispatcher exists.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from types import MethodType
import ast
import copy
import inspect
import json
import os
import shlex
import textwrap

from common import need, digest, hash_file
from native_peer_registry import process_birth
from native_baseline_smoke import BaselineSmokeSources, NativeBaselineSmoke
from smoke_bootstrap_task_ports import NewRootSourceTaskPorts
from smoke_bootstrap_task_launch import NativeSameCoreSmokeLaunch
from smoke_checkpoint_final_controller import create_smoke_final_controller
from native_dynamic_checkpoint import DynamicCheckpointPorts
from smoke_checkpoint_final_retirement import create_smoke_retirement
from formal_count14_tester import original_formal_tester_run, FormalCount14Tester
from formal_count14_tester_public import TesterPublicExecution
from formal_count14_task_export import ApprovedTaskView
from count14_public_racing_judge import PublicToolScope
from native_beta_layout import native_aliases

APPROVED_TARGET = '/opt/count14-approved-input'
HELPERS = ('racing-background-00', *(f'racing-player-{i:02d}' for i in range(7)))


@dataclass(frozen=True)
class RacingGameSources:
    code_directory: Path
    code_map_sha256: str
    custodian_path: Path
    custodian_sha256: str
    public_tool_scope: PublicToolScope


def _arm_only(function):
    """One exact original arm comparison, inverse AST checked before use."""
    source = textwrap.dedent(inspect.getsource(function))
    tree = ast.parse(source)
    prior = copy.deepcopy(tree)
    found = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Compare) and len(node.ops) == len(node.comparators) == 1 and
            isinstance(node.ops[0], ast.Eq) and isinstance(node.comparators[0], ast.Constant) and
            node.comparators[0].value == 'DYNTEAM'):
            found.append(node)
            node.comparators[0].value = 'DYNTEAM_RACING'
    need(len(found) == 1, 'RACING_SMOKE_ONE_EXACT_ORIGINAL_ARM_ENUM_SITE')
    restored = copy.deepcopy(tree)
    matches = [node for node in ast.walk(restored) if isinstance(node, ast.Compare) and
               ast.dump(node, include_attributes=False) == ast.dump(found[0], include_attributes=False)]
    need(len(matches) == 1, 'RACING_SMOKE_ONE_INVERSE_ARM_SITE')
    matches[0].comparators[0].value = 'DYNTEAM'
    need(ast.dump(restored, include_attributes=False) == ast.dump(prior, include_attributes=False),
         'RACING_SMOKE_ONLY_ARM_ENUM_NO_LEDGER_MODEL_OR_FREEZE_DELTA')
    namespace = dict(function.__globals__)
    exec(compile(ast.fix_missing_locations(tree), inspect.getsourcefile(function) + ':racing-arm-only', 'exec'), namespace)
    return namespace[function.__name__]


def racing_checkpoint(core, trajectory, **kwargs):
    """Still an exact DynamicCheckpointPorts, not a bypassing proxy/subclass."""
    checkpoint = DynamicCheckpointPorts.__new__(DynamicCheckpointPorts)
    MethodType(_arm_only(DynamicCheckpointPorts.__init__), checkpoint)(core, trajectory, **kwargs)
    return checkpoint


def racing_launcher(core, trajectory, source_ports, *, pbench_source):
    """Still exact NativeSameCoreSmokeLaunch for original task/retirement ports."""
    launch = NativeSameCoreSmokeLaunch.__new__(NativeSameCoreSmokeLaunch)
    MethodType(_arm_only(NativeSameCoreSmokeLaunch.__init__), launch)(core, trajectory, source_ports,
                                                                   pbench_source=pbench_source)
    return launch


def racing_final_controller(core, configuration, configuration_sha256):
    controller = create_smoke_final_controller(core, configuration, configuration_sha256)
    # Original _prepare's required enabled arm is RACING rather than baseline.
    # Every profile/asset/key/capacity/child/import/schema/audit guard stays exact.
    controller._prepare = MethodType(_arm_only(type(controller)._prepare), controller)
    return controller


def _append(path, value):
    raw = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as out:
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())


def approved_helper_overlay(aliases, view):
    """Pure fixed RO input view for all eight native helper account slots."""
    need(type(view) is ApprovedTaskView and set(HELPERS) ==
         {role for role, alias in aliases.items() if alias['kind'] in ('racing_background', 'racing_player')},
         'RACING_SMOKE_ALL_EIGHT_HELPERS_SAME_APPROVED_INPUT')
    environment = dict(COUNT14_APPROVED_TASK_FILE=APPROVED_TARGET + '/task-description.bin',
        COUNT14_APPROVED_SOURCE_ARCHIVE=APPROVED_TARGET + '/source.tar.gz',
        COUNT14_APPROVED_TASK_SHA256=view.task_sha256,
        COUNT14_APPROVED_SOURCE_ARCHIVE_SHA256=view.source_archive_sha256,
        COUNT14_APPROVED_BOOTSTRAP_COMMIT=view.bootstrap_commit)
    return {'services': {aliases[role]['agent_service']: dict(environment=environment,
        volumes=[dict(type='bind', source=str(view.directory), target=APPROVED_TARGET, read_only=True)])
        for role in HELPERS}}


def install_approved_helper_view(core, trajectory, manager, view):
    need(trajectory in core.gate.startup_held and manager.core is core and manager.t == trajectory and
         manager.helper_index == 0 and not manager.helpers and type(view) is ApprovedTaskView and
         view.trajectory == trajectory and not core.ledger.mutex._is_owned(),
         'RACING_SMOKE_APPROVED_INPUT_BEFORE_ANY_HELPER_UP')
    need(hash_file(view.task_path)['sha256'] == view.task_sha256 and
         hash_file(view.source_archive)['sha256'] == view.source_archive_sha256,
         'RACING_SMOKE_APPROVED_HELPER_INPUT_PIN_UNCHANGED')
    root = Path(core.rows[trajectory]['root']) / 'native-racing-approved-input'
    root.mkdir(mode=0o700)
    path = root / 'compose.approved-helper-input-ro.json'
    _append(path, approved_helper_overlay(native_aliases('DYNTEAM_RACING'), view))
    host = core.native_host_environment['trajectories'][trajectory]
    if 'native_bridge_user_layer' in host:
        from native_bridge_user_cold import append_existing_cold_overlay
        append_existing_cold_overlay(core,trajectory,path)
    else:
        command = list(host['compose'])
        at = command.index('--project-name')
        command[at:at] = ['-f', str(path)]
        host['compose'] = tuple(command)
        host['launcher_env']['COUNT14_NATIVE_COMPOSE_COMMAND'] = shlex.join(command)
    return path


def verify_actual_helper_views(core, trajectory, view):
    """Fresh scope/mount/inode metadata only; no task/source/body is opened."""
    need(not core.ledger.mutex._is_owned(), 'RACING_SMOKE_HELPER_MOUNT_CHECK_OUTSIDE_LEDGER_LOCK')
    identity = (view.directory.stat().st_dev, view.directory.stat().st_ino)
    registry = core.native_containers
    records = {**registry.boot_plans, **registry.records}
    for role in HELPERS:
        record = records.get((trajectory, role, 'agent'))
        need(record is not None, 'RACING_SMOKE_ALL_EIGHT_REAL_HELPER_CONTAINERS')
        row = registry.docker.inspect(record.cid)
        from native_container_retirement import ContainerBinding
        if not isinstance(record, ContainerBinding):
            record = ContainerBinding(trajectory, role, 'agent', record.cid, record.image_id,
                                      record.init_birth, record.init_birth)
        registry.validate(record, row, running=True)
        mounts = [mount for mount in row['mounts'] if mount.get('Destination') == APPROVED_TARGET]
        need(len(mounts) == 1 and mounts[0].get('Type') == 'bind' and mounts[0].get('RW') is False and
             mounts[0].get('Source') == str(view.directory),
             'RACING_SMOKE_EXACT_HELPER_APPROVED_INPUT_READONLY_BIND')
        inside = Path('/proc', str(row['pid']), 'root', APPROVED_TARGET.lstrip('/')).stat()
        need((inside.st_dev, inside.st_ino) == identity,
             'RACING_SMOKE_HELPER_TRUE_MOUNT_SAME_APPROVED_INODE')
    return len(HELPERS)


class NativeRacingSmoke:
    def __init__(self, owner, *, sources, game_sources):
        from native_cold_owner import NativeColdOwner
        need(type(owner) is NativeColdOwner and type(sources) is BaselineSmokeSources and
             type(game_sources) is RacingGameSources and not hasattr(owner, 'scientific_smoke') and
             owner.core is not None and not owner.errors,
             'RACING_SMOKE_EXACT_ORIGINAL_COLD_OWNER_AND_FROZEN_SOURCES')
        core = owner.core
        racing = [t for t, row in core.rows.items() if row['arm'] == 'DYNTEAM_RACING']
        need(core.contract['mode'] == 'smoke' and not core.qualification_only and len(racing) == 1 and
             len(core.rows) == 2 and set(core.gate.startup_held) == set(core.rows) and
             hasattr(core, 'system_health') and hasattr(core, 'resource_producer') and
             hasattr(core, 'native_kernel_tool_custody'),
             'RACING_SMOKE_PAIRED_SMALL_CONTRACT_REAL_RESOURCE_AND_KERNEL_PORTS')
        need(core.rows[racing[0]]['request_cap'] == 13 and
             core.contract['capacities']['all_own_relay_physical'] == 96,
             'RACING_SMOKE_UNCHANGED_PER_TRACK13_ALL_OWN96_CAP')
        self.owner, self.core, self.sources, self.game_sources = owner, core, sources, game_sources
        self.t = racing[0]
        self.state, self.failure = 'BOUND_AWAIT_ORIGINAL_SOURCE', None
        self.birth = process_birth(os.getpid())
        self.source_ports = self.final = self.checkpoint = self.launch = self.tester = None
        self.manager = self.consumer = self.retirement = None
        self.approved_view_overlay = None
        self.host_checkpoint = None
        self.retirement_custody = None
        owner.scientific_smoke = self

    def _partial(self, error, phase):
        NativeBaselineSmoke._partial(self, error, phase)
        if self.consumer is not None:
            self.consumer.request_checkpoint_hold()
        if self.tester is not None:
            self.tester.checkpoint_hold()

    def _active_seconds(self):
        return self.core.active_clock.read(self.t)['active_ns'] / 1e9

    def prepare_tick(self):
        try:
            core, t = self.core, self.t
            if self.state == 'BOUND_AWAIT_ORIGINAL_SOURCE':
                source = getattr(core, 'source_bootstraps', {}).get(t)
                if source is None or source['state'] != 'SOURCE_ONLY_READY':
                    return self.public()
                self.owner.bootstrap.start(t)
                self.state = 'WAITING_ORIGINAL_INFRA'
                return self.public()
            if self.state in ('WAITING_ORIGINAL_INFRA', 'WAITING_EXACT_HOST_PUBLISH_READY'):
                boot = self.owner.bootstrap.step(t)
                need(boot['failure_type'] is None, 'RACING_SMOKE_ORIGINAL_INFRA_PARTIAL')
                if boot['phase'] != 'INFRA_READY_AWAIT_SOURCE_PUBLICATION':
                    return self.public()
                if self.source_ports is None:
                    self.source_ports = NewRootSourceTaskPorts(core,
                        original_task_host_source=self.sources.original_task_host_source)
                result = self.source_ports.prepare(t)
                if result['state'] == 'WAITING_EXACT_HOST_PUBLISH_READY':
                    self.state = result['state']
                    return self.public()
                need(result['state'] == 'SOURCE_TASK_CHANNEL_READY', 'RACING_SOURCE_PORTS_TRUE_READY')
                self.state = 'SOURCE_TASK_CHANNEL_READY'
                return self.public()
            if self.state == 'SOURCE_TASK_CHANNEL_READY':
                self.final = racing_final_controller(core, self.sources.final_configuration,
                                                     self.sources.final_configuration_sha256)
                self.final.preflight()
                core.cohort_resources.bind_aux_capacity(self.final.capacity)
                self.state = 'ORIGINAL_FINAL_BOUND_BEFORE_SCIENTIFIC_WAITERS'
                return self.public()
            if self.state == 'ORIGINAL_FINAL_BOUND_BEFORE_SCIENTIFIC_WAITERS':
                protocol = core.contract['v2_baseline_reference_protocol']
                pins = dict(manifest=digest(core.contract), protocol=self.final.scope.protocol_sha256(t),
                    source=protocol['source_bundle'], task_description=protocol['task_description'])
                self.checkpoint = racing_checkpoint(core, t, scope=self.final.scope,
                    source_ports=self.source_ports, pins=pins)
                self.state = 'ORIGINAL_RELAY_CHECKPOINT_BOUND'
                return self.public()
            if self.state == 'ORIGINAL_RELAY_CHECKPOINT_BOUND':
                run = original_formal_tester_run(core, t, self.source_ports,
                                                pbench_tester_source=self.sources.native_tester_source)
                execution = TesterPublicExecution(ports={}, active_now=self._active_seconds)
                self.tester = FormalCount14Tester(core, t, run, active_now=self._active_seconds,
                                                  public_execution=execution)
                self.tester.prepare()
                self.state = 'TASK_AWARE_NATIVE_TESTER_CYCLE0_READY'
                return self.public()
            if self.state == 'TASK_AWARE_NATIVE_TESTER_CYCLE0_READY':
                from smoke_racing_tools_game_manager import NativeRacingGameManager
                from native_racing_shared_tests import RacingSharedPublicTests
                g = self.game_sources
                self.manager = NativeRacingGameManager(core, t, code_directory=g.code_directory,
                    code_map_sha256=g.code_map_sha256, custodian_path=g.custodian_path,
                    custodian_sha256=g.custodian_sha256, public_tool_scope=g.public_tool_scope)
                self.approved_view_overlay = install_approved_helper_view(core, t, self.manager,
                                                                        self.tester.task_view)
                # Cold mounts MUST precede even the first worker UP. No ACL or
                # MM identity is invented for any native tester/helper account.
                self.consumer = RacingSharedPublicTests(core, t, self.manager)
                self.consumer.bind_original_publisher(self.tester)
                self.state = 'WAITING_EIGHT_ORIGINAL_HELPERS_ZERO_MODELS'
                return self.public()
            if self.state == 'WAITING_EIGHT_ORIGINAL_HELPERS_ZERO_MODELS':
                result = self.manager.poll()
                need(result['failure'] is None, 'RACING_SMOKE_HELPER_PREPARE_PARTIAL_RETAINED')
                if result['helpers_prepared'] != result['helpers_expected']:
                    return self.public()
                need(result['helpers_prepared'] == 8 and not self.manager.games,
                     'RACING_SMOKE_EIGHT_ORIGINAL_CLI_READY_WITHOUT_MODEL_GAME')
                self.owner.bootstrap.start_initial(t)
                self.state = 'WAITING_ORIGINAL_INITIAL_ROLES'
                return self.public()
            if self.state == 'WAITING_ORIGINAL_INITIAL_ROLES':
                boot = self.owner.bootstrap.step(t)
                need(boot['failure_type'] is None, 'RACING_SMOKE_ORIGINAL_INITIAL_PARTIAL')
                discovery = boot.get('discovery')
                if (boot['phase'] != 'INITIAL_UP_COMMANDS_RETURNED_MODEL_HELD' or
                    discovery is None or discovery['pending_components']):
                    return self.public()
                self.launch = racing_launcher(core, t, self.source_ports,
                                                pbench_source=self.sources.native_pbench_source)
                self.launch.start()
                from native_scientific_host_checkpoint import install_host_writer_checkpoint
                self.host_checkpoint = install_host_writer_checkpoint(self.checkpoint,
                    tester=self.tester, consumer=self.consumer, manager=self.manager)
                self.checkpoint.preflight()
                self.consumer.verify_actual_readonly_mounts()
                verify_actual_helper_views(core, t, self.tester.task_view)
                self.state = 'PREPARED_RACING_SMOKE_BASELINE_HELD'
                return self.public()
            return self.public()
        except Exception as error:
            self._partial(error, self.state)
            raise

    def activate(self):
        need(self.state == 'PREPARED_RACING_SMOKE_BASELINE_HELD' and process_birth(os.getpid()) == self.birth and
             self.manager.helper_index == 8 and not self.manager.games,
             'RACING_SMOKE_ACTIVATE_ONLY_TRUE_PREPARED_SAME_OWNER_ALL_EIGHT_READY')
        try:
            self.launch.validate_release_prefix()
            self.checkpoint.preflight()
            self.consumer.verify_actual_readonly_mounts()
            verify_actual_helper_views(self.core, self.t, self.tester.task_view)
            resources = self.core.cohort_resources
            resources.maybe_refresh()
            need(resources.experiment_open(), 'RACING_SMOKE_FRESH_HEALTH_AND_ALL_OWN_CAPACITY')
            evidence = dict(current_owner_authorized=True,
                gateway_health_sha256=resources.state['raw_public_receipt_sha256'],
                allocation_sha256=digest(asdict(resources.allocation)))
            self.final.release(owner_evidence=evidence)
            self.core.gate.release_startup(self.t)
            self.core.scientific_activation_qualified = True
            self.core.state = 'SAME_ORIGINAL_RACING_SYSTEM_SMOKE_RUNNING_BASELINE_HELD'
            self.state = 'ACTIVATED_ORIGINAL_TASK_PENDING'
            self.source_ports.task(self.t, self.launch)
            # This smoke only uses genuine task-aware cycle0. It deliberately
            # does NOT claim formal1800s tester/reference adaptation acceptance.
            self.state = 'RUNNING_RACING_SMOKE_BASELINE_HELD'
            return self.public()
        except Exception as error:
            self._partial(error, self.state)
            raise

    def poll(self):
        try:
            return self._poll()
        except Exception as error:
            self._partial(error, self.state)
            raise

    def _poll(self):
        if self.core.closed:
            return self.public()
        if self.retirement is not None:
            self.state = self.retirement.step()['state']
            return self.public()
        active = ('RUNNING_RACING_SMOKE_BASELINE_HELD', 'FINAL_PARKED_K3_PENDING',
                  'SMOKE_SEARCH_AND_K3_COMPLETE', 'PARTIAL_RETAINED_NO_RETRY')
        if self.state not in active:
            return self.prepare_tick()
        if self.final is not None and self.final.state in ('PREPARED_ORIGINAL_FINAL_MODELS_PAUSED', 'RELEASED'):
            if self.state == 'PARTIAL_RETAINED_NO_RETRY':
                self.final.dispatcher.poll()  # paid jobs retained, no fresh claim
            else:
                self.final.poll()
        if self.consumer is not None:
            self.consumer.poll()  # also completes a held original bounded RPC
            if self.state != 'PARTIAL_RETAINED_NO_RETRY':
                need(self.consumer.failure is None, 'RACING_SMOKE_ORIGINAL_PUBLIC_CONSUMER_PARTIAL')
        if self.state in ('RUNNING_RACING_SMOKE_BASELINE_HELD', 'FINAL_PARKED_K3_PENDING'):
            with self.core.ledger.mutex:
                frontier = self.core.ledger.frontier(self.t)
                search_running = frontier['state'] == 'RUNNING'
            # Once DRAINING starts, the checkpoint sidecar writes its final
            # fresh guest HOLD then freezes. Never keep host manager metadata
            # writes running across PARKING/capture or wait for Game exit.
            if (self.checkpoint.state in ('BOUND_MODELS_HELD', 'RUNNING') and search_running and
                not self.host_checkpoint.held):
                result = self.manager.poll()
                need(result['failure'] is None, 'RACING_SMOKE_ACTUAL_GAME_PARTIAL_RETAINED')
            self.checkpoint.step()
            if self.checkpoint.state == 'FINAL_PARKED':
                self.state = 'FINAL_PARKED_K3_PENDING'
            if self.state == 'FINAL_PARKED_K3_PENDING':
                counts = self.core.queue.frontier()
                if counts and set(counts) == {'COMPLETE'} and counts['COMPLETE'] == 6:
                    self.tester.close_admission()
                    self.consumer.close_after_drained()
                    self.state = 'SMOKE_SEARCH_AND_K3_COMPLETE'
                    self.retirement = create_smoke_retirement(self.core, checkpoint=self.checkpoint,
                                                             final=self.final, launch=self.launch)
                    from native_racing_smoke_retirement import install_racing_retirement
                    self.retirement_custody = install_racing_retirement(self.retirement,
                        manager=self.manager, consumer=self.consumer)
        return self.public()

    def public(self):
        if self.core.closed:
            return copy.deepcopy(self.core.smoke_terminal_public)
        with self.core.ledger.mutex:
            frontier = self.core.ledger.frontier(self.t)
            counter = {k: frontier[k] for k in ('generation', 'actual', 'reserved', 'unresolved', 'target', 'state')}
        return dict(schema='count14-actual-racing-system-smoke-owner-v1', state=self.state,
            trajectory=self.t, counter=counter, DYNTEAM_startup_held=all(t in self.core.gate.startup_held
                for t, row in self.core.rows.items() if row['arm'] == 'DYNTEAM'),
            final=None if self.final is None else self.final.public(),
            checkpoint=None if self.checkpoint is None else self.checkpoint.public(),
            tester=None if self.tester is None else self.tester.public(),
            racing=None if self.manager is None else self.manager.public(),
            public_tests=None if self.consumer is None else self.consumer.public(),
            retirement=None if self.retirement is None else self.retirement.public(),
            formal_six_trajectory_activation=False, periodic_formal_tester_started=False,
            game_rounds_not_inferred_from_helper_prepare=True, failure=copy.deepcopy(self.failure))


def _racing_owner_activate(original):
    tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
    prior = copy.deepcopy(tree)
    imports = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == 'native_baseline_smoke' and
               [(a.name, a.asname) for a in n.names] == [('NativeBaselineSmoke', None)]]
    need(len(imports) == 1, 'RACING_SMOKE_ONE_ORIGINAL_OWNER_ACTIVATE_TYPE_IMPORT')
    imports[0].module = 'native_racing_smoke'
    imports[0].names = [ast.alias(name='NativeRacingSmoke', asname='NativeBaselineSmoke')]
    restored = copy.deepcopy(tree)
    node = next(n for n in ast.walk(restored) if isinstance(n, ast.ImportFrom) and n.module == 'native_racing_smoke')
    node.module = 'native_baseline_smoke'
    node.names = [ast.alias(name='NativeBaselineSmoke', asname=None)]
    need(ast.dump(restored, include_attributes=False) == ast.dump(prior, include_attributes=False),
         'RACING_SMOKE_ORIGINAL_OWNER_ACTIVATE_ONLY_EXACT_TYPE_ENUM')
    namespace = dict(original.__globals__)
    exec(compile(ast.fix_missing_locations(tree), __file__ + ':owner-activate-type-enum', 'exec'), namespace)
    return namespace[original.__name__]


def _racing_owner_public(owner):
    from native_cold_owner import NativeColdOwner
    value = NativeColdOwner.public(owner)
    if owner.core.closed:
        return value
    smoke = owner.scientific_smoke
    need(type(smoke) is NativeRacingSmoke and smoke.owner is owner,
         'RACING_SMOKE_PUBLIC_EXACT_SAME_OWNER_REGISTRATION')
    value['scientific_PREPARED'] = smoke.state == 'PREPARED_RACING_SMOKE_BASELINE_HELD'
    value['scientific_ACTIVATED'] = smoke.state in ('RUNNING_RACING_SMOKE_BASELINE_HELD',
        'FINAL_PARKED_K3_PENDING', 'SMOKE_SEARCH_AND_K3_COMPLETE')
    value['scientific_scope'] = 'RACING_SYSTEM_SMOKE_ONLY_BASELINE_HELD'
    return value


def bind_racing_smoke(owner, *, sources, game_sources):
    """Cold-only method bindings; owner itself stays exact NativeColdOwner."""
    from native_cold_owner import NativeColdOwner
    need(type(owner) is NativeColdOwner, 'RACING_SMOKE_NO_REPLACEMENT_OR_SUBCLASS_OWNER')
    owner._validate_scientific_prefix()
    smoke = NativeRacingSmoke(owner, sources=sources, game_sources=game_sources)
    owner.activate = MethodType(_racing_owner_activate(NativeColdOwner.activate), owner)
    owner.public = MethodType(_racing_owner_public, owner)
    return smoke.public()
