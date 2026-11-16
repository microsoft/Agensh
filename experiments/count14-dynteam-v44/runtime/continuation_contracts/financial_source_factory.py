"""Current original cold factory, then explicit financial control publication."""
from pathlib import Path
from types import FunctionType
import hashlib
import importlib.util

PIN = '86b2e37752e7e94c9eaf3d4f111b57c32190b964efea782df8c9f0c43f2a7551'
RETAINED_PARENT_NAMESPACE = None
RETAINED_PRIVATE_FACTORY = None
RETAINED_ORIGINAL_OWNER = None
RETAINED_ORIGINAL_LEDGER = None


def parent():
    path = Path(__file__).resolve().parents[1] / 'formal100m-normal-inert-source-cold-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/normal_inert_source_factory.py'
    if path.resolve() != path or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != PIN:
        raise ValueError('FINANCIAL_SOURCE_CURRENT_ORIGINAL_FACTORY_PIN')
    spec = importlib.util.spec_from_file_location('count14_financial_source_parent_factory', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def load_private_factory(*, tester_sources=None, tester_companion=None, approved_repair_sources=()):
    factory = parent().load_private_factory(tester_sources=tester_sources,
        tester_companion=tester_companion, approved_repair_sources=approved_repair_sources)
    from financial_source_cold import install_private_factory_last
    return install_private_factory_last(factory)


def verify_actual_formal_import_graph():
    previous = parent().verify_actual_formal_import_graph()
    factory = load_private_factory()
    return dict(schema='count14-financial-source-cold-import-graph-v1', parent=previous,
        financial_source=factory._financial_source_cold_proof,
        source_issuer=factory._normal_inert_source_cold_proof,
        original_owner_constructed=False, actual_production_six_runtime_qualified=False,
        safe_to_TERM=False, whole_runnable_ready=False, paid_activation_authorized=False)


def create_prefix_owner(bindings_path, bindings_sha256, *, code_root, factory_path, factory_manifest,
                        tester_bindings_path=None, tester_bindings_sha256=None, approved_repair_sources=()):
    global RETAINED_PARENT_NAMESPACE, RETAINED_PRIVATE_FACTORY, RETAINED_ORIGINAL_OWNER, RETAINED_ORIGINAL_LEDGER
    if RETAINED_PARENT_NAMESPACE is not None:
        raise ValueError('FINANCIAL_SOURCE_SINGLE_RETAINED_OWNER_NO_REPLAY')
    module = parent(); original = module.create_prefix_owner
    namespace = dict(vars(module), load_private_factory=load_private_factory)
    fn = FunctionType(original.__code__, namespace, original.__name__, original.__defaults__, original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__; RETAINED_PARENT_NAMESPACE = namespace
    try:
        return fn(bindings_path, bindings_sha256, code_root=code_root, factory_path=factory_path,
            factory_manifest=factory_manifest, tester_bindings_path=tester_bindings_path,
            tester_bindings_sha256=tester_bindings_sha256, approved_repair_sources=tuple(approved_repair_sources))
    finally:
        RETAINED_PRIVATE_FACTORY = namespace['RETAINED_PRIVATE_FACTORY']
        RETAINED_ORIGINAL_OWNER = namespace['RETAINED_ORIGINAL_OWNER']
        RETAINED_ORIGINAL_LEDGER = namespace['RETAINED_ORIGINAL_LEDGER']
