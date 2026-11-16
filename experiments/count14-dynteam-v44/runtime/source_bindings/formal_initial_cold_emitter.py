"""NEW formal roots only: original emitter plus RAM/exec/team-id cold seams.

No production admission, existing-owner mutation, financial rule or retry.
All original source/financial/service binders and retained partials survive.
"""
from pathlib import Path
from types import CodeType, FunctionType, ModuleType
import ast
import copy
import hashlib
import importlib.util
import inspect
import os
import stat
import textwrap

HERE = Path(__file__).resolve().parent
RAM = ('prospective-initial-ram-binding-cold-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/ram_bindings_sidecar.py',
       '3e80545f53608f5e29956447b915776f962fce800018e3dbc3ee24762449acb9')
TEAM = ('prospective-native-team-guard-cold-v1-msg237-prefix21-v1/bootstrap_team_guard_cold.py',
        '341413e34241b85e43bf81544e579d66f2d1b5a4c5cd9d19732b03610d1bf7bd')
EMITTER = ('formal100m-two-daemon-private-config-cold-wip-v3-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/emit_http_source_two_daemon_chain.py',
           'f4ad7b5bfd1707e812fe65192a660b464f7999d23ec2b8b35ea00ce5947f7535')
WRAPPERS = (
    ('formal100m-http-source-entry-wip-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/http_source_cold_chain.py',
     'eaba1e3e91ab85bf2e472cd65026082e25d59e92157fe124a233188bf7aa3903'),
    ('formal100m-kernel-control-source-entry-wip-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/kernel_source_cold_chain.py',
     'daad48586a851408991dcfe86b7bfbc3e9d7e34a59b38e6ded2d84f86e0c1aa1'),
    ('formal100m-native-control-source-entry-cold-wip-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/native_source_cold_chain.py',
     '27fd9b4eb32c432c56924ea9bf2ae4dfcec31af3bca09e8a403bcf02812a5cdd'),
    ('formal100m-services-source-cold-chain-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/services_source_cold_chain.py',
     '0a7bba3df321045b5714bba144d77f86545c1517ae219241926a6c5d8565c286'),
)
FACTORY = ('formal100m-public-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-prefix21-v1/formal_public_factory.py',
           '63dfe3378035a04dbc4c319b779c095439607ef82dbdd6dddab0d33751ee1db1')
BASE_SHA = '71de11f1bb3f778b9d4afc7ce965d18fd4f7ed9dcf49bcb6fdbf622cea9dd29f'


def need(ok, code):
    if not ok:
        raise ValueError(code)


def pin(path, expected):
    path = Path(path)
    s = path.lstat()
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink()
         and stat.S_ISREG(s.st_mode) and not s.st_mode & 0o022
         and s.st_uid in (0, os.geteuid()) and s.st_nlink == 1
         and hashlib.sha256(path.read_bytes()).hexdigest() == expected,
         'FUTURE_FORMAL_INITIAL_EXACT_FROZEN_REGULAR_SOURCE')
    return path


def load(reference):
    path = pin(HERE.parent / reference[0], reference[1])
    spec = importlib.util.spec_from_file_location('count14_future_formal_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clone(fn, namespace):
    result = FunctionType(fn.__code__, namespace, fn.__name__, fn.__defaults__, fn.__closure__)
    result.__kwdefaults__ = fn.__kwdefaults__
    return result


def code_semantics(code):
    """All executable CodeType fields, omitting only source-location metadata."""
    return (code.co_argcount, code.co_posonlyargcount, code.co_kwonlyargcount,
            code.co_nlocals, code.co_stacksize, code.co_flags, code.co_code,
            tuple(code_semantics(x) if isinstance(x, CodeType) else x for x in code.co_consts),
            code.co_names, code.co_varnames, code.co_freevars, code.co_cellvars,
            code.co_exceptiontable)


def select_new_formal_factory(factory):
    pin(factory.__file__, FACTORY[1])
    need(factory.create_prefix_owner.__globals__ is vars(factory)
         and all(value is None for name, value in vars(factory).items() if name.startswith('RETAINED_')),
         'FUTURE_FORMAL_ONLY_NEW_UNCONSTRUCTED_ORIGINAL_FACTORY')
    previous = factory.private_original_constructor
    component = load(TEAM)

    def constructor(bind_same_owner):
        helper = previous(bind_same_owner)
        pin(helper.__file__, BASE_SHA)
        original = factory.base_helper().create_prefix_owner
        tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
        counts = dict(mode=0, typed=0, binder=0)

        class OriginalFormal(ast.NodeTransformer):
            def visit_Constant(self, node):
                if type(node.value) is str and node.value == 'smoke':
                    counts['mode'] += 1
                    return ast.copy_location(ast.Constant('production'), node)
                return node

            def visit_ImportFrom(self, node):
                if node.module == 'native_baseline_smoke' and [(x.name, x.asname) for x in node.names] == [('BaselineSmokeSources', None)]:
                    counts['typed'] += 1
                    return ast.copy_location(ast.ImportFrom(module='native_formal_cohort',
                        names=[ast.alias(name='FormalCohortSources', asname='BaselineSmokeSources')], level=0), node)
                return node

            def visit_Call(self, node):
                if ast.unparse(node.func) == 'owner.bind_scientific_smoke':
                    counts['binder'] += 1
                    value = copy.deepcopy(node)
                    value.func = ast.Name(id='_formal_bind_same_owner', ctx=ast.Load())
                    value.args.insert(0, ast.Name(id='owner', ctx=ast.Load()))
                    return ast.copy_location(value, node)
                return self.generic_visit(node)

        formal = OriginalFormal().visit(tree)
        need(counts == dict(mode=1, typed=1, binder=1),
             'FUTURE_FORMAL_EXACT_ORIGINAL_FORMAL_CONSTRUCTOR_SELECTORS')
        namespace = dict(vars(helper))
        exec(compile(ast.fix_missing_locations(copy.deepcopy(formal)), __file__ + ':original-inverse', 'exec'), namespace)
        need(code_semantics(namespace['create_prefix_owner'].__code__) == code_semantics(helper.create_prefix_owner.__code__),
             'FUTURE_FORMAL_INVERSE_IS_ACTUAL_CURRENT_FULL_BINDER_HELPER_CODE')
        selected = copy.deepcopy(formal)
        sites = [n for n in ast.walk(selected) if isinstance(n, ast.Call) and ast.unparse(n.func) == 'NativeColdOwner.prepare']
        need(len(sites) == 1, 'FUTURE_FORMAL_ONE_ORIGINAL_OWNER_PREPARE_SEAM')
        sites[0].func = ast.Name(id='_future_team_executable_prepare', ctx=ast.Load())
        inverse = copy.deepcopy(selected)
        for node in ast.walk(inverse):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == '_future_team_executable_prepare':
                node.func = ast.Attribute(value=ast.Name(id='NativeColdOwner', ctx=ast.Load()), attr='prepare', ctx=ast.Load())
        need(ast.dump(inverse, include_attributes=False) == ast.dump(formal, include_attributes=False),
             'FUTURE_FORMAL_ONLY_PREPARE_CALL_EXACT_AST_INVERSE')
        helper._future_team_executable_prepare = component.prepare_new_owner
        exec(compile(ast.fix_missing_locations(selected), __file__ + ':new-prepare-only', 'exec'), vars(helper))
        need(helper.create_prefix_owner.__globals__ is vars(helper),
             'FUTURE_FORMAL_SAME_RETAINED_HELPER_BINDERS_AND_PARTIAL_NAMESPACE')
        return helper

    selected = ModuleType(factory.__name__ + '_new_initial_cold')
    selected.__dict__.update(vars(factory))
    selected.private_original_constructor = constructor
    selected.create_prefix_owner = clone(factory.create_prefix_owner, vars(selected))
    need(factory.private_original_constructor is previous
         and selected.create_prefix_owner.__code__ is factory.create_prefix_owner.__code__,
         'FUTURE_FORMAL_ORIGINAL_FACTORY_AND_CREATE_CODE_UNMODIFIED')
    return selected


def select_new_source_module(module, level=0):
    need(type(level) is int and 0 <= level < len(WRAPPERS), 'FUTURE_FORMAL_FINITE_EXACT_SOURCE_CHAIN')
    pin(module.__file__, WRAPPERS[level][1])
    need(Path(module.__file__) == HERE.parent / WRAPPERS[level][0]
         and all(value is None for name, value in vars(module).items() if name.startswith('RETAINED_')),
         'FUTURE_FORMAL_ONLY_UNCONSTRUCTED_NEW_SOURCE_MODULE')
    selected = ModuleType(module.__name__ + '_new_initial_cold')
    selected.__dict__.update(vars(module))
    if level == len(WRAPPERS) - 1:
        original_load = module.load_private_factory

        def load_selected(*args, **kwargs):
            return select_new_formal_factory(original_load(*args, **kwargs))

        selected.load_private_factory = load_selected
    else:
        original_parent = module.parent

        def parent_selected():
            return select_new_source_module(original_parent(), level + 1)

        selected.parent = parent_selected
        selected.load_private_factory = clone(module.load_private_factory, vars(selected))
    selected.create_prefix_owner = clone(module.create_prefix_owner, vars(selected))
    need(selected.create_prefix_owner.__code__ is module.create_prefix_owner.__code__,
         'FUTURE_FORMAL_ORIGINAL_SOURCE_CREATE_CODE_AND_RETAINED_STATE')
    return selected


def insert_selection(original):
    path = Path(__file__).resolve()
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    pin(path, sha)
    block = f'''_initial_cold_path=Path({str(path)!r})
_initial_cold_stat=_initial_cold_path.lstat()
if not (_initial_cold_path.resolve()==_initial_cold_path and not _initial_cold_path.is_symlink() and
        __import__('stat').S_ISREG(_initial_cold_stat.st_mode) and not _initial_cold_stat.st_mode&0o022 and
        _initial_cold_stat.st_uid in (0,__import__('os').geteuid()) and _initial_cold_stat.st_nlink==1 and
        hashlib.sha256(_initial_cold_path.read_bytes()).hexdigest()=={sha!r}):
    raise ValueError('FUTURE_FORMAL_GENERATED_INITIAL_COLD_EXTERNAL_SOURCE_PIN')
_initial_cold_spec=importlib.util.spec_from_file_location('count14_future_formal_initial_cold',_initial_cold_path)
_initial_cold=importlib.util.module_from_spec(_initial_cold_spec)
_initial_cold_spec.loader.exec_module(_initial_cold)
module=_initial_cold.select_new_source_module(module)
'''
    constants = original.__code__.co_consts
    sites = [(i, s) for i, s in enumerate(constants) if type(s) is str and
             s.startswith('# Prospective formal SAME-owner factory: import never creates owner.\n')]
    anchor = 'module.verify_actual_formal_import_graph()\n'
    need(len(sites) == 1 and sites[0][1].count(anchor) == 1,
         'FUTURE_FORMAL_ONE_GENERATED_IMPORT_SELECTION_ANCHOR')
    index, before = sites[0]
    after = before.replace(anchor, anchor + block, 1)
    need(after.replace(block, '', 1) == before, 'FUTURE_FORMAL_GENERATED_SOURCE_EXACT_BYTE_INVERSE')
    changed = list(constants)
    changed[index] = after
    code = original.__code__.replace(co_consts=tuple(changed))
    need(code.co_code == original.__code__.co_code and code.replace(co_consts=constants) == original.__code__,
         'FUTURE_FORMAL_ORIGINAL_EMITTER_CODE_ONE_CONSTANT_ONLY')
    fn = FunctionType(code, original.__globals__, original.__name__, original.__defaults__, original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__
    return fn


def emit_formal(bindings_path, bindings_sha256, *, ram_bindings_path, destination,
                tester_bindings_path=None, tester_bindings_sha256=None, new_bindings=None):
    ram = load(RAM)
    ref = ram.derive_bindings(bindings_path, bindings_sha256, destination=ram_bindings_path, scope='FORMAL_SIX')
    emitter = load(EMITTER)

    def private_emitter(**kwargs):
        value = emitter.private_emitter(**kwargs)
        value.emit = insert_selection(value.emit)
        value._idle_pin_paths = tuple(dict.fromkeys((*value._idle_pin_paths, Path(__file__).resolve(),
                                                     *(HERE.parent / r[0] for r in (RAM, TEAM)))))
        return value

    fn = clone(emitter.emit, dict(vars(emitter), private_emitter=private_emitter))
    binding = ref['bindings']
    result = fn(binding['path'], binding['sha256'], destination=destination,
                tester_bindings_path=tester_bindings_path, tester_bindings_sha256=tester_bindings_sha256,
                new_bindings=new_bindings)
    return dict(original_emission=result, prospective_RAM_binding=ref,
                actual_original_HTTP_source_and_two_daemon_emitter_used=True,
                component_sha256=TEAM[1], original_binder_chain_preserved=True,
                production_admission_or_actual_six_runtime_qualified=False,
                current_R6_or_existing_owner_modified=False)
