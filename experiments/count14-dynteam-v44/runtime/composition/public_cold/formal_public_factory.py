"""Strict prospective PUBLIC bindings -> original one-owner formal cold graph.

Stdlib-only import. Actual creation reuses inverse-checked ORIGINAL constructor,
financial registration, GLM/key/header, host/network/resource and absence guards.
No host facts are invented and no existing owner/module/class is changed.
"""
from pathlib import Path
import ast
import copy
from formal_public_common import (need, sha, digest, original_module, clone_into, read_contract,
    FACTORY_SHA, BINDINGS_SCHEMA)

RETAINED_FORMAL_FACTORY = None
RETAINED_FORMAL_OWNER = None
RETAINED_FORMAL_LEDGER = None


def base_helper():
    return original_module('smoke_bootstrap_task_factory.py', FACTORY_SHA)


def base_fields(helper):
    return (set(helper.FIELDS) - {'baseline_smoke_sources'}) | {'formal_cohort_sources'}


def validate_base_bindings(helper, value, *, code_root):
    need(type(value) is dict and set(value) == base_fields(helper) and value['schema'] == BINDINGS_SCHEMA,
         'FORMAL_PUBLIC_EXACT_BASE_BINDING_FIELDS')
    read_contract(helper, value['contract'], code_root=code_root)
    projection = copy.deepcopy(value)
    projection['schema'] = 'count14-dynteam-baseline-smoke-bindings-v1'
    projection['baseline_smoke_sources'] = projection.pop('formal_cohort_sources')
    # Fresh private helper; only filename scope changes, every other original
    # source/provider/parameter/template/pin constraint still executes.
    guarded = base_helper()
    clone_into(guarded, guarded.validate_bindings,
        constants={'SMOKE_PUBLIC_CONTRACT.json': 'PRODUCTION_PUBLIC_CONTRACT.json'},
        expected={'const:SMOKE_PUBLIC_CONTRACT.json': 1})
    guarded.validate_bindings(projection, code_root=code_root)
    return value


def validate_game_sources(helper, value, *, code_root, contract):
    racing = {r['trajectory_id'] for r in contract['trajectories'] if r['arm'] == 'DYNTEAM_RACING'}
    need(type(value) is dict and set(value) == racing, 'FORMAL_THREE_EXACT_RACING_GAME_DESCRIPTORS')
    fields = {'code_directory', 'code_map_sha256', 'custodian_path', 'custodian_sha256', 'public_tool_scope'}
    scopes = {'original_v2_tool_binding_sha256', 'original_count14_catalogue_sha256',
        'native_scope_sha256', 'original_public_tools_only', 'official_evaluator_access', 'private_reference_access'}
    for t, item in value.items():
        need(type(item) is dict and set(item) == fields, 'FORMAL_EXACT_FIVE_GAME_SOURCE_FIELDS')
        for key in ('code_directory', 'custodian_path'):
            path = Path(item[key])
            need(path.is_absolute() and path.resolve() == path and path.is_relative_to(Path(code_root)) and
                 not path.is_symlink() and (path.is_dir() if key == 'code_directory' else path.is_file()),
                 'FORMAL_GAME_FROZEN_CODE_SCOPE_ONLY')
        for key in ('code_map_sha256', 'custodian_sha256'):
            helper._sha(item[key])
        scope = item['public_tool_scope']
        need(type(scope) is dict and set(scope) == scopes and scope['original_public_tools_only'] is True and
             scope['official_evaluator_access'] is scope['private_reference_access'] is False,
             'FORMAL_GAME_EXACT_PUBLIC_TOOLS_NO_ORACLE_SCOPE')
        for key in ('original_v2_tool_binding_sha256', 'original_count14_catalogue_sha256', 'native_scope_sha256'):
            helper._sha(scope[key])
    return value


def validate_bindings(helper, value, *, code_root):
    need(type(value) is dict and set(value) == base_fields(helper) | {'racing_game_sources'},
         'FORMAL_PUBLIC_EXACT_FULL_BINDING_FIELDS')
    base = {k: copy.deepcopy(v) for k, v in value.items() if k != 'racing_game_sources'}
    validate_base_bindings(helper, base, code_root=code_root)
    contract = read_contract(helper, value['contract'], code_root=code_root)
    validate_game_sources(helper, value['racing_game_sources'], code_root=code_root, contract=contract)
    return value


def private_original_constructor(bind_same_owner):
    helper = base_helper()
    def validate(value, *, code_root):
        validate_bindings(helper, value, code_root=code_root)
        projected = {k: copy.deepcopy(v) for k, v in value.items() if k != 'racing_game_sources'}
        projected['schema'] = 'count14-dynteam-baseline-smoke-bindings-v1'
        projected['baseline_smoke_sources'] = projected.pop('formal_cohort_sources')
        return projected  # private parameter view only; no saved binding rewrite
    helper.validate_bindings = validate
    helper._formal_bind_same_owner = bind_same_owner
    def transform(node):
        if (isinstance(node, ast.ImportFrom) and node.module == 'native_baseline_smoke' and
            [(a.name, a.asname) for a in node.names] == [('BaselineSmokeSources', None)]):
            return ast.ImportFrom(module='native_formal_cohort',
                names=[ast.alias(name='FormalCohortSources', asname='BaselineSmokeSources')], level=0), 'typed_formal_sources'
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and
            isinstance(node.func.value, ast.Name) and node.func.value.id == 'owner' and
            node.func.attr == 'bind_scientific_smoke'):
            value = copy.deepcopy(node)
            value.func = ast.Name(id='_formal_bind_same_owner', ctx=ast.Load())
            value.args.insert(0, ast.Name(id='owner', ctx=ast.Load()))
            return value, 'same_owner_formal_binder'
        return None
    clone_into(helper, helper.create_prefix_owner, constants={'smoke': 'production'}, transform=transform,
        expected={'const:smoke': 1, 'typed_formal_sources': 1, 'same_owner_formal_binder': 1})
    return helper


def verify_actual_formal_import_graph():
    from native_cold_owner import NativeColdOwner
    from original_relay_core import OriginalRelayCore
    from native_formal_cohort import NativeFormalCohort, FormalCohortSources
    from formal_controller import FormalFinalController
    from formal_checkpoint import create_formal_checkpoint_ports
    from native_sdk_startup_epochs import NativeSdkStartupEpochs
    from formal_terminal_source import FormalPointTerminalSource
    from formal_cohort_retirement import install_formal_retirement
    from formal_owner_factory import require_cold_sdk_epoch_hooks
    require_cold_sdk_epoch_hooks()
    return dict(actual_formal_framework_import_graph=True, owner_created=False, models=0,
                cold_SDK_restore_qualified=False, native_idle_watchdog_still_remaining=True)


def create_prefix_owner(bindings_path, bindings_sha256, *, code_root, factory_path, factory_manifest):
    global RETAINED_FORMAL_FACTORY, RETAINED_FORMAL_OWNER, RETAINED_FORMAL_LEDGER
    need(RETAINED_FORMAL_FACTORY is RETAINED_FORMAL_OWNER is RETAINED_FORMAL_LEDGER is None,
         'FORMAL_PUBLIC_ONE_ORIGINAL_OWNER_CONSTRUCTOR_NO_REPLAY')
    guard = base_helper()
    value = guard.public(bindings_path, bindings_sha256)
    need(value.get('template_only') is False, 'FORMAL_PUBLIC_DRAFT_NEVER_CREATES_OWNER')
    validate_bindings(guard, value, code_root=code_root)
    def bind_same_owner(owner, *, sources):
        from native_formal_cohort import bind_formal_cohort
        from native_racing_smoke import RacingGameSources
        from count14_public_racing_judge import PublicToolScope
        from native_sdk_startup_epochs import NativeSdkStartupEpochs
        from formal_owner_factory import require_cold_sdk_epoch_hooks
        require_cold_sdk_epoch_hooks()
        need(not hasattr(owner.core, 'native_sdk_startup_epochs'), 'FORMAL_PUBLIC_COLD_EPOCHS_ONCE')
        NativeSdkStartupEpochs(owner.core.native_kernel_tool_custody)
        games = {}
        for t, g in value['racing_game_sources'].items():
            games[t] = RacingGameSources(Path(g['code_directory']), g['code_map_sha256'],
                Path(g['custodian_path']), g['custodian_sha256'], PublicToolScope(**g['public_tool_scope']).checked())
        cohort = bind_formal_cohort(owner, sources=sources, game_sources=games)
        from formal_terminal_source import FormalPointTerminalSource
        from formal_cohort_retirement import install_formal_retirement
        install_formal_retirement(cohort, terminal_source=FormalPointTerminalSource(cohort))
        return cohort
    helper = private_original_constructor(bind_same_owner)
    RETAINED_FORMAL_FACTORY = helper  # retain namespace BEFORE original ledger/owner construction
    try:
        return helper.create_prefix_owner(bindings_path, bindings_sha256, code_root=code_root,
            factory_path=factory_path, factory_manifest=factory_manifest)
    finally:
        RETAINED_FORMAL_OWNER = helper.RETAINED_FACTORY_OWNER
        RETAINED_FORMAL_LEDGER = helper.RETAINED_FACTORY_LEDGER
