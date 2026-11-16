#!/usr/bin/env python3
"""WIP six-track cold deployment selectors, not production qualification.

OPS-only operations reuse pinned original opaque copiers and full-framework
copy. Import/--verify-only reads framework/PUBLIC metadata only and creates no
owner, asset, request, evaluator, Docker object or scientific root. This module
does not install into, or change, any existing owner or original module.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from pathlib import Path
from types import FunctionType, SimpleNamespace
import argparse
import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import os
import stat
import textwrap

CONTRACT_RAW_SHA256 = '9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'
CONTRACT_CANONICAL_SHA256 = '9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'
SOURCE_PINS = {
    'smoke_checkpoint_final_deploy.py': 'a662e49ef6fb6f504627b46251f92c63d2cfc32dd2e47927a675da17dfa025bb',
    'smoke_checkpoint_final_newroot_assets_v1.py': '16e6ab60b88ab4c0d86e4790f461b0fd330a0313bf7071b6dafb30bec7877a16',
    'smoke_checkpoint_final_framework_copy_v2.py': 'e303b21a546863326435197e13147b0cb568351b7c9489c5a47828babbe0e04b',
}
FORMAL_SCHEMA = 'count14-dynteam-formal100m-final-controller-v1'
ENV_SCHEMA = 'count14-formal100m-shared-final-infrastructure-environment-v1'
FINAL_FIELDS = frozenset(('native_directory', 'evaluator_root', 'image_mapping',
    'image_mapping_sha256', 'dependency_freeze_sha256', 'framework_root',
    'docker_config', 'python_command', 'environment', 'credential_source'))


def need(ok, code):
    if not ok:
        raise ValueError(code)


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def clone(function, **bindings):
    result = FunctionType(function.__code__, dict(function.__globals__, **bindings),
                          function.__name__, function.__defaults__, function.__closure__)
    result.__kwdefaults__ = function.__kwdefaults__
    return result


def expression(value):
    return ast.parse(value, mode='eval').body


def replace_exact(function, changes, **bindings):
    """Every selector is one pinned AST site with an exact inverse proof."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    original = copy.deepcopy(tree)
    sites = []
    for before, after in changes:
        old, new = expression(before), expression(after)
        matches = [node for node in ast.walk(tree) if ast.dump(node, include_attributes=False) ==
                   ast.dump(old, include_attributes=False)]
        need(len(matches) == 1, 'FORMAL_DEPLOY_ONE_EXACT_ORIGINAL_SELECTOR_SITE')
        target = matches[0]
        sites.append((copy.deepcopy(old), copy.deepcopy(new)))
        target.__class__ = type(new)
        target.__dict__.clear()
        target.__dict__.update(copy.deepcopy(new.__dict__))
    restored = copy.deepcopy(tree)
    for old, new in reversed(sites):
        matches = [node for node in ast.walk(restored) if ast.dump(node, include_attributes=False) ==
                   ast.dump(new, include_attributes=False)]
        need(len(matches) == 1, 'FORMAL_DEPLOY_ONE_EXACT_INVERSE_SELECTOR_SITE')
        target = matches[0]
        target.__class__ = type(old)
        target.__dict__.clear()
        target.__dict__.update(copy.deepcopy(old.__dict__))
    need(ast.dump(restored, include_attributes=False) == ast.dump(original, include_attributes=False),
         'FORMAL_DEPLOY_ORIGINAL_COPY_PINS_KEEP_AND_FORMULAS_INVERSE_AST_UNCHANGED')
    namespace = dict(function.__globals__, **bindings)
    exec(compile(ast.fix_missing_locations(tree), __file__ + ':cold-selectors', 'exec'), namespace)
    return namespace[function.__name__]


def load_sources(runtime):
    runtime = Path(runtime)
    need(runtime.is_absolute() and runtime.resolve() == runtime and runtime.is_dir(),
         'FORMAL_DEPLOY_CANONICAL_FROZEN_RUNTIME')
    modules = {}
    for name, pin in SOURCE_PINS.items():
        path = runtime / name
        need(path.is_file() and not path.is_symlink() and sha(path.read_bytes()) == pin,
             'FORMAL_DEPLOY_EXACT_ORIGINAL_FRAMEWORK_SOURCE_PIN')
        spec = importlib.util.spec_from_file_location('_formal_deploy_' + path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules[name] = module
    return modules


def registered(stager, path, pin):
    need(pin == CONTRACT_RAW_SHA256, 'FORMAL_DEPLOY_REGISTERED_PUBLIC_CONTRACT_RAW_PIN')
    contract = stager.public(path, pin)
    need(stager.digest(contract) == CONTRACT_CANONICAL_SHA256 and
         contract.get('mode') == 'production' and len(contract['trajectories']) == 6 and
         contract['capacities']['per_track_SEARCH'] == 13,
         'FORMAL_DEPLOY_EXACT_SIX_TRACK_REGISTERED_PRODUCTION_CONTRACT')
    return contract


def selected(contract, trajectory):
    need(type(trajectory) is str, 'FORMAL_DEPLOY_EXPLICIT_TRAJECTORY_NO_B1_DEFAULT')
    rows = [r for r in contract['trajectories'] if r['trajectory_id'] == trajectory]
    need(len(rows) == 1, 'FORMAL_DEPLOY_ONE_EXACT_REGISTERED_TRAJECTORY')
    row = rows[0]
    arms = [a for a in contract['arms'] if a['arm'] == row['arm']]
    root = Path(row['root'])
    need(len(arms) == 1 and row['block'] in (1, 2, 3) and
         root == Path(arms[0]['root']) / ('b' + str(row['block'])) and
         root.is_absolute() and root.is_relative_to((_C14_SCRATCH)),
         'FORMAL_DEPLOY_REGISTERED_ARM_BLOCK_ROOT_NOT_ARBITRARY_PREFIX')
    return row


def shared_home(contract):
    return Path(contract['arms'][0]['root']) / 'formal-final-owner-environment-v1'


def directory(path):
    path = Path(path)
    info = path.lstat()
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink() and
         stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid() and
         stat.S_IMODE(info.st_mode) == 0o700,
         'FORMAL_DEPLOY_EXACT_OWNER_INFRASTRUCTURE_PRIVATE_DIRECTORY')
    return path


def prepare_environment(stager, contract):
    """OPS pre-owner preparation only; O_EXCL/no replacement or cleanup."""
    directory(contract['arms'][0]['root'])
    home = shared_home(contract)
    need(not home.exists() and not home.is_symlink(), 'FORMAL_DEPLOY_SHARED_ENV_ABSENT_NO_RETRY')
    home.mkdir(mode=0o700)
    (home / 'home').mkdir(mode=0o700)
    value = {'schema': ENV_SCHEMA, 'contract_sha256': stager.digest(contract),
        'environment': {'PATH': os.environ.get('PATH', os.defpath), 'HOME': str(home / 'home'),
                        'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'},
        'owner_created_by_command': False, 'scientific_state_stored_here': False,
        'models': 0, 'not_runtime_qualification': True}
    path = home / 'SHARED_FINAL_ENVIRONMENT_PUBLIC.json'
    return {'path': str(path), 'sha256': stager.write_new(path, value, mode=0o400)}


def environment(stager, contract, path, pin):
    home = directory(shared_home(contract))
    directory(home / 'home')
    need(Path(path) == home / 'SHARED_FINAL_ENVIRONMENT_PUBLIC.json',
         'FORMAL_DEPLOY_EXACT_SHARED_ENV_DESCRIPTOR_PATH')
    value = stager.public(path, pin)
    need(value.get('schema') == ENV_SCHEMA and value.get('contract_sha256') == stager.digest(contract),
         'FORMAL_DEPLOY_SHARED_ENV_CURRENT_CONTRACT')
    env = value['environment']
    need(set(env) == {'PATH', 'HOME', 'LANG', 'PYTHONDONTWRITEBYTECODE'} and
         all(type(x) is str for x in env.values()) and env['HOME'] == str(home / 'home') and
         env['LANG'] == 'C.UTF-8' and env['PYTHONDONTWRITEBYTECODE'] == '1',
         'FORMAL_DEPLOY_ONLY_SHARED_INFRASTRUCTURE_ENV_NOT_CREDENTIAL_OR_SCIENCE')
    return env


def adapters(runtime, *, trajectory, shared_env=None):
    sources = load_sources(runtime)
    stager = sources['smoke_checkpoint_final_deploy.py']
    assets = sources['smoke_checkpoint_final_newroot_assets_v1.py']
    framework = sources['smoke_checkpoint_final_framework_copy_v2.py']

    def scope(original_stager, path, pin, requested=None):
        need(requested == trajectory, 'FORMAL_DEPLOY_SAME_EXPLICIT_TRACK_THROUGH_COPY_AND_CONFIG')
        contract = registered(original_stager, path, pin)
        row = selected(contract, trajectory)
        return contract, row, Path(row['root']) / 'approved-final-runtime-assets-v1'

    # Original stage makes each track's distinct native/evaluator/framework and
    # Docker-config roots. Only its common infrastructure env is shared, since
    # the original one-controller child-environment equality guard stays exact.
    stage = replace_exact(stager.stage, [
        ("'smoke'", "'production'"),
        ("[r for r in contract['trajectories'] if r['arm'] == 'DYNTEAM']",
         "[_formal_select(contract, _formal_trajectory)]"),
        ("'count14-dynteam-smoke-final-controller-v1'", repr(FORMAL_SCHEMA)),
        ("{'PATH': os.environ.get('PATH', os.defpath), 'HOME': str(home/'home'), 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}",
         'dict(_formal_shared_environment)'),
    ], _formal_select=selected, _formal_trajectory=trajectory, _formal_shared_environment=shared_env)

    def original_stager(source=None):
        original = assets.frozen_stager(source)  # retains original exact source pin
        return SimpleNamespace(**dict(original.__dict__, stage=stage))

    verify = clone(assets.verify_receipt, contract_scope=scope)
    stage_three = clone(assets.stage_three, contract_scope=scope, frozen_stager=original_stager)
    deploy = clone(assets.deploy_with_staged, verify_receipt=verify, frozen_stager=original_stager)

    def framework_row(contract, arm):
        row = selected(contract, trajectory)
        need(row['arm'] == arm and not framework.SOURCE.is_relative_to(Path(row['root'])) and
             not Path(row['root']).is_relative_to(framework.SOURCE),
             'FORMAL_DEPLOY_FULL_COPY_EXACT_ARM_TRACK_DISJOINT_SOURCE')
        return row

    patch = replace_exact(framework.patch_configuration, [
        ("'count14-dynteam-smoke-final-controller-v1'", repr(FORMAL_SCHEMA))])
    fullcopy = replace_exact(framework.execute, [("'smoke'", "'production'")],
                             selected_row=framework_row, patch_configuration=patch)
    return stager, assets, stage_three, deploy, fullcopy


def aggregate(stager, contract, descriptors, *, environment_value):
    """Normal trusted-runtime config assembly, no old config is rewritten."""
    need(type(descriptors) is list and len(descriptors) == 6,
         'FORMAL_DEPLOY_EXACTLY_SIX_CURRENT_CONFIG_DESCRIPTORS')
    rows = {r['trajectory_id']: r for r in contract['trajectories']}
    entries, references, commands = {}, [], set()
    for descriptor in descriptors:
        need(set(descriptor) == {'trajectory', 'path', 'sha256'}, 'FORMAL_DEPLOY_EXACT_DESCRIPTOR_FIELDS')
        t = descriptor['trajectory']
        need(t in rows and t not in entries, 'FORMAL_DEPLOY_SIX_DISTINCT_REGISTERED_CONFIGS')
        root = Path(selected(contract, t)['root'])
        path = Path(descriptor['path'])
        need(path == root / 'final-framework-copy-v1' / 'PRIVATE_FINAL_CONFIGURATION_FRAMEWORK_COPY_V1.json',
             'FORMAL_DEPLOY_ONLY_NEW_PER_TRACK_COMPLETE_FRAMEWORK_CONFIG_B')
        info = path.lstat()
        need(stat.S_ISREG(info.st_mode) and not path.is_symlink() and path.resolve() == path and
             info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1,
             'FORMAL_DEPLOY_NEW_PRIVATE_INFRASTRUCTURE_CONFIG_IDENTITY')
        config = stager.public(path, descriptor['sha256'])
        need(config.get('schema') == FORMAL_SCHEMA and config.get('contract_sha256') == stager.digest(contract) and
             set(config) == {'schema', 'contract_sha256', 'trajectories', 'reference_profile'} and
             set(config['trajectories']) == {t}, 'FORMAL_DEPLOY_PER_TRACK_CONFIG_B_CURRENT_CONTRACT')
        f = config['trajectories'][t]
        need(set(f) == FINAL_FIELDS and f['environment'] == environment_value and
             Path(f['framework_root']) == root / 'final-framework-dependencies-v1' and
             Path(f['native_directory']) == root / 'final-deployment-v1' / 'native' and
             Path(f['evaluator_root']) == root / 'final-deployment-v1' / 'evaluator' and
             Path(f['docker_config']) == root / 'final-deployment-v1' / 'docker-config',
             'FORMAL_DEPLOY_SIX_ISOLATED_ASSET_ROOTS_WITH_COMMON_INFRASTRUCTURE_ENV')
        commands.add(tuple(f['python_command']))
        references.append(config['reference_profile'])
        entries[t] = f
    need(set(entries) == set(rows) and len(commands) == 1 and all(r == references[0] for r in references),
         'FORMAL_DEPLOY_ONE_ORIGINAL_PYTHON_REFERENCE_AND_SIX_FULL_TRACKS')
    config = {'schema': FORMAL_SCHEMA, 'contract_sha256': stager.digest(contract),
              'trajectories': entries, 'reference_profile': references[0]}
    path = directory(shared_home(contract)) / 'PRIVATE_FINAL_CONFIGURATION.json'
    pin = stager.write_new(path, config, mode=0o600)
    return {'configuration': {'path': str(path), 'sha256': pin}, 'tracks': 6,
            'models': 0, 'actual_Dev4_smoke_pass': False, 'formal_delivery_claimed': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--contract')
    parser.add_argument('--contract-sha256')
    parser.add_argument('--trajectory')
    parser.add_argument('--shared-environment')
    parser.add_argument('--shared-environment-sha256')
    parser.add_argument('--operation', choices=('prepare-environment', 'stage-three', 'deploy-with-staged',
                                               'full-framework-copy', 'aggregate'))
    parser.add_argument('--descriptors-public')
    parser.add_argument('--descriptors-public-sha256')
    args, extra = parser.parse_known_args(argv)
    try:
        stager, assets, stage_three, deploy, fullcopy = adapters(args.runtime, trajectory=args.trajectory)
        if args.verify_only:
            need(not extra and not args.operation, 'FORMAL_DEPLOY_VERIFY_ONLY_NO_ACTION')
            print(json.dumps({'inverse_original_AST': True, 'models': 0, 'owners': 0,
                              'assets_copied': False, 'runtime_qualified': False}, sort_keys=True))
            return 0
        contract = registered(stager, args.contract, args.contract_sha256)
        if args.operation == 'prepare-environment':
            need(not extra, 'FORMAL_DEPLOY_SHARED_PREP_NO_EXTRA_ARGUMENTS')
            result = prepare_environment(stager, contract)
        else:
            env = environment(stager, contract, args.shared_environment, args.shared_environment_sha256)
            if args.operation == 'aggregate':
                need(not extra, 'FORMAL_DEPLOY_AGGREGATE_NO_EXTRA_ARGUMENTS')
                descriptors = stager.public(args.descriptors_public, args.descriptors_public_sha256)
                result = aggregate(stager, contract, descriptors, environment_value=env)
            else:
                selected(contract, args.trajectory)
                stager, assets, stage_three, deploy, fullcopy = adapters(
                    args.runtime, trajectory=args.trajectory, shared_env=env)
                if args.operation in ('stage-three', 'deploy-with-staged'):
                    original = assets.parser().parse_args([args.operation, '--contract', args.contract,
                        '--contract-sha256', args.contract_sha256, '--trajectory', args.trajectory, *extra])
                    result = stage_three(original) if args.operation == 'stage-three' else deploy(original)
                else:
                    need(args.operation == 'full-framework-copy', 'FORMAL_DEPLOY_OPERATION_REQUIRED')
                    p = argparse.ArgumentParser()
                    for name in ('final-configuration', 'final-configuration-sha256',
                                 'ops-boundary-public', 'ops-boundary-sha256'):
                        p.add_argument('--' + name, required=True)
                    original = p.parse_args(extra)
                    original.contract, original.contract_sha256 = args.contract, args.contract_sha256
                    original.arm = selected(contract, args.trajectory)['arm']
                    result = fullcopy(original)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        tb, locations = error.__traceback__, []
        while tb:
            locations.append({'file': tb.tb_frame.f_code.co_filename, 'line': tb.tb_lineno,
                              'function': tb.tb_frame.f_code.co_name})
            tb = tb.tb_next
        print(json.dumps({'PUBLIC_code': 'FORMAL_DEPLOY_RETAIN_PARTIAL_NO_RETRY',
            'exception_type': type(error).__name__, 'locations': locations,
            'models': 0, 'formal_delivery_claimed': False}, sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
