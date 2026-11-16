"""One cold outer composition on CURRENT fixed-code/allowance/actualn graph.

No new owner/control/controller/queue/capacity/dispatcher. Every preexisting
hook runs first. No admitted request or active framework object is hot patched.
"""
from pathlib import Path
from types import MethodType
import ast,json
from common import need,digest,strict,publish,wire,hash_file
from formal_ast import reversible,globals_clone
from formal_natural_scope import augment_scope
from formal_natural_cut import FormalFirstNaturalPoint,first_record
from formal_natural_sampler import NativeTeamIdleSampler
from formal_natural_terminal import NaturalCompositeTerminalSource,point_id
from formal_natural_compile import redirect
import formal_natural_abi as abi


def registered_control_point(control,point,row):
    t=row['trajectory'];target=row['target']
    if point==point_id(t,target):return target in control.core.rows[t]['checkpoints_tokens']
    record=first_record(control.core.ledger,t)
    if record is None:return False
    meta=record['natural_stop']
    if meta!=abi.metadata(t,meta['generation'],meta['actual_tokens']) or point!=point_id(t,target,meta):return False
    if target!=meta['actual_tokens'] or record['contract_sha256']!=digest(control.core.contract):return False
    account=control.core.ledger.account(t)
    if json.loads(account['targets'])!=record['targets_with_natural_cut']:return False
    committed=control.core.ledger.db.execute('SELECT target FROM snapshots WHERE trajectory=? AND generation=?',
        (t,meta['generation'])).fetchall()
    return [r[0]for r in committed]==[target]


def bind_control(control):
    from allowance_control import FormalAllowanceControl
    need(type(control)is FormalAllowanceControl and not hasattr(control,'formal_natural_point_guard'),
         'FORMAL_NATURAL_SAME_EXACT_NEW_ALLOWANCE_CONTROL_ONCE')
    fn=control_snapshot_body(control._snapshot.__func__)
    control._snapshot=MethodType(fn,control);control.formal_natural_point_guard=fn._formal_inverse_AST_proof

def control_snapshot_body(original):
    class PointGuard(ast.NodeTransformer):
        def __init__(self,e):self.e=e
        def visit_Compare(self,n):
            if ast.unparse(n)=="r['target'] in self.core.rows[r['trajectory']]['checkpoints_tokens']":
                value=ast.parse('_natural_control_point(self,point,r)',mode='eval').body
                return self.e.replace(n,value,'registered_regular_or_exact_durable_first_natural_point')
            return self.generic_visit(n)
    fn=reversible(original,PointGuard,expected={'registered_regular_or_exact_durable_first_natural_point':1},
        bindings={'_natural_control_point':registered_control_point})
    return fn


def expected_targets(source,t):
    record=first_record(source.core.ledger,t)
    return list(__import__('formal_scope').FORMAL_CUTS) if record is None else record['targets_with_natural_cut']


def bind_retirement(retirement,source):
    from formal_cohort_retirement import FormalCohortRetirement,WAIT_SOURCE
    need(type(retirement)is FormalCohortRetirement and type(source)is NaturalCompositeTerminalSource and
         retirement.state==WAIT_SOURCE and retirement.evidence is None and retirement.home is None and
         not retirement.cohort.activation_attempted and source.core is retirement.core and source.cohort is retirement.cohort,
         'FORMAL_NATURAL_COLD_EXISTING_RETIREMENT_AND_COMPOSITE_SOURCE')
    for name in('_require_source_type','_read_verified_evidence'):
        fn=redirect(getattr(FormalCohortRetirement,name),expected_imports=1,
            old='formal_terminal_source',new='formal_natural_terminal')
        setattr(retirement,name,MethodType(fn,retirement))
    original=retirement._read_verified_evidence
    def read(own):
        source.poll_produce_ready_points()
        return original()
    retirement._read_verified_evidence=MethodType(read,retirement)
    class FinalCuts(ast.NodeTransformer):
        def __init__(self,e):self.e=e
        def visit_Compare(self,n):
            if ast.unparse(n)=="[point['target_tokens'] for point in cp.points] == list(CUTS)":
                value=ast.parse("[point['target_tokens'] for point in cp.points]==_natural_targets(t)",mode='eval').body
                return self.e.replace(n,value,'preserve_all_regulars_and_exact_first_natural_order')
            if ast.unparse(n)=="account['stage'] == 3":
                value=ast.parse("account['stage']==len(_natural_targets(t))-1 and json.loads(account['targets'])==_natural_targets(t)",mode='eval').body
                return self.e.replace(n,value,'actual_final_stage_from_preserved_targets')
            return self.generic_visit(n)
    fn=reversible(FormalCohortRetirement.verify_original_final_cuts,FinalCuts,
        expected={'preserve_all_regulars_and_exact_first_natural_order':1,'actual_final_stage_from_preserved_targets':1},
        bindings={'_natural_targets':lambda t:expected_targets(source,t),'json':json})
    retirement.verify_original_final_cuts=MethodType(fn,retirement)
    retirement.terminal_source=source;retirement._require_source_type()


def expanded_import_publisher(original):
    def publish_imports(destination):
        destination=Path(destination)
        prefix=destination.with_name(destination.name+'.before-natural-prefix')
        original(prefix) # original frozen source receipt preserved, not rewritten
        value=strict(prefix.read_bytes());root=Path(__file__).resolve().parent
        need(str(root)not in {r['path']for r in value['roots']},'FORMAL_NATURAL_IMPORT_ROOT_APPEND_ONCE')
        value['roots'].insert(0,dict(path=str(root),files={p.name:hash_file(p)['sha256']for p in sorted(root.glob('*.py'))}))
        publish(destination,wire(value),mode=0o400)
        return destination,hash_file(destination)['sha256']
    return publish_imports


def install(cohort):
    from native_formal_cohort import NativeFormalCohort
    from formal_allowance_cold import FormalAllowanceColdHooks
    from formal_fixed_code_cold import FormalFixedCodeColdHooks
    need(type(cohort)is NativeFormalCohort and cohort.final is None and not cohort.activation_attempted and
         type(getattr(cohort,'formal_allowance_cold_hooks',None))is FormalAllowanceColdHooks and
         type(getattr(cohort,'formal_fixed_public_code_cold_hook',None))is FormalFixedCodeColdHooks and
         not hasattr(cohort,'formal_first_natural_point'), 'FORMAL_NATURAL_ONLY_AFTER_CURRENT_FIXED_CODE_FULL_COLD_BIND')
    control=cohort.formal_allowance_cold_hooks.control
    bind_control(control)
    source=NaturalCompositeTerminalSource(cohort.formal_actualn_source)
    cohort.formal_natural_terminal_source=source
    bind_retirement(cohort.formal_retirement,source)
    sampler=NativeTeamIdleSampler(cohort)
    producer=FormalFirstNaturalPoint(cohort,sampler=sampler)
    # CURRENT typed-initial/tester/failure/allowance hook is already compiled;
    # preserve its exact code object and replace only captured factory binding.
    current=cohort._prepare_one.__func__
    factory=current.__globals__['create_formal_final_controller']
    def controller(*args,**kwargs):
        value=factory(*args,**kwargs)
        before=value._prepare.__func__
        parent_scope=before.__globals__['SmokeFinalRuntimeScope']
        publisher=before.__globals__['publish_import_pins']
        def scope(*a,**k):return augment_scope(parent_scope(*a,**k))
        value._prepare=MethodType(globals_clone(before,SmokeFinalRuntimeScope=scope,
            publish_import_pins=expanded_import_publisher(publisher)),value)
        return value
    cohort._prepare_one=MethodType(globals_clone(current,create_formal_final_controller=controller),cohort)
    cohort.formal_natural_cold_proof=dict(current_prepare_code_identical=True,current_allowance_scope_factory_chained=True,
        same_fixed_code_and_failure_dispatcher_preserved=True,extra_points_typed_not_fixed72=True,
        no_new_financial_schema_or_formula=True,actual_runtime_qualified=False)
    return producer
