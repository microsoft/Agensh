"""Approved carrier outer loader over CURRENT SDK4+natural+fixed/allowance."""
from pathlib import Path
from types import FunctionType
import hashlib,importlib.util
PIN='b9c973845c287ff44450e74772c7b379b4a1d9c29473dec62c267ba94b156150'
RETAINED_PARENT_NAMESPACE=None
RETAINED_PRIVATE_FACTORY=None
RETAINED_ORIGINAL_OWNER=None
RETAINED_ORIGINAL_LEDGER=None


def parent():
    p=Path(__file__).resolve().parents[1]/'formal100m-sdk-restore-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_sdk_factory.py'
    if p.resolve()!=p or p.is_symlink()or hashlib.sha256(p.read_bytes()).hexdigest()!=PIN:
        raise ValueError('APPROVED_CARRIER_CURRENT_SDK4_NATURAL_OUTER_SOURCE_PIN')
    spec=importlib.util.spec_from_file_location('count14_approved_queue_private_sdk_factory',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def load_private_factory(*,tester_sources=None,tester_companion=None,approved_repair_sources=()):
    m=parent().load_private_factory(tester_sources=tester_sources,tester_companion=tester_companion,
        approved_repair_sources=approved_repair_sources)
    if m.create_prefix_owner.__globals__ is not vars(m)or hasattr(m,'_approved_queue_outer_constructor'):
        raise ValueError('APPROVED_CARRIER_EXACT_NEW_PRIVATE_CURRENT_FACTORY')
    original=m.private_original_constructor
    def constructor(bind_same_owner):
        helper=original(bind_same_owner);binder=helper._formal_bind_same_owner
        def bind(owner,*,sources):
            cohort=binder(owner,sources=sources)
            from approved_queue_cold import install
            install(cohort)
            return cohort
        helper._formal_bind_same_owner=bind;return helper
    m._approved_queue_outer_constructor=original;m.private_original_constructor=constructor
    m._approved_carrier_cold_proof=dict(current_SDK4_natural_fixed_code_allowance_actualn_binder_runs_once_first=True,
        original_same_owner_ledger_controller_capacity_queue_dispatcher_preserved=True,
        guarded_exact_approved_two_new_CONTROL_tables_only=True,
        one_domain_all_effective_current_production_child_reader=True,
        original_policy3_plus_extra1_exemptions_not_raw_ordinal=True,actual_runtime_qualified=False)
    return m


def verify_actual_formal_import_graph():
    previous=parent().verify_actual_formal_import_graph();m=load_private_factory()
    from approved_queue_install import verify_approval_sources,ddl_statements,pristine_queue_schema
    from approved_queue_binding import bind_natural_point_guard,approved_native_ports
    from approved_queue_reader import ApprovedCarrierReader
    verify_approval_sources();ddl_statements();pristine_queue_schema()
    from queue_control import CarrierQueueDomain
    prototype=CarrierQueueDomain.__new__(CarrierQueueDomain)
    bind_natural_point_guard(prototype) # compile-only, no domain constructor/control
    from approved_queue_cold import child_prepare_body
    from allowance_native import controller_prepare_body
    child_prepare_body(controller_prepare_body(None)) # compile current selector only, no controller
    return dict(schema='count14-approved-carrier-current-SDK4-cold-import-graph-v1',parent=previous,
        approved_carrier=m._approved_carrier_cold_proof,production_guard_and_reader_imported=True,
        actual_owner_or_domain_or_reader_or_DDL_constructed=False,models=0,actual_Dev4_or_formal_qualified=False)


def create_prefix_owner(bindings_path,bindings_sha256,*,code_root,factory_path,factory_manifest,
                        tester_bindings_path=None,tester_bindings_sha256=None,approved_repair_sources=()):
    global RETAINED_PARENT_NAMESPACE,RETAINED_PRIVATE_FACTORY,RETAINED_ORIGINAL_OWNER,RETAINED_ORIGINAL_LEDGER
    if RETAINED_PARENT_NAMESPACE is not None:raise ValueError('APPROVED_CARRIER_ONE_ORIGINAL_OWNER_NO_REPLAY')
    m=parent();original=m.create_prefix_owner;space=dict(vars(m),load_private_factory=load_private_factory)
    fn=FunctionType(original.__code__,space,original.__name__,original.__defaults__,original.__closure__)
    fn.__kwdefaults__=original.__kwdefaults__;RETAINED_PARENT_NAMESPACE=space
    try:return fn(bindings_path,bindings_sha256,code_root=code_root,factory_path=factory_path,
        factory_manifest=factory_manifest,tester_bindings_path=tester_bindings_path,
        tester_bindings_sha256=tester_bindings_sha256,approved_repair_sources=tuple(approved_repair_sources))
    finally:
        RETAINED_PRIVATE_FACTORY=space['RETAINED_PRIVATE_FACTORY'];RETAINED_ORIGINAL_OWNER=space['RETAINED_ORIGINAL_OWNER']
        RETAINED_ORIGINAL_LEDGER=space['RETAINED_ORIGINAL_LEDGER']
