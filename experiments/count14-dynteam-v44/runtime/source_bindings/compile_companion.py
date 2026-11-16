"""Compile the actual six-Tester companion after execution CODE is frozen.

Pure PUBLIC metadata/code operation. No host facts, current program proof,
owner, model, queue, ledger, source asset or experiment admission is created.
The companion is outside CODE, contains the existing exact schema, and is
accepted by the unmodified original read_sources before a receipt is issued.
"""
from pathlib import Path
import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import re
import stat
import sys

GUARD = 'runtime-v1-msg237-held20-v1-msg237-prefix21-v1/smoke_bootstrap_task_factory.py'
GUARD_SHA = '71de11f1bb3f778b9d4afc7ce965d18fd4f7ed9dcf49bcb6fdbf622cea9dd29f'
CONTRACT_SHA = '9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'
CONTRACT_CANONICAL = '9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'
MODULES = {
    'formal_tester_cold': 'formal-tester-current-declaration-msg238-v3/formal_tester_cold.py',
    'tester_public_tool_scope_compile': 'formal100m-tester-tool-scope-wip-v1-msg237-held20-v1-msg237-testersuffix-v1-msg237-prefix21-v1/tester_public_tool_scope_compile.py',
}
PINNED = {
    'runtime-v1-msg237-held20-v1-msg237-prefix21-v1/racing_public_tool_scope_compile_v1.py': '6dcf60b98f1fe05e3cc605958e26d17ff5234e4fed003246f3f8c93cbd9be1f7',
    'runtime-v1-msg237-held20-v1-msg237-prefix21-v1/smoke_racing_tools_public_exec.py': '573fcdae1a1c847300cfaedbf498f41849a532400600528ebb2bf86223e217ea',
    'runtime-v1-msg237-held20-v1-msg237-prefix21-v1/formal_count14_tester_public.py': 'd930818edd3e30d0adf3039b2274a50ec8a83c133fee8b1d35c5ec051aeb78d6',
    'formal100m-tester-public-binding-wip-v1-msg237-held20-v1-msg237-prefix21-v1/formal_tester_public_binding.py': 'cce864f6961d96e2135ccc5fa15e7b52fc6537d729761aa3fc77e65581818666',
    'formal100m-tester-public-binding-wip-v1-msg237-held20-v1-msg237-prefix21-v1/PROGRAM_REGISTRATION_PROTOCOL.md': 'fb067afe2791ed00c609f42ab3b5aef5acfa759fb8e1218d40595848fe785e51',
    'formal100m-tester-public-binding-wip-v1-msg237-held20-v1-msg237-prefix21-v1/tester-native-runner/smoke_racing_tools_public_runner.cjs': '8c4a1194bd925f730ade182cb7f6e4c2c37844d77b368ba09340f241744f97dc',
}


def need(ok, code):
    if not ok:
        raise ValueError(code)


def pin(path, expected):
    path = Path(path)
    need(type(expected) is str and re.fullmatch('[0-9a-f]{64}', expected), 'TESTER_COMPANION_PIN_FORMAT')
    s = path.lstat()
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink() and
         stat.S_ISREG(s.st_mode) and s.st_uid in (0, os.geteuid()) and
         s.st_nlink == 1 and not s.st_mode & 0o022 and s.st_size <= 8 * 1024 * 1024,
         'TESTER_COMPANION_FROZEN_REGULAR_FILE')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        start = os.fstat(fd)
        with os.fdopen(os.dup(fd), 'rb') as stream:
            raw = stream.read(s.st_size + 1)
        end = os.fstat(fd)
    finally:
        os.close(fd)
    stamp = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns, x.st_mode, x.st_nlink)
    need(stamp(s) == stamp(start) == stamp(end) == stamp(path.lstat()) and
         len(raw) == s.st_size and hashlib.sha256(raw).hexdigest() == expected,
         'TESTER_COMPANION_STABLE_FD_SOURCE_PIN')
    return raw


def save(path, value):
    raw = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest())


def compile_companion(*, code_root, manifest_sha256, import_registry, import_registry_sha256, destination):
    root, dest, registry_path = Path(code_root), Path(destination), Path(import_registry)
    need(root.is_absolute() and root.resolve() == root and root.is_dir() and
         dest.is_absolute() and dest.parent.resolve() == dest.parent and
         not dest.is_relative_to(root) and not os.path.lexists(dest) and
         not any(part.startswith('OWN') for part in (*root.parts, *dest.parts)),
         'TESTER_COMPANION_NEW_EXTERNAL_METADATA_LEAF_NOT_OWN_OR_IN_CODE')
    manifest_path = root / 'formal-tester-current-declaration-msg238-v3' / 'CURRENT_EXECUTION_DECLARATION_PUBLIC.json'
    manifest = json.loads(pin(manifest_path, manifest_sha256))
    need(set(manifest) == {'schema', 'files'} and manifest['schema'] == 'count14-frozen-package-files-v1' and
         type(manifest['files']) is dict, 'TESTER_COMPANION_ORIGINAL_EXECUTION_MAP_SCHEMA')
    # Read only fixed framework code/protocol metadata, never arbitrary members
    # of the execution map or any native prompt/task/candidate body.
    for relative, expected in {GUARD: GUARD_SHA, **PINNED}.items():
        record = manifest['files'][relative]
        raw = pin(root / relative, expected)
        need(record == dict(bytes=len(raw), sha256=expected), 'TESTER_COMPANION_EXECUTION_AND_EXACT_ORIGINAL_SOURCE_AGREE')
    spec = importlib.util.spec_from_file_location('count14_companion_original_import_guard', root / GUARD)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    pin(registry_path, import_registry_sha256)
    guard.verify_framework_imports(registry_path, import_registry_sha256, code_root=root)
    modules = {}
    for name, relative in MODULES.items():
        record = manifest['files'][relative]
        pin(root / relative, record['sha256'])
        module = importlib.import_module(name)
        need(Path(module.__file__).resolve() == root / relative, 'TESTER_COMPANION_NO_FOREIGN_PRELOADED_MODULE')
        modules[name] = module
    cold = modules['formal_tester_cold']
    compiler = modules['tester_public_tool_scope_compile']
    original = compiler.original(root)
    contract = original.public(root / 'PRODUCTION_PUBLIC_CONTRACT.json', CONTRACT_SHA)
    need(original.digest(contract) == CONTRACT_CANONICAL and len(contract['trajectories']) == 6 and
         [row['arm'] for row in contract['arms']] == ['DYNTEAM', 'DYNTEAM_RACING'],
         'TESTER_COMPANION_ORIGINAL_SIX_PAIRED_PRODUCTION_CONTRACT')
    profile = original.public(root / 'ORIGINAL_FINAL_PROFILE_8530_PUBLIC.json', original.PROFILE_SHA256)
    rows, proofs = {}, {}
    for trajectory in contract['trajectories']:
        t = trajectory['trajectory_id']
        need(t not in rows, 'TESTER_COMPANION_NO_DUPLICATE_TRAJECTORY')
        scope, provenance = compiler.compile_tester(original, contract=contract, profile=profile,
            manifest=manifest, manifest_sha256=manifest_sha256, trajectory=t,
            binding_module=cold.BINDING, protocol=cold.PROTOCOL, runner=cold.RUNNER)
        rows[t] = dict(runner_host_path=str(root / cold.RUNNER), runner_sha256=manifest['files'][cold.RUNNER]['sha256'],
            protocol_host_path=str(root / cold.PROTOCOL), protocol_sha256=manifest['files'][cold.PROTOCOL]['sha256'],
            scope=scope)
        proofs[t] = provenance
    # No output until all six original compilers and fixed source checks pass.
    dest.mkdir(mode=0o700)
    companion = save(dest / 'TESTER_BINDINGS_PUBLIC.json', dict(schema=cold.SCHEMA,
        contract_sha256=CONTRACT_CANONICAL, frozen_execution_map_sha256=manifest_sha256, trajectories=rows))
    # Original strict consumer, not a local schema approximation; failure leaves
    # this unique prefix and no VERIFIED receipt, never automatic retry.
    sources, consumed = cold.read_sources(path=companion['path'], pin=companion['sha256'], code_root=root, contract=contract)
    need(set(sources) == set(rows) and consumed == dict(companion, frozen_execution_map_sha256=manifest_sha256),
         'TESTER_COMPANION_ORIGINAL_TYPED_CONSUMER_ALL_SIX')
    provenance = save(dest / 'TESTER_COMPANION_PROVENANCE_PUBLIC.json', dict(
        schema='count14-formal-six-tester-companion-compiled-v1', original_per_trajectory_provenance=proofs,
        companion=companion, execution_map=dict(path=str(manifest_path), sha256=manifest_sha256),
        framework_import_pins=dict(path=str(registry_path), sha256=import_registry_sha256),
        original_read_sources_accepted_all_six_typed_sources=True, original_six_field_tool_scope_ABI=True,
        ledger_schema_fee_UNKNOWN_or_retry_rules_changed=False, host_program_or_resource_proof_fabricated=False,
        runtime_qualified=False, production_admission=False, owners_created=0, models=0))
    return dict(PUBLIC_code='FORMAL_SIX_TESTER_COMPANION_COMPILED_ORIGINAL_CONSUMER_PASS',
        companion=companion, provenance=provenance, trajectories=6,
        runtime_qualified=False, production_admission=False, owners_created=0, models=0)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('code-root', 'manifest-sha256', 'import-registry', 'import-registry-sha256', 'destination'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args(argv)
    try:
        result = compile_companion(**vars(args))
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        locations, tb = [], error.__traceback__
        while tb:
            locations.append(dict(file=Path(tb.tb_frame.f_code.co_filename).name, line=tb.tb_lineno,
                                  function=tb.tb_frame.f_code.co_name))
            tb = tb.tb_next
        print(json.dumps(dict(PUBLIC_code='FORMAL_SIX_TESTER_COMPANION_REFUSED_RETAIN_NO_RETRY',
            exception_type=type(error).__name__, locations=locations, messages_or_locals_exported=False), sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
