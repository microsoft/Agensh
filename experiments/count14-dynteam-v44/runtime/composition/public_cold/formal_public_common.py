"""Stdlib-only pinned ORIGINAL compiler guards/private inverse AST utilities."""
from pathlib import Path
import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import os
import stat
import textwrap

FACTORY_SHA = '71de11f1bb3f778b9d4afc7ce965d18fd4f7ed9dcf49bcb6fdbf622cea9dd29f'
INPUTS_SHA = 'ee70a45a74b0a4375034f1d605232a0afccf8f396e56027dc2ba2a662a7e2b5d'
CONTRACT_FILE_SHA = '9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'
CONTRACT_CANONICAL_SHA = '9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'
BINDINGS_SCHEMA = 'count14-dynteam-formal100m-bindings-v1'
LAYOUT_SCHEMA = 'count14-dynteam-formal100m-code-layout-v1'
PROOFS = []


def need(ok, code):
    if not ok:
        raise ValueError(code)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def original_module(name, expected):
    path = Path(__file__).resolve().parents[1] / 'runtime-v1-msg237-held20-v1-msg237-prefix21-v1' / name
    need(path.resolve() == path and not path.is_symlink() and sha(path) == expected,
         'FORMAL_PUBLIC_EXACT_ORIGINAL_SOURCE_PIN')
    spec = importlib.util.spec_from_file_location('count14_formal_private_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clone_into(module, function, *, constants=None, expressions=None, transform=None, expected):
    """Only a fresh private module is changed, never an imported original class."""
    constants, expressions = constants or {}, expressions or {}
    prior = ast.parse(textwrap.dedent(inspect.getsource(function)))
    tree, edits = copy.deepcopy(prior), []
    patterns = {ast.dump(ast.parse(old, mode='eval').body, include_attributes=False): (old, new)
                for old, new in expressions.items()}
    class Rewrite(ast.NodeTransformer):
        def visit(self, node):
            value = patterns.get(ast.dump(node, include_attributes=False))
            if value is not None:
                old, new = value
                replacement = ast.parse(new, mode='eval').body
                edits.append((copy.deepcopy(node), replacement, 'expr:' + old))
                return replacement
            if transform is not None:
                changed = transform(node)
                if changed is not None:
                    replacement, key = changed
                    edits.append((copy.deepcopy(node), replacement, key))
                    return replacement
            return super().visit(node)
        def visit_Constant(self, node):
            if type(node.value) is str and node.value in constants:
                replacement = ast.Constant(constants[node.value])
                edits.append((copy.deepcopy(node), replacement, 'const:' + node.value))
                return replacement
            return node
    tree = Rewrite().visit(tree)
    counts = {}
    for old, new, key in edits:
        counts[key] = counts.get(key, 0) + 1
    need(counts == expected, 'FORMAL_PUBLIC_EXACT_ENUMERATED_PRIVATE_AST_SITES')
    inverse_memo = {}
    reverted = copy.deepcopy(tree, inverse_memo)
    # Reverse in edit order: selectors are non-overlapping by construction.
    for old, new, _ in edits:
        match = inverse_memo.get(id(new))
        need(match is not None and type(match) is type(new) and
             ast.dump(match, include_attributes=False) == ast.dump(new, include_attributes=False),
             'FORMAL_PUBLIC_AVAILABLE_INVERSE_SELECTOR')
        match.__dict__.update(copy.deepcopy(old.__dict__))
    need(ast.dump(reverted, include_attributes=False) == ast.dump(prior, include_attributes=False),
         'FORMAL_PUBLIC_ALL_OTHER_ORIGINAL_ACTIONS_GUARDS_AST_UNCHANGED')
    exec(compile(ast.fix_missing_locations(tree), __file__ + ':private-original-graph', 'exec'), module.__dict__)
    PROOFS.append(dict(function=function.__module__ + '.' + function.__name__, sites=counts,
                       reverse_AST_equal=True))
    return module.__dict__[function.__name__]


def read_contract(helper, descriptor, *, code_root):
    need(type(descriptor) is dict and set(descriptor) ==
         {'directory', 'filename', 'sha256', 'index_sha256', 'canonical_sha256'} and
         descriptor['filename'] == 'PRODUCTION_PUBLIC_CONTRACT.json' and
         descriptor['sha256'] == CONTRACT_FILE_SHA and descriptor['canonical_sha256'] == CONTRACT_CANONICAL_SHA,
         'FORMAL_PUBLIC_REGISTERED_SIX_PRODUCTION_DESCRIPTOR_NOT_SMOKE')
    path = Path(descriptor['directory']) / descriptor['filename']
    need(path.is_relative_to(Path(code_root)), 'FORMAL_PUBLIC_CONTRACT_IN_FROZEN_CODE_ROOT')
    need(path.resolve() == path and not path.is_symlink(), 'FORMAL_PUBLIC_CANONICAL_CONTRACT_FILE')
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd); raw = os.read(fd, 200001); after = os.fstat(fd)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        need(stat.S_ISREG(before.st_mode) and before.st_uid in (0, os.geteuid()) and
             not before.st_mode & 0o022 and 0 < before.st_size == len(raw) <= 200000 and
             identity(before) == identity(after) == identity(path.lstat()) and
             hashlib.sha256(raw).hexdigest() == descriptor['sha256'], 'FORMAL_PUBLIC_FIXED_CONTRACT_IDENTITY_PIN')
    finally:
        os.close(fd)
    value = json.loads(raw)
    need(digest(value) == descriptor['canonical_sha256'], 'FORMAL_PUBLIC_FIXED_CONTRACT_CANONICAL_PIN')
    need(value['mode'] == 'production' and len(value['trajectories']) == 6 and
         [a['arm'] for a in value['arms']] == ['DYNTEAM', 'DYNTEAM_RACING'],
         'FORMAL_PUBLIC_EXACT_SIX_PAIRED_ORDER')
    return value


def save(path, value):
    path = Path(path)
    raw = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as out:
            out.write(raw); out.flush(); os.fsync(fd)
        os.fchmod(fd, 0o444)
    finally:
        os.close(fd)
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest())
