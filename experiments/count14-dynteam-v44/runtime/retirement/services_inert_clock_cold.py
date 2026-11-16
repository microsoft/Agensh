"""Private first-cold INERT post observer for truly retired original clocks.

Original modules/types/source pins/science shape are unchanged. Only the exact
unpublished issuer instance receives its original issue code object with one
private _post_controls binding. The post observer's sole AST delta replaces its
local clocks import with fixed capture. No global module or active source edit.
"""
from pathlib import Path
from types import FunctionType, MethodType
import ast
import copy
import hashlib
import inspect
import textwrap

from source_services_retirement import need, registered, ReadBudget

CLOCK_SHA = '395a5ad1edaf8f622f5a88d87a2cffb2bef22003bcdcb28a08b03dc9835baa29'
INERT_SHA = 'aac25e6b4f30c199a84d1ac7f5652283585f259f93a2d3f4a3e3134c9f203262'


def clone(fn, **bindings):
    value = FunctionType(fn.__code__, dict(fn.__globals__, **bindings),
                         fn.__name__, fn.__defaults__, fn.__closure__)
    value.__kwdefaults__ = fn.__kwdefaults__; return value


def pin(module, expected):
    p = Path(module.__file__)
    need(p.is_absolute() and p.resolve() == p and not p.is_symlink() and
         hashlib.sha256(p.read_bytes()).hexdigest() == expected,
         'SERVICES_INERT_EXACT_UNMODIFIED_QUALIFIED_MODULE_PIN')


def original_or_retired_projection(core, projection, read_budget):
    """RAM only: called within the original diagnostic projection RLock."""
    if not projection.closed: return True  # exact original path
    rt = registered(core)
    return type(read_budget) is ReadBudget and rt.clock_retired_RAM(projection)


def project_adapter(C):
    pin(C, CLOCK_SHA)
    tree = ast.parse(textwrap.dedent(inspect.getsource(C._project)))
    original = copy.deepcopy(tree)
    sites = [v for v in ast.walk(tree) if isinstance(v, ast.UnaryOp) and isinstance(v.op, ast.Not)
             and isinstance(v.operand, ast.Attribute) and v.operand.attr == 'closed'
             and isinstance(v.operand.value, ast.Name) and v.operand.value.id == 'projection']
    need(len(sites) == 1, 'SERVICES_INERT_ONE_ORIGINAL_NOT_CLOSED_CLOCK_GUARD')
    target = sites[0]
    replacement = ast.parse('_original_or_retired_projection(core, projection, read_budget)', mode='eval').body
    class Replace(ast.NodeTransformer):
        def visit_UnaryOp(self, node):
            return copy.deepcopy(replacement) if node is target else self.generic_visit(node)
    tree = Replace().visit(tree)
    inverse = copy.deepcopy(tree)
    class Inverse(ast.NodeTransformer):
        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id == '_original_or_retired_projection':
                return copy.deepcopy(target)
            return self.generic_visit(node)
    need(ast.dump(Inverse().visit(inverse), include_attributes=False) ==
         ast.dump(original, include_attributes=False), 'SERVICES_INERT_SINGLE_GUARD_INVERSE_ORIGINAL_AST')
    scope = dict(C._project.__globals__, _original_or_retired_projection=original_or_retired_projection)
    exec(compile(ast.fix_missing_locations(tree), C.__file__+':normal_service_clock_guard', 'exec'), scope)
    result = scope['_project']; result._single_guard_inverse_original_AST = True
    return result


def capture_adapter(C):
    project = project_adapter(C)
    original = clone(C.capture_registered, _project=project)
    def capture(owner, *, read_budget):
        rt = registered(owner.core)
        rt.observe(read_budget=read_budget)
        return original(owner, read_budget=read_budget)
    capture._project_adapter = project
    capture._original_capture_code = original.__code__
    return capture


def post_adapter(N, capture):
    pin(N, INERT_SHA)
    tree = ast.parse(textwrap.dedent(inspect.getsource(N._post_controls)))
    original = copy.deepcopy(tree)
    sites = [v for v in ast.walk(tree) if isinstance(v, ast.ImportFrom)
             and v.module == 'clock_controls_cold' and len(v.names) == 1
             and v.names[0].name == 'capture_registered' and v.names[0].asname == 'clocks']
    need(len(sites) == 1, 'SERVICES_INERT_ONE_ORIGINAL_LOCAL_CLOCK_CAPTURE_IMPORT')
    target = sites[0]
    replacement = ast.Assign(targets=[ast.Name(id='clocks', ctx=ast.Store())],
                             value=ast.Name(id='_services_clock_capture', ctx=ast.Load()))
    class Replace(ast.NodeTransformer):
        def visit_ImportFrom(self, node): return copy.deepcopy(replacement) if node is target else node
    tree = Replace().visit(tree)
    inverse = copy.deepcopy(tree)
    class Inverse(ast.NodeTransformer):
        def visit_Assign(self, node):
            if isinstance(node.value, ast.Name) and node.value.id == '_services_clock_capture':
                return copy.deepcopy(target)
            return self.generic_visit(node)
    need(ast.dump(Inverse().visit(inverse), include_attributes=False) ==
         ast.dump(original, include_attributes=False), 'SERVICES_INERT_SINGLE_IMPORT_INVERSE_ORIGINAL_POST_AST')
    scope = dict(N._post_controls.__globals__, _services_clock_capture=capture)
    exec(compile(ast.fix_missing_locations(tree), N.__file__+':normal_services_private_post_observer', 'exec'), scope)
    result = scope['_post_controls']; result._single_import_inverse_original_AST = True
    return result


def install_unpublished_issuer(issuer):
    """First-cold normal instance only; exact issuer type and issue code retained."""
    import normal_inert_cut as N
    import clock_controls_cold as C
    pin(N, INERT_SHA); pin(C, CLOCK_SHA)
    need(type(issuer) is N.NormalInertIssuer and issuer.ticket is None and not issuer.publication_started and
         issuer.issue.__func__ is N.NormalInertIssuer.issue and
         not issuer.source.requested and not issuer.source.cohort.activation_attempted,
         'SERVICES_INERT_ONLY_NEW_UNPUBLISHED_UNACTIVATED_ORIGINAL_ISSUER')
    rt = registered(issuer.core)
    need(not rt.OWN and rt.owner is issuer.owner and not rt.requested,
         'SERVICES_INERT_FIXED_NORMAL_SOURCE_REGISTRATION_BEFORE_ACTIVITY')
    post = post_adapter(N, capture_adapter(C))
    value = clone(N.NormalInertIssuer.issue, _post_controls=post)
    issuer.issue = MethodType(value, issuer)
    issuer._source_services_private_post_observer = post
    need(type(issuer) is N.NormalInertIssuer and issuer.issue.__func__.__code__ is
         N.NormalInertIssuer.issue.__code__, 'SERVICES_INERT_KEEP_ORIGINAL_ISSUER_CLASS_AND_CODE_OBJECT')
    return dict(original_issuer_type_and_issue_code_retained=True,
                post_clock_import_only_private_delta=True, clock_guard_only_private_delta=True,
                original_before_after_scientific_shape_preserved=True,
                safe_to_TERM=False, paid_activation_authorized=False, whole_runnable_ready=False)
