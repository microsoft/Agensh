"""Cold suffix: exactly three original FINAL runtime assets, never old state.

stage-three: OPS-projected current PUBLIC paths -> original opaque copier ->
exact new trajectory root + PUBLIC provenance. deploy-with-staged: scoped clone
of the frozen original stager admits ONLY those exact receipt-bound assets.
No old-root whitelist mutation, model, evaluator, Docker, source/task or PKL work.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
from types import FunctionType

PROFILE_SHA256 = '8530bb5026d7ad9a77a5aa78a92d9d18426fb97b5236de75ccb6c278ae28aeba'
MAPPING_CANONICAL_SHA256 = 'ad4f22108cb4f9aaac57dd3627f667e2355ebcbd3ed4f05715e8a7ffa3885de3'
ORIGINAL_STAGER_SHA256 = 'a662e49ef6fb6f504627b46251f92c63d2cfc32dd2e47927a675da17dfa025bb'
ORIGINAL_COMMON_SHA256 = '8e282841a16b0c3632b61063c1e3cadf9d58a9285baca94e5d6c8a4841d6c5fe'
ORIGINAL_COPY_SOURCE_SHA256 = '9c137e44d1bcbfbec816f43871982e1997b31bc66b1dc99f0e3df18943257290'
DESTINATION_NAMES = ('roster.json', 'validator-preflight.json', 'image-mapping.json')
PROVENANCE_NAME = 'THREE_RUNTIME_ASSETS_PROVENANCE_PUBLIC.json'
# SOURCE_METADATA_FIELDS is the complete OPS PUBLIC projection, not a private
# launch/config/engine dump. Every identity field must match the fresh source.
SOURCE_METADATA_FIELDS = frozenset(('path', 'realpath', 'device', 'inode', 'size',
    'mtime_ns', 'ctime_ns', 'mode', 'uid', 'gid', 'nlink', 'sha256', 'runtime_asset_kind'))
SOURCE_KIND = {'roster.json': 'ORIGINAL_FINAL_RUNTIME_ROSTER',
    'validator-preflight.json': 'ORIGINAL_FINAL_RUNTIME_VALIDATOR_PREFLIGHT',
    'image-mapping.json': 'ORIGINAL_FINAL_PUBLIC_IMAGE_MAPPING'}


def need(ok, code):
    if not ok:raise RuntimeError(code)


def load_module(path, expected, name):
    path = Path(path)
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink() and
         hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'ASSET_FROZEN_CODE_PIN')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def frozen_stager(path=None):
    return load_module(Path(path) if path else Path(__file__).resolve().with_name('smoke_checkpoint_final_deploy.py'),
                       ORIGINAL_STAGER_SHA256, '_smoke_frozen_final_stager_v1')


def source_stat(path):
    path = Path(path);s = path.lstat()
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink() and
         stat.S_ISREG(s.st_mode) and s.st_uid in (0, os.geteuid()) and not s.st_mode & 0o002,
         'ASSET_EXACT_CANONICAL_REGULAR_RUNTIME_FILE')
    return {'path': str(path), 'realpath': str(path), 'device': s.st_dev, 'inode': s.st_ino,
        'size': s.st_size, 'mtime_ns': s.st_mtime_ns, 'ctime_ns': s.st_ctime_ns,
        'mode': stat.S_IMODE(s.st_mode), 'uid': s.st_uid, 'gid': s.st_gid, 'nlink': s.st_nlink}


def validate_source(row, name, expected_pin):
    need(type(row) is dict and set(row) == SOURCE_METADATA_FIELDS and name in DESTINATION_NAMES,
         'ASSET_EXACT_SOURCE_METADATA_FIELDS')
    need(row['runtime_asset_kind'] == SOURCE_KIND[name] and row['sha256'] == expected_pin,
         'ASSET_ONLY_ORIGINAL_RUNTIME_PIN_NOT_SCIENTIFIC_STATE')
    if name != 'image-mapping.json':need(Path(row['path']).name == name, 'ASSET_TWO_LITERAL_EVALUATOR_ASSET_NAMES')
    else:need(Path(row['path']).suffix == '.json', 'ASSET_ONLY_PUBLIC_IMAGE_MAPPING_JSON')
    need(all(row[k] == value for k, value in source_stat(row['path']).items()),
         'ASSET_CURRENT_SOURCE_IDENTITY_CHANGED')
    return Path(row['path'])


def original_copier(base):
    base = Path(base)
    common = load_module(base/'common.py', ORIGINAL_COMMON_SHA256, '_smoke_original_opaque_common_v1')
    text = (base/'run_native_scientific6.py').read_text()
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == '_copy_opaque')
    need(hashlib.sha256(ast.get_source_segment(text, node).encode()).hexdigest() == ORIGINAL_COPY_SOURCE_SHA256,
         'ASSET_ORIGINAL_TRUSTED_COPY_BODY_PIN')
    namespace = {'Path': Path, 'os': os, 'regular_fd': common.regular_fd,
                 'need': common.need, 'hash_file': common.hash_file}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(base/'run_native_scientific6.py'), 'exec'), namespace)
    return namespace['_copy_opaque']


def contract_scope(stager, path, pin, trajectory=None):
    contract = stager.public(path, pin)
    need(contract.get('schema') == 'count14-dynteam-two-arm-public-contract-v1' and
         contract.get('mode') == 'smoke' and
         contract['v2_baseline_reference_protocol']['final_v21'] == PROFILE_SHA256,
         'ASSET_EXACT_ORIGINAL_PROFILE_SMOKE_CONTRACT')
    rows = [r for r in contract['trajectories'] if r['trajectory_id'] == trajectory] if trajectory else [
        r for r in contract['trajectories'] if r['arm'] == 'DYNTEAM']
    need(len(rows) == 1 and rows[0]['arm'] == 'DYNTEAM', 'ASSET_V1_ONLY_EXACT_BASELINE_CONTRACT_TRAJECTORY')
    root = stager.canonical(rows[0]['root'])
    return contract, rows[0], root/'approved-final-runtime-assets-v1'


def expected_pins(stager, profile_path, profile_pin):
    need(profile_pin == PROFILE_SHA256, 'ASSET_COMPLETE_PROFILE8530_RAW_PIN')
    profile = stager.public(profile_path, profile_pin)
    need(profile.get('schema') == 'count14-agensh-native-v21-profile-v1' and
         stager.digest(profile) == PROFILE_SHA256 and
         profile['image_mapping_sha256'] == MAPPING_CANONICAL_SHA256,
         'ASSET_COMPLETE_ORIGINAL_PROFILE8530_CANONICAL_PIN')
    return {n: profile['evaluator_assets'][n]['sha256'] for n in DESTINATION_NAMES[:2]}


def stage_three(a):
    stager = frozen_stager(a.original_stager)
    contract, row, home = contract_scope(stager, a.contract, a.contract_sha256, a.trajectory)
    pins = expected_pins(stager, a.reference_profile, a.reference_profile_sha256)
    metadata = stager.public(a.public_sources, a.public_sources_sha256)
    need(type(metadata) is dict and set(metadata) == {'schema', 'observed_at', 'contract_sha256',
         'trajectory', 'original_final_profile_sha256', 'copy_requested_by_original_OPS_owner', 'assets'} and
         metadata['schema'] == 'count14-smoke-original-runtime-three-source-paths-public-v1' and
         type(metadata['observed_at']) is str and metadata['contract_sha256'] == stager.digest(contract) and
         metadata['trajectory'] == row['trajectory_id'] and metadata['original_final_profile_sha256'] == PROFILE_SHA256 and
         metadata['copy_requested_by_original_OPS_owner'] is True and type(metadata['assets']) is dict and
         set(metadata['assets']) == set(DESTINATION_NAMES), 'ASSET_EXACT_OPS_PUBLIC_PATH_PROJECTION')
    pins['image-mapping.json'] = stager.sha(metadata['assets']['image-mapping.json']['sha256'])
    sources = {n: validate_source(metadata['assets'][n], n, pins[n]) for n in DESTINATION_NAMES}
    need(len(set(sources.values())) == 3 and not home.exists() and not home.is_symlink(),
         'ASSET_THREE_DISTINCT_FILES_FRESH_NEWROOT_NO_RETRY')
    # Owner explicitly runs this command; PUBLIC metadata alone grants no rights.
    copier = original_copier(stager.canonical(a.base))
    home.mkdir(mode=0o700, parents=False)
    copies = {}
    for name in DESTINATION_NAMES:
        validate_source(metadata['assets'][name], name, pins[name])
        copier(sources[name], home/name, pins[name])  # exact original body
        validate_source(metadata['assets'][name], name, pins[name])
        copies[name] = {'source': metadata['assets'][name], 'destination': str(home/name),
            'destination_metadata': source_stat(home/name), 'sha256': pins[name]}
    # Only public image/layer-ID mapping metadata is parsed. The two evaluator
    # files above remain opaque bytes throughout stage and verification.
    mapping = stager.strict((home/'image-mapping.json').read_bytes())
    need(type(mapping) is list and stager.digest(mapping) == MAPPING_CANONICAL_SHA256,
         'ASSET_ORIGINAL_MAPPING_CANONICAL_AD4F_PIN')
    copies['image-mapping.json']['canonical_sha256'] = MAPPING_CANONICAL_SHA256
    value = {'schema': 'count14-smoke-newroot-three-runtime-assets-provenance-v1',
        'contract_sha256': stager.digest(contract), 'trajectory': row['trajectory_id'], 'root': str(home),
        'original_final_profile_sha256': PROFILE_SHA256,
        'profile_descriptor': {'path': str(stager.canonical(a.reference_profile)), 'sha256': PROFILE_SHA256},
        'source_metadata_descriptor': {'path': str(stager.canonical(a.public_sources)), 'sha256': a.public_sources_sha256},
        'source_observed_at': metadata['observed_at'], 'assets': copies,
        'original_copy_source_sha256': ORIGINAL_COPY_SOURCE_SHA256,
        'original_common_sha256': ORIGINAL_COMMON_SHA256, 'original_stager_sha256': ORIGINAL_STAGER_SHA256,
        'evaluator_files_semantically_decoded': False, 'scientific_state_task_candidate_or_PKL_copied': False,
        'credentials_opened_hashed_or_copied': False, 'model_calls': 0, 'evaluator_runs': 0, 'Docker_actions': 0,
        'provenance_is_not_authorization_or_scientific_qualification': True}
    path = home/PROVENANCE_NAME;pin = stager.write_new(path, value, mode=0o400)
    return {'schema': 'count14-smoke-newroot-runtime-assets-staged-public-v1',
            'root': str(home), 'provenance': {'path': str(path), 'sha256': pin}, 'exact_runtime_assets': 3,
            'model_calls': 0, 'evaluator_runs': 0, 'Docker_actions': 0}


def receipt_scope(receipt, home, *, contract_sha256, trajectory):
    need(receipt.get('schema') == 'count14-smoke-newroot-three-runtime-assets-provenance-v1' and
         receipt.get('contract_sha256') == contract_sha256 and receipt.get('trajectory') == trajectory and
         receipt.get('root') == str(home) and receipt.get('original_final_profile_sha256') == PROFILE_SHA256 and
         receipt.get('original_copy_source_sha256') == ORIGINAL_COPY_SOURCE_SHA256 and
         receipt.get('original_common_sha256') == ORIGINAL_COMMON_SHA256 and
         receipt.get('original_stager_sha256') == ORIGINAL_STAGER_SHA256 and
         type(receipt.get('assets')) is dict and set(receipt['assets']) == set(DESTINATION_NAMES),
         'ASSET_RECEIPT_EXACT_CONTRACT_NEWROOT_AND_THREE_NAMES')
    for name, row in receipt['assets'].items():
        need(row['destination'] == str(home/name), 'ASSET_RECEIPT_NO_PATH_SUBSTITUTION_OR_PREFIX_EXPANSION')
    return frozenset((home, home/'image-mapping.json'))


def verify_receipt(stager, a):
    contract, row, home = contract_scope(stager, a.contract, a.contract_sha256, a.trajectory)
    path = stager.canonical(a.staged_provenance)
    need(path == home/PROVENANCE_NAME, 'ASSET_RECEIPT_ONLY_EXACT_NEWROOT_FILENAME')
    receipt = stager.public(path, a.staged_provenance_sha256)
    allowed = receipt_scope(receipt, home, contract_sha256=stager.digest(contract), trajectory=row['trajectory_id'])
    profile = receipt['profile_descriptor']
    pins = expected_pins(stager, profile['path'], profile['sha256'])
    need(set(p.name for p in home.iterdir()) == set(DESTINATION_NAMES) | {PROVENANCE_NAME},
         'ASSET_NEWROOT_EXACT_THREE_ASSETS_AND_RECEIPT_ONLY')
    for name in DESTINATION_NAMES:
        info = receipt['assets'][name];current = source_stat(home/name)
        need(info['destination_metadata'] == current and stager.file_sha(home/name) == info['sha256'],
             'ASSET_RECEIPT_DESTINATION_CURRENT_IDENTITY_AND_RAW_PIN')
        if name != 'image-mapping.json':need(info['sha256'] == pins[name], 'ASSET_EVALUATOR_RAW_PROFILE_PIN')
    mapping = stager.strict((home/'image-mapping.json').read_bytes())
    need(type(mapping) is list and stager.digest(mapping) == MAPPING_CANONICAL_SHA256 and
         receipt['assets']['image-mapping.json']['canonical_sha256'] == MAPPING_CANONICAL_SHA256,
         'ASSET_MAPPING_RECEIPT_CANONICAL_PIN')
    return receipt, allowed


def deploy_with_staged(a):
    stager = frozen_stager(a.original_stager);receipt, allowed = verify_receipt(stager, a)
    home = Path(receipt['root'])
    need(Path(a.native_source) not in allowed, 'ASSET_NATIVE_SOURCE_MUST_REMAIN_ORIGINAL_KEEP_ROOT')
    if a.reference_profile:
        need(a.reference_profile_sha256 == PROFILE_SHA256, 'ASSET_SAME_COMPLETE_PROFILE_REFERENCE')
    else:
        a.reference_profile = receipt['profile_descriptor']['path'];a.reference_profile_sha256 = PROFILE_SHA256
    a.evaluator_source = str(home);a.image_mapping = str(home/'image-mapping.json')
    a.image_mapping_sha256 = receipt['assets']['image-mapping.json']['sha256']
    original_kept = stager.kept
    def exact_kept(path, old_roots):
        candidate = stager.canonical(path)
        if candidate in allowed:return candidate
        return original_kept(path, old_roots)  # unchanged original old-root list
    stage = FunctionType(stager.stage.__code__, dict(stager.stage.__globals__, kept=exact_kept),
                         stager.stage.__name__, stager.stage.__defaults__, stager.stage.__closure__)
    result = stage(a)
    result['staged_runtime_provenance'] = {'path': a.staged_provenance, 'sha256': a.staged_provenance_sha256}
    result['old_root_whitelist_expanded'] = False
    return result


def parser():
    p = argparse.ArgumentParser(description=__doc__);sub = p.add_subparsers(dest='command', required=True)
    stage = sub.add_parser('stage-three');deploy = sub.add_parser('deploy-with-staged')
    for current in (stage, deploy):
        for name in ('base', 'contract', 'contract-sha256'):current.add_argument('--'+name, required=True)
        current.add_argument('--original-stager');current.add_argument('--trajectory')
    for name in ('public-sources', 'public-sources-sha256', 'reference-profile', 'reference-profile-sha256'):
        stage.add_argument('--'+name, required=True)
    for name in ('staged-provenance', 'staged-provenance-sha256', 'keep13', 'native-source',
                 'framework-imports', 'framework-imports-sha256', 'python', 'credential-source'):
        deploy.add_argument('--'+name, required=True)
    for name in ('native-source-index-sha256', 'evaluator-roster-sha256', 'evaluator-preflight-sha256',
                 'dependency-freeze-sha256', 'reference-profile', 'reference-profile-sha256'):
        deploy.add_argument('--'+name)
    return p


def main():
    a = parser().parse_args()
    try:
        result = stage_three(a) if a.command == 'stage-three' else deploy_with_staged(a)
        print(json.dumps(result, sort_keys=True));return 0
    except BaseException as error:
        code = getattr(error, 'code', None)
        if code is None and type(error) is RuntimeError and error.args:code = error.args[0]
        if type(code) is not str or re.fullmatch('[A-Z][A-Z0-9_]{0,159}', code) is None:code = 'ASSET_RETAIN_PARTIAL_NO_RETRY'
        print(json.dumps({'schema': 'count14-smoke-newroot-runtime-assets-failure-public-v1',
            'exception_type': type(error).__name__, 'code': code, 'partial_artifacts_retained': True,
            'model_calls': 0, 'evaluator_runs': 0, 'Docker_actions': 0}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == '__main__':raise SystemExit(main())
