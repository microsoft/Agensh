"""Same-live-instance admission parking at a budget cut, never upstream retry.

This host-side gate owns *unadmitted* local requests while a cut is captured.
The same relay call/response ID remains in memory. It never resends SENT work,
restarts the CLI, supplies role quiescence proof, or automatically resumes a cut.
Native CLI/tool/service fences remain required before snapshot capture.
"""
import threading,json,time
from common import need,Refused,integer

class AdmissionGate:
    def __init__(self,ledger,*,global_allocated_cap=96,search_allocated_cap=None):
        integer(global_allocated_cap,'ALLOCATED_CAP',1);need(global_allocated_cap<=96,'ALLOCATED_CAP');self.global_cap=global_allocated_cap
        self.search_cap=global_allocated_cap if search_allocated_cap is None else search_allocated_cap
        integer(self.search_cap,'SEARCH_ALLOCATED_CAP',1);need(self.search_cap<=self.global_cap,'SEARCH_ALLOCATED_CAP')
        self.ledger=ledger;self.condition=ledger.capacity_changed;self.waiters={};self.closed=False;self._budget_pause={};self.startup_held=set()
    def hold_startup(self,trajectory):
        """First-start only; expose original metadata endpoints before prompt.

        Original ACP/CLI can initialize while all actual model sends stay
        UNSENT. It is not a fault, cancellation, model request or paid retry.
        """
        with self.condition:
            f=self.ledger.frontier(trajectory)
            need(not self.closed and f['state']=='RUNNING' and f['generation']==1
                 and self.ledger.db.execute('SELECT COUNT(*) FROM requests WHERE trajectory=?',(trajectory,)).fetchone()[0]==0,
                 'STARTUP_HOLD_BEFORE_FIRST_MODEL')
            with self.ledger.tx():
                need(self.ledger.db.execute("SELECT COUNT(*) FROM events WHERE trajectory=? AND kind='NATIVE_STARTUP_SEARCH_HELD'",(trajectory,)).fetchone()[0]==0,
                     'STARTUP_HOLD_ONCE')
                self.ledger.event(trajectory,'NATIVE_STARTUP_SEARCH_HELD',{'dispatches':0})
            self.startup_held.add(trajectory)
    def release_startup(self,trajectory):
        with self.condition:
            f=self.ledger.frontier(trajectory)
            need(not self.closed and trajectory in self.startup_held
                 and not self.ledger.admission_fault(trajectory) and f['state']=='RUNNING'
                 and f['generation']==1 and f['unresolved']==f['reserved']==0,
                 'STARTUP_RELEASE_ORIGINAL_UNSENT_HOLD')
            with self.ledger.tx():self.ledger.event(trajectory,'NATIVE_STARTUP_SEARCH_RELEASED',{'replay':False})
            self.startup_held.remove(trajectory);self.condition.notify_all()
    def notify(self):
        with self.condition:self.condition.notify_all()
    def _pause(self,identity,paused):
        # Original gate mutex held. Counters survive an entire missed projection
        # interval: a router frozen across a cut must not see that wall time as
        # model/ACP silence after thaw. Only genuine budget-cut waits count.
        now=time.monotonic_ns()
        state=self._budget_pause.setdefault(identity,{'total_ns':0,'since_ns':None})
        if paused and state['since_ns'] is None:state['since_ns']=now
        elif not paused and state['since_ns'] is not None:
            state['total_ns']+=now-state['since_ns'];state['since_ns']=None
    def budget_pause(self,trajectory,role):
        with self.condition:
            f=self.ledger.frontier(trajectory)
            self.ledger._identity(trajectory,role,f['generation'])
            state=self._budget_pause.get((trajectory,role),{'total_ns':0,'since_ns':None})
            now=time.monotonic_ns();since=state['since_ns']
            return {'total_ns':state['total_ns']+(0 if since is None else now-since),
                    'paused':since is not None,'request_id':self.waiters.get((trajectory,role)),
                    'sampled_ns':now,'generation':f['generation']}
    def reserve(self,trajectory,role,rid,upper,proof_sha,request_payload,*,pending_store=None,admission_guard=None):
        need(admission_guard is None or callable(admission_guard),'ADMISSION_GUARD_HOST_CALLABLE')
        identity=(trajectory,role)
        with self.condition:
            need(identity not in self.waiters,'ROLE_ADMISSION_ALREADY_WAITING')
            self.waiters[identity]=rid
            if pending_store is not None:pending_store.park(rid,identity,request_payload)
            try:
                while True:
                    if admission_guard is not None:admission_guard()
                    need(not self.closed,'ADMISSION_GATE_SHUTDOWN_NO_SEND')
                    need(not self.ledger.admission_fault(trajectory),'TRAJECTORY_FAULT_NO_SEND')
                    need(not hasattr(self.ledger,'model_capacity_global_cap')or self.ledger.model_capacity_global_cap==self.global_cap,'SHARED_CAPACITY_ALLOCATION_BINDING')
                    f=self.ledger.frontier(trajectory)
                    final=f['state']=='COMMITTED_PARKED' and self.ledger.account(trajectory)['stage']+1>=len(json.loads(self.ledger.account(trajectory)['targets']))
                    need(not final,'SEARCH_FINAL_STOP_NO_SEND')
                    need(f['state']not in ('FAULT',),'TRAJECTORY_FAULT_NO_SEND')
                    sanity=getattr(self,'formal_early_sanity',None)
                    if sanity is not None and sanity.check(trajectory):
                        self._pause(identity,True)
                        self.condition.wait(timeout=.25)
                        continue
                    if trajectory in self.startup_held:
                        self._pause(identity,True)
                        self.condition.wait(timeout=.25 if admission_guard is not None else None)
                        continue
                    self._pause(identity,f['state'] in ('DRAINING','CAPTURING','COMMITTED_PARKED'))
                    if f['state']=='RUNNING':
                        if self.ledger.model_paused():self.condition.wait(timeout=.25 if admission_guard is not None else None);continue
                        n=self.ledger.global_unresolved()
                        search_n=self.ledger.db.execute("SELECT COUNT(*) FROM requests WHERE state IN ('RESERVED','SENT','UNKNOWN')").fetchone()[0]
                        if n>=self.global_cap or search_n>=self.search_cap:
                            self.condition.wait(timeout=.25 if admission_guard is not None else None);continue
                        try:
                            self.ledger.reserve(trajectory,role,f['generation'],rid,upper,proof_sha)
                            if pending_store is not None:pending_store.admitted(rid,f['generation'])
                            return f['generation']
                        except Refused as exc:
                            if exc.code not in ('ROLE_ALREADY_INFLIGHT','TRAJECTORY_CAPACITY','BUDGET_BOUNDARY'):raise
                            # Pending actual requests may release their conservative
                            # reserve. Wait for original settlements, don't preempt.
                            if exc.code=='BUDGET_BOUNDARY' and f['unresolved']==0:
                                self.ledger.close_admission(trajectory,'BUDGET_TAIL_CLOSED')
                                self._pause(identity,True)
                    self.condition.wait(timeout=.25 if admission_guard is not None else None)
            finally:
                self._pause(identity,False)
                self.waiters.pop(identity,None)
                self.condition.notify_all()
    def resume_next(self,trajectory,*,verified_snapshot_sha256):
        # Called by trusted owner only AFTER complete no-clobber snapshot commit.
        with self.condition:
            f=self.ledger.frontier(trajectory)
            r=self.ledger.db.execute('SELECT ref_sha FROM snapshots WHERE trajectory=? AND generation=?',(trajectory,f['generation'])).fetchone()
            need(r is not None and r[0]==verified_snapshot_sha256,'COMMITTED_SNAPSHOT_REQUIRED_BEFORE_RESUME')
            result=self.ledger.resume_next(trajectory);self.condition.notify_all();return result
    def shutdown(self):
        with self.condition:self.closed=True;self.condition.notify_all()
