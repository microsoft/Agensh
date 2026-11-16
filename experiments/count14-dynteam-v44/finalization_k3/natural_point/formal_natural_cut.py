"""Exact existing-Ledger insertion, no old Driver facade/new control tables.

Producer admission requires actual framework sampler evidence; this WIP does
not fabricate a sampler/owner or grant runtime installation. Original capture,
collector, K3 and same-live thaw are always delegated, never prefix-replayed.
"""
from dataclasses import dataclass,asdict
from types import MethodType
import copy
import json
from common import need,wire,digest,strict,sha
from formal_scope import FORMAL_CUTS,PUBLIC_CONTRACT_CANONICAL_SHA256
from formal_natural_abi import metadata,POLICY_SHA,KIND

FIRST='DYNTEAM_FORMAL_FIRST_NATURAL_POINT_REQUESTED'
SEALED='DYNTEAM_FORMAL_FIRST_NATURAL_SNAPSHOT_AND_K3_QUEUED'
RELEASED='DYNTEAM_FORMAL_FIRST_NATURAL_ORIGINAL_RELEASE_CONFIRMED'


@dataclass(frozen=True)
class NativeTeamIdleSample:
    trajectory:str
    activity_sha256:str
    source_sha256:str
    active_idle_seconds:int
    pending:int
    sending:int
    retrying:int
    live_workers:int
    exact_live_roles:tuple
    physical_http_clear:bool
    pending_native_effects:int
    native_sampler_terminal:bool

    def validate(self,t):
        need(self.trajectory==t and type(self.active_idle_seconds)is int and self.active_idle_seconds>=600 and
             type(self.live_workers)is int and self.live_workers>0 and
             type(self.exact_live_roles)is tuple and len(set(self.exact_live_roles))==len(self.exact_live_roles) and
             self.live_workers==len(self.exact_live_roles), 'FORMAL_NATURAL_REAL_NONEMPTY_NATIVE_IDLE_600_ACTIVE')
        for value in (self.pending,self.sending,self.retrying,self.pending_native_effects):
            need(type(value)is int and value==0,'FORMAL_NATURAL_NATIVE_PENDING_OR_UNKNOWN_MUST_NOT_BE_ZEROED')
        need(self.physical_http_clear is True and self.native_sampler_terminal is True,
             'FORMAL_NATURAL_ACTUAL_NATIVE_AND_HTTP_PHYSICAL_DRAIN')
        sha(self.activity_sha256);sha(self.source_sha256)
        return True


def first_record(ledger,t):
    """One fixed PUBLIC event only; no request or response body queries."""
    with ledger.mutex:
        rows=ledger.db.execute('SELECT metadata FROM events WHERE trajectory=? AND kind=? ORDER BY seq',(t,FIRST)).fetchall()
        need(len(rows)<=1,'FORMAL_NATURAL_EXACT_ONE_DURABLE_FIRST_EVENT')
        return None if not rows else strict(rows[0][0])


def insert_first_cut(ledger,t,sample):
    """Existing normal SQL actions only, one transaction and no RAM first marker.

    This primitive is separately OWN-tested with the exact original Ledger.
    Actual production entry is request_first(), never an untrusted dataclass.
    """
    from budget import Ledger
    need(type(ledger)is Ledger and type(sample)is NativeTeamIdleSample,
         'FORMAL_NATURAL_TYPED_ORIGINAL_LEDGER_AND_NATIVE_SAMPLE')
    sample.validate(t)
    with ledger.tx():
        if first_record(ledger,t) is not None:return False
        f=ledger.frontier(t);account=ledger.account(t)
        if f['state']!='RUNNING' or f['unresolved'] or f['reserved'] or f['active_operations'] or ledger.admission_fault(t):return False
        targets=json.loads(account['targets']);stage=f['stage']
        need(targets==list(FORMAL_CUTS),'FORMAL_NATURAL_KEEP_ALL_ORIGINAL_REGISTERED_REGULAR_CUTS')
        need(f['actual']<=targets[stage] and f['actual']<FORMAL_CUTS[-1],
             'FORMAL_NATURAL_EXACT_ACTUAL_WITHIN_CURRENT_REGULAR_AND_TOTAL_BUDGET')
        meta=metadata(t,f['generation'],f['actual']);updated=list(targets);updated.insert(stage,f['actual'])
        request=dict(natural_stop=meta,original_stage=stage,original_regular_targets=targets,
            targets_with_natural_cut=updated,native_idle_sample=asdict(sample),
            measured_search_tokens=f['measured_actual'],actual_budget_tokens=f['actual'],
            unknown_reservation_charge=f['unknown_reservation_charge'],effective_reservations=f['reserved'],
            contract_sha256=PUBLIC_CONTRACT_CANONICAL_SHA256,policy_sha256=POLICY_SHA)
        # Same normal targets/state UPDATE as original NaturalStopManager.
        # No stage/generation/actual/request/charge/unknown row changes.
        ledger.db.execute("UPDATE accounts SET targets=?,state='DRAINING' WHERE trajectory=?",(wire(updated).decode(),t))
        ledger.event(t,'ADMISSION_CLOSED',{'reason':'NATURAL_STOP','generation':f['generation'],'policy_sha256':POLICY_SHA})
        ledger.event(t,FIRST,request)
    return True


class FormalFirstNaturalPoint:
    """Typed live graph adapter; no constructor or scientific action at import.

    Cold installer composes the exact sampler/current FINAL child and typed
    terminal source; actual SDK/capture/provider qualification remains separate.
    """
    def __init__(self,cohort,*,sampler):
        from native_formal_cohort import NativeFormalCohort
        from original_relay_core import OriginalRelayCore
        need(type(cohort)is NativeFormalCohort and type(cohort.core)is OriginalRelayCore and
             not cohort.activation_attempted and set(cohort.core.gate.startup_held)==set(cohort.tracks),
             'FORMAL_NATURAL_NEW_EXACT_ORIGINAL_COHORT_COLD_ONLY')
        from formal_natural_sampler import NativeTeamIdleSampler
        from formal_natural_terminal import NaturalCompositeTerminalSource
        from native_peer_registry import process_birth
        import os
        need(type(sampler)is NativeTeamIdleSampler and sampler.cohort is cohort and sampler.core is cohort.core and
             type(getattr(cohort,'formal_natural_terminal_source',None))is NaturalCompositeTerminalSource and
             not hasattr(cohort,'formal_first_natural_point') and cohort.final is None,
             'FORMAL_NATURAL_SAME_EXACT_SAMPLER_TERMINAL_SOURCE_BEFORE_FIRST_PREPARE')
        self.cohort,self.core,self.sampler=cohort,cohort.core,sampler
        self.birth=process_birth(os.getpid());self.bound=set()
        cohort.formal_first_natural_point=self
        original=cohort.poll
        def poll(own):
            value=original()
            self.poll()
            return value
        cohort.poll=MethodType(poll,cohort)

    def outside(self):
        from native_peer_registry import process_birth
        import os
        need(process_birth(os.getpid())==self.birth and not self.core.ledger.mutex._is_owned(),
             'FORMAL_NATURAL_SAME_OWNER_NO_IO_OR_WAITS_UNDER_SCIENCE_LOCK')

    def request_first(self,t,sample):
        from native_dynamic_checkpoint import DynamicCheckpointPorts
        from native_formal_cohort import RUNNING
        self.outside()
        cp=self.cohort.tracks[t]['checkpoint'];core=self.core
        need(type(cp)is DynamicCheckpointPorts and cp is core.formal_checkpoint_ports[t] and
             cp.core is core and cp.ledger is core.ledger and type(sample)is NativeTeamIdleSample and
             self.sampler.accepts_current_sample(sample,t) is True,
             'FORMAL_NATURAL_ONLY_ORIGINAL_CHECKPOINT_AND_PINNED_CURRENT_SAMPLER')
        sample.validate(t)
        if cp.state!='RUNNING' or self.cohort.tracks[t]['state']!=RUNNING:return False
        with core.ledger.mutex:
            live=tuple(sorted(role for (trajectory,role) in core.roles.births if trajectory==t and role.startswith('worker-')))
            need(live==tuple(sorted(sample.exact_live_roles)), 'FORMAL_NATURAL_FRESH_EXACT_LIVE_ROLE_ENUMERATION')
        http=core.servers[t]
        if not http.trajectory_park_ready(t)['safe_to_park_writers'] or http.lifecycle_storage_unknown:return False
        if core.membership_fences[t].public_counts()['pending_native_effects']:return False
        # All potentially blocking sampler/kernel work occurred before tx.
        accepted=insert_first_cut(core.ledger,t,sample)
        if accepted:
            record=first_record(core.ledger,t)
            cp.pins={**cp.pins,'natural_stop_policy':POLICY_SHA,'natural_stop_point':digest(record['natural_stop'])}
            core.gate.notify()
        return accepted

    def poll(self):
        self.outside()
        if self.core.closed:return
        for t,track in self.cohort.tracks.items():
            try:
                cp=track['checkpoint']
                if cp is not None and t not in self.bound:
                    self.bind_checkpoint(t);self.bound.add(t)
                if not self.cohort.activation_attempted or not track['gate_released'] or track['failure']is not None:continue
                if first_record(self.core.ledger,t)is not None:continue
                sample=self.sampler.sample(t)
                if sample is not None:self.request_first(t,sample)
            except Exception as error:self.cohort._partial(t,error,'FORMAL_FIRST_NATURAL_SAME_OWNER_POLL')

    def bind_checkpoint(self,t):
        from native_dynamic_checkpoint import DynamicCheckpointPorts
        cp=self.cohort.tracks[t]['checkpoint']
        need(type(cp)is DynamicCheckpointPorts and cp.core is self.core and cp.state=='BOUND_MODELS_HELD',
             'FORMAL_NATURAL_BIND_ORIGINAL_CHECKPOINT_BEFORE_ACTIVATION')
        original=cp.step
        def step(bound):
            value=original() # exact original freeze/backup/capture/collect/K3/resume
            self.after_original_step(t,cp)
            return value
        cp.step=MethodType(step,cp)

    def after_original_step(self,t,cp):
        """Append-only observations AFTER real original evidence, never rewrite it."""
        self.outside();record=first_record(self.core.ledger,t)
        if record is None:return
        meta=record['natural_stop'];points=[p for p in cp.points if p['generation']==meta['generation']]
        need(len(points)<=1,'FORMAL_NATURAL_ONE_ORIGINAL_GENERATION_POINT')
        if not points:return
        point=points[0]
        need(point['target_tokens']==meta['actual_tokens'] and len(point['jobs'])==len(set(point['jobs']))==3,
             'FORMAL_NATURAL_ORIGINAL_EXACT_ACTUAL_AND_K3')
        with self.core.ledger.mutex:
            sealed=self.core.ledger.db.execute('SELECT COUNT(*) FROM events WHERE trajectory=? AND kind=?',(t,SEALED)).fetchone()[0]
            released=self.core.ledger.db.execute('SELECT COUNT(*) FROM events WHERE trajectory=? AND kind=?',(t,RELEASED)).fetchone()[0]
        need(sealed<=1 and released<=1,'FORMAL_NATURAL_SINGLE_OBSERVATION_EVENTS')
        if not sealed:
            expected=dict(self.core.ledger.frontier(t));expected.update(generation=meta['generation'],target=meta['actual_tokens'],actual=meta['actual_tokens'],shortfall=0)
            snap=self.core.cas.verify_snapshot(point['snapshot'],expected=expected)
            need(snap['pins']['natural_stop_point']==digest(meta) and snap['pins']['natural_stop_policy']==POLICY_SHA,
                 'FORMAL_NATURAL_ACTUAL_ORIGINAL_COMMITTED_SNAPSHOT')
            with self.core.ledger.tx():self.core.ledger.event(t,SEALED,dict(natural_stop=meta,snapshot=point['snapshot'],jobs=point['jobs']))
        f=self.core.ledger.frontier(t)
        if not released and cp.state=='RUNNING' and f['generation']>meta['generation']:
            need(cp.writer is None,'FORMAL_NATURAL_RELEASE_ONLY_AFTER_ORIGINAL_SAME_LIVE_THAW')
            with self.core.ledger.tx():self.core.ledger.event(t,RELEASED,dict(natural_stop=meta,current_generation=f['generation']))
            cp.pins={k:v for k,v in cp.pins.items() if k not in ('natural_stop_policy','natural_stop_point')}
            # This opens only the original watchdog admission after real seal
            # + enqueue + original thaw, never performs neutral/POST itself.
            self.sampler.allow_original_neutral_after_release(t,meta,point['snapshot'])
