#!/usr/bin/env python3
"""Real original independent v2.1 child; pinned bootstrap works under -I."""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from pathlib import Path
import hashlib
import json
import os
import stat
import sys


def bootstrap():
    """Only stdlib before exact owner-generated PUBLIC framework source pins."""
    path = Path(os.environ['COUNT14_SMOKE_FINAL_IMPORTS_PUBLIC'])
    expected = os.environ['COUNT14_SMOKE_FINAL_IMPORTS_SHA256']
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
            value['schema'] == 'count14-smoke-final-frozen-imports-v1' and
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




def _msg221_alias():
    import importlib.util
    p=Path(__file__).resolve().parents[1]/'provider_model_alias.py'
    s=p.lstat()
    import stat
    if not (p.is_absolute() and p.resolve()==p and not p.is_symlink() and
            stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid in (0,os.geteuid()) and
            stat.S_IMODE(s.st_mode)==0o444 and
            hashlib.sha256(p.read_bytes()).hexdigest()=='5924a5b99af0ebc8f6cfedaa22ea40932300259049f97f513092ded21a54a981'):
        raise ValueError('MSG221_EXACT_FROZEN_PRIVATE_ALIAS_SOURCE')
    spec=importlib.util.spec_from_file_location('count14_msg221_private_provider_alias',p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def _msg220_install_provider_options(contract):
    """New AUX child only; original request/seed guards execute before URL copy."""
    from final_binding import FinalBinding
    from types import FunctionType
    if not (type(contract) is dict and contract.get('schema') == 'count14-dynteam-two-arm-public-contract-v1'
            and contract.get('mode') in ('smoke', 'production')
            and {r['arm'] for r in contract['arms']} == {'DYNTEAM', 'DYNTEAM_RACING'}
            and len(contract['trajectories']) == (2 if contract['mode'] == 'smoke' else 6)
            and all(Path(r['root']).is_absolute() and Path(r['root']).is_relative_to((_C14_SCRATCH))
                and not any('mockdebug' in p for p in Path(r['root']).parts) for r in contract['arms'])):
        raise ValueError('MSG220_AUX_ONLY_TWO_REGISTERED_NEW_ARMS')
    alias = _msg221_alias()
    alias.scope(contract)
    origin = FinalBinding.seed_provider_options
    if type(origin) is not FunctionType or origin.__name__ != 'seed_provider_options':
        raise ValueError('MSG220_ORIGINAL_AUX_PROVIDER_OPTIONS_METHOD')
    source = Path(origin.__code__.co_filename)
    if not (source.is_absolute() and source.resolve() == source and not source.is_symlink()
            and hashlib.sha256(source.read_bytes()).hexdigest() == '3547d4013adfbdd88bcec1f748a2f48c056f33045cfb0d70f66c50386d2b72cb'):
        raise ValueError('MSG220_AUX_ORIGINAL_BINDING_SOURCE_PIN')
    def selected(self, body, options):
        out = origin(self, body, options)  # Original verify_request/RNG/seed implementation, no payload observation here.
        if not (type(out) is dict and out.get('base_url') in (
                _count14_os.environ.get('COUNT14_GLM_LEGACY_BASE_URL', 'https://glm-legacy-gateway.example.invalid/v1'),
                _count14_os.environ.get('COUNT14_GLM_BASE_URL', 'https://glm-gateway.example.invalid/v1'))):
            raise ValueError('MSG220_AUX_ONLY_EXACT_OLD_OR_NEW_PROVIDER_BASE')
        return alias.alias_options(body,out) # original guard first; before native SENT/wire
    FinalBinding.seed_provider_options = selected  # Only this newly created isolated AUX child's module instance.
    return {'schema': 'count14-msg220-AUX-original-provider-option-base-only-v1',
            'original_request_seed_sampling_and_affinity_guards_retained': True,
            'base_url': _count14_os.environ.get('COUNT14_GLM_BASE_URL', 'https://glm-gateway.example.invalid/v1'),
            'upstream_model_id': alias.NEW_MODEL,
            'key_header_timeout_retry_UNKNOWN_or_fee_changed': False,
            'historical_logical_body_policy_unchanged': True}


def main():
    pin = bootstrap()
    # No ambient PYTHONPATH/cwd/script-dir dependency, even with python -I.
    from common import need, hash_file, strict, digest
    import run_native_final_child as original
    from smoke_checkpoint_final_scope import _bind_globals
    from smoke_checkpoint_final_runtime import SmokeFinalRuntimeScope, load_profile_registry
    if sys.argv[1:] == ['--verify-imports']:
        print(json.dumps({'schema': 'count14-smoke-final-zero-model-import-v1',
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
        registry = load_profile_registry(os.environ['COUNT14_SMOKE_FINAL_PROFILE_PUBLIC'],
                                         os.environ['COUNT14_SMOKE_FINAL_PROFILE_SHA256'])
        scope = SmokeFinalRuntimeScope(contract, contract_sha256=digest(contract), profile_registry=registry)
        _msg220_install_provider_options(contract)
        return _bind_globals(original.run, NativeFinalRuntime=scope.runtime, NativeImages=scope.images)(path, expected_sha256)

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
        print(json.dumps({'schema': 'count14-smoke-final-bootstrap-sanitized-failure-v1',
                          'exception_type': kind, 'frames': frames}, sort_keys=True),
              file=sys.stderr, flush=True)
        return 2


if __name__ == '__main__':
    sys.exit(entry())
