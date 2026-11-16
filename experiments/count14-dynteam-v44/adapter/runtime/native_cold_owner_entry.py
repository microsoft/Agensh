#!/usr/bin/env python3
"""Unique retained cold-owner process entry; control metadata stdin/stdout only.

A frozen PUBLIC factory manifest supplies reviewed orchestration, never a task
or payload. Model activation is NOT implemented by the prefix. Failed phases
retain the same owner; EOF never abandons any launched native guest/custodian.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import select
import stat
import sys
import time

RETAINED_OWNER=None


def load_factory(manifest_path,expected_sha256):
    path=Path(manifest_path)
    if path.resolve()!=path or path.is_symlink() or path.stat().st_size>8192:
        raise ValueError('DYNTEAM_COLD_ENTRY_PUBLIC_MANIFEST_CANONICAL_BOUNDED')
    raw=path.read_bytes()
    metadata=path.stat()
    if not(stat.S_ISREG(metadata.st_mode) and not metadata.st_mode&0o022 and metadata.st_uid in (0,os.geteuid())):
        raise ValueError('DYNTEAM_COLD_ENTRY_PUBLIC_MANIFEST_OWNER_MODE')
    if hashlib.sha256(raw).hexdigest()!=expected_sha256:raise ValueError('DYNTEAM_COLD_ENTRY_PUBLIC_MANIFEST_PIN')
    row=json.loads(raw)
    if not(type(row) is dict and set(row)=={'schema','package_code_root','factory_path','factory_sha256','entry'} and
        row['schema']=='count14-native-cold-owner-public-factory-v1' and row['entry']=='create_prefix_owner'):
        raise ValueError('DYNTEAM_COLD_ENTRY_FIXED_FACTORY_SCHEMA')
    root,factory=Path(row['package_code_root']),Path(row['factory_path'])
    if not(root.is_absolute() and root.resolve()==root and root.is_dir() and factory.is_absolute() and
        factory.resolve()==factory and not factory.is_symlink() and factory.is_relative_to(root) and
        factory.name=='count14_native_owner_factory.py' and factory.stat().st_size<=262144 and
        hashlib.sha256(factory.read_bytes()).hexdigest()==row['factory_sha256']):
        raise ValueError('DYNTEAM_COLD_ENTRY_FROZEN_FRAMEWORK_FACTORY_ONLY')
    metadata=factory.stat()
    if not(stat.S_ISREG(metadata.st_mode) and not metadata.st_mode&0o022 and metadata.st_uid in (0,os.geteuid())):
        raise ValueError('DYNTEAM_COLD_ENTRY_FACTORY_OWNER_MODE')
    spec=importlib.util.spec_from_file_location('count14_frozen_cold_owner_factory',factory)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    function=getattr(module,'create_prefix_owner',None)
    if not callable(function):raise ValueError('DYNTEAM_COLD_ENTRY_FACTORY_FUNCTION_REQUIRED')
    return function


def attach(owner):
    global RETAINED_OWNER
    # Import AFTER the qualified factory sets its frozen dependency paths. -I
    # must not accidentally import a checkout from cwd or an ambient PYTHONPATH.
    from native_cold_owner import NativeColdOwner
    if type(owner) is not NativeColdOwner or RETAINED_OWNER is not None:
        raise ValueError('DYNTEAM_COLD_ENTRY_ONE_EXACT_SOURCE_OWNER_ONLY')
    RETAINED_OWNER=owner
    return owner.public()


def command(row):
    if RETAINED_OWNER is None:raise ValueError('DYNTEAM_COLD_ENTRY_ORIGINAL_OWNER_REQUIRED')
    allowed={'op','trajectory_id'}
    if type(row) is dict and row.get('op')=='PREPARE_SOURCE':allowed|={'binding_path','binding_sha256'}
    if type(row) is not dict or set(row)-allowed:
        raise ValueError('DYNTEAM_COLD_ENTRY_CONTROL_FIELDS_ONLY')
    op=row.get('op');owner=RETAINED_OWNER
    if op=='STATUS':return owner.public()
    if op=='ZERO_MODEL_PREFIX':return owner.zero_model_prefix()
    if op=='START_BOOTSTRAP':return owner.start_bootstrap(row['trajectory_id'])
    if op=='START_SYSTEM_HEALTH':return owner.start_system_health()
    if op=='PREPARE_SOURCE':return owner.prepare_source(row['trajectory_id'],binding_path=row['binding_path'],binding_sha256=row['binding_sha256'])
    if op=='POLL':return owner.poll(row.get('trajectory_id'))
    if op=='ACTIVATE':return owner.activate() # prefix refuses, cannot spoof proof with a flag
    raise ValueError('DYNTEAM_COLD_ENTRY_CONTROL_OPCODE_REFUSED')


def emit(value):
    print(json.dumps(value,sort_keys=True),flush=True)


def failure(error):
    frames=[];tb=error.__traceback__
    while tb:
        frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
    return dict(PUBLIC_code='DYNTEAM_COLD_ENTRY_CONTROL_FAILED_OWNER_RETAINED',exception_type=type(error).__name__,
                locations=frames,messages_locals_or_scientific_body_exported=False)


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--public-factory',required=True);parser.add_argument('--public-factory-sha256',required=True)
    parser.add_argument('--verify-factory-only',action='store_true')
    args=parser.parse_args(argv)
    try:
        create=load_factory(args.public_factory,args.public_factory_sha256)
        if args.verify_factory_only:
            emit(dict(FROZEN_PUBLIC_FACTORY_IMPORT_PASS=True,factory_create_function_called=False,
                      activation_requested=False));return 0
        emit(attach(create()))
        # The SAME owner must drain native control/refreshers/checkpoints even
        # when OPS sends no commands. Never block on readline waiting for an
        # operator while native receipt threads wait for this exact owner.
        fd=sys.stdin.fileno();os.set_blocking(fd,False);buffer=bytearray()
        while True:
            ready,_,_=select.select([fd],[],[],.1)
            if ready:
                raw=os.read(fd,4097)
                if not raw:break
                buffer.extend(raw)
                if len(buffer)>4096 and b'\n' not in buffer:
                    raise ValueError('DYNTEAM_COLD_ENTRY_CONTROL_LINE_BOUND')
                while b'\n' in buffer:
                    raw,_,remaining=buffer.partition(b'\n');buffer=bytearray(remaining)
                    try:
                        if len(raw)>4096:raise ValueError('DYNTEAM_COLD_ENTRY_CONTROL_LINE_BOUND')
                        emit(command(json.loads(raw)))
                    except Exception as error:emit(failure(error))
            if RETAINED_OWNER.core is not None:
                RETAINED_OWNER.poll()
                if RETAINED_OWNER.core.closed:
                    emit(RETAINED_OWNER.public());return 0
        owner=RETAINED_OWNER
        if (owner.core is not None and not owner.core.peers._peers and
            (owner.bootstrap is None or not owner.bootstrap.records)):
            # Only a genuinely unused zero-model prefix can close normally.
            owner.core.close_original_transports_after_drained();owner.ledger.close()
            emit(dict(ZERO_UNUSED_PREFIX_NORMAL_CLOSE=True,models=0));return 0
        emit(dict(CONTROL_EOF_SAME_OWNER_CUSTODY_RETAINED=True,models_NOT_inferred=True))
        while True:
            if owner.core is not None and owner.core.control is not None:
                owner.poll()
                if owner.core.closed:
                    emit(owner.public());return 0
            time.sleep(.1) # no locks; OPS may use approved exact normal TERM guards
    except Exception as error:
        emit(failure(error))
        if RETAINED_OWNER is not None:
            while True:time.sleep(.5) # retain partial custody; no automatic restart/teardown
        return 2


if __name__=='__main__':raise SystemExit(main())
