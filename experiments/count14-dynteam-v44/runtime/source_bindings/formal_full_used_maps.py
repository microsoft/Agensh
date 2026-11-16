"""Independent exact-source supplement over current approved maps, never edit them.

No OWN generated factory, template, runtime control or qualification receipt is
an execution/import-map input. main() reuses the already-passed two OWN only.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time

IMPORT_PIN = '403782ab70fa7f40bd58444b6e97251299dfcd43baa31f930c8268659f2718ee'
EXECUTION_PIN = '93010ea20d64d96815ed01b4c20abd1c53dc9b707a6f2724b531f49571cb41ac'
OWN_QUALIFICATION_PIN = 'a4c89d4b24f4ef63d11a545803617d91bce34e3a4974b508cf3260c413eacde4'
SOURCES = ('formal_full_used_cold.py', 'formal_full_used_domain.py', 'formal_full_used_emit.py',
           'formal_full_used_factory.py', 'formal_full_used_maps.py',
           'qualify_full_used_domain.py', 'test_full_used_domain_OWN.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(destination):
    from formal_public_factory import base_helper
    from formal_public_common import save
    root = Path(__file__).resolve().parent
    d = root.parent
    previous = d / 'formal100m-queue-approved-cold-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/maps-v2'
    guard = base_helper()
    imports = guard.public(previous / 'FRAMEWORK_IMPORT_PINS_PUBLIC.json', IMPORT_PIN, 8*1024*1024)
    guard.verify_framework_imports(previous / 'FRAMEWORK_IMPORT_PINS_PUBLIC.json', IMPORT_PIN, code_root=d)
    execution = guard.public(previous / 'FROZEN_FILES_PUBLIC.json', EXECUTION_PIN, 8*1024*1024)
    if set(p.name for p in root.glob('*.py')) != set(SOURCES):
        raise ValueError('FULL_USED_MAP_ONLY_EXACT_DECLARED_SEVEN_SOURCE_FILES')
    files = {}
    for name in SOURCES:
        path = root / name
        if path.resolve() != path or path.is_symlink() or not path.is_file():
            raise ValueError('FULL_USED_MAP_CANONICAL_DECLARED_SOURCE_ONLY')
        raw = path.read_bytes()
        pin = hashlib.sha256(raw).hexdigest()
        files[name] = pin
        key, value = str(path.relative_to(d)), dict(bytes=len(raw), sha256=pin)
        if key in execution['files'] and execution['files'][key] != value:
            raise ValueError('FULL_USED_INHERITED_EXECUTION_MAP_PREFIX_UNCHANGED')
        execution['files'][key] = value
    if any(r['path'] == str(root) for r in imports['roots']):
        raise ValueError('FULL_USED_ONE_NEW_IMPORT_ROOT_ONLY')
    imports['roots'].insert(0, dict(path=str(root), files=files))
    dst = Path(destination)
    if dst.exists() or dst.parent.resolve() != dst.parent or not dst.is_relative_to(root):
        raise ValueError('FULL_USED_ABSENT_NEW_LEAF_MAP_DIRECTORY_ONLY')
    dst.mkdir(mode=0o700)
    return dict(import_registry=save(dst / 'FRAMEWORK_IMPORT_PINS_PUBLIC.json', imports),
        execution_map=save(dst / 'FROZEN_FILES_PUBLIC.json', execution),
        inherited_import_sha256=IMPORT_PIN, inherited_execution_sha256=EXECUTION_PIN,
        new_roots=1, declared_source_files=list(SOURCES), generated_OWN_receipts_in_map=False,
        actual_runtime_qualified=False)


def main():
    start = time.monotonic()
    root, d = Path(__file__).resolve().parent, Path(__file__).resolve().parents[1]
    previous = d / 'formal100m-queue-approved-cold-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/maps-v2/FRAMEWORK_IMPORT_PINS_PUBLIC.json'
    assert sha(previous) == IMPORT_PIN
    inherited = json.loads(previous.read_bytes())
    sys.path[:0] = [str(root)] + [r['path'] for r in inherited['roots']]
    from formal_public_factory import base_helper, base_fields
    from formal_public_common import save, BINDINGS_SCHEMA
    from formal_full_used_emit import emit
    qualification = root / 'QUALIFICATION_PUBLIC.json'
    assert sha(qualification) == OWN_QUALIFICATION_PIN
    passed = json.loads(qualification.read_bytes())
    assert passed['PASS'] and passed['focused_OWN_cases'] == 2
    # No new OWN run/matrix: all six previously exercised sources are unchanged.
    assert all(sha(root / n) == pin for n, pin in passed['source_sha256'].items())
    maps = build(root / 'maps-wip-v1')
    reg = maps['import_registry']
    helper = base_helper()
    helper.verify_framework_imports(reg['path'], reg['sha256'], code_root=d)
    with tempfile.TemporaryDirectory(prefix='OWN-full-used-stable-map-entry-', dir=root) as name:
        temp = Path(name)
        bindings = {k: None for k in base_fields(helper) | {'racing_game_sources'}}
        bindings.update(schema=BINDINGS_SCHEMA, template_only=True, code_root=str(d),
            framework_import_pins=dict(path=reg['path'], sha256=reg['sha256']))
        desc = save(temp / 'OWN_TEMPLATE_BINDINGS_PUBLIC.json', bindings)
        made = emit(desc['path'], desc['sha256'], destination=temp / 'factory')
        entry = d / 'racing-complete-cold-tree-v4-msg237-held20-v1-msg237-prefix21-v1/runtime-v1/native_cold_owner_entry.py'
        command = [sys.executable, '-I', '-B', str(entry), '--public-factory', made['manifest']['path'],
            '--public-factory-sha256', made['manifest']['sha256'], '--verify-factory-only']
        child = subprocess.run(command, cwd='/', env=dict(PATH='/usr/bin:/bin', HOME=str(temp),
            LANG='C.UTF-8'), stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
        (root / 'STABLE_MAP_ENTRY_I_CHILD.stdout').write_bytes(child.stdout)
        (root / 'STABLE_MAP_ENTRY_I_CHILD.stderr').write_bytes(child.stderr)
        assert child.returncode == 0 and not child.stderr
        receipt = json.loads(child.stdout)
        assert receipt == dict(FROZEN_PUBLIC_FACTORY_IMPORT_PASS=True,
            factory_create_function_called=False, activation_requested=False)
    result = dict(schema='count14-formal-full-used-domain-stable-map-entry-qualification-v1', PASS=True,
        maps=maps, reused_focused_OWN=dict(path=str(qualification), sha256=OWN_QUALIFICATION_PIN, cases=2),
        new_OWN_matrix_cases=0, original_generated_entry_I_exit_code=child.returncode,
        original_generated_entry_I_stderr_bytes=0, original_generated_entry_I_receipt=receipt,
        template_and_factory_removed=True, original_owner_core_or_producer_constructed=False,
        actual_normal_writer_COMMITTED_cut_qualified=False, whole_paid_restore_factory_implemented=False,
        actual_cold_qualified=False, Dev4=False, models=0, baseline_smoke_waits_for_this=False,
        source_sha256={n: sha(root / n) for n in SOURCES}, elapsed_seconds=time.monotonic()-start)
    save(root / 'MAPS_AND_ENTRY_QUALIFICATION_PUBLIC.json', result)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
