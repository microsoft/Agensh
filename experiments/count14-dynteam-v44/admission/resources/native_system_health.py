"""Cold SAME-owner SYSTEM health custody; no experimental model permits.

Only one bounded, original fixed health request per600s. Two reserved system
slots may retain unproven network UNKNOWN; no borrowed SEARCH/AUX capacity,
no retries or forced request cancellation. All waits/IO are outside scientific
locks; poll() never waits for a live probe and never TERM/KILLs one.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import os
import stat
import subprocess
import time
import uuid

from common import need,digest
from native_peer_registry import process_birth
from native_system_probe_child import append,read_control,original,ORIGINAL_SHA,OWN_endpoint_ok


@dataclass(frozen=True)
class SystemProbeSources:
    python:Path
    python_sha256:str
    child:Path
    child_sha256:str


def executable(path,pin,*,child=False):
    path=Path(path);s=path.lstat()
    need(path.is_absolute() and path.resolve()==path and not path.is_symlink() and
         stat.S_ISREG(s.st_mode) and not s.st_mode&0o022 and s.st_uid in (0,os.geteuid()) and
         (child or s.st_mode&0o111) and hashlib.sha256(path.read_bytes()).hexdigest()==pin and
         (not child or path.name=='native_system_probe_child.py'),
         'DYNTEAM_FROZEN_SYSTEM_PROBE_EXECUTABLE')
    return str(path)


class NativeSystemHealth:
    def __init__(self,core,sources,*,key_path,OWN_endpoint=None,wall_ns=None,monotonic_ns=None):
        from original_relay_core import OriginalRelayCore
        from native_cohort_resources import NativeCohortResources
        need(type(core) is OriginalRelayCore and type(sources) is SystemProbeSources and
             type(getattr(core,'cohort_resources',None)) is NativeCohortResources and
             not hasattr(core,'system_health') and set(core.gate.startup_held)==set(core.rows) and
             not core.ledger.mutex._is_owned() and
             (core.qualification_only or OWN_endpoint is wall_ns is monotonic_ns is None),
             'DYNTEAM_SYSTEM_HEALTH_COLD_SAME_ORIGINAL_RESOURCE_OWNER')
        P=original();need(P.MODEL==core.profile.policy['model'],'DYNTEAM_SYSTEM_PROBE_SAME_ORIGINAL_GLM_MODEL')
        if core.qualification_only:
            need(OWN_endpoint_ok(OWN_endpoint),
                 'DYNTEAM_OWN_PROBE_NEVER_REAL_NETWORK')
        with core.ledger.mutex:
            need(core.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]==0,
                 'DYNTEAM_SYSTEM_HEALTH_INSTALLED_COLD_BEFORE_PAID_REQUESTS')
        self.core,self.sources,self.key_path=core,sources,Path(key_path)
        self.argv=(executable(sources.python,sources.python_sha256),'-I','-B',
                   executable(sources.child,sources.child_sha256,child=True))
        # Key never enters a PUBLIC receipt or child argv; only its path is a
        # control field, as with the original v2 affinity installer.
        read_control(self.key_path,4096)
        self.owner=process_birth(os.getpid());self.contract_sha=digest(core.contract)
        self.home=core.home/'system-health';self.home.mkdir(mode=0o700) # no overwrite/reconstruct on blind retry
        self.sequence=0;self.records=[];self.last_intent_wall=None;self.last_intent_mono=None
        self.wall=time.time_ns if wall_ns is None else wall_ns
        self.monotonic=time.monotonic_ns if monotonic_ns is None else monotonic_ns
        self.endpoint=OWN_endpoint;self.accepting=False;self.started=False
        self.unmeasured_upper=len(json.dumps(P.BODY).encode())+8192+256+P.OUTPUT
        self.session_id=str(uuid.uuid5(uuid.NAMESPACE_URL,'count14-dynteam-system:'+self.contract_sha+':'+self.owner.boot_id))
        self.core.system_health=self

    def _outside(self):
        need(not self.core.ledger.mutex._is_owned(),'DYNTEAM_SYSTEM_PROBE_NO_IO_OR_WAIT_IN_SCIENCE_LOCK')
        need(process_birth(os.getpid())==self.owner and digest(self.core.contract)==self.contract_sha,
             'DYNTEAM_SYSTEM_PROBE_EXACT_SAME_OWNER_CONTRACT')

    def occupied(self):return sum(r['state'] in ('RUNNING','UNPROVEN_PHYSICAL_UNKNOWN') for r in self.records)

    def start(self):
        self._outside()
        need(not self.started,'DYNTEAM_SYSTEM_PROBE_EXPLICIT_START_ONCE_NO_ZERO_MODEL_AUTOSTART')
        append(self.home/'EXPLICIT_START_PUBLIC.json',dict(schema='count14-dynteam-system-probe-start-v1',
            owner_pid=self.owner.pid,owner_start_ticks=self.owner.start_ticks,owner_boot_id=self.owner.boot_id,
            contract_sha256=self.contract_sha,system_reserved_slots=2,experiment_permits_used=0))
        self.started=True;self.accepting=True
        return self.public()

    def stop_admission(self):
        self._outside();self.accepting=False # existing live request is untouched

    def physical_clear(self):return self.occupied()==0

    def _terminal(self,record):
        child=record['child']
        if child is None or child.poll() is None:return False
        record['exit_code']=child.returncode
        try:
            value=json.loads(read_control(record['directory']/'TERMINAL_PUBLIC.json'))
            need(child.returncode==0 and value['schema']=='count14-dynteam-system-probe-terminal-v1' and
                 value['sequence']==record['sequence'] and value['request_id']==record['request_id'] and
                 value['session_id']==self.session_id and value['contract_sha256']==self.contract_sha and
                 value['original_probe_source_sha256']==ORIGINAL_SHA and value['retries']==0 and
                 value['system_cost_not_experiment'] is True and value['included_in_search_budget'] is False and
                 value['original_financial_tables_written']==0 and value['request_replays']==0,
                 'DYNTEAM_ORIGINAL_SYSTEM_TERMINAL_EXACT_BINDING')
            status=value['http_status'];need(status is None or type(status) is int and 100<=status<=599,
                                           'DYNTEAM_ORIGINAL_SYSTEM_HTTP_ENUM')
            measured=value['reported_tokens'];upper=value['possible_unmeasured_tokens_upper']
            need((measured is None or type(measured) is int and measured>0) and type(upper) is int and upper>=0 and
                 (measured is None or upper==0),'DYNTEAM_ORIGINAL_SYSTEM_USAGE_OR_UPPER_NO_FABRICATION')
            record['terminal']=value
            # HTTP status is returned only after the original context closed.
            # Client exception/timeout is not a proven upstream physical end.
            record['state']='HTTP_PHYSICAL_TERMINAL' if status is not None and (status != 200 or value.get('stream_complete') is True) else 'UNPROVEN_PHYSICAL_UNKNOWN'
        except Exception as error:
            record['state']='UNPROVEN_PHYSICAL_UNKNOWN'
            record['failure_type']=type(error).__name__
        append(record['directory']/'CUSTODY_PUBLIC.json',dict(schema='count14-dynteam-system-probe-custody-v1',
                sequence=record['sequence'],state=record['state'],exit_code=record['exit_code'],
            upper_charge_preserved=True,experiment_permits_used=0,request_replays=0))
        return True

    def poll(self):
        self._outside()
        for r in self.records:
            if r['state']=='RUNNING':self._terminal(r)
        wall,mono=self.wall(),self.monotonic()
        due=self.last_intent_wall is None or (wall-self.last_intent_wall>=600*10**9 and
                                              mono-self.last_intent_mono>=600*10**9)
        # A live finite probe never overlaps another. A dead, unproven one
        # retains a SYSTEM slot; the second reserved slot remains independent.
        if (not self.accepting or not due or any(r['state']=='RUNNING' for r in self.records) or
            self.occupied()>=2 or not self.core.cohort_resources.system_open()):return self.public()
        self.sequence+=1;rid='count14-dynteam-system-'+str(uuid.uuid4())
        directory=self.home/(f'{self.sequence:08d}-'+rid);directory.mkdir(mode=0o700)
        job=dict(schema='count14-dynteam-system-probe-intent-v1',sequence=self.sequence,request_id=rid,
            session_id=self.session_id,owner_pid=self.owner.pid,owner_start_ticks=self.owner.start_ticks,
            owner_boot_id=self.owner.boot_id,contract_sha256=self.contract_sha,key_path=str(self.key_path),
            qualification_only=self.core.qualification_only,OWN_endpoint=self.endpoint)
        path=directory/'INTENT_PUBLIC.json';append(path,job)
        record=dict(sequence=self.sequence,request_id=rid,directory=directory,child=None,state='RUNNING',
                    terminal=None,exit_code=None,failure_type=None,intent_wall_ns=wall)
        self.records.append(record);self.last_intent_wall=wall;self.last_intent_mono=mono
        # Durable intent first. Popen failure is retained, not a resend or a
        # reason to loop a new request immediately. No timeout/TERM/KILL path.
        try:
            record['child']=subprocess.Popen([*self.argv,'--intent',str(path),'--intent-sha256',
                                             hashlib.sha256(path.read_bytes()).hexdigest()],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,cwd='/',
                env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'})
        except Exception as error:
            record['state']='NOT_STARTED';record['failure_type']=type(error).__name__
            append(directory/'NOT_STARTED_PUBLIC.json',dict(PUBLIC_code='DYNTEAM_SYSTEM_PROBE_POPEN_NOT_STARTED',
                sequence=self.sequence,exception_type=type(error).__name__,request_replays=0))
        return self.public()

    def public(self):
        return dict(PUBLIC_code='DYNTEAM_INDEPENDENT_SYSTEM_HEALTH_CUSTODY',SYSTEM_reserved_slots=2,
            SYSTEM_occupied_slots=self.occupied(),running=sum(r['state']=='RUNNING' for r in self.records),
            physical_unknown=sum(r['state']=='UNPROVEN_PHYSICAL_UNKNOWN' for r in self.records),
            HTTP_physical_terminal=sum(r['state']=='HTTP_PHYSICAL_TERMINAL' for r in self.records),
            reported_SYSTEM_tokens=sum((r['terminal'] or {}).get('reported_tokens') or 0 for r in self.records),
            unmeasured_SYSTEM_upper=sum((r['terminal'] or {}).get('possible_unmeasured_tokens_upper',
                                        self.unmeasured_upper if r['state']!='NOT_STARTED' else 0)
                                        for r in self.records),
            explicitly_started=self.started,accepting=self.accepting,period_seconds=600,probe_output_limit=8,original_deadline_seconds=45,
            experiment_permits_used=0,experiment_financial_rows_written=0,request_replays=0,
            original_probe_source_sha256=ORIGINAL_SHA)
