"""Finite CONTROL receipt work on the existing original owner loop.

No model dispatcher, grant cache, financial write, fake ACK or background poll.
Only identical *unfinished* metadata intents from the same actual peer coalesce.
An attempt after completion always gets a new real owner/physical guard check.
Expired unstarted work never takes an owner lease. If an executing handler
finishes after all clients leave, its actual partial effects remain retained;
this queue never clears an owner permit/lease or invents delivery.
"""
from collections import deque
from dataclasses import astuple, dataclass, field
import hashlib
import json
import math
import re
import threading
import time


class ControlUnstartedExpired(Exception):
    """Negative CONTROL outcome only: the exact ticket never entered RUNNING.

    This is not a model/physical-clear receipt and never forgives partial work.
    """
    def __init__(self):
        super().__init__('DYNTEAM_CONTROL_UNSTARTED_EXPIRED_NO_EFFECT')


@dataclass(eq=False)
class Waiter:
    deadline: float
    active: bool = True


@dataclass(eq=False)
class ControlTicket:
    key: str
    row: dict
    peer: tuple
    enqueued: float
    complete: threading.Event = field(default_factory=threading.Event)
    waiters: list = field(default_factory=list)
    state: str = 'QUEUED'
    result: object = None
    finished: float | None = None
    started: float | None = None

    @property
    def envelope(self):
        return self.row

    @property
    def accepted(self):
        return self.result


class OwnerControlQueue:
    def __init__(self, *, checked, timeout=30, maximum=128, result_normalizer=None):
        if not (callable(checked) and type(timeout) in (int,float) and
                math.isfinite(timeout) and 0 < timeout <= 30 and
                type(maximum) is int and 0 < maximum <= 128):
            raise ValueError('DYNTEAM_FINITE_METADATA_CONTROL_QUEUE')
        if result_normalizer is not None and not callable(result_normalizer):
            raise ValueError('DYNTEAM_TYPED_CONTROL_RESULT_NORMALIZER')
        self.checked,self.timeout,self.maximum=checked,timeout,maximum
        self.normalize=(lambda value:value if type(value) is bool else None) if result_normalizer is None else result_normalizer
        self.lock=threading.Lock()
        self.pending=deque()
        self.tickets={}
        self.counts={k:0 for k in ('coalesced','expired_before_start',
            'waiter_timeouts','handler_calls','handler_errors','receiver_true_returns',
            'receiver_false_returns','owner_true_without_live_waiter')}
        self.max_queue_wait=0.0
        self.max_handler_seconds=0.0
        self.last_errors=[]

    def _live(self,ticket,now):
        return any(w.active and w.deadline > now for w in ticket.waiters)

    def _cancel_unstarted(self,ticket):
        if ticket.state != 'QUEUED':return
        ticket.state='EXPIRED_UNSTARTED'
        if self.tickets.get(ticket.key) is ticket:del self.tickets[ticket.key]
        try:self.pending.remove(ticket)
        except ValueError:pass # already in the owner's bounded local batch
        self.counts['expired_before_start']+=1
        ticket.complete.set()

    def receive(self,row,peer,*,report_unstarted_expiry=False):
        if type(report_unstarted_expiry) is not bool:
            raise ValueError('DYNTEAM_CONTROL_TYPED_UNSTARTED_OUTCOME_SELECTION')
        self.checked(row)
        if not (type(peer) is tuple and len(peer)==3 and
                all(type(v) is int for v in peer) and
                peer[0]>0 and peer[1]>=0 and peer[2]>=0):
            raise ValueError('DYNTEAM_CONTROL_ACTUAL_PEER_TUPLE')
        # A PID/UID tuple alone is NOT an identity generation. Never merge an
        # in-progress proof with a reused PID/new namespace/changed credentials.
        # The original owner still performs its complete registry check later.
        from native_peer_registry import process_birth
        birth=process_birth(peer[0])
        if (birth.pid,birth.uid,birth.gid)!=peer:
            raise ValueError('DYNTEAM_CONTROL_PEER_BIRTH_CREDENTIALS_CHANGED')
        # Deep copy only the checked CONTROL envelope, not any science body.
        raw=json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=False,
                       allow_nan=False).encode()
        key=hashlib.sha256(raw+b'\0'+json.dumps(astuple(birth)).encode()).hexdigest()
        waiter=Waiter(time.monotonic()+self.timeout)
        with self.lock:
            ticket=self.tickets.get(key)
            if ticket is not None and ticket.state=='QUEUED' and not self._live(ticket,time.monotonic()):
                self._cancel_unstarted(ticket);ticket=None
            if ticket is None:
                if len(self.tickets)>=self.maximum:return None
                ticket=ControlTicket(key,json.loads(raw),peer,time.monotonic())
                self.tickets[key]=ticket;self.pending.append(ticket)
            else:
                if ticket.state not in ('QUEUED','RUNNING'):return None
                self.counts['coalesced']+=1
            if len(ticket.waiters)>=128:return None
            ticket.waiters.append(waiter)
        signaled=ticket.complete.wait(max(0,waiter.deadline-time.monotonic()))
        with self.lock:
            delivered=(signaled and waiter.active and ticket.state=='FINISHED' and
                       ticket.finished is not None and ticket.finished<=waiter.deadline)
            waiter.active=False
            if not delivered:
                self.counts['waiter_timeouts']+=1
                if not self._live(ticket,time.monotonic()):self._cancel_unstarted(ticket)
                # Decide under the SAME queue lock used by drain/claim. A
                # RUNNING or finished-late ticket must keep the original None
                # (ambiguous/partial) outcome; never turn that into retry.
                if (report_unstarted_expiry and ticket.state=='EXPIRED_UNSTARTED' and
                        ticket.started is None and ticket.finished is None and ticket.result is None):
                    raise ControlUnstartedExpired()
                return None
            if ticket.result is True:self.counts['receiver_true_returns']+=1
            elif ticket.result is False:self.counts['receiver_false_returns']+=1
            return ticket.result

    def drain(self,maximum=128):
        """Claim one at a time just before original owner work, outside locks."""
        if type(maximum) is not int or not 0<maximum<=128:
            raise ValueError('DYNTEAM_CONTROL_FINITE_DRAIN')
        with self.lock:
            batch=tuple(self.pending.popleft() for _ in range(min(maximum,len(self.pending))))
        for ticket in batch:
            with self.lock:
                if ticket.state!='QUEUED' or self.tickets.get(ticket.key) is not ticket:continue
                now=time.monotonic()
                if not self._live(ticket,now):
                    self._cancel_unstarted(ticket);continue
                ticket.state='RUNNING'
                ticket.started=now
                self.max_queue_wait=max(self.max_queue_wait,now-ticket.enqueued)
                self.counts['handler_calls']+=1
            yield ticket

    def resolve(self,ticket,value,*,error=None):
        """Original publisher durability decides result; never an ACK cache."""
        value=self.normalize(value)
        finished=time.monotonic()
        with self.lock:
            if (ticket.state!='RUNNING' or ticket.started is None or
                    self.tickets.get(ticket.key) is not ticket):
                raise ValueError('DYNTEAM_CONTROL_EXACT_RUNNING_TICKET_RESOLVE_ONCE')
            ticket.result=value;ticket.finished=finished;ticket.state='FINISHED'
            del self.tickets[ticket.key]
            self.max_handler_seconds=max(self.max_handler_seconds,finished-ticket.started)
            if error is not None:
                self.counts['handler_errors']+=1
                self.last_errors.append(error);self.last_errors=self.last_errors[-128:]
            if value is True and not self._live(ticket,finished):
                self.counts['owner_true_without_live_waiter']+=1
            ticket.complete.set()

    def poll_once(self,handler):
        if not callable(handler):raise ValueError('DYNTEAM_CONTROL_ORIGINAL_OWNER_HANDLER')
        processed=accepted=0
        for ticket in self.drain():
            # ALL original peer/fullbirth/COUNT/kernel/physical callbacks occur
            # outside this queue lock, once per unfinished exact intent.
            error=None
            try:
                value=self.normalize(handler(ticket.row,ticket.peer))
            except Exception as exc:
                value=None
                code=str(exc)
                error=dict(exception_type=type(exc).__name__,
                    fixed_guard_code=code if re.fullmatch(r'DYNTEAM_[A-Z0-9_]{1,240}',code) else None)
            self.resolve(ticket,value,error=error)
            processed+=1;accepted+=int(value is True)
        return dict(processed=processed,accepted=accepted)

    def public(self):
        with self.lock:
            return dict(timeout_seconds=self.timeout,maximum=self.maximum,
                pending_unstarted=len(self.pending),unfinished_intents=len(self.tickets),
                max_observed_queue_wait_seconds=self.max_queue_wait,
                max_observed_handler_seconds=self.max_handler_seconds,
                **self.counts,last_errors=list(self.last_errors))
