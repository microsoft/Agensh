"""Private outer allowance factory, one fixed-code seam after original bind."""
from pathlib import Path
from types import FunctionType
import hashlib,importlib.util
ALLOWANCE_FACTORY_SHA='ee178902bc25f6d15502a1a67495762cd8dcd45eed661cdb50368e779b78df82'
RETAINED_ALLOWANCE_NAMESPACE=None
RETAINED_PRIVATE_FACTORY=None
RETAINED_ORIGINAL_OWNER=None
RETAINED_ORIGINAL_LEDGER=None


def need(ok,code):
    if not ok:raise ValueError(code)


def _allowance_module():
    path=Path(__file__).resolve().parents[1]/'formal100m-allowance-factory-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_allowance_factory.py'
    need(path.resolve()==path and not path.is_symlink() and
        hashlib.sha256(path.read_bytes()).hexdigest()==ALLOWANCE_FACTORY_SHA,
        'FIXED_CODE_FACTORY_EXACT_PRIOR_ALLOWANCE_FACTORY_SOURCE_PIN')
    spec=importlib.util.spec_from_file_location('count14_fixed_code_private_allowance_factory',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def load_private_factory(*,tester_sources=None,tester_companion=None,approved_repair_sources=()):
    parent=_allowance_module()
    m=parent.load_private_factory(tester_sources=tester_sources,tester_companion=tester_companion,
        approved_repair_sources=approved_repair_sources)
    need(m.create_prefix_owner.__globals__ is vars(m) and not hasattr(m,'_fixed_code_original_constructor'),
        'FIXED_CODE_FACTORY_ONE_PRIVATE_NEW_NAMESPACE_ONLY')
    constructor=m.private_original_constructor
    def original_constructor(bind_same_owner):
        helper=constructor(bind_same_owner)
        need(helper.create_prefix_owner.__globals__ is vars(helper),
            'FIXED_CODE_FACTORY_ORIGINAL_HELPER_EXPLICIT_PRIVATE_BINDER_LOOKUP')
        original=helper._formal_bind_same_owner
        def after_original_bind(owner,*,sources):
            cohort=original(owner,sources=sources) # original control+SDK+idle+tester+actualn+retirement+allowance
            from formal_fixed_code_cold import install
            install(cohort) # before any original prepare/dispatch, never a second binder
            return cohort
        helper._formal_bind_same_owner=after_original_bind
        return helper
    m._fixed_code_original_constructor=constructor
    m.private_original_constructor=original_constructor
    m._fixed_code_cold_seam_proof=dict(original_private_create_code_unchanged=True,
        original_binder_called_exactly_once=True,fixed_hook_only_after_allowance_binder_returns=True,
        original_prepare_and_single_dispatcher_constructor_unchanged=True,
        producer_installs_only_on_same_fresh_dispatcher_before_first_dispatch=True,
        new_control_or_capacity_or_queue_or_controller_or_dispatcher_constructed=False,
        production_carrier_install_authorized=False,automatic_tool_exemptions=0)
    return m


def verify_actual_formal_import_graph():
    parent=_allowance_module();proof=parent.verify_actual_formal_import_graph()
    module=load_private_factory()
    from formal_fixed_code_cold import FormalFixedCodeColdHooks,install,PRODUCER_SHA
    from fixed_public_code_producer import FixedPublicCodeProducer,validate_static_sources,install_fixed_public_code_producer
    need(set(validate_static_sources())=={'AUX_SCOPE_NOT_CURRENT','FINAL_AUTHORITY_QUEUE_CLAIM'},
        'FIXED_CODE_FACTORY_EXACT_TWO_FRAMEWORK_PUBLIC_ENUMS_ONLY')
    return dict(actual_formal_fixed_code_cold_import_graph=True,parent_allowance=proof,
        fixed_code_seam=module._fixed_code_cold_seam_proof,producer_source_sha256=PRODUCER_SHA,
        producer_constructor_or_install_called=False,owner_or_control_or_controller_or_dispatcher_constructed=False,
        models=0,actual_Dev4_or_formal_qualified=False)


def create_prefix_owner(bindings_path,bindings_sha256,*,code_root,factory_path,factory_manifest,
                        tester_bindings_path=None,tester_bindings_sha256=None,approved_repair_sources=()):
    global RETAINED_ALLOWANCE_NAMESPACE,RETAINED_PRIVATE_FACTORY,RETAINED_ORIGINAL_OWNER,RETAINED_ORIGINAL_LEDGER
    need(RETAINED_ALLOWANCE_NAMESPACE is None,'FIXED_CODE_FACTORY_ONE_ORIGINAL_OWNER_CONSTRUCTOR_NO_REPLAY')
    parent=_allowance_module();original=parent.create_prefix_owner
    approved_repair_sources=tuple(approved_repair_sources)
    def loader(**kwargs):return load_private_factory(**kwargs)
    space=dict(vars(parent),load_private_factory=loader)
    create=FunctionType(original.__code__,space,original.__name__,original.__defaults__,original.__closure__)
    create.__kwdefaults__=original.__kwdefaults__
    RETAINED_ALLOWANCE_NAMESPACE=space
    try:
        return create(bindings_path,bindings_sha256,code_root=code_root,factory_path=factory_path,
            factory_manifest=factory_manifest,tester_bindings_path=tester_bindings_path,
            tester_bindings_sha256=tester_bindings_sha256,approved_repair_sources=approved_repair_sources)
    finally:
        RETAINED_PRIVATE_FACTORY=space['RETAINED_PRIVATE_FACTORY']
        RETAINED_ORIGINAL_OWNER=space['RETAINED_ORIGINAL_OWNER']
        RETAINED_ORIGINAL_LEDGER=space['RETAINED_ORIGINAL_LEDGER']
