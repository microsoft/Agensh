"""Closed resource lineage SOURCE ingredient for a real continuing receiver.

Old archived controls and every current-epoch control are preserved verbatim.
Only genuine registered Q3 state is accepted. No next-owner/T permission,
SYSTEM lineage restore, activation, model, financial write, Popen or cleanup.
The legacy source verifier is unchanged and remains fail closed.
"""
from dataclasses import asdict
from pathlib import Path
import copy
import hashlib
import importlib
import json
import os
import stat
import subprocess
import threading

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
from native_peer_registry import process_birth

PINS={
 'resource_epoch_continuing_producer_v6':'7fc0a72de729068fd42ce35dd4e50d80e2b0af07ce4ceede661a45e710b7dc73',
 'resource_epoch_transition_v3':'a4efa66a5fb85a4611a56844dfd15f8398107671935238de510088021be98a7d',
 'resource_epoch_archive_v2':'aa54e75ce3af53d4d257082e6159792d5a32b9966554c245fec7f371ae7e60c9',
 'retired_resource_history':'b756439360673e2e0cf96d7e0e3ae7f546cfd43fd7862e437894fc85cd3ade97',
}
LEAF='continued-resource-lineage-source-v1'
OWN_LEAF='OWN-continued-resource-lineage-source-v1'
_SEAL=object();_REG={};_CAPTURE_ATTEMPTS={};_PUBLISH_ATTEMPTS={}
MAX_BYTES=32*1024*1024
JOB_FIELDS={'schema','owner','contract_sha256','inventory_sha256','other_maximum_FP8_inflight',
 'core_home','new_root','trajectory_roots','ledger_path','system_registered','qualification_only','plan_path'}


def _pin(name,pin):
    m=importlib.import_module(name);p=Path(m.__file__);s=p.lstat()
    M.need(p.is_absolute() and p.resolve()==p and stat.S_ISREG(s.st_mode) and s.st_nlink==1
           and not s.st_mode&0o022 and hashlib.sha256(p.read_bytes()).hexdigest()==pin,
           'RESOURCE_LINEAGE_EXACT_FROZEN_ORIGINAL_MODULES')
    return m


def verify_sources():
    p=Path(__file__);s=p.lstat()
    M.need(p.is_absolute() and p.resolve()==p and stat.S_ISREG(s.st_mode) and s.st_nlink==1
           and not s.st_mode&0o022,'RESOURCE_LINEAGE_CANONICAL_FROZEN_SELF')
    modules={name:_pin(name,pin)for name,pin in PINS.items()}
    modules['resource_epoch_continuing_producer_v6'].verify_sources()
    return modules


def _json(value):return (json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()


def _budget(value):
    M.need(type(value)is ReadBudget,'RESOURCE_LINEAGE_ORIGINAL_FINITE_METADATA_BUDGET');value.check()


def _names(path,maximum,budget):
    out=set()
    for p in path.iterdir():
        budget.check();M.need(len(out)<maximum,'RESOURCE_LINEAGE_FINITE_EXACT_REGISTERED_LEAF_SET')
        out.add(p.name)
    return out


def _inspect(bound,budget,*,own):
    _budget(budget);modules=verify_sources()
    Q=modules['resource_epoch_continuing_producer_v6'];E=modules['resource_epoch_transition_v3']
    A=modules['resource_epoch_archive_v2'];R=modules['retired_resource_history']
    M.need(type(bound)is Q.ContinuingResourceReceiver and bound.OWN is own,
           'RESOURCE_LINEAGE_ONLY_ACTUAL_REGISTERED_RECEIVER_AND_NAMESPACE')
    er=Q._current(bound,budget);p=bound.producer;core=p.core
    M.need(not p.accepting and p.physical_clear() and not core.ledger.mutex._is_owned()
           and not core.queue.mutex._is_owned(),'RESOURCE_LINEAGE_ORIGINAL_ADMISSION_CLOSED_PHYSICAL_CLEAR_OUTSIDE_LOCKS')
    registered=bound.old_history._source.component('SYSTEM')['registered']
    if registered:
        M.need(Q._registered_SYSTEM(bound),'RESOURCE_LINEAGE_ACTUAL_ORIGINAL_SYSTEM_REGISTRY_REQUIRED')
        M.need(core.system_health.accepting is False and core.system_health.physical_clear(),
               'RESOURCE_LINEAGE_SYSTEM_MUST_ALSO_CLOSE_ADMISSION_AND_RETAIN_PHYSICAL_TERMINALS')
    else:
        M.need(not hasattr(core,'system_health'),'RESOURCE_LINEAGE_ABSENT_SYSTEM_REMAINS_ABSENT')
    old=bound.old_history._snapshot['configuration']['sequence']
    M.need(type(old)is int and type(p.sequence)is int and p.sequence==old+len(p.records)
           and 0<=old<p.sequence<=99999999,'RESOURCE_LINEAGE_FULL_GLOBAL_SEQUENCE_WITHOUT_FAKE_OLD_HANDLES')
    files={};total=0
    def read(path,*,mode,expected=None,limit=131072):
        nonlocal total
        path=Path(path)
        if str(path)in files:
            raw,ref=files[str(path)]
            M.need(expected is None or ref==expected,'RESOURCE_LINEAGE_CONFLICTING_SAME_CONTROL_REFERENCE')
            return raw,ref
        raw,ref=A._read(path,mode=mode,limit=limit,budget=budget,expected=expected)
        total+=len(raw);M.need(total<=MAX_BYTES,'RESOURCE_LINEAGE_FINITE_TOTAL_REGISTERED_METADATA_BYTES')
        files[str(path)]=(raw,ref);return raw,ref
    archive=er['archive']
    for ref in (archive._manifest,archive._issued):
        read(ref['path'],mode=ref['identity'][4]&0o777,expected=ref,limit=MAX_BYTES)
    for row in archive._body['copies']:
        ref=row['copy'];read(ref['path'],mode=ref['identity'][4]&0o777,expected=ref,limit=MAX_BYTES)
    for ref in er['refs'].values():read(ref['path'],mode=0o600,expected=ref)
    plan_raw,plan_ref=read(p.plan_path,mode=0o444)
    M.need(hashlib.sha256(plan_raw).hexdigest()==p.inventory_sha and R._object(plan_raw)==p.plan,
           'RESOURCE_LINEAGE_EXACT_ORIGINAL_FROZEN_PLAN')
    rows=[];latest=None
    expected_home={Path(r['directory']).name for r in bound.old_history._source.component('resource')['records']}
    M.need(p.records[0]['child'] is er['child'] and p.records[0]['directory']==er['root']
           and p.records[0]['job']==er['job'],'RESOURCE_LINEAGE_SAME_ACTUAL_FIRST_EPOCH_NOT_RECONSTRUCTED_POPEN')
    old_views=bound.old_history._source.component('resource')['history_control_bindings']['record_directories']
    for view in old_views:
        path=Path(view['path'])
        M.need(path.parent==p.home and A._directory(path,budget)==view['identity']
               and _names(path,4,budget)==set(view['files']),
               'RESOURCE_LINEAGE_ALL_OLD_REGISTERED_RECORDS_RETAINED_NO_UNKNOWN_FILES')
    for index,row in enumerate(p.records):
        seq=old+index+1;directory=row['directory'];child=row['child'];state=row['state']
        M.need(state in ('OBSERVATION_PUBLISHED','FAILED_RETAINED','NOT_STARTED')
               and (child is None or type(child)is subprocess.Popen and child.poll()is not None),
               'RESOURCE_LINEAGE_REAL_TERMINAL_RECORDS_NO_RUNNING_OR_FAKE_CHILD')
        job=row['job']
        M.need(type(job)is dict and set(job)==JOB_FIELDS and job['owner']==asdict(bound.birth)
               and job['contract_sha256']==p.contract_sha and job['inventory_sha256']==p.inventory_sha
               and job['qualification_only']is own and job['system_registered']is registered
               and job['core_home']==str(core.home) and job['new_root']==core.contract['arms'][0]['root']
               and job['trajectory_roots']=={t:r['root']for t,r in core.rows.items()}
               and job['ledger_path']==str(core.ledger.home/'ledger.sqlite') and job['plan_path']==str(p.plan_path)
               and job['other_maximum_FP8_inflight']==p.plan['other_maximum_FP8_inflight'],
               'RESOURCE_LINEAGE_EVERY_JOB_SAME_REAL_NEW_OWNER_PLAN_ALLOCATION_AND_REGISTERED_SYSTEM')
        if index:
            M.need(directory==p.home/f'{seq:08d}',
                   'RESOURCE_LINEAGE_SUBSEQUENT_ORIGINAL_GLOBAL_SEQUENCE_DIRECTORY')
            expected_home.add(directory.name);A._directory(directory,budget)
            names=_names(directory,4,budget)
            M.need('INTENT_PUBLIC.json'in names and names<={'INTENT_PUBLIC.json','RESULT_PUBLIC.json',
                   'FAILURE_PUBLIC.json','PUBLISHED_PUBLIC.json'},'RESOURCE_LINEAGE_NO_UNKNOWN_CURRENT_CONTROL')
            if state=='NOT_STARTED':
                M.need(child is None and names=={'INTENT_PUBLIC.json'},'RESOURCE_LINEAGE_NOT_STARTED_HAS_NO_FAKE_EXIT0')
            else:
                M.need(type(child)is subprocess.Popen and type(child.returncode)is int,
                       'RESOURCE_LINEAGE_ORIGINAL_SAME_POPEN_REAL_PHYSICAL_RETURNCODE')
            controls={n:read(directory/n,mode=0o600)[1]for n in sorted(names)}
        else:
            M.need(state=='OBSERVATION_PUBLISHED' and child.returncode==0,
                   'RESOURCE_LINEAGE_FIRST_EPOCH_IS_ACTUAL_ORIGINAL_COMPLETE')
            controls={Path(ref['path']).name:ref for ref in er['refs'].values()}
        intent_raw,intent=read(directory/'INTENT_PUBLIC.json',mode=0o600)
        M.need(intent['sha256']==row['intent_sha256'] and R._object(intent_raw)==job,
               'RESOURCE_LINEAGE_EXACT_ORIGINAL_RAM_INTENT_HASH_AND_BODY')
        if state=='OBSERVATION_PUBLISHED':
            if index:M.need(set(controls)=={'INTENT_PUBLIC.json','RESULT_PUBLIC.json','PUBLISHED_PUBLIC.json'}
                            and child.returncode==0,'RESOURCE_LINEAGE_PUBLISHED_REQUIRES_TRUE_CHILD0_AND_FULL_CONTROLS')
            result_raw,_=read(directory/'RESULT_PUBLIC.json',mode=0o600)
            published_raw,_=read(directory/'PUBLISHED_PUBLIC.json',mode=0o600)
            result=R._object(result_raw);published=R._object(published_raw)
            M.need(set(result)=={'schema','intent_sha256','factory_constructor_called','owner','value'}
                   and result['schema']=='count14-dynteam-finite-resource-result-v1'
                   and result['owner']==asdict(bound.birth) and result['intent_sha256']==intent['sha256']
                   and result['factory_constructor_called']is False,
                   'RESOURCE_LINEAGE_EXACT_ORIGINAL_RESULT_NOT_HANDWRITTEN_GREEN_VALUE')
            value=result['value'];encoded=_json(value)
            from native_resource_sampler import allocation_envelope
            M.need(value['dynteam_allocation']==allocation_envelope(job) and value['qualification_only']is own
                   and value['models']==0 and (own or value['OWN_fixture_host_projection_used']is False)
                   and published['restamped']is False and published['source_observed_ns']==value['observed_ns']
                   and published['value_sha256']==hashlib.sha256(encoded).hexdigest(),
                   'RESOURCE_LINEAGE_ORIGINAL_ALLOCATION_NO_RESTAMP_OR_SYNTHETIC_SUCCESS')
            latest=(seq,encoded)
        rows.append(dict(global_sequence=seq,kind='ORIGINAL_CADENCE'if index else'ORIGINAL_NEW_OWNER_EPOCH',
            state=state,actual_child_pid=None if child is None else child.pid,
            actual_child_returncode=None if child is None else child.returncode,
            actual_child_birth=asdict(er['child_birth'])if not index else None,
            subsequent_child_birth_not_reconstructed=index>0,job=copy.deepcopy(job),controls=controls))
    M.need(_names(p.home,len(expected_home)+1,budget)==expected_home,
           'RESOURCE_LINEAGE_NO_MISSING_OLD_OR_CURRENT_OR_UNKNOWN_PRODUCER_HOME_LEAF')
    raw,pointer=read(core.home/'resources/COHORT_RESOURCES_PUBLIC.json',mode=0o444)
    M.need(latest is not None and raw==latest[1] and pointer['sha256']==p.last_published,
           'RESOURCE_LINEAGE_CURRENT_POINTER_EXACT_LATEST_TRUE_PUBLISHED_RESULT')
    body=dict(schema='count14-continuing-resource-closed-lineage-source-ingredient-v1',OWN=own,
        source_owner_birth=asdict(bound.birth),original_source_owner_birth=asdict(bound.old_history._source.old_owner_birth),
        contract_sha256=p.contract_sha,configuration=dict(plan=plan_ref,inventory_sha256=p.inventory_sha,
        sourcehome=str(p.home),global_sequence=p.sequence,next_due=p.next_due,accepting=p.accepting,
        last_published=p.last_published,original_public=p.public()),
        origin_service_snapshot=bound.old_history._source.snapshot(),origin_archive=archive._manifest,
        origin_archive_issued=archive._issued,epoch_controls=copy.deepcopy(er['refs']),records=rows,
        old_history_in_archive_not_relabelled=True,current_pointer=pointer,latest_published_global_sequence=latest[0],
        source_pins=dict(PINS),source_component_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        next_SOURCE_receiver_authority=False,SYSTEM_lineage_qualified=False,
        safe_to_TERM=False,paid_activation_authorized=False,whole_runnable_ready=False)
    # Every old source ref (including historical pointers) remains an immutable
    # fact INSIDE archived metadata. Only these actual current inputs are read.
    return body,files


class ResourceLineageSource:
    def __init__(self,*a,**k):raise M.PaidColdWait('RESOURCE_LINEAGE_NO_METADATA_CAPABILITY_CONSTRUCTOR')
    def snapshot(self,*,read_budget):
        row=_same(self,read_budget);return copy.deepcopy(row['body'])


def _same(cap,budget):
    _budget(budget);row=_REG.get(id(cap))
    M.need(type(cap)is ResourceLineageSource and type(row)is dict and row['cap']is cap and row['seal']is _SEAL
           and row['birth']==process_birth(os.getpid()) and row['thread']==threading.get_ident(),
           'RESOURCE_LINEAGE_SAME_REGISTERED_REAL_BIRTH_THREAD_AND_CAPABILITY')
    body,files=_inspect(row['bound'],budget,own=row['OWN'])
    M.need(body==row['body'] and files==row['files'],'RESOURCE_LINEAGE_CLOSED_SOURCE_CHANGED_RETAIN_NO_RETRY')
    return row


def _capture(bound,budget,own):
    _budget(budget)
    M.need(id(bound)not in _CAPTURE_ATTEMPTS,'RESOURCE_LINEAGE_ONE_CAPTURE_ATTEMPT_RETAIN_PARTIAL')
    body,files=_inspect(bound,budget,own=own)
    _CAPTURE_ATTEMPTS[id(bound)]=dict(bound=bound,phase='CAPTURED_NOT_PUBLISHED')
    cap=object.__new__(ResourceLineageSource)
    _REG[id(cap)]=dict(cap=cap,bound=bound,body=body,files=files,OWN=own,seal=_SEAL,
        birth=process_birth(os.getpid()),thread=threading.get_ident())
    return cap


def capture_registered(bound,*,read_budget):return _capture(bound,read_budget,False)
def capture_OWN(bound,*,read_budget):return _capture(bound,read_budget,True)


def publish(cap,*,read_budget):
    row=_same(cap,read_budget);key=id(cap)
    M.need(key not in _PUBLISH_ATTEMPTS,'RESOURCE_LINEAGE_ONE_PUBLICATION_ATTEMPT_NO_RETRY')
    A=importlib.import_module('resource_epoch_archive_v2');home=row['bound'].producer.core.home
    parent=home/(OWN_LEAF if row['OWN']else LEAF)
    _PUBLISH_ATTEMPTS[key]=dict(cap=cap,phase='PUBLISHING_RETAIN_ALL_PARTIALS')
    attempt=_PUBLISH_ATTEMPTS[key]
    try:
        if not os.path.lexists(parent):parent.mkdir(mode=0o700)
        A._directory(parent,read_budget)
        root=parent/f'{row["birth"].pid}-{row["birth"].start_ticks}';root.mkdir(mode=0o700)
        A._directory(root,read_budget);copies=root/'COPIES';copies.mkdir(mode=0o700)
        preserved=[]
        for i,(path,(raw,original))in enumerate(sorted(row['files'].items())):
            copied=A._write(copies/f'{i:06d}.raw',raw,read_budget)
            preserved.append(dict(original=original,copy=copied))
        body=dict(row['body'],preserved_control_copies=preserved,
                  publisher_module_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        reference=A._write(root/'SOURCE_PUBLIC.json',_json(body),read_budget)
        _same(cap,read_budget)
        marker=A._write(root/'ISSUED_PUBLIC.json',_json(dict(schema='count14-resource-lineage-ingredient-ISSUED-v1',
            OWN=row['OWN'],source=reference,source_owner_birth=asdict(row['birth']),
            source_snapshot_sha256=hashlib.sha256(_json(row['body'])).hexdigest(),
            no_new_receiver_or_T_authority=True)),read_budget)
        M.need(_names(root,3,read_budget)=={'SOURCE_PUBLIC.json','ISSUED_PUBLIC.json','COPIES'}
               and _names(copies,len(preserved)+1,read_budget)=={f'{i:06d}.raw'for i in range(len(preserved))},
               'RESOURCE_LINEAGE_PUBLISHED_EXACT_CLOSED_LEAF_SET')
        A._sync(copies);A._sync(root);A._sync(parent)
        _same(cap,read_budget)
        attempt.update(phase='ISSUED_SOURCE_INGREDIENT_ONLY',reference=reference,issued=marker)
        return dict(source=reference,issued=marker,copies=len(preserved),OWN=row['OWN'],
                    next_SOURCE_receiver_authority=False,whole_runnable_ready=False)
    except BaseException as error:
        attempt.update(phase='PARTIAL_RETAINED_NO_RETRY',failure_type=type(error).__name__);raise
