#!/usr/bin/env python3
"""Finite55s -I metadata sampler; import frozen factory, NEVER construct owner."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import signal
import sys
PUBLIC_FAILURE_PATH=None


def main(argv=None):
    global PUBLIC_FAILURE_PATH
    p=argparse.ArgumentParser();p.add_argument('--intent',required=True);p.add_argument('--intent-sha256',required=True)
    p.add_argument('--factory',required=True);p.add_argument('--factory-sha256',required=True)
    p.add_argument('--bootstrap-sha256',required=True);args=p.parse_args(argv)
    def alarm(*_):raise TimeoutError('DYNTEAM_FINITE_METADATA_SAMPLE_DEADLINE')
    signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,55)
    bootstrap=Path(__file__).with_name('native_cold_owner_entry.py')
    if bootstrap.is_symlink() or hashlib.sha256(bootstrap.read_bytes()).hexdigest()!=args.bootstrap_sha256:
        raise ValueError('DYNTEAM_RESOURCE_FROZEN_IMPORT_BOOTSTRAP_SHA')
    spec=importlib.util.spec_from_file_location('count14_resource_import_only_bootstrap',bootstrap)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    create=module.load_factory(args.factory,args.factory_sha256) # DO NOT call it: no second owner/DB/dispatcher
    from native_system_probe_child import read_control,append
    from native_resource_sampler import read_public,sample
    path=Path(args.intent);raw=read_control(path,131072)
    if path.name!='INTENT_PUBLIC.json' or hashlib.sha256(raw).hexdigest()!=args.intent_sha256:
        raise ValueError('DYNTEAM_RESOURCE_EXACT_INTENT_SHA')
    job=json.loads(raw);plan,plan_raw=read_public(Path(job['plan_path']))
    PUBLIC_FAILURE_PATH=path.with_name('FAILURE_PUBLIC.json')
    if hashlib.sha256(plan_raw).hexdigest()!=job['inventory_sha256']:
        raise ValueError('DYNTEAM_RESOURCE_FROZEN_PLAN_SHA')
    _exact18_path=Path(__file__).with_name('select_new_private_sampler.py')
    if _exact18_path.is_symlink() or hashlib.sha256(_exact18_path.read_bytes()).hexdigest()!='1b9224fd77818e660c1868af570be4eeffecad99e8c4c9e1752f72805a3b0884':
        raise ValueError('EXACT18_SAME_NEW_PRIVATE_SAMPLER_SELECTION_SHA')
    _exact18_spec=importlib.util.spec_from_file_location('count14_exact18_new_finite_sampler_selection',_exact18_path)
    _exact18_module=importlib.util.module_from_spec(_exact18_spec);_exact18_spec.loader.exec_module(_exact18_module)
    sample,_exact18_proof=_exact18_module.select(sample,job,plan)
    _provider_path=Path(__file__).with_name('gateway_pr1_v2.py')
    if _provider_path.resolve()!=_provider_path or _provider_path.is_symlink() or hashlib.sha256(_provider_path.read_bytes()).hexdigest()!='071fd2df5b3dd799c464575d0d95b4b9026fc01a421ce6e6bb83103dbc45bedc':
        raise ValueError('MSG220_FIXED_PRIVATE_PROVIDER_HEALTH_SOURCE')
    _provider_spec=importlib.util.spec_from_file_location('count14_msg220_private_provider_health',_provider_path)
    _provider_module=importlib.util.module_from_spec(_provider_spec);_provider_spec.loader.exec_module(_provider_module)
    sample,_provider_proof=_provider_module.select_sample(sample,job,plan)
    _complete_path=Path(__file__).with_name('complete_outside_retained_adapter_v2.py')
    if _complete_path.is_symlink()or hashlib.sha256(_complete_path.read_bytes()).hexdigest()!='12361bf88e0f6a0badf1141813c19e5af421d8b1accf13e7608afb565c60bd1f':
        raise ValueError('COMPLETE_RETAINED_SCOPE_SOURCE_PIN')
    _s=importlib.util.spec_from_file_location('new_only_complete_retained_sampler',_complete_path)
    _m=importlib.util.module_from_spec(_s);_s.loader.exec_module(_m)
    sample,_complete_proof=_m.select_sample(sample,job,plan)
    value=sample(job,plan)
    append(path.with_name('RESULT_PUBLIC.json'),dict(schema='count14-dynteam-finite-resource-result-v1',
        intent_sha256=args.intent_sha256,factory_constructor_called=False,owner=job['owner'],value=value))
    signal.setitimer(signal.ITIMER_REAL,0)
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        tb=error.__traceback__;frames=[]
        while tb:
            frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
        value=dict(PUBLIC_code='DYNTEAM_RESOURCE_SAMPLE_FAILED_NO_ADMISSION',exception_type=type(error).__name__,locations=frames)
        if PUBLIC_FAILURE_PATH is not None:
            try:
                from native_system_probe_child import append
                append(PUBLIC_FAILURE_PATH,value)
            except Exception:pass
        print(json.dumps(value))
        raise SystemExit(2)
