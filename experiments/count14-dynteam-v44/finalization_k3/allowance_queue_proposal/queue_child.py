#!/usr/bin/env python3
"""Same formal child with private allowance native ports; no owner/model action."""
from pathlib import Path
import hashlib
import json
import os
import stat
import sys


def bootstrap():
    """Only stdlib before exact owner-generated PUBLIC framework source pins."""
    path = Path(os.environ['COUNT14_FORMAL_FINAL_IMPORTS_PUBLIC'])
    expected = os.environ['COUNT14_FORMAL_FINAL_IMPORTS_SHA256']
    if not (path.is_absolute() and path.resolve() == path and not path.is_symlink()):
        raise ValueError('SMOKE_CHILD_CANONICAL_IMPORT_MANIFEST')
    st = path.lstat()
    if not (stat.S_ISREG(st.st_mode) and st.st_uid in (0, os.geteuid()) and
            not st.st_mode & 0o022 and st.st_nlink == 1 and st.st_size <= 1024 * 1024):
        raise ValueError('SMOKE_CHILD_TRUSTED_IMPORT_MANIFEST')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('SMOKE_CHILD_IMPORT_MANIFEST_PIN')
    value = json.loads(raw)
    if not (type(value) is dict and set(value) == {'schema', 'roots'} and
            value['schema'] == 'count14-formal100m-final-frozen-imports-v1' and
            type(value['roots']) is list and value['roots']):
        raise ValueError('SMOKE_CHILD_EXACT_IMPORT_MANIFEST_SCHEMA')
    roots = []
    for row in value['roots']:
        if not (type(row) is dict and set(row) == {'path', 'files'} and
                type(row['files']) is dict and row['files']):
            raise ValueError('SMOKE_CHILD_EXACT_FRAMEWORK_SOURCE_ROOT')
        root = Path(row['path'])
        if not (root.is_absolute() and root.resolve() == root and root.is_dir() and
                not root.is_symlink() and root not in roots):
            raise ValueError('SMOKE_CHILD_CANONICAL_FRAMEWORK_SOURCE_ROOT')
        actual = {p.name for p in root.glob('*.py')}
        if actual != set(row['files']):
            raise ValueError('SMOKE_CHILD_FROZEN_FRAMEWORK_MODULE_SET')
        for name, pin in row['files'].items():
            p = root / name
            st = p.lstat()
            if not (p.parent == root and p.suffix == '.py' and p.resolve() == p and
                    stat.S_ISREG(st.st_mode) and st.st_uid in (0, os.geteuid()) and
                    st.st_gid in (0, os.getegid()) and not st.st_mode & 0o002 and
                    hashlib.sha256(p.read_bytes()).hexdigest() == pin):
                raise ValueError('SMOKE_CHILD_FROZEN_FRAMEWORK_MODULE_PIN')
        roots.append(root)
    sys.path[:0] = [str(root) for root in roots]
    return expected


def main():
    pin = bootstrap()
    # No ambient PYTHONPATH/cwd/script-dir dependency, even with python -I.
    from common import need, hash_file, strict, digest
    import run_native_final_child as original
    from smoke_checkpoint_final_scope import _bind_globals
    from formal_runtime import FormalFinalRuntimeScope as SmokeFinalRuntimeScope
    from smoke_checkpoint_final_runtime import load_profile_registry
    from queue_native import bind_scope, native_ports
    from queue_control import CarrierReader as FormalAllowanceReader
    reader = None
    if 'COUNT14_FORMAL_QUEUE_CONTROL_DOMAIN_PUBLIC' in os.environ:
        reader = FormalAllowanceReader(os.environ['COUNT14_FORMAL_QUEUE_CONTROL_DOMAIN_PUBLIC'],
                                       os.environ['COUNT14_FORMAL_QUEUE_CONTROL_DOMAIN_SHA256'])
    ports = native_ports(reader)
    if sys.argv[1:] == ['--verify-imports']:
        print(json.dumps({'schema': 'count14-formal100m-final-zero-model-import-v1',
            'PASS': True, 'isolated': bool(sys.flags.isolated), 'external_models': 0,
            'import_manifest_sha256': pin, 'original_child_imported': True,
            'original_runtime_imported': True}, sort_keys=True), flush=True)
        return 0

    def run(path, expected_sha256):
        # Original run repeats every private-config mode/link/hash/ready check.
        path = Path(path)
        need(path.is_absolute() and path.resolve() == path and
             hash_file(path)['sha256'] == expected_sha256, 'SMOKE_CHILD_EXACT_CONFIG_FOR_SCOPE')
        config = strict(path.read_bytes())
        contract = config['manifest']
        registry = load_profile_registry(os.environ['COUNT14_FORMAL_FINAL_PROFILE_PUBLIC'],
                                         os.environ['COUNT14_FORMAL_FINAL_PROFILE_SHA256'])
        scope = SmokeFinalRuntimeScope(contract, contract_sha256=digest(contract), profile_registry=registry)
        bind_scope(scope, reader)
        return _bind_globals(original.run, NativeFinalRuntime=scope.runtime, NativeImages=scope.images,
                             config_fields=ports.config_fields)(path, expected_sha256)

    return _bind_globals(original.main, run=run)()


def entry():
    try:return main()
    except BaseException as error:
        # Outer bootstrap/import/argument failure only. The original scientific
        # child's own failure handler remains unchanged inside original.main.
        kind = type(error).__name__
        if not (kind.isidentifier() and len(kind) <= 160):kind = 'Exception'
        frames = [];tb = error.__traceback__
        while tb is not None:
            frames.append({'file': tb.tb_frame.f_code.co_filename, 'line': tb.tb_lineno,
                           'function': tb.tb_frame.f_code.co_name})
            tb = tb.tb_next
        print(json.dumps({'schema': 'count14-formal100m-final-bootstrap-sanitized-failure-v1',
                          'exception_type': kind, 'frames': frames}, sort_keys=True),
              file=sys.stderr, flush=True)
        return 2


if __name__ == '__main__':
    sys.exit(entry())
