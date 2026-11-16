"""Outer private cold factory: ensure control -> original binder -> FINAL hook.

All original binder/idle/tester/mixed-terminal/retirement actions run once and
unchanged. Only NEW private namespaces are rebound; no imported module changes.
"""
from pathlib import Path
from types import FunctionType
import hashlib
import importlib.util

ACTUALN_FACTORY_SHA='2e3d4f8153fb752f48487d10569982b97d673e9b10ae1dc69bee5f20bca1d634'
RETAINED_ACTUALN_NAMESPACE=None
RETAINED_PRIVATE_FACTORY=None
RETAINED_ORIGINAL_OWNER=None
RETAINED_ORIGINAL_LEDGER=None


def need(ok,code):
    if not ok:raise ValueError(code)


def _actualn_module():
    path=Path(__file__).resolve().parents[1]/'formal100m-actualn-factory-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_actualn_factory.py'
    need(path.resolve()==path and not path.is_symlink() and
        hashlib.sha256(path.read_bytes()).hexdigest()==ACTUALN_FACTORY_SHA,
        'ALLOWANCE_FACTORY_EXACT_NEW_ACTUALN_FACTORY_SOURCE_PIN')
    spec=importlib.util.spec_from_file_location('count14_allowance_private_actualn_factory',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def load_private_factory(*,tester_sources=None,tester_companion=None,approved_repair_sources=()):
    parent=_actualn_module()
    module=parent.load_private_factory(tester_sources=tester_sources,tester_companion=tester_companion)
    need(module.create_prefix_owner.__globals__ is vars(module) and
        not hasattr(module,'_allowance_original_constructor'),
        'ALLOWANCE_FACTORY_ONE_EXACT_PRIVATE_NAMESPACE_NOT_ACTIVE_MODULE')
    original=module.private_original_constructor
    approved_repair_sources=tuple(approved_repair_sources)
    def constructor(bind_same_owner):
        def same_owner_cold(owner,*,sources):
            from formal_allowance_cold import ensure_formal_allowance_control,install_formal_allowance_cold_hooks
            # Needed by ORIGINAL actual-n source construction inside binder.
            control=ensure_formal_allowance_control(owner,approved_repair_sources=approved_repair_sources)
            cohort=bind_same_owner(owner,sources=sources) # original SDK/bind/idle/tester/source/retire order
            need(cohort.core.formal_allowance_control is control,
                'ALLOWANCE_FACTORY_ACTUALN_MUST_REUSE_SAME_CONTROL_NOT_CREATE_ANOTHER')
            install_formal_allowance_cold_hooks(owner,cohort,
                approved_repair_sources=approved_repair_sources) # AFTER original tester installer
            return cohort
        return original(same_owner_cold)
    module._allowance_original_constructor=original
    module.private_original_constructor=constructor
    module._allowance_cold_seam_proof=dict(
        original_factory_body_code_object_unchanged=True,original_nested_binder_called_exactly_once=True,
        only_private_constructor_callback_rebound=True,control_ensure_before_cohort_bind=True,
        final_hooks_after_idle_tester_actualn_and_retirement=True,
        original_owner_ledger_request_controller_constructors_unchanged=True,
        schema_carrier_install_authorized=False,cause_exemption_producer_installed=False)
    return module


def verify_actual_formal_import_graph():
    parent=_actualn_module();proof=parent.verify_actual_formal_import_graph()
    module=load_private_factory()
    from formal_allowance_cold import ensure_formal_allowance_control,install_formal_allowance_cold_hooks,FormalAllowanceColdHooks
    from allowance_control import FormalAllowanceControl
    from allowance_native import controller_prepare_body
    from failure_continuation import compile_new_dispatcher_poll,compile_dispose
    function=controller_prepare_body(None) # compile only; never execute null-control expression
    dispose=compile_dispose(lambda*d:None) # compile-only inverse proof, NOT a production callback port
    need(function._formal_inverse_AST_proof['reverse_AST_equal'] and
         dispose._formal_inverse_AST_proof['reverse_AST_equal'],
         'ALLOWANCE_FACTORY_ORIGINAL_CONTROLLER_AND_DISPOSITION_REVERSE_AST')
    return dict(actual_formal_allowance_cold_import_graph=True,parent_actualn_import=proof,
        same_owner_cold_control_factory_seam=module._allowance_cold_seam_proof,
        controller_prepare_reverse_AST=function._formal_inverse_AST_proof,
        disposition_reverse_AST=dispose._formal_inverse_AST_proof,
        owner_or_control_or_controller_or_dispatcher_constructed=False,
        raw4_carrier_installed=False,public_cause_producer_installed=False,
        models=0,actual_Dev4_or_formal_qualified=False)


def create_prefix_owner(bindings_path,bindings_sha256,*,code_root,factory_path,factory_manifest,
                        tester_bindings_path=None,tester_bindings_sha256=None,approved_repair_sources=()):
    global RETAINED_ACTUALN_NAMESPACE,RETAINED_PRIVATE_FACTORY,RETAINED_ORIGINAL_OWNER,RETAINED_ORIGINAL_LEDGER
    need(RETAINED_ACTUALN_NAMESPACE is None,'ALLOWANCE_FACTORY_ONE_RETAINED_ORIGINAL_CREATE_NO_REPLAY')
    parent=_actualn_module();original=parent.create_prefix_owner
    approved_repair_sources=tuple(approved_repair_sources)
    def loader(**kwargs):return load_private_factory(**kwargs,approved_repair_sources=approved_repair_sources)
    space=dict(vars(parent),load_private_factory=loader)
    create=FunctionType(original.__code__,space,original.__name__,original.__defaults__,original.__closure__)
    create.__kwdefaults__=original.__kwdefaults__
    RETAINED_ACTUALN_NAMESPACE=space
    try:
        return create(bindings_path,bindings_sha256,code_root=code_root,factory_path=factory_path,
            factory_manifest=factory_manifest,tester_bindings_path=tester_bindings_path,
            tester_bindings_sha256=tester_bindings_sha256)
    finally:
        RETAINED_PRIVATE_FACTORY=space['RETAINED_PRIVATE_FACTORY']
        RETAINED_ORIGINAL_OWNER=space['RETAINED_ORIGINAL_OWNER']
        RETAINED_ORIGINAL_LEDGER=space['RETAINED_ORIGINAL_LEDGER']
