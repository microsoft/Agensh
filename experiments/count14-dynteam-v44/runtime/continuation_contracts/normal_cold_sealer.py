"""Fixed-source same-owner normal barrier metadata candidate producer.

NOT an authoritative handoff/cold-ready proof. No SDK/CAS/PKL/private log body
read/hash, financial rewrite/backup, model dispatch, force stop, new thread, or
raw SID is exported. Only registered framework controls and existing refs/pins.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
import copy
import hashlib
import importlib
import json
import os
import stat
import threading
import time

PINS=dict(normal_cold_barrier='a778d6cde3bdb8840919231bb8336b4635762be9923cf1315d067461654f753e',
    normal_cold_barrier_cold='d044cefffc215b2fc583f7d99a4485d773fcac28dcad577ca12cd0e3e0932d3f',
    native_cold_owner='22af3bfe52f711ee27bb4e523ed8ab13d375528b05f927afcb64c921095b5ddf',
    original_relay_core='89ac900e66caa67887504522c574c1870f7a8faf51542fe248ca7f35b1541556',
    native_formal_cohort='7a38d82988e3c60181ece17e541c4c86c644ce160dfedba66fe235d5d03b7723',
    anonymous_roster_journal='853a333ead7beb01229412f96d00a1947803b8ad3e8f5599ce93b5d2d02652e4',
    dynamic_role_gate='605a824a6b3fa0ec039947b33e263396448814c50daf38d1384ee83cf7176212',
    formal_full_used_domain='cd980946aa14ad3105372c65a1d76a04a1ba1cca6be5b93d376b4a173b839dee',
    paid_layout_adopt='62f93eb3196e25478548c9c19944610cdb32917ffe736d9f9e058c56f98cdd7c')
CONTROL='count14-normal-cold-whole-graph-control-CANDIDATE-v1'
HANDOFF='count14-normal-cold-whole-graph-handoff-CANDIDATE-v1'
OUTPUT='normal-cold-candidate-control-v1'
GAPS=('TRUSTED_PRODUCER_IDENTITY_IS_NOT_GLOBAL_CUT_OR_TERM_AUTHORITY',
      'SDK_AND_OPAQUE_NATIVE_SESSION_RESTORE_NOT_SEALED',
      'RAW_SID_AND_PROTECTED_FULL_USED_VALUES_NOT_RECONSTRUCTED_BY_THIS_PRODUCER',
      'HTTP_UNSENT_BUDGET_WAITERS_AND_TRANSPORT_NOT_RETIRED',
      'NATIVE_PEERS_CONTROL_INGRESS_AND_SYSTEM_SERVICES_RETAINED',
      'PAID_FINAL_ALL_EFFECTIVE_CUSTODY_NOT_RETIRED',
      'PRODUCTION_RESTORE_FULL_GRAPH_NOT_READY')


class CandidateWait(RuntimeError):pass
class ObservationNotStable(CandidateWait):pass


def need(ok,code):
    if not ok:raise CandidateWait(code)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
        ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def verify_sources():
    for name,pin in PINS.items():
        p=Path(importlib.import_module(name).__file__)
        need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and
             hashlib.sha256(p.read_bytes()).hexdigest()==pin,'NORMAL_SEALER_EXACT_FIXED_SOURCE_PINS')
    return dict(PINS)


@contextmanager
def short_lock(lock):
    need(lock.acquire(timeout=.2),'NORMAL_SEALER_CONTROL_LOCK_FINITE_TIMEOUT')
    try:yield
    finally:lock.release()


def identity(path):
    p=Path(path);s=p.lstat()
    need(p.is_absolute()and p.resolve()==p and not p.is_symlink(),'NORMAL_SEALER_CANONICAL_CONTROL_IDENTITY')
    return dict(path=str(p),device=s.st_dev,inode=s.st_ino,uid=s.st_uid,gid=s.st_gid,mode=stat.S_IMODE(s.st_mode))


def financial_controls(core,approved):
    """Fixed control COUNT/SUM only: no SELECT *, event metadata, job/result body."""
    l=core.ledger;q=core.queue
    with short_lock(l.mutex):
        fronts={t:dict(l.frontier(t))for t in sorted(core.rows)}
        requests=[list(r)for r in l.db.execute('SELECT state,COUNT(*),COALESCE(SUM(upper_bound),0),'
            'COALESCE(SUM(input),0),COALESCE(SUM(output),0) FROM requests GROUP BY state ORDER BY state')]
        operations=[list(r)for r in l.db.execute('SELECT kind,state,COUNT(*) FROM operations GROUP BY kind,state ORDER BY kind,state')]
        aux=[list(r)for r in l.db.execute('SELECT state,COUNT(*) FROM aux_permits GROUP BY state ORDER BY state')]
        unknown=list(l.db.execute('SELECT COUNT(*),COALESCE(SUM(upper_bound),0) FROM unknown_charges').fetchone())
        roles=dict(epoch=core.roles.epoch,
            births=[dict(trajectory=t,role=r,birth_sha256=b)for(t,r),b in sorted(core.roles.births.items())],
            held=[list(x)for x in sorted(core.roles.held)])
    with short_lock(q.mutex):
        need(approved.q is q,'NORMAL_SEALER_SAME_CURRENT_APPROVED_QUEUE')
        approved._known_job_tables_locked() # original fixed schema guard, no rows/body
        tables={r[0]for r in q.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        names=('jobs','replacement_jobs','formal_final_control_jobs_v1')
        final={name:dict(present=name in tables,state_counts=([list(r)for r in q.db.execute(
            'SELECT state,COUNT(*) FROM "'+name+'" GROUP BY state ORDER BY state')]if name in tables else None))for name in names}
    return dict(frontiers=fronts,requests_state_COUNT_upper_input_output_SUM=requests,
        operations_kind_state_COUNT=operations,aux_state_COUNT=aux,unknown_COUNT_upper_SUM=unknown,
        registered_role_controls=roles,FINAL_all_known_tables_state_COUNT=final,
        FINAL_effective_terminal_or_retirement_qualified=False)


def journal_controls(core):
    from anonymous_roster_journal import AnonymousRosterJournal,snapshot
    result={}
    need(set(core.journals)==set(core.rows),'NORMAL_SEALER_EXACT_SIX_ORIGINAL_JOURNALS')
    for t,journal in sorted(core.journals.items()):
        need(type(journal)is AnonymousRosterJournal and not journal.qualification_only and
             journal.path==Path(core.rows[t]['root'])/'metadata/DYNTEAM_ROSTER_PUBLIC_METADATA.sqlite',
             'NORMAL_SEALER_ORIGINAL_REGISTERED_ANONYMOUS_JOURNAL')
        state=snapshot(journal.projection) # original anonymous controls only, not SDK/science
        row=journal.db.execute('SELECT id,state_sha256 FROM roster_batches ORDER BY id DESC LIMIT 1').fetchone()
        if row is not None:
            if digest(state)!=row[1]:raise ObservationNotStable('NORMAL_SEALER_ANONYMOUS_DURABILITY_CHANGED')
        else:
            need(state['sequence']==0 and not state['live'] and not state['seen'],
                 'NORMAL_SEALER_INITIAL_ANONYMOUS_PROJECTION_NOT_UNPROVEN_HISTORY')
        result[t]=dict(identity=identity(journal.path),anonymous_projection=state,
            latest_id=None if row is None else row[0],latest_state_sha256=None if row is None else row[1],
            initial_empty_projection_verified=row is None)
    return result


def capture_registered_metadata(sealer):
    """Only exact registered owner graph, never a caller callback/capture path."""
    sealer._current();core=sealer.core;b=sealer.barrier
    controls=financial_controls(core,b.approved)
    cuts={}
    for t,(cp,_,_)in sorted(b.checkpoints.items()):
        need(cp.reference==cp.writer.reference and cp.state in ('COMMITTED','POINT_QUEUED','FINAL_PARKED'),
             'NORMAL_SEALER_SAME_ALREADY_COMMITTED_NATIVE_REFERENCE')
        physical=core.servers[t].trajectory_park_ready(t)
        # Existing refs/pins ONLY. No CAS.resolve/verify, serializer, backup,
        # SDK load, native_control read, archive or state hash is added here.
        cuts[t]=dict(checkpoint_phase=cp.state,snapshot_reference=copy.deepcopy(cp.reference),
            original_cut_sha256=cp.writer.cut.cut_sha,membership_token_sha256=digest(cp.writer.membership_token),
            safe_to_park_writers=physical['safe_to_park_writers'],
            original_budget_waiters=physical['original_budget_waiters'],
            HTTP_lifecycle_storage_unknown=core.servers[t].lifecycle_storage_unknown)
        need(controls['frontiers'][t]['state']=='COMMITTED_PARKED'and
             controls['frontiers'][t]['reserved']==controls['frontiers'][t]['unresolved']==
             controls['frontiers'][t]['active_operations']==0,
             'NORMAL_SEALER_ALL_SIX_ORIGINAL_COMMITTED_DRAINED_FRONTIERS')
    need(set(cuts)==set(core.rows),'NORMAL_SEALER_ALL_SIX_FROZEN_REFERENCES')
    with short_lock(core.peers._lock):
        peers=[dict(trajectory=t,role=r,purpose=p,birth=asdict(v))for(t,r,p),v in sorted(core.peers._peers.items())]
    with short_lock(core.inbox.lock):
        inbox=dict(pending=len(core.inbox.pending),unresolved=core.inbox.unresolved,
                   registered_tickets=len(core.inbox.tickets)) # no envelopes/payload/SID read
    with short_lock(core.ledger.mutex):
        waiters=len(core.gate.waiters)
    native=core.control
    sdk=core.native_sdk_startup_epochs
    result=dict(cuts=cuts,financial=controls,anonymous_journals=journal_controls(core),
        original_storage_identities=dict(owner_home=identity(core.home),ledger_home=identity(core.ledger.home),
            ledger_database=identity(core.ledger.home/'ledger.sqlite'),queue_home=identity(core.queue.home),
            queue_database=identity(core.queue.home/'queue.sqlite'),CAS_home=identity(core.cas.home)),
        fullused_public_tip=copy.deepcopy(sealer.domain.public()),native_peer_birth_controls=peers,
        native_affinity_inbox_counts=inbox,original_gate_waiter_count=waiters,
        native_control_thread_alive=native.thread.is_alive(),native_control_socket_open=native.server.socket.fileno()!=-1,
        native_SDK_registered_epoch_count=len(sdk.current),native_SDK_retirement_qualified=False,
        HTTP_transport_retirement_qualified=False,native_peer_retirement_qualified=False,
        paid_FINAL_retirement_qualified=False,SYSTEM_services_retired=False)
    need(result['fullused_public_tip']['pending'] is False and
         result['fullused_public_tip']['failure_code'] is None,'NORMAL_SEALER_ORIGINAL_FULLUSED_PENDING_OR_FAILED_WAIT')
    return result


def save_candidate(path,value):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb')as out:out.write(raw);out.flush();os.fsync(out.fileno())
    fd=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
    return dict(identity=identity(path),sha256=hashlib.sha256(raw).hexdigest())


class NormalColdCandidateSealer:
    def __init__(self,owner):
        from normal_cold_barrier import NormalCheckpointBarrier
        from native_cold_owner import NativeColdOwner
        from native_formal_cohort import NativeFormalCohort
        from original_relay_core import OriginalRelayCore
        from native_layout import NativeLayout
        from native_metadata_publisher import NativeMetadataPublisher
        from dynamic_role_gate import DynamicRoleGate
        from formal_full_used_domain import FullUsedDomainProducer
        from formal_scope import validate_contract
        verify_sources()
        need(type(owner)is NativeColdOwner and type(owner.core)is OriginalRelayCore and
             type(owner.scientific_smoke)is NativeFormalCohort and
             type(owner.normal_cold_barrier)is NormalCheckpointBarrier,
             'NORMAL_SEALER_EXACT_ORIGINAL_OWNER_CORE_COHORT_BARRIER')
        b=owner.normal_cold_barrier;b._current();core=owner.core
        validate_contract(core.contract,digest(core.contract))
        need(not core.qualification_only and len(core.rows)==6 and core.contract['mode']=='production'and
             not b.requested and not b.cohort.activation_attempted and
             type(owner.layout)is NativeLayout and owner.layout is core.native_layout and
             type(core.publisher)is NativeMetadataPublisher and core.publisher.sessions is core.sessions and
             core.publisher.journals==core.journals and b.domain.sessions is core.sessions and
             type(b.domain)is FullUsedDomainProducer and type(core.roles)is DynamicRoleGate and
             core.roles.ledger is core.ledger and core.gate._dynteam_role_control is core.roles and
             core.home==Path(core.contract['arms'][0]['root'])/'owner'and
             core.home.resolve()==core.home and core.home.is_relative_to((_C14_SCRATCH))and
             not hasattr(core,'normal_cold_sealer'),
             'NORMAL_SEALER_FIRST_REGISTERED_COLD_SIX_NO_OWN_OR_RETAINED_PAID_INSTALL')
        self.owner,self.core,self.cohort,self.barrier=owner,core,b.cohort,b
        self.domain,self.birth,self.pid,self.thread=b.domain,b.birth,b.pid,b.thread
        self.source_binding=digest(core.contract)
        self.home,self.home_identity=core.home,identity(core.home)
        self.state='COLD_INSTALLED_NOT_REQUESTED';self.requested=False;self.sequence=0
        self.control_reference=self.handoff_reference=None;self.publication_started=False
        self.failure=None;self.observation_attempts=0;self.producer_registered_graph_verified=True

    def _current(self):
        self.barrier._current()
        need(os.getpid()==self.pid and threading.get_ident()==self.thread and
             self.owner.normal_cold_sealer is self.core.normal_cold_sealer is self.cohort.normal_cold_sealer is self and
             self.owner.core is self.core and self.core.formal_full_used_domain is self.domain and
             self.core.home==self.home==Path(self.core.contract['arms'][0]['root'])/'owner'and
             identity(self.core.home)==self.home_identity and
             self.source_binding==digest(self.core.contract)and not self.core.ledger.mutex._is_owned(),
             'NORMAL_SEALER_SAME_REGISTERED_OWNER_METADATA_THREAD_OUTSIDE_SCIENCE_LOCK')

    def request(self):
        self._current()
        if not self.requested:
            self.barrier.request_barrier()
            self.requested=True;self.state='REQUESTED_WAIT_ORIGINAL_SIX_NORMAL_CUTS'
        return self.public()

    def poll_once(self):
        self._current()
        if not self.requested or self.publication_started or self.failure is not None:return self.public()
        self.barrier.poll()
        if self.barrier.failure is not None:
            self.state='ORIGINAL_BARRIER_PARTIAL_RETAINED_NO_RETRY';return self.public()
        if not self.barrier.last_static_observation:return self.public()
        self.observation_attempts+=1;deadline=time.monotonic()+25
        try:
            before=capture_registered_metadata(self)
            from paid_layout_adopt import capture_layout_section
            epoch=getattr(self.domain,'_paid_writer_epoch',1)
            layout=capture_layout_section(self.owner.layout,old_epoch=epoch,new_epoch=epoch+1)
            after=capture_registered_metadata(self)
            if before!=after or time.monotonic()>deadline:
                self.state='NOT_STABLE_RETRY_OBSERVATION';return self.public()
            self._current()
            authority=dict(fixed_source_registered_owner_graph_verified=self.producer_registered_graph_verified,
                original_owner_birth=asdict(self.birth),metadata_owner_thread=self.thread,
                source_pins=verify_sources(),contract_sha256=self.source_binding,
                whole_cohort_cut_qualified=False,normal_handoff_authoritative=False,safe_to_TERM=False,
                whole_paid_restore_qualified=False,actual_cold_ready=False)
            self.sequence+=1
            control=dict(schema=CONTROL,sequence=self.sequence,authority=authority,
                observed_six_normal_frozen_cuts=True,metadata_stable_before_publication=True,
                metadata_capture=before,native_layout_adoption=layout,
                raw_SID_or_SDK_state_exported=False,per_track_fullused_capabilities_not_upgraded=True,
                remaining_custody_and_gaps=list(GAPS),candidate_notready=True)
            root=self.core.home/OUTPUT
            root.mkdir(mode=0o700,parents=False,exist_ok=False)
            self.publication_started=True # failure/partial from this point is never recaptured
            self.state='CANDIDATE_PARTIAL_RETAINED_NO_RETRY'
            self.control_reference=save_candidate(root/('CONTROL_'+str(self.sequence).zfill(12)+'.json'),control)
            post=capture_registered_metadata(self)
            if post!=after:
                self.state='NOT_STABLE_AFTER_CONTROL_PARTIAL_RETAINED_NO_RETRY';return self.public()
            handoff=dict(schema=HANDOFF,sequence=self.sequence,authority=authority,
                control_reference=self.control_reference,original_owner_home=identity(self.core.home),
                captured_scope=sorted(self.core.rows),metadata_stable_after_CONTROL=True,
                remaining_custody_and_gaps=list(GAPS),candidate_notready=True,
                original_owner_still_retained=True,old_owner_exit_or_TERM_authorized=False,
                activation_or_restore_authorized=False)
            self.handoff_reference=save_candidate(root/('HANDOFF_'+str(self.sequence).zfill(12)+'.json'),handoff)
            self.state='NORMAL_SOURCE_CANDIDATE_WRITTEN_NOT_READY'
        except ObservationNotStable:
            self.state=('CANDIDATE_PARTIAL_RETAINED_NO_RETRY'if self.publication_started else'NOT_STABLE_RETRY_OBSERVATION')
        except Exception as error:
            frames=[];tb=error.__traceback__
            while tb:frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,
                function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
            self.failure=dict(PUBLIC_code='NORMAL_SEALER_METADATA_OBSERVATION_REFUSED',
                exception_type=type(error).__name__,locations=frames)
            self.state=('CANDIDATE_PARTIAL_RETAINED_NO_RETRY'if self.publication_started else'METADATA_OBSERVATION_UNAVAILABLE')
        return self.public()

    def public(self):
        # No raw SID, per-role birth hash, journal, request, candidate/result body.
        return dict(schema='count14-normal-cold-candidate-producer-PUBLIC-v1',state=self.state,
            requested=self.requested,observation_attempts=self.observation_attempts,
            control_sha256=None if self.control_reference is None else self.control_reference['sha256'],
            handoff_sha256=None if self.handoff_reference is None else self.handoff_reference['sha256'],
            candidate_written=self.handoff_reference is not None,candidate_notready=True,
            source_registered_graph_verified=self.producer_registered_graph_verified,
            whole_cohort_cut_qualified=False,normal_handoff_authoritative=False,safe_to_TERM=False,
            whole_paid_restore_qualified=False,actual_cold_ready=False,models_replayed=0,
            science_fault_or_close_called=False,failure=copy.deepcopy(self.failure))
