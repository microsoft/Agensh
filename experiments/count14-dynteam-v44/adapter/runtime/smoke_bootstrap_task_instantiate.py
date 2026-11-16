#!/usr/bin/env python3
"""Emit fixed factory/manifest/control plan from explicit PUBLIC bindings.

No SSH/Docker/key/task/source archive call. Does not construct an owner, refresh
proof timestamps, create scientific roots or claim a real smoke has passed.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import sys


def emit(bindings_path,bindings_sha256,*,destination):
    helper_path=Path(__file__).with_name('smoke_bootstrap_task_factory.py').resolve()
    spec=importlib.util.spec_from_file_location('count14_smoke_factory_emit_helper',helper_path)
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    b=helper.public(bindings_path,bindings_sha256)
    helper.require(set(b)==helper.FIELDS and b['schema']=='count14-dynteam-baseline-smoke-bindings-v1' and
        type(b['template_only']) is bool,'DYNTEAM_FACTORY_INSTANTIATION_EXACT_BINDINGS_SCHEMA')
    code_root=Path(b['code_root']);destination=Path(destination)
    helper.require(code_root.is_absolute() and code_root.resolve()==code_root and code_root.is_dir() and
        destination.is_absolute() and destination.parent.resolve()==destination.parent and
        destination.is_relative_to(code_root) and not destination.exists() and helper_path.is_relative_to(code_root),
        'DYNTEAM_FACTORY_NEW_FROZEN_PACKAGE_ENTRY_DIRECTORY')
    pin=b['framework_import_pins'];helper.descriptor(pin)
    registry=helper.public(pin['path'],pin['sha256'],8*1024*1024)
    helper_sha=hashlib.sha256(helper_path.read_bytes()).hexdigest()
    helper.require(any(Path(root['path'])/name==helper_path and sha==helper_sha
        for root in registry['roots'] for name,sha in root['files'].items()),
        'DYNTEAM_FACTORY_HELPER_INCLUDED_IN_COMPLETE_SOURCE_PINS')
    helper.verify_framework_imports(pin['path'],pin['sha256'],code_root=code_root)
    destination.mkdir(mode=0o700)
    factory=destination/'count14_native_owner_factory.py';manifest=destination/'FACTORY_PUBLIC.json'
    source='''# Generated frozen count14 SAME-owner factory; import NEVER constructs.
from pathlib import Path
import hashlib
import importlib.util
HELPER=Path(@HELPER@)
if HELPER.resolve()!=HELPER or hashlib.sha256(HELPER.read_bytes()).hexdigest()!=@HELPER_SHA@:
    raise ValueError('DYNTEAM_FACTORY_CONSTRUCTOR_SOURCE_PIN')
spec=importlib.util.spec_from_file_location('count14_frozen_actual_smoke_constructor',HELPER)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.verify_framework_imports(@REGISTRY@,@REGISTRY_SHA@,code_root=Path(@CODE_ROOT@))
module.verify_actual_import_graph()
def create_prefix_owner():
    return module.create_prefix_owner(@BINDINGS@,@BINDINGS_SHA@,code_root=Path(@CODE_ROOT@),
        factory_path=Path(__file__).resolve(),factory_manifest=Path(@MANIFEST@))
'''
    values={'HELPER':str(helper_path),'HELPER_SHA':helper_sha,'REGISTRY':pin['path'],'REGISTRY_SHA':pin['sha256'],
        'CODE_ROOT':str(code_root),'BINDINGS':str(Path(bindings_path)),'BINDINGS_SHA':bindings_sha256,'MANIFEST':str(manifest)}
    for key,value in values.items():source=source.replace('@'+key+'@',repr(value))
    def write(path,raw):
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
        try:
            with os.fdopen(fd,'wb',closefd=False) as out:out.write(raw);out.flush();os.fsync(fd)
            os.fchmod(fd,0o444)
        finally:os.close(fd)
    def document(path,value):write(path,(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode())
    write(factory,source.encode());factory_sha=hashlib.sha256(factory.read_bytes()).hexdigest()
    value={'schema':'count14-native-cold-owner-public-factory-v1','package_code_root':str(code_root),
        'factory_path':str(factory),'factory_sha256':factory_sha,'entry':'create_prefix_owner'}
    document(manifest,value);manifest_sha=hashlib.sha256(manifest.read_bytes()).hexdigest()
    baseline='TEMPLATE_REQUIRES_REAL_FROZEN_SMALL_CONTRACT'
    if not b['template_only']:
        c=b['contract']
        helper.require(c['filename']=='SMOKE_PUBLIC_CONTRACT.json',
                       'DYNTEAM_FACTORY_ONLY_EXACT_FROZEN_SMALL_CONTRACT_FILENAME')
        contract=helper._file_json({'path':str(Path(c['directory'])/c['filename']),
            'sha256':c['sha256'],'canonical_sha256':c['canonical_sha256']})
        rows=[r['trajectory_id'] for r in contract['trajectories'] if r['arm']=='DYNTEAM']
        helper.require(len(rows)==1,'DYNTEAM_FACTORY_SINGLE_BASELINE_SMALL_SMOKE');baseline=rows[0]
    plan={'schema':'count14-native-baseline-smoke-control-plan-v1','template_only':b['template_only'],
        'factory_manifest':str(manifest),'factory_manifest_sha256':manifest_sha,
        'import_verification_is_not_source_or_scientific_smoke_proof':True,
        'constructor_creates_one_held_owner_no_model_no_container_no_source_replay':True,
        'initial_commands':[{'op':'START_SYSTEM_HEALTH'},{'op':'POLL'}],
        'wait_for_original_resource_public_SYSTEM_admission_open':True,
        'one_source_command_only_after_real_fresh_resource_pointer':{'op':'PREPARE_SOURCE','trajectory_id':baseline,
            'binding_path':b['source_binding']['path'],'binding_sha256':b['source_binding']['sha256']},
        'then_poll_same_owner_until':'PREPARED_BASELINE_SMOKE_RACING_HELD',
        'activation_command':{'op':'ACTIVATE'},'retain_partial_owner_no_retry':True,
        'system_cost_not_experiment_ledger':True,'RACING_remains_startup_held':True}
    document(destination/'INITIAL_CONTROL_PLAN_PUBLIC.json',plan)
    return {'schema':'count14-native-smoke-factory-instantiation-public-v1','factory':str(factory),
        'factory_sha256':factory_sha,'manifest':str(manifest),'manifest_sha256':manifest_sha,
        'bindings_sha256':bindings_sha256,'template_only':b['template_only'],'owner_created':False,
        'models':0,'scientific_input_or_provider_key_opened':False}


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--bindings',required=True);p.add_argument('--bindings-sha256',required=True)
    p.add_argument('--destination',required=True);a=p.parse_args(argv)
    try:
        value=emit(a.bindings,a.bindings_sha256,destination=a.destination)
        print(json.dumps(value,sort_keys=True));return 0
    except BaseException as e:
        frames=[];tb=e.__traceback__
        while tb:frames.append({'file':tb.tb_frame.f_code.co_filename,'line':tb.tb_lineno,'function':tb.tb_frame.f_code.co_name});tb=tb.tb_next
        print(json.dumps({'PUBLIC_code':'DYNTEAM_FACTORY_INSTANTIATION_REFUSED','exception_type':type(e).__name__,'locations':frames},sort_keys=True))
        return 2

if __name__=='__main__':raise SystemExit(main())
