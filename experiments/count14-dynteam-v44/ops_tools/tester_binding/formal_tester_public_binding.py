"""Cold-only per-slot tester bindings to the ORIGINAL public-tool executor.

No guessed candidate/program, official oracle, new model/dispatcher, privilege,
socket mount, private-body read or financial operation. Science actively writes
the fixed metadata protocol. Missing actual programs stay PENDING. Only fixed
registration fields and stat/inode/UID/mode cross this host control seam.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path, PurePosixPath
from types import FunctionType, MethodType
import copy
import hashlib
import json
import os
import re
import shlex
import stat

from common import need, digest, publish, wire
from native_peer_registry import process_birth
from native_beta_layout import native_aliases
from count14_public_racing_judge import PublicToolScope, NativePublicProbePort
from formal_count14_tester_public import TesterPublicExecution, native_tester_public_exec
from smoke_racing_tools_public_exec import PublicProgramBinding, RUNNER

PROTOCOL_TARGET = '/opt/count14-public-probe/PROGRAM_REGISTRATION_PROTOCOL.md'
REGISTRATION_RELATIVE = Path('tests/.count14-public-probe/registrations')
REGISTRATION_SCHEMA = 'count14-native-tester-public-program-registration-v1'
FIELDS = {'schema', 'task_slot', 'program', 'public_task_only', 'official_verdict', 'private_reference_access'}
CHARTER_REFERENCE = ('\nCount14 native tester public-program registration: read the fixed adapter protocol at '
    + PROTOCOL_TARGET + '. Build/select actual per-slot PUBLIC /work executable FILES with your original '
    'charged native tools, then publish only its specified metadata; never guess a program, use a directory, '
    'a reference/evaluator, or treat an unbound/invalid case as a pass. Use the original tester Git '
    'repository/tracked normal push so native phase cleanup preserves your registration and executable.\n')


@dataclass(frozen=True)
class TesterPublicBindingSources:
    runner_host_path: Path
    runner_sha256: str
    protocol_host_path: Path
    protocol_sha256: str
    scope: PublicToolScope


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _code(path, expected, basename):
    path = Path(path)
    value = path.lstat()
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink() and
        path.name == basename and stat.S_ISREG(value.st_mode) and value.st_uid in (0, os.geteuid()) and
        not value.st_mode & 0o022 and value.st_nlink == 1 and value.st_size <= 1024 * 1024 and
        re.fullmatch('[0-9a-f]{64}', expected) is not None and sha(path.read_bytes()) == expected,
        'TESTER_PUBLIC_BINDING_EXACT_FROZEN_ADAPTER_CODE_OR_PROTOCOL')
    return path


def cold_overlay(arm, sources):
    need(arm in ('DYNTEAM', 'DYNTEAM_RACING') and type(sources) is TesterPublicBindingSources and
        type(sources.scope) is PublicToolScope, 'TESTER_PUBLIC_SAME_TYPED_TWO_ARM_COLD_OVERLAY')
    sources.scope.checked()
    return dict(services={native_aliases(arm)['tester-00']['agent_service']: dict(
        environment=dict(COUNT14_PUBLIC_PROGRAM_REGISTRATION_PROTOCOL=PROTOCOL_TARGET),
        volumes=[dict(type='bind', source=str(sources.runner_host_path), target=RUNNER, read_only=True),
            dict(type='bind', source=str(sources.protocol_host_path), target=PROTOCOL_TARGET, read_only=True)])})


def program_stat(workspace, program, *, expected_uid=10000):
    """Fixed explicit path -> stat ONLY. Never open/hash program bytes."""
    pure = PurePosixPath(program) if type(program) is str else None
    need(pure is not None and pure.is_absolute() and str(pure) == program and
        pure != PurePosixPath('/work') and pure.is_relative_to('/work') and '..' not in pure.parts and
        re.fullmatch(r'/[A-Za-z0-9_./+\-]+', program) is not None,
        'TESTER_PUBLIC_PROGRAM_EXPLICIT_WORK_EXECUTABLE_PATH')
    workspace = Path(workspace)
    need(workspace.is_absolute() and workspace.resolve() == workspace and workspace.is_dir(),
        'TESTER_PUBLIC_ORIGINAL_CANONICAL_WORKSPACE')
    path = workspace.joinpath(*pure.relative_to('/work').parts)
    try:
        value = path.lstat()
    except FileNotFoundError:
        return None
    need(path.resolve() == path and not path.is_symlink() and path.is_relative_to(workspace) and
        stat.S_ISREG(value.st_mode) and value.st_uid == expected_uid and value.st_nlink == 1 and
        bool(value.st_mode & 0o111) and not value.st_mode & 0o002,
        'TESTER_PUBLIC_ACTUAL_REGULAR_NATIVE_UID_EXECUTABLE_NOT_DIRECTORY_OR_ALIAS')
    return dict(device=value.st_dev, inode=value.st_ino, uid=value.st_uid, gid=value.st_gid,
        mode=stat.S_IMODE(value.st_mode), size=value.st_size, mtime_ns=value.st_mtime_ns,
        ctime_ns=value.st_ctime_ns)


def read_registration(workspace, slot, *, expected_uid=10000):
    """Only one exact small PUBLIC control file; no science directory scan."""
    need(type(slot) is int and 1 <= slot <= 14, 'TESTER_PUBLIC_EXACT_REGISTERED_SLOT')
    path = Path(workspace) / REGISTRATION_RELATIVE / f'slot-{slot:02d}.PUBLIC.json'
    try:
        initial = path.lstat()
    except FileNotFoundError:
        return None
    need(path.resolve() == path and not path.is_symlink() and stat.S_ISREG(initial.st_mode) and
        initial.st_uid == expected_uid and initial.st_nlink == 1 and not initial.st_mode & 0o022 and
        0 < initial.st_size <= 4096, 'TESTER_PUBLIC_ONLY_FIXED_METADATA_OWNER_KIND_MODE_SIZE')
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        start = os.fstat(fd)
        raw = os.read(fd, 4097)
        end, last = os.fstat(fd), path.lstat()
        key = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode, s.st_uid)
        need(len(raw) == initial.st_size and key(initial) == key(start) == key(end) == key(last),
            'TESTER_PUBLIC_REGISTRATION_METADATA_ATOMIC_STABLE_READ')
    finally:
        os.close(fd)

    def pairs(items):
        value = {}
        for key, entry in items:
            need(key not in value, 'TESTER_PUBLIC_NO_DUPLICATE_REGISTRATION_FIELDS')
            value[key] = entry
        return value

    value = json.loads(raw, object_pairs_hook=pairs)
    need(type(value) is dict and set(value) == FIELDS and value['schema'] == REGISTRATION_SCHEMA and
        type(value['task_slot']) is int and value['task_slot'] == slot and
        value['public_task_only'] is True and value['official_verdict'] is False and
        value['private_reference_access'] is False,
        'TESTER_PUBLIC_EXACT_METADATA_ONLY_PUBLIC_TASK_NOT_ORACLE')
    observed = program_stat(workspace, value['program'], expected_uid=expected_uid)
    if observed is None:
        return None
    return value, observed, sha(raw)  # hash fixed metadata only, NOT program content


def clone_release_reference(function):
    """Original method code; one NEW adapter-charter reference, not a task edit."""
    before = function.__globals__['COUNT14_TESTER_DIRECTIVE']
    need(PROTOCOL_TARGET not in before, 'TESTER_PUBLIC_ADD_PROTOCOL_REFERENCE_ONCE')
    namespace = dict(function.__globals__, COUNT14_TESTER_DIRECTIVE=before + CHARTER_REFERENCE)
    cloned = FunctionType(function.__code__, namespace, function.__name__, function.__defaults__, function.__closure__)
    cloned.__kwdefaults__ = function.__kwdefaults__
    need(cloned.__code__ is function.__code__ and function.__globals__['COUNT14_TESTER_DIRECTIVE'] == before and
        {k for k in namespace if namespace[k] is not function.__globals__[k]} == {'COUNT14_TESTER_DIRECTIVE'},
        'TESTER_PUBLIC_ORIGINAL_RELEASE_BODY_AND_UPSTREAM_GLOBALS_UNCHANGED')
    return cloned, dict(original_directive_sha256=sha(before.encode()),
        adapter_reference_sha256=sha(CHARTER_REFERENCE.encode()), new_directive_sha256=sha((before + CHARTER_REFERENCE).encode()),
        original_method_code_identity=True, upstream_70e_or_Game_prompt_changed=False)


class FormalTesterPublicBindings:
    def __init__(self, core, trajectory, tester, *, sources):
        from original_relay_core import OriginalRelayCore
        from formal_count14_tester import FormalCount14Tester
        need(type(core) is OriginalRelayCore and type(tester) is FormalCount14Tester and
            tester.core is core and tester.t == trajectory and type(tester.execution) is TesterPublicExecution and
            trajectory in core.gate.startup_held and not core.qualification_only and not core.closed and
            tester.state == 'BOUND_NOT_PREPARED' and not tester.execution.ports and
            not hasattr(tester, 'public_program_bindings') and type(sources) is TesterPublicBindingSources,
            'TESTER_PUBLIC_COLD_INSTALL_BEFORE_ORIGINAL_CYCLE0_AND_ANY_NATIVE_TESTER_UP')
        need(not core.ledger.mutex._is_owned(), 'TESTER_PUBLIC_NO_IO_UNDER_SCIENCE_LOCK')
        sources.scope.checked()
        runner = _code(sources.runner_host_path, sources.runner_sha256, 'smoke_racing_tools_public_runner.cjs')
        protocol = _code(sources.protocol_host_path, sources.protocol_sha256, 'PROGRAM_REGISTRATION_PROTOCOL.md')
        registry = core.native_containers
        need(all((trajectory, 'tester-00', 'agent') not in rows for rows in
            (registry.records, registry.boot_plans)), 'TESTER_PUBLIC_RO_OVERLAY_BEFORE_ANY_TESTER_AGENT_BIRTH')
        self.core, self.t, self.tester, self.sources = core, trajectory, tester, sources
        self.workspace = Path(core.native_layout.current(trajectory)['roles']['tester-00']['workspace'])
        self.owner_birth, self.contract_sha256 = process_birth(os.getpid()), digest(core.contract)
        self.registrations, self.native, self.revisions, self.binding_history = {}, {}, {}, {}
        self.cursor, self.registering, self.held, self.closed, self.failure = 1, False, True, False, None
        self.control = tester.control / 'public-program-bindings'
        self.control.mkdir(mode=0o700)
        self.original_poll, self.original_clear = tester.poll, tester.physical_clear
        self.original_hold, self.original_resume = tester.checkpoint_hold, tester.resume_after_cut
        self.original_close = tester.close_admission
        self.original_public = tester.public
        self.host = self.original_host_control = None
        host = core.native_host_environment['trajectories'][trajectory]
        path = self.control / 'compose.tester-native-public-runner-ro.json'
        publish(path, wire(cold_overlay(core.rows[trajectory]['arm'], sources)), mode=0o400)
        if 'native_bridge_user_layer' in host:
            from native_bridge_user_cold import append_existing_cold_overlay
            append_existing_cold_overlay(core,trajectory,path)
        else:
            command = list(host['compose'])
            command[command.index('--project-name'):command.index('--project-name')] = ['-f', str(path)]
            host['compose'] = tuple(command)
            host['launcher_env']['COUNT14_NATIVE_COMPOSE_COMMAND'] = shlex.join(command)
        release, delta = clone_release_reference(tester._release.__func__)
        tester._release = MethodType(release, tester)
        publish(self.control / 'COLD_PROTOCOL_REFERENCE_DIFF_PUBLIC.json', wire(dict(
            schema='count14-tester-protocol-charter-cold-diff-v1', **delta,
            runner_sha256=sources.runner_sha256, protocol_sha256=sources.protocol_sha256,
            per_arm_behavior_identical=True, actual_public_execution_qualified=False)), mode=0o400)
        tester.public_program_bindings = self
        tester.poll = MethodType(lambda own: self.poll_tester(), tester)
        tester.physical_clear = MethodType(lambda own: self.physical_clear(), tester)
        tester.checkpoint_hold = MethodType(lambda own: self.checkpoint_hold(), tester)
        tester.resume_after_cut = MethodType(lambda own: self.resume_after_cut(), tester)
        tester.close_admission = MethodType(lambda own: self.close_admission(), tester)
        tester.public = MethodType(lambda own: self.tester_public(), tester)

    def _outside(self):
        need(not self.core.ledger.mutex._is_owned() and process_birth(os.getpid()) == self.owner_birth,
            'TESTER_PUBLIC_BINDING_SAME_OWNER_OUTSIDE_LEDGER_LOCK')

    def verify_actual_mounts(self):
        self._outside()
        registry = self.core.native_containers
        record = registry.records.get((self.t, 'tester-00', 'agent'))
        if record is None:
            return None
        view = registry.docker.inspect(record.cid)
        registry.validate(record, view, running=True)
        need(process_birth(record.init_birth.pid) == record.init_birth,
            'TESTER_PUBLIC_EXACT_ORIGINAL_NATIVE_CONTAINER_BIRTH')
        for source, target in ((self.sources.runner_host_path, RUNNER),
                               (self.sources.protocol_host_path, PROTOCOL_TARGET)):
            mounts = [row for row in view['mounts'] if row.get('Destination') == target]
            need(len(mounts) == 1 and mounts[0].get('Type') == 'bind' and mounts[0].get('RW') is False and
                mounts[0].get('Source') == str(source), 'TESTER_PUBLIC_FIXED_RUNNER_PROTOCOL_RO_MOUNTS')
            inside = Path('/proc', str(record.init_birth.pid), 'root', target.lstrip('/')).stat()
            outside = Path(source).stat()
            need((inside.st_dev, inside.st_ino) == (outside.st_dev, outside.st_ino),
                'TESTER_PUBLIC_TRUE_GUEST_MOUNT_SAME_FROZEN_INODE')
        return record

    def existing_cases(self, slot):
        # Scientific runtime callback only. Uses the last original completed
        # release's exact suite; never scans/reads a candidate or official data.
        from formal_count14_tester import public_cases
        with self.tester.lock:
            last = copy.deepcopy(self.tester.last)
        if last is None:
            return ()
        suite = self.tester.run.inbox / f'{last["number"]:04d}' / 'suite'
        return tuple((name, directory) for case_slot, name, directory in public_cases(suite) if case_slot == slot)

    def _register(self, slot, data):
        value, observed, metadata_sha = data
        old = self.registrations.get(slot)
        if old is not None and old['registration'] == value and old['original_program_stat'] == observed:
            return False  # same real metadata/stat, not another registration/replay
        with self.tester.execution.lock:
            if self.tester.execution.busy:
                return False
        if not self.tester.execution.physical_clear() or any(not instance.physical_clear() for instance in self.native.values()):
            return False  # never replace a binding of an accepted/in-flight tool
        record = self.verify_actual_mounts()
        if record is None:
            return False
        binding = PublicProgramBinding(self.t, 'tester-00', slot, record.cid, value['program'],
            Path(self.sources.runner_host_path), self.sources.runner_sha256)
        native = self.native.get(slot)
        refreshing = native is not None
        if refreshing:
            need(old is not None and native.binding.container_id == record.cid and
                slot in self.tester.execution.ports,
                'TESTER_PUBLIC_REFRESH_ONLY_SAME_ORIGINAL_NATIVE_CONTAINER_AND_REGISTERED_PORT')
            previous_binding = native.binding
            port = self.tester.execution.ports[slot]
        else:
            native = native_tester_public_exec(self.core, binding=binding, scope=self.sources.scope,
                existing_cases=lambda: self.existing_cases(slot), active_now=self.tester.active_now)
            self.native[slot] = native  # retain BEFORE fallible publication/registration
            previous_binding = None
        original = native.port()

        def guarded_run_case(directory, deadline):
            # Original runner also realpaths/X_OK-checks the program in guest,
            # enforces UID10000/caps0 and preserves actual Popen/cgroup custody.
            need(program_stat(self.workspace, native.binding.program) is not None,
                'TESTER_PUBLIC_PROGRAM_PENDING_NOT_A_FABRICATED_PASS')
            return original.run_case(directory, deadline)

        if not refreshing:
            port = NativePublicProbePort(scope=original.scope, run_case=guarded_run_case,
                existing_cases=original.existing_cases, physical_clear=original.physical_clear)
        revision = self.revisions.get(slot, 0) + 1
        receipt = dict(schema='count14-tester-public-program-binding-control-v1', trajectory=self.t,
            task_slot=slot, revision=revision, registration=value, metadata_sha256=metadata_sha, original_program_stat=observed,
            container_id=record.cid, init_birth=asdict(record.init_birth),
            runner_sha256=self.sources.runner_sha256, protocol_sha256=self.sources.protocol_sha256,
            native_scope_sha256=self.sources.scope.native_scope_sha256, official_verdict=False,
            prior_binding_sha256=None if old is None else digest(old),
            prior_native_exec_job_ids=tuple(sorted(native.jobs)))
        prefix = f'SLOT_{slot:02d}_REV_{revision:08d}'
        publish(self.control / (prefix + '_INTENT_PUBLIC.json'), wire(receipt), mode=0o400)
        if refreshing:
            self.binding_history.setdefault(slot, []).append(previous_binding)
            # Normal typed control binding refresh on the SAME retained runtime
            # and port, only after original physical-clear. No jobs/judges/case
            # receipts are erased; no old case is dispatched again.
            native.binding = binding
            native._scope()  # original CID/birth/RO runner check, not a new exec
        else:
            self.tester.execution.register_slot(slot, port)  # ORIGINAL actual typed registration once
        self.registrations[slot] = receipt
        self.revisions[slot] = revision
        publish(self.control / (prefix + '_DONE_PUBLIC.json'), wire(dict(
            schema='count14-tester-public-program-registered-public-v1', task_slot=slot,
            revision=revision, binding_sha256=digest(receipt), native_typed_port_registered=True,
            same_runtime_binding_refreshed=refreshing,
            official_verdict=False, model_calls=0)), mode=0o400)
        return True

    def poll_registration(self):
        self._outside()
        if self.closed or self.held or self.failure is not None or not self.original_clear():
            return
        with self.tester.lock:
            if self.tester.hold or self.tester.closed or self.tester.busy:
                return
        slot = self.cursor
        self.cursor = slot % 14 + 1
        try:
            data = read_registration(self.workspace, slot)
        except (ValueError, RuntimeError, OSError):
            # No action/request was accepted. Bad/incomplete PUBLIC metadata is
            # unbound, never a successful public execution. Next normal read is
            # not a model/case retry or a guessed program.
            return
        if data is None:
            return
        self.registering = True
        try:
            self._register(slot, data)
        except Exception as error:
            locations, tb = [], error.__traceback__
            while tb:
                locations.append(dict(file=tb.tb_frame.f_code.co_filename, line=tb.tb_lineno,
                    function=tb.tb_frame.f_code.co_name))
                tb = tb.tb_next
            self.failure = dict(PUBLIC_code='TESTER_PUBLIC_BINDING_PARTIAL_RETAINED_NO_RETRY',
                exception_type=type(error).__name__, locations=locations)
        finally:
            self.registering = False

    def poll_tester(self):
        if not self.closed:
            self.held = self.tester.hold
            self.poll_registration()
        return self.original_poll()

    def physical_clear(self):
        return not self.registering and self.failure is None and self.original_clear() and all(
            native.physical_clear() for native in self.native.values())

    def checkpoint_hold(self):
        self._outside()
        self.held = True
        return self.original_hold() and self.physical_clear()

    def resume_after_cut(self):
        self._outside()
        need(not self.closed and self.physical_clear(), 'TESTER_PUBLIC_RESUME_ONLY_SAME_DRAINED_BINDINGS')
        result = self.original_resume()
        self.held = False
        return result

    def close_admission(self):
        self._outside()
        self.closed = self.held = True
        self.original_close()
        return self.physical_clear()

    def capture_control(self):
        self._outside()
        need(self.held and self.physical_clear(), 'TESTER_PUBLIC_CAPTURE_ONLY_ORIGINAL_HOST_HOLD_DRAIN')
        return dict(schema='count14-tester-public-binding-same-live-control-v1', trajectory=self.t,
            contract_sha256=self.contract_sha256, owner_birth=asdict(self.owner_birth),
            registrations={str(slot): json.loads(wire(row)) for slot, row in self.registrations.items()},
            cold_SDK_or_new_container_restore_qualified=False)

    def bind_formal_host_writer(self, host):
        """Cold SAME host-writer control seam; its existing roots include us.

        tester.control and native exec custody roots already belong to original
        tester.capture_roots; guest registrations/program/.git probes remain in
        original WHOLE /work. No extra writable mount or writer domain is added.
        """
        from formal_host_writers import FormalHostWriters
        need(type(host) is FormalHostWriters and host.core is self.core and host.t == self.t and
            host.tester is self.tester and host.checkpoint.state == 'BOUND_MODELS_HELD' and
            self.t in self.core.gate.startup_held and self.host is None,
            'TESTER_PUBLIC_BIND_HOST_CONTROL_ONLY_SAME_COLD_FORMAL_WRITER')
        self.host, self.original_host_control = host, host.control

        def control(own):
            result = self.original_host_control()
            need('tester_public_program_bindings' not in result,
                'TESTER_PUBLIC_ONE_UNAMBIGUOUS_CAPTURE_CONTROL_FIELD')
            result['tester_public_program_bindings'] = self.capture_control()
            return result

        host.control = MethodType(control, host)
        # Original checkpoint callback resolves this same host.control method;
        # other cold host-writer hooks may chain it without class/global edits.
        return self

    def verify_same_live_restore(self, control):
        # Same immutable actual ports/CID/birth, not re-register/replay or paid
        # rebaseline. Original checkpoint captures these PUBLIC control files
        # under tester.control and complete /work, including native .git probes.
        need(control == self.capture_control(), 'TESTER_PUBLIC_RESTORE_ONLY_SAME_LIVE_CAPTURED_CONTROL')
        if self.registrations:
            record = self.verify_actual_mounts()
            need(record is not None and all(row['container_id'] == record.cid and
                row['init_birth'] == asdict(record.init_birth) for row in self.registrations.values()),
                'TESTER_PUBLIC_NO_DIFFERENT_CONTAINER_OR_PAID_REBASELINE_RESTORE')
        return True

    def public(self):
        return dict(schema='count14-formal-tester-public-bindings-wip-v1', registered_slots=sorted(self.registrations),
            binding_revisions={str(slot): revision for slot, revision in self.revisions.items()},
            pending_slots=14 - len(self.registrations), binding_writer_busy=self.registering,
            checkpoint_held=self.held, closed=self.closed, failure=copy.deepcopy(self.failure),
            official_verdict=False, model_calls_by_adapter=0, actual_Dev4_or_public_execution_qualified=False)

    def tester_public(self):
        value = self.original_public()
        value['public_program_bindings'] = self.public()
        return value


def install_tester_public_bindings(core, trajectory, tester, *, sources):
    return FormalTesterPublicBindings(core, trajectory, tester, sources=sources)
