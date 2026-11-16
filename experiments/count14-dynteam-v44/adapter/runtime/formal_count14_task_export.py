"""Trusted-scientific runtime export of the SAME approved count14 input.

This module is not a coordinator inspection port. Only the scientific owner
may execute it against real inputs; offline tests use freshly generated OWN
inputs. It copies task bytes without decoding/rephrasing them and exports the
exact immutable bootstrap commit, never a working tree or a private reference.
The new leaf can be mounted read-only in tester/racing helper containers: the
task's original root:0400 file is NOT bind-mounted as an unreadable placeholder.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import os
import re
import stat
import subprocess

from common import need, digest, hash_file, regular_fd, stamp, strict
from native_system_probe_child import append


@dataclass(frozen=True)
class ApprovedTaskView:
    trajectory: str
    directory: Path
    task_path: Path
    source_archive: Path
    task_sha256: str
    source_bundle_sha256: str
    source_archive_sha256: str
    bootstrap_commit: str
    bootstrap_tree: str
    receipt_sha256: str

    def public(self):
        return dict(schema='count14-formal-approved-helper-input-v1',
            trajectory=self.trajectory, directory=str(self.directory), task_path=str(self.task_path),
            source_archive=str(self.source_archive), task_sha256=self.task_sha256,
            source_bundle_sha256=self.source_bundle_sha256,
            source_archive_sha256=self.source_archive_sha256,
            bootstrap_commit=self.bootstrap_commit, bootstrap_tree=self.bootstrap_tree,
            receipt_sha256=self.receipt_sha256, task_bytes_unchanged=True,
            input_leaf_uid10000_readable=True, official_or_reference_access=False)


def _new_readable_copy(source, destination, expected_sha256):
    """Byte-for-byte separate inode; no old file permissions are changed."""
    source, destination = Path(source), Path(destination)
    need(source.is_absolute() and source.resolve() == source,
         'DYNTEAM_HELPER_APPROVED_TASK_CANONICAL')
    with regular_fd(source) as incoming:
        before = os.fstat(incoming)
        need(before.st_nlink == 1 and before.st_uid in (0, os.geteuid()) and
             stat.S_IMODE(before.st_mode) == 0o400,
             'DYNTEAM_HELPER_ONLY_ORIGINAL_APPROVED_TASK_FILE')
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            h = hashlib.sha256()
            for block in iter(lambda: os.read(incoming, 1024 * 1024), b''):
                h.update(block)
                view = memoryview(block)
                while view:
                    wrote = os.write(fd, view)
                    need(wrote > 0, 'DYNTEAM_HELPER_TASK_COPY_PROGRESS')
                    view = view[wrote:]
            need(stamp(before) == stamp(os.fstat(incoming)) == stamp(source.lstat()) and
                 h.hexdigest() == expected_sha256,
                 'DYNTEAM_HELPER_SAME_TASK_BYTES_AND_PIN')
            os.fchmod(fd, 0o444)
            os.fsync(fd)
        finally:
            os.close(fd)
    need(destination.stat().st_ino != before.st_ino and
         stat.S_IMODE(destination.stat().st_mode) == 0o444,
         'DYNTEAM_HELPER_TASK_NEW_READABLE_INODE')


def approved_task_export(core, trajectory, destination):
    """Prepare one NEW exact-scope read-only task/source view, before models.

    No candidate/checkpoint gate: this is immutable initial source. The caller
    owns/retains this host-writer operation and must not run it under ledger or
    scientific-object locks. On any failure, retain the partial leaf and report
    it; this function never retries, removes it or rewrites an existing export.
    ROOT may mount the *same* resulting leaf in RACING helpers without granting
    those helpers the org/main ACL or a Mattermost identity.
    """
    need(trajectory in core.rows and core.rows[trajectory]['arm'] in ('DYNTEAM', 'DYNTEAM_RACING') and
         trajectory in core.gate.startup_held and not core.ledger.mutex._is_owned(),
         'DYNTEAM_HELPER_INPUT_SAME_HELD_OWNER_OUTSIDE_LEDGER_LOCK')
    root = Path(core.rows[trajectory]['root'])
    destination = Path(destination)
    record = core.source_bootstraps[trajectory]
    receipt = record['receipt']
    source_root = Path(receipt['source_root'])
    need(record['state'] == 'SOURCE_ONLY_READY' and receipt['trajectory'] == trajectory and
         receipt['contract_sha256'] == digest(core.contract) and
         source_root == root / 'source-bootstrap' and source_root.resolve() == source_root and
         destination.is_absolute() and destination.is_relative_to(root) and
         destination.parent.resolve() == destination.parent and
         not destination.exists() and not destination.is_symlink(),
         'DYNTEAM_HELPER_INPUT_ONLY_NEW_EXACT_SOURCE_SCOPE')
    protocol = core.contract['v2_baseline_reference_protocol']
    original = strict((source_root / 'bootstrap-receipt.json').read_bytes())
    need(original.get('schema') == 'count14-agensh-bootstrap-v1' and original['roles'] == [] and
         original['source_sha256'] == receipt['source_sha256'] == protocol['source_bundle'] and
         original['task_description_sha256'] == receipt['task_description_sha256'] == protocol['task_description'] and
         original['bootstrap_commit'] == receipt['bootstrap_commit'] and
         original['bootstrap_tree'] == receipt['bootstrap_tree'] and
         all(re.fullmatch('[0-9a-f]{40}', original[k]) for k in ('bootstrap_commit', 'bootstrap_tree')),
         'DYNTEAM_HELPER_INPUT_ORIGINAL_APPROVED_TASK_SOURCE_OBJECTS')
    repo = source_root / 'bootstrap.git'
    need(repo.resolve() == repo and repo.is_dir() and not repo.is_symlink(),
         'DYNTEAM_HELPER_IMMUTABLE_BOOTSTRAP_REPOSITORY_ONLY')
    destination.mkdir(mode=0o700)
    append(destination / 'EXPORT_INTENT_PUBLIC.json', dict(
        schema='count14-helper-input-export-intent-v1', trajectory=trajectory,
        contract_sha256=digest(core.contract), automatic_retry=False, model_calls=0))
    task = destination / 'task-description.bin'
    _new_readable_copy(source_root / 'task-description.bin', task, protocol['task_description'])
    # Exact immutable commit, not refs/heads/main after SEARCH has changed it.
    # Original trusted bootstrap Git primitive keeps its sandbox/environment/
    # hooks/timeout policy. No target project files are read by DEV here.
    from bootstrap import git
    objects = git(['--git-dir=' + str(repo), 'rev-parse', original['bootstrap_commit'],
                   original['bootstrap_commit'] + '^{tree}'], cwd=source_root).decode('ascii').splitlines()
    need(objects == [original['bootstrap_commit'], original['bootstrap_tree']],
         'DYNTEAM_HELPER_EXPORT_EXACT_BOOTSTRAP_OBJECTS')
    archive = destination / 'source.tar.gz'
    env = dict(PATH='/usr/bin:/bin', HOME=str(destination), LANG='C',
               GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', GIT_TERMINAL_PROMPT='0')
    fd = os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as out:
            # This is scientific input export, not a model or diagnostic job.
            # No timeout-kill/retry: the original exact owner retains the child
            # until its natural terminal; checkpoint custody includes this call.
            child = subprocess.Popen(['git', '-c', 'core.hooksPath=/dev/null',
                '-c', 'core.fsmonitor=false', '--git-dir=' + str(repo), 'archive',
                '--format=tar.gz', original['bootstrap_commit']], cwd=source_root, env=env,
                stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.DEVNULL)
            code = child.wait()
            need(code == 0, 'DYNTEAM_HELPER_BOOTSTRAP_ARCHIVE_FAILED_RETAIN_PARTIAL')
            out.flush()
            os.fchmod(fd, 0o444)
            os.fsync(fd)
    finally:
        os.close(fd)
    metadata = dict(schema='count14-helper-input-export-ready-v1', trajectory=trajectory,
        contract_sha256=digest(core.contract), task_sha256=hash_file(task)['sha256'],
        source_bundle_sha256=protocol['source_bundle'], source_archive=hash_file(archive),
        bootstrap_commit=original['bootstrap_commit'], bootstrap_tree=original['bootstrap_tree'],
        task_bytes_unchanged=True, input_files_mode=0o444, input_directory_mode=0o755,
        private_evaluator_or_history_imported=False, model_calls=0)
    need(metadata['task_sha256'] == protocol['task_description'], 'DYNTEAM_HELPER_TASK_EXPORT_FINAL_PIN')
    append(destination / 'EXPORT_READY_PUBLIC.json', metadata)
    # Bind this *leaf* as RO. Host root ancestors need not be made traversable.
    # All scientific assets in this dedicated new leaf are now UID10000-readable.
    destination.chmod(0o755)
    return ApprovedTaskView(trajectory, destination, task, archive, metadata['task_sha256'],
        protocol['source_bundle'], metadata['source_archive']['sha256'],
        original['bootstrap_commit'], original['bootstrap_tree'], digest(metadata))
