"""Same-owner R16 public clock refresh; no journal/snapshot durability changes.

A ten-second, boot/owner/monotonic-bound projection is disposable telemetry,
not a recovery receipt. Keep flush +0444 +atomic replacement, but do not wait
for stable-storage fsync per role. Crash-recovery still requires the original
owner and the original ten-second fresh sample; no lease/reader change.
"""
from pathlib import Path
from types import MethodType
import ast,hashlib,inspect,os,stat,threading,time,uuid
from native_budget_park import NativeBudgetParkProjection,SCHEMA,BINDING,VALID_FOR_NS
from common import need,digest,wire,hash_file
from r16_resume_budget_clocks import _public

ORIGINAL_SAMPLE_SHA256='e56f48465dda462453754428f79c9347e02cb99ce9820b4531e687b64b55fe60'

def _sample_source_sha():
    # The class method is never modified. Instance-bound overrides are explicit.
    raw=inspect.getsource(NativeBudgetParkProjection.sample)
    return hashlib.sha256(raw.encode()).hexdigest()

def sample_atomic_refresh(self):
    """Original current-owner/gate/counter/schema/file checks, no durable sync.

    Original publisher loop, stop Event, lock, object and sequence all survive.
    Only these short-lived public files omit fsync. Ordinary flush completes
    before chmod/atomic replace. No ledger/receipt/CAS writes are intercepted.
    """
    with self.lock:
        started=time.monotonic_ns();gate_ns=write_ns=0
        self._current();self.sequence+=1
        for role in self.roles:
            tick=time.monotonic_ns();value=self.gate.budget_pause(self.t,role)
            gate_ns+=time.monotonic_ns()-tick
            status={'schema':SCHEMA,'binding_sha256':digest(self.bindings[role]),
                    'sequence':self.sequence,'generation':value['generation'],
                    'sampled_at_mono_ns':str(value['sampled_ns']),
                    'valid_for_ns':str(VALID_FOR_NS),'total_paused_ns':str(value['total_ns']),
                    'paused':value['paused']}
            raw=wire(status);need(len(raw)<=4096,'BUDGET_PARK_METADATA_BOUND')
            dest=self.directory/(role+'.json')
            temp=self.directory/('.'+uuid.uuid4().hex+'.partial')
            tick=time.monotonic_ns()
            fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            try:
                with os.fdopen(fd,'wb',closefd=False)as f:
                    f.write(raw);f.flush();os.fchmod(fd,0o444)
                if dest.exists():
                    st=dest.lstat()
                    need(stat.S_ISREG(st.st_mode)and st.st_uid==os.geteuid()
                         and st.st_nlink==1 and stat.S_IMODE(st.st_mode)==0o444,
                         'BUDGET_PARK_PROJECTION_REPLACED')
                    os.replace(temp,dest)
                else:os.link(temp,dest,follow_symlinks=False)
            finally:
                os.close(fd)
                if temp.exists():temp.unlink()
            write_ns+=time.monotonic_ns()-tick
        self._r16_clock_refresh_metrics={
            'sequence':self.sequence,'roles':len(self.roles),
            'sample_duration_ns':time.monotonic_ns()-started,
            'gate_read_duration_ns':gate_ns,'public_write_duration_ns':write_ns,
            'valid_for_ns':VALID_FOR_NS,'public_metadata_fsync_calls':0}

def refresh_projection(p,*,expected_bindings,expected_directory):
    """Patch just this original live producer, safely between original samples."""
    need(type(p)is NativeBudgetParkProjection,'R16_REFRESH_ORIGINAL_PROJECTION_TYPE')
    need(_sample_source_sha()==ORIGINAL_SAMPLE_SHA256,'R16_REFRESH_ORIGINAL_SAMPLE_SOURCE_PIN')
    with p.lock:
        p._current()
        need(not p.stop_event.is_set()and not p.closed,'R16_REFRESH_STOPPED_NOT_RESUMABLE')
        need(p.directory==Path(expected_directory),'R16_REFRESH_ORIGINAL_DIRECTORY')
        need(set(expected_bindings)==set(p.roles)==set(p.bindings),'R16_REFRESH_EXACT_ROLE_ROSTER')
        need(type(p.thread)is threading.Thread and p.thread.is_alive(),
             'R16_REFRESH_EXISTING_LIVE_PUBLISHER_REQUIRED')
        for role in p.roles:
            need(digest(p.bindings[role])==expected_bindings[role],'R16_REFRESH_ORIGINAL_BINDING_PIN')
        if getattr(p.sample,'__func__',None)is sample_atomic_refresh:
            return {'trajectory':p.t,'status':'ALREADY_ATOMIC_REFRESH','roles':len(p.roles),
                    'sequence':p.sequence,'publisher_restarted':False}
        need(getattr(p.sample,'__func__',None)is NativeBudgetParkProjection.sample,
             'R16_REFRESH_UNEXPECTED_SAMPLE_OVERRIDE')
        sequence=p.sequence
        need(type(sequence)is int and sequence>0,'R16_REFRESH_ORIGINAL_SEQUENCE')
        for role in p.roles:
            old=_public(p.directory/(role+'.json'))
            need(old.get('schema')==SCHEMA and old.get('binding_sha256')==expected_bindings[role]
                 and type(old.get('sequence'))is int and 0<old['sequence']<=sequence,
                 'R16_REFRESH_PUBLISHED_BINDING_SEQUENCE')
        # Never reset the original sequence/clock cursor/Event/lock/thread.
        original=p.sample;p._r16_original_durable_clock_sample=original
        p.sample=MethodType(sample_atomic_refresh,p)
        try:p.sample()
        except BaseException:
            p.ledger.latch_fault(p.t,'R16_CLOCK_REFRESH_INSTALL_FAILED_RETAINED')
            raise
        with p.ledger.tx():p.ledger.event(p.t,'R16_PUBLIC_CLOCK_ATOMIC_REFRESH_INSTALLED',{
            'prior_sequence':sequence,'first_sequence':p.sequence,'roles':len(p.roles),
            'binding_roster_sha256':digest(expected_bindings),
            'implementation_sha256':hash_file(Path(__file__))['sha256'],
            'original_class_projection_thread_lock_event_retained':True,
            'valid_for_ns':VALID_FOR_NS,'public_metadata_only_no_fsync':True,
            'ledger_receipt_snapshot_durability_unchanged':True})
        return {'trajectory':p.t,'status':'ATOMIC_REFRESH_INSTALLED','roles':len(p.roles),
                'previous_sequence':sequence,'sequence':p.sequence,'publisher_restarted':False,
                'metrics':dict(p._r16_clock_refresh_metrics)}

def install_driver_clock_refresh(driver):
    """OPS entry on original RUNNING R16 owner only. No task/charge/adoption."""
    from run_native_scientific6 import ScientificSixDriver
    need(type(driver)is ScientificSixDriver and driver.shared_started
         and not driver.failed and not driver.finished,'R16_REFRESH_LIVE_ORIGINAL_DRIVER')
    need(_sample_source_sha()==ORIGINAL_SAMPLE_SHA256,'R16_REFRESH_ORIGINAL_SAMPLE_SOURCE_PIN')
    ledger=driver.ledger;manifest_sha=digest(driver.manifest);plans=[]
    for t,record in driver.records.items():
        launch=record.get('launch');controller=getattr(launch,'controller',None)
        need(controller is not None and record.get('phase')=='ORIGINAL_TASK_RELEASED',
             'R16_REFRESH_SIX_ORIGINAL_TASKS_REQUIRED')
        p=controller.projection
        need(type(p)is NativeBudgetParkProjection and p.gate is launch.gate
             and p.ledger is ledger and p.t==t,'R16_REFRESH_ORIGINAL_LEDGER_GATE')
        need(set(p.roles)==set(record['row']['roles']),'R16_REFRESH_DRIVER_ROLE_ROSTER')
        pins={}
        for role in p.roles:
            binding=p.bindings[role]
            need(binding=={'schema':BINDING,'trajectory':t,'role':role,
                'manifest_sha256':manifest_sha,'owner':p.owner},'R16_REFRESH_MANIFEST_OWNER_BINDING')
            startup=launch.startup_bindings[role]
            ready=_public(Path(startup['directory'])/'CLOCK_READY.json')
            need(ready.get('schema')=='agensh-original-router-clock-release-v1'
                 and ready.get('binding_sha256')==startup['binding_sha256']
                 and ready.get('budget_pause_binding_sha256')==digest(binding)
                 and ready.get('budget_pause_file')==startup['clock_container_file']
                 and ready.get('budget_pause_owner_uid')==startup['owner_uid'],
                 'R16_REFRESH_ORIGINAL_CLOCK_READY_PIN')
            pins[role]=digest(binding)
        # Preflight the complete original set before changing any method.
        with p.lock:
            p._current()
            need(p.directory==controller.root/'budget-clock' and not p.stop_event.is_set()
                 and type(p.thread)is threading.Thread and p.thread.is_alive(),
                 'R16_REFRESH_ALL_ORIGINAL_PUBLISHERS_LIVE')
            need(getattr(p.sample,'__func__',None)in(NativeBudgetParkProjection.sample,sample_atomic_refresh),
                 'R16_REFRESH_UNEXPECTED_SAMPLE_OVERRIDE')
        plans.append((p,pins,controller.root/'budget-clock'))
    rows=[refresh_projection(p,expected_bindings=pins,expected_directory=directory)
          for p,pins,directory in plans]
    return {'schema':'r16-same-owner-atomic-public-clock-refresh-v1','rows':rows,
            'same_owner':True,'new_projection_thread_task_charge':False,
            'reader_lease_ns_unchanged':VALID_FOR_NS,'model_calls':0}
