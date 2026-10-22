# Save per-boot worker state and verify it before profile data can be removed.
# A complete manifest records the sealed archive's size and SHA-256 digest.

import hashlib
import json
import os
from pathlib import Path
import sys
import tarfile
import time
import uuid


def _digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def _manifest(directory, **values):
    if directory.resolve() != directory:
        raise ValueError('manifest directory must not traverse symlinks')
    path = directory / 'manifest.json'
    if path.is_symlink():
        raise ValueError('manifest must not be a symlink')
    current = json.loads(path.read_text()) if path.exists() else {}
    current.update(values)
    temporary = directory / 'manifest.json.tmp'
    with temporary.open('w') as output:
        json.dump(current, output, indent=2)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())
    temporary.chmod(0o600)
    # Publish the manifest atomically and persist its directory entry.
    temporary.replace(path)
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def begin(state_root):
    parent = Path(state_root).absolute() / 'shutdown'
    if parent.resolve() != parent:
        raise ValueError('shutdown directory must not traverse symlinks')
    parent.mkdir(mode=0o700, exist_ok=True)
    parent.chmod(0o700)
    directory = parent / uuid.uuid4().hex
    directory.mkdir(mode=0o700)
    _manifest(directory, status='running', started_at=time.time())
    return directory


def save(directory, home, workspace):
    try:
        for path in (directory, home, workspace):
            if path.resolve() != path:
                raise ValueError('archive source/destination must not traverse symlinks')
        if directory.is_relative_to(home) or directory.is_relative_to(workspace):
            raise ValueError('archive must be outside saved state')
        temporary = directory / 'state.tar.gz.tmp'
        # Preserve links and the complete trees, including Git and ignored files.
        with tarfile.open(temporary, 'w:gz', dereference=False, compresslevel=1) as bundle:
            bundle.add(home, arcname='home')
            bundle.add(workspace, arcname='work')
        temporary.chmod(0o600)
        with temporary.open('rb') as stream:
            os.fsync(stream.fileno())
        archive = directory / 'state.tar.gz'
        temporary.replace(archive)
        # Completion is recorded only after the archive has been flushed and sealed.
        _manifest(directory, status='complete', finished_at=time.time(),
                  sha256=_digest(archive), bytes=archive.stat().st_size)
    except Exception as error:
        _manifest(directory, status='failed', error=type(error).__name__)
        raise


def check(data):
    agents = Path(data).absolute() / 'agents'
    failures = []
    if not agents.exists():
        return failures
    for agent in sorted(agents.iterdir()):
        if not agent.is_dir():
            continue
        try:
            if agent.resolve() != agent:
                raise ValueError('agent directory traverses a symlink')
            manifests = list((agent / 'shutdown').glob('*/manifest.json'))
            if not manifests:
                raise ValueError('missing worker shutdown manifest')
            # Validate every boot so an earlier incomplete archive prevents cleanup.
            for path in manifests:
                if path.resolve() != path:
                    raise ValueError('manifest traverses a symlink')
                manifest = json.loads(path.read_text())
                archive = path.parent / 'state.tar.gz'
                if manifest['status'] != 'complete' or archive.is_symlink():
                    raise ValueError('worker shutdown did not finish')
                if archive.stat().st_size != manifest['bytes'] or _digest(archive) != manifest['sha256']:
                    raise ValueError('archive size/checksum mismatch')
        except (OSError, ValueError, KeyError, TypeError) as error:
            failures.append(f'{agent.name}: {type(error).__name__}: {error}')
    return failures


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] != 'check':
        sys.exit('usage: archive.py check <profile-data-root>')
    failures = check(sys.argv[2])
    if failures:
        sys.stderr.write('Incomplete worker archives; preserve data for recovery:\n' + '\n'.join(failures) + '\n')
        sys.exit(1)
    print('Worker shutdown archives verified')
