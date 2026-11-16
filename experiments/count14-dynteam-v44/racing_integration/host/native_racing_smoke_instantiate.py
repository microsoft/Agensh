#!/usr/bin/env python3
"""Actual RACING factory/control CLI from exact new PUBLIC frozen bindings.

No scientific root/model/source/key/container is created here. The emitted
same original -I entry genuinely imports the complete new framework graph;
its later explicit constructor creates only the original held owner.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os


def emit(bindings_path, bindings_sha256, *, destination):
    original_path = Path(__file__).with_name('smoke_bootstrap_task_factory.py').resolve()
    spec = importlib.util.spec_from_file_location('count14_racing_emit_original_guard', original_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    b = helper.public(bindings_path, bindings_sha256)
    helper.require(set(b) == helper.FIELDS | {'racing_game_sources'} and
        b['schema'] == 'count14-dynteam-racing-smoke-bindings-v1' and type(b['template_only']) is bool,
        'RACING_INSTANTIATE_EXACT_NEW_RACING_BINDING_SCHEMA')
    code_root, destination = Path(b['code_root']), Path(destination)
    racing_path = Path(__file__).with_name('native_racing_smoke_factory.py').resolve()
    helper.require(code_root.is_absolute() and code_root.resolve() == code_root and code_root.is_dir() and
        destination.is_absolute() and destination.parent.resolve() == destination.parent and
        destination.is_relative_to(code_root) and not destination.exists() and
        original_path.is_relative_to(code_root) and racing_path.is_relative_to(code_root),
        'RACING_INSTANTIATE_NEW_FROZEN_PACKAGE_FACTORY_DIRECTORY')
    descriptor = b['framework_import_pins']
    helper.descriptor(descriptor)
    registry = helper.public(descriptor['path'], descriptor['sha256'], 8 * 1024 * 1024)
    originals = {original_path: hashlib.sha256(original_path.read_bytes()).hexdigest(),
                 racing_path: hashlib.sha256(racing_path.read_bytes()).hexdigest()}
    for path, pin in originals.items():
        helper.require(any(Path(root['path']) / name == path and sha == pin
            for root in registry['roots'] for name, sha in root['files'].items()),
            'RACING_INSTANTIATE_BOTH_FACTORY_HELPERS_IN_FROZEN_REGISTRY')
    helper.verify_framework_imports(descriptor['path'], descriptor['sha256'], code_root=code_root)
    destination.mkdir(mode=0o700)
    factory = destination / 'count14_native_owner_factory.py'
    manifest = destination / 'FACTORY_PUBLIC.json'
    source = '''# Frozen RACING same-owner entry; import NEVER constructs.
from pathlib import Path
import hashlib
import importlib.util
ORIGINAL = Path(@ORIGINAL@)
RACING = Path(@RACING@)
for path, pin in ((ORIGINAL, @ORIGINAL_SHA@), (RACING, @RACING_SHA@)):
    if path.resolve() != path or hashlib.sha256(path.read_bytes()).hexdigest() != pin:
        raise ValueError('RACING_FACTORY_EXACT_FROZEN_HELPER_SOURCE_PIN')
spec = importlib.util.spec_from_file_location('count14_racing_original_cold_guard', ORIGINAL)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
guard.verify_framework_imports(@REGISTRY@, @REGISTRY_SHA@, code_root=Path(@CODE_ROOT@))
spec = importlib.util.spec_from_file_location('count14_actual_racing_cold_factory', RACING)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.verify_actual_racing_import_graph()
def create_prefix_owner():
    return module.create_racing_prefix_owner(@BINDINGS@, @BINDINGS_SHA@,
        code_root=Path(@CODE_ROOT@), factory_path=Path(__file__).resolve(),
        factory_manifest=Path(@MANIFEST@))
'''
    values = dict(ORIGINAL=str(original_path), RACING=str(racing_path), ORIGINAL_SHA=originals[original_path],
        RACING_SHA=originals[racing_path], REGISTRY=descriptor['path'], REGISTRY_SHA=descriptor['sha256'],
        CODE_ROOT=str(code_root), BINDINGS=str(Path(bindings_path)), BINDINGS_SHA=bindings_sha256,
        MANIFEST=str(manifest))
    for key, value in values.items():
        source = source.replace('@' + key + '@', repr(value))

    def write(path, raw):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
        try:
            with os.fdopen(fd, 'wb', closefd=False) as out:
                out.write(raw)
                out.flush()
                os.fchmod(fd, 0o444)
                os.fsync(fd)
        finally:
            os.close(fd)

    def document(path, value):
        write(path, (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode())

    write(factory, source.encode())
    factory_sha = hashlib.sha256(factory.read_bytes()).hexdigest()
    document(manifest, dict(schema='count14-native-cold-owner-public-factory-v1',
        package_code_root=str(code_root), factory_path=str(factory), factory_sha256=factory_sha,
        entry='create_prefix_owner'))
    manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
    trajectory = 'TEMPLATE_REQUIRES_REAL_FROZEN_PAIRED_SMALL_CONTRACT'
    if not b['template_only']:
        c = b['contract']
        helper.require(c['filename'] == 'SMOKE_PUBLIC_CONTRACT.json',
                       'RACING_INSTANTIATE_EXACT_PAIRED_SMALL_CONTRACT_FILENAME')
        contract = helper._file_json(dict(path=str(Path(c['directory']) / c['filename']),
            sha256=c['sha256'], canonical_sha256=c['canonical_sha256']))
        racing = [row for row in contract['trajectories'] if row['arm'] == 'DYNTEAM_RACING']
        helper.require(len(racing) == 1 and racing[0]['request_cap'] == 13 and
            racing[0]['search_tokens'] == 1000000 and racing[0]['checkpoints_tokens'] == [500000, 1000000],
            'RACING_INSTANTIATE_EXACT_REGISTERED_1M_TWO_K3_SMALL_SCOPE')
        trajectory = racing[0]['trajectory_id']
    plan = dict(schema='count14-native-racing-smoke-control-plan-v1', template_only=b['template_only'],
        factory_manifest=str(manifest), factory_manifest_sha256=manifest_sha,
        initial_commands=[dict(op='START_SYSTEM_HEALTH'), dict(op='POLL')],
        wait_for_original_resource_public_SYSTEM_admission_open=True,
        one_source_command_only_after_real_fresh_resource_pointer=dict(op='PREPARE_SOURCE', trajectory_id=trajectory,
            binding_path=b['source_binding']['path'], binding_sha256=b['source_binding']['sha256']),
        then_poll_same_owner_until='PREPARED_RACING_SMOKE_BASELINE_HELD', activation_command=dict(op='ACTIVATE'),
        DYNTEAM_remains_startup_held=True, same_original_owner_exact_type=True,
        helpers_zero_model_prepared_before_activation=8, system_cost_not_experiment_ledger=True,
        actual_game_not_inferred_from_helper_prepare=True, game_bottleneck_active_seconds_unchanged=600,
        original_graph_acceptance_separate_from_racing_mechanism_and_fully_retired=True,
        retain_partial_owner_no_retry=True)
    document(destination / 'INITIAL_CONTROL_PLAN_PUBLIC.json', plan)
    return dict(schema='count14-native-racing-smoke-factory-instantiation-public-v1',
        factory=str(factory), factory_sha256=factory_sha, manifest=str(manifest), manifest_sha256=manifest_sha,
        bindings_sha256=bindings_sha256, template_only=b['template_only'], owner_created=False, models=0,
        scientific_input_or_provider_key_opened=False)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--bindings', required=True)
    parser.add_argument('--bindings-sha256', required=True)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args(argv)
    try:
        result = emit(args.bindings, args.bindings_sha256, destination=args.destination)
        print(json.dumps(result, sort_keys=True))
        return 0
    except BaseException as error:
        locations, tb = [], error.__traceback__
        while tb:
            locations.append(dict(file=tb.tb_frame.f_code.co_filename, line=tb.tb_lineno,
                                  function=tb.tb_frame.f_code.co_name))
            tb = tb.tb_next
        print(json.dumps(dict(PUBLIC_code='RACING_FACTORY_INSTANTIATION_REFUSED',
            exception_type=type(error).__name__, locations=locations), sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
