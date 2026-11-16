"""Same-owner formal n3/n<3 producer -> accepted -> verified mixed evidence.

No new scientific request/audit/metrics/fee/table. Original n3 path stays n3;
n<3 uses only authenticated original per-replicate PUBLIC results after natural
termination and original policy exhaustion. Scientific acceptance != physical
UNKNOWN terminal. All file I/O is outside scientific locks.
"""
from dataclasses import dataclass,asdict
from pathlib import Path
from types import SimpleNamespace
import copy,os,re,time
from common import need,digest,sha,strict,hash_file,publish,wire,private_dir
from formal_scope import FORMAL_CUTS
from formal_terminal_source import FormalPointTerminalSource
from native_peer_registry import process_birth
from allowance_original import load_kernels
import final_attempts
from formal_nlt3_rules import load_public_rules,select_terminal,bind_committed_metadata,original_statistics,WaitForEvidence,METRICS

SCHEMA='count14-formal100m-terminal-nlt3-public-v1'
PREPARED='FORMAL_TERMINAL_NLT3_PREPARED_PUBLIC.json'
AUDIT='FORMAL_TERMINAL_NLT3_AUDIT_PUBLIC.json'
ACCEPTED='FORMAL_TERMINAL_NLT3_ACCEPTED_PUBLIC.json'


@dataclass(frozen=True)
class FormalMixedPointEvidence:
    contract_sha256:str
    original_owner_birth_sha256:str
    basis_sha256:str
    points:tuple
    def public(self):
        return dict(schema='count14-formal100m-mixed-verified-point-terminals-public-v1',
            contract_sha256=self.contract_sha256,original_owner_birth_sha256=self.original_owner_birth_sha256,
            basis_sha256=self.basis_sha256,terminal_points=len(self.points),effective_n=[p[3]for p in self.points],
            score_computable=[p[3]>0 for p in self.points],original_n3_only=all(p[3]==3 for p in self.points),
            nlt3_producer_implemented=True,n0_is_terminal_not_computable=True,
            fixed_sum72_success_requirement=False,physical_unknown_slot_release_claimed=False)


class FormalTypedQueueRows:
    def __init__(self,core,provider=None):
        from original_relay_core import OriginalRelayCore
        from final_queue import FinalQueue
        need(type(core)is OriginalRelayCore and type(core.queue)is FinalQueue,'FORMAL_NLT3_EXACT_ORIGINAL_ROW_CORE')
        self.core,self.q,self.provider=core,core.queue,provider
        if provider is not None:
            from queue_control import CarrierQueueDomain
            from allowance_control import FormalAllowanceControl
            need(type(provider)in(CarrierQueueDomain,FormalAllowanceControl),'FORMAL_NLT3_TYPED_ROW_PROVIDER_ONLY')
            if type(provider)is CarrierQueueDomain:
                need(provider.q is self.q and provider.control is not None and provider.control.core is core and
                    provider.offline_OWN is False,'FORMAL_NLT3_SAME_PRODUCTION_PRIVATE_ROW_DOMAIN')
            else:need(provider.core is core,'FORMAL_NLT3_SAME_HOST_CONTROL_ROW_SOURCE')
    def _no_unregistered_tables(self):
        required={'id','point','replicate','state','claim','child','terminal','result'}
        for r in self.q.db.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            name=r[0];need(re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',name)is not None,'FORMAL_NLT3_SAFE_TABLE_IDENTIFIER')
            cols={v[1]for v in self.q.db.execute('PRAGMA table_info("'+name+'")')}
            if required<=cols and name not in('jobs','replacement_jobs'):
                raise WaitForEvidence('UNREGISTERED_EXTRA_NATIVE_ROW_DOMAIN')
    def all_rows(self,q):
        need(q is self.q,'FORMAL_NLT3_ONE_SAME_QUEUE')
        if self.provider is not None:return self.provider.all_rows(q)
        self._no_unregistered_tables();return final_attempts.all_rows(q)
    def effective_rows(self,q):
        need(q is self.q,'FORMAL_NLT3_ONE_SAME_QUEUE')
        if self.provider is not None:return self.provider.effective_rows(q)
        self._no_unregistered_tables();return final_attempts.effective_rows(q)


class FormalActualNTerminalSource(FormalPointTerminalSource):
    def __init__(self,cohort,*,original_kernel_paths,sidecar_public_code,rows_provider=None):
        super().__init__(cohort)
        self.kernels=load_kernels(original_kernel_paths)
        self.rules=load_public_rules(sidecar_public_code,self.kernels)
        self.rows=FormalTypedQueueRows(self.core,rows_provider);self.provider=rows_provider
        self.partial={};self.point_failures={};self._issued=None
        self.producer_sha256=digest(source_pins())
    def _current(self):
        need(self.cohort.core is self.core and self.birth==process_birth(os.getpid())and
            digest(self.core.contract)==self.contract_sha256 and digest(self.core.rows)==self.rows_sha256,
            'FORMAL_NLT3_SAME_CURRENT_OWNER_CONTRACT')
        need(not self.core.ledger.mutex._is_owned()and not self.core.queue.mutex._is_owned(),
            'FORMAL_NLT3_NO_FILES_UNDER_SCIENCE_LOCKS')
        final=self.cohort.final
        if final is None or final.state!='RELEASED':raise WaitForEvidence('SHARED_FINAL_NOT_RELEASED')
        from formal_controller import FormalFinalController
        need(type(final)is FormalFinalController and final.core is self.core and
            final.dispatcher.ledger is self.core.ledger and final.dispatcher.queue is self.core.queue,
            'FORMAL_NLT3_SAME_ORIGINAL_SHARED_FINAL')
        return final
    def _dispatcher_record(self,point):
        d=self.cohort.final.dispatcher
        if not d.lock.acquire(timeout=.25):raise WaitForEvidence('ORIGINAL_DISPATCHER_METADATA_BUSY')
        try:
            p=d.points.get(point)
            return None if p is None else dict(aux=Path(p['aux']),jobs=tuple(p['jobs']),audited=p['audited'])
        finally:d.lock.release()
    def _queue_point(self,point):
        q=self.core.queue
        if not q.mutex.acquire(timeout=.25):raise WaitForEvidence('ORIGINAL_QUEUE_BUSY')
        try:
            r=q.db.execute('SELECT *FROM points WHERE point=?',(point,)).fetchone()
            if r is None:raise WaitForEvidence('ORIGINAL_POINT_NOT_QUEUED')
            allrows=copy.deepcopy(self.rows.all_rows(q));rows=[r for r in allrows if r['point']==point]
            partials={r['job_id']:strict(r['metadata'])for r in q.db.execute('SELECT job_id,metadata FROM replicate_partials')if r['job_id']in {j['id']for j in rows}}
            events=[strict(r[0])for r in q.db.execute("SELECT metadata FROM events WHERE kind='CHILD_TERMINAL'")]
            waits={j['id']:sum(e==dict(job_id=j['id'],**strict(j['terminal']))for e in events)==1 if j['terminal']else False for j in rows}
            completions=[strict(r[0])for r in q.db.execute("SELECT metadata FROM events WHERE kind='COMPLETE'")]
            grants={}
            # Only exact registered private-domain authorizations can convey
            # last-extra status; never infer a grant from raw ordinal4.
            if self.provider is not None and hasattr(self.provider,'attempts'):
                from queue_control import AUTH
                for j in rows:
                    a=q.db.execute('SELECT metadata,sha256 FROM '+AUTH+' WHERE id=?',(j['id'],)).fetchone()
                    if a is not None:
                        v=strict(a[0]);need(digest(v)==a[1],'FORMAL_NLT3_AUTHORIZATION_NOT_CHANGED')
                        if v['last_extra']:grants[j['id']]=v['last_extra_grant_sha256']
            row=dict(r)
        finally:q.mutex.release()
        exemptions={}
        host=getattr(self.core,'formal_allowance_control',None)
        for j in rows:
            if j['id']in partials:
                # EXACT original V4 financial proof reader, no fee writes.
                with self.core.ledger.mutex:
                    allocation=self.core.ledger.db.execute('SELECT metadata FROM aux_attempt_allocations WHERE job_id=?',(j['id'],)).fetchone()
                if allocation is None:raise WaitForEvidence('ORIGINAL_SYSTEM_ALLOCATION_NOT_READY')
                try:self.rules.financial_disposition(SimpleNamespace(driver=SimpleNamespace(ledger=self.core.ledger)),j,partials[j['id']])
                except (KeyError,TypeError):raise WaitForEvidence('ORIGINAL_FINANCIAL_DISPOSITION_MISSING')
                if host is not None:
                    x=host.home/(j['id']+'_EXEMPTION_PUBLIC.json')
                    if x.exists():
                        normalized={**j,'attempt':j.get('attempt',1)}
                        with self.core.ledger.mutex:
                            a=self.core.ledger.db.execute('SELECT metadata FROM aux_attempt_allocations WHERE job_id=?',(j['id'],)).fetchone()
                        if a is None:raise WaitForEvidence('ORIGINAL_ALLOCATION_MISSING')
                        # Reuse original full host reader, not supplied bools.
                        proof=self.kernels.failed_proof(q,normalized,partials[j['id']],strict(a[0]))
                        exemptions[j['id']]=host._exemption(normalized,proof,x)
        return row,dict(rows=rows,partials=partials,wait_events=waits,last_extra_grants=grants,
                        tool_exemptions=exemptions),completions
    def _binding(self,point,row,snapshot):
        from native_dynamic_checkpoint import DynamicCheckpointPorts
        t,cut=row['trajectory'],row['target'];cp=self.cohort.tracks[t]['checkpoint']
        if cp is None:raise WaitForEvidence('REAL_CHECKPOINT_PORT_NOT_READY')
        need(type(cp)is DynamicCheckpointPorts and cp.core is self.core and cp.t==t and
             self.core.formal_checkpoint_ports[t]is cp,'FORMAL_NLT3_EXACT_REAL_ORIGINAL_DYNAMIC_CHECKPOINT')
        entries=[copy.deepcopy(p)for p in cp.points if p['target_tokens']==cut]
        if not entries:raise WaitForEvidence('ORIGINAL_COMMITTED_POINT_MEMORY_NOT_READY')
        need(len(entries)==1,'FORMAL_NLT3_UNIQUE_ORIGINAL_CHECKPOINT_ENTRY');entry=entries[0]
        with self.core.ledger.mutex:
            committed=[tuple(r)for r in self.core.ledger.db.execute('SELECT trajectory,generation,target,ref_sha FROM snapshots WHERE trajectory=?AND generation=?',(t,entry['generation']))]
        expected_root=Path(self.core.rows[t]['root'])/'checkpoints'/('generation-'+str(entry['generation']))/'v21'
        need(Path(row['input_root'])==expected_root,'FORMAL_NLT3_ORIGINAL_DYNAMIC_INPUT_PATH')
        policy,pp=self._public_audit(expected_root/'input-policy.json');saved,sp=self._public_audit(expected_root/'snapshot/saved.json')
        need(policy['pins']['manifest']==self.contract_sha256 and
             policy['pins']['source']==self.core.contract['v2_baseline_reference_protocol']['source_bundle'],
             'FORMAL_NLT3_INPUT_CANONICAL_MANIFEST_SOURCE')
        initial=sorted((r for r in snapshot['rows']if r.get('attempt',1)==1),key=lambda j:j['replicate'])
        need([j['replicate']for j in initial]==[1,2,3],'FORMAL_NLT3_THREE_ORIGINAL_INITIAL_JOB_IDENTITIES')
        binding=bind_committed_metadata(trajectory=t,target=cut,point=point,row=row,checkpoint_entry=entry,
            committed_rows=committed,initial_jobs=[j['id']for j in initial],policy=policy,policy_pin=pp,saved=saved,saved_pin=sp)
        final=self.cohort.final;facade=final.facades[t]
        if point not in facade.points or facade.points[point]['ready']is not True:
            raise WaitForEvidence('ACTUAL_ORIGINAL_FACADE_POINT_NOT_READY')
        aux=Path(facade.points[point]['home'])
        need(aux.is_absolute()and aux.resolve()==aux and aux.is_relative_to(Path(self.core.rows[t]['root'])/'final/final-points'),
             'FORMAL_NLT3_ACTUAL_FACADE_AUX_NOT_RECONSTRUCTED')
        p=self._dispatcher_record(point)
        if p is None:raise WaitForEvidence('ORIGINAL_DISPATCHER_POINT_NOT_READY')
        need(Path(p['aux'])==aux,'FORMAL_NLT3_SAME_ACTUAL_DISPATCHER_FACADE_POINT')
        return binding,aux
    def _replicates(self,point,row,selection,aux):
        records=[];evidence=[];l=self.core.ledger
        protocol=self.cohort.final.scope.protocol_sha256(row['trajectory'])
        for j in selection['selected']:
            k,a=j['replicate'],j.get('attempt',1);base=aux if a==1 else aux/'replacement-attempts'/f'k{k}-a{a}'
            ap=base/'results'/row['setting']/(f"s{row['target']//1000000}m-k{k}")/'aggregate.json'
            cp=base/f'k{k}'/'physical-custody.json'
            if not ap.exists()or not cp.exists():raise WaitForEvidence('ORIGINAL_REPLICATE_PUBLIC_FILES_MISSING')
            agg,ah=self._public_audit(ap);cust,ch=self._public_audit(cp)
            need(agg['trajectory']==row['trajectory']and agg['setting']==row['setting']and agg['replicate_index']==k and
                 agg['nominal_budget']==row['target']and agg['input_policy_sha256']==row['input_policy']and
                 agg['source_sha256']==self.core.contract['v2_baseline_reference_protocol']['source_bundle']and
                 agg['protocol_sha256']==protocol and agg['complete']is True and agg['evaluation_complete']is True and
                 agg.get('unknown_requests')==0,'FORMAL_NLT3_ORIGINAL_VALID_REPLICATE_PUBLIC')
            need(cust['native_model_and_evaluator_scopes_terminal']is True and cust['unresolved']==0 and
                 cust['aggregate_sha256']==ah['sha256']and cust['trajectory']==row['trajectory']and
                 cust['replicate_index']==k and cust['target_tokens']==row['target']and
                 cust['input_policy_sha256']==row['input_policy']and cust['evaluator_custody']['physical_terminal']is True and
                 cust['evaluator_custody']['unresolved']==0,'FORMAL_NLT3_SUCCESS_PHYSICAL_CUSTODY')
            if a>1:need(agg['replicate_attempt']==cust['replicate_attempt']==a and agg['point_id']==cust['point_id']==point,
                        'FORMAL_NLT3_EXACT_ORIGINAL_REPLICATE_ATTEMPT')
            for m in METRICS:need(type(agg.get(m))is int and agg[m]>=0,'FORMAL_NLT3_ORIGINAL_REPLICATE_METRIC')
            scope=agg['native_domain_binding_sha256']
            with l.mutex:
                s=l.db.execute('SELECT trajectory,binding FROM aux_scopes WHERE scope=?',(scope,)).fetchone()
                if s is None:raise WaitForEvidence('ORIGINAL_SUCCESS_SCOPE_MISSING')
                native=strict(s[1]);unresolved=l.db.execute("SELECT COUNT(*)FROM aux_permits WHERE scope=?AND state IN('RESERVED','SENT','UNKNOWN')",(scope,)).fetchone()[0]
            need(digest(native)==scope and s[0]==native['trajectory']==row['trajectory']and
                 native['setting']==row['setting']and native['purpose']=='AUX_FINALIZATION'and
                 native['target_tokens']==row['target']and native['replicate_index']==k and
                 native['input_policy_sha256']==row['input_policy']and native['manifest_sha256']==self.contract_sha256 and
                 native.get('replicate_attempt',1)==a and (a==1 or native['point_id']==point)and unresolved==0,
                 'FORMAL_NLT3_ORIGINAL_SUCCESS_HOST_SCOPE_AND_PHYSICAL_CLEAR')
            if j['state']=='COMPLETE':need(j['result']==ah['sha256'],'FORMAL_NLT3_ALREADY_COMPLETE_SAME_RESULT')
            records.append(agg);evidence.append(dict(job_id=j['id'],replicate_index=k,replicate_attempt=a,
                aggregate=ah,aggregate_path=str(ap),custody=ch,custody_path=str(cp),scope=scope,
                terminal_sha256=digest(self.rules.waited(j))))
        for name in('initial_input_sha256','frozen_catalog_sha256'):
            need(all(isinstance(r.get(name),str)and len(r[name])==64 for r in records)and
                 len({r[name]for r in records})<=1,'FORMAL_NLT3_SAME_FROZEN_ORIGINAL_INPUT_CATALOGUE')
        return records,evidence
    def _prepare(self,point):
        self._current();row,snapshot,completions=self._queue_point(point)
        selection=select_terminal(snapshot,self.rules)
        if selection['n']==3:return None # original n3 audit/producer owns that branch
        binding,aux=self._binding(point,row,snapshot)
        records,evidence=self._replicates(point,row,selection,aux)
        return dict(point=point,row=row,snapshot=snapshot,selection=selection,binding=binding,aux=aux,
            records=records,evidence=evidence)
    def produce_point(self,point):
        if point in self.partial:return None
        try:p=self._prepare(point)
        except (WaitForEvidence,FileNotFoundError):return None
        if p is None:return None
        aux=p['aux']
        if (aux/ACCEPTED).exists():return self.consume_point(point)
        if any((aux/name).exists()for name in(PREPARED,AUDIT)):
            self.partial[point]='RETAINED_PREFIX_REQUIRES_EXPLICIT_MINIMAL_SUFFIX_NOT_RETRY';return None
        try:
            prepared=dict(schema='count14-formal100m-terminal-nlt3-prepared-public-v1',PASS=False,
                not_terminal_acceptance=True,owner_birth_sha256=digest(asdict(self.birth)),contract_sha256=self.contract_sha256,
                point=point,source_snapshot_sha256=p['binding']['original_snapshot']['sha256'],
                source_queue_snapshot_sha256=digest(p['snapshot']),binding=p['binding'],evidence=p['evidence'],
                excluded_attempts=p['selection']['excluded'],allowance_decisions=p['selection']['decisions'])
            publish(aux/PREPARED,wire(prepared),mode=0o400)
            for j,e in zip(p['selection']['selected'],p['evidence']):
                with self.core.queue.mutex:
                    need(self.core.queue._job(j['id'])==j,'FORMAL_NLT3_ORIGINAL_JOB_CHANGED_BEFORE_COMPLETE')
                if j['state']!='COMPLETE':self.core.queue.complete(j['id'],j['claim'],result_sha256=e['aggregate']['sha256'],
                    verified_native_audit=dict(job_id=j['id'],result_sha256=e['aggregate']['sha256'],complete=True,
                        unresolved_physical_custody=0,terminal_nlt3_prepared_sha256=digest(prepared)))
            after=self._prepare(point)
            need(after is not None and after['binding']==p['binding']and after['evidence']==p['evidence']and
                 after['selection']['excluded']==p['selection']['excluded']and
                 all(j['state']=='COMPLETE'for j in after['selection']['selected']),
                 'FORMAL_NLT3_REVALIDATE_ORIGINAL_COMPLETE_FILES_AND_ALLOWANCE')
            n=p['selection']['n']
            audit=dict(schema=SCHEMA,PASS=True,terminal=True,contract_sha256=self.contract_sha256,
                owner_birth_sha256=digest(asdict(self.birth)),producer_source_sha256=self.producer_sha256,
                point=point,trajectory=p['row']['trajectory'],setting=p['row']['setting'],nominal_budget=p['row']['target'],
                input_policy_sha256=p['row']['input_policy'],source_snapshot_sha256=p['binding']['original_snapshot']['sha256'],
                planned_replicates=3,replicates_complete=n,complete=n>0,evaluation_complete=n>0,score_computable=n>0,
                binding=p['binding'],evidence=p['evidence'],excluded_attempts=p['selection']['excluded'],
                allowance_decisions=after['selection']['decisions'],all_original_slots_naturally_terminal=True,
                all_unsuccessful_slots_exhausted=True,no_pending_or_unregistered_extra_ignored=True,
                prepared_sha256=digest(prepared),source_queue_snapshot_after_sha256=digest(after['snapshot']),
                billing_domain='AUX_FINALIZATION',search_feedback=False,original_strict_n3_NOT_claimed=True,
                UNKNOWN_fees_and_physical_unproven_slots_NOT_released=True,union_metrics_not_available=True,
                validated_before_publication_at_ns=time.time_ns(),**original_statistics(p['records']))
            publish(aux/AUDIT,wire(audit),mode=0o400)
            # Actual durable publication precedes the acceptance observation.
            accepted=dict(schema='count14-formal100m-terminal-nlt3-accepted-public-v1',PASS=True,
                contract_sha256=self.contract_sha256,owner_birth_sha256=digest(asdict(self.birth)),point=point,
                audit_sha256=digest(audit),producer_source_sha256=self.producer_sha256,replicates_complete=n,
                score_computable=n>0,durable_audit_acceptance_observed_at_ns=time.time_ns())
            publish(aux/ACCEPTED,wire(accepted),mode=0o400)
            return self.consume_point(point)
        except Exception:
            self.partial[point]='RETAIN_ALL_PREFIXES_NO_AUTOMATIC_RETRY';raise
    def consume_point(self,point):
        p=self._prepare(point)
        if p is None:return None
        aux=p['aux']
        if not all((aux/name).exists()for name in(PREPARED,AUDIT,ACCEPTED)):return None
        prepared,ph=self._public_audit(aux/PREPARED);audit,ah=self._public_audit(aux/AUDIT);accepted,ch=self._public_audit(aux/ACCEPTED)
        n=p['selection']['n'];need(n in(0,1,2),'FORMAL_NLT3_SEPARATE_FROM_N3')
        need(audit['schema']==SCHEMA and audit['PASS']is True and audit['terminal']is True and
             audit['contract_sha256']==self.contract_sha256 and audit['owner_birth_sha256']==digest(asdict(self.birth))and
             audit['producer_source_sha256']==self.producer_sha256 and audit['point']==point and
             audit['replicates_complete']==n and audit['complete']is(n>0)and audit['evaluation_complete']is(n>0)and
             audit['score_computable']is(n>0)and audit['binding']==p['binding']and audit['evidence']==p['evidence']and
             audit['excluded_attempts']==p['selection']['excluded']and audit['allowance_decisions']==p['selection']['decisions']and
             audit['prepared_sha256']==ph['sha256']and audit['source_queue_snapshot_after_sha256']==digest(p['snapshot'])and
             prepared['PASS']is False and prepared['not_terminal_acceptance']is True and
             prepared['point']==point and prepared['binding']==p['binding']and prepared['evidence']==p['evidence']and
             accepted['schema']=='count14-formal100m-terminal-nlt3-accepted-public-v1'and accepted['PASS']is True and
             accepted['point']==point and accepted['audit_sha256']==ah['sha256']and
             accepted['producer_source_sha256']==self.producer_sha256 and accepted['replicates_complete']==n and
             accepted['score_computable']is(n>0)and accepted['owner_birth_sha256']==digest(asdict(self.birth))and
             accepted['contract_sha256']==self.contract_sha256 and
             type(accepted['durable_audit_acceptance_observed_at_ns'])is int and
             accepted['durable_audit_acceptance_observed_at_ns']>=audit['validated_before_publication_at_ns'],
             'FORMAL_NLT3_MATCHING_DURABLE_ACCEPTED_ORIGINAL_POINT_PROOFS')
        need({k:audit[k]for k in('means','ranges')}==original_statistics(p['records']),
             'FORMAL_NLT3_ONLY_ORIGINAL_VALID_REPLICATE_MEAN_RANGE')
        for j,e in zip(p['selection']['selected'],p['evidence']):
            need(j['state']=='COMPLETE','FORMAL_NLT3_SELECTED_ORIGINAL_JOB_COMPLETE_REQUIRED')
            proof=dict(job_id=j['id'],result_sha256=e['aggregate']['sha256'],complete=True,
                unresolved_physical_custody=0,terminal_nlt3_prepared_sha256=ph['sha256'])
            _,_,events=self._queue_point(point)
            matching=[event for event in events if event['job_id']==j['id']]
            need(len(matching)==1 and matching[0]['result_sha256']==e['aggregate']['sha256']and
                 matching[0]['audit_sha256']==digest(proof),'FORMAL_NLT3_ORIGINAL_COMPLETE_EVENT_SUFFIX_BINDING')
        return p['row']['trajectory'],p['row']['target'],point,n,ah['sha256'],'N0_UNCOMPUTABLE'if n==0 else'ORIGINAL_VALID_NLT3',digest(dict(audit=ah,accepted=ch,binding=p['binding']))
    def _retain_point_failure(self,point,error,phase):
        """First typed PUBLIC failure only; preserve every original prefix/fee."""
        if point in self.point_failures:return
        locations=[];tb=error.__traceback__
        while tb:
            locations.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,
                                  function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
        value=dict(schema='count14-formal-terminal-point-first-failure-public-v1',
            PUBLIC_code='FORMAL_TERMINAL_POINT_EVIDENCE_RETAINED_NO_RETRY',point=point,
            exception_type=type(error).__name__,phase=phase,locations=locations,
            model_request_retry_or_fee_change=False)
        self.partial.setdefault(point,'RETAIN_ORIGINAL_POINT_PREFIXES_NO_AUTOMATIC_RETRY')
        self.point_failures[point]=value
        home=private_dir(self.core.home/'formal-terminal-point-failures',create=True)
        publish(home/(point+'_FIRST_FAILURE_PUBLIC.json'),wire(value),mode=0o444)

    def poll_produce_ready_points(self):
        """One existing owner tick, at most one suffix commit; no new loop/job."""
        try:final=self._current()
        except WaitForEvidence:return None
        for t in self.core.rows:
            for cut in FORMAL_CUTS:
                point=digest(dict(trajectory=t,target=cut))
                if point in self.partial:continue
                phase='DISPATCHER_POINT_OBSERVATION'
                try:
                    try:record=self._dispatcher_record(point)
                    except WaitForEvidence:return None
                    if record is None or record['audited']is True:continue
                    aux=Path(record['aux'])
                    if not(aux/ACCEPTED).exists():
                        phase='PRODUCE_OR_CONSUME_POINT_EVIDENCE'
                        result=self.produce_point(point)
                        if result is not None:return result
                except Exception as error:
                    self._retain_point_failure(point,error,phase)
        return None
    def _n3_point(self,point,row,snapshot,completions,binding,aux):
        if not(aux/'K3_AUDIT.json').exists():return None
        audit,pin=self._public_audit(aux/'K3_AUDIT.json')
        need(audit['schema']=='count14-agensh-v21-k3-summary-v1'and audit['trajectory']==row['trajectory']and
            audit['setting']==row['setting']and audit['nominal_budget']==row['target']and
            audit['input_policy_sha256']==row['input_policy']and
            audit['source_sha256']==self.core.contract['v2_baseline_reference_protocol']['source_bundle']and
            audit['protocol_sha256']==self.cohort.final.scope.protocol_sha256(row['trajectory'])and
            audit['complete']is True and audit['evaluation_complete']is True and audit['replicates_complete']==3 and
            audit['billing_domain']=='AUX_FINALIZATION'and audit['search_feedback']is False,
            'FORMAL_MIXED_ORIGINAL_STRICT_N3_SUMMARY_UNCHANGED')
        with self.core.queue.mutex:
            jobs=[copy.deepcopy(j)for j in self.rows.effective_rows(self.core.queue)if j['point']==point]
        jobs.sort(key=lambda j:j['replicate'])
        need(len(jobs)==3 and [j['replicate']for j in jobs]==[1,2,3]and all(j['state']=='COMPLETE'for j in jobs),
            'FORMAL_MIXED_N3_THREE_EFFECTIVE_SUCCESSFUL_ORIGINAL_JOBS')
        reps=audit['evidence'];need(len(reps)==3 and {r['replicate_index']for r in reps}=={1,2,3},
            'FORMAL_MIXED_N3_ORIGINAL_AUDIT_EVIDENCE')
        for j in jobs:
            rep=next(r for r in reps if r['replicate_index']==j['replicate']);terminal=self.rules.waited(j)
            need(terminal['exit_code']==0 and terminal['signal']is None and snapshot['wait_events'].get(j['id'])is True and
                 j['result']==rep['aggregate']['sha256']and j.get('attempt',1)==rep.get('replicate_attempt',1),
                 'FORMAL_MIXED_N3_GENUINE_WAIT_ORIGINAL_ATTEMPT_RESULT')
            proof=dict(job_id=j['id'],result_sha256=j['result'],complete=True,
                unresolved_physical_custody=0,original_k3_audit_sha256=digest(audit))
            events=[e for e in completions if e['job_id']==j['id']]
            need(len(events)==1 and events[0]['result_sha256']==j['result']and events[0]['audit_sha256']==digest(proof),
                'FORMAL_MIXED_N3_ORIGINAL_COMPLETE_EVENT')
        return row['trajectory'],row['target'],point,3,pin['sha256'],'ORIGINAL_STRICT_N3',digest(dict(audit=pin,jobs=jobs,binding=binding))
    def _snapshot(self,cohort):
        need(cohort is self.cohort,'FORMAL_MIXED_EXACT_COHORT')
        try:
            final=self._current();expected={digest(dict(trajectory=t,target=cut))for t in self.core.rows for cut in FORMAL_CUTS}
            if not self.core.queue.mutex.acquire(timeout=.25):return None
            try:
                if {r[0]for r in self.core.queue.db.execute('SELECT point FROM points')}!=expected:return None
            finally:self.core.queue.mutex.release()
            evidence=[]
            for t in self.core.rows:
                for cut in FORMAL_CUTS:
                    point=digest(dict(trajectory=t,target=cut))
                    if point in self.point_failures:return None
                    try:
                        row,snapshot,events=self._queue_point(point)
                        need(row['trajectory']==t and row['target']==cut and row['setting']==self.core.rows[t]['arm'],
                            'FORMAL_MIXED_EXACT_REGISTERED_REGULAR_POINT')
                        binding,aux=self._binding(point,row,snapshot)
                        record=self._dispatcher_record(point)
                        if record is None:return None
                        audited=record['audited']
                        outcome=self._n3_point(point,row,snapshot,events,binding,aux)if audited is True else self.consume_point(point)
                        if outcome is None:return None
                        evidence.append(outcome)
                    except (WaitForEvidence,FileNotFoundError):return None
                    except Exception as error:
                        self._retain_point_failure(point,error,'VERIFY_ALL_REGISTERED_POINT_EVIDENCE')
                        return None
            return tuple(evidence),digest(evidence)
        except (WaitForEvidence,FileNotFoundError):return None
    def read_verified_terminal_points(self,cohort):
        snapshot=self._snapshot(cohort)
        if snapshot is None:return None
        points,basis=snapshot
        result=FormalMixedPointEvidence(self.contract_sha256,digest(asdict(self.birth)),basis,points)
        self._issued=result;return result
    def verify(self,cohort,evidence):
        need(type(evidence)is FormalMixedPointEvidence and evidence is self._issued,
             'FORMAL_MIXED_ONLY_THIS_SOURCE_ACTUAL_ISSUED_TYPED_EVIDENCE')
        value=self._snapshot(cohort)
        need(value is not None and value==(evidence.points,evidence.basis_sha256),
             'FORMAL_MIXED_FRESH_UNCHANGED_POINT_PROOFS')
        return evidence.public()
    def close_shared_final_after_drained(self,final,evidence):
        from formal_nlt3_binding import scoped_original_close
        need(final is self.cohort.final and final.core is self.core,'FORMAL_MIXED_SAME_SHARED_FINAL_CLOSE')
        self.verify(self.cohort,evidence)
        if all(p[3]==3 for p in evidence.points):return final.close_after_drained()
        # ONLY the old all-COMPLETE queue predicate is replaced with this
        # independently verified 24-point mixed certificate. Original physical
        # global/children/Popen/HostServer close guards/body remain untouched.
        return scoped_original_close(self,evidence)(final)


def source_pins():
    return {name:hash_file(Path(__file__).with_name(name))['sha256']for name in
        ('formal_nlt3_rules.py','formal_nlt3_source.py','formal_nlt3_binding.py')}
