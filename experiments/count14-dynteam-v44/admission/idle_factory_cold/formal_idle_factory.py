"""ONE private cold seam in prior formal factory, no parallel owner/ledger.

Only install the already-tested native watchdog immediately after bind_cohort,
before the exact prior terminal-source/retirement calls. All original context,
source, custody, formal scope, budget/model/host/DB/source/task actions remain.
"""
from pathlib import Path
import ast
import copy
import hashlib
import importlib.util
import inspect
import textwrap

FORMAL_FACTORY_SHA='63dfe3378035a04dbc4c319b779c095439607ef82dbdd6dddab0d33751ee1db1'
RETAINED_PRIVATE_FACTORY=None
RETAINED_ORIGINAL_OWNER=None
RETAINED_ORIGINAL_LEDGER=None


def need(ok,code):
    if not ok:raise ValueError(code)


def load_private_factory(*,tester_sources=None,tester_companion=None):
    path=Path(__file__).resolve().parents[1]/'formal100m-public-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-prefix21-v1/formal_public_factory.py'
    need(path.resolve()==path and not path.is_symlink() and
         hashlib.sha256(path.read_bytes()).hexdigest()==FORMAL_FACTORY_SHA,
         'FORMAL_IDLE_ORIGINAL_FORMAL_FACTORY_SOURCE_PIN')
    spec=importlib.util.spec_from_file_location('count14_formal_private_idle_factory',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    original=module.create_prefix_owner
    prior=ast.parse(textwrap.dedent(inspect.getsource(original)));tree=copy.deepcopy(prior)
    hits=[]
    class AddOriginalIdle(ast.NodeTransformer):
        def visit_Assign(self,node):
            if (len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='cohort' and
                isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='bind_formal_cohort'):
                hits.append(node)
                call=ast.Expr(value=ast.Call(func=ast.Name(id='_cold_install_original_idle',ctx=ast.Load()),
                    args=[ast.Name(id='cohort',ctx=ast.Load()),ast.Name(id='sources',ctx=ast.Load())],keywords=[]))
                return [node,call]
            return self.generic_visit(node)
    tree=AddOriginalIdle().visit(tree)
    need(len(hits)==1,'FORMAL_IDLE_ONE_SAME_COHORT_COLD_INSTALL_SITE')
    reverted=copy.deepcopy(tree);removed=[]
    class RemoveOnlyIdle(ast.NodeTransformer):
        def visit_Expr(self,node):
            if isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='_cold_install_original_idle':
                removed.append(node);return None
            return self.generic_visit(node)
    reverted=RemoveOnlyIdle().visit(reverted)
    need(len(removed)==1 and ast.dump(reverted,include_attributes=False)==ast.dump(prior,include_attributes=False),
         'FORMAL_IDLE_ALL_OTHER_ORIGINAL_COHORT_OWNER_CONTROLLER_ACTIONS_AST_UNCHANGED')
    from formal_idle_installer import install as install_idle
    def install_components(cohort,sources):
        need(tester_sources is not None,'FORMAL_TESTER_REAL_CREATE_REQUIRES_EXPLICIT_SIX_COMPANION_SOURCES')
        from newroot_native_metadata import bind_checkpoint_consumers
        bind_checkpoint_consumers(cohort.owner) # exact original unused method BEFORE idle/Tester hooks
        idle=install_idle(cohort,sources)
        from formal_tester_cold import install as install_testers
        install_testers(cohort,sources_by_trajectory=tester_sources)
        for trajectory in cohort.tracks:
            idle.receipt(trajectory,'TESTER_BINDINGS_COMPANION',companion=tester_companion)
        return idle
    module._cold_install_original_idle=install_components
    exec(compile(ast.fix_missing_locations(tree),__file__+':one-cold-watchdog-seam','exec'),module.__dict__)
    module._idle_inverse_AST_proof=dict(original_formal_factory_sha256=FORMAL_FACTORY_SHA,
        insertion_count=1,reverse_AST_equal=True,existing_owner_or_class_or_global_changed=False,
        original_bind_then_terminal_retirement_order_retained=True)
    return module


def verify_actual_formal_import_graph():
    module=load_private_factory()
    module.verify_actual_formal_import_graph()
    from native_idle_watchdog import NativeIdleWatchdog
    from native_idle_source import NativeIdleSources
    from native_idle_runtime import ActiveProjection
    from formal_tester_public_binding import TesterPublicBindingSources, install_tester_public_bindings
    from formal_tester_cold import compile_prepare_one
    _,tester_proof=compile_prepare_one({}) # compile only: no fake owner/source/control input
    return dict(actual_formal_native_idle_import_graph=True,owner_created=False,models=0,
        private_cold_insertion_inverse_AST=module._idle_inverse_AST_proof,
        original_watchdog_factory_hook_implemented=True,tester_binding_two_cold_seams_compiled=tester_proof,
        tester_binding_module_imported_not_installed=True,
        first_formal_natural_point_K3_remaining=True,
        zero_live_without_pending_still_no_spawn=True,actual_Dev4_or_formal_qualification=False)


def create_prefix_owner(bindings_path,bindings_sha256,*,code_root,factory_path,factory_manifest,
                        tester_bindings_path=None,tester_bindings_sha256=None):
    global RETAINED_PRIVATE_FACTORY,RETAINED_ORIGINAL_OWNER,RETAINED_ORIGINAL_LEDGER
    need(RETAINED_PRIVATE_FACTORY is RETAINED_ORIGINAL_OWNER is RETAINED_ORIGINAL_LEDGER is None,
         'FORMAL_IDLE_ONE_RETAINED_ORIGINAL_FACTORY_OWNER_NO_REPLAY')
    need(tester_bindings_path is not None and tester_bindings_sha256 is not None,
         'FORMAL_TESTER_REAL_CREATE_MISSING_REQUIRED_PUBLIC_COMPANION')
    from formal_public_factory import base_helper,validate_bindings
    from formal_public_common import read_contract
    from formal_tester_cold import read_sources
    guard=base_helper();value=guard.public(bindings_path,bindings_sha256)
    need(value.get('template_only')is False,'FORMAL_TESTER_TEMPLATE_IMPORT_NEVER_CREATES_OWNER')
    validate_bindings(guard,value,code_root=code_root)
    contract=read_contract(guard,value['contract'],code_root=code_root)
    sources,companion=read_sources(path=tester_bindings_path,pin=tester_bindings_sha256,
        code_root=code_root,contract=contract)
    module=load_private_factory(tester_sources=sources,tester_companion=companion);RETAINED_PRIVATE_FACTORY=module
    try:
        return module.create_prefix_owner(bindings_path,bindings_sha256,code_root=code_root,
            factory_path=factory_path,factory_manifest=factory_manifest)
    finally:
        RETAINED_ORIGINAL_OWNER=module.RETAINED_FORMAL_OWNER
        RETAINED_ORIGINAL_LEDGER=module.RETAINED_FORMAL_LEDGER
