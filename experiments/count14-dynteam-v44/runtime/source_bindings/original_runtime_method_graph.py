"""Original method-only tails for a NEW unpublished, quarantined cold graph.

No original constructor, schema, transaction, SELECT, UPDATE, migration or
admission is called here. Existing constructors/guards are untouched. These
tails are not an activation seam: the caller must quarantine the resulting
graph before publishing it. Production RW authority is deliberately absent.
"""
import ast
import copy
import hashlib
import importlib
import inspect
from pathlib import Path
import textwrap

from common import need

PINS = {
    'native_v2_dispositions': 'ea52ad4a916008714c755471275763b2d132c225a569089a410f980988d6c199',
    'native_cohort_resources': '26d1181e98dbf9972b517c1cb621f2b16d0d84780eef9bea83ab9eca7755ebb5',
    'new_scope_ledger': '72588b3071cc23bd5453aa9d77f1ba46d4a408b87f632529f95e9c70cbf57298',
    'budget': 'a05ca90afffb7c149766cf4b74126eb94ba79910afd72049a1ff54d2bc50df8f',
    'final_queue': '7a7aeadc26ca35bdd64c6569634dab4ff6e9617ec9dee18a71ccd6797742773c',
    'model_capacity': '1df72fa17fa25159befd4fed8c5751921c60720d53212dddac57c9de283b09ba',
    'original_relay_core': '89ac900e66caa67887504522c574c1870f7a8faf51542fe248ca7f35b1541556',
    'queue_control': 'a3b01a4712d958048d58ab8c9c3ebd1e78b7143728ac0d9686532fdd4d80d382',
}


def verify_sources():
    for name,pin in PINS.items():
        path=Path(importlib.import_module(name).__file__)
        need(path.is_absolute() and path.resolve()==path and not path.is_symlink() and
             hashlib.sha256(path.read_bytes()).hexdigest()==pin,
             'STAGED_FINANCE_PINNED_ORIGINAL_RUNTIME_METHOD_SOURCES')
    return dict(PINS)


def _function(method):
    return ast.parse(textwrap.dedent(inspect.getsource(method))).body[0]


def _attribute_assignment(node,name):
    return isinstance(node,ast.Assign) and any(isinstance(t,ast.Attribute) and
        isinstance(t.value,ast.Name) and t.value.id=='self' and t.attr==name for t in node.targets)


def _compile(method,statements,args,code):
    """Compile identical selected AST nodes, not a guard-edited constructor."""
    original=copy.deepcopy(statements)
    body=ast.FunctionDef(name=method.__name__,
        args=ast.arguments(posonlyargs=[],args=[ast.arg(arg=n) for n in args],
            kwonlyargs=[],kw_defaults=[],defaults=[]),body=copy.deepcopy(statements),decorator_list=[])
    # An unpublished temporary class shell preserves each original nested
    # method's co_qualname. No constructor is called and no original class is
    # modified; semantic hashes can retain the complete closure/name graph.
    shell_name=method.__qualname__.split('.')[0]
    shell=ast.ClassDef(name=shell_name,bases=[],keywords=[],body=[body],decorator_list=[])
    tree=ast.fix_missing_locations(ast.Module(body=[shell],type_ignores=[]))
    need(ast.dump(ast.Module(body=body.body,type_ignores=[]),include_attributes=False)==
        ast.dump(ast.Module(body=original,type_ignores=[]),include_attributes=False),
        'STAGED_FINANCE_IDENTICAL_SELECTED_ORIGINAL_METHOD_AST')
    namespace={}
    exec(compile(tree,method.__code__.co_filename+':stage_method_graph_only','exec'),method.__globals__,namespace)
    proof=dict(PUBLIC_code=code,original_method=method.__qualname__,
        original_method_source_sha256=hashlib.sha256(textwrap.dedent(inspect.getsource(method)).encode()).hexdigest(),
        identical_selected_AST_sha256=hashlib.sha256(ast.dump(ast.Module(body=original,type_ignores=[]),
            include_attributes=False).encode()).hexdigest(),
        original_constructor_and_guards_unchanged=True,constructor_not_called=True)
    return getattr(namespace[shell_name],body.name),proof


def bind_original_v2_methods(dispositions,ledger):
    from native_v2_dispositions import NativeV2Dispositions
    verify_sources()
    original=_function(NativeV2Dispositions.__init__)
    guarded=original.body[-1]
    need(isinstance(guarded,ast.With),'STAGED_FINANCE_ORIGINAL_V2_ONE_GUARDED_BLOCK')
    starts=[i for i,n in enumerate(guarded.body) if _attribute_assignment(n,'raw_connection')]
    need(len(starts)==1 and _attribute_assignment(guarded.body[-1],'servers'),
         'STAGED_FINANCE_ORIGINAL_V2_METHOD_TAIL_BOUNDARIES')
    nodes=guarded.body[starts[0]:]
    need(not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and
        n.func.attr in ('schema','execute','executescript','tx') for n in nodes),
        'STAGED_FINANCE_V2_BIND_TAIL_NO_EAGER_SQL_OR_SCHEMA')
    method,proof=_compile(NativeV2Dispositions.__init__,nodes,['self','ledger'],
        'STAGED_FINANCE_ORIGINAL_V2_METHOD_TAIL_BOUND_ONLY')
    method(dispositions,ledger)
    return proof


def bind_original_resource_methods(resources,ledger):
    from native_cohort_resources import NativeCohortResources
    verify_sources()
    original=_function(NativeCohortResources.__init__)
    assignments=[n for n in original.body if _attribute_assignment(n,'original_paused') or
                 _attribute_assignment(n,'original_reserve')]
    need(len(assignments)==2,'STAGED_FINANCE_ORIGINAL_RESOURCE_PAUSED_AND_RESERVE_ASSIGNMENT')
    guarded=original.body[-1]
    need(isinstance(guarded,ast.With),'STAGED_FINANCE_ORIGINAL_RESOURCE_ONE_GUARDED_BLOCK')
    starts=[i for i,n in enumerate(guarded.body) if isinstance(n,ast.Assign) and
        any(isinstance(t,ast.Name) and t.id=='owner' for t in n.targets)]
    need(len(starts)==1,'STAGED_FINANCE_ORIGINAL_RESOURCE_BIND_TAIL_BOUNDARY')
    nodes=[*assignments,*guarded.body[starts[0]:]]
    method,proof=_compile(NativeCohortResources.__init__,nodes,['self','core'],
        'STAGED_FINANCE_ORIGINAL_RESOURCE_WRAPPER_TAIL_BOUND_ONLY')
    need(resources.ledger is ledger and resources.core.ledger is ledger,
        'STAGED_FINANCE_ONE_NEW_UNPUBLISHED_RESOURCE_LEDGER')
    method(resources,resources.core)
    return proof


def bind_original_aux_capacity_methods(resources,capacity):
    from native_cohort_resources import NativeCohortResources
    verify_sources()
    original=_function(NativeCohortResources.bind_aux_capacity)
    # Original pure compiler prefix follows the source/type guard. Skip only
    # the fresh-requests SQL block, not its constructor or any runtime guard.
    source=[i for i,n in enumerate(original.body) if isinstance(n,ast.Assign) and
        any(isinstance(t,ast.Name) and t.id=='source' for t in n.targets)]
    pin=[n for n in original.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
         and any(isinstance(a,ast.Constant) and a.value=='DYNTEAM_ORIGINAL_AUX_ACQUIRE_SOURCE_PIN'
                 for a in n.value.args)]
    starts=[i for i,n in enumerate(original.body) if isinstance(n,ast.Assign) and
        any(isinstance(t,ast.Name) and t.id=='sites' for t in n.targets)]
    need(len(source)==len(pin)==len(starts)==1,'STAGED_FINANCE_ORIGINAL_AUX_COMPILER_BOUNDARIES')
    imports=[n for n in original.body if isinstance(n,ast.ImportFrom)]
    blocks=[i for i,n in enumerate(original.body) if isinstance(n,ast.With)]
    need(len(blocks)==1 and source[0]<blocks[0]<starts[0],
        'STAGED_FINANCE_AUX_COMPILER_PURE_PREFIX_AND_SUFFIX')
    nodes=[*imports,*original.body[source[0]:blocks[0]],*original.body[starts[0]:]]
    method,proof=_compile(NativeCohortResources.bind_aux_capacity,nodes,['self','capacity'],
        'STAGED_FINANCE_ORIGINAL_AUX_GUARD_COMPILER_BOUND_ONLY')
    need(capacity.ledger is resources.ledger and not resources.capacities,
        'STAGED_FINANCE_SAME_NEW_STAGE_CAPACITY_NOT_EXISTING_OWNER')
    method(resources,capacity)
    return proof
