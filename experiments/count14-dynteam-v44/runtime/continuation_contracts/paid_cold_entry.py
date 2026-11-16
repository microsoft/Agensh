#!/usr/bin/env python3
"""DEDICATED paid-custody entry; never call the original fresh-entry main/EOF.

Only STATUS/POLL metadata are available. EOF ALWAYS retains the stopped-owner
handoff's real custody locks; no zero-unused close or fresh bootstrap exists.
Whole-owner runtime restoration and permission to create a cold boundary are
not supplied by this first implementation.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import select
import stat
import sys
import time

RETAINED_OWNER = None
CODE_SCHEMA = 'count14-paid-cold-dedicated-entry-source-v1'
SOURCES = {'paid_cold_material.py','paid_cold_attach.py','paid_cold_owner.py','paid_cold_entry.py',
           'test_paid_cold_custody_OWN.py','qualify_paid_cold_custody.py'}


def load_code(manifest_path, manifest_sha256):
    path = Path(manifest_path)
    s = path.lstat()
    if not (path.is_absolute() and path.resolve() == path and not path.is_symlink() and
            stat.S_ISREG(s.st_mode) and not s.st_mode & 0o022 and s.st_uid in (0, os.geteuid()) and
            s.st_size <= 16*1024*1024):
        raise ValueError('PAID_COLD_ENTRY_EXACT_PUBLIC_SOURCE_MANIFEST')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest_sha256:
        raise ValueError('PAID_COLD_ENTRY_PUBLIC_SOURCE_MANIFEST_PIN')
    value = json.loads(raw)
    if (value.get('schema') != CODE_SCHEMA or value.get('entry') != 'restore_paid_custody_owner'
            or set(value.get('files', {})) != SOURCES):
        raise ValueError('PAID_COLD_ENTRY_NOT_ORIGINAL_FRESH_FACTORY_SCHEMA')
    root = Path(value['code_root'])
    if root.resolve() != root or root != Path(__file__).resolve().parent:
        raise ValueError('PAID_COLD_ENTRY_DEDICATED_SOURCE_ROOT_ONLY')
    for name, pin in value['files'].items():
        p = root/name
        s = p.lstat()
        if not (p.parent == root and p.resolve() == p and not p.is_symlink() and
                stat.S_ISREG(s.st_mode) and not s.st_mode & 0o022 and s.st_uid in (0, os.geteuid()) and
                hashlib.sha256(p.read_bytes()).hexdigest() == pin):
            raise ValueError('PAID_COLD_ENTRY_EXACT_SOURCE_FILE_PIN')
    registry = value['framework_import_registry']
    rp = Path(registry['path'])
    rraw = rp.read_bytes()
    if hashlib.sha256(rraw).hexdigest() != registry['sha256']:
        raise ValueError('PAID_COLD_ENTRY_CURRENT_FRAMEWORK_IMPORT_REGISTRY_PIN')
    inherited = json.loads(rraw)
    if inherited['schema'] != 'count14-dynteam-framework-import-pins-v1':
        raise ValueError('PAID_COLD_ENTRY_FRAMEWORK_IMPORT_SCHEMA')
    for row in inherited['roots']:
        directory = Path(row['path'])
        if directory.resolve() != directory:
            raise ValueError('PAID_COLD_ENTRY_CANONICAL_FRAMEWORK_ROOT')
        for name, pin in row['files'].items():
            p = directory/name
            if p.resolve() != p or p.is_symlink() or not p.is_relative_to(directory) or hashlib.sha256(p.read_bytes()).hexdigest() != pin:
                raise ValueError('PAID_COLD_ENTRY_INHERITED_FRAMEWORK_SOURCE_PIN')
    sys.path[:0] = [str(root)] + [r['path'] for r in inherited['roots']]
    from paid_cold_owner import restore_paid_custody_owner, verify_original_sources
    verify_original_sources()
    return restore_paid_custody_owner


def emit(value):
    print(json.dumps(value, sort_keys=True), flush=True)


def main(argv=None):
    global RETAINED_OWNER
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--code-manifest', required=True)
    p.add_argument('--code-manifest-sha256', required=True)
    p.add_argument('--verify-code-only', action='store_true')
    p.add_argument('--protected-handoff')
    p.add_argument('--protected-handoff-sha256')
    a = p.parse_args(argv)
    try:
        restore = load_code(a.code_manifest, a.code_manifest_sha256)
        if a.verify_code_only:
            if a.protected_handoff or a.protected_handoff_sha256:
                raise ValueError('PAID_COLD_ENTRY_CODE_VERIFY_HAS_NO_RESTORE_INPUT')
            emit(dict(PASS=True, original_classes_imported=True, restore_called=False,
                original_fresh_entry_EOF_used=False, isolated=bool(sys.flags.isolated), models=0))
            return 0
        if not (a.protected_handoff and a.protected_handoff_sha256):
            raise ValueError('PAID_COLD_ENTRY_EXPLICIT_PROTECTED_HANDOFF_REQUIRED')
        owner = restore(a.protected_handoff, a.protected_handoff_sha256)
        from native_cold_owner import NativeColdOwner
        if type(owner) is not NativeColdOwner or RETAINED_OWNER is not None:
            raise ValueError('PAID_COLD_ENTRY_ONE_EXACT_TYPED_OWNER')
        RETAINED_OWNER = owner
        emit(owner.public())
        # No original fresh command dispatcher is imported or called. In this
        # HELD first layer, poll is metadata-only and cannot activate/resume.
        fd = sys.stdin.fileno()
        os.set_blocking(fd, False)
        buf = bytearray()
        while True:
            ready, _, _ = select.select([fd], [], [], .25)
            if ready:
                chunk = os.read(fd, 4097)
                if not chunk:
                    emit(dict(PAID_COLD_CONTROL_EOF_CUSTODY_RETAINED=True, runtime_ready=False))
                    while True:
                        time.sleep(1) # retained original FDs, no automatic close/stop/restart
                buf.extend(chunk)
                if len(buf) > 4096:
                    raise ValueError('PAID_COLD_ENTRY_CONTROL_BOUND')
                while b'\n' in buf:
                    line, _, tail = buf.partition(b'\n')
                    buf = bytearray(tail)
                    row = json.loads(line)
                    if row not in ({'op':'STATUS'}, {'op':'POLL'}):
                        raise ValueError('PAID_COLD_ENTRY_RUNTIME_OPERATION_NOT_IMPLEMENTED')
                    emit(owner.poll())
    except Exception as error:
        try:
            emit(dict(PUBLIC_code='PAID_COLD_ENTRY_HELD_PARTIAL_NO_RETRY', exception_type=type(error).__name__,
                      owner_retained=RETAINED_OWNER is not None, models=0, runtime_ready=False))
        except Exception:
            pass # broken PUBLIC pipe never abandons attached custody
        if RETAINED_OWNER is not None:
            while True:
                time.sleep(1)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
