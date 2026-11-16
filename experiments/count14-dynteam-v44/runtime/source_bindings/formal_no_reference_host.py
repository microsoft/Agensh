"""NEW formal public-Tester host binding, never a reference executable.

Original helper/owner/model/ledger/budget code is unchanged. The NEW private
environment compiler admits the already-registered no-reference production
case, retains original smoke and actual-wrapper cases, and does not mislabel
formal as smoke-only. All actual six-Tester binding/activation gates remain.
"""
from pathlib import Path
from types import CodeType, FunctionType
import ast
import copy
import hashlib
import importlib.util
import inspect
import os
import stat
import textwrap

HERE = Path(__file__).resolve().parent
FORMAL = ('prospective-formal-ram-team-exec-emitter-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_initial_cold_emitter.py',
          '996a3e31eff49c22b6acd3db55efd357863baa4e13c7bf0eda40444a881a4450')
TEAM = ('prospective-native-team-guard-cold-v1-msg237-prefix21-v1/bootstrap_team_guard_cold.py',
        '341413e34241b85e43bf81544e579d66f2d1b5a4c5cd9d19732b03610d1bf7bd')
PRODUCTION_CONTRACT = '9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'


def need(ok, code):
    if not ok:
        raise ValueError(code)


def load(reference):
    path = HERE.parent / reference[0]
    s = path.lstat()
    need(path.resolve() == path and not path.is_symlink() and stat.S_ISREG(s.st_mode) and
         s.st_uid in (0, os.geteuid()) and s.st_nlink == 1 and not s.st_mode & 0o022 and
         hashlib.sha256(path.read_bytes()).hexdigest() == reference[1],
         'FORMAL_NO_REFERENCE_EXACT_FROZEN_NEW_COMPONENT')
    spec = importlib.util.spec_from_file_location('count14_formal_no_reference_' + path.stem, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def eligible(core, facts):
    """Existing typed held owner; actual production pins remain mandatory."""
    from original_relay_core import OriginalRelayCore
    from native_host_environment import NativeHostFacts
    from common import digest
    need(type(core) is OriginalRelayCore and type(facts) is NativeHostFacts,
         'FORMAL_NO_REFERENCE_ORIGINAL_TYPED_CORE_AND_FACTS')
    if core.contract.get('mode') != 'production' or facts.opaque_task_executable is not None or facts.opaque_task_binding_sha256 is not None:
        return False  # original smoke or actual-wrapper behavior, not a bypass
    need(type(core.qualification_only) is bool and not core.closed and not core.scientific_activation_qualified and
         core.state == 'ORIGINAL_TRANSPORT_HELD_NATIVE_BINDINGS_PENDING' and
         set(core.gate.startup_held) == set(core.rows), 'FORMAL_NO_REFERENCE_ONLY_NEW_SIX_HELD_CORE')
    contract = core.contract
    need(contract.get('schema') == 'count14-dynteam-two-arm-public-contract-v1' and len(core.rows) == 6 and
         {(r['arm'], r['block']) for r in core.rows.values()} ==
         {(arm, b) for arm in ('DYNTEAM', 'DYNTEAM_RACING') for b in (1, 2, 3)} and
         all(r['search_tokens'] == 100000000 and r['request_cap'] == 13 and
             r['checkpoints_tokens'] == [10000000, 20000000, 50000000, 100000000] for r in core.rows.values()) and
         all(core.rows[r['trajectory_id']] is r for r in contract['trajectories']),
         'FORMAL_NO_REFERENCE_SAME_REGISTERED_PAIRED100M_GRID')
    if core.qualification_only:
        # ORIGINAL core/ledger already require an explicit OWN home and OWN
        # qualification ledger. This preserves that existing test domain;
        # it is not allowed to become a production activation proof.
        need(any(p.startswith('OWN-') for p in Path(core.home).parts) and
             getattr(core.ledger, '_dynteam_qualification_only', None) is True,
             'FORMAL_NO_REFERENCE_ORIGINAL_OWN_DOMAIN_REMAINS_NONPRODUCTION')
    else:
        need(digest(contract) == PRODUCTION_CONTRACT and
             getattr(core.ledger, '_dynteam_qualification_only', None) is False and
             core.ledger._dynteam_frozen_directory_proof.canonical_contract_sha256 == PRODUCTION_CONTRACT,
             'FORMAL_NO_REFERENCE_REAL_FROZEN_PRODUCTION_CONTRACT_NOT_OWN')
    return True


def code_semantics(code):
    return (code.co_argcount, code.co_posonlyargcount, code.co_kwonlyargcount, code.co_nlocals,
            code.co_stacksize, code.co_flags, code.co_code,
            tuple(code_semantics(v) if isinstance(v, CodeType) else v for v in code.co_consts),
            code.co_names, code.co_varnames, code.co_freevars, code.co_cellvars, code.co_exceptiontable)


def compiled_environment():
    import native_host_environment as original
    team = load(TEAM)
    executable = team.executable()
    executable.pin(original, executable.ENV_SHA)
    baseline, inherited_proof = team.compiled_environment()
    tree = ast.parse(textwrap.dedent(inspect.getsource(original.prepare)))
    sites = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and
             isinstance(n.func, ast.Name) and n.func.id == 'bootstrap_overlay']
    need(len(sites) == 1, 'FORMAL_NO_REFERENCE_ORIGINAL_ONE_EXEC_TEAM_BOOTSTRAP_SITE')
    sites[0].func.id = '_cold_executable_bootstrap_overlay'
    namespace = dict(baseline.__globals__)
    exec(compile(ast.fix_missing_locations(copy.deepcopy(tree)), __file__ + ':original-team-inverse', 'exec'), namespace)
    need(code_semantics(namespace['prepare'].__code__) == code_semantics(baseline.__code__),
         'FORMAL_NO_REFERENCE_EXACT_ACTUAL_TEAM_ENVIRONMENT_CODE_INVERSE')
    before = copy.deepcopy(tree)
    changes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'initial_only':
            expected = "core.contract.get('mode') == 'smoke' and facts.opaque_task_executable is None and facts.opaque_task_binding_sha256 is None"
            need(ast.dump(node.value, include_attributes=False) == ast.dump(ast.parse(expected, mode='eval').body, include_attributes=False),
                 'FORMAL_NO_REFERENCE_ORIGINAL_EXACT_NONE_PAIR_GUARD')
            old = copy.deepcopy(node)
            node.value = ast.BoolOp(op=ast.Or(), values=[node.value, ast.parse('_formal_no_reference_eligible(core,facts)', mode='eval').body])
            changes.append((node, old))
        elif isinstance(node, ast.keyword) and node.arg == 'smoke_initial_tester_only_no_reference_ABI_claim':
            need(isinstance(node.value, ast.Name) and node.value.id == 'initial_only',
                 'FORMAL_NO_REFERENCE_ORIGINAL_EXACT_SMOKE_ONLY_METADATA')
            old = copy.deepcopy(node)
            node.value = ast.parse("initial_only and core.contract.get('mode') == 'smoke'", mode='eval').body
            changes.append((node, old))
    need(len(changes) == 2, 'FORMAL_NO_REFERENCE_ONLY_NONE_PAIR_AND_TRUTHFUL_SMOKE_METADATA_TWO_SITES')
    inverse = copy.deepcopy(tree)
    for current, old in changes:
        matches = [n for n in ast.walk(inverse) if type(n) is type(current) and
                   ast.dump(n, include_attributes=False) == ast.dump(current, include_attributes=False)]
        need(len(matches) == 1, 'FORMAL_NO_REFERENCE_UNIQUE_INVERSE_SELECTOR')
        matches[0].__dict__.update(copy.deepcopy(old.__dict__))
    need(ast.dump(inverse, include_attributes=False) == ast.dump(before, include_attributes=False),
         'FORMAL_NO_REFERENCE_ALL_OTHER_HOST_AND_PRIVATE_ENV_ACTIONS_AST_UNCHANGED')
    namespace = dict(baseline.__globals__, _formal_no_reference_eligible=eligible)
    exec(compile(ast.fix_missing_locations(tree), __file__ + ':two-private-host-sites', 'exec'), namespace)
    return namespace['prepare'], dict(original_team_proof=inherited_proof, formal_host_sites=2,
        original_environment_inverse_all_executable_CodeType_fields=True, two_site_inverse_AST=True,
        no_reference_executable_or_PBENCH_BIN_invented=True, original_smoke_and_existing_wrapper_paths_retained=True,
        new_production_None_pair_does_not_claim_smoke_only=True,
        actual_six_public_tester_bindings_and_all_original_activation_gates_still_required=True)


def prepare_new_owner(**kwargs):
    import native_cold_owner as original
    team = load(TEAM)
    executable = team.executable()
    executable.pin(original, executable.OWNER_SHA)
    fn = original.NativeColdOwner.prepare.__func__
    executable.inspect.signature(fn).bind(original.NativeColdOwner, **kwargs)
    environment, _ = compiled_environment()
    selected = FunctionType(fn.__code__, dict(fn.__globals__, prepare_environment=environment),
                            fn.__name__, fn.__defaults__, fn.__closure__)
    selected.__kwdefaults__ = fn.__kwdefaults__
    need(original.NativeColdOwner.prepare.__func__ is fn, 'FORMAL_NO_REFERENCE_ORIGINAL_OWNER_CLASS_UNCHANGED')
    return selected(original.NativeColdOwner, **kwargs)


def select_new_formal_factory(factory):
    old = load(FORMAL)
    selected = old.select_new_formal_factory(factory)
    previous = selected.private_original_constructor
    def constructor(bind_same_owner):
        helper = previous(bind_same_owner)
        original = helper._future_team_executable_prepare
        need(hashlib.sha256(Path(original.__globals__['__file__']).read_bytes()).hexdigest() == TEAM[1],
             'FORMAL_NO_REFERENCE_EXACT_EXISTING_FORMAL_PREPARE_INPUT')
        helper._future_team_executable_prepare = prepare_new_owner
        return helper
    selected.private_original_constructor = constructor
    return selected


def select_new_source_module(module, level=0):
    old = load(FORMAL)
    function = FunctionType(old.select_new_source_module.__code__, dict(vars(old),
        select_new_formal_factory=select_new_formal_factory, select_new_source_module=select_new_source_module),
        old.select_new_source_module.__name__, old.select_new_source_module.__defaults__, old.select_new_source_module.__closure__)
    function.__kwdefaults__ = old.select_new_source_module.__kwdefaults__
    return function(module, level)


def insert_selection(original):
    old = load(FORMAL)
    selected = old.insert_selection(original)
    before = selected.__code__
    constants = list(before.co_consts)
    candidates = [(i, s) for i, s in enumerate(constants) if type(s) is str and
                  s.startswith('# Prospective formal SAME-owner factory: import never creates owner.\n')]
    need(len(candidates) == 1, 'FORMAL_NO_REFERENCE_ONE_GENERATED_SELECTION_SOURCE')
    index, text = candidates[0]
    old_path, new_path = str(Path(old.__file__).resolve()), str(Path(__file__).resolve())
    old_sha, new_sha = FORMAL[1], hashlib.sha256(Path(new_path).read_bytes()).hexdigest()
    need(text.count(old_path) == text.count(old_sha) == 1, 'FORMAL_NO_REFERENCE_ONLY_SELECTION_MODULE_PATH_SHA_PAIR')
    changed = text.replace(old_path, new_path, 1).replace(old_sha, new_sha, 1)
    need(changed.replace(new_path, old_path, 1).replace(new_sha, old_sha, 1) == text,
         'FORMAL_NO_REFERENCE_GENERATED_PATH_SHA_EXACT_BYTE_INVERSE')
    constants[index] = changed
    code = before.replace(co_consts=tuple(constants))
    need(code.co_code == before.co_code and code.replace(co_consts=before.co_consts) == before,
         'FORMAL_NO_REFERENCE_EMITTER_CODE_AND_ALL_OTHER_CONSTANTS_UNCHANGED')
    result = FunctionType(code, selected.__globals__, selected.__name__, selected.__defaults__, selected.__closure__)
    result.__kwdefaults__ = selected.__kwdefaults__
    return result


def emit_formal(*args, **kwargs):
    old = load(FORMAL)
    fn = old.emit_formal
    selected = FunctionType(fn.__code__, dict(vars(old), insert_selection=insert_selection, __file__=str(Path(__file__).resolve())),
                            fn.__name__, fn.__defaults__, fn.__closure__)
    selected.__kwdefaults__ = fn.__kwdefaults__
    return selected(*args, **kwargs)
