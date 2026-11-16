"""Private terminal/retirement selectors on the exact idle+tester cold factory."""
from pathlib import Path
from types import FunctionType
import ast,copy,hashlib,importlib.util,inspect,textwrap

IDLE_FACTORY_SHA='02844198d829ae9a1abd1bad403b0d8048ed74b09b6cb26f192272286d9ab1c5'
RETAINED_IDLE_NAMESPACE=None
RETAINED_PRIVATE_FACTORY=None
RETAINED_ORIGINAL_OWNER=None
RETAINED_ORIGINAL_LEDGER=None


def need(ok,code):
    if not ok:raise ValueError(code)


def _idle_module():
    path=Path(__file__).resolve().parents[1]/'formal100m-idle-factory-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_idle_factory.py'
    need(path.resolve()==path and not path.is_symlink() and
         hashlib.sha256(path.read_bytes()).hexdigest()==IDLE_FACTORY_SHA,
         'FORMAL_ACTUALN_EXACT_IDLE_FACTORY_SOURCE_PIN')
    spec=importlib.util.spec_from_file_location('count14_actualn_private_idle_factory',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def load_private_factory(*,tester_sources=None,tester_companion=None):
    idle=_idle_module();selector_proofs=[]
    def select_terminal_imports(tree):
        prior=copy.deepcopy(tree);edits=[]
        class Select(ast.NodeTransformer):
            def visit_ImportFrom(self,node):
                targets={
                    'formal_terminal_source':('FormalPointTerminalSource','create_actualn_source'),
                    'formal_cohort_retirement':('install_formal_retirement','install_actualn_retirement')}
                if node.module in targets:
                    old,new=targets[node.module]
                    need([(a.name,a.asname)for a in node.names]==[(old,None)],
                         'FORMAL_ACTUALN_EXACT_TWO_ORIGINAL_COLD_IMPORT_REFERENCES')
                    replacement=ast.ImportFrom(module='formal_actualn_cold',
                        names=[ast.alias(name=new,asname=old)],level=0)
                    edits.append((copy.deepcopy(node),copy.deepcopy(replacement)))
                    return replacement
                return node
        tree=Select().visit(tree)
        need(len(edits)==2,'FORMAL_ACTUALN_ONLY_SOURCE_AND_RETIREMENT_SELECTOR_COUNT')
        reverted=copy.deepcopy(tree)
        for old,new in edits:
            matches=[n for n in ast.walk(reverted)if type(n)is type(new) and
                ast.dump(n,include_attributes=False)==ast.dump(new,include_attributes=False)]
            need(len(matches)==1,'FORMAL_ACTUALN_UNIQUE_INVERSE_IMPORT_SELECTOR')
            matches[0].__dict__.update(copy.deepcopy(old.__dict__))
        need(ast.dump(reverted,include_attributes=False)==ast.dump(prior,include_attributes=False),
             'FORMAL_ACTUALN_IDLE_TESTER_OWNER_LEDGER_BODY_AST_UNCHANGED')
        selector_proofs.append(dict(selectors=2,reverse_AST_equal=True,
            idle_watchdog_and_tester_two_cold_seams_retained=True,
            original_constructor_and_owner_ledger_actions_unchanged=True))
        return ast.fix_missing_locations(tree)
    # The pinned idle loader owns the AST with its original insertion. Add a
    # compile-time selector, not another runtime bind or reconstructed body.
    from formal_public_common import clone_into,PROOFS
    idle._actualn_select_ast=select_terminal_imports
    before=len(PROOFS)
    clone_into(idle,idle.load_private_factory,
        expressions={'ast.fix_missing_locations(tree)':'_actualn_select_ast(ast.fix_missing_locations(tree))'},
        expected={'expr:ast.fix_missing_locations(tree)':1})
    module=idle.load_private_factory(tester_sources=tester_sources,tester_companion=tester_companion)
    need(len(selector_proofs)==1,'FORMAL_ACTUALN_ONE_PRIVATE_FACTORY_COMPILE')
    module._actualn_selector_proof=selector_proofs[0]
    module._actualn_loader_proof=PROOFS[before:]
    return module


def verify_actual_formal_import_graph():
    module=load_private_factory();module.verify_actual_formal_import_graph()
    from formal_actualn_cold import original_kernel_paths,original_sidecar_path,create_actualn_source,install_actualn_retirement
    from formal_nlt3_source import FormalActualNTerminalSource,FormalMixedPointEvidence,FormalTypedQueueRows
    from formal_nlt3_binding import scoped_original_close,bind_retirement_source
    from formal_nlt3_rules import load_public_rules
    from allowance_original import load_kernels
    from allowance_control import FormalAllowanceControl
    from queue_control import CarrierQueueDomain
    from formal_tester_cold import compile_prepare_one
    from native_idle_watchdog import NativeIdleWatchdog
    from native_idle_source import NativeIdleSources
    from native_idle_runtime import ActiveProjection
    kernels=load_kernels(original_kernel_paths());load_public_rules(original_sidecar_path(),kernels)
    _,tester_proof=compile_prepare_one({})
    need(callable(scoped_original_close(None,None)),'FORMAL_ACTUALN_MIXED_CLOSE_PRIVATE_AST_COMPILE')
    return dict(actual_formal_actualn_import_graph=True,owner_created=False,models=0,
        private_idle_proof=module._idle_inverse_AST_proof,
        private_actualn_selectors=module._actualn_selector_proof,
        private_actualn_loader=module._actualn_loader_proof,
        tester_two_seams_compiled=tester_proof,original_kernels_byte_pins_verified=True,
        source_ctor_control_retirement_or_dispatcher_called=False,
        actual_COMMITTED_physical_chain_qualified=False,formal_runtime_qualification=False)


def create_prefix_owner(bindings_path,bindings_sha256,*,code_root,factory_path,factory_manifest,
                        tester_bindings_path=None,tester_bindings_sha256=None):
    global RETAINED_IDLE_NAMESPACE,RETAINED_PRIVATE_FACTORY,RETAINED_ORIGINAL_OWNER,RETAINED_ORIGINAL_LEDGER
    need(RETAINED_IDLE_NAMESPACE is None,'FORMAL_ACTUALN_ONE_RETAINED_FACTORY_NO_REPLAY')
    idle=_idle_module();original=idle.create_prefix_owner
    space=dict(vars(idle),load_private_factory=load_private_factory)
    # Exact original code object and create signature, only a private loader
    # binding differs. Its companion validations and retention body are intact.
    create=FunctionType(original.__code__,space,original.__name__,original.__defaults__,original.__closure__)
    create.__kwdefaults__=original.__kwdefaults__
    RETAINED_IDLE_NAMESPACE=space
    try:
        return create(bindings_path,bindings_sha256,code_root=code_root,factory_path=factory_path,
            factory_manifest=factory_manifest,tester_bindings_path=tester_bindings_path,
            tester_bindings_sha256=tester_bindings_sha256)
    finally:
        RETAINED_PRIVATE_FACTORY=space['RETAINED_PRIVATE_FACTORY']
        RETAINED_ORIGINAL_OWNER=space['RETAINED_ORIGINAL_OWNER']
        RETAINED_ORIGINAL_LEDGER=space['RETAINED_ORIGINAL_LEDGER']
