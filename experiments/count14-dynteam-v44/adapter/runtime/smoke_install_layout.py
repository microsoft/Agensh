#!/usr/bin/env python3
"""Map fixed frozen package layout, never invent host/scientific facts."""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from pathlib import Path
import argparse,hashlib,json,os,stat

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(ok):
    if not ok:raise ValueError('DYNTEAM_SMOKE_FIXED_INSTALL_LAYOUT_REFUSED')
def write(path,value):
    raw=(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
    with os.fdopen(fd,'wb') as out:out.write(raw);out.flush();os.fsync(out.fileno())
    path.chmod(0o444)
    return {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest()}

def install(root,manifest_sha,final_configuration,final_sha):
    root=Path(root);require(root.is_absolute() and root.resolve()==root and root.is_dir())
    require(root.is_relative_to((_C14_SCRATCH + '/count14-dynteam-70e2ca54-smoke-20261105')) and
            root.name=='frozen-code')
    manifest=root/'FROZEN_FILES_PUBLIC.json';require(sha(manifest)==manifest_sha)
    registered=json.loads(manifest.read_bytes())['files']
    paths={'contract_directory':'contracts-two-arm-v4','native_source_tree':'upstream-70e2ca54',
        'guarded_agent_directory':'native-guarded-control-source-v2',
        'compiled_router_directory':'native-clock-overlay-v1/dist','public_router_source':'runtime-v1-msg237-held20-v1-msg237-prefix21-v1/router',
        'spawn_source':'native-host-orchestration-v4/count14_spawn_loop.sh',
        'original_task_host_source':'original-framework-msg237-held20-v1/task-host.py'}
    for relative in paths.values():
        path=root/relative;require(path.resolve()==path and path.exists())
        if path.is_file():require(relative in registered and sha(path)==registered[relative]['sha256'])
    registry=root/'FRAMEWORK_IMPORT_PINS_PUBLIC.json'
    s=registry.lstat();require(stat.S_ISREG(s.st_mode) and not registry.is_symlink() and not s.st_mode&0o022)
    final=Path(final_configuration)
    require(final.is_absolute() and final.resolve()==final and final.is_file() and
            final.is_relative_to(root.parent) and final.name=='PRIVATE_FINAL_CONFIGURATION.json' and
            len(final_sha)==64 and all(c in '0123456789abcdef' for c in final_sha))
    # Config is NOT decoded or hashed here. Original FINAL preflight owns the
    # trusted producer's exact descriptor and performs its normal verification.
    value={'schema':'count14-dynteam-smoke-code-layout-v1','code_root':str(root),
        **{k:str(root/v) for k,v in paths.items()},
        'framework_import_pins':{'path':str(registry),'sha256':sha(registry)},
        'source_binding':{'path':str(root/'DYNTEAM_ORIGINAL_SOURCE_PATH_BINDING_PUBLIC.json'),
            'sha256':'a063532a03a06939242c19c8e9aa72e7acaef37feb4c5d0247db085a6a4c6724'},
        'final_configuration':{'path':str(final),'sha256':final_sha}}
    result=write(root/'INSTALL_CODE_LAYOUT_PUBLIC.json',value)
    return {'layout':result,'models':0,'owner_created':False,'scientific_smoke_pass':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--code-root',required=True);p.add_argument('--manifest-sha256',required=True)
    p.add_argument('--final-configuration',required=True);p.add_argument('--final-configuration-sha256',required=True);a=p.parse_args()
    try:print(json.dumps(install(a.code_root,a.manifest_sha256,a.final_configuration,a.final_configuration_sha256),sort_keys=True))
    except Exception as e:
        locations=[];tb=e.__traceback__
        while tb:locations.append({'file':tb.tb_frame.f_code.co_filename,'line':tb.tb_lineno,'function':tb.tb_frame.f_code.co_name});tb=tb.tb_next
        print(json.dumps({'PUBLIC_code':'DYNTEAM_SMOKE_INSTALL_LAYOUT_REFUSED','exception_type':type(e).__name__,'locations':locations},sort_keys=True));raise SystemExit(2)
