"""Approved R16 fix: atomic EPHEMERAL heartbeat, never ledger durability.

The existing no-fsync atomic path remains. Only repeated per-role mutex
competition is replaced by one fresh original-gate cohort read. A clock leaf is a
renewable, ten-second, exact-host/binding/boot observation, NOT a committed
checkpoint, account, request, receipt, ledger or recovery authorization.
The original owner can issue ONE explicit same-generation authorization to
its already-restored three team16 groups. Only the deployed reader's existing
lease-expiry-only branch can consume it. No router/CLI restart, signal, prompt,
request replay, accounting mutation, cgroup operation or privilege change.
"""
from contextlib import ExitStack
from pathlib import Path
import copy,hashlib,inspect,os,stat,threading,time,uuid
from types import MethodType
from common import need,digest,wire,sha
from bridge import process_identity
from native_budget_park import NativeBudgetParkProjection,SCHEMA,VALID_FOR_NS
from native_scientific_owner import NativeScientificOwner
from native_writer_fence import NativeWriterFence
from run_native_scientific6 import ScientificSixDriver
from r16_original_session_rebind import TARGETS,_role_scope
from r16_checkpoint_clock_rearm import _atomic_public,SCHEMA as REARM_SCHEMA
from r16_resume_budget_clocks import _public

ORIGINAL_SAMPLE_SHA256='e56f48465dda462453754428f79c9347e02cb99ce9820b4531e687b64b55fe60'
GAP_EVIDENCE_SHA256='2787be01e29f3c3fe324daa59c9eb6a04a929c8073a5b349692ee3a8551eaa20'
TEAM16_TARGETS={t for t in TARGETS if '/Agensh-16/' in t}
REARM_FIELDS={'schema','binding_sha256','sequence','generation'}


def sample_cohort_atomic(self):
    """Original current-owner/gate/counter/schema/file checks, no durable sync.

    Original publisher loop, stop Event, lock, object and sequence all survive.
    Only these short-lived public files omit fsync. Ordinary flush completes
    before chmod/atomic replace. No ledger/receipt/CAS writes are intercepted.
    """
    with self.lock:
        started=time.monotonic_ns();gate_ns=write_ns=0
        tick=time.monotonic_ns()
        # ONE fresh local cohort under the ORIGINAL condition/mutex. Reentrant
        # calls retain every original role, generation and pause-counter check.
        # No file writes or cross-call cache are inside this critical section.
        with self.gate.condition:
            self._current();self.sequence+=1
            snapshots={role:self.gate.budget_pause(self.t,role)for role in self.roles}
        gate_ns=time.monotonic_ns()-tick
        for role in self.roles:
            value=snapshots[role]
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
            'valid_for_ns':VALID_FOR_NS,'public_metadata_fsync_calls':0,
            'outer_gate_acquisitions':1,'cross_call_cache':False}

def _driver(d,owner):
    need(type(d)is ScientificSixDriver and d.shared_started and not d.failed and not d.finished,
         'CLOCK_REPAIR_EXACT_RUNNING_DRIVER')
    need(process_identity(os.getpid())==owner,'CLOCK_REPAIR_EXACT_LIVE_OWNER')


def _sample_pin(function):
    return hashlib.sha256(inspect.getsource(function).encode()).hexdigest()


def install_cohort_clock_publisher(driver, *, expected_owner):
    """Same original objects/threads: replace only proven instance methods.

    Historical class method stays pinned. Existing instance atomic overrides
    are checked by actual bound-source SHA, not mistaken for class behavior.
    An old in-progress sample completes normally under its original lock.
    """
    _driver(driver,expected_owner)
    need(_sample_pin(NativeBudgetParkProjection.sample)==ORIGINAL_SAMPLE_SHA256,
         'CLOCK_REPAIR_ORIGINAL_SAMPLE_SOURCE_PIN')
    projections=[]
    for t,record in sorted(driver.records.items()):
        launch=record.get('launch');c=getattr(launch,'controller',None)
        if c is None:continue
        need(type(c)is NativeScientificOwner and c.t==t and c.ledger is driver.ledger,
             'CLOCK_REPAIR_ORIGINAL_CONTROLLER')
        p=c.projection
        need(type(p)is NativeBudgetParkProjection and p.owner==expected_owner
             and p.ledger is driver.ledger and p.gate is launch.gate and p.t==t
             and set(p.roles)==set(c.team.roles),'CLOCK_REPAIR_ORIGINAL_PUBLISHER')
        if not p.closed:p._current()
        function=getattr(p.sample,'__func__',None)
        need(function is sample_cohort_atomic or function is not None and
             _sample_pin(function) in {ORIGINAL_SAMPLE_SHA256,ORIGINAL_ATOMIC_SAMPLE_SHA256},
             'CLOCK_REPAIR_CURRENT_INSTANCE_SAMPLE_SOURCE_PIN')
        projections.append(p)
    need(len(projections)==6,'CLOCK_REPAIR_SIX_CURRENT_CONTROLLERS')
    state=getattr(driver,'_r16_cohort_clock_repair',None)
    need(state is None or state['owner']==expected_owner,'CLOCK_REPAIR_NO_NEW_OWNER')
    if state is not None:
        need(all(getattr(p.sample,'__func__',None)is sample_cohort_atomic for p in projections),
             'CLOCK_REPAIR_INSTALLED_STATE_REQUIRED')
        return copy.deepcopy(state['install_receipt'])
    for p in projections:
        p._r16_before_cohort_sample=p.sample
        p.sample=MethodType(sample_cohort_atomic,p)
    receipt={'status':'ORIGINAL_PUBLISHERS_USE_SINGLE_COHORT_ATOMIC_CLOCK',
             'controllers':6,'lease_ns':VALID_FOR_NS,'no_ledger_or_account_durability_change':True,
             'restarts_thaws_tasks_requests':0}
    driver._r16_cohort_clock_repair={'owner':copy.deepcopy(expected_owner),
        'install_receipt':receipt,'rearm_status':'NOT_STARTED','roles_rearmed':{}}
    with driver.ledger.tx():driver.ledger.event('GLOBAL','R16_COHORT_CLOCK_PUBLISHER_INSTALLED',{
        **receipt,'implementation_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'bindings_sequences_pause_counters_and_original_threads_retained':True})
    return copy.deepcopy(receipt)


ORIGINAL_ATOMIC_SAMPLE_SHA256='c86aa05288231687c4c88bce02a19d1af9a774f21e20b3af6e516c6fc4f5991f'


def _existing_marker(path, binding, sequence, generation):
    if not(path.exists()or path.is_symlink()):return
    s=path.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_uid==os.geteuid() and s.st_nlink==1
         and stat.S_IMODE(s.st_mode)==0o444,'CLOCK_REPAIR_OLD_REARM_IDENTITY')
    previous=_public(path)
    need(set(previous)==REARM_FIELDS and previous['schema']==REARM_SCHEMA
         and previous['binding_sha256']==binding
         and type(previous['sequence'])is int and previous['sequence']<sequence
         and type(previous['generation'])is int and 1<=previous['generation']<=generation,
         'CLOCK_REPAIR_OLD_REARM_BINDING_MONOTONIC')


def rearm_approved_original_readers_once(driver, *, expected_owner, evidence_sha256):
    """One host-authorized repair for still-searching observed-expired readers.

    Up to48 team16 readers. Native boundaries and confirmed FINAL20M domains
    are EXCLUDED, never resumed/thawed merely to issue a nonce. a2 stays out.

    In-flight calls remain in-flight: this grants NO model/budget permission and
    does not reconnect/cancel/replay. It only supplies the existing reader's
    explicit host nonce. A non-lease security latch remains latched. Exact
    current same-generation status is validated; no synthetic checkpoint or
    generation advance is manufactured. Normal checkpoint thaw hook stays.
    """
    _driver(driver,expected_owner);sha(evidence_sha256)
    need(evidence_sha256==GAP_EVIDENCE_SHA256,'CLOCK_REPAIR_EXACT_PUBLIC_GAP_EVIDENCE')
    state=getattr(driver,'_r16_cohort_clock_repair',None)
    need(state is not None and state['owner']==expected_owner
         and all(getattr(driver.records[t]['launch'].controller.projection.sample,'__func__',None)
                 is sample_cohort_atomic for t in TEAM16_TARGETS),
         'CLOCK_REPAIR_FAST_ORIGINAL_PUBLISHER_FIRST')
    need(state['rearm_status']=='NOT_STARTED','CLOCK_REPAIR_NO_AUTOMATIC_REARM_RETRY')
    recovery=getattr(driver,'_r16_original_recovery',None)
    need(recovery is not None and recovery['owner']==expected_owner and recovery['released']
         and set(recovery['plans'])==TARGETS,'CLOCK_REPAIR_ONLY_ALREADY_RESTORED_ORIGINAL_FIVE')
    plans=[];excluded_final={};deferred_native={}
    with ExitStack()as locks:
        for t in sorted(TEAM16_TARGETS):
            c=driver.records[t]['launch'].controller;locks.enter_context(c.lock)
            need(type(c)is NativeScientificOwner and c.t==t and c.ledger is driver.ledger,
                 'CLOCK_REPAIR_ORIGINAL_CONTROLLER')
            f=driver.ledger.frontier(t)
            need(not driver.ledger.admission_fault(t),'CLOCK_REPAIR_ORIGINAL_ACTIVE_GENERATION')
            if c.state in {'FINAL_PARKED','RETIRING','RETIRED_WRITERS','CLOSED'}:
                need(f['state']=='COMMITTED_PARKED' and any(
                    point.get('point_kind')!='NATURAL_STOP' and point.get('target_tokens')==20000000
                    for point in c.points),'CLOCK_REPAIR_FINAL_POINT_NOT_INVENTED')
                excluded_final[t]={'status':'FINAL20M_RETAINED_NO_REARM_OR_THAW',
                    'controller_state':c.state,'generation':f['generation']}
                continue
            if c.cut is not None or c.stage is not None or c.state in {
                    'PARKING','PARKED','BACKUP_STARTED','COMMITTED','POINT_STARTED','POINT_QUEUED','RELEASING'}:
                deferred_native[t]={'status':'ORIGINAL_NATIVE_BOUNDARY_NO_REARM_OR_THAW',
                    'controller_state':c.state,'generation':f['generation']}
                continue
            need(c.state=='RUNNING' and f['state']=='RUNNING'
                 and type(c.fence)is NativeWriterFence and c.fence.state=='REGISTERED'
                 and c.team.writer_fence is c.fence,'CLOCK_REPAIR_NO_CHECKPOINT_STATE_CHANGE')
            plan=recovery['plans'][t]
            need(plan['controller'] is c and plan['status']=='REBOUND_ORIGINAL_SESSION'
                 and set(plan['restored_roles'])==set(c.team.roles)==set(c.projection.roles)
                 and len(c.team.roles)==16,'CLOCK_REPAIR_EXACT_RECOVERED_ROLES')
            c._shared();c.fence._coverage()
            for role,receipt in plan['restored_roles'].items():
                need(receipt['session_sha256']==plan['sessions'][role]
                     and receipt['loaded_original'] is True and receipt['prompt_sent'] is False,
                     'CLOCK_REPAIR_ORIGINAL_SESSION_RECEIPT')
                _role_scope(c.fence,receipt['router'])
                # Historical load receipt is immutable. A CLI may naturally
                # exit after a turn; never resurrect or substitute that PID.
                try:old_cli_still_same=process_identity(receipt['cli']['pid'])==receipt['cli']
                except (FileNotFoundError,ProcessLookupError):old_cli_still_same=False
                if old_cli_still_same:_role_scope(c.fence,receipt['cli'])
                # Current native children remain covered by full original
                # worker/fence coverage above, not a stale CLI receipt PID.
            p=c.projection
            need(type(p)is NativeBudgetParkProjection and p.owner==expected_owner
                 and p.ledger is driver.ledger and p.t==t,'CLOCK_REPAIR_ORIGINAL_PROJECTION')
            p._current();f=driver.ledger.frontier(t)
            need(f['state']=='RUNNING' and not driver.ledger.admission_fault(t),
                 'CLOCK_REPAIR_ORIGINAL_ACTIVE_GENERATION')
            # Accepted work is deliberately NOT cancelled or reclassified.
            plans.append((t,c,p,f['generation']))
        state['rearm_status']='INTENT_RETAINED_NO_AUTOMATIC_RETRY'
        with driver.ledger.tx():driver.ledger.event('GLOBAL','R16_ORIGINAL_READER_LEASE_REARM_INTENT',{
            'evidence_sha256':evidence_sha256,'trajectories':sorted(TEAM16_TARGETS),
            'roles':sum(len(p.roles)for _,_,p,_ in plans),'same_original_session':True,
            'excluded_final':excluded_final,'deferred_native':deferred_native,'new_tasks_prompts_replays':0})
        for t,c,p,generation in plans:
            with p.lock:
                p.sample();p._current()
                values={}
                for role in p.roles:
                    current=_public(p.directory/(role+'.json'))
                    binding=digest(p.bindings[role])
                    need(current['schema']==SCHEMA and current['binding_sha256']==binding
                         and current['sequence']==p.sequence and current['generation']==generation
                         and current['valid_for_ns']==str(VALID_FOR_NS)
                         and 0<=time.monotonic_ns()-int(current['sampled_at_mono_ns'])<VALID_FOR_NS,
                         'CLOCK_REPAIR_FRESH_SAME_ORIGINAL_TEN_SECOND_STATUS')
                    marker=p.directory/(role+'.json.rearm')
                    _existing_marker(marker,binding,p.sequence,generation)
                    values[role]={'schema':REARM_SCHEMA,'binding_sha256':binding,
                                  'sequence':p.sequence,'generation':generation}
                for role,value in values.items():
                    _atomic_public(p.directory/(role+'.json.rearm'),value)
                    state['roles_rearmed'].setdefault(t,[]).append(role)
                p.sample() # final fresh sample; no durability flush under clock lock
        # Any durable ledger work stays outside publisher locks. Original ledger
        # durability is unchanged, and there is no budget/frontier/request UPDATE.
        with driver.ledger.tx():driver.ledger.event('GLOBAL','R16_ORIGINAL_READER_LEASE_REARM_COMPLETED',{
            'evidence_sha256':evidence_sha256,'roles_rearmed':copy.deepcopy(state['roles_rearmed']),
            'excluded_final':excluded_final,'deferred_native':deferred_native,
            'pause_policy_or_counters_changed':False,'nonlease_faults_stay_latched':True,
            'model_requests_cancelled_or_replayed':0,'scientific_point_or_generation_created':False})
        state['rearm_status']='COMPLETED'
    return {'status':'ORIGINAL_ELIGIBLE_READERS_HOST_REARM_AUTHORIZATION_PUBLISHED',
            'roles':sum(len(p.roles)for _,_,p,_ in plans),
            'excluded_final':excluded_final,'deferred_native':deferred_native,'lease_ns':VALID_FOR_NS,'same_generation':True,
            'nonlease_faults_stay_latched':True,'router_CLI_restarts':0,
            'model_requests_cancelled_or_replayed':0,'does_not_claim_all_live_latches_cleared':True}
