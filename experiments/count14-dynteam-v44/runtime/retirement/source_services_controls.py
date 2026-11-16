"""Fixed source-control supplement for a later inert receiver, not a grant.

Only exact registered same-birth service/fence metadata. No schema/accounting
change, payload, raw SID/key/request text, process argv, pickle, private log or
scientific file. Retired-source evidence is distinct from new-owner authority.
"""
from dataclasses import asdict
from pathlib import Path
import copy
import hashlib
import importlib

from source_services_retirement import registered, need, ReadBudget, ram_lock

FENCE_SHA = '2f6e13e919778c4dcfc985ca3338ddbb89b77cac98437f7adb19ff02bf192a51'
_SEAL = object()


class RetiredServiceSourceControls:
    __slots__ = ('_body','_core','_retirement','_seal','source_birth','OWN')
    def __init__(self,*args,**kwargs):
        raise RuntimeError('SOURCE_SERVICES_CONTROL_ONLY_FIXED_ORIGINAL_PRODUCER')
    def __setattr__(self,name,value):
        need(not hasattr(self,'_seal'),'SOURCE_SERVICES_CAPTURED_CONTROL_CAPABILITY_IMMUTABLE')
        object.__setattr__(self,name,value)
    def snapshot(self):
        need(self._seal is _SEAL,'SOURCE_SERVICES_FIXED_SOURCE_CONTROL_SEAL')
        return copy.deepcopy(self._body)
    @property
    def safe_to_TERM(self):return False
    @property
    def paid_activation_authorized(self):return False
    @property
    def whole_runnable_ready(self):return False


def sources(value, read_budget):
    body = {}
    for key,field in asdict(value).items():
        read_budget.check()
        body[key] = str(field) if isinstance(field,Path) else field
    # Every registered executable/code/manifest path remains byte-pinned. No
    # task/private data/credential file is a member of either source dataclass.
    for key,value in body.items():
        if key.endswith('_sha256'):continue
        pair = 'python_sha256' if key=='python' else key+'_sha256'
        if pair not in body:continue
        p=Path(value)
        need(p.is_absolute() and p.resolve()==p and not p.is_symlink() and
             hashlib.sha256(p.read_bytes()).hexdigest()==body[pair],
             'SOURCE_SERVICES_ORIGINAL_REGISTERED_CODE_PATH_AND_PIN_STILL_MATCH')
    return body


def fence_controls(core, read_budget):
    from dynteam_membership_fence import MembershipFence, Lease
    module=importlib.import_module('dynteam_membership_fence');p=Path(module.__file__)
    need(p.resolve()==p and not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest()==FENCE_SHA and
         set(core.membership_fences)==set(core.rows),
         'SOURCE_SERVICES_ORIGINAL_COMPLETE_MEMBERSHIP_FENCE_SOURCE')
    result={}
    for t,f in sorted(core.membership_fences.items()):
        need(type(f)is MembershipFence,'SOURCE_SERVICES_EXACT_REGISTERED_FENCE_TYPE')
        with ram_lock(f._lock,read_budget):
            need(all(type(v)is Lease for v in f._leases.values()),
                 'SOURCE_SERVICES_ORIGINAL_MEMBERSHIP_LEASE_TYPES')
            result[t]=dict(roles=dict(f.roles),_leases=[asdict(v)for _,v in sorted(f._leases.items())],
                _role_busy=sorted(f._role_busy),_epoch=f._epoch,_cut=f._cut,_sealed=f._sealed,
                _last_generation=f._last_generation,_final_retirement=copy.deepcopy(f._final_retirement))
    return result


def system_controls(service, read_budget):
    if service is None:return dict(registered=False,configuration=None,records=None)
    from native_system_health import NativeSystemHealth,SystemProbeSources
    need(type(service)is NativeSystemHealth and type(service.sources)is SystemProbeSources and
         service.accepting is False,'SOURCE_SERVICES_EXACT_STOPPED_ORIGINAL_SYSTEM_CONTROL')
    records=[]
    for r in service.records:
        read_budget.check();terminal=r['terminal'];child=r['child']
        need(child is None or child.poll()is not None,
             'SOURCE_SERVICES_NO_LIVE_SYSTEM_HANDLE_IN_RETIRED_SOURCE_SUPPLEMENT')
        row=dict(sequence=r['sequence'],state=r['state'],exit_code=r['exit_code'],
            failure_type=r['failure_type'],intent_wall_ns=r['intent_wall_ns'],
            child_handle_present=child is not None,child_returncode=None if child is None else child.returncode,
            terminal_present=terminal is not None)
        if terminal is not None:
            row['terminal']=dict(reported_tokens=terminal['reported_tokens'],
                possible_unmeasured_tokens_upper=terminal['possible_unmeasured_tokens_upper'],
                http_status=terminal['http_status'])
        else:row['terminal']=None
        records.append(row)
    return dict(registered=True,source_owner_birth=asdict(service.owner),
        configuration=dict(sources=sources(service.sources,read_budget),sequence=service.sequence,
            last_intent_wall=service.last_intent_wall,last_intent_mono=service.last_intent_mono,
            started=service.started,accepting=service.accepting,unmeasured_upper=service.unmeasured_upper,
            home=str(service.home),contract_sha256=service.contract_sha),
        original_public=service.public(),records=records,
        history_control_bindings=system_history_bindings(service,read_budget),
        raw_request_session_key_and_body_excluded=True,constructor_restarted=False)



def system_history_bindings(service, read_budget):
    """Fixed full PUBLIC-control refs, captured INSIDE the OLD sealed cap.

    No helper imports/caller refs or sidecar trust. The original durable
    SOURCE/ISSUED hashes this field along with the actual same-birth RAM cap.
    """
    import os,stat
    from native_system_health import NativeSystemHealth
    need(type(service)is NativeSystemHealth and type(read_budget)is ReadBudget and
         service.accepting is False and service.physical_clear() and
         service.home==service.core.home/'system-health' and
         len(service.records)==service.sequence,
         'SOURCE_SYSTEM_HISTORY_FIXED_ORIGINAL_STOPPED_SERVICE')
    home=service.home
    def directory(p):
        read_budget.check();s=p.lstat()
        need(p.is_absolute()and p.resolve()==p and stat.S_ISDIR(s.st_mode)and
             s.st_uid==os.geteuid()and stat.S_IMODE(s.st_mode)==0o700,
             'SOURCE_SYSTEM_HISTORY_CANONICAL_PRIVATE_DIRECTORY')
        return [s.st_dev,s.st_ino,s.st_uid,s.st_gid,s.st_mode]
    def token(s):
        return [s.st_dev,s.st_ino,s.st_uid,s.st_gid,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
    def control(p):
        read_budget.check();s=p.lstat()
        need(p.resolve()==p and stat.S_ISREG(s.st_mode)and s.st_uid==os.geteuid()and s.st_nlink==1 and
             stat.S_IMODE(s.st_mode)==0o600 and 0<s.st_size<=32768,
             'SOURCE_SYSTEM_HISTORY_FIXED_BOUNDED_PUBLIC_CONTROL')
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            a=os.fstat(fd);raw=os.read(fd,32769);b=os.fstat(fd)
            need(token(s)==token(a)==token(b)==token(p.lstat())and len(raw)==s.st_size,
                 'SOURCE_SYSTEM_HISTORY_STABLE_NOFOLLOW_FD')
        finally:os.close(fd)
        read_budget.check()
        return dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),identity=token(s))
    def names(p,maximum):
        result=[]
        for x in p.iterdir():
            read_budget.check();need(len(result)<maximum,'SOURCE_SYSTEM_HISTORY_REGISTERED_LEAF_BOUND')
            result.append(x.name)
        return sorted(result)
    identity=directory(home);refs=[];expected=[]
    if service.started:
        refs.append(control(home/'EXPLICIT_START_PUBLIC.json'));expected.append('EXPLICIT_START_PUBLIC.json')
    else:need(service.sequence==0,'SOURCE_SYSTEM_HISTORY_UNSTARTED_HAS_NO_PROBES')
    for seq,r in enumerate(service.records,1):
        read_budget.check();p=r['directory']
        need(r['sequence']==seq and p.parent==home and p.name==f'{seq:08d}-'+r['request_id']and
             r['state']in('HTTP_PHYSICAL_TERMINAL','NOT_STARTED')and
             (r['child']is None or r['child'].poll()is not None),
             'SOURCE_SYSTEM_HISTORY_EXACT_ORIGINAL_REGISTERED_RECORD_DIRECTORY')
        before=directory(p)
        files=['INTENT_PUBLIC.json']+(['NOT_STARTED_PUBLIC.json']if r['state']=='NOT_STARTED'else
                                    ['CUSTODY_PUBLIC.json','TERMINAL_PUBLIC.json'])
        need(names(p,3)==sorted(files),'SOURCE_SYSTEM_HISTORY_COMPLETE_FIXED_CONTROL_SET')
        refs.extend(control(p/n)for n in files);expected.append(p.name)
        need(directory(p)==before,'SOURCE_SYSTEM_HISTORY_PROBE_DIRECTORY_DRIFT')
    need(names(home,len(expected))==sorted(expected),'SOURCE_SYSTEM_HISTORY_NO_MISSING_OR_UNKNOWN_PROBE')
    for ref in refs:
        need(control(Path(ref['path']))==ref,'SOURCE_SYSTEM_HISTORY_CONTROL_CHANGED_DURING_CAPTURE')
    need(directory(home)==identity and names(home,len(expected))==sorted(expected),
         'SOURCE_SYSTEM_HISTORY_ORIGINAL_HOME_AND_ALL_LEAVES_STILL_EQUAL')
    return dict(schema='count14-original-sealed-SYSTEM-history-control-bindings-v1',
        home=str(home),home_identity=identity,control_references=refs)


def resource_controls(service, read_budget):
    if service is None:return dict(registered=False,configuration=None,records=None)
    from native_resource_producer import NativeResourceProducer,ResourceSamplerSources
    need(type(service)is NativeResourceProducer and type(service.sources)is ResourceSamplerSources and
         service.accepting is False,'SOURCE_SERVICES_EXACT_STOPPED_ORIGINAL_RESOURCE_CONTROL')
    records=[]
    for r in service.records:
        read_budget.check();child=r['child']
        need(child is None or child.poll()is not None,
             'SOURCE_SERVICES_NO_LIVE_SAMPLER_HANDLE_IN_RETIRED_SOURCE_SUPPLEMENT')
        records.append(dict(state=r['state'],child_handle_present=child is not None,
            child_returncode=None if child is None else child.returncode,intent_sha256=r['intent_sha256'],
            directory=str(r['directory'])))
    plan=Path(service.plan_path)
    need(plan.resolve()==plan and not plan.is_symlink() and
         hashlib.sha256(plan.read_bytes()).hexdigest()==service.inventory_sha,
         'SOURCE_SERVICES_SAME_ORIGINAL_RESOURCE_PLAN_RAW_PIN')
    return dict(registered=True,source_owner_birth=asdict(service.owner),
        configuration=dict(plan_path=str(plan),inventory_sha256=service.inventory_sha,
            sources=sources(service.sources,read_budget),sequence=service.sequence,next_due=service.next_due,
            accepting=service.accepting,sourcehome=str(service.home),last_published=service.last_published,
            contract_sha256=service.contract_sha),
        original_public=service.public(),records=records,
        history_control_bindings=resource_history_bindings(service,read_budget),
        constructor_restarted=False)


def resource_history_bindings(service, read_budget):
    """Close fixed sampler PUBLIC controls INSIDE the real old-source cap.

    No receiver, constructor, pointer transition or admission is implemented.
    Failed/NOT_STARTED records are retained, never converted to success. The
    last readonly pointer must still be exactly the original parent's hash.
    """
    import os,stat,subprocess
    from types import MethodType
    from native_resource_producer import NativeResourceProducer
    from native_peer_registry import process_birth
    need(type(service)is NativeResourceProducer and type(read_budget)is ReadBudget and
         service.accepting is False and service.core.resource_producer is service and
         service.owner==process_birth(os.getpid()) and
         type(service.home)is type(Path('/')) and
         service.home==service.core.home/'resources/producer' and
         type(service.sequence)is int and 0<=service.sequence<=99999999 and
         type(service.records)is list and len(service.records)==service.sequence,
         'SOURCE_RESOURCE_HISTORY_FIXED_ORIGINAL_STOPPED_SERVICE')
    for name in ('_outside','_publish','poll','public','stop_admission','physical_clear'):
        method=getattr(service,name)
        need(type(method)is MethodType and method.__self__ is service and
             method.__func__ is getattr(NativeResourceProducer,name),
             'SOURCE_RESOURCE_HISTORY_ORIGINAL_METHODS_NOT_METADATA_SUBSTITUTES')
    service._outside()
    need(not service.core.queue.mutex._is_owned(),
         'SOURCE_RESOURCE_HISTORY_OUTSIDE_BOTH_SCIENTIFIC_LOCKS')
    home=service.home
    def directory(p):
        read_budget.check();s=p.lstat()
        need(p.is_absolute()and p.resolve()==p and stat.S_ISDIR(s.st_mode)and
             s.st_uid==os.geteuid()and stat.S_IMODE(s.st_mode)==0o700,
             'SOURCE_RESOURCE_HISTORY_CANONICAL_PRIVATE_DIRECTORY')
        return [s.st_dev,s.st_ino,s.st_uid,s.st_gid,s.st_mode]
    def token(s):
        return [s.st_dev,s.st_ino,s.st_uid,s.st_gid,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
    def control(p,mode):
        read_budget.check();s=p.lstat()
        need(p.resolve()==p and stat.S_ISREG(s.st_mode)and s.st_uid==os.geteuid()and
             s.st_nlink==1 and stat.S_IMODE(s.st_mode)==mode and 0<s.st_size<=131072,
             'SOURCE_RESOURCE_HISTORY_FIXED_BOUNDED_PUBLIC_CONTROL')
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            a=os.fstat(fd);raw=os.read(fd,131073);b=os.fstat(fd)
            need(token(s)==token(a)==token(b)==token(p.lstat())and len(raw)==s.st_size,
                 'SOURCE_RESOURCE_HISTORY_STABLE_NOFOLLOW_FD')
        finally:os.close(fd)
        read_budget.check()
        return dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),identity=token(s))
    def names(p,maximum):
        result=[]
        for x in p.iterdir():
            read_budget.check();need(len(result)<maximum,'SOURCE_RESOURCE_HISTORY_REGISTERED_LEAF_BOUND')
            result.append(x.name)
        return sorted(result)
    identity=directory(home);refs=[];views=[];expected=[]
    pointer=service.core.home/'resources/COHORT_RESOURCES_PUBLIC.json'
    pointer_before=control(pointer,0o444)if os.path.lexists(pointer)else None
    need((pointer_before is None and service.last_published is None)or
         (pointer_before is not None and type(service.last_published)is str and
          pointer_before['sha256']==service.last_published),
         'SOURCE_RESOURCE_HISTORY_ORIGINAL_LAST_POINTER_HASH_NOT_CALLER_RESTAMP')
    for seq,r in enumerate(service.records,1):
        read_budget.check();p=r['directory'];child=r['child']
        need(type(p)is type(home) and p.parent==home and p.name==f'{seq:08d}'and
             r['state']in('OBSERVATION_PUBLISHED','FAILED_RETAINED','NOT_STARTED')and
             (child is None or type(child)is subprocess.Popen and child.poll()is not None),
             'SOURCE_RESOURCE_HISTORY_EXACT_ORIGINAL_REGISTERED_TERMINAL_RECORD')
        before=directory(p);files=names(p,4)
        need('INTENT_PUBLIC.json'in files and
             set(files)<={'INTENT_PUBLIC.json','RESULT_PUBLIC.json','FAILURE_PUBLIC.json','PUBLISHED_PUBLIC.json'}and
             ('PUBLISHED_PUBLIC.json'not in files or 'RESULT_PUBLIC.json'in files),
             'SOURCE_RESOURCE_HISTORY_FIXED_PUBLIC_CONTROL_SET_NO_UNKNOWN_FILES')
        if r['state']=='NOT_STARTED':
            need(child is None and files==['INTENT_PUBLIC.json'],
                 'SOURCE_RESOURCE_HISTORY_NOT_STARTED_NO_FAKE_CHILD_OR_TERMINAL')
        else:
            need(child is not None and type(child.returncode)is int,
                 'SOURCE_RESOURCE_HISTORY_REAL_PHYSICAL_TERMINAL_NOT_NONE_ZERO_FILL')
            if r['state']=='OBSERVATION_PUBLISHED':
                need(child.returncode==0 and files==['INTENT_PUBLIC.json','PUBLISHED_PUBLIC.json','RESULT_PUBLIC.json'],
                     'SOURCE_RESOURCE_HISTORY_PUBLISHED_REQUIRES_TRUE_CHILD0_AND_ALL_CONTROLS')
        rows=[control(p/n,0o600)for n in files]
        intent=next(v for v in rows if Path(v['path']).name=='INTENT_PUBLIC.json')
        need(intent['sha256']==r['intent_sha256'],
             'SOURCE_RESOURCE_HISTORY_ORIGINAL_RAM_INTENT_HASH_STILL_EXACT')
        refs.extend(rows);expected.append(p.name)
        views.append(dict(sequence=seq,path=str(p),identity=before,files=files))
        need(directory(p)==before,'SOURCE_RESOURCE_HISTORY_SAMPLE_DIRECTORY_DRIFT')
    need(names(home,len(expected))==expected,
         'SOURCE_RESOURCE_HISTORY_NO_MISSING_OR_UNKNOWN_SAMPLER_LEAF')
    for ref in refs:
        need(control(Path(ref['path']),0o600)==ref,
             'SOURCE_RESOURCE_HISTORY_CONTROL_CHANGED_DURING_CAPTURE')
    for row in views:
        p=Path(row['path'])
        need(directory(p)==row['identity']and names(p,4)==row['files'],
             'SOURCE_RESOURCE_HISTORY_CONTROL_SET_OR_DIRECTORY_CHANGED_DURING_CAPTURE')
    pointer_after=control(pointer,0o444)if os.path.lexists(pointer)else None
    need(pointer_after==pointer_before and directory(home)==identity and
         names(home,len(expected))==expected,
         'SOURCE_RESOURCE_HISTORY_HOME_LEAVES_OR_POINTER_CHANGED_DURING_CAPTURE')
    return dict(schema='count14-original-sealed-resource-history-control-bindings-v1',
        home=str(home),home_identity=identity,record_directories=views,
        control_references=refs,pointer_present=pointer_before is not None,
        pointer_reference=pointer_before,last_published_sha256=service.last_published)


def capture_registered(core, *, read_budget):
    need(type(read_budget)is ReadBudget,'SOURCE_SERVICES_FINITE_SOURCE_CAPTURE_BUDGET')
    rt=registered(core);physical=rt.observe(read_budget=read_budget)
    body=dict(schema='count14-retired-native-service-and-fence-source-controls-v1',OWN=rt.OWN,
        source_owner_birth=asdict(rt.birth),physical_service_retirement=physical,
        membership_fences=fence_controls(core,read_budget),
        SYSTEM=system_controls(rt.system,read_budget),resource=resource_controls(rt.resource,read_budget),
        receiver_or_new_owner_verified=False,raw_request_session_key_and_body_excluded=True,
        safe_to_TERM=False,paid_activation_authorized=False,whole_runnable_ready=False)
    for s in (rt.system,rt.resource):
        need(s is None or s.owner==rt.birth,
             'SOURCE_SERVICES_ORIGINAL_COMPONENTS_EXACT_SAME_SOURCE_BIRTH')
    rt.observe(read_budget=read_budget)
    result=object.__new__(RetiredServiceSourceControls)
    result._body,result._core,result._retirement=body,core,rt
    result.source_birth,result.OWN,result._seal=rt.birth,rt.OWN,_SEAL
    return result


def verify_registered_source(value, *, core, read_budget):
    need(type(value)is RetiredServiceSourceControls and value._seal is _SEAL and value._core is core and
         value._retirement is registered(core),
         'SOURCE_SERVICES_EXACT_CAPTURED_SOURCE_CAPABILITY_NOT_DICT_OR_BOOL')
    current=capture_registered(core,read_budget=read_budget)
    need(current.snapshot()==value.snapshot(),
         'SOURCE_SERVICES_ACTUAL_SAME_BIRTH_SOURCE_CONTROLS_UNCHANGED')
    return value
