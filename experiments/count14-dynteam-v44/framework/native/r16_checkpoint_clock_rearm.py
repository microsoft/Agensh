"""Exact retained-owner checkpoint thaw hook. No process/model/session action.

This explicit host authorization clears ONLY reader lease-expiry latches. It
never clears file/binding/parent/regression faults, changes a ten-second lease,
replays a request, or releases a gate itself. Installed before rebuilding the
approved routers. New reader code is required; old loaded Node is not patched.
"""
from contextlib import ExitStack
from pathlib import Path
import hashlib,inspect,os,stat,uuid
from bridge import process_identity
from common import need,digest,wire,hash_file
from native_budget_park import NativeBudgetParkProjection
from native_writer_fence import NativeWriterFence

SCHEMA='agensh-checkpoint-clock-rearm-v1'
ORIGINAL_RELEASE_SHA256='e97217bef7a529269a0f54a1d97beb7c0f0ee3c2adb552acf9870831b6c0c338'

def _atomic_public(path, value):
    path=Path(path);raw=wire(value)
    need(len(raw)<=4096,'CHECKPOINT_REARM_METADATA_BOUND')
    if path.exists() or path.is_symlink():
        s=path.lstat()
        need(stat.S_ISREG(s.st_mode) and s.st_uid==os.geteuid() and s.st_nlink==1
             and stat.S_IMODE(s.st_mode)==0o444,'CHECKPOINT_REARM_OLD_METADATA_IDENTITY')
    temp=path.parent/('.rearm-'+uuid.uuid4().hex+'.partial')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb',closefd=False)as f:
            f.write(raw);f.flush();os.fchmod(fd,0o444)
        os.replace(temp,path)
    finally:
        os.close(fd)
        if temp.exists():temp.unlink()

def rearm_before_thaw(projection, fence):
    """After native stage resumes, BEFORE the first whole-team domain thaws."""
    p=projection
    need(type(p)is NativeBudgetParkProjection and type(fence)is NativeWriterFence
         and fence.whole_team is not None and fence.state=='PARKED'
         and p.ledger is fence.ledger and p.t==fence.t
         and getattr(fence.owner,'_r16_budget_pause_projection',None)is p,
         'CHECKPOINT_REARM_EXACT_HOST_PROJECTION_FENCE')
    fence._coverage()
    need(all(d.frozen() and d.read('cgroup.freeze').strip()=='1'for d in fence.domains),
         'CHECKPOINT_REARM_ALL_TEAM_STILL_FROZEN')
    with p.lock:
        p._current()
        f=p.ledger.frontier(p.t)
        need(f['state']=='RUNNING' and f['generation']==fence.cut.cut['generation']+1,
             'CHECKPOINT_REARM_NATIVE_SUCCESSOR_NOT_ACTIVE')
        # Same original publisher/object/counters, no lease or cursor reset.
        p.sample();sequence=p.sequence
        values={r:{'schema':SCHEMA,'binding_sha256':digest(p.bindings[r]),
                   'sequence':sequence,'generation':f['generation']}for r in p.roles}
        # Preflight every previous leaf before any replacement.
        for r,v in values.items():
            path=p.directory/(r+'.json.rearm')
            if path.exists()or path.is_symlink():
                s=path.lstat()
                need(stat.S_ISREG(s.st_mode) and s.st_uid==os.geteuid() and s.st_nlink==1
                     and stat.S_IMODE(s.st_mode)==0o444,'CHECKPOINT_REARM_OLD_METADATA_IDENTITY')
                from r16_resume_budget_clocks import _public
                previous=_public(path)
                need(set(previous)==set(v) and previous['schema']==SCHEMA
                     and previous['binding_sha256']==v['binding_sha256']
                     and type(previous['sequence'])is int and previous['sequence']<sequence
                     and type(previous['generation'])is int and previous['generation']<f['generation'],
                     'CHECKPOINT_REARM_MONOTONIC_AUTHORIZATION')
        for r,v in values.items():_atomic_public(p.directory/(r+'.json.rearm'),v)
        # Refresh after writing ALL markers, while every domain is still frozen.
        with p.ledger.tx():p.ledger.event(p.t,'R16_HOST_CHECKPOINT_CLOCK_REARM_AUTHORIZED',{
            'generation':f['generation'],'authorization_sequence':sequence,
            'minimum_fresh_status_sequence':p.sequence+1,'roles':len(values),
            'binding_roster_sha256':digest({r:v['binding_sha256']for r,v in values.items()}),
            'cut_sha256':fence.cut.cut_sha,'all_team_frozen_before_native_thaw':True,
            'lease_ns_unchanged':10_000_000_000,'budget_requests_or_sessions_modified':False})
        # Do not place a potentially slow durable ledger commit between this
        # final fresh sample and native thaw. Original lease stays ten seconds.
        p.sample()
        return {'generation':f['generation'],'sequence':sequence,'roles':len(values)}

def request_release_with_checkpoint_rearm(self, stage, gate):
    """Prepare ALL original ports; existing gate resumes; thaw same domains.

    Original parked host HTTP calls may be admitted after gate release;
    already-SENT work still retains its normal custody if a thaw fails.
    This does not establish native router/CLI watchdog park compatibility.
    At20M there is no successor, so it rejects before ANY thaw/port change.
    """
    from native_stage_binding import NativeStageBinding
    from admission_gate import AdmissionGate
    need(type(stage) is NativeStageBinding and type(gate) is AdmissionGate
         and stage.ledger is self.ledger and gate.ledger is self.ledger
         and stage.trajectory == self.t and stage.old == self.cut.cut['generation'],
         'WRITER_FENCE_ORIGINAL_STAGE_AND_GATE')
    need(self.state == 'PARKED', 'WRITER_FENCE_RELEASE_ONCE_FROM_PARKED')
    # Stage constructor has verified committed snapshot and actual successor.
    row = self.ledger.db.execute('SELECT ref_sha FROM snapshots WHERE trajectory=? AND generation=?',
                                 (self.t,self.cut.cut['generation'])).fetchone()
    need(row is not None and row[0] == stage.ref, 'WRITER_FENCE_ORIGINAL_COMMITTED_REFERENCE')
    self._coverage();need(all(d.frozen() for d in self.domains), 'WRITER_FENCE_PARK_LOST')
    try:
        stage.prepare_team(self.owner)
        stage.resume_team(gate,self.owner)
        projection = getattr(self.owner, '_r16_budget_pause_projection', None)
        if projection is not None:
            rearm_before_thaw(projection, self)
        self.state = 'RELEASE_REQUESTED'
        with self.ledger.tx():
            self.ledger.event(self.t,'NATIVE_WRITER_SAME_LIVE_RELEASE_REQUESTED',
                {'cut_sha256':self.cut.cut_sha,'snapshot_sha256':stage.ref,
                 'domains_sha256':self.domains_sha})
        for domain in self.domains:
            domain.request(False)
    except BaseException:
        self.state = 'RELEASE_INCOMPLETE'
        self.ledger.latch_fault(self.t,'NATIVE_WRITER_RELEASE_INCOMPLETE_RETAIN_NO_RETRY')
        raise

def install_driver_checkpoint_clock_rearm(driver, *, expected_owner):
    """Fixed apply-fix action in the SAME retained owner. Install, never thaw.

    Locks every original controller, including the active b1 replacement a2.
    No controller/gate/fault/session/queue/ledger-state reset occurs here.
    """
    from run_native_scientific6 import ScientificSixDriver
    from native_scientific_owner import NativeScientificOwner
    need(type(driver)is ScientificSixDriver and driver.shared_started
         and not driver.failed and not driver.finished,
         'CHECKPOINT_REARM_ORIGINAL_LIVE_DRIVER')
    need(process_identity(os.getpid())==expected_owner,'CHECKPOINT_REARM_EXACT_RETAINED_OWNER')
    current=NativeWriterFence.request_release
    installed=current is request_release_with_checkpoint_rearm
    need(installed or hashlib.sha256(inspect.getsource(current).encode()).hexdigest()==ORIGINAL_RELEASE_SHA256,
         'CHECKPOINT_REARM_ORIGINAL_RELEASE_SOURCE_PIN')
    plans=[]
    with ExitStack()as locks:
        for t,record in sorted(driver.records.items()):
            launch=record.get('launch');c=getattr(launch,'controller',None)
            if c is None:continue
            need(type(c)is NativeScientificOwner,'CHECKPOINT_REARM_ORIGINAL_CONTROLLER')
            locks.enter_context(c.lock)
            need(not c.step_in_progress and c.ledger is driver.ledger and c.t==t,
                 'CHECKPOINT_REARM_CONTROLLER_BOUNDARY')
            p=c.projection
            need(type(p)is NativeBudgetParkProjection and p.owner==expected_owner
                 and p.ledger is driver.ledger and p.gate is launch.gate and p.t==t
                 and set(p.roles)==set(c.team.roles),'CHECKPOINT_REARM_ORIGINAL_PROJECTION')
            with p.lock:p._current()
            prior=getattr(c.team,'_r16_budget_pause_projection',None)
            need(prior is None or prior is p,'CHECKPOINT_REARM_NO_PROJECTION_REBIND')
            plans.append((t,c,p))
        need(len(plans)==6,'CHECKPOINT_REARM_ALL_SIX_INCLUDING_NEW_B1_ATTEMPT')
        for t,c,p in plans:c.team._r16_budget_pause_projection=p
        NativeWriterFence.request_release=request_release_with_checkpoint_rearm
        with driver.ledger.tx():
            for t,c,p in plans:driver.ledger.event(t,'R16_CHECKPOINT_CLOCK_REARM_HOOK_INSTALLED',{
                'implementation_sha256':hash_file(Path(__file__))['sha256'],
                'original_projection_and_team_retained':True,'current_controller_state':c.state,
                'triggered_thaw_or_task_or_request':False})
    return {'schema':'r16-checkpoint-clock-rearm-install-v1','controllers':len(plans),
            'same_original_owner':True,'already_installed':installed,
            'new_task_model_prompt_thaw_replay':False,'original_lease_ns':10_000_000_000}
