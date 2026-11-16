"""Strict RACING-only cold factory projection over the original prefix.

No original factory/module/global/live source is edited. The extended new
PUBLIC binding contributes only frozen Game code/scope descriptors; a private
in-memory view retains the original strict baseline binding fields/guards.
Only its final smoke binder differs. The original arms[0] owner-home selector,
NativeColdOwner, original ledger/schema/GLM/header/resource creation remain.
"""
from __future__ import annotations

from pathlib import Path
import ast
import copy
import inspect
import textwrap

import smoke_bootstrap_task_factory as original

RETAINED_RACING_FACTORY = None
RETAINED_FACTORY_OWNER = None
RETAINED_FACTORY_LEDGER = None


def _game_sources(value, code_root):
    # Called only AFTER original framework import pins installed all new cold
    # roots in their declared order; not at module import and not from cwd.
    from count14_public_racing_judge import PublicToolScope
    from native_racing_smoke import RacingGameSources
    original.require(type(value) is dict and set(value) == {'code_directory', 'code_map_sha256',
        'custodian_path', 'custodian_sha256', 'public_tool_scope'},
        'RACING_FACTORY_EXACT_FROZEN_GAME_SOURCE_FIELDS')
    root = Path(code_root)
    for key in ('code_directory', 'custodian_path'):
        path = Path(value[key])
        original.require(path.is_absolute() and path.resolve() == path and path.is_relative_to(root) and
            not path.is_symlink() and (path.is_dir() if key == 'code_directory' else path.is_file()),
            'RACING_FACTORY_ONLY_FROZEN_PACKAGE_GAME_FRAMEWORK')
    for key in ('code_map_sha256', 'custodian_sha256'):
        original._sha(value[key])
    fields = {'original_v2_tool_binding_sha256', 'original_count14_catalogue_sha256',
        'native_scope_sha256', 'original_public_tools_only', 'official_evaluator_access', 'private_reference_access'}
    scope = value['public_tool_scope']
    original.require(type(scope) is dict and set(scope) == fields,
                     'RACING_FACTORY_EXACT_PUBLIC_TOOL_SCOPE_FIELDS')
    scope = PublicToolScope(**scope).checked()
    return RacingGameSources(Path(value['code_directory']), value['code_map_sha256'],
        Path(value['custodian_path']), value['custodian_sha256'], scope)


def _racing_home(contract):
    # PUBLIC diagnostic selector only; actual original factory source below
    # retains its own original arms[0] expression byte/AST unchanged.
    original.require([arm['arm'] for arm in contract['arms']] == ['DYNTEAM', 'DYNTEAM_RACING'],
                     'RACING_FACTORY_ORIGINAL_REGISTERED_ARM_ORDER')
    return Path(contract['arms'][0]['root']) / 'owner'


def clone_original_racing_factory(*, projected_public, bind_racing):
    """One inverse-verified smoke binder, rest of actual factory original."""
    function = original.create_prefix_owner
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    before = copy.deepcopy(tree)
    sites = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and
            isinstance(node.func.value, ast.Name) and node.func.value.id == 'owner' and
            node.func.attr == 'bind_scientific_smoke'):
            sites.append((node, copy.deepcopy(node)))
            node.func = ast.Name(id='_racing_bind_same_owner_smoke', ctx=ast.Load())
            node.args.insert(0, ast.Name(id='owner', ctx=ast.Load()))
    original.require(len(sites) == 1, 'RACING_FACTORY_ONE_EXACT_SMOKE_BINDER_SITE')
    restored = copy.deepcopy(tree)
    for target, old in sites:
        matches = [node for node in ast.walk(restored) if type(node) is type(target) and
            ast.dump(node, include_attributes=False) == ast.dump(target, include_attributes=False)]
        original.require(len(matches) == 1, 'RACING_FACTORY_UNIQUE_INVERSE_SELECTOR')
        matches[0].__dict__.update(copy.deepcopy(old.__dict__))
    original.require(ast.dump(restored, include_attributes=False) == ast.dump(before, include_attributes=False),
        'RACING_FACTORY_ORIGINAL_PREFIX_NO_MODEL_LEDGER_OR_CAPACITY_DELTA')
    namespace = dict(function.__globals__, public=projected_public,
        _racing_bind_same_owner_smoke=bind_racing,
        RETAINED_FACTORY_OWNER=None, RETAINED_FACTORY_LEDGER=None)
    exec(compile(ast.fix_missing_locations(tree), __file__ + ':original-factory-arm-binding', 'exec'), namespace)
    return namespace['create_prefix_owner'], namespace


def verify_actual_racing_import_graph():
    """Side-effect-free imports only; no owner, source/task or model work."""
    original.verify_actual_import_graph()
    from native_racing_smoke import NativeRacingSmoke, RacingGameSources
    from formal_count14_tester import FormalCount14Tester
    from native_racing_shared_tests import RacingSharedPublicTests
    from native_scientific_host_checkpoint import ScientificHostCheckpoint
    from smoke_racing_tools_game_manager import NativeRacingGameManager
    from native_sdk_startup_epochs import NativeSdkStartupEpochs
    from native_racing_smoke_retirement import RacingRetirementCustody
    return dict(actual_racing_framework_import_graph=True, owner_created=False, models=0)


def create_racing_prefix_owner(bindings_path, bindings_sha256, *, code_root, factory_path, factory_manifest):
    global RETAINED_RACING_FACTORY, RETAINED_FACTORY_OWNER, RETAINED_FACTORY_LEDGER
    original.require(RETAINED_RACING_FACTORY is None and RETAINED_FACTORY_OWNER is None and
        RETAINED_FACTORY_LEDGER is None, 'RACING_FACTORY_UNIQUE_COLD_OWNER_NO_REPLAY')
    binding = original.public(bindings_path, bindings_sha256)
    original.require(type(binding) is dict and set(binding) == original.FIELDS | {'racing_game_sources'} and
        binding['schema'] == 'count14-dynteam-racing-smoke-bindings-v1' and
        binding['template_only'] is False, 'RACING_FACTORY_EXACT_NEW_RACING_BINDING_NOT_BASELINE')
    # This projection is not a ledger/contract/schema rewrite: it is only the
    # original factory's PUBLIC deployment parameter view, never persisted over
    # its input file. Scientific contract/rosters/pins/arguments are unchanged.
    projected = {key: copy.deepcopy(value) for key, value in binding.items() if key != 'racing_game_sources'}
    projected['schema'] = 'count14-dynteam-baseline-smoke-bindings-v1'
    original.validate_bindings(projected, code_root=code_root)
    expected_path, expected_sha = Path(bindings_path), bindings_sha256

    def projected_public(path, pin, maximum=1048576):
        value = original.public(path, pin, maximum)
        if Path(path) == expected_path and pin == expected_sha:
            original.require(value == binding, 'RACING_FACTORY_PUBLIC_BINDING_STILL_EXACT')
            return copy.deepcopy(projected)
        return value

    def bind_same_owner(owner, *, sources):
        # Original factory calls this only after custody.bind(core), so all
        # retained native components are the very same objects. SDK epoch cold
        # installers must already be in the pinned prefix used to create core.
        from native_racing_smoke import bind_racing_smoke
        from native_sdk_startup_epochs import NativeSdkStartupEpochs
        custody = owner.core.native_kernel_tool_custody
        original.require(not hasattr(owner.core, 'native_sdk_startup_epochs'),
                         'RACING_FACTORY_COLD_EPOCH_INSTALL_EXACTLY_ONCE')
        NativeSdkStartupEpochs(custody)
        game = _game_sources(binding['racing_game_sources'], code_root)
        return bind_racing_smoke(owner, sources=sources, game_sources=game)

    create, namespace = clone_original_racing_factory(projected_public=projected_public,
                                                      bind_racing=bind_same_owner)
    # Retain namespace BEFORE first ledger construction/child, even on failure.
    RETAINED_RACING_FACTORY = namespace
    try:
        return create(bindings_path, bindings_sha256, code_root=code_root,
                      factory_path=factory_path, factory_manifest=factory_manifest)
    finally:
        RETAINED_FACTORY_OWNER = namespace['RETAINED_FACTORY_OWNER']
        RETAINED_FACTORY_LEDGER = namespace['RETAINED_FACTORY_LEDGER']
