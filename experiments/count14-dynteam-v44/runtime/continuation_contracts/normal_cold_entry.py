#!/usr/bin/env python3
"""Cold-only original entry code in ONE shared namespace; two exact new ops."""
from pathlib import Path
from types import FunctionType,ModuleType
import hashlib
import importlib.util
import json
import os
import stat

ENTRY_PIN='33b94ab50a4552b23e868508639a24cc534893aee6c08d7a5e5e9f0b9ec461aa'


def original_entry():
    p=Path(__file__).resolve().parents[1]/'racing-complete-cold-tree-v4-msg237-held20-v1-msg237-prefix21-v1/runtime-v1/native_cold_owner_entry.py'
    s=p.lstat()
    if not(p.resolve()==p and not p.is_symlink()and stat.S_ISREG(s.st_mode)and
           s.st_uid in(0,os.geteuid())and not s.st_mode&0o022 and
           hashlib.sha256(p.read_bytes()).hexdigest()==ENTRY_PIN):
        raise ValueError('NORMAL_SEALER_ENTRY_ORIGINAL_FIXED_COLD_SOURCE_PIN')
    spec=importlib.util.spec_from_file_location('count14_original_normal_sealer_entry_source',p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def private_namespace(original):
    if original.RETAINED_OWNER is not None:raise ValueError('NORMAL_SEALER_ENTRY_NEW_COLD_ONLY')
    shared=ModuleType('count14_normal_sealer_shared_cold_entry')
    shared.__dict__.update({k:v for k,v in vars(original).items()if k not in
        ('__file__','__spec__','__loader__','__name__','__package__')})
    namespace=vars(shared)
    for name in ('main','attach','command','load_factory','emit','failure'):
        old=getattr(original,name)
        fn=FunctionType(old.__code__,namespace,old.__name__,old.__defaults__,old.__closure__)
        fn.__kwdefaults__=old.__kwdefaults__;namespace[name]=fn
        if fn.__code__ is not old.__code__ or fn.__globals__ is not namespace:
            raise ValueError('NORMAL_SEALER_ENTRY_ORIGINAL_CODE_OBJECTS_ONE_SHARED_NAMESPACE')
    original_command=namespace['command']
    def command(row):
        if type(row)is dict and row.get('op')in('REQUEST_NORMAL_COLD_CANDIDATE','POLL_NORMAL_COLD_CANDIDATE'):
            if set(row)!={'op'}:raise ValueError('NORMAL_SEALER_ENTRY_NO_CALLER_PATH_FLAGS_OR_SCOPE')
            owner=namespace['RETAINED_OWNER']
            if owner is None:raise ValueError('NORMAL_SEALER_ENTRY_RETAINED_ORIGINAL_OWNER_REQUIRED')
            from normal_cold_sealer import NormalColdCandidateSealer
            sealer=getattr(owner,'normal_cold_sealer',None)
            if type(sealer)is not NormalColdCandidateSealer or sealer.owner is not owner:
                raise ValueError('NORMAL_SEALER_ENTRY_EXACT_COLD_REGISTERED_PRODUCER')
            return sealer.request()if row['op']=='REQUEST_NORMAL_COLD_CANDIDATE'else sealer.poll_once()
        return original_command(row)
    namespace['command']=command
    shared._original_command_code=original_command.__code__
    shared._source_module=original
    shared._code_object_names=('main','attach','load_factory','emit','failure')
    return shared


def main(argv=None):
    try:return private_namespace(original_entry()).main(argv)
    except Exception as error:
        frames=[];tb=error.__traceback__
        while tb:frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,
            function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
        print(json.dumps(dict(PUBLIC_code='NORMAL_SEALER_COLD_ENTRY_SOURCE_REFUSED',
            exception_type=type(error).__name__,locations=frames,models=0),sort_keys=True));return 2


if __name__=='__main__':raise SystemExit(main())
