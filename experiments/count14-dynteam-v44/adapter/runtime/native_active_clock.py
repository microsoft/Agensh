"""One original-owner monotonic active clock for native spawn/racing timers.

No budget/usage/accounting formula or schema change. Pure timing samples use
the SAME original ledger mutex, never a new clock->ledger lock order. Original
transaction/gate functions run exactly once; their committed control changes
bound active intervals. No wall T-15 and no work dispatch are implemented here.
"""
from contextlib import contextmanager
import json
import re
import sys
import time
from types import MethodType

from common import need


class NativeActiveClock:
    def __init__(self, core, *, monotonic_ns=None):
        need(not hasattr(core,'active_clock') and core.state=='ORIGINAL_TRANSPORT_HELD_NATIVE_BINDINGS_PENDING' and
             (monotonic_ns is None or core.qualification_only), 'DYNTEAM_ACTIVE_CLOCK_FIRST_COLD_CORE_ONLY')
        self.core,self.ledger=core,core.ledger
        self.now=time.monotonic_ns if monotonic_ns is None else monotonic_ns
        self.states={}
        self.failure_type=None
        self.latch_observer_sequence=0
        self.latch_observer_events=[]
        self.latch_observer_failed=False
        self.original_tx=self.ledger.tx
        self.original_latch=self.ledger.latch_fault
        self.original_hold=core.gate.hold_startup
        self.original_release=core.gate.release_startup
        with self.ledger.mutex:
            need(self.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]==0,
                 'DYNTEAM_ACTIVE_CLOCK_INSTALL_BEFORE_MODELS')
            self._observe_safely()
        core.active_clock=self
        # This wrapper does not add SQL writes, another transaction, swallow an
        # exception or alter original COMMIT/ROLLBACK/condition notification.
        @contextmanager
        def observed_tx(_ledger):
            with self.ledger.mutex:
                self._observe_safely()
                try:
                    with self.original_tx() as result:yield result
                finally:self._observe_safely()
        def observed_latch(_ledger,*args,**kw):
            with self.ledger.mutex:
                self._observe_safely()
                observation=self._note_latch_start(args,kw)
                returned=False
                try:
                    result=self.original_latch(*args,**kw)
                    returned=True
                    return result
                finally:
                    self._note_latch_end(observation,returned)
                    self._observe_safely()
        def gate_call(original):
            def observed(_gate,*args,**kw):
                with self.ledger.mutex:
                    self._observe_safely()
                    try:return original(*args,**kw)
                    finally:self._observe_safely()
            return observed
        self.ledger.tx=MethodType(observed_tx,self.ledger)
        self.ledger.latch_fault=MethodType(observed_latch,self.ledger)
        core.gate.hold_startup=MethodType(gate_call(self.original_hold),core.gate)
        core.gate.release_startup=MethodType(gate_call(self.original_release),core.gate)
        for fence in core.membership_fences.values():
            for name in ('request_cut','after_original_resume'):
                original=getattr(fence,name)
                setattr(fence,name,MethodType(gate_call(original),fence))

    def _note_latch_start(self,args,kw):
        # Fixed CONTROL arguments and source locations only. No exception
        # text, locals, envelope, SID, task/model/tool data, process RAM access,
        # IO, callback, new lock, or synthetic active-clock value is involved.
        try:
            self.latch_observer_sequence+=1
            if len(self.latch_observer_events)>=128:
                return None  # Keep the FIRST 128; never evict first evidence.
            trajectory=args[0] if args else kw.get('t')
            code=args[1] if len(args)>1 else kw.get('code')
            slots=tuple(self.core.rows)
            slot=slots.index(trajectory) if type(trajectory)is str and trajectory in slots else None
            fixed=code if type(code)is str and re.fullmatch(r'[A-Z][A-Z0-9_]{0,239}',code) else None
            locations=[]
            frame=sys._getframe(2)  # Original caller of the existing wrapper.
            try:
                while frame is not None and len(locations)<16:
                    file=frame.f_code.co_filename.rsplit('/',1)[-1]
                    function=frame.f_code.co_name
                    locations.append(dict(
                        file=file if re.fullmatch(r'[A-Za-z0-9_.:<>-]{1,240}',file) else 'OTHER',
                        function=function if re.fullmatch(r'[A-Za-z0-9_.<>-]{1,128}',function) else 'OTHER',
                        line=frame.f_lineno))
                    frame=frame.f_back
            finally:
                del frame
            event=dict(sequence=self.latch_observer_sequence,trajectory_slot=slot,
                fixed_code=fixed,locations=locations,original_call_state='PENDING',
                original_returned=None,no_fault_clear_or_clock_restore=True)
            self.latch_observer_events.append(event)
            return event
        except BaseException:
            self.latch_observer_failed=True
            return None  # Observation must never prevent the original latch.

    def _note_latch_end(self,event,returned):
        try:
            if event is not None:
                event['original_returned']=returned is True
                event['original_call_state']='RETURNED' if returned else 'RAISED'
        except BaseException:
            self.latch_observer_failed=True

    def public_latch_observer(self):
        # Called only by the original normal PUBLIC/STATUS path, never a new
        # endpoint. This does not read or export ledger.memory_faults itself.
        with self.ledger.mutex:
            return dict(schema='count14-original-latch-call-fixed-metadata-v1',
                total_observed_calls=self.latch_observer_sequence,
                first_events=[dict(row,locations=[dict(x)for x in row['locations']])
                              for row in self.latch_observer_events],
                maximum_events=128,first_events_not_evicted=True,
                observer_failed=self.latch_observer_failed,
                preinstallation_calls_not_recovered=True,
                original_memory_fault_contents_not_read_or_exported=True,
                original_latch_setdefault_notify_and_return_unchanged=True)

    def _mode_locked(self,t):
        account=self.ledger.account(t)
        targets=json.loads(account['targets'])
        if account['state']=='COMMITTED_PARKED' and account['stage']+1==len(targets):return 'FINAL'
        if (account['state']=='RUNNING' and t not in self.core.gate.startup_held and not self.core.gate.closed and
            not self.ledger.model_paused() and not self.ledger.admission_fault(t) and
            not self.core.membership_fences[t].public_counts()['cut_held']):return 'RUNNING'
        return 'HOLD'

    def _observe_all_locked(self):
        now=self.now()
        need(type(now) is int and now>=0,'DYNTEAM_ORIGINAL_MONOTONIC_CLOCK_VALUE')
        for t in self.core.rows:
            mode=self._mode_locked(t)
            previous=self.states.get(t)
            active=0
            if previous is not None:
                need(now>=previous['observed_ns'],'DYNTEAM_ACTIVE_CLOCK_MONOTONIC_REGRESSION')
                active=previous['active_ns']+(now-previous['observed_ns'] if previous['mode']=='RUNNING' else 0)
            self.states[t]=dict(active_ns=active,observed_ns=now,mode=mode)

    def _observe_safely(self):
        # A diagnostic/timer defect must NEVER prevent original SETTLED/UNKNOWN
        # accounting, rollback, or the real latch_fault from running. Only NEW
        # timer-driven work is held. No message/locals or I/O under this mutex.
        if self.failure_type is not None:return
        try:self._observe_all_locked()
        except Exception as error:self.failure_type=type(error).__name__

    def read(self,t):
        need(t in self.core.rows,'DYNTEAM_NATIVE_CLOCK_REGISTERED_TRAJECTORY')
        with self.ledger.mutex:
            self._observe_safely()
            need(self.failure_type is None,'DYNTEAM_ACTIVE_CLOCK_FAILED_RETAIN_NO_TIMER_ADVANCE')
            return dict(self.states[t])

    def active_now(self,t):
        return self.read(t)['active_ns']/1_000_000_000

    def checkpoint_control_state(self):
        # Fixed control metadata to include in the full writer snapshot. This
        # is NOT a paid SDK/session restore or a whole-checkpoint proof.
        with self.ledger.mutex:
            self._observe_safely()
            need(self.failure_type is None,'DYNTEAM_ACTIVE_CLOCK_FAILED_RETAIN_NO_TIMER_ADVANCE')
            return {t:dict(row) for t,row in self.states.items()}
