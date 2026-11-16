"""Read-only proof for an original removed cgroup2 leaf, never PID inference.

kernfs can retain directory nlink=2 after removal. Require the exact retained
inode/FD, same live cgroup2 mount, Docker CID path, kernel d_unlinked rendering,
and both original path and cgroup.events ENOENT. Never create/remove a domain,
read task bodies, change processes, signal, or manufacture a live census.
"""
import errno
import os
from pathlib import Path
import re
import stat


def _mount_id(fd):
    raw = Path('/proc/self/fdinfo', str(fd)).read_text()
    values = {}
    for line in raw.splitlines():
        if line.startswith(('mnt_id:', 'ino:')):
            key, value = line.split(':', 1)
            if key in values or not value.strip().isdigit():
                return None
            values[key] = int(value.strip())
    return values.get('mnt_id')


def exact_removed_cgroup2_leaf(domain, *, container_id):
    """False on drift/unknown. Does NOT discharge peer/archive/model custody."""
    if not (type(container_id) is str and re.fullmatch('[0-9a-f]{64}', container_id)):
        return False
    fd = domain.fd
    relative = Path(domain.relative)
    if (type(fd) is not int or fd < 0 or not relative.is_absolute()
            or '..' in relative.parts or relative.name != 'docker-' + container_id + '.scope'):
        return False
    root = Path('/sys/fs/cgroup')
    original = root / relative.relative_to('/')
    root_fd = None
    try:
        before = os.fstat(fd)
        if (not stat.S_ISDIR(before.st_mode) or before.st_nlink != 2
                or (before.st_dev, before.st_ino) != domain.inode):
            return False
        if root.resolve() != root or root.is_symlink():
            return False
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        root_before = os.fstat(root_fd)
        mount = _mount_id(fd)
        if mount is None or mount != _mount_id(root_fd) or before.st_dev != root_before.st_dev:
            return False
        matches = []
        for line in Path('/proc/self/mountinfo').read_text().splitlines():
            left, separator, right = line.partition(' - ')
            if not separator:
                return False
            fields, filesystem = left.split(), right.split()
            if len(fields) >= 6 and fields[0] == str(mount):
                matches.append((fields, filesystem))
        if not (len(matches) == 1 and len(matches[0][1]) >= 3
                and matches[0][0][3:5] == ['/', str(root)]
                and matches[0][1][0] == 'cgroup2'):
            return False
        magic_link = Path('/proc/self/fd', str(fd))
        expected = str(original) + ' (deleted)'
        if os.readlink(magic_link) != expected:
            return False
        # A literal filename ending " (deleted)" cannot impersonate the CID
        # pathname: relative's basename was checked above, and the original
        # pathname must actually be absent on the very same mounted hierarchy.
        try:
            original.lstat()
        except OSError as error:
            if error.errno != errno.ENOENT:
                return False
        else:
            return False
        try:
            events = os.open('cgroup.events', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        except OSError as error:
            if error.errno != errno.ENOENT:
                return False
        else:
            os.close(events)
            return False
        after = os.fstat(fd)
        root_after = os.fstat(root_fd)
        identity = lambda value: (value.st_dev, value.st_ino, value.st_mode,
                                  value.st_uid, value.st_gid, value.st_nlink)
        return (identity(before) == identity(after)
                and identity(root_before) == identity(root_after)
                and _mount_id(fd) == _mount_id(root_fd) == mount
                and os.readlink(magic_link) == expected)
    except (OSError, ValueError, TypeError, AttributeError):
        return False
    finally:
        if root_fd is not None:
            os.close(root_fd)
