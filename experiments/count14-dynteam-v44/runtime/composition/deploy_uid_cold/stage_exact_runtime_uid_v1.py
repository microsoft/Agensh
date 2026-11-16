"""Cold stage-only suffix: three exact public identities, no broad UID allowance.

The c88 frozen source is imported privately and never changed on disk/in RAM.
Only its source_stat binding and its single mkdir call are privately replaced.
No models/owners/SQL/Docker/credentials/scientific content are accessed.
"""
from pathlib import Path
from types import FunctionType
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
import stat
import sys

ORIGINAL_ASSETS_SHA256 = '16e6ab60b88ab4c0d86e4790f461b0fd330a0313bf7071b6dafb30bec7877a16'
CONTRACT_SHA256 = '3fa035cc45db9b9e539581c0c37d10fb46c576d79ea61f0ce52c08df44d7ae16'
ARM_ROOT = Path('/mnt/ptb-scratch2/count14-dynteam-70e2ca54-smoke-20261105')
ASSETS_HOME = ARM_ROOT/'b1/approved-final-runtime-assets-v1'
EXACT_SOURCE_INODES = {'image-mapping.json': 3474021663,
    'roster.json': 7577477961, 'validator-preflight.json': 7577477962}

class Refused(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

def need(ok, code):
    if not ok: raise Refused(code)

def metadata(path, s):
    return {'path': str(path), 'realpath': str(path), 'device': s.st_dev,
        'inode': s.st_ino, 'size': s.st_size, 'mtime_ns': s.st_mtime_ns,
        'ctime_ns': s.st_ctime_ns, 'mode': stat.S_IMODE(s.st_mode),
        'uid': s.st_uid, 'gid': s.st_gid, 'nlink': s.st_nlink}

def exact_source_stat(path, selected, original_stat):
    path = Path(path)
    if path not in selected:
        return original_stat(path)  # all destination/unselected guards unchanged
    name = selected[path]
    need(name in EXACT_SOURCE_INODES, 'ASSET_UID_ONLY_THREE_ENUMERATED_NAMES')
    s = path.lstat()
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink()
         and stat.S_ISREG(s.st_mode) and s.st_ino == EXACT_SOURCE_INODES[name]
         and s.st_uid == s.st_gid == 1000 and stat.S_IMODE(s.st_mode) == 0o400
         and s.st_nlink == 1, 'ASSET_UID_EXACT_PUBLIC_IDENTITY_NOT_GENERAL_UID1000')
    return metadata(path, s)  # original validate_source still compares EVERY field

def create_exact_home(home, expected_home):
    home = Path(home)
    need(home == expected_home and home.resolve() == home and not home.is_symlink(),
         'ASSET_UID_ONLY_CONTRACT_BASELINE_ASSET_HOME')
    root = home.parent
    parent = root.parent
    s = parent.lstat()
    need(parent.resolve() == parent and not parent.is_symlink()
         and stat.S_ISDIR(s.st_mode) and s.st_uid == os.geteuid()
         and not s.st_mode & 0o022, 'ASSET_UID_EXISTING_OWNED_CANONICAL_ARM_PARENT')
    need(not root.exists() and not root.is_symlink()
         and not home.exists() and not home.is_symlink(),
         'ASSET_UID_NEW_B1_AND_ASSETS_ONLY_NO_RETRY')
    root.mkdir(mode=0o700, parents=False)  # only exact b1, never recursive
    home.mkdir(mode=0o700, parents=False)  # original mkdir arguments unchanged

def load_original(path):
    path = Path(path)
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink(),
         'ASSET_UID_ORIGINAL_CANONICAL_FROZEN_FILE')
    s = path.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_uid in (0, os.geteuid())
         and not s.st_mode & 0o022 and s.st_size < 65536,
         'ASSET_UID_ORIGINAL_REGULAR_CODE_OWNER_MODE')
    raw = path.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == ORIGINAL_ASSETS_SHA256,
         'ASSET_UID_ORIGINAL_C88_PIN')
    spec = importlib.util.spec_from_file_location('_exact_uid_private_frozen_c88', path)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    return original, raw

def mkdir_delta(raw):
    tree = ast.parse(raw)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'stage_three')
    prior = copy.deepcopy(node)
    target = ast.parse('home.mkdir(mode=0o700, parents=False)', mode='eval').body
    matches = [n for n in ast.walk(node) if isinstance(n, ast.Call)
        and ast.dump(n, include_attributes=False) == ast.dump(target, include_attributes=False)]
    need(len(matches) == 1, 'ASSET_UID_SINGLE_ORIGINAL_ASSET_MKDIR')
    call = matches[0]
    call.func = ast.Name(id='_create_exact_assets_home', ctx=ast.Load())
    call.args = [ast.Name(id='home', ctx=ast.Load())]
    call.keywords = []
    inverse = copy.deepcopy(node)
    changed = [n for n in ast.walk(inverse) if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name) and n.func.id == '_create_exact_assets_home']
    need(len(changed) == 1, 'ASSET_UID_SINGLE_COLD_MKDIR_DELTA')
    changed[0].func, changed[0].args, changed[0].keywords = copy.deepcopy(target.func), [], copy.deepcopy(target.keywords)
    need(ast.dump(inverse, include_attributes=False) == ast.dump(prior, include_attributes=False),
         'ASSET_UID_ORIGINAL_MKDIR_AST_INVERSE')
    return ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))

def cold_stage(original, raw, selected):
    stat_fn = lambda p: exact_source_stat(p, selected, original.source_stat)
    validate = FunctionType(original.validate_source.__code__,
        dict(original.validate_source.__globals__, source_stat=stat_fn),
        original.validate_source.__name__, original.validate_source.__defaults__,
        original.validate_source.__closure__)
    scope = dict(original.__dict__, source_stat=stat_fn, validate_source=validate,
        _create_exact_assets_home=lambda p: create_exact_home(p, ASSETS_HOME))
    exec(compile(mkdir_delta(raw), str(original.__file__)+':exact_uid_parent_only', 'exec'), scope)
    return scope['stage_three']

def proof():
    return {'schema': 'count14-smoke-exact-asset-uid-cold-suffix-v1',
        'original_assets_sha256': ORIGINAL_ASSETS_SHA256,
        'exact_source_inodes': EXACT_SOURCE_INODES,
        'source_UID_GID': [1000, 1000], 'source_mode': '0400', 'source_nlink': 1,
        'contract_sha256': CONTRACT_SHA256, 'exact_home': str(ASSETS_HOME),
        'original_mkdir_AST_inverse': True,
        'source_full_metadata_and_pin_checks_retained': True,
        'original_opaque_copier_unchanged': True,
        'destination_and_other_UID_guards_unchanged': True,
        'old_files_or_permissions_modified': False, 'model_calls': 0,
        'owners': 0, 'Docker_actions': 0}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--original-assets', required=True)
    p.add_argument('--verify-only', action='store_true')
    a, rest = p.parse_known_args()
    try:
        original, raw = load_original(a.original_assets)
        frozen_stat, frozen_validate, frozen_stage = original.source_stat, original.validate_source, original.stage_three
        stage = cold_stage(original, raw, {})
        original.frozen_stager()
        original.original_copier(Path(original.__file__).parent/'original-framework-msg237-held20-v1/base')
        if a.verify_only:
            need(not rest, 'ASSET_UID_VERIFY_ONLY_NO_STAGE_ARGUMENTS')
            value = dict(proof(), PASS=True, actual_stage_executed=False,
                runtime_assets_opened=False, isolated=bool(sys.flags.isolated))
        else:
            need(os.geteuid() == 0, 'ASSET_UID_PRODUCTION_STAGE_SAME_ROOT_OPS')
            args = original.parser().parse_args(rest)
            need(args.command == 'stage-three' and args.contract_sha256 == CONTRACT_SHA256,
                 'ASSET_UID_STAGE_ONLY_EXACT_BASELINE_CONTRACT')
            stager = original.frozen_stager(args.original_stager)
            contract, row, home = original.contract_scope(stager, args.contract, args.contract_sha256, args.trajectory)
            need(home == ASSETS_HOME and Path(row['root']) == ARM_ROOT/'b1',
                 'ASSET_UID_EXACT_BASELINE_NEW_ROOT_NO_RACING')
            public = stager.public(args.public_sources, args.public_sources_sha256)
            need(type(public.get('assets')) is dict and set(public['assets']) == set(EXACT_SOURCE_INODES),
                 'ASSET_UID_EXACT_THREE_PUBLIC_SOURCE_PATHS')
            selected = {Path(r['path']): n for n, r in public['assets'].items()}
            need(len(selected) == 3, 'ASSET_UID_THREE_DISTINCT_EXACT_PATHS')
            value = cold_stage(original, raw, selected)(args)
            value['cold_suffix'] = proof()
        need(original.source_stat is frozen_stat and original.validate_source is frozen_validate
             and original.stage_three is frozen_stage, 'ASSET_UID_ORIGINAL_MODULE_UNCHANGED')
        print(json.dumps(value, sort_keys=True));return 0
    except Exception as error:
        frames = [];tb = error.__traceback__
        while tb:
            frames.append({'file': tb.tb_frame.f_code.co_filename, 'line': tb.tb_lineno,
                'function': tb.tb_frame.f_code.co_name});tb = tb.tb_next
        code = getattr(error, 'code', None)
        if not isinstance(code, str) or not code.startswith('ASSET_UID_'):
            code = 'ASSET_UID_PARTIAL_RETAINED_NO_AUTOMATIC_RETRY'
        print(json.dumps({'PUBLIC_code': code, 'exception_type': type(error).__name__,
            'locations': frames, 'partial_artifacts_retained': True,
            'model_calls': 0, 'owners': 0}, sort_keys=True));return 2

if __name__ == '__main__': raise SystemExit(main())
