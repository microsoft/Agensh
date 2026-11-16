#!/usr/bin/env python3
"""Finite metadata-only first-natural bridge around original watchdog runtime.

Only native runtime consumes opaque stdin. Before first seal+enqueue+thaw, a
would-be original POST projects eligibility and is NOT sent. No payload, account
or message is stored. After release, original post_once/UNKNOWN rules run intact.
"""
from pathlib import Path
import hashlib
import importlib.util
import os
import sys

ORIGINAL_PIN='407691920dfbc86523ca429d01d383b6291c48e9226573a3ae902769d67241f5'


def original():
    p=Path(__file__).resolve().parents[1]/'formal100m-idle-watchdog-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-prefix21-v1/native_idle_runtime.py'
    if hashlib.sha256(p.read_bytes()).hexdigest()!=ORIGINAL_PIN:raise ValueError('FORMAL_NATURAL_ORIGINAL_IDLE_RUNTIME_PIN')
    spec=importlib.util.spec_from_file_location('count14_original_natural_idle_runtime',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def main(args):
    m=original();operation,home,*rest=args
    if operation!='POST':return m.main(args)
    home=Path(home);control,opened=m.admission(home)
    tick=m.read_json(home/'CURRENT_TICK_PUBLIC.json',8192)
    worker,*arguments=rest;role=m.role_for(control,worker)
    release=home/'FIRST_NATURAL_RELEASE_PUBLIC.json'
    if release.exists():
        proof=m.read_json(release,8192)
        m.need(proof.get('schema')=='count14-formal-native-first-natural-release-v1' and
               proof.get('control_home')==str(home) and proof.get('organization')==control['organization'] and
               proof.get('owner')==[control['owner_pid'],control['owner_start_ticks'],control['owner_boot_id']] and
               proof.get('snapshot_and_K3_queued')is True and proof.get('original_same_live_thaw_complete')is True,
               'FORMAL_NATURAL_ONLY_ORIGINAL_OWNER_ACTUAL_RELEASE')
        return m.main(args)
    # This is not a POST intent/UNKNOWN: not one byte is passed to curl.
    # The original shell already evaluated its unchanged account/idle/pending/
    # DM/recheck conditions. The metadata parent additionally requires all live
    # workers, fixed global pending COUNT, ledger/HTTP/membership physical zero.
    payload=sys.stdin.buffer.read(2*1024*1024+1)
    m.need(len(payload)<=2*1024*1024,'FORMAL_NATURAL_OPAQUE_NATIVE_STDIN_BOUND')
    if opened:
        name=f"N{tick['ordinal']:08d}-{role}-ELIGIBLE_PUBLIC.json";path=home/name
        value=dict(schema='count14-native-first-natural-eligible-v1',role=role,tick=tick['ordinal'],
            active_seconds=tick['active_seconds'],owner=[control['owner_pid'],control['owner_start_ticks'],control['owner_boot_id']],
            original_native_conditions_passed=True,POST_performed=False,payload_or_account_stored=False)
        try:m.append(path,value)
        except FileExistsError:m.need(m.read_json(path)==value,'FORMAL_NATURAL_DUPLICATE_NATIVE_ELIGIBILITY_MATCHES')
    return 75 # original fallback can only add the SAME metadata, never POST


if __name__=='__main__':
    try:raise SystemExit(main(sys.argv[1:]))
    except BaseException as error:
        if isinstance(error,SystemExit):raise
        print('{"PUBLIC_code":"FORMAL_NATURAL_METADATA_RUNTIME_FAILED","exception_type":"'+type(error).__name__+'"}',file=sys.stderr)
        raise SystemExit(2)
