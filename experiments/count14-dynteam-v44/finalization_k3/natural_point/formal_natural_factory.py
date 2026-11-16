"""Private cold outer loader AFTER CURRENT fixed-code/allowance/actualn chain."""
from pathlib import Path
from types import FunctionType
import hashlib,importlib.util
PIN='2c83086eed5b2284f840467d3417860fdbf8049b6ce966222ccb7e1a65f3004e'
RETAINED_PARENT_NAMESPACE=None
RETAINED_PRIVATE_FACTORY=None
RETAINED_ORIGINAL_OWNER=None
RETAINED_ORIGINAL_LEDGER=None


def parent():
    p=Path(__file__).resolve().parents[1]/'formal100m-fixed-code-factory-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_fixed_code_factory.py'
    if p.resolve()!=p or p.is_symlink()or hashlib.sha256(p.read_bytes()).hexdigest()!=PIN:
        raise ValueError('FORMAL_NATURAL_CURRENT_FIXED_CODE_PARENT_SOURCE_PIN')
    spec=importlib.util.spec_from_file_location('count14_natural_private_fixed_code_factory',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def load_private_factory(*,tester_sources=None,tester_companion=None,approved_repair_sources=()):
    m=parent().load_private_factory(tester_sources=tester_sources,tester_companion=tester_companion,
        approved_repair_sources=approved_repair_sources)
    if m.create_prefix_owner.__globals__ is not vars(m)or hasattr(m,'_natural_outer_constructor'):
        raise ValueError('FORMAL_NATURAL_EXACT_NEW_PRIVATE_CURRENT_FACTORY')
    original=m.private_original_constructor
    def constructor(bind_same_owner):
        helper=original(bind_same_owner);binder=helper._formal_bind_same_owner
        def bind(owner,*,sources):
            cohort=binder(owner,sources=sources)
            from formal_natural_cold import install
            install(cohort)
            return cohort
        helper._formal_bind_same_owner=bind
        return helper
    m._natural_outer_constructor=original;m.private_original_constructor=constructor
    m._natural_cold_proof=dict(current_fixed_code_binder_runs_once_first=True,
        original_same_owner_ledger_controller_capacity_queue_dispatcher_preserved=True,
        typed_natural_sampler_capture_collector_current_allowance_child_and_composite_terminal_connected=True,
        current_prepare_function_code_objects_preserved=True,actual_runtime_qualified=False)
    return m


def verify_actual_formal_import_graph():
    previous=parent().verify_actual_formal_import_graph()
    m=load_private_factory()
    from formal_natural_cold import install,control_snapshot_body,bind_retirement
    from allowance_control import FormalAllowanceControl
    from formal_natural_terminal import NaturalCompositeTerminalSource,compile_terminal_ports
    from formal_natural_sampler import NativeTeamIdleSampler
    from formal_natural_cut import FormalFirstNaturalPoint
    from formal_natural_scope import augment_scope
    control_snapshot_body(FormalAllowanceControl._snapshot)
    prototype=NaturalCompositeTerminalSource.__new__(NaturalCompositeTerminalSource)
    compile_terminal_ports(prototype) # compile ports only; no source/core ctor
    return dict(schema='count14-formal-natural-current-fixed-code-import-graph-v1',parent=previous,
        natural=m._natural_cold_proof,prototype_compile_only_no_source_constructor=True,
        control_snapshot_guard_compiled=True,actual_owner_or_sampler_or_control_or_dispatcher_constructed=False,
        models=0,actual_Dev4_or_formal_qualified=False)


def create_prefix_owner(bindings_path,bindings_sha256,*,code_root,factory_path,factory_manifest,
                        tester_bindings_path=None,tester_bindings_sha256=None,approved_repair_sources=()):
    global RETAINED_PARENT_NAMESPACE,RETAINED_PRIVATE_FACTORY,RETAINED_ORIGINAL_OWNER,RETAINED_ORIGINAL_LEDGER
    if RETAINED_PARENT_NAMESPACE is not None:raise ValueError('FORMAL_NATURAL_ONE_ORIGINAL_OWNER_NO_REPLAY')
    m=parent();original=m.create_prefix_owner;space=dict(vars(m),load_private_factory=load_private_factory)
    fn=FunctionType(original.__code__,space,original.__name__,original.__defaults__,original.__closure__)
    fn.__kwdefaults__=original.__kwdefaults__;RETAINED_PARENT_NAMESPACE=space
    try:return fn(bindings_path,bindings_sha256,code_root=code_root,factory_path=factory_path,
        factory_manifest=factory_manifest,tester_bindings_path=tester_bindings_path,
        tester_bindings_sha256=tester_bindings_sha256,approved_repair_sources=tuple(approved_repair_sources))
    finally:
        RETAINED_PRIVATE_FACTORY=space['RETAINED_PRIVATE_FACTORY']
        RETAINED_ORIGINAL_OWNER=space['RETAINED_ORIGINAL_OWNER']
        RETAINED_ORIGINAL_LEDGER=space['RETAINED_ORIGINAL_LEDGER']
