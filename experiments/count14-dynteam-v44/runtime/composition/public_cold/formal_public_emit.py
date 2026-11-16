#!/usr/bin/env python3
"""Emit ORIGINAL unique entry factory/manifest; never create/activate an owner."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from formal_public_common import need, sha, save, BINDINGS_SCHEMA
from formal_public_factory import base_helper, base_fields, validate_bindings


def emit(bindings_path, bindings_sha256, *, destination):
    helper = base_helper()
    b = helper.public(bindings_path, bindings_sha256)
    need(type(b) is dict and set(b) == base_fields(helper) | {'racing_game_sources'} and
         b['schema'] == BINDINGS_SCHEMA and type(b['template_only']) is bool,
         'FORMAL_EMIT_EXACT_NEW_PUBLIC_BINDINGS_SCHEMA')
    root, dest = Path(b['code_root']), Path(destination)
    helper_path = Path(__file__).resolve().with_name('formal_public_factory.py')
    need(root.is_absolute() and root.resolve() == root and root.is_dir() and
         dest.is_absolute() and dest.parent.resolve() == dest.parent and dest.is_relative_to(root) and
         not dest.exists() and helper_path.is_relative_to(root), 'FORMAL_EMIT_ABSENT_FIXED_FACTORY_IN_CODE_ROOT')
    descriptor = b['framework_import_pins']; helper.descriptor(descriptor)
    registry = helper.public(descriptor['path'], descriptor['sha256'], 8 * 1024 * 1024)
    helper.verify_framework_imports(descriptor['path'], descriptor['sha256'], code_root=root)
    # The emitter and all new adapter modules must be covered by the same map.
    for path in (helper_path, Path(__file__).resolve(), helper_path.with_name('formal_public_common.py')):
        need(any(Path(row['path']) / name == path and pin == sha(path)
            for row in registry['roots'] for name, pin in row['files'].items()),
            'FORMAL_EMIT_EACH_NEW_FRAMEWORK_MODULE_IN_UNIFIED_PIN_MAP')
    contract = None
    if not b['template_only']:
        validate_bindings(helper, b, code_root=root)
        from formal_public_common import read_contract
        contract = read_contract(helper, b['contract'], code_root=root)
    dest.mkdir(mode=0o700)
    factory, manifest = dest / 'count14_native_owner_factory.py', dest / 'FACTORY_PUBLIC.json'
    original_helper = Path(helper.__file__).resolve()
    source = '''# Prospective formal SAME-owner factory: import never creates owner.
from pathlib import Path
import hashlib,importlib.util,sys
ORIGINAL=Path(@ORIGINAL@)
HELPER=Path(@HELPER@)
for path,pin in ((ORIGINAL,@ORIGINAL_SHA@),(HELPER,@HELPER_SHA@)):
    if path.resolve()!=path or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=pin:
        raise ValueError('FORMAL_FACTORY_EXACT_FROZEN_HELPER_SOURCE_PIN')
spec=importlib.util.spec_from_file_location('count14_formal_original_import_guard',ORIGINAL)
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
guard.verify_framework_imports(@REGISTRY@,@REGISTRY_SHA@,code_root=Path(@CODE_ROOT@))
spec=importlib.util.spec_from_file_location('count14_actual_formal_cold_factory',HELPER)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.verify_actual_formal_import_graph()
def create_prefix_owner():
    return module.create_prefix_owner(@BINDINGS@,@BINDINGS_SHA@,code_root=Path(@CODE_ROOT@),
        factory_path=Path(__file__).resolve(),factory_manifest=Path(@MANIFEST@))
'''
    values = dict(ORIGINAL=str(original_helper), HELPER=str(helper_path), ORIGINAL_SHA=sha(original_helper),
        HELPER_SHA=sha(helper_path), REGISTRY=descriptor['path'], REGISTRY_SHA=descriptor['sha256'],
        CODE_ROOT=str(root), BINDINGS=str(Path(bindings_path)), BINDINGS_SHA=bindings_sha256, MANIFEST=str(manifest))
    for k, v in values.items():
        source = source.replace('@' + k + '@', repr(v))
    raw = source.encode()
    fd = os.open(factory, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as out:
            out.write(raw); out.flush(); os.fsync(fd)
        os.fchmod(fd, 0o444)
    finally:
        os.close(fd)
    md = save(manifest, dict(schema='count14-native-cold-owner-public-factory-v1', package_code_root=str(root),
        factory_path=str(factory), factory_sha256=sha(factory), entry='create_prefix_owner'))
    rows = [] if contract is None else contract['trajectories']
    plan = save(dest / 'INITIAL_CONTROL_PLAN_PUBLIC.json', dict(
        schema='count14-formal100m-same-owner-control-plan-WIP-v1', template_only=b['template_only'],
        factory_manifest=md, initial_commands=[dict(op='START_SYSTEM_HEALTH'), dict(op='POLL')],
        only_after_real_fresh_resource_pointer=[dict(op='PREPARE_SOURCE', trajectory_id=r['trajectory_id'],
            binding_path=b['source_binding']['path'], binding_sha256=b['source_binding']['sha256']) for r in rows],
        wait_until='PREPARED_ALL_SIX_ORIGINAL_OBJECTS_MODELS_HELD', activation_command=dict(op='ACTIVATE'),
        activation_count=1, retained_original_owner=True, missing_host_facts_never_fabricated=True,
        no_pending_as_active=True, no_prefix_or_request_replay=True, formal_release_authorization=False,
        native_idle_watchdog_remaining=True, natural_first_point_and_0live_semantics_remaining=True,
        allowance_and_n_lt3_producer_remaining=True, real_Dev4_smoke_and_formal_qualification_remaining=True))
    return dict(schema='count14-formal100m-factory-emission-WIP-v1', factory=str(factory), factory_sha256=sha(factory),
        manifest=md, control_plan=plan, template_only=b['template_only'], owner_created=False, models=0,
        formal_delivery=False, formal_runtime_qualification=False)


def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('--bindings',required=True); p.add_argument('--bindings-sha256',required=True)
    p.add_argument('--destination',required=True); a=p.parse_args(argv)
    try:
        print(json.dumps(emit(a.bindings,a.bindings_sha256,destination=a.destination),sort_keys=True));return 0
    except Exception as error:
        frames,tb=[],error.__traceback__
        while tb:
            frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
        print(json.dumps(dict(PUBLIC_code='FORMAL_FACTORY_EMISSION_REFUSED',exception_type=type(error).__name__,locations=frames),sort_keys=True));return 2
if __name__=='__main__':raise SystemExit(main())
