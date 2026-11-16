"""OPS-only fixed opaque FINAL asset stager. No owner/model/Docker/task work.

Reads PUBLIC pin metadata; hashes/copies only enumerated runtime-code assets.
Never opens credentials or original task/source/candidate/PKL/ledger/log bodies.
"""
from __future__ import annotations
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

KEEP13_SHA256 = '2185927429abc97b3d9a318ba65d394001d036241af30f2b57a8b64488a2a570'
ORIGIN_SHA256 = 'c193188fd4d20de8ec0729b4a41bc4df7e15e38b54d84736147da0a546a147b6'
RUNTIME_KEEP_ROOTS = ((_C14_SCRATCH + '/ag30v2x48/final-runtime'),
                      (_C14_SCRATCH + '/ag30v2x48/h'),
                      (_C14_SCRATCH + '/ag30v2x48/original-fresh'))
DENIED_COMPONENTS = frozenset(('candidates', 'count14_candidates', 'private-context',
    'evaluator-private', 'requests', 'responses', 'results', 'sessions', 'snapshots',
    'workspaces', 'ledger', 'logs', '.git', '__pycache__'))


def require(ok, code):
    if not ok:raise RuntimeError(code)


def sha(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'DEPLOY_SHA256_REQUIRED')
    return value


def canonical(path):
    p = Path(path)
    require(p.is_absolute() and p.resolve() == p, 'DEPLOY_CANONICAL_ABSOLUTE_PATH')
    return p


def regular(path):
    p = canonical(path);s = p.lstat()
    require(stat.S_ISREG(s.st_mode) and not p.is_symlink() and s.st_uid in (0, os.geteuid()) and
            not s.st_mode & 0o002, 'DEPLOY_ORIGINAL_REGULAR_OWNER_NOT_WORLD_WRITABLE')
    return p


def file_sha(path):
    h = hashlib.sha256()
    source = regular(path)
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        require(stat.S_ISREG(os.fstat(f.fileno()).st_mode), 'DEPLOY_OPEN_ORIGINAL_REGULAR_FILE')
        for chunk in iter(lambda: f.read(1024*1024), b''):h.update(chunk)
    return h.hexdigest()


def public(path, expected):
    p = regular(path)
    require(p.stat().st_size <= 16*1024*1024 and file_sha(p) == sha(expected), 'DEPLOY_PUBLIC_FILE_PIN')
    return strict(p.read_bytes())



def strict(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, 'DEPLOY_PUBLIC_NO_DUPLICATE_KEY');value[key] = item
        return value
    def nonfinite(_):raise RuntimeError('DEPLOY_PUBLIC_NO_NONFINITE_JSON')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def relative_code(name, *, native=False):
    require(type(name) is str, 'DEPLOY_CODE_PATH_STRING')
    p = PurePosixPath(name)
    require(not p.is_absolute() and str(p) == name and '..' not in p.parts and
            not any(x.lower() in DENIED_COMPONENTS for x in p.parts) and
            (p.suffix in ('.py', '.js', '.mjs') or native and name in
             ('config.json', 'original-images-metadata.json', 'source-manifest.json')),
            'DEPLOY_ENUMERATED_CODE_ONLY_NEVER_TASK_CANDIDATE_PKL')
    return p


def kept(path, roots):
    p = canonical(path)
    require(any(p == r or p.is_relative_to(r) for r in roots), 'DEPLOY_SOURCE_INSIDE_REGISTERED_RUNTIME_KEEP')
    return p


def copy_pinned(source, destination, expected):
    """Byte copy, not decode; no copytree/link/symlink or replacement/retry."""
    source = regular(source);expected = sha(expected)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    before = source.stat();h = hashlib.sha256();size = 0
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as src, destination.open('xb') as dst:
        opened = os.fstat(src.fileno())
        require(stat.S_ISREG(opened.st_mode) and
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns),
                'DEPLOY_EXACT_OPEN_ORIGINAL_INODE')
        for chunk in iter(lambda: src.read(1024*1024), b''):
            h.update(chunk);size += len(chunk);dst.write(chunk)
        dst.flush();os.fsync(dst.fileno())
        ended = os.fstat(src.fileno())
        require((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) ==
                (ended.st_dev, ended.st_ino, ended.st_size, ended.st_mtime_ns, ended.st_ctime_ns),
                'DEPLOY_OPEN_SOURCE_STABLE')
    after = source.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) and
            h.hexdigest() == expected, 'DEPLOY_ORIGINAL_FILE_CHANGED_OR_PIN_MISMATCH_RETAIN_NO_RETRY')
    os.chmod(destination, 0o400)
    return {'size': size, 'sha256': expected}


def write_new(path, value, mode=0o600):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    os.chmod(path, mode)
    return hashlib.sha256(raw).hexdigest()


def stage(a):
    base = canonical(a.base);contract = public(a.contract, a.contract_sha256)
    require(contract['schema'] == 'count14-dynteam-two-arm-public-contract-v1' and contract['mode'] == 'smoke',
            'DEPLOY_ONLY_EXACT_SMOKE_CONTRACT')
    keep = regular(a.keep13)
    require(file_sha(keep) == KEEP13_SHA256, 'DEPLOY_EXACT_REGISTERED_13_KEEP_METADATA_PIN')
    keep_rows = [line.split('\t') for line in keep.read_text().splitlines() if line]
    require(len(keep_rows) == 13 and all(len(r) == 2 for r in keep_rows), 'DEPLOY_EXACT_13_KEEP_ROWS')
    kept_paths = {Path(r[0]) for r in keep_rows}
    roots = [Path(p) for p in RUNTIME_KEEP_ROOTS]
    require(all(p in kept_paths for p in roots), 'DEPLOY_REGISTERED_RUNTIME_KEEP_ROWS_REQUIRED')
    native = kept(a.native_source, roots);evaluator = kept(a.evaluator_source, roots)
    mapping = kept(a.image_mapping, roots)
    origin = public(base/'NATIVE_FINAL_CODE_ORIGIN.json', ORIGIN_SHA256)
    require(origin['schema'] == 'agensh-original-native-final-code-v1', 'DEPLOY_ORIGINAL_NATIVE_CODE_ORIGIN')
    reference = None
    if a.reference_profile:
        require(a.reference_profile_sha256, 'DEPLOY_PUBLIC_REFERENCE_FILE_PIN_REQUIRED')
        reference = public(a.reference_profile, a.reference_profile_sha256)
        require(reference['schema'] == 'count14-agensh-native-v21-profile-v1' and
                digest(reference) == contract['v2_baseline_reference_protocol']['final_v21'],
                'DEPLOY_COMPLETE_PUBLIC_REFERENCE_MUST_EQUAL_HISTORICAL_PIN')
    source_index_pin = a.native_source_index_sha256 or (reference or {}).get('source_index', {}).get('sha256')
    evaluator_pins = {n: (a.evaluator_roster_sha256 if n == 'roster.json' else a.evaluator_preflight_sha256)
        or (reference or {}).get('evaluator_assets', {}).get(n, {}).get('sha256')
        for n in ('roster.json', 'validator-preflight.json')}
    dependency_pin = a.dependency_freeze_sha256 or (reference or {}).get('dependency_freeze_sha256')
    for value in (source_index_pin, dependency_pin, *evaluator_pins.values()):sha(value)
    imports = public(a.framework_imports, a.framework_imports_sha256)
    require(imports['schema'] == 'count14-dynteam-framework-import-pins-v1' and
            type(imports['roots']) is list and imports['roots'], 'DEPLOY_EXISTING_PUBLIC_FRAMEWORK_PINS')
    framework_files = {}
    for row in imports['roots']:
        source_root = canonical(row['path'])
        # Package-owned base is allowed; old external code must be under KEEP.
        require(source_root == base or source_root.is_relative_to(Path(contract['arms'][0]['root'])/'frozen-code') or
                any(source_root == r or source_root.is_relative_to(r) for r in roots),
                'DEPLOY_FRAMEWORK_ONLY_PACKAGE_BASE_OR_REGISTERED_RUNTIME')
        for name, pin in row['files'].items():
            relative_code(name);sha(pin)
            if name in framework_files:require(framework_files[name][1] == pin, 'DEPLOY_NO_CONFLICTING_FRAMEWORK_FLATTEN')
            else:framework_files[name] = (source_root/name, pin)
    baseline = [r for r in contract['trajectories'] if r['arm'] == 'DYNTEAM']
    require(len(baseline) == 1, 'DEPLOY_BASELINE_FIRST_ONE_EXACT_SMOKE_TRAJECTORY')
    row = baseline[0];root = canonical(row['root']);home = root/'final-deployment-v1'
    python = Path(a.python)
    require(python.is_absolute() and '..' not in python.parts and python.is_file() and os.access(python, os.X_OK), 'DEPLOY_EXISTING_ISOLATED_PYTHON_EXECUTABLE')
    credential = regular(a.credential_source)  # stat ONLY: never open/hash/copy
    require(credential.stat().st_uid == os.geteuid() and stat.S_IMODE(credential.stat().st_mode) == 0o600 and
            credential.is_relative_to(Path(contract['arms'][0]['root'])), 'DEPLOY_NEW_OWNER_KEY_PATH_ONLY')
    require(not home.exists(), 'DEPLOY_FRESH_ASSET_HOME_NO_RETRY_OR_REPLACEMENT')
    home.mkdir(mode=0o700, parents=False)
    native_out, evaluator_out, framework_out = (home/n for n in ('native', 'evaluator', 'framework'))
    for p in (native_out, evaluator_out, framework_out, home/'docker-config', home/'home'):p.mkdir(mode=0o700)
    copied = {}
    for name, pin in origin['files'].items():
        relative_code(name, native=True)
        copied['native/'+name] = copy_pinned(native/name, native_out/name, pin)
    copied['native/source-manifest.json'] = copy_pinned(native/'source-manifest.json', native_out/'source-manifest.json', source_index_pin)
    for name, pin in evaluator_pins.items():copied['evaluator/'+name] = copy_pinned(evaluator/name, evaluator_out/name, pin)
    for name, (source, pin) in framework_files.items():copied['framework/'+name] = copy_pinned(source, framework_out/name, pin)
    mapping_out = home/'image-mapping.json'
    copied['image-mapping.json'] = copy_pinned(mapping, mapping_out, a.image_mapping_sha256)
    images = strict(mapping_out.read_bytes());require(type(images) is list, 'DEPLOY_ORIGINAL_IMAGE_MAPPING_LIST')
    mapping_pin = digest(images)
    if reference is not None:require(mapping_pin == reference['image_mapping_sha256'], 'DEPLOY_MAPPING_MATCH_PUBLIC_REFERENCE')
    # Fresh empty public Docker client configuration; no old Docker credentials.
    write_new(home/'docker-config'/'config.json', {'auths': {}}, mode=0o400)
    configuration = {'schema': 'count14-dynteam-smoke-final-controller-v1', 'contract_sha256': digest(contract),
        'trajectories': {row['trajectory_id']: {'native_directory': str(native_out), 'evaluator_root': str(evaluator_out),
            'image_mapping': str(mapping_out), 'image_mapping_sha256': mapping_pin,
            'dependency_freeze_sha256': dependency_pin, 'framework_root': str(framework_out),
            'docker_config': str(home/'docker-config'), 'python_command': [str(python), '-I', '-B'],
            'environment': {'PATH': os.environ.get('PATH', os.defpath), 'HOME': str(home/'home'),
                'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}, 'credential_source': str(credential)}}}
    if reference is not None:configuration['reference_profile'] = {'path': str(canonical(a.reference_profile)), 'sha256': a.reference_profile_sha256}
    config_path = home/'PRIVATE_FINAL_CONFIGURATION.json';config_sha = write_new(config_path, configuration)
    # The original trusted compiler hashes runtime/evaluator metadata; no engine,
    # subprocess, live image inspector, task source or model is executed.
    sys.path[:0] = [str(base)]
    from native_final_profile import compile_profile
    profile = compile_profile(native_out, source_bundle_sha256=contract['v2_baseline_reference_protocol']['source_bundle'],
        model_policy_sha256=contract['v2_baseline_reference_protocol']['model_configuration'], evaluator_root=evaluator_out,
        image_mapping_sha256=mapping_pin, dependency_freeze_sha256=dependency_pin)
    write_new(home/'COMPILED_FINAL_PROFILE_PUBLIC.json', profile, mode=0o400)
    value = {'schema': 'count14-smoke-final-opaque-deployment-public-v1', 'assets_staged': True,
        'contract_sha256': digest(contract), 'configuration': {'path': str(config_path), 'sha256': config_sha},
        'actual_compiled_profile_sha256': digest(profile),
        'historical_profile_exact_match': digest(profile) == contract['v2_baseline_reference_protocol']['final_v21'],
        'reference_profile_supplied': reference is not None, 'controller_preflight_still_required': True,
        'keep13_metadata_sha256': KEEP13_SHA256, 'keep_directory_hash_claimed': False,
        'copied_runtime_files': copied, 'credential_opened_hashed_or_copied': False,
        'task_source_candidate_PKL_or_private_state_copied': False, 'model_calls': 0, 'Docker_actions': 0}
    write_new(home/'DEPLOYMENT_PUBLIC.json', value, mode=0o400)
    return {k: v for k, v in value.items() if k != 'copied_runtime_files'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'contract', 'contract-sha256', 'keep13', 'native-source', 'evaluator-source',
                 'image-mapping', 'image-mapping-sha256', 'framework-imports', 'framework-imports-sha256',
                 'python', 'credential-source'):
        p.add_argument('--'+name, required=True)
    for name in ('native-source-index-sha256', 'evaluator-roster-sha256', 'evaluator-preflight-sha256',
                 'dependency-freeze-sha256', 'reference-profile', 'reference-profile-sha256'):
        p.add_argument('--'+name)
    args = p.parse_args()
    try:print(json.dumps(stage(args), sort_keys=True));return 0
    except Exception as error:
        print(json.dumps({'schema': 'count14-smoke-final-deployment-failure-public-v1',
            'exception_type': type(error).__name__, 'code': str(error) if type(error) is RuntimeError else 'DEPLOY_RETAIN_PARTIAL_NO_RETRY',
            'partial_assets_retained': True, 'model_calls': 0, 'Docker_actions': 0}), file=sys.stderr)
        return 2


if __name__ == '__main__':raise SystemExit(main())
