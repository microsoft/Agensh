"""Independent WIP outer factory over CURRENT approved carrier -> SDK4 chain."""
from pathlib import Path
from types import FunctionType
import hashlib
import importlib.util

PIN = '68985fc4c4967ad6efd967a9b188c299bb6f2d690fdfa6cd10d548275436bc92'
RETAINED_PARENT_NAMESPACE = None
RETAINED_PRIVATE_FACTORY = None
RETAINED_ORIGINAL_OWNER = None
RETAINED_ORIGINAL_LEDGER = None


def parent():
    p = Path(__file__).resolve().parents[1] / 'formal100m-queue-approved-cold-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/approved_queue_factory.py'
    if p.resolve() != p or p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest() != PIN:
        raise ValueError('FULL_USED_CURRENT_APPROVED_SDK4_PARENT_SOURCE_PIN')
    spec = importlib.util.spec_from_file_location('count14_full_used_private_approved_factory', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def load_private_factory(*, tester_sources=None, tester_companion=None, approved_repair_sources=()):
    m = parent().load_private_factory(tester_sources=tester_sources, tester_companion=tester_companion,
        approved_repair_sources=approved_repair_sources)
    if m.create_prefix_owner.__globals__ is not vars(m) or hasattr(m, '_full_used_outer_constructor'):
        raise ValueError('FULL_USED_ONLY_NEW_PRIVATE_FACTORY_NAMESPACE')
    original = m.private_original_constructor
    def constructor(bind_same_owner):
        helper = original(bind_same_owner)
        from formal_full_used_cold import before_after_binder
        helper._formal_bind_same_owner = before_after_binder(helper._formal_bind_same_owner)
        return helper
    m._full_used_outer_constructor = original
    m.private_original_constructor = constructor
    m._full_used_cold_proof = dict(full_domain_producer_before_first_formal_constructor=True,
        original_owner_ledger_queue_and_current_approved_SDK4_natural_chain_preserved=True,
        protected_control_only_no_financial_or_model_patch=True,
        per_track_cut_is_not_whole_cohort=True, whole_paid_restore_factory_implemented=False)
    return m


def verify_actual_formal_import_graph():
    previous = parent().verify_actual_formal_import_graph()
    m = load_private_factory()
    from formal_full_used_cold import verify_component_imports
    return dict(schema='count14-formal-full-used-domain-current-import-graph-v1', parent=previous,
        full_used_domain=m._full_used_cold_proof, component=verify_component_imports(),
        producer_owner_or_core_constructed=False, model_calls=0, Dev4=False,
        actual_cold_qualified=False)


def create_prefix_owner(bindings_path, bindings_sha256, *, code_root, factory_path, factory_manifest,
                        tester_bindings_path=None, tester_bindings_sha256=None, approved_repair_sources=()):
    global RETAINED_PARENT_NAMESPACE, RETAINED_PRIVATE_FACTORY, RETAINED_ORIGINAL_OWNER, RETAINED_ORIGINAL_LEDGER
    if RETAINED_PARENT_NAMESPACE is not None:
        raise ValueError('FULL_USED_ONE_ORIGINAL_OWNER_NO_REPLAY')
    m = parent()
    original = m.create_prefix_owner
    space = dict(vars(m), load_private_factory=load_private_factory)
    fn = FunctionType(original.__code__, space, original.__name__, original.__defaults__, original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__
    RETAINED_PARENT_NAMESPACE = space
    try:
        return fn(bindings_path, bindings_sha256, code_root=code_root, factory_path=factory_path,
            factory_manifest=factory_manifest, tester_bindings_path=tester_bindings_path,
            tester_bindings_sha256=tester_bindings_sha256, approved_repair_sources=tuple(approved_repair_sources))
    finally:
        RETAINED_PRIVATE_FACTORY = space['RETAINED_PRIVATE_FACTORY']
        RETAINED_ORIGINAL_OWNER = space['RETAINED_ORIGINAL_OWNER']
        RETAINED_ORIGINAL_LEDGER = space['RETAINED_ORIGINAL_LEDGER']
