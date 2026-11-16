"""Cold-only private typed retirement/close seams; no owner or dispatcher loop."""
import ast,copy
from types import MethodType
from common import need,digest
from formal_ast import reversible


def scoped_original_close(source,evidence):
    from smoke_checkpoint_final_controller import SmokeFinalController
    class MixedQueuePredicate(ast.NodeTransformer):
        def __init__(self,e):self.e=e
        def visit_Compare(self,n):
            if ast.unparse(n)=="set(counts) == {'COMPLETE'}":
                return self.e.replace(n,ast.Call(func=ast.Name('_verified_mixed_points',ast.Load()),args=[],keywords=[]),
                    'separate_verified_mixed_terminal_predicate')
            return self.generic_visit(n)
    def verified():return source.verify(source.cohort,evidence)['terminal_points']==24
    return reversible(SmokeFinalController.close_after_drained,MixedQueuePredicate,
        expected={'separate_verified_mixed_terminal_predicate':1},bindings={'_verified_mixed_points':verified})


def bind_retirement_source(retirement,source):
    """Bind only to a new same-owner cold retirement instance, never hot adoption."""
    from formal_cohort_retirement import FormalCohortRetirement,WAIT_SOURCE
    from formal_nlt3_source import FormalActualNTerminalSource,FormalMixedPointEvidence
    need(type(retirement)is FormalCohortRetirement and type(source)is FormalActualNTerminalSource and
        source.cohort is retirement.cohort and source.core is retirement.core and retirement.state==WAIT_SOURCE and
        retirement.evidence is None and retirement.home is None and not retirement.cohort.activation_attempted and
        set(retirement.core.gate.startup_held)==set(retirement.core.rows),
        'FORMAL_MIXED_ONLY_NEW_COLD_SAME_ORIGINAL_RETIREMENT')
    class TypedImports(ast.NodeTransformer):
        def __init__(self,e):self.e=e
        def visit_ImportFrom(self,n):
            if n.module=='formal_terminal_source':
                names=[]
                for a in n.names:
                    name={'FormalPointTerminalSource':'FormalActualNTerminalSource',
                          'FormalPointTerminalEvidence':'FormalMixedPointEvidence'}.get(a.name)
                    need(name is not None,'FORMAL_MIXED_EXACT_ORIGINAL_SOURCE_IMPORT')
                    names.append(ast.alias(name=name,asname=a.name))
                return self.e.replace(n,ast.ImportFrom(module='formal_nlt3_source',names=names,level=0),'typed_new_source_import')
            return n
    for name in('_require_source_type','_read_verified_evidence'):
        fn=reversible(getattr(FormalCohortRetirement,name),TypedImports,expected={'typed_new_source_import':1})
        setattr(retirement,name,MethodType(fn,retirement))
    original_read=retirement._read_verified_evidence
    def read(this):
        source.poll_produce_ready_points() # one existing owner tick, not new loop
        return original_read()
    retirement._read_verified_evidence=MethodType(read,retirement)
    retirement.terminal_source=source;retirement._require_source_type()
    # Original host PUBLIC metadata's 72-success label is not a new rule.
    final=retirement.cohort.final
    if final is not None:
        original_public=final.public
        def public(this):
            value=original_public();value.pop('expected_effective_K3_jobs',None)
            value.update(terminal_rule='ORIGINAL_STRICT_N3_OR_VERIFIED_NATURAL_ACTUAL_N',
                planned_initial_replicate_slots=len(source.core.rows)*4*source.core.contract['finalization']['K'],
                fixed_success_count_gate=False)
            return value
        final.public=MethodType(public,final)
    return retirement
