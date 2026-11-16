"""Private reversible infrastructure AST scopes; never mutate original objects."""
import ast
import copy
import hashlib
import inspect
import textwrap
from types import FunctionType
from common import need

PROOFS = []


def globals_clone(function, **bindings):
    value = FunctionType(function.__code__, dict(function.__globals__, **bindings),
                         function.__name__, function.__defaults__, function.__closure__)
    value.__kwdefaults__ = function.__kwdefaults__
    value._formal_original_code_identical = value.__code__ is function.__code__
    return value


class Edits:
    def __init__(self):self.counts = {}
    def replace(self, node, value, kind):
        value = copy.deepcopy(value)
        value._formal_inverse_original = copy.deepcopy(node)
        self.counts[kind] = self.counts.get(kind, 0) + 1
        return ast.copy_location(value, node)


def reversible(function, transformer, *, expected, bindings=None, filename=None):
    source = textwrap.dedent(inspect.getsource(function));original = ast.parse(source)
    edits = Edits();changed = transformer(edits).visit(copy.deepcopy(original))
    need(edits.counts == expected, 'FORMAL_EXACT_ENUM_IDENTITY_AST_SITES')
    class Reverse(ast.NodeTransformer):
        def visit(self, node):
            if hasattr(node, '_formal_inverse_original'):
                return copy.deepcopy(node._formal_inverse_original)
            return super().visit(node)
    restored = Reverse().visit(copy.deepcopy(changed))
    equal = ast.dump(restored, include_attributes=False) == ast.dump(original, include_attributes=False)
    need(equal, 'FORMAL_ORIGINAL_METHOD_REVERSE_AST_EXACT')
    namespace = {}
    exec(compile(ast.fix_missing_locations(changed), filename or inspect.getsourcefile(function), 'exec'),
         dict(function.__globals__, **(bindings or {})), namespace)
    value = namespace[function.__name__]
    proof = {'function': function.__module__+'.'+function.__qualname__,
        'original_source_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'edit_sites': dict(edits.counts), 'reverse_AST_equal': equal}
    value._formal_inverse_AST_proof = proof;PROOFS.append(proof)
    return value


def infrastructure_transform(*, constants=None, attributes=None):
    constants, attributes = constants or {}, attributes or {}
    class Transform(ast.NodeTransformer):
        def __init__(self, edits):self.edits = edits
        def visit_Constant(self, node):
            if type(node.value) is str and node.value in constants:
                return self.edits.replace(node, ast.Constant(constants[node.value]), 'constant:'+node.value)
            return node
        def visit_Attribute(self, node):
            if node.attr in attributes:
                changed=copy.deepcopy(node);changed.attr=attributes[node.attr]
                return self.edits.replace(node, changed, 'attribute:'+node.attr)
            return self.generic_visit(node)
    return Transform
