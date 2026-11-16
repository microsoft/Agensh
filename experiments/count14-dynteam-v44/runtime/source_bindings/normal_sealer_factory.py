"""Final normal-candidate outer seam over unchanged current full-used factory."""
from pathlib import Path
from types import FunctionType
import hashlib
import importlib.util

PIN='f056dc63323492bf9c708126f815d973664df199b20ffe04a2c0fe4f4e7fa1c8'
RETAINED_PARENT_NAMESPACE=None
RETAINED_PRIVATE_FACTORY=None
RETAINED_ORIGINAL_OWNER=None
RETAINED_ORIGINAL_LEDGER=None


def parent():
    p=Path(__file__).resolve().parents[1]/'formal100m-full-used-domain-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_full_used_factory.py'
    if p.resolve()!=p or p.is_symlink()or hashlib.sha256(p.read_bytes()).hexdigest()!=PIN:
        raise ValueError('NORMAL_SEALER_CURRENT_LAST_FULLUSED_FACTORY_PIN')
    spec=importlib.util.spec_from_file_location('count14_normal_sealer_current_fullused_factory',p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def load_private_factory(*,tester_sources=None,tester_companion=None,approved_repair_sources=()):
    factory=parent().load_private_factory(tester_sources=tester_sources,tester_companion=tester_companion,
        approved_repair_sources=approved_repair_sources)
    from normal_cold_sealer_cold import install_private_factory_last
    return install_private_factory_last(factory)


def verify_actual_formal_import_graph():
    previous=parent().verify_actual_formal_import_graph()
    from normal_cold_sealer import verify_sources
    verify_sources()
    factory=load_private_factory()
    return dict(schema='count14-normal-cold-candidate-current-last-import-graph-v1',parent=previous,
        cold_sealer=factory._normal_sealer_cold_proof,owner_or_sealer_constructed=False,
        normal_handoff_authoritative=False,actual_cold_ready=False)


def create_prefix_owner(bindings_path,bindings_sha256,*,code_root,factory_path,factory_manifest,
                        tester_bindings_path=None,tester_bindings_sha256=None,approved_repair_sources=()):
    global RETAINED_PARENT_NAMESPACE,RETAINED_PRIVATE_FACTORY,RETAINED_ORIGINAL_OWNER,RETAINED_ORIGINAL_LEDGER
    if RETAINED_PARENT_NAMESPACE is not None:raise ValueError('NORMAL_SEALER_ONE_RETAINED_OWNER_NO_REPLAY')
    module=parent();original=module.create_prefix_owner
    namespace=dict(vars(module),load_private_factory=load_private_factory)
    fn=FunctionType(original.__code__,namespace,original.__name__,original.__defaults__,original.__closure__)
    fn.__kwdefaults__=original.__kwdefaults__;RETAINED_PARENT_NAMESPACE=namespace
    try:
        return fn(bindings_path,bindings_sha256,code_root=code_root,factory_path=factory_path,
            factory_manifest=factory_manifest,tester_bindings_path=tester_bindings_path,
            tester_bindings_sha256=tester_bindings_sha256,approved_repair_sources=tuple(approved_repair_sources))
    finally:
        RETAINED_PRIVATE_FACTORY=namespace['RETAINED_PRIVATE_FACTORY']
        RETAINED_ORIGINAL_OWNER=namespace['RETAINED_ORIGINAL_OWNER']
        RETAINED_ORIGINAL_LEDGER=namespace['RETAINED_ORIGINAL_LEDGER']
