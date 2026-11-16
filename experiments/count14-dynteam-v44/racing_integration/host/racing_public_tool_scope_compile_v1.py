"""Compile prospective public-tool bindings from frozen PUBLIC metadata.

This creates a NEW v2-reference document, NOT a historical runtime receipt.
It supplies the existing exact six-field PublicToolScope ABI without inventing
Docker/program/permission facts. Original live program, UID/caps, scope/census,
physical terminal and checkpoint guards remain mandatory and unchanged.
No question, task/source, private evaluator, code body or private config is read.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import stat

PROFILE_SHA256='8530bb5026d7ad9a77a5aa78a92d9d18426fb97b5236de75ccb6c278ae28aeba'
SCOPE_FIELDS={'original_v2_tool_binding_sha256','original_count14_catalogue_sha256',
              'native_scope_sha256','original_public_tools_only',
              'official_evaluator_access','private_reference_access'}
POLICY={'native_uid':10000,'native_gid':10000,'effective_capabilities':0,
    'allowed_program_workspace':'/work/.count14-racing',
    'approved_public_input_view':'/opt/count14-approved-input',
    'public_case_ABI':'cmd/stdin/files','official_evaluator_access':False,
    'private_reference_access':False,'public_execution_is_not_official_verdict':True,
    'new_model_transport_or_request_replay':False,
    'actual_program_UID_caps_census_mount_and_physical_guards_required':True}


def need(ok):
    if not ok:raise ValueError('RACING_PUBLIC_TOOL_PROSPECTIVE_BINDING_REFUSED')


def wire(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def digest(value):return hashlib.sha256(wire(value)).hexdigest()


def strict(raw):
    def pairs(items):
        value={}
        for key,item in items:need(key not in value);value[key]=item
        return value
    def reject(_):raise ValueError('RACING_PUBLIC_TOOL_NONFINITE_METADATA_REFUSED')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=reject)


def public(path,pin):
    path=Path(path);s=path.lstat()
    need(re.fullmatch('[0-9a-f]{64}',pin) and path.is_absolute() and path.resolve()==path and
        not path.is_symlink() and stat.S_ISREG(s.st_mode) and s.st_uid in (0,os.geteuid()) and
        s.st_nlink==1 and not s.st_mode&0o022 and s.st_size<=1024*1024)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        start=os.fstat(fd);raw=bytearray()
        while True:
            part=os.read(fd,65536)
            if not part:break
            raw.extend(part);need(len(raw)<=1024*1024)
        end=os.fstat(fd)
    finally:os.close(fd)
    stamp=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_mode,x.st_nlink)
    need(stamp(s)==stamp(start)==stamp(end)==stamp(path.lstat()) and
         hashlib.sha256(raw).hexdigest()==pin)
    return strict(raw)


def compile_scope(*,contract,contract_sha256,profile,manifest,manifest_sha256,trajectory):
    need(digest(contract)==contract_sha256 and
        contract.get('schema')=='count14-dynteam-two-arm-public-contract-v1' and
        contract.get('mode') in ('smoke','production') and contract['racing']['method']=='m7')
    rows=[row for row in contract['trajectories'] if row['trajectory_id']==trajectory]
    need(len(rows)==1 and rows[0]['arm']=='DYNTEAM_RACING' and rows[0]['request_cap']==13)
    reference=contract['v2_baseline_reference_protocol']
    need(digest(profile)==PROFILE_SHA256==reference['final_v21'] and
        profile['source_bundle_sha256']==reference['source_bundle'] and
        profile['model_policy_sha256']==reference['model_configuration'])
    catalogue=profile['evaluator_assets']['roster.json']['sha256']
    need(re.fullmatch('[0-9a-f]{64}',catalogue))
    generated_reference={'schema':'count14-new-generated-v2-public-tool-reference-binding-v1',
        'historical_runtime_receipt':False,'original_reference_pins':{key:reference[key] for key in
            ('cli','bridge','agensh_commit_tree','source_bundle','task_description')},
        'reference_provenance':'EXISTING_FROZEN_PUBLIC_V2_CONTRACT_NOT_CURRENT_PROGRAM_PROOF'}
    source_names=('racing-guest-code/CODE_MAP_PUBLIC.json',
        'racing-guest-code/smoke_racing_tools_public_runner.cjs',
        'racing-guest-code/smoke_racing_tools_game_runtime.py',
        'native-guarded-control-source-v2/acp-bridge.py')
    need(type(manifest) is dict and type(manifest.get('files')) is dict and
         re.fullmatch('[0-9a-f]{64}',manifest_sha256))
    pins={}
    for name in source_names:
        value=manifest['files'][name]
        need(set(value)=={'bytes','sha256'} and type(value['bytes']) is int and value['bytes']>0 and
             re.fullmatch('[0-9a-f]{64}',value['sha256']))
        pins[name]=value['sha256']
    native={'schema':'count14-prospective-native-public-tool-scope-v1',
        'contract_sha256':contract_sha256,'trajectory':trajectory,'root':rows[0]['root'],
        'original_count14_catalogue_sha256':catalogue,
        'frozen_manifest_sha256':manifest_sha256,'frozen_execution_code_sha256':pins,
        'policy':dict(POLICY),'current_Docker_or_program_qualified':False}
    scope={'original_v2_tool_binding_sha256':digest(generated_reference),
        'original_count14_catalogue_sha256':catalogue,'native_scope_sha256':digest(native),
        'original_public_tools_only':True,'official_evaluator_access':False,
        'private_reference_access':False}
    need(set(scope)==SCOPE_FIELDS)
    provenance={'schema':'count14-prospective-public-tool-scope-provenance-v1',
        'scope_sha256':digest(scope),'generated_v2_reference':generated_reference,
        'native_scope_definition':native,'catalogue_pin_source':
            'PUBLIC_ORIGINAL_FINAL_PROFILE_8530.evaluator_assets.roster.json.sha256',
        'catalogue_is_not_profile_digest':True,'catalogue_salt_is_stable_across_seeds_boots_rounds':True,
        'new_generated_reference_not_historical_runtime_receipt':True,
        'prospective_policy_not_current_Docker_program_or_permission_proof':True,
        'all_original_runtime_guards_remain_required':True,
        'actual_Dev4_or_public_execution_qualified':False,'models':0,'scientific_owners_created':0}
    return scope,provenance


def write_new(path,value):
    raw=wire(value);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
    with os.fdopen(fd,'wb') as out:out.write(raw);out.flush();os.fsync(out.fileno())
    path.chmod(0o444)
    return {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('code-root','manifest-sha256','contract','contract-sha256','trajectory','destination'):
        parser.add_argument('--'+arg,required=True)
    args=parser.parse_args()
    try:
        root=Path(args.code_root);contract_path=Path(args.contract);dest=Path(args.destination)
        need(root.is_absolute() and root.resolve()==root and root.is_dir() and
            contract_path.is_relative_to(root) and contract_path.name.endswith('PUBLIC_CONTRACT.json') and
            dest.is_absolute() and dest.parent.resolve()==dest.parent and
            dest.is_relative_to(root.parent) and not dest.exists() and not dest.is_symlink())
        manifest=public(root/'FROZEN_FILES_PUBLIC.json',args.manifest_sha256)
        contract=public(contract_path,args.contract_sha256)
        profile=public(root/'ORIGINAL_FINAL_PROFILE_8530_PUBLIC.json',PROFILE_SHA256)
        scope,provenance=compile_scope(contract=contract,contract_sha256=digest(contract),profile=profile,
            manifest=manifest,manifest_sha256=args.manifest_sha256,trajectory=args.trajectory)
        dest.mkdir(mode=0o700)
        generated=write_new(dest/'GENERATED_V2_PUBLIC_TOOL_REFERENCE_BINDING_PUBLIC.json',provenance['generated_v2_reference'])
        native=write_new(dest/'PROSPECTIVE_NATIVE_PUBLIC_TOOL_SCOPE_DEFINITION_PUBLIC.json',provenance['native_scope_definition'])
        result=write_new(dest/'PUBLIC_TOOL_SCOPE.json',scope)
        receipt=write_new(dest/'PUBLIC_TOOL_SCOPE_PROVENANCE_PUBLIC.json',provenance)
        print(json.dumps(dict(schema='count14-prospective-public-tool-scope-compiled-v1',
            public_tool_scope=result,provenance=receipt,generated_reference=generated,native_policy=native,
            prospective_only=True,actual_runtime_qualified=False,models=0,scientific_owners_created=0),sort_keys=True))
        return 0
    except Exception as error:
        frames=[];tb=error.__traceback__
        while tb:
            frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,
                               function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
        print(json.dumps(dict(PUBLIC_code='RACING_TOOL_SCOPE_COMPILE_REFUSED_RETAIN_PREFIX',
            exception_type=type(error).__name__,locations=frames,models=0,scientific_owners_created=0),sort_keys=True))
        return 2


if __name__=='__main__':raise SystemExit(main())
