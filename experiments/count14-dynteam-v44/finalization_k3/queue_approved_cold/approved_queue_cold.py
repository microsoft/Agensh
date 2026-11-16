"""Approved carrier outer cold wiring, after CURRENT natural+SDK binder only."""
from pathlib import Path
from types import FunctionType,MethodType
from common import need,digest
from formal_ast import globals_clone
from approved_queue_install import install as install_domain
from approved_queue_binding import bind_natural_point_guard,bind_control,augment_scope
from approved_queue_reader import ApprovedCarrierReader


def append_import_publisher(original):
    from formal_natural_cold import expanded_import_publisher
    from common import strict,publish,wire,hash_file
    def publisher(destination):
        destination=Path(destination);prefix=destination.with_name(destination.name+'.before-approved-queue-prefix')
        original(prefix);value=strict(prefix.read_bytes());root=Path(__file__).resolve().parent
        need(str(root)not in {r['path']for r in value['roots']},'APPROVED_CARRIER_IMPORT_ROOT_APPEND_ONCE')
        value['roots'].insert(0,dict(path=str(root),files={p.name:hash_file(p)['sha256']for p in sorted(root.glob('*.py'))}))
        # The approved reader/binding imports the ORIGINAL queue proposal.
        # Parent owner already has this explicit frozen source, but python -I
        # does not inherit that parent's sys.path or sys.modules. Pin the same
        # root in the child manifest; never use ambient cwd/PYTHONPATH.
        import queue_control,queue_native
        proposal=Path(__file__).resolve().parents[1]/'formal100m-allowance-queue-proposal-v1'
        need(Path(queue_control.__file__).resolve().parent==proposal and
             Path(queue_native.__file__).resolve().parent==proposal and
             proposal.resolve()==proposal and proposal.is_dir(),
             'APPROVED_CARRIER_EXACT_ORIGINAL_QUEUE_CHILD_IMPORT_ROOT')
        need(str(proposal)not in {r['path']for r in value['roots']},
             'APPROVED_CARRIER_ORIGINAL_QUEUE_CHILD_ROOT_APPEND_ONCE')
        value['roots'].append(dict(path=str(proposal),files={p.name:hash_file(p)['sha256']
            for p in sorted(proposal.glob('*.py'))}))
        publish(destination,wire(value),mode=0o400);return destination,hash_file(destination)['sha256']
    return publisher


def child_prepare_body(current,**bindings):
    old='allowance_final_child.py';new='approved_queue_child.py'
    need(current.__code__.co_consts.count(old)==1,'APPROVED_CARRIER_CURRENT_PREPARE_ONE_CHILD_SOURCE_SELECTOR')
    code=current.__code__.replace(co_consts=tuple(new if v==old else v for v in current.__code__.co_consts))
    need(code.co_code==current.__code__.co_code and code.replace(co_consts=current.__code__.co_consts)==current.__code__,
         'APPROVED_CARRIER_CURRENT_PREPARE_CHILD_SELECTOR_INVERSE_CODE')
    fn=FunctionType(code,dict(current.__globals__,**bindings,__file__=__file__),
        current.__name__,current.__defaults__,current.__closure__)
    fn.__kwdefaults__=current.__kwdefaults__
    return fn


def install(cohort):
    from native_formal_cohort import NativeFormalCohort
    from formal_natural_cut import FormalFirstNaturalPoint
    from formal_natural_terminal import NaturalCompositeTerminalSource
    from formal_nlt3_source import FormalTypedQueueRows
    need(type(cohort)is NativeFormalCohort and type(getattr(cohort,'formal_first_natural_point',None))is FormalFirstNaturalPoint and
         type(getattr(cohort,'formal_natural_terminal_source',None))is NaturalCompositeTerminalSource and
         not hasattr(cohort,'formal_approved_carrier_domain')and cohort.final is None and not cohort.activation_attempted,
         'APPROVED_CARRIER_CURRENT_NATURAL_SAME_COLD_GRAPH_ONLY')
    core=cohort.core;control=cohort.formal_allowance_cold_hooks.control
    def input_verifier(*args,**kwargs):
        need(cohort.final is not None and hasattr(cohort.final.scope,'formal_natural_sidecar'),
             'APPROVED_CARRIER_NO_JOB_INPUT_VERIFICATION_BEFORE_ORIGINAL_FINAL_PREPARE')
        return cohort.final.scope.verify_input(*args,**kwargs)
    domain=install_domain(cohort.owner,cohort,control,input_verifier=input_verifier)
    cohort.formal_approved_carrier_domain=domain
    bind_natural_point_guard(domain);bind_control(control,domain)
    # The SAME exact domain supplies ALL/effective rows to every already-bound
    # actual-n/natural/failure/fixed-producer observer, never old table fallback.
    for source in(cohort.formal_actualn_source,cohort.formal_natural_terminal_source):
        source.provider=domain;source.rows=FormalTypedQueueRows(core,domain)
    need(cohort.formal_retirement.terminal_source is cohort.formal_natural_terminal_source,
         'APPROVED_CARRIER_KEEP_CURRENT_COMPOSITE_TERMINAL_SOURCE')
    current=cohort._prepare_one.__func__;factory=current.__globals__['create_formal_final_controller']
    def controller(*args,**kwargs):
        value=factory(*args,**kwargs)
        before=value._prepare.__func__;parent_scope=before.__globals__['SmokeFinalRuntimeScope']
        def scope(*a,**k):return augment_scope(parent_scope(*a,**k),domain)
        value._prepare=MethodType(child_prepare_body(before,SmokeFinalRuntimeScope=scope,
            publish_import_pins=append_import_publisher(before.__globals__['publish_import_pins'])),value)
        return value
    cohort._prepare_one=MethodType(globals_clone(current,create_formal_final_controller=controller),cohort)
    cohort.formal_approved_carrier_cold_proof=dict(exact_approved_two_table_DDL_installed=True,
        old_queue_and_Ledger_schema_rows_and_events_equal=True,current_natural_SDK_allowance_fixed_code_hooks_retained=True,
        same_domain_all_effective_and_production_native_reader=True,raw_ordinal_is_not_allowance=True,
        no_new_controller_capacity_queue_dispatcher=True,actual_Dev4_or_scientific_runtime_qualified=False)
    return domain
