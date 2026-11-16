"""Generation save port retaining the ORIGINAL registered services-clock issue.

No global or instance method is patched. Only G's class-function selector is
replaced with the exact source instance's checked original issue function.
Its code, globals and original services post/capture/project chain are verified
before use. The original source/current/six-cut/pre/post/commit guards remain.
"""
from pathlib import Path
from types import CodeType, FunctionType, MethodType
import hashlib
import importlib
import stat
import sys

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
import generation_inert_cut as G
import generation_financial_runtime_source_v2 as GF
import normal_inert_cut as T
import normal_inert_source_cold as N
import services_inert_clock_cold as SC
import clock_controls_cold as C

PINS = {
    'generation_inert_cut': '0d23b664bf8dcfae949c11877fd3a6160d134b1a3a1bcc7f00bd2c660e0d73c5',
    'generation_financial_runtime_source_v2': 'd30309aa7c29b6c61b550d9f3a463f0e33913d70bd96c2e1528d9c98e0bdc162',
    'normal_inert_source_cold': 'addd82d80c31d83a661cafc3d7a9dd9fbc8942f0cb6526b6d1e9621330ba094a',
    'services_inert_clock_cold': 'b90faf172bf7c21ade52915a5c31d058e55a692aa165465bf06eaad287f87075',
    'clock_controls_cold': '395a5ad1edaf8f622f5a88d87a2cffb2bef22003bcdcb28a08b03dc9835baa29',
}


def _function(value, expected):
    M.need(type(value) is FunctionType and type(expected) is FunctionType,
           'GENERATION_ISSUE_EXACT_FUNCTION_BEFORE_ATTRIBUTES')
    M.need(GF._builtin_constants(value.__code__)
           and GF._same_builtin(value.__code__, expected.__code__)
           and type(value.__name__) is type(value.__qualname__) is type(value.__module__) is str
           and (value.__name__, value.__qualname__, value.__module__)
               == (expected.__name__, expected.__qualname__, expected.__module__)
           and value.__defaults__ is expected.__defaults__ is None
           and value.__kwdefaults__ is expected.__kwdefaults__ is None
           and type(value.__annotations__) is dict and not value.__annotations__,
           'GENERATION_ISSUE_ALL_ORIGINAL_FUNCTION_CODE_FIELDS_AND_BINDINGS')


def _globals(actual, original, ports):
    M.need(type(actual) is dict and type(original) is dict and type(ports) is dict
           and all(type(k) is str for k in actual)
           and set(actual) == set(original) | set(ports)
           and all(actual[k] is ports[k] if k in ports else actual[k] is original[k]
                   for k in actual),
           'GENERATION_ISSUE_ONLY_EXACT_EXPLICIT_GLOBAL_PORTS')


def verify_sources():
    for name, pin in PINS.items():
        path = Path(importlib.import_module(name).__file__)
        s = path.lstat()
        M.need(path.is_absolute() and path.resolve() == path and stat.S_ISREG(s.st_mode)
               and s.st_nlink == 1 and not s.st_mode & 0o022
               and hashlib.sha256(path.read_bytes()).hexdigest() == pin,
               'GENERATION_ISSUE_FROZEN_ORIGINAL_PORT_PINS')
    GF.verify_sources()
    GF._original_functions(G, ('issue_registered', '_save', '_clone_expression', '_budget', 'verify_sources'))
    GF._original_functions(N, ('verify_sources', 'registered'))
    GF._original_functions(SC, ('clone', 'pin', 'original_or_retired_projection',
                               'project_adapter', 'capture_adapter', 'post_adapter'))
    GF._original_functions(C, ('_project', 'capture_registered'))
    GF._original_functions(T, ('_post_controls', 'verify_source_components'))
    # Validate methods against the protected source without executing it.
    source = compile(Path(T.__file__).read_bytes(), T.__file__, 'exec',
                     dont_inherit=True, optimize=sys.flags.optimize)
    cls = next(code for code in source.co_consts
               if type(code) is CodeType and code.co_name == 'NormalInertIssuer')
    methods = {code.co_name: code for code in cls.co_consts if type(code) is CodeType}
    for name in ('__init__', '_current', 'issue'):
        value = vars(T.NormalInertIssuer).get(name)
        M.need(type(value) is FunctionType and value.__globals__ is vars(T)
               and GF._builtin_constants(value.__code__)
               and GF._same_builtin(value.__code__, methods[name]),
               'GENERATION_ISSUE_ORIGINAL_ISSUER_CLASS_METHOD_CODE_AND_NAMESPACE')
    path = Path(__file__)
    s = path.lstat()
    M.need(path.is_absolute() and path.resolve() == path and stat.S_ISREG(s.st_mode)
           and s.st_nlink == 1 and not s.st_mode & 0o022,
           'GENERATION_ISSUE_CANONICAL_FROZEN_SELF')
    return dict(PINS)


def _verified_services_issue(issuer):
    """Verify but do not execute the original private services observation chain."""
    M.need(type(issuer) is T.NormalInertIssuer,
           'GENERATION_ISSUE_ORIGINAL_TYPED_ISSUER_NOT_CALLER_OBJECT')
    method = vars(issuer).get('issue')
    M.need(type(method) is MethodType and method.__self__ is issuer
           and type(method.__func__) is FunctionType,
           'GENERATION_ISSUE_EXACT_REGISTERED_SERVICES_INSTANCE_METHOD')
    fn = method.__func__
    _function(fn, T.NormalInertIssuer.issue)
    post = vars(issuer).get('_source_services_private_post_observer')
    M.need(type(post) is FunctionType and fn.__globals__.get('_post_controls') is post,
           'GENERATION_ISSUE_SAME_REGISTERED_SERVICES_POST_OBSERVER')
    _globals(fn.__globals__, vars(T), {'_post_controls': post})
    M.need(fn.__closure__ is None and not fn.__dict__,
           'GENERATION_ISSUE_ORIGINAL_ISSUE_NO_FOREIGN_CLOSURE_OR_ATTRIBUTES')
    expected_capture = SC.capture_adapter(C)
    expected_post = SC.post_adapter(T, expected_capture)
    _function(post, expected_post)
    capture = post.__globals__.get('_services_clock_capture')
    M.need(type(capture) is FunctionType and post.__closure__ is None
           and set(post.__dict__) == {'_single_import_inverse_original_AST'}
           and post.__dict__['_single_import_inverse_original_AST'] is True,
           'GENERATION_ISSUE_ORIGINAL_POST_EXACT_INVERSE_IMPORT_ONLY')
    _globals(post.__globals__, T._post_controls.__globals__,
             {'_services_clock_capture': capture, '_post_controls': post})
    _function(capture, expected_capture)
    M.need(capture.__globals__ is vars(SC) and type(capture.__closure__) is tuple
           and len(capture.__closure__) == 1 and capture.__code__.co_freevars == ('original',),
           'GENERATION_ISSUE_ORIGINAL_CAPTURE_EXACT_ONE_CLOSURE')
    original = capture.__closure__[0].cell_contents
    M.need(type(original) is FunctionType,
           'GENERATION_ISSUE_ORIGINAL_CAPTURE_FUNCTION_NOT_CALLER_CLOSURE')
    _function(original, C.capture_registered)
    project = original.__globals__.get('_project')
    M.need(type(project) is FunctionType and original.__closure__ is None and not original.__dict__
           and set(capture.__dict__) == {'_project_adapter', '_original_capture_code'}
           and capture._project_adapter is project
           and capture._original_capture_code is C.capture_registered.__code__,
           'GENERATION_ISSUE_ORIGINAL_CAPTURE_SAME_PROJECT_AND_CODE')
    _globals(original.__globals__, vars(C), {'_project': project})
    _function(project, expected_capture._project_adapter)
    M.need(project.__closure__ is None
           and set(project.__dict__) == {'_single_guard_inverse_original_AST'}
           and project.__dict__['_single_guard_inverse_original_AST'] is True,
           'GENERATION_ISSUE_ORIGINAL_PROJECT_EXACT_INVERSE_GUARD_ONLY')
    _globals(project.__globals__, C._project.__globals__,
             {'_original_or_retired_projection': SC.original_or_retired_projection, '_project': project})
    return fn


def issuer_function():
    """Original G issue AST with only its original-issue selector port changed."""
    verify_sources()
    return G._clone_expression(G.issue_registered, 'T.NormalInertIssuer.issue',
        '_verified_services_issue(issuer)', {'_verified_services_issue': _verified_services_issue})


def issue_registered(issuer, *, read_budget):
    M.need(type(read_budget) is ReadBudget, 'GENERATION_ISSUE_ORIGINAL_FINITE_METADATA_BUDGET')
    read_budget.check()
    return issuer_function()(issuer, read_budget=read_budget)
