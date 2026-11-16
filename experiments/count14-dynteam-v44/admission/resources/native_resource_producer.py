"""SAME cold-owner finite sampler custody + atomic PUBLIC pointer.

No resident observer/dispatcher, model requests, science-lock IO or child
signals. Source errors retain prior timestamps and fail closed at original TTL.
Only a completed exact child may publish; observations are NOT admission.
"""
from dataclasses import dataclass,asdict
from pathlib import Path
import hashlib
import json
import os
import stat
import subprocess
import time

from common import need,digest
from native_peer_registry import process_birth
from native_cohort_resources import NativeCohortResources,CohortAllocation,storage_lifecycle_phase
from native_system_health import executable
from native_system_probe_child import append,read_control
from native_resource_sampler import read_public,allocation_envelope,validate_promise_directories


@dataclass(frozen=True)
class ResourceSamplerSources:
    python:Path
    python_sha256:str
    child:Path
    child_sha256:str
    factory_manifest:Path
    factory_manifest_sha256:str
    bootstrap_sha256:str


class NativeResourceProducer:
    def __init__(self,core,plan_path,plan_sha256,sources,*,memory_reader=None):
        from original_relay_core import OriginalRelayCore
        need(type(core) is OriginalRelayCore and type(sources) is ResourceSamplerSources and
             not hasattr(core,'resource_producer') and set(core.gate.startup_held)==set(core.rows) and
             hasattr(core,'native_containers') and hasattr(core,'native_host_environment') and
             not core.ledger.mutex._is_owned() and (core.qualification_only or memory_reader is None),
             'DYNTEAM_RESOURCE_PRODUCER_ONLY_COLD_SAME_ORIGINAL_OWNER')
        plan,raw=read_public(Path(plan_path))
        need(hashlib.sha256(raw).hexdigest()==plan_sha256 and plan['contract_sha256']==digest(core.contract) and
             plan['schema']=='count14-dynteam-resource-production-plan-v1' and
             plan['no_active_unregistered_roots'] is True and
             plan['other_bound_is_full_allocations_plus_retained_UNKNOWN'] is True and
             (core.qualification_only or plan['OWN_fixture'] is None),'DYNTEAM_RESOURCE_PRODUCER_FROZEN_PLAN')
        search=plan['docker_routes']['SEARCH_BACKEND']['route'];route=core.native_containers.docker.route
        need(search==dict(cli=str(route.cli),cli_sha256=route.cli_sha256,socket_path=str(route.socket_path),
             daemon_id=route.daemon_id,data_root=str(route.data_root),qualification_only=core.qualification_only),
             'DYNTEAM_RESOURCE_SAME_NATIVE_SEARCH_DAEMON_NOT_A_NEW_ROUTE')
        required={value for row in core.native_host_environment['trajectories'].values() for value in row['image_ids'].values()}
        need(required<={p['id'] for p in plan['docker_routes']['SEARCH_BACKEND']['images']},
             'DYNTEAM_RESOURCE_PLAN_INCLUDES_ACTUAL_NATIVE_AGENT_ROUTER_INFRA_IMAGES')
        for storage in plan['storage'].values():validate_promise_directories(storage['promise_directories'])
        space=core.home/'space'
        need(str(space) in plan['storage']['scratch2_roots_snapshots']['promise_directories'],
             'DYNTEAM_RESOURCE_ACTUAL_NEW_AUX_SPACE_HOME_MUST_BE_REGISTERED')
        with core.ledger.mutex:
            need(core.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]==0 and
                 core.ledger.db.execute('SELECT COUNT(*) FROM aux_permits').fetchone()[0]==0,
                 'DYNTEAM_RESOURCE_PRODUCER_BEFORE_PAID_REQUESTS_ONLY')
        from newroot_private_resource_sources import select_for_newroot
        sources=select_for_newroot(sources,core=core)
        python=executable(sources.python,sources.python_sha256)
        child=Path(sources.child);metadata=child.lstat()
        need(child.name=='native_resource_sample_child.py' and child.resolve()==child and
             stat.S_ISREG(metadata.st_mode) and not metadata.st_mode&0o022 and metadata.st_uid in (0,os.geteuid()) and
             hashlib.sha256(child.read_bytes()).hexdigest()==sources.child_sha256,
             'DYNTEAM_RESOURCE_FROZEN_FINITE_CHILD_SOURCE')
        bootstrap=child.with_name('native_cold_owner_entry.py')
        need(bootstrap.resolve()==bootstrap and not bootstrap.is_symlink() and
             hashlib.sha256(bootstrap.read_bytes()).hexdigest()==sources.bootstrap_sha256,
             'DYNTEAM_RESOURCE_SAME_COLD_ENTRY_IMPORT_BOOTSTRAP')
        _,factory_raw=read_public(sources.factory_manifest)
        need(hashlib.sha256(factory_raw).hexdigest()==sources.factory_manifest_sha256,
             'DYNTEAM_RESOURCE_FROZEN_IMPORT_ONLY_FACTORY_MANIFEST')
        allocation=CohortAllocation(plan_sha256,plan['other_maximum_FP8_inflight']).checked()
        if not hasattr(core,'cohort_resources'):NativeCohortResources(core,allocation,memory_reader=memory_reader)
        need(core.cohort_resources.allocation==allocation,'DYNTEAM_RESOURCE_EXISTING_ALLOCATION_CANNOT_CHANGE')
        self.core,self.plan,self.plan_path,self.sources=core,plan,Path(plan_path),sources
        self.owner=process_birth(os.getpid());self.contract_sha=digest(core.contract);self.inventory_sha=plan_sha256
        self.home=core.home/'resources/producer';self.records=[];self.failures=[];self.accepting=True
        self.sequence=0;self.next_due=0;self.last_published=None
        self.argv=(python,'-I','-B',str(child));core.resource_producer=self # retain partial same object
        self.home.mkdir(mode=0o700,parents=True)
        if not space.exists():space.mkdir(mode=0o700)
        need(space.resolve()==space and not space.is_symlink() and space.is_dir(),
             'DYNTEAM_RESOURCE_NEW_SPACE_HOME_CANONICAL_NO_RECURSIVE_REPAIR')

    def _outside(self):
        need(not self.core.ledger.mutex._is_owned() and process_birth(os.getpid())==self.owner and
             digest(self.core.contract)==self.contract_sha,'DYNTEAM_RESOURCE_SAME_OWNER_NO_IO_UNDER_SCIENCE_LOCK')

    def stop_admission(self):self._outside();self.accepting=False

    def physical_clear(self):
        return not self.records or self.records[-1]['child'] is None or self.records[-1]['child'].poll() is not None

    def _publish(self,record):
        result=json.loads(read_control(record['directory']/'RESULT_PUBLIC.json',131072))
        need(record['child'].returncode==0 and result['schema']=='count14-dynteam-finite-resource-result-v1' and
             result['intent_sha256']==record['intent_sha256'] and result['owner']==asdict(self.owner) and
             result['factory_constructor_called'] is False,'DYNTEAM_RESOURCE_ONLY_EXACT_COMPLETED_CHILD_CAN_PUBLISH')
        value=result['value']
        need(value['schema']=='count14-seed46-global-resource-admission-v1' and
             value['dynteam_allocation']==allocation_envelope(record['job']) and
             value['storage_lifecycle_phase']==record['job']['storage_lifecycle_phase'] and
             value['qualification_only'] is self.core.qualification_only and
             (self.core.qualification_only or value['OWN_fixture_host_projection_used'] is False),
             'DYNTEAM_RESOURCE_EXACT_SOURCE_RESULT_NOT_GREEN_FIXTURE')
        destination=self.core.cohort_resources.path
        if destination.exists():
            previous,_=read_public(destination)
            need(previous['schema']==value['schema'] and previous['dynteam_allocation']==value['dynteam_allocation'],
                 'DYNTEAM_RESOURCE_REPLACE_ONLY_SAME_OWNER_NUMERIC_POINTER')
        raw=(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
        need(len(raw)<=131072,'DYNTEAM_RESOURCE_BOUNDED_PUBLIC_POINTER')
        temporary=destination.with_name(f'.COHORT_RESOURCES-{self.sequence}.partial')
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
        with os.fdopen(fd,'wb') as out:out.write(raw);out.flush();os.fsync(out.fileno())
        self._outside();os.replace(temporary,destination)
        fd=os.open(destination.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:os.close(fd)
        self.last_published=hashlib.sha256(raw).hexdigest();record['state']='OBSERVATION_PUBLISHED'
        append(record['directory']/'PUBLISHED_PUBLIC.json',dict(schema='count14-dynteam-resource-published-v1',
            source_observed_ns=value['observed_ns'],value_sha256=self.last_published,
            restamped=False,observation_is_not_admission=True,models=0))

    def poll(self):
        self._outside();now=time.monotonic_ns()
        if self.records:
            record=self.records[-1]
            if record['state']=='RUNNING':
                if record['child'].poll() is None:return self.public()
                try:self._publish(record)
                except Exception as error:
                    record['state']='FAILED_RETAINED';self.failures.append(dict(exception_type=type(error).__name__,
                        exit_code=record['child'].returncode))
                self.failures=self.failures[-32:]
        if not self.accepting or now<self.next_due:return self.public()
        self.sequence+=1;directory=self.home/f'{self.sequence:08d}';directory.mkdir(mode=0o700)
        job=dict(schema='count14-dynteam-finite-resource-intent-v1',owner=asdict(self.owner),contract_sha256=self.contract_sha,
            inventory_sha256=self.inventory_sha,other_maximum_FP8_inflight=self.plan['other_maximum_FP8_inflight'],
            core_home=str(self.core.home),new_root=self.core.contract['arms'][0]['root'],
            trajectory_roots={t:r['root'] for t,r in self.core.rows.items()},ledger_path=str(self.core.ledger.home/'ledger.sqlite'),
            system_registered=hasattr(self.core,'system_health'),qualification_only=self.core.qualification_only,
            plan_path=str(self.plan_path),storage_lifecycle_phase=storage_lifecycle_phase(self.core))
        path=directory/'INTENT_PUBLIC.json';append(path,job);pin=hashlib.sha256(path.read_bytes()).hexdigest()
        record=dict(child=None,state='STARTING',directory=directory,job=job,intent_sha256=pin)
        self.records.append(record);self.next_due=now+20*10**9
        try:
            record['child']=subprocess.Popen([*self.argv,'--intent',str(path),'--intent-sha256',pin,
                '--factory',str(self.sources.factory_manifest),'--factory-sha256',self.sources.factory_manifest_sha256,
                '--bootstrap-sha256',self.sources.bootstrap_sha256],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,cwd='/',env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'})
            record['state']='RUNNING'
        except Exception as error:
            record['state']='NOT_STARTED';self.failures.append(dict(exception_type=type(error).__name__,exit_code=None))
        return self.public()

    def public(self):
        return dict(PUBLIC_code='DYNTEAM_SAME_OWNER_FINITE_RESOURCE_PRODUCER',sample_sequence=self.sequence,
            latest_state=None if not self.records else self.records[-1]['state'],accepting=self.accepting,
            latest_published_sha256=self.last_published,period_seconds=20,child_deadline_seconds=55,
            failures=list(self.failures),models=0,another_owner_or_dispatcher_constructed=False,
            observation_is_not_admission=True)
