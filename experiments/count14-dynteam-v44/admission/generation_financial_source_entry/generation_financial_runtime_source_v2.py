"""Production generation-aware ORIGINAL financial control sidecars, never RW grants.

No old file/module/method is patched. The original source and receiver guards,
fixed SQL equations, retirement, actual method/control capture and two-phase
publication remain. Explicit private ports substitute generation T inspection,
verification, pair verification and the source-birth-derived sidecar directory.
OWN is not accepted by these production entry points; no fallback is provided.
"""
from dataclasses import asdict
from pathlib import Path
from types import CodeType, FunctionType
import ast
import copy
import hashlib
import importlib
import inspect
import struct
import os
import stat
import sys
import textwrap

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
from native_peer_registry import process_birth
import normal_inert_cut as T
import metadata_inert_pair as P
import financial_runtime_source_control as F
import generation_inert_cut as G

PINS = {
    'normal_inert_cut': 'aac25e6b4f30c199a84d1ac7f5652283585f259f93a2d3f4a3e3134c9f203262',
    'metadata_inert_pair': '83b2662daef394a6c3bb9cbfa46fc15a49c4382df7db5c963ec89a1f61b853da',
    'financial_runtime_source_control': '5d7aedc421df71583d55ec6ffc32cd80389c1f944ed93c3dcad99b433d38f906',
    'generation_inert_cut': '0d23b664bf8dcfae949c11877fd3a6160d134b1a3a1bcc7f00bd2c660e0d73c5',
}
LEAF = 'normal-financial-runtime-source-generations-v1'
SCHEMA = 'count14-original-financial-control-explicit-generation-port-v1'
_CODE_CACHE = {}
_F_FUNCTIONS = ('verify_sources', '_source', '_source_storage', '_db_controls', '_bind_db',
                'capture_registered', 'publish_registered', '_complete', '_read_complete',
                'load_registered_source', '_verified', '_save', '_self_pin')
_G_FUNCTIONS = ('verify_sources', '_read_reference', '_clone_expression', '_source_key',
                'verify_ticket', 'verify_registered_pair', 'inspect_reference')


def _budget(value):
    M.need(type(value) is ReadBudget, 'GENERATION_FINANCIAL_ORIGINAL_FINITE_METADATA_BUDGET')
    value.check()


def _builtin_constants(value):
    typ = type(value)
    if typ is CodeType:
        return all(_builtin_constants(v) for v in value.co_consts)
    if typ in (type(None), bool, int, float, complex, str, bytes, type(Ellipsis)):
        return True
    if typ in (tuple, frozenset):
        return all(_builtin_constants(v) for v in value)
    return False



_CODE_FIELDS = ('co_argcount', 'co_posonlyargcount', 'co_kwonlyargcount', 'co_nlocals',
    'co_stacksize', 'co_flags', 'co_code', 'co_consts', 'co_names', 'co_varnames',
    'co_filename', 'co_name', 'co_qualname', 'co_firstlineno', 'co_linetable',
    'co_lnotab', 'co_exceptiontable', 'co_freevars', 'co_cellvars')

def _same_builtin(a, b):
    typ = type(a)
    if typ is not type(b):
        return False
    if typ is CodeType:
        fields = {name for name in dir(a) if name.startswith('co_') and not callable(getattr(a, name))}
        return fields == set(_CODE_FIELDS) and all(_same_builtin(getattr(a, name), getattr(b, name)) for name in _CODE_FIELDS)
    if typ in (type(None), type(Ellipsis)):
        return a is b
    if typ in (bool, int, str, bytes):
        return a == b
    if typ is float:
        return struct.pack('!d', a) == struct.pack('!d', b)
    if typ is complex:
        return _same_builtin(a.real, b.real) and _same_builtin(a.imag, b.imag)
    if typ is tuple:
        return len(a) == len(b) and all(_same_builtin(x, y) for x, y in zip(a, b))
    if typ is frozenset:
        remaining = list(b)
        for value in a:
            match = next((i for i, other in enumerate(remaining) if _same_builtin(value, other)), None)
            if match is None:
                return False
            remaining.pop(match)
        return not remaining
    return False


def _original_functions(module, names):
    """No callable lookalike or hostile constant equality is invoked."""
    path = Path(module.__file__)
    key = str(path), hashlib.sha256(path.read_bytes()).hexdigest()
    if key not in _CODE_CACHE:
        code = compile(path.read_bytes(), str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize)
        _CODE_CACHE[key] = {c.co_name: c for c in code.co_consts if type(c) is CodeType}
    expected = _CODE_CACHE[key]
    for name in names:
        fn = vars(module).get(name)
        M.need(type(fn) is FunctionType, 'GENERATION_FINANCIAL_EXACT_ORIGINAL_FUNCTION_TYPE')
        M.need(fn.__globals__ is vars(module) and type(fn.__module__) is str and type(module.__name__) is str
               and type(fn.__name__) is type(fn.__qualname__) is str and fn.__module__ == module.__name__
               and fn.__name__ == fn.__qualname__ == name and fn.__defaults__ is None
               and fn.__kwdefaults__ is None and fn.__closure__ is None
               and type(fn.__annotations__) is dict and not fn.__annotations__
               and type(fn.__dict__) is dict and not fn.__dict__,
               'GENERATION_FINANCIAL_ORIGINAL_FUNCTION_NAMESPACE_AND_BINDINGS')
        M.need(name in expected and type(fn.__code__) is CodeType and _builtin_constants(fn.__code__)
               and _same_builtin(fn.__code__, expected[name]),
               'GENERATION_FINANCIAL_ALL_ORIGINAL_CODE_FIELDS_UNCHANGED')


def verify_sources():
    for name, pin in PINS.items():
        module = importlib.import_module(name)
        path = Path(module.__file__)
        s = path.lstat()
        M.need(path.is_absolute() and path.resolve() == path and stat.S_ISREG(s.st_mode)
               and s.st_nlink == 1 and not s.st_mode & 0o022
               and hashlib.sha256(path.read_bytes()).hexdigest() == pin,
               'GENERATION_FINANCIAL_EXACT_FROZEN_ORIGINAL_SOURCE_PINS')
    _original_functions(F, _F_FUNCTIONS)
    _original_functions(G, _G_FUNCTIONS)
    G.verify_sources()
    F.verify_sources()
    path = Path(__file__)
    s = path.lstat()
    M.need(path.is_absolute() and path.resolve() == path and stat.S_ISREG(s.st_mode)
           and s.st_nlink == 1 and not s.st_mode & 0o022,
           'GENERATION_FINANCIAL_CANONICAL_FROZEN_SELF')
    return dict(PINS)


def _copy_function(original, replacements):
    fn = FunctionType(original.__code__, dict(original.__globals__, **replacements),
                      original.__name__, original.__defaults__, original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__
    return fn


def _source(owner, budget):
    _budget(budget)
    verify_sources()
    fn = G._clone_expression(F._source,
        'T._read_reference(ticket, own=False, read_budget=budget)',
        'generation_read(ticket, own=False, read_budget=budget)', dict(generation_read=G._read_reference))
    return fn(owner, budget)


def _generation_leaf(home, ticket, budget):
    body = G._read_reference(ticket, own=False, read_budget=budget)
    M.need(M.existing(body['owner_home'], directory=True, private=True) == home,
           'GENERATION_FINANCIAL_HOME_IS_EXACT_ORIGINAL_T_HOME')
    return home / LEAF / G._source_key(M.birth(body['old_owner_birth']))


def _ticket_reference(ticket):
    return dict(path=ticket.path, sha256=ticket.sha256, identity=M.descriptor(ticket.path))


def _validate_generation(body, home, ticket, budget):
    source = G._read_reference(ticket, own=False, read_budget=budget)
    meta = body.get('financial_generation')
    M.need(type(meta) is dict and set(meta) == {'schema', 'port_sha256', 'ticket', 'source_birth', 'parent_identity'},
           'GENERATION_FINANCIAL_COMPLETE_EXPLICIT_PORT_METADATA')
    M.need(meta['schema'] == SCHEMA and meta['port_sha256'] == hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
           and meta['ticket'] == body['original_ticket'] == _ticket_reference(ticket)
           and meta['source_birth'] == body['old_owner_birth'] == source['old_owner_birth'],
           'GENERATION_FINANCIAL_SAME_ORIGINAL_T_SOURCE_BIRTH_AND_PORT_PIN')
    parent = M.existing(meta['parent_identity'], directory=True, private=True)
    M.need(parent == home / LEAF and body['source_directory']['path'] == str(_generation_leaf(home, ticket, budget)),
           'GENERATION_FINANCIAL_EXACT_PRIVATE_PARENT_AND_GENERATION_DIRECTORY')
    budget.check()


def _read_complete(home, *, ticket, budget):
    _budget(budget)
    verify_sources()
    fn = G._clone_expression(F._read_complete, 'home / (OWN_LEAF if own else LEAF)',
        '_generation_leaf(home, _ticket, budget)', dict(_generation_leaf=_generation_leaf, _ticket=ticket))
    body, reference = fn(home, own=False, budget=budget)
    _validate_generation(body, home, ticket, budget)
    return body, reference


def _sync_original_home(home):
    # F._complete already syncs the generation parent; preserve its original
    # home sync too, before returning a reference to the original registry.
    M.existing(M.descriptor(home), directory=True, private=True)
    fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _complete_for_source(owner, budget):
    def complete(old_leaf, body, *, final_guard):
        issuer, ticket_body, _, _, _ = _source(owner, budget)
        home, ticket = owner.core.home, issuer.ticket
        current = process_birth(os.getpid())
        M.need(old_leaf == home / F.LEAF and body['OWN'] is False
               and body['original_ticket'] == _ticket_reference(ticket)
               and body['old_owner_birth'] == ticket_body['old_owner_birth'] == asdict(current),
               'GENERATION_FINANCIAL_ONLY_ACTUAL_ORIGINAL_LIVE_SOURCE_PUBLICATION')
        parent = home / LEAF
        if not os.path.lexists(parent):
            parent.mkdir(mode=0o700)
        M.existing(M.descriptor(parent), directory=True, private=True)
        value = dict(body, financial_generation=dict(schema=SCHEMA,
            port_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            ticket=_ticket_reference(ticket), source_birth=asdict(current), parent_identity=M.descriptor(parent)))
        leaf = _generation_leaf(home, ticket, budget)
        # _complete adds this identical descriptor before calling final_guard.
        def guarded_original_postcheck():
            final_guard()  # ORIGINAL source/transport/RAM/DB equality checks
            probe = dict(value, source_directory=M.descriptor(leaf))
            _validate_generation(probe, home, ticket, budget)
            verify_sources()
        result = F._complete(leaf, value, final_guard=guarded_original_postcheck)
        _sync_original_home(home)
        return result
    return complete


def publish_registered(owner, *, read_budget):
    _budget(read_budget)
    verify_sources()
    # Original publisher, real before/after capture, fixed SQL, O_EXCL and
    # shared original publication registry; no manually forged registry row.
    fn = _copy_function(F.publish_registered,
        dict(_source=_source, _complete=_complete_for_source(owner, read_budget)))
    return fn(owner, read_budget=read_budget)


def _receiver_function(ticket):
    original = ast.parse(textwrap.dedent(inspect.getsource(F.load_registered_source)))
    changes = [
        ('T.verify_inert_ticket(ticket, owner=owner, read_budget=read_budget)',
         'generation_verify(ticket, owner=owner, read_budget=read_budget, own=False)', 2),
        ('P.verify_registered_pair(owner, ticket=ticket, read_budget=read_budget)',
         'generation_pair(owner, ticket=ticket, read_budget=read_budget)', 1),
        ('T._read_reference(ticket, own=False, read_budget=read_budget)',
         'generation_read(ticket, own=False, read_budget=read_budget)', 1),
    ]
    tree = copy.deepcopy(original)
    for before, after, count in changes:
        a, b = ast.parse(before, mode='eval').body, ast.parse(after, mode='eval').body
        hits = []
        class Change(ast.NodeTransformer):
            def generic_visit(self, node):
                if ast.dump(node) == ast.dump(a):
                    hits.append(True)
                    return ast.copy_location(copy.deepcopy(b), node)
                return super().generic_visit(node)
        tree = Change().visit(tree)
        M.need(len(hits) == count, 'GENERATION_FINANCIAL_EXACT_ORIGINAL_RECEIVER_PORT_SITES')
    reverse = copy.deepcopy(tree)
    for before, after, count in reversed(changes):
        a, b = ast.parse(before, mode='eval').body, ast.parse(after, mode='eval').body
        hits = []
        class Back(ast.NodeTransformer):
            def generic_visit(self, node):
                if ast.dump(node) == ast.dump(b):
                    hits.append(True)
                    return ast.copy_location(copy.deepcopy(a), node)
                return super().generic_visit(node)
        reverse = Back().visit(reverse)
        M.need(len(hits) == count, 'GENERATION_FINANCIAL_EXACT_RECEIVER_PORT_INVERSE_COUNTS')
    M.need(ast.dump(reverse) == ast.dump(original), 'GENERATION_FINANCIAL_ALL_OTHER_RECEIVER_GUARDS_UNCHANGED')
    local = {}
    namespace = dict(F.__dict__, generation_verify=G.verify_ticket, generation_pair=G.verify_registered_pair,
        generation_read=G._read_reference,
        _read_complete=lambda home, *, own, budget: _read_complete(home, ticket=ticket, budget=budget))
    exec(compile(ast.fix_missing_locations(tree), __file__ + ':four-original-receiver-call-ports', 'exec'), namespace, local)
    return local['load_registered_source']


def load_registered_source(owner, *, ticket, read_budget):
    _budget(read_budget)
    verify_sources()
    value = _receiver_function(ticket)(owner, ticket=ticket, read_budget=read_budget)
    M.need(type(value) is F.VerifiedFinancialRuntimeSource and value.OWN is False,
           'GENERATION_FINANCIAL_ORIGINAL_VERIFIED_SOURCE_TYPE_NOT_RW_AUTHORITY')
    return value
