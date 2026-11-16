"""New-root count14 task-aware native tester; never the ProgramBench oracle.

Only trusted scientific runtime executes these exports. Original archive and
publish methods, native tester_cycle IDs, publish-before-latest periodic order,
ACP charged sessions, headers and model dispatcher are preserved. Single-
program prepare_main/capture_reference/score and destructive retry/cleanup/run
are NOT called. This is separate from the already frozen SYSTEM smoke tree.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath
import math
import os
import re
import shutil
import stat
import tarfile
import threading
import time

from common import need, digest, hash_file, strict
from native_system_probe_child import append
from smoke_bootstrap_task_tester import (original_tester_namespace,
    TOKEN_CONTROLLED_WALL_SENTINEL_SECONDS)
from formal_count14_task_export import approved_task_export, ApprovedTaskView
from formal_count14_tester_public import TesterPublicExecution

CADENCE_ACTIVE_SECONDS = 1800
PUBLIC_CASE_ABI = 'tests/count14/<slot-1-through-14>/<case-id>/{cmd,stdin,files/}'
COUNT14_TESTER_DIRECTIVE = '''COUNT14 task-aware tester assignment.
The immutable task below is the SAME approved task given to the search team.
This is count14, NOT ProgramBench single-program replacement. No reference
binary or official evaluator is supplied to you. Never invoke /opt/pbench or
interpret public assertions as official count14 success verdicts.
Use the approved source archive and, for periodic assignments, the exact
immutable current-main archive specified below. Unpack scientific inputs only
inside your own /work. Your private Gitea tests repository remains the original
native tester repository; do not request org/main write or Mattermost access.
Develop task-specific publicly reproducible test assertions and fixtures there.
Case ABI: tests/count14/<slot-1-through-14>/<case-id>/cmd; optional stdin and
files/. cmd contains a shell assertion using PROG as the explicit public /work
program binding. Exit 0/1 is only public assertion pass/failure; infrastructure
errors and signals are invalid/unknown, NEVER official verdicts. Do not copy
official/private/reference tests or results. The native public-tool runner may
reproduce an assertion twice and share that public evidence with workers.
Publish genuine useful cases; an empty suite is not completed evaluation.
All model work, including yours, uses the original charged native session and
the same token budget. Checkpoint/K3 official evaluation stays in its original
separate pipeline. Do not start a model API client or replay a request.
'''


def native_tester_names(arm, organization):
    """All original native tester slots; RACING helpers really occupy 2..9."""
    from native_beta_layout import native_aliases
    aliases = native_aliases(arm)
    slots = sorted((value['native_short'] for value in aliases.values()
                    if re.fullmatch(r'tester[1-9][0-9]*', value['native_short'])),
                   key=lambda short: int(short.removeprefix('tester')))
    need(slots == ['tester' + str(i + 1) for i in range(len(slots))] and
         aliases['tester-00']['native_short'] == 'tester1' and
         aliases['tester-00']['kind'] == 'tester',
         'DYNTEAM_FORMAL_TESTER_NATIVE_ROSTER_DERIVED_EXACT_SLOTS')
    return [organization + '-' + short for short in slots]


def _readable_directory(path):
    path = Path(path)
    path.mkdir(mode=0o755)
    # umask must not turn a RO bind's scientific input into UID10000-unreadable
    # root0700. Only this newly created exact directory changes permissions.
    path.chmod(0o755)
    return path


def _safe_suite_extract(archive, destination):
    """No links/special files, duplicate names or escapes from NEW suite leaf.

    This parser runs in the scientific runtime, never the coordinator. It does
    not execute tester files or trust tar ownership/permissions. No extraction
    retry/rmtree, original repo and original archive remain intact on failure.
    """
    destination = Path(destination)
    need(destination.resolve() == destination and not destination.exists(),
         'DYNTEAM_TESTER_NEW_SUITE_DESTINATION')
    _readable_directory(destination)
    with tarfile.open(archive, 'r:gz') as source:
        members = source.getmembers()
        names = set()
        for member in members:
            name = member.name.rstrip('/')
            parts = name.split('/')
            need(bool(name) and '\\' not in name and '\x00' not in name and
                 not PurePosixPath(name).is_absolute() and
                 all(p not in ('', '.', '..') for p in parts) and name not in names and
                 (member.isdir() or member.isfile()) and not member.issym() and not member.islnk(),
                 'DYNTEAM_TESTER_SUITE_NO_LINK_SPECIAL_DUPLICATE_OR_ESCAPE')
            names.add(name)
        for member in members:
            path = destination.joinpath(*member.name.rstrip('/').split('/'))
            path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            # All parents are from this new verified tar tree, never source
            # symlinks. Set traverse bits individually for the RO native mount.
            for parent in path.parents:
                if parent == destination.parent:
                    break
                parent.chmod(0o755)
            if member.isdir():
                path.mkdir(mode=0o755, exist_ok=True)
                path.chmod(0o755)
                continue
            incoming = source.extractfile(member)
            need(incoming is not None, 'DYNTEAM_TESTER_SUITE_REGULAR_MEMBER')
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                with incoming, os.fdopen(fd, 'wb', closefd=False) as out:
                    shutil.copyfileobj(incoming, out)
                    need(out.tell() == member.size, 'DYNTEAM_TESTER_SUITE_MEMBER_SIZE')
                    out.flush()
                    os.fchmod(fd, 0o555 if member.mode & 0o111 else 0o444)
                    os.fsync(fd)
            finally:
                os.close(fd)


def public_cases(suite):
    """Scientific case directories only; never infer a slot from case body."""
    suite = Path(suite)
    base = suite / 'tests/count14'
    if not base.exists():
        return ()
    need(base.resolve() == base and base.is_dir(), 'DYNTEAM_TESTER_EXACT_PUBLIC_CASE_ROOT')
    result = []
    for slot_dir in sorted(base.iterdir(), key=lambda p: p.name):
        need(slot_dir.is_dir() and not slot_dir.is_symlink() and
             re.fullmatch(r'(?:[1-9]|1[0-4])', slot_dir.name),
             'DYNTEAM_TESTER_PUBLIC_CASE_REGISTERED_SLOT')
        for case in sorted(slot_dir.iterdir(), key=lambda p: p.name):
            need(case.is_dir() and not case.is_symlink() and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+-]{0,127}', case.name) and
                 (case / 'cmd').is_file() and not (case / 'cmd').is_symlink(),
                 'DYNTEAM_TESTER_PUBLIC_CASE_CMD_STDIN_FILES_ABI')
            result.append((int(slot_dir.name), case.name, case))
    return tuple(result)


def original_formal_tester_run(core, trajectory, source_task_ports, *, pbench_tester_source):
    """Construct/configure original tester against only the NEW native env."""
    need(trajectory in core.rows and core.rows[trajectory]['arm'] in ('DYNTEAM', 'DYNTEAM_RACING') and
         source_task_ports is getattr(core, 'source_task_ports', None) and source_task_ports.core is core and
         source_task_ports.rows[trajectory]['state'] == 'SOURCE_TASK_CHANNEL_READY' and
         trajectory in core.gate.startup_held and not core.ledger.mutex._is_owned(),
         'DYNTEAM_FORMAL_TESTER_EXACT_SAME_HELD_CORE_AND_TASK')
    host = core.native_host_environment['trajectories'][trajectory]
    layout = core.native_layout.current(trajectory)
    source = Path(pbench_tester_source)
    need(source.parent.parent == Path(host['project_root']),
         'DYNTEAM_FORMAL_TESTER_ORIGINAL_PROJECT_ROOT')
    env = Path(host['envfile'])
    status = env.lstat()
    need(env.resolve() == env and stat.S_ISREG(status.st_mode) and status.st_uid == os.geteuid() and
         status.st_nlink == 1 and stat.S_IMODE(status.st_mode) == 0o400 and status.st_size <= 65536,
         'DYNTEAM_FORMAL_TESTER_ONLY_NEW_NATIVE_ENV')
    configuration = dict(line.split('=', 1) for line in env.read_text().splitlines() if line and not line.startswith('#'))
    docker = core.native_containers.docker
    docker.verify_daemon()
    namespace = original_tester_namespace(source, configuration=configuration, docker_argv=docker.argv())
    run = namespace['TesterRun'](host['profile'])
    need(run.data == Path(layout['profile_root']) and run.org == layout['org'] and len(run.workers) == 32 and
         run.testers == native_tester_names(core.rows[trajectory]['arm'], layout['org']) and
         run.tester == layout['org'] + '-tester1' and
         configuration['AGENT_IMAGE'] == host['image_ids']['agent'] and
         not (run.inbox / '0000').exists() and not (run.data / 'control/run.json').exists(),
         'DYNTEAM_FORMAL_TESTER_ORIGINAL_CATALOGUE_NEW_ASSIGNMENT_NO_REPLAY')
    channel = source_task_ports.ports['STATE'][trajectory]
    ready = strict((channel['layout'] / 'ORIGINAL_PRIVATE_TASK_CHANNEL_READY.json').read_bytes())
    run.configure(int(time.time() * 1000), TOKEN_CONTROLLED_WALL_SENTINEL_SECONDS,
                  mm_team_id=ready['team_id'], task_channel_id=ready['channel_id'])
    return run


class FormalCount14Tester:
    """Serial host writer scheduled by the SAME original owner's poll loop.

    No independent model dispatcher/timer or original TesterRun.run thread is
    started. release0 is synchronous while native model gates are held. Periodic
    exports run on one retained scientific-host thread, outside all ledger/
    membership locks, at 1800 ACTIVE seconds. Global COMMITTED is intentionally
    NOT a gate on scientific periodic Git exports; exact commit+archive is.

    Writer integration is MANDATORY: checkpoint_hold atomically prevents a new
    host export and reports whether the current one and its native public tool
    processes have physically drained; capture_roots includes host-only main
    archives/suites/reports, not just Docker-mounted input. Parent may freeze/
    capture only after this returns True. It must resume_after_cut on release.
    """
    def __init__(self, core, trajectory, run, *, active_now, public_execution):
        need(trajectory in core.rows and core.rows[trajectory]['arm'] in ('DYNTEAM', 'DYNTEAM_RACING') and
             trajectory in core.gate.startup_held and callable(active_now) and
             type(public_execution) is TesterPublicExecution and
             run.data.is_relative_to(Path(core.rows[trajectory]['root'])) and
             run.inbox == run.data / 'tester/input' / run.tester,
             'DYNTEAM_FORMAL_TESTER_NEW_NATIVE_SCOPE_AND_TYPED_PUBLIC_EXECUTION')
        self.core, self.t, self.run = core, trajectory, run
        self.active_now, self.execution = active_now, public_execution
        self.control = Path(core.rows[trajectory]['root']) / 'formal-tester-control'
        self.control.mkdir(mode=0o700)
        self.lock = threading.Lock()
        self.hold, self.busy, self.closed = True, False, False
        self.thread = None
        self.state = 'BOUND_NOT_PREPARED'
        self.next_number = 0
        self.start_active = None
        self.task_view = None
        self.last = None

    def _outside_locks(self):
        need(not self.core.ledger.mutex._is_owned(),
             'DYNTEAM_FORMAL_TESTER_WAIT_FORBIDDEN_UNDER_LEDGER_LOCK')

    def prepare(self):
        self._outside_locks()
        need(self.state == 'BOUND_NOT_PREPARED' and self.t in self.core.gate.startup_held,
             'DYNTEAM_FORMAL_TESTER_PREPARE_ONCE_WHILE_MODELS_HELD')
        self.state = 'INITIAL_EXPORT_PARTIAL_RETAINED'
        if not self.run.inbox.exists():
            self.run.inbox.mkdir(mode=0o755, parents=True)
            self.run.inbox.chmod(0o755)
        need(self.run.inbox.resolve() == self.run.inbox and not (self.run.inbox / '0000').exists(),
             'DYNTEAM_FORMAL_TESTER_NO_INITIAL_REPLAY')
        # These are generated NEW-root framework input/publication directories,
        # not scientific payloads. Docker binds these exact leaves read-only.
        # Existing initial scaffolds are allowed only before the first release.
        for path in (self.run.inbox, self.run.directory / 'suites', self.run.directory / 'reports'):
            path.mkdir(mode=0o755, parents=True, exist_ok=True)
            need(path.resolve() == path and path.is_dir() and not path.is_symlink() and
                 path.stat().st_uid == os.geteuid(),
                 'DYNTEAM_FORMAL_TESTER_NEW_OWNED_PUBLICATION_SCAFFOLD')
            path.chmod(0o755)
        self.task_view = approved_task_export(self.core, self.t, self.run.inbox / 'approved-input')
        self._release(0)
        self.next_number = 1
        self.state = 'TASK_AWARE_NATIVE_CYCLE0_READY_MODELS_HELD'
        return self.public()

    def start(self):
        need(self.state == 'TASK_AWARE_NATIVE_CYCLE0_READY_MODELS_HELD' and
             self.t not in self.core.gate.startup_held and self.start_active is None,
             'DYNTEAM_FORMAL_TESTER_ONLY_ORIGINAL_ACTIVATION_STARTS_CADENCE')
        now = self.active_now()
        need(type(now) in (int, float) and math.isfinite(now), 'DYNTEAM_FORMAL_TESTER_FINITE_ACTIVE_CLOCK')
        with self.lock:
            self.start_active, self.hold = now, False
            self.state = 'PERIODIC_NATIVE_TESTER_RUNNING'

    def _release(self, number):
        self._outside_locks()
        need(type(number) is int and number >= 0 and type(self.task_view) is ApprovedTaskView,
             'DYNTEAM_FORMAL_TESTER_TYPED_SAME_TASK_VIEW')
        directory = self.run.inbox / f'{number:04d}'
        need(not directory.exists() and not directory.is_symlink(),
             'DYNTEAM_FORMAL_TESTER_CYCLE_NEVER_REPLAY_OR_DELETE')
        _readable_directory(directory)
        append(self.control / f'CYCLE_{number:04d}_INTENT_PUBLIC.json', dict(
            schema='count14-formal-native-tester-cycle-intent-v1', trajectory=self.t, number=number,
            automatic_retry=False, original_native_event_id=f'tester-cycle:{self.run.tester}:{number}',
            global_committed_gate_required=False, model_calls_by_host=0))
        main_sha = None
        if number:
            # Native archive first selects immutable refs/heads/main commit,
            # then Git-archives exactly that commit. Not a checkpoint snapshot,
            # and deliberately NOT gated on global checkpoint COMMITTED.
            full = self.run.main_archive(number)
            need(not full.exists(), 'DYNTEAM_FORMAL_TESTER_CURRENT_MAIN_ARCHIVE_ONCE')
            main_sha = self.run.archive(self.run.org, self.run.config.get('REPO', 'main'), full)
            need(re.fullmatch('[0-9a-f]{40}', main_sha) is not None,
                 'DYNTEAM_FORMAL_TESTER_IMMUTABLE_CURRENT_MAIN_COMMIT')
            shutil.copyfile(full, directory / 'main.tar.gz')
            (directory / 'main.tar.gz').chmod(0o444)
        suite_sha = self.run.archive(self.run.tester, 'tests', directory / 'suite.tar.gz')
        need(re.fullmatch('[0-9a-f]{40}', suite_sha) is not None,
             'DYNTEAM_FORMAL_TESTER_IMMUTABLE_PRIVATE_TESTS_COMMIT')
        (directory / 'suite.tar.gz').chmod(0o444)
        _safe_suite_extract(directory / 'suite.tar.gz', directory / 'suite')
        release = dict(number=number, tester=self.run.tester, main_sha=main_sha, suite_sha=suite_sha,
            captured_at_ms=int(time.time() * 1000), count14_task_aware=True,
            approved_task_sha256=self.task_view.task_sha256,
            approved_source_commit=self.task_view.bootstrap_commit, private_reference_used=False)
        append(directory / 'release.json', release)
        (directory / 'release.json').chmod(0o444)
        cases = public_cases(directory / 'suite')
        if number:
            self._share_suite(directory, release)
        header = (COUNT14_TESTER_DIRECTIVE + '\n'
            f'Approved task file: /opt/tester-input/approved-input/task-description.bin\n'
            f'Approved source archive: /opt/tester-input/approved-input/source.tar.gz\n'
            f'Approved bootstrap commit: {self.task_view.bootstrap_commit}\n'
            f'Current-main exact commit: {main_sha or "initial approved bootstrap"}\n' +
            (f'Current-main archive: /opt/tester-input/{number:04d}/main.tar.gz\n' if number else '') +
            f'Frozen prior test suite: /opt/tester-input/{number:04d}/suite\n' +
            '\nBEGIN UNCHANGED APPROVED TASK\n').encode('utf-8')
        task = self.task_view.task_path.read_bytes()
        need(hash_file(self.task_view.task_path)['sha256'] == self.task_view.task_sha256 and
             hash_file(self.task_view.source_archive)['sha256'] == self.task_view.source_archive_sha256,
             'DYNTEAM_FORMAL_TESTER_INPUT_VIEW_UNCHANGED')
        prompt = header + task + b'\nEND UNCHANGED APPROVED TASK\n'
        prompt.decode('utf-8')  # original event API is UTF-8 text, no lossy rewrite.
        fd = os.open(directory / 'interval-prompt.md', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as out:
            out.write(prompt)
            out.flush()
            os.fchmod(out.fileno(), 0o444)
            os.fsync(out.fileno())
        # Preserve EXACT native cycle event ID/kind and ordering. Original
        # publish has original collaboration-message delivery semantics; this
        # wrapper never repeats the cycle if its transport acceptance is unknown.
        if number:
            self.run.publish(f'tester-cycle:{self.run.tester}:{number}', [self.run.tester],
                             'tester_cycle', prompt.decode('utf-8').rstrip('\n'), release)
        latest = directory.parent / 'latest'
        temporary = latest.with_name('latest.tmp')
        need(not temporary.exists() and not temporary.is_symlink(),
             'DYNTEAM_FORMAL_TESTER_LATEST_NO_OTHER_WRITER')
        temporary.symlink_to(directory.name, target_is_directory=True)
        temporary.replace(latest)
        if not number:
            self.run.publish(f'tester-cycle:{self.run.tester}:{number}', [self.run.tester],
                             'tester_cycle', prompt.decode('utf-8').rstrip('\n'), release)
        if number:
            if cases:
                self._notify_public_suite(release)
            observations = self.execution.evaluate(number, cases)
            report = self.run.directory / 'reports' / self.run.tester / f'{number:04d}'
            report.mkdir(mode=0o755, parents=True)
            report.parent.chmod(0o755)
            report.chmod(0o755)
            append(report / 'public-observations.json', observations)
            (report / 'public-observations.json').chmod(0o444)
            self._notify_public_result(release, observations)
        append(self.control / f'CYCLE_{number:04d}_READY_PUBLIC.json', dict(
            schema='count14-formal-native-tester-cycle-ready-v1', trajectory=self.t, number=number,
            main_commit=main_sha, suite_commit=suite_sha, cases=len(cases),
            source_task_view_receipt_sha256=self.task_view.receipt_sha256,
            archive_before_event=True, original_event_latest_order=True,
            global_committed_gate_required=False, official_verdict=False, model_calls_by_host=0))
        self.last = dict(number=number, case_count=len(cases), main_commit=main_sha, suite_commit=suite_sha)
        return release

    def _share_suite(self, directory, release):
        parent = self.run.directory / 'suites' / self.run.tester
        parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        parent.chmod(0o755)
        shared = parent / f'{release["number"]:04d}'
        need(not shared.exists(), 'DYNTEAM_FORMAL_TESTER_PUBLIC_SUITE_SHARE_ONCE')
        temporary_share = directory / 'count14-share.partial'
        need(not temporary_share.exists(), 'DYNTEAM_FORMAL_TESTER_NEW_ATOMIC_SUITE_SHARE')
        _readable_directory(temporary_share)
        shutil.copytree(directory / 'suite', temporary_share / 'suite', symlinks=False)
        shutil.copyfile(directory / 'suite.tar.gz', temporary_share / 'suite.tar.gz')
        (temporary_share / 'suite.tar.gz').chmod(0o444)
        append(temporary_share / 'release.json', release)
        (temporary_share / 'release.json').chmod(0o444)
        # Original all-bytes-before-publication property, without its rmtree
        # retry branch. A failed partial remains under this cycle's custody.
        temporary_share.rename(shared)
        latest = parent / 'latest'
        temporary = parent / 'latest.tmp'
        need(not temporary.exists() and not temporary.is_symlink(),
             'DYNTEAM_FORMAL_TESTER_SHARE_NO_OTHER_WRITER')
        temporary.symlink_to(shared.name, target_is_directory=True)
        temporary.replace(latest)

    def _notify_public_suite(self, release):
        number = release['number']
        path = f'/opt/test-suites/{self.run.tester}/{number:04d}/suite'
        summary = (f'Count14 tester {self.run.tester}, release {number}: genuine public assertion cases and fixtures at {path}; '
                   f'case ABI={PUBLIC_CASE_ABI}. main={release["main_sha"]}; suite={release["suite_sha"]}. '
                   'Use only original public task tools and an explicit per-slot /work program binding. '
                   'Public pass/failure observations are NOT official count14 verdicts. No reference binary is available.')
        self.run.publish(f'test-suite:{self.run.tester}:{number}', self.run.workers, 'test_suite', summary,
                         dict(release, suite_path=path, official_verdict=False))

    def _notify_public_result(self, release, observations):
        number = release['number']
        path = f'/opt/test-reports/{self.run.tester}/{number:04d}/public-observations.json'
        summary = (f'Count14 public tester observations for release {number}: '
                   f'total={observations["total"]}, valid={observations["valid"]}, '
                   f'reproduced_public_failures={observations["reproduced_public_failures"]}. '
                   f'Scientific report: {path}. Invalid/unbound cases are not passes; this is NOT an official count14 verdict.')
        self.run.publish(f'test-report:{self.run.tester}:{number}', self.run.workers, 'test_report', summary,
                         dict(release, report_path=path, official_verdict=False))

    def poll(self):
        self._outside_locks()
        now = self.active_now()  # callbacks/ledger access NEVER under our lock
        need(type(now) in (int, float) and math.isfinite(now), 'DYNTEAM_FORMAL_TESTER_FINITE_ACTIVE_CLOCK')
        with self.lock:
            if self.closed or self.hold or self.busy or self.state != 'PERIODIC_NATIVE_TESTER_RUNNING':
                return self.public_unlocked()
            number = self.next_number
            need(self.start_active is not None, 'DYNTEAM_FORMAL_TESTER_ACTIVATED_CADENCE_CLOCK')
            if now < self.start_active + number * CADENCE_ACTIVE_SECONDS:
                return self.public_unlocked()
            self.busy = True
            self.state = 'PERIODIC_EXPORT_IN_PROGRESS_RETAIN_CUSTODY'
            thread = threading.Thread(target=self._perform_cycle, args=(number,),
                                      name='count14-native-formal-tester-export', daemon=False)
            self.thread = thread
        # No scientific, ledger, or own control lock is held during work/start.
        try:
            thread.start()
        except BaseException:
            with self.lock:
                self.state = 'CYCLE_PARTIAL_RETAINED_NO_RETRY'
                self.busy = False
            raise
        return self.public()

    def _perform_cycle(self, number):
        try:
            self._release(number)
            with self.lock:
                self.next_number += 1
                self.state = 'PERIODIC_NATIVE_TESTER_RUNNING'
        except BaseException as error:
            # Narrow public exception type only; no message, locals or body.
            try:
                append(self.control / f'CYCLE_{number:04d}_FAILED_PUBLIC.json', dict(
                    schema='count14-formal-native-tester-failure-v1', trajectory=self.t, number=number,
                    exception_type=type(error).__name__, no_retry=True, all_prefixes_retained=True))
            except BaseException:
                # Metadata I/O failure still retains custody; no default thread
                # traceback/error message and no retry of scientific work.
                pass
            with self.lock:
                self.state = 'CYCLE_PARTIAL_RETAINED_NO_RETRY'
        finally:
            with self.lock:
                self.busy = False

    def physical_clear(self):
        with self.lock:
            busy = self.busy
            partial = self.state in ('INITIAL_EXPORT_PARTIAL_RETAINED', 'CYCLE_PARTIAL_RETAINED_NO_RETRY')
            thread = self.thread
        return not busy and not partial and (thread is None or not thread.is_alive()) and self.execution.physical_clear()

    def checkpoint_hold(self):
        self._outside_locks()
        with self.lock:
            self.hold = True
        return self.physical_clear()

    def capture_roots(self):
        self._outside_locks()
        need(self.hold and self.physical_clear(),
             'DYNTEAM_FORMAL_TESTER_HOST_WRITER_MUST_DRAIN_BEFORE_CAPTURE')
        roots = [self.run.directory, self.control]
        public_exec = Path(self.core.rows[self.t]['root']) / 'tester-public-exec-private'
        if public_exec.exists():
            roots.append(public_exec)
        need(all(p.resolve() == p and p.is_dir() and p.is_relative_to(Path(self.core.rows[self.t]['root'])) for p in roots),
             'DYNTEAM_FORMAL_TESTER_CAPTURE_EXACT_NEW_ROOT_ONLY')
        return tuple(roots)

    def resume_after_cut(self):
        self._outside_locks()
        need(not self.closed and self.physical_clear(), 'DYNTEAM_FORMAL_TESTER_RESUME_SAME_RETAINED_WRITER')
        with self.lock:
            self.hold = False

    def close_admission(self):
        self._outside_locks()
        with self.lock:
            self.hold, self.closed = True, True
        # Natural drain only; no thread cancellation, process kill or rmtree.
        return self.physical_clear()

    def public_unlocked(self):
        return dict(schema='count14-formal-native-tester-public-v1', trajectory=self.t, state=self.state,
            hold=self.hold, busy=self.busy, closed=self.closed, next_number=self.next_number,
            cadence_active_seconds=CADENCE_ACTIVE_SECONDS, last=self.last,
            same_approved_task=self.task_view is not None, periodic_current_main_archive=True,
            public_execution_bound_slots=sorted(self.execution.ports),
            global_committed_gate_required=False, original_tester_run_started=False,
            private_reference_or_official_evaluator_access=False, model_calls_by_host=0)

    def public(self):
        with self.lock:
            return self.public_unlocked()
