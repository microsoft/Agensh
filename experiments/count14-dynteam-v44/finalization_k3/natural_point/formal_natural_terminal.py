"""Original actual-n regular24 PLUS 0..6 authentic first-natural point proofs.

Same original queue/financial policy/n<3 producer, no fabricated summary/result.
Extra points derive ONLY from original durable first-cut events + exact committed
snapshot generation/input/K3 rows. Regular/natural actual-token collisions remain
separate original point IDs. This is a typed cold source, not a count waiver.
"""
from dataclasses import dataclass,asdict
from pathlib import Path
from types import MethodType
import ast,copy
from common import need,digest,strict,hash_file
from formal_ast import reversible,globals_clone
from formal_scope import FORMAL_CUTS
from formal_nlt3_source import FormalActualNTerminalSource as OriginalSource,FormalMixedPointEvidence as OriginalEvidence
from formal_nlt3_rules import bind_committed_metadata,WaitForEvidence
from formal_natural_cut import first_record,SEALED
import formal_natural_abi as abi


@dataclass(frozen=True)
class NaturalCompositeEvidence:
    contract_sha256:str
    original_owner_birth_sha256:str
    basis_sha256:str
    points:tuple
    natural_points:tuple
    def public(self):
        nids={p[2]for p in self.natural_points}
        return dict(schema='count14-formal100m-regular-and-natural-terminal-public-v1',
            contract_sha256=self.contract_sha256,original_owner_birth_sha256=self.original_owner_birth_sha256,
            basis_sha256=self.basis_sha256,terminal_points=len(self.points),
            regular_terminal_points=sum(p[2]not in nids for p in self.points),
            natural_terminal_points=len(self.natural_points),effective_n=[p[3]for p in self.points],
            n0_is_terminal_not_computable=True,fixed_sum72_success_requirement=False,
            physical_unknown_slot_release_claimed=False)


def point_id(t,target,meta=None):
    value=dict(trajectory=t,target=target)
    if meta is not None:value.update(point_kind=abi.KIND,policy_sha256=meta['policy_sha256'])
    return digest(value)


class NaturalCompositeTerminalSource(OriginalSource):
    def __init__(self,source):
        need(type(source)is OriginalSource and not source.cohort.activation_attempted and source._issued is None,
             'FORMAL_NATURAL_TERMINAL_SAME_COLD_EXACT_ACTUALN_SOURCE')
        self.__dict__=dict(source.__dict__)
        self.original_regular_source=source
        self.producer_sha256=digest(dict(original=source.producer_sha256,natural=hash_file(Path(__file__))['sha256']))
        self._natural_map={};self._issued=None
        compile_terminal_ports(self)

    def expected(self):
        regular={point_id(t,cut):(t,cut,None)for t in self.core.rows for cut in FORMAL_CUTS}
        natural={}
        for t in self.core.rows:
            record=first_record(self.core.ledger,t)
            if record is None:continue
            meta=record['natural_stop']
            need(meta==abi.metadata(t,meta['generation'],meta['actual_tokens']) and
                 record['contract_sha256']==self.contract_sha256,'FORMAL_NATURAL_DURABLE_FIRST_EVENT_AUTHORITY')
            key=point_id(t,meta['actual_tokens'],meta)
            natural[key]=(t,meta['actual_tokens'],meta)
        need(len(natural)<=len(self.core.rows),'FORMAL_NATURAL_MAX_ONE_FIRST_PER_TRAJECTORY')
        self._natural_map=natural
        return {**regular,**natural}

    def _bind_metadata(self,**values):
        point=values['point'];meta=self._natural_map.get(point,(None,None,None))[2]
        if meta is None:return bind_committed_metadata(**values)
        policy=values['policy']
        need(abi.natural(policy)==meta and values['checkpoint_entry']['generation']==meta['generation'] and
             values['target']==meta['actual_tokens'],'FORMAL_NATURAL_COMMITTED_INPUT_EXACT_FIRST_GENERATION')
        canonical=dict(trajectory=values['trajectory'],target=values['target'])
        # Original body and every saved/snapshot/job/hash equality stay exact;
        # only that body's original point-namespace lookup is scoped.
        def scoped_digest(value):return point if value==canonical else digest(value)
        result=globals_clone(bind_committed_metadata,digest=scoped_digest)(**values)
        result.update(point_kind=abi.KIND,natural_stop=meta)
        return result

    def _n3_point(self,point,row,snapshot,completions,binding,aux):
        meta=self._natural_map.get(point,(None,None,None))[2]
        if meta is not None:
            if not(aux/'K3_AUDIT.json').exists():return None
            audit,_=self._public_audit(aux/'K3_AUDIT.json')
            need(audit.get('point_kind')==abi.KIND and audit.get('natural_stop')==meta,
                 'FORMAL_NATURAL_ORIGINAL_N3_SUMMARY_EXACT_IDENTITY')
        return OriginalSource._n3_point(self,point,row,snapshot,completions,binding,aux)

    def _snapshot(self,cohort):
        need(cohort is self.cohort,'FORMAL_NATURAL_COMPOSITE_EXACT_COHORT')
        try:
            self._current();expected=self.expected()
            if not self.core.queue.mutex.acquire(timeout=.25):return None
            try:
                if {r[0]for r in self.core.queue.db.execute('SELECT point FROM points')}!=set(expected):return None
            finally:self.core.queue.mutex.release()
            evidence=[]
            for point,(t,cut,meta)in sorted(expected.items()):
                if point in self.point_failures:return None
                try:
                    row,snapshot,events=self._queue_point(point)
                    need(row['trajectory']==t and row['target']==cut and row['setting']==self.core.rows[t]['arm'],
                         'FORMAL_NATURAL_COMPOSITE_EXACT_REGISTERED_POINT_KIND')
                    binding,aux=self._binding(point,row,snapshot)
                    record=self._dispatcher_record(point)
                    if record is None:return None
                    outcome=self._n3_point(point,row,snapshot,events,binding,aux)if record['audited']is True else self.consume_point(point)
                    if outcome is None:return None
                    evidence.append(outcome)
                except (WaitForEvidence,FileNotFoundError):return None
                except Exception as error:
                    self._retain_point_failure(point,error,'VERIFY_ALL_REGISTERED_NATURAL_POINT_EVIDENCE')
                    return None
            return tuple(evidence),digest(evidence)
        except (WaitForEvidence,FileNotFoundError):return None

    def poll_produce_ready_points(self):
        try:self._current();expected=self.expected()
        except WaitForEvidence:return None
        for point in sorted(expected):
            if point in self.partial:continue
            phase='NATURAL_DISPATCHER_POINT_OBSERVATION'
            try:
                try:record=self._dispatcher_record(point)
                except WaitForEvidence:return None
                if record is None or record['audited']is True:continue
                aux=Path(record['aux'])
                from formal_nlt3_source import ACCEPTED
                if not(aux/ACCEPTED).exists():
                    phase='PRODUCE_OR_CONSUME_NATURAL_POINT_EVIDENCE'
                    result=self.produce_point(point)
                    if result is not None:return result
            except Exception as error:
                self._retain_point_failure(point,error,phase)
        return None

    def read_verified_terminal_points(self,cohort):
        value=self._snapshot(cohort)
        if value is None:return None
        points,basis=value
        natural=tuple(p for p in points if p[2]in self._natural_map)
        result=NaturalCompositeEvidence(self.contract_sha256,digest(asdict(self.birth)),basis,points,natural)
        self._issued=result;return result

    def verify(self,cohort,evidence):
        need(type(evidence)is NaturalCompositeEvidence and evidence is self._issued,
             'FORMAL_NATURAL_ONLY_THIS_COMPOSITE_ISSUED_TYPED_EVIDENCE')
        value=self._snapshot(cohort)
        need(value is not None and value==(evidence.points,evidence.basis_sha256)and
             tuple(p for p in value[0]if p[2]in self._natural_map)==evidence.natural_points,
             'FORMAL_NATURAL_ALL_REGULAR_AND_EXTRA_FRESH_UNCHANGED_PROOFS')
        public=evidence.public();need(public['regular_terminal_points']==24,'FORMAL_NATURAL_ALL_ORIGINAL_REGULAR24_RETAINED')
        return public

    def close_shared_final_after_drained(self,final,evidence):
        from formal_nlt3_binding import scoped_original_close
        need(final is self.cohort.final and final.core is self.core,'FORMAL_NATURAL_SAME_SHARED_FINAL_CLOSE')
        self.verify(self.cohort,evidence)
        # Private original close differs only at all-COMPLETE predicate, same
        # original physical/global/child Popen and HostServer normal close.
        from smoke_checkpoint_final_controller import SmokeFinalController
        class Certified(ast.NodeTransformer):
            def __init__(self,e):self.e=e
            def visit_Compare(self,n):
                if ast.unparse(n)=="set(counts) == {'COMPLETE'}":
                    return self.e.replace(n,ast.Call(func=ast.Name('_natural_verified',ast.Load()),args=[],keywords=[]),
                        'typed_regular24_and_all_actual_natural_terminals')
                return self.generic_visit(n)
        def verified():return self.verify(self.cohort,evidence)['regular_terminal_points']==24
        body=reversible(SmokeFinalController.close_after_drained,Certified,
            expected={'typed_regular24_and_all_actual_natural_terminals':1},bindings={'_natural_verified':verified})
        return body(final)


def compile_terminal_ports(self):
    # Keep CURRENT original n<3 physical/allowance readers; only exact point
    # entry discrimination and report-label lookup differ.
    class EntryKind(ast.NodeTransformer):
        def __init__(self,e):self.e=e
        def visit_Compare(self,n):
            if ast.unparse(n)=="p['target_tokens'] == cut":
                value=ast.parse("p['target_tokens']==cut and _natural_entry(self,point,p)",mode='eval').body
                return self.e.replace(n,value,'natural_vs_regular_original_generation')
            return self.generic_visit(n)
    binding=reversible(OriginalSource._binding,EntryKind,
        expected={'natural_vs_regular_original_generation':1},
        bindings={'_natural_entry':entry_matches,'bind_committed_metadata':self._bind_metadata})
    self._binding=MethodType(binding,self)
    class ExactLabel(ast.NodeTransformer):
        def __init__(self,e):self.e=e
        def visit_JoinedStr(self,n):
            if ast.dump(n,include_attributes=False)==ast.dump(ast.parse('''f"s{row['target']//1000000}m-k{k}"''',mode='eval').body,include_attributes=False):
                value=ast.parse("_natural_label(self,point,row['target'])+f'-k{k}'",mode='eval').body
                return self.e.replace(n,value,'original_exact_natural_report_label')
            return self.generic_visit(n)
    replicate=reversible(OriginalSource._replicates,ExactLabel,
        expected={'original_exact_natural_report_label':1},bindings={'_natural_label':report_label})
    self._replicates=MethodType(replicate,self)


def entry_matches(source,point,entry):
    source.expected()
    meta=source._natural_map.get(point,(None,None,None))[2]
    if meta is not None:return entry['generation']==meta['generation']
    # Regular entry can equal the first actual-token cut; never select its gen.
    return all(entry['generation']!=m['generation']for t,cut,m in source._natural_map.values()
               if t==source._binding_trajectory_for_point(point))


def report_label(source,point,target):
    meta=source._natural_map.get(point,(None,None,None))[2]
    return abi.label(target,meta)


def _trajectory(source,point):return source.expected()[point][0]
NaturalCompositeTerminalSource._binding_trajectory_for_point=_trajectory

# Exact aliases consumed by ORIGINAL retirement import names, no facade type.
FormalPointTerminalSource=FormalActualNTerminalSource=NaturalCompositeTerminalSource
FormalPointTerminalEvidence=FormalMixedPointEvidence=NaturalCompositeEvidence
