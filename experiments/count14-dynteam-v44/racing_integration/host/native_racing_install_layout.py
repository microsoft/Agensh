#!/usr/bin/env python3
"""RACING NEW-cold-root PUBLIC layout, without reading FINAL/task/key bodies.

This is not the old baseline layout's hard-coded-root bypass. The NEW paired
contract retains the original arm order and arm0 code/key/control placement.
Only explicit public tool proofs and frozen framework pins are consumed here.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import stat

SOURCE_BINDING_SHA256 = 'a063532a03a06939242c19c8e9aa72e7acaef37feb4c5d0247db085a6a4c6724'
PUBLIC_SCOPE_FIELDS = {'original_v2_tool_binding_sha256', 'original_count14_catalogue_sha256',
    'native_scope_sha256', 'original_public_tools_only', 'official_evaluator_access',
    'private_reference_access'}


def need(ok, code):
    if not ok:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(value):
    need(type(value) is str and len(value) == 64 and
        all(c in '0123456789abcdef' for c in value), 'RACING_LAYOUT_EXPLICIT_SHA256')
    return value


def public(path, expected, maximum=8 * 1024 * 1024):
    path = Path(path)
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink() and
        path.name.endswith('PUBLIC.json'), 'RACING_LAYOUT_PUBLIC_METADATA_ONLY')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        raw = os.read(fd, maximum + 1)
        b, c = os.fstat(fd), path.lstat()
        key = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        need(stat.S_ISREG(a.st_mode) and not a.st_mode & 0o022 and
            a.st_uid in (0, os.geteuid()) and a.st_nlink == 1 and
            0 < len(raw) == a.st_size <= maximum and key(a) == key(b) == key(c) and
            sha(raw) == pin(expected), 'RACING_LAYOUT_PUBLIC_PIN_AND_IDENTITY')
    finally:
        os.close(fd)

    def pairs(items):
        value = {}
        for k, v in items:
            need(k not in value, 'RACING_LAYOUT_NO_DUPLICATE_PUBLIC_FIELD')
            value[k] = v
        return value

    value = json.loads(raw, object_pairs_hook=pairs)
    need(type(value) is dict, 'RACING_LAYOUT_PUBLIC_OBJECT')
    return value


def install(*, code_root, manifest_sha256, contract_directory,
            final_configuration, final_configuration_sha256,
            public_tool_scope, public_tool_scope_sha256):
    root = Path(code_root)
    need(root.is_absolute() and root.resolve() == root and root.is_dir() and
        root.name == 'frozen-code', 'RACING_LAYOUT_EXACT_NEW_FROZEN_CODE_ROOT')
    files = public(root / 'FROZEN_FILES_PUBLIC.json', manifest_sha256)['files']

    def framework(relative, directory=False):
        path = root / relative
        need(path.resolve() == path and not path.is_symlink() and
            (path.is_dir() if directory else path.is_file()), 'RACING_LAYOUT_FRAMEWORK_MEMBER')
        if not directory:
            s = path.lstat()
            need(relative in files and stat.S_ISREG(s.st_mode) and not s.st_mode & 0o022 and
                s.st_size == files[relative]['bytes'] and sha(path.read_bytes()) == files[relative]['sha256'],
                'RACING_LAYOUT_FROZEN_FRAMEWORK_PIN')
        return path

    layout_path = framework('PACKAGE_LAYOUT_PUBLIC.json')
    package = public(layout_path, files['PACKAGE_LAYOUT_PUBLIC.json']['sha256'])
    need(package['only_enabled_arm'] == 'DYNTEAM_RACING' and package['mode'] == 'smoke' and
        package['DYNTEAM_startup_held'] is True and package['Dev4_smoke_pass'] is False,
        'RACING_LAYOUT_ONLY_NEW_RACING_SYSTEM_SMOKE_PACKAGE')
    contracts = Path(contract_directory)
    need(contracts.is_absolute() and contracts.resolve() == contracts and contracts.is_dir() and
        contracts.is_relative_to(root) and contracts != root / 'contracts-two-arm-v4',
        'RACING_LAYOUT_NEW_REGISTERED_PAIRED_CONTRACT_NOT_BASELINE')
    relative = (contracts / 'SMOKE_PUBLIC_CONTRACT.json').relative_to(root).as_posix()
    contract_path = framework(relative)
    contract = public(contract_path, files[relative]['sha256'])
    rows = contract.get('arms', [])
    racing = [row for row in rows if row['arm'] == 'DYNTEAM_RACING']
    baseline = [row for row in rows if row['arm'] == 'DYNTEAM']
    need(contract.get('mode') == 'smoke' and len(rows) == 2 and len(racing) == len(baseline) == 1 and
        rows[0]['arm'] == 'DYNTEAM' and rows[1]['arm'] == 'DYNTEAM_RACING' and
        Path(baseline[0]['root']) / 'frozen-code' == root and
        racing[0]['root'] != baseline[0]['root'] and
        all(Path(row['root']).is_relative_to('/mnt/ptb-scratch2') or
            Path(row['root']).is_relative_to('/mnt/ptb-scratch') for row in rows),
        'RACING_LAYOUT_ONLY_NEW_PAIRED_SCRATCH_ARM_NAMESPACE')
    framework((contracts / 'CONTRACT_AND_NATIVE_ROLE_DIRECTORY_PINS_PUBLIC.json').relative_to(root).as_posix())
    framework('VERIFY_AND_INSTALL_IMPORTS.py')  # exact code-only helper present
    registry = root / 'FRAMEWORK_IMPORT_PINS_PUBLIC.json'
    rs = registry.lstat()
    need(registry.resolve() == registry and stat.S_ISREG(rs.st_mode) and
        rs.st_uid in (0, os.geteuid()) and not rs.st_mode & 0o022 and rs.st_nlink == 1,
        'RACING_LAYOUT_ALREADY_INSTALLED_FROZEN_IMPORT_REGISTRY')
    final = Path(final_configuration)
    need(final.is_absolute() and final.resolve() == final and final.is_file() and
        not final.is_symlink() and final.is_relative_to(Path(racing[0]['root'])) and
        final.name in ('PRIVATE_FINAL_CONFIGURATION.json',
            'PRIVATE_FINAL_CONFIGURATION_FRAMEWORK_COPY_V1.json'),
        'RACING_LAYOUT_NEW_ARM_FINAL_DESCRIPTOR_ONLY')
    pin(final_configuration_sha256)  # DO NOT read/decode/hash private config.
    scope = public(public_tool_scope, public_tool_scope_sha256, maximum=131072)
    need(set(scope) == PUBLIC_SCOPE_FIELDS and scope['original_public_tools_only'] is True and
        scope['official_evaluator_access'] is False and scope['private_reference_access'] is False,
        'RACING_LAYOUT_ORIGINAL_PUBLIC_TOOLS_NOT_OFFICIAL_OR_PRIVATE_ORACLE')
    for k in ('original_v2_tool_binding_sha256', 'original_count14_catalogue_sha256', 'native_scope_sha256'):
        pin(scope[k])
    guest = framework('racing-guest-code', directory=True)
    guest_map = framework('racing-guest-code/CODE_MAP_PUBLIC.json')
    custodian = framework('runtime-v1-msg237-held20-v1-msg237-prefix21-v1/smoke_racing_tools_game_exec_custodian.py')
    paths = {'native_source_tree': 'upstream-70e2ca54',
        'guarded_agent_directory': 'native-guarded-control-source-v2',
        'compiled_router_directory': 'native-clock-overlay-v1/dist',
        'public_router_source': 'runtime-v1-msg237-held20-v1-msg237-prefix21-v1/router',
        'spawn_source': 'native-host-orchestration-v4/count14_spawn_loop.sh',
        'original_task_host_source': 'original-framework-msg237-held20-v1/task-host.py'}
    for name in paths.values():
        framework(name, directory=(root / name).is_dir())
    source = framework('DYNTEAM_ORIGINAL_SOURCE_PATH_BINDING_PUBLIC.json')
    need(files[source.relative_to(root).as_posix()]['sha256'] == SOURCE_BINDING_SHA256,
        'RACING_LAYOUT_SAME_ORIGINAL_APPROVED_TASK_PATH_PROOF')
    value = dict(schema='count14-dynteam-racing-smoke-code-layout-v1', code_root=str(root),
        contract_directory=str(contracts), **{k: str(root / v) for k, v in paths.items()},
        framework_import_pins=dict(path=str(registry), sha256=sha(registry.read_bytes())),
        source_binding=dict(path=str(source), sha256=SOURCE_BINDING_SHA256),
        final_configuration=dict(path=str(final), sha256=final_configuration_sha256),
        racing_game_sources=dict(code_directory=str(guest), code_map_sha256=sha(guest_map.read_bytes()),
            custodian_path=str(custodian), custodian_sha256=sha(custodian.read_bytes()),
            public_tool_scope=scope))
    output = root / 'INSTALL_RACING_CODE_LAYOUT_PUBLIC.json'
    raw = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as out:
            out.write(raw)
            out.flush()
            os.fchmod(fd, 0o444)
            os.fsync(fd)
    finally:
        os.close(fd)
    return dict(layout=dict(path=str(output), sha256=sha(raw)), models=0, owner_created=False,
        scientific_input_or_FINAL_body_opened=False, Dev4_smoke_pass=False)


def main(argv=None):
    parser = argparse.ArgumentParser()
    for name in ('code-root', 'manifest-sha256', 'contract-directory', 'final-configuration',
                 'final-configuration-sha256', 'public-tool-scope', 'public-tool-scope-sha256'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(install(**vars(args)), sort_keys=True))
        return 0
    except Exception as error:
        locations, tb = [], error.__traceback__
        while tb:
            locations.append(dict(file=tb.tb_frame.f_code.co_filename, line=tb.tb_lineno,
                function=tb.tb_frame.f_code.co_name))
            tb = tb.tb_next
        print(json.dumps(dict(PUBLIC_code='RACING_NEW_LAYOUT_REFUSED_RETAIN_NO_RETRY',
            exception_type=type(error).__name__, locations=locations), sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
