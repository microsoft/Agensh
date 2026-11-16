"""OPS-only complete original x48 framework copy before owner or model release.

Exact original cp -a --reflink=auto, one retained Popen, natural wait; no shell,
kill, retry, overwrite, privilege escalation or old-source mutation. Metadata
walks prevent symlink escape; no package/scientific body tree hash is required.
"""
from __future__ import annotations
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

SOURCE = Path((_C14_SCRATCH + '/ag30v2x48/final-runtime/framework_root'))
CP = Path('/usr/bin/cp')
MAX_METADATA_NODES = 200000
MAX_METADATA_SECONDS = 60
PROFILE_SHA256 = '8530bb5026d7ad9a77a5aa78a92d9d18426fb97b5236de75ccb6c278ae28aeba'
DEPENDENCY_SHA256 = '08637ac7e2fee08807d3547f1e6ff44f476e58488c81fc8a2bc94476347e6e07'
FINAL_FIELDS = frozenset(('native_directory','evaluator_root','image_mapping','image_mapping_sha256',
    'dependency_freeze_sha256','framework_root','docker_config','python_command','environment','credential_source'))
SAFE_ENV_KEYS = frozenset(('PATH','HOME','LANG','LC_ALL','TMPDIR','LD_LIBRARY_PATH','VIRTUAL_ENV',
    'SSL_CERT_FILE','SSL_CERT_DIR','REQUESTS_CA_BUNDLE','PYTHONDONTWRITEBYTECODE','PYTHONNOUSERSITE',
    'LITELLM_LOCAL_MODEL_COST_MAP','DOCKER_HOST','DOCKER_CONFIG','PYTHONPATH'))


def need(ok, code):
    if not ok:raise RuntimeError(code)


def strict(raw):
    def pairs(items):
        value={}
        for k,v in items:need(k not in value,'FRAMEWORK_DUPLICATE_JSON_FIELD');value[k]=v
        return value
    def no_constant(_):raise RuntimeError('FRAMEWORK_NONFINITE_JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=no_constant)


def wire(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()


def canonical(path):
    path=Path(path);need(path.is_absolute() and path.resolve()==path and not path.is_symlink(),
                        'FRAMEWORK_CANONICAL_NONLINK_PATH');return path


def stamp(path):
    path=Path(path);s=path.lstat()
    return {'device':s.st_dev,'inode':s.st_ino,'size':s.st_size,'mtime_ns':s.st_mtime_ns,
        'ctime_ns':s.st_ctime_ns,'mode':stat.S_IMODE(s.st_mode),'uid':s.st_uid,'gid':s.st_gid,'nlink':s.st_nlink}


def pinned_json(path,pin,*,private=False):
    need(type(pin) is str and re.fullmatch('[0-9a-f]{64}',pin),'FRAMEWORK_PUBLIC_RAW_SHA_REQUIRED')
    path=canonical(path);s=path.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_uid in (0,os.geteuid()) and s.st_nlink==1 and
         not s.st_mode&0o022 and s.st_size<=4*1024*1024 and
         (not private or stat.S_IMODE(s.st_mode)==0o600 and s.st_uid==os.geteuid()),
         'FRAMEWORK_PINNED_METADATA_OWNER_TYPE_MODE')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        start=os.fstat(fd);raw=bytearray()
        while True:
            part=os.read(fd,65536)
            if not part:break
            raw.extend(part);need(len(raw)<=4*1024*1024,'FRAMEWORK_METADATA_SIZE')
        end=os.fstat(fd)
    finally:os.close(fd)
    identity=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_mode,x.st_nlink)
    need(identity(s)==identity(start)==identity(end)==identity(path.lstat()) and sha(raw)==pin,
         'FRAMEWORK_PINNED_METADATA_CHANGED')
    return strict(raw)


def write_new(path,value,mode=0o400):
    raw=wire(value)
    with Path(path).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    os.chmod(path,mode);return sha(raw)


def scan_tree(root):
    """lstat/readlink only; never read regular-file contents or follow links."""
    root=canonical(root);need(root.is_dir(),'FRAMEWORK_EXACT_DIRECTORY_REQUIRED')
    entries={};todo=[root];started=time.monotonic();seen=0
    while todo:
        need(time.monotonic()-started<=MAX_METADATA_SECONDS,'FRAMEWORK_METADATA_TIME_BOUND_UNKNOWN')
        directory=todo.pop();children=[]
        with os.scandir(directory) as iterator:
            for item in iterator:
                seen+=1
                need(seen<=MAX_METADATA_NODES and time.monotonic()-started<=MAX_METADATA_SECONDS,
                     'FRAMEWORK_METADATA_NODE_OR_TIME_BOUND_UNKNOWN')
                children.append(item)
        for item in sorted(children,key=lambda x:x.name):
            path=directory/item.name;s=path.lstat();relative=str(path.relative_to(root))
            need(not any(p in ('private-context','count14_candidates') for p in path.relative_to(root).parts),
                 'FRAMEWORK_FORBIDDEN_SCIENTIFIC_STATE_METADATA_NO_COPY')
            row={'stat':stamp(path)}
            if stat.S_ISDIR(s.st_mode):row['kind']='directory';todo.append(path)
            elif stat.S_ISREG(s.st_mode):row['kind']='regular'
            elif stat.S_ISLNK(s.st_mode):
                target=os.readlink(path)
                need(not Path(target).is_absolute() and path.resolve(strict=True).is_relative_to(root),
                     'FRAMEWORK_SYMLINK_ESCAPE_OR_DANGLING_REFUSED')
                row.update(kind='symlink',target=target)
            else:need(False,'FRAMEWORK_SPECIAL_FILE_NOT_ORIGINAL_PACKAGE_DATA')
            entries[relative]=row
    return entries


def structural_projection(entries):
    return {name:{'kind':row['kind'],'size':row['stat']['size'] if row['kind']=='regular' else None,
        'mode':row['stat']['mode'],'target':row.get('target')} for name,row in entries.items()}


def patch_configuration(configuration, *, contract_sha256, trajectory, destination):
    need(type(configuration) is dict and set(configuration) in (
        {'schema','contract_sha256','trajectories'}, {'schema','contract_sha256','trajectories','reference_profile'}) and
        configuration['schema']=='count14-dynteam-smoke-final-controller-v1' and
        configuration['contract_sha256']==contract_sha256 and type(configuration['trajectories']) is dict and
        set(configuration['trajectories'])=={trajectory},'FRAMEWORK_ONLY_NEW_SELECTED_ARM_FINAL_CONFIGURATION')
    old=configuration['trajectories'][trajectory]
    need(type(old) is dict and set(old)==FINAL_FIELDS and old['dependency_freeze_sha256']==DEPENDENCY_SHA256 and
        type(old['environment']) is dict and set(old['environment'])<=SAFE_ENV_KEYS,
        'FRAMEWORK_ONLY_ORIGINAL_INFRASTRUCTURE_CONFIGURATION_NO_SECRET_ENV')
    new=copy.deepcopy(configuration);new['trajectories'][trajectory]['framework_root']=str(destination)
    restored=copy.deepcopy(new);restored['trajectories'][trajectory]['framework_root']=old['framework_root']
    need(restored==configuration,'FRAMEWORK_ONLY_ONE_CONFIGURATION_FIELD_CHANGED')
    return new



def wait_naturally(child):
    pending=None
    while True:
        try:return child.wait(),pending
        except (KeyboardInterrupt,InterruptedError) as error:
            # Keep the SAME accepted copy handle. No signal/kill/relaunch.
            if pending is None:pending=error


def copy_and_wait(source,destination,receipt):
    need(not destination.exists() and not destination.is_symlink(),'FRAMEWORK_FRESH_DESTINATION_NO_OVERWRITE')
    argv=[str(CP),'-a','--reflink=auto','--',str(source),str(destination)]
    receipt('COPY_INTENT',argv=argv)
    child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,close_fds=True)
    # Retain this actual Popen before fallible receipt I/O. Any I/O error still
    # waits the same accepted child naturally, never starts another cp.
    try:
        receipt('COPY_STARTED',copy_pid=child.pid)
    except BaseException:
        wait_naturally(child);raise
    code,pending=wait_naturally(child)
    receipt('COPY_TERMINAL',copy_pid=child.pid,actual_exit_code=code,wait_observed=True)
    if pending is not None:raise pending
    need(code==0,'FRAMEWORK_ORIGINAL_CP_FAILED_RETAIN_NO_RETRY')
    return child



def selected_row(contract,arm):
    need(arm in ('DYNTEAM','DYNTEAM_RACING'),'FRAMEWORK_EXACT_DEPLOYMENT_ARM_SELECTOR')
    rows=[r for r in contract['trajectories'] if r['arm']==arm]
    arms=[r for r in contract['arms'] if r['arm']==arm]
    need(len(rows)==len(arms)==1,'FRAMEWORK_ONE_EXACT_SELECTED_ARM_B1')
    root=Path(rows[0]['root']);arm_root=Path(arms[0]['root'])
    need(root.is_absolute() and root.is_relative_to(Path((_C14_SCRATCH))) and
         root==arm_root/'b1' and not SOURCE.is_relative_to(root) and not root.is_relative_to(SOURCE),
         'FRAMEWORK_ONLY_CURRENT_CONTRACT_SELECTED_SCRATCH2_B1_ROOT')
    return rows[0]


def boundary_kind(boundary):
    phase=boundary.get('phase')
    if phase=='BEFORE_OWNER_CONSTRUCTION':
        need(boundary.get('owner_created') is False and
             boundary.get('ops_deployment_lease_held_through_copy') is True and
             boundary.get('owner_start_prohibited_through_copy') is True,
             'FRAMEWORK_ACTUAL_OPS_PREOWNER_DEPLOYMENT_EXCLUSION_REQUIRED')
        evidence=boundary.get('deployment_evidence_sha256');kind='OPS_DEPLOYMENT_EXCLUSION_NO_OWNER'
    elif phase=='BEFORE_FIRST_MODEL_RELEASE':
        need(boundary.get('owner_created') is True and
             boundary.get('same_owner_model_admission_held_through_copy') is True,
             'FRAMEWORK_ACTUAL_EXISTING_OWNER_MODEL_HOLD_REQUIRED')
        evidence=boundary.get('original_owner_evidence_sha256');kind='ORIGINAL_OWNER_MODEL_ADMISSION_HELD'
    else:need(False,'FRAMEWORK_ONLY_PREOWNER_OR_BEFORE_FIRST_MODEL_BOUNDARY')
    need(type(evidence) is str and re.fullmatch('[0-9a-f]{64}',evidence),
         'FRAMEWORK_ACTUAL_OPS_OR_OWNER_METADATA_EVIDENCE_SHA_REQUIRED')
    return kind


def execute(a):
    contract=pinned_json(a.contract,a.contract_sha256)
    need(contract.get('mode')=='smoke' and contract.get('schema')=='count14-dynteam-two-arm-public-contract-v1' and
        contract['v2_baseline_reference_protocol']['final_v21']==PROFILE_SHA256,
        'FRAMEWORK_ONLY_EXACT_CURRENT_SMOKE_CONTRACT')
    row=selected_row(contract,a.arm);trajectory=row['trajectory_id'];root=canonical(row['root']);contract_sha=sha(wire(contract))
    need(root.is_dir(),'FRAMEWORK_NEW_SELECTED_ARM_ROOT_ALREADY_PREPARED')
    destination=root/'final-framework-dependencies-v1';home=root/'final-framework-copy-v1'
    need(not destination.exists() and not destination.is_symlink() and not home.exists() and not home.is_symlink(),
        'FRAMEWORK_NEW_EXACT_COPY_AND_RECEIPT_HOMES_NO_RETRY')
    source=canonical(SOURCE);need(source==SOURCE and source.is_dir(),'FRAMEWORK_ONLY_PROTECTED_ORIGINAL_X48_SOURCE')
    boundary=pinned_json(a.ops_boundary_public,a.ops_boundary_sha256)
    need(boundary.get('schema')=='count14-smoke-original-framework-copy-boundary-public-v1' and
        boundary.get('contract_sha256')==contract_sha and boundary.get('trajectory')==trajectory and
        type(boundary.get('original_SEARCH_sent_requests')) is int and boundary['original_SEARCH_sent_requests']==0 and
        type(boundary.get('original_AUX_sent_requests')) is int and boundary['original_AUX_sent_requests']==0 and
        boundary.get('source_runtime_dependencies_only') is True and boundary.get('source_no_active_writers') is True and
        boundary.get('destination_no_active_writers') is True and boundary.get('scientific_state_absent') is True and
        boundary.get('source')==str(SOURCE) and boundary.get('destination')==str(destination) and
        boundary.get('source_root_stat')==stamp(source) and type(boundary.get('trajectory_root_stat')) is dict and
        all(boundary['trajectory_root_stat'].get(k)==stamp(root)[k] for k in ('device','inode','mode','uid','gid')),
        'FRAMEWORK_REQUIRES_ACTUAL_OPS_CURRENT_NO_WRITER_AND_MODEL_HOLD_PROOF')
    proof_kind=boundary_kind(boundary)
    observed=datetime.fromisoformat(boundary['observed_at'].replace('Z','+00:00'))
    need(observed.tzinfo is not None and -30<=(datetime.now(timezone.utc)-observed).total_seconds()<=300,
        'FRAMEWORK_FRESH_OPS_BOUNDARY_REQUIRED')
    configuration_path=canonical(a.final_configuration)
    need(configuration_path.is_relative_to(root),'FRAMEWORK_INPUT_IS_NEW_SELECTED_ARM_FINAL_CONFIG_NOT_OLD_LAUNCH')
    configuration=pinned_json(configuration_path,a.final_configuration_sha256,private=True)
    patched=patch_configuration(configuration,contract_sha256=contract_sha,trajectory=trajectory,destination=destination)
    source_root_before=stamp(source);source_before=scan_tree(source)
    need(stamp(source)==source_root_before,'FRAMEWORK_SOURCE_CHANGED_DURING_METADATA_SAFETY_WALK')
    home.mkdir(mode=0o700);sequence=0
    def receipt(kind,**extra):
        nonlocal sequence
        sequence+=1
        value={'schema':'count14-smoke-complete-framework-copy-event-public-v1','kind':kind,'sequence':sequence,
            'at_utc':datetime.now(timezone.utc).isoformat(),'source':str(source),'destination':str(destination),
            'contract_sha256':contract_sha,'trajectory':trajectory,'model_calls':0,'evaluator_runs':0,'Docker_actions':0,
            'overwrite_delete_or_retry':False,**extra}
        write_new(home/(str(sequence).zfill(4)+'-'+kind+'.json'),value)
    receipt('BOUNDARY_ACCEPTED',ops_boundary={'path':str(canonical(a.ops_boundary_public)),'sha256':a.ops_boundary_sha256},
            source_root_stat=source_root_before,source_metadata_entries=len(source_before),
            body_treehash_required=False,boundary_proof_kind=proof_kind,proof_is_actual_OPS_metadata_not_new_authority=True)
    started=time.monotonic();child=copy_and_wait(source,destination,receipt)
    copy_elapsed=time.monotonic()-started;postcheck_started=time.monotonic()
    source_after=scan_tree(source);destination_entries=scan_tree(destination)
    need(stamp(source)==source_root_before and source_after==source_before,
         'FRAMEWORK_ORIGINAL_SOURCE_METADATA_CHANGED_NO_CONFIG_PUBLISH')
    need(structural_projection(source_before)==structural_projection(destination_entries),
         'FRAMEWORK_COMPLETE_DESTINATION_METADATA_SHAPE_DIFFERS_NO_CONFIG_PUBLISH')
    config_path=home/'PRIVATE_FINAL_CONFIGURATION_FRAMEWORK_COPY_V1.json'
    config_sha=write_new(config_path,patched,mode=0o600)
    receipt('NEW_CONFIGURATION_PUBLISHED',configuration={'path':str(config_path),'sha256':config_sha},
        previous_configuration={'path':str(configuration_path),'sha256':a.final_configuration_sha256},
        only_configuration_field_changed='framework_root',dependency_freeze_sha256=DEPENDENCY_SHA256,
        source_root_stat=stamp(source),destination_root_stat=stamp(destination),
        complete_metadata_entries=len(destination_entries),copy_elapsed_seconds=copy_elapsed,postcheck_elapsed_seconds=time.monotonic()-postcheck_started,
        actual_copy_exit_code=child.returncode,body_treehash_required=False,
        original_B_runtime_import_registry_unchanged=True,complete_package_runtime_qualified=False)
    return {'schema':'count14-smoke-complete-framework-copy-result-public-v1',
        'configuration':{'path':str(config_path),'sha256':config_sha},'framework_root':str(destination),
        'receipt_home':str(home),'only_configuration_field_changed':'framework_root',
        'dependency_freeze_sha256':DEPENDENCY_SHA256,'original_configuration_modified':False,
        'original_B_runtime_import_registry_unchanged':True,'complete_package_runtime_qualified':False,
        'original_child_verify_imports_is_not_complete_engine_ABI_proof':True,
        'required_next':'ORIGINAL_SAME_ENTRY_FINAL_PREFLIGHT_AND_ZERO_MODEL_RUNTIME_PROOF_BY_OPS',
        'model_calls':0,'evaluator_runs':0,'Docker_actions':0}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--arm',choices=('DYNTEAM','DYNTEAM_RACING'),default='DYNTEAM')
    for name in ('contract','contract-sha256','final-configuration','final-configuration-sha256',
                 'ops-boundary-public','ops-boundary-sha256'):p.add_argument('--'+name,required=True)
    a=p.parse_args()
    try:print(json.dumps(execute(a),sort_keys=True));return 0
    except BaseException as error:
        code=error.args[0] if type(error) is RuntimeError and error.args else None
        if type(code) is not str or re.fullmatch('[A-Z][A-Z0-9_]{0,159}',code) is None:code='FRAMEWORK_RETAIN_PARTIAL_NO_RETRY'
        print(json.dumps({'schema':'count14-smoke-framework-copy-sanitized-failure-public-v1',
            'exception_type':type(error).__name__,'PUBLIC_code':code,'partial_artifacts_retained':True,
            'no_forced_stop_or_copy_retry':True,'metadata_entries':None,'source_stability_proven':None,
            'destination_completeness_proven':None,'model_calls':0,'evaluator_runs':0,'Docker_actions':0},sort_keys=True));return 2


if __name__=='__main__':raise SystemExit(main())
