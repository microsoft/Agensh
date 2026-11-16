"""Normal control-service retirement subset, never whole runtime authority.

Original UDS close exactly once in one retained timeout-observed job; original
clock stop + bounded join then original close; synchronous publisher retained;
SYSTEM/resource stop_admission + original natural poll. No core.close, journal
close, SDK/CLI close, request cancellation, signals, replay or new dispatcher.
"""
from dataclasses import asdict
from pathlib import Path
import hashlib
import importlib
import os
import threading

from bounded_metadata_ro import ReadBudget, ram_lock

PINS = dict(
    native_session_control='cba05b39fb3231f5791ba7421bf2b6a8487d081df6016885ab7f291b326cd370',
    native_metadata_publisher='a0e2fe4a193a25333424c7c4c723714bb1f2aa6b7b352c811421f59ffa9e4bdb',
    native_budget_park='2d906ac6ed892ead16abc2140b310920d8d2a8d9bdd2430e189716eb4588e93d',
    native_system_health='9786f682727d02392ef53431b793df030525c4bac7ba5b0555ee75c5ecb37163',
    native_resource_producer='c1187cd5195a3b431a6eabd330578bd911ebe3fc4405a1358944d750df48be07',
    native_spawn_protocol='b56ef5ddc84ccb1e02cd602906d1f1908c58355b5f230fc7a89f260c776b1e4b',
    native_bridge_protocol='7ccb8ac370c6d9f3d2a1688295de59cb55a2c0201b731ec72d70acc0f0cdb848',
    native_phase_proof='d11eaf0ebb39d4b08766156785a0686062b8634b7a951ca1058f1dd6d26f868a')
_REGISTERED = {}


class ServicesWait(RuntimeError):
    def __init__(self, code): self.code = code; super().__init__(code)


def need(ok, code):
    if not ok: raise ServicesWait(code)


def verify_sources():
    for name, pin in PINS.items():
        p = Path(importlib.import_module(name).__file__)
        need(p.is_absolute() and p.resolve() == p and not p.is_symlink()
             and hashlib.sha256(p.read_bytes()).hexdigest() == pin,
             'SOURCE_SERVICES_EXACT_FROZEN_ORIGINAL_API_PIN')
    return dict(PINS)


def error_public(error):
    locations, tb = [], error.__traceback__
    while tb:
        locations.append(dict(file=tb.tb_frame.f_code.co_filename, line=tb.tb_lineno,
                              function=tb.tb_frame.f_code.co_name)); tb = tb.tb_next
    return dict(exception_type=type(error).__name__, locations=locations)


class CloseJob:
    """One ORIGINAL close call. Timeout retains this same job; never re-close."""
    def __init__(self, control):
        from native_session_control import NativeSessionControl
        need(type(control) is NativeSessionControl and
             control.close.__func__ is NativeSessionControl.close,
             'SOURCE_SERVICES_ORIGINAL_CONTROL_CLOSE_METHOD')
        self.control, self.method = control, control.close
        self.completed = threading.Event(); self.failure = None; self.started = False
        self.thread = threading.Thread(target=self._run, daemon=True,
            name='count14-own-source-control-normal-close')

    def _run(self):
        try: self.method()
        except Exception as error: self.failure = error_public(error)
        finally: self.completed.set()

    def start(self):
        need(not self.started, 'SOURCE_SERVICES_ORIGINAL_CONTROL_CLOSE_ONCE')
        self.started = True; self.thread.start()

    def observe(self, budget):
        budget.check()
        if self.started and self.thread.is_alive():
            self.thread.join(timeout=min(.05, budget.remaining()))
        budget.check()
        return self.completed.is_set() and not self.thread.is_alive() and self.failure is None


class SourceServicesRetirement:
    def __init__(self, owner):
        from native_cold_owner import NativeColdOwner
        from normal_cold_sealer import NormalColdCandidateSealer
        need(type(owner) is NativeColdOwner and not owner.core.qualification_only and
             type(owner.normal_cold_sealer) is NormalColdCandidateSealer and
             not owner.normal_cold_sealer.requested and not owner.normal_cold_sealer.publication_started and
             not owner.normal_cold_sealer.cohort.activation_attempted,
             'SOURCE_SERVICES_INSTALL_ONLY_NEW_NORMAL_FIRST_COLD_BEFORE_PAID')
        self._install(owner.core, owner=owner, own=False)
        owner.source_services_retirement = self

    def _install(self, core, *, owner, own):
        from original_relay_core import OriginalRelayCore
        from native_session_control import NativeSessionControl, NativeSessionInbox
        from native_metadata_publisher import NativeMetadataPublisher
        from native_spawn_protocol import NativeSpawnInbox
        from native_bridge_protocol import NativeBridgeInbox
        from native_phase_proof import NativePhaseProofInbox
        from native_budget_park import NativeBudgetParkProjection
        from native_peer_registry import process_birth
        from native_system_health import NativeSystemHealth
        from native_resource_producer import NativeResourceProducer
        verify_sources()
        need(type(core) is OriginalRelayCore and core.qualification_only is own and
             id(core) not in _REGISTERED and not hasattr(core, 'source_services_retirement') and
             type(core.control) is NativeSessionControl and type(core.publisher) is NativeMetadataPublisher,
             'SOURCE_SERVICES_EXACT_COLD_ORIGINAL_CORE_AND_REGISTERED_CONTROL')
        need(type(core.inbox) is NativeSessionInbox and type(core.spawn_inbox) is NativeSpawnInbox and
             type(core.bridge_inbox) is NativeBridgeInbox and type(core.phase_proof_inbox) is NativePhaseProofInbox and
             core.publisher.inbox is core.inbox and set(core.clocks) == set(core.rows) and
             all(type(c) is NativeBudgetParkProjection and c.gate is core.gate and not c.closed
                 for c in core.clocks.values()), 'SOURCE_SERVICES_ORIGINAL_INBOX_PUBLISHER_AND_CLOCK_SET')
        self.core, self.owner, self.OWN = core, owner, own
        self.birth = process_birth(os.getpid()); self.thread = threading.get_ident()
        self.control = core.control; self.publisher = core.publisher
        self.clocks = dict(core.clocks); self.closed_clocks = {}
        self.inboxes = {n:getattr(core, n) for n in ('inbox','spawn_inbox','bridge_inbox','phase_proof_inbox')}
        self.pending = {n:v.pending for n,v in self.inboxes.items()}
        self.tickets = core.inbox.tickets
        self.journals = dict(core.journals)
        self.system = getattr(core, 'system_health', None)
        self.resource = getattr(core, 'resource_producer', None)
        need(self.system is None or type(self.system) is NativeSystemHealth,
             'SOURCE_SERVICES_ORIGINAL_SYSTEM_COMPONENT_IF_REGISTERED')
        need(self.resource is None or type(self.resource) is NativeResourceProducer,
             'SOURCE_SERVICES_ORIGINAL_RESOURCE_COMPONENT_IF_REGISTERED')
        self.job = CloseJob(self.control)
        self.requested = False; self.state = 'COLD_INSTALLED_NOT_REQUESTED'
        self.failure = None; self.wait_code = None; self.last = None
        self.stopped_sequences = None
        _REGISTERED[id(core)] = self; core.source_services_retirement = self

    def _current(self):
        from native_peer_registry import process_birth
        need(_REGISTERED.get(id(self.core)) is self and self.core.source_services_retirement is self and
             self.thread == threading.get_ident() and process_birth(os.getpid()) == self.birth and
             self.core.control is self.control and self.core.publisher is self.publisher and
             getattr(self.core,'system_health',None) is self.system and
             getattr(self.core,'resource_producer',None) is self.resource and
             all(self.core.clocks.get(t) is c for t,c in self.clocks.items()) and
             all(getattr(self.core,n) is v and v.pending is self.pending[n] for n,v in self.inboxes.items()) and
             self.core.inbox.tickets is self.tickets and
             all(self.core.journals.get(t) is j and self.publisher.journals.get(t) is j for t,j in self.journals.items()),
             'SOURCE_SERVICES_EXACT_SAME_OWNER_THREAD_AND_ORIGINAL_OBJECTS')
        need(not self.core.ledger.mutex._is_owned() and not self.core.queue.mutex._is_owned(),
             'SOURCE_SERVICES_NEVER_WAIT_IO_OR_CLOSE_UNDER_SCIENCE_LOCK')

    def _preflight(self, budget):
        self._current(); budget.check()
        if not self.OWN:
            from normal_inert_cut import _retired_transport
            source = self.owner.normal_cold_sealer
            need(source.state == 'NORMAL_SOURCE_CANDIDATE_WRITTEN_NOT_READY' and
                 source.control_reference is not None and source.handoff_reference is not None,
                 'SOURCE_SERVICES_WAIT_ORIGINAL_PRE_RETIREMENT_DURABLE_CANDIDATE')
            _retired_transport(self.owner, budget)

    def request(self, *, read_budget):
        need(type(read_budget) is ReadBudget, 'SOURCE_SERVICES_FINITE_CALLER_BUDGET')
        self._preflight(read_budget)
        need(not self.requested, 'SOURCE_SERVICES_REQUEST_ONCE_RETAIN_NO_REPLAY')
        self.requested = True; self.state = 'STOPPING_ADMISSION_AND_ORIGINAL_CONTROL'
        # Original methods are RAM-only. Existing request/cost/child untouched.
        if self.system is not None: self.system.stop_admission()
        if self.resource is not None: self.resource.stop_admission()
        self.stopped_sequences = dict(SYSTEM=None if self.system is None else self.system.sequence,
                                      resource=None if self.resource is None else self.resource.sequence)
        self.job.start()
        return self.public()

    def _inbox_counts(self, budget):
        rows = {}
        for name, inbox in self.inboxes.items():
            with ram_lock(inbox.lock, budget):
                row = dict(pending=len(inbox.pending))
                if name == 'inbox': row.update(tickets=len(inbox.tickets), unresolved=inbox.unresolved)
                rows[name] = row
        return rows

    def _control_retired(self, budget):
        from native_session_control import NativeSessionControl
        need(self.control.close.__func__ is NativeSessionControl.close,
             'SOURCE_SERVICES_STILL_ORIGINAL_CONTROL_API')
        if not self.job.observe(budget): return False
        slots = self.control.server.control_slots
        with ram_lock(slots._cond, budget):
            clear = slots._value == slots._initial_value == 16
        return self.control.started and not self.control.thread.is_alive() and \
            self.control.server.socket.fileno() == -1 and clear

    def _stop_clocks(self, budget):
        from native_budget_park import NativeBudgetParkProjection
        for t, clock in self.clocks.items():
            if t in self.closed_clocks: continue
            budget.check()
            need(clock.close.__func__ is NativeBudgetParkProjection.close,
                 'SOURCE_SERVICES_STILL_ORIGINAL_CLOCK_CLOSE_API')
            clock.stop_event.set()  # normal original stop control; never force unlock/interrupt
            thread = clock.thread
            if thread is not None and thread.is_alive():
                thread.join(timeout=min(.05, budget.remaining()))
            if thread is not None and thread.is_alive(): return False
            with ram_lock(clock.lock, budget):
                # Original close's only join now sees a physically dead thread.
                # No scientific lock held; original file/bindings/sequence kept.
                clock.close()
                need(clock.closed and clock.stop_event.is_set() and
                     (clock.thread is None or not clock.thread.is_alive()),
                     'SOURCE_SERVICES_WAIT_TRUE_NORMAL_CLOCK_THREAD_END')
                self.closed_clocks[t] = dict(clock=clock, thread=clock.thread, sequence=clock.sequence)
            return False  # one original clock close per poll, not a bulk wait
        return True

    def _natural(self, service):
        if service is None: return dict(registered=False, accepting=None, physical_clear=None, live_children=None)
        need(service.accepting is False, 'SOURCE_SERVICES_ADMISSION_REMAINS_STOPPED')
        service.poll()  # original sole-owner terminal processing, never new admit
        live = sum(r['child'] is not None and r['child'].poll() is None for r in service.records)
        return dict(registered=True, accepting=service.accepting,
                    physical_clear=service.physical_clear(), live_children=live)

    def _service_projection(self, service):
        if service is None:
            return dict(registered=False, original_public=None, records=None,
                        child_handles=None, live_children=None, physical_clear=None)
        states = {}
        live = handles = 0
        for r in service.records:
            state = r['state']; states[state] = states.get(state, 0) + 1
            child = r['child']
            handles += child is not None
            live += child is not None and child.poll() is None
        return dict(registered=True, original_public=service.public(), records=len(service.records),
            record_state_counts=states, child_handles=handles, live_children=live,
            physical_clear=service.physical_clear(), constructor_or_probe_restarted=False,
            original_request_records_and_financial_totals_retained=True)

    def poll(self, *, read_budget):
        need(type(read_budget) is ReadBudget, 'SOURCE_SERVICES_FINITE_CALLER_BUDGET')
        self._current()
        if not self.requested or self.failure is not None: return self.public()
        try:
            self._preflight(read_budget)
            self.wait_code = None
            system, resource = self._natural(self.system), self._natural(self.resource)
            read_budget.check()
            need(self.stopped_sequences == dict(SYSTEM=None if self.system is None else self.system.sequence,
                resource=None if self.resource is None else self.resource.sequence),
                'SOURCE_SERVICES_NO_NEW_PROBE_OR_SAMPLE_AFTER_STOP_ADMISSION')
            self.last = dict(SYSTEM=system, resource=resource)
            if not self._control_retired(read_budget):
                if self.job.failure is not None:
                    self.failure = self.job.failure; self.state = 'ORIGINAL_CONTROL_CLOSE_FAILED_RETAIN_NO_RETRY'
                else:
                    self.state = 'WAIT_SAME_ORIGINAL_CLOSE_JOB_OR_EXISTING_HANDLERS'
                return self.public()
            counts = self._inbox_counts(read_budget); self.last['inboxes'] = counts
            if any(r['pending'] or r.get('unresolved', 0) for r in counts.values()):
                self.state = 'WAIT_ORIGINAL_OWNER_PUBLISHER_PENDING_RETAINED'; return self.public()
            if not self._stop_clocks(read_budget):
                self.state = 'WAIT_ORIGINAL_CLOCKS_NORMAL_STOP'; return self.public()
            if any(r['registered'] and (r['live_children'] or r['physical_clear'] is not True)
                   for r in (system, resource)):
                self.state = 'WAIT_SYSTEM_RESOURCE_ORIGINAL_NATURAL_TERMINAL'; return self.public()
            self.state = 'ORIGINAL_SERVICE_SUBSET_RETIRED_JOURNALS_SDK_RETAINED'
        except ServicesWait as error: self.wait_code = error.code
        except Exception as error:
            from normal_cold_sealer import ObservationNotStable
            if isinstance(error, ObservationNotStable):
                self.wait_code = 'SOURCE_SERVICES_CONTROL_READ_DEADLINE_RETAIN_SAME_JOB'
                return self.public()
            self.failure = error_public(error); self.state = 'PARTIAL_RETAINED_NO_RETRY'
        return self.public()

    def clock_retired_RAM(self, clock):
        """Pure control predicate usable inside the ORIGINAL clock RLock."""
        row = self.closed_clocks.get(clock.t)
        return self.requested and row is not None and row['clock'] is clock and \
            self.core.clocks.get(clock.t) is clock and clock.closed and clock.stop_event.is_set() and \
            clock.thread is row['thread'] and (clock.thread is None or not clock.thread.is_alive()) and \
            clock.sequence == row['sequence']

    def observe(self, *, read_budget):
        """Fixed real post-retirement metadata, no old HTTP poll or state body."""
        self._preflight(read_budget)
        need(self.state == 'ORIGINAL_SERVICE_SUBSET_RETIRED_JOURNALS_SDK_RETAINED' and
             self.failure is None and self._control_retired(read_budget),
             'SOURCE_SERVICES_WAIT_TRUE_ORIGINAL_RETIRED_SUBSET')
        counts = self._inbox_counts(read_budget)
        need(all(not r['pending'] and not r.get('unresolved', 0) for r in counts.values()) and
             all(self.clock_retired_RAM(c) for c in self.clocks.values()),
             'SOURCE_SERVICES_POST_SAME_EMPTY_INBOXES_AND_ENDED_CLOCKS')
        for service in (self.system, self.resource):
            if service is not None:
                need(not service.accepting and service.physical_clear() and
                     all(r['child'] is None or r['child'].poll() is not None for r in service.records),
                     'SOURCE_SERVICES_POST_ORIGINAL_SYSTEM_RESOURCE_PHYSICAL_CLEAR')
        return dict(schema='count14-normal-source-services-retired-subset-v1', OWN=self.OWN,
            owner_birth=asdict(self.birth), native_control_listener_and_handlers_ended=True,
            original_control_close_calls=1, control_close_job_alive=self.job.thread.is_alive(),
            inbox_counts=counts, publisher_synchronous=True, publisher_instance_retained=True,
            journal_connections_retained_for_post_capture=True,
            clocks={t:dict(sequence=c.sequence, closed=c.closed, stop_set=c.stop_event.is_set(),
                thread_alive=False) for t,c in sorted(self.clocks.items())},
            SYSTEM=self._service_projection(self.system), resource=self._service_projection(self.resource),
            CLI_retired=False, SDK_retired=False, safe_to_TERM=False,
            paid_activation_authorized=False, whole_runnable_ready=False)

    def public(self):
        return dict(PUBLIC_code='NORMAL_SOURCE_SERVICES_RETIREMENT_SUBSET', OWN=self.OWN,
            state=self.state, requested=self.requested, wait_code=self.wait_code, failure=self.failure,
            original_close_job_started=self.job.started, original_close_job_alive=self.job.thread.is_alive(),
            clocks_closed=len(self.closed_clocks), clocks_registered=len(self.clocks),
            publisher_synchronous=True, journals_retained=True, CLI_retired=False, SDK_retired=False,
            safe_to_TERM=False, paid_activation_authorized=False, whole_runnable_ready=False)


def install_OWN(core):
    """Explicit real-component harness namespace, cannot install production."""
    need(core.qualification_only is True, 'SOURCE_SERVICES_OWN_ONLY_ORIGINAL_OWN_CORE')
    result = object.__new__(SourceServicesRetirement)
    result._install(core, owner=None, own=True)
    return result


def registered(core):
    result = _REGISTERED.get(id(core))
    need(type(result) is SourceServicesRetirement and result.core is core and
         core.source_services_retirement is result,
         'SOURCE_SERVICES_EXACT_REGISTERED_PHYSICAL_RETIREMENT_NOT_CALLER_BOOLEAN')
    return result
