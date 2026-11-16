"""Outer cold SDK hook on CURRENT natural/fixed-code/allowance/actualn chain."""
from pathlib import Path
from types import FunctionType
import hashlib,importlib.util
PARENT_SHA='208921bccb3856a714200b47edc30d2996d5260f98c8a6529c6152f0d3931b00'
RETAINED_PARENT_NAMESPACE=None
RETAINED_PRIVATE_FACTORY=None
RETAINED_ORIGINAL_OWNER=None
RETAINED_ORIGINAL_LEDGER=None


def parent():
    p=Path(__file__).resolve().parents[1]/'formal100m-natural-point-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_natural_factory.py'
    if p.resolve()!=p or p.is_symlink()or hashlib.sha256(p.read_bytes()).hexdigest()!=PARENT_SHA:raise ValueError('SDK_RESTORE_CURRENT_NATURAL_OUTER_SOURCE_PIN')
    spec=importlib.util.spec_from_file_location('count14_sdk_private_natural_factory',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def load_private_factory(*,tester_sources=None,tester_companion=None,approved_repair_sources=()):
    m=parent().load_private_factory(tester_sources=tester_sources,tester_companion=tester_companion,
        approved_repair_sources=approved_repair_sources)
    if m.create_prefix_owner.__globals__ is not vars(m)or hasattr(m,'_sdk_outer_constructor'):raise ValueError('SDK_RESTORE_ONLY_NEW_PRIVATE_FACTORY_NAMESPACE')
    original=m.private_original_constructor
    def constructor(bind_same_owner):
        helper=original(bind_same_owner);binder=helper._formal_bind_same_owner
        def bind(owner,*,sources):
            cohort=binder(owner,sources=sources)
            from formal_sdk_restore import install_sdk_restore
            install_sdk_restore(cohort)
            return cohort
        helper._formal_bind_same_owner=bind;return helper
    m._sdk_outer_constructor=original;m.private_original_constructor=constructor
    m._sdk_cold_proof=dict(current_natural_fixed_code_allowance_actualn_binder_runs_once_first=True,
        current_prepare_function_code_objects_preserved=True,original_owner_ledger_dispatcher_unchanged=True,
        fresh_epoch_constructor_guards_not_weakened=True,whole_cold_owner_restore_implemented=False,
        prospective_strict_same_owner_CLI_restore_only=True)
    return m


def verify_actual_formal_import_graph():
    previous=parent().verify_actual_formal_import_graph();m=load_private_factory()
    from formal_sdk_restore import FormalSdkRestoreControl,SdkRestorePlan,install_sdk_restore
    from sdk_restore_overlay import compile_overlay
    from sdk_restore_bridge_guest import serve_if_cold
    root=Path(__file__).resolve().parents[1]/'racing-complete-cold-tree-v4-msg237-held20-v1-msg237-prefix21-v1'
    _,proof=compile_overlay(root/'native-clock-overlay-v1/dist/acp_socket_channel.js',
        root/'native-clock-overlay-v1/dist/main.js',root/'native-guarded-control-source-v2/acp-bridge.py')
    return dict(parent=previous,sdk=m._sdk_cold_proof,strict_overlay_inverse=proof,
        source_control_constructor_or_SDK_load_called=False,models=0,actual_SDK_or_whole_owner_restore_qualified=False)


def create_prefix_owner(bindings_path,bindings_sha256,*,code_root,factory_path,factory_manifest,
                        tester_bindings_path=None,tester_bindings_sha256=None,approved_repair_sources=()):
    global RETAINED_PARENT_NAMESPACE,RETAINED_PRIVATE_FACTORY,RETAINED_ORIGINAL_OWNER,RETAINED_ORIGINAL_LEDGER
    if RETAINED_PARENT_NAMESPACE is not None:raise ValueError('SDK_RESTORE_ONE_ORIGINAL_OWNER_NO_REPLAY')
    m=parent();original=m.create_prefix_owner;space=dict(vars(m),load_private_factory=load_private_factory)
    fn=FunctionType(original.__code__,space,original.__name__,original.__defaults__,original.__closure__)
    fn.__kwdefaults__=original.__kwdefaults__;RETAINED_PARENT_NAMESPACE=space
    try:return fn(bindings_path,bindings_sha256,code_root=code_root,factory_path=factory_path,
        factory_manifest=factory_manifest,tester_bindings_path=tester_bindings_path,
        tester_bindings_sha256=tester_bindings_sha256,approved_repair_sources=tuple(approved_repair_sources))
    finally:
        RETAINED_PRIVATE_FACTORY=space['RETAINED_PRIVATE_FACTORY'];RETAINED_ORIGINAL_OWNER=space['RETAINED_ORIGINAL_OWNER']
        RETAINED_ORIGINAL_LEDGER=space['RETAINED_ORIGINAL_LEDGER']
