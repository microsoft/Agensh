#!/usr/bin/env python3
"""Formal fresh-only UID cold leaf, WIP and not production qualification.

The original exact six-track selector, shared environment, full-framework copy,
and aggregate remain unchanged. No empty-partial or retry exception is included.
"""
from pathlib import Path
from types import FunctionType
import hashlib
import importlib.util

HERE = Path(__file__).resolve().parent
PARENT_SHA256 = '96e38367a88d566704218cc202da52148b4206d5d36683411198221e7ef69f08'
ASSET_HELPER_SHA256 = '39cf73bac3848bc484079204b65f5a1ef1332af8835f6f1e083159dbe9a83322'
NATIVE_HELPER_SHA256 = 'e0ee160532c8b074207c8f8607e7f9bcc4025ea95e01821ca4e5482a85441e4a'


def need(ok, code):
    if not ok:
        raise ValueError(code)


def load(path, pin, name):
    path = Path(path)
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink()
         and hashlib.sha256(path.read_bytes()).hexdigest() == pin,
         'FORMAL_UID_EXACT_COLD_FRAMEWORK_SOURCE_PIN')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


FORMAL = load(HERE.parent / 'formal100m-deploy-wip-v1-msg237-held20-v1/formal_deploy.py', PARENT_SHA256,
              '_formal_uid_original_deployment')
ASSET_HELPER = load(HERE / 'stage_exact_runtime_uid_v1.py', ASSET_HELPER_SHA256,
                    '_formal_uid_original_three_asset_helper')
NATIVE_HELPER = load(HERE / 'native_pinned_source_uid_v1.py', NATIVE_HELPER_SHA256,
                     '_formal_uid_original_native_source_helper')


def formal_native_builder():
    """One exact private mode selector; full formal raw/canonical guard is outside."""
    original = NATIVE_HELPER.build_stager
    before = original.__code__; constants = before.co_consts
    need(sum(type(x) is str and x == 'smoke' for x in constants) == 1,
         'FORMAL_UID_ONE_NATIVE_HELPER_MODE_SELECTOR')
    after_constants = tuple('production' if type(x) is str and x == 'smoke' else x for x in constants)
    after = before.replace(co_consts=after_constants)
    need(after.co_code == before.co_code and after.replace(co_consts=constants) == before,
         'FORMAL_UID_NATIVE_SELECTOR_CODE_INVERSE')
    fn = FunctionType(after, original.__globals__, original.__name__, original.__defaults__, original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__
    return fn


def compile_three_stage(current, assets, selected_sources, home):
    """Reuse verified exact source_stat and the single fresh-mkdir AST delta."""
    need(current.__code__ is assets.stage_three.__code__,
         'FORMAL_UID_CURRENT_THREE_STAGE_ONLY_PRIVATE_GLOBAL_CHANGES')
    stat_fn = lambda p: ASSET_HELPER.exact_source_stat(p, selected_sources, assets.source_stat)
    validate = FORMAL.clone(assets.validate_source, source_stat=stat_fn)
    scope = dict(current.__globals__, source_stat=stat_fn, validate_source=validate,
                 _create_exact_assets_home=lambda p: ASSET_HELPER.create_exact_home(p, home))
    raw = Path(assets.__file__).read_bytes()
    need(hashlib.sha256(raw).hexdigest() == ASSET_HELPER.ORIGINAL_ASSETS_SHA256,
         'FORMAL_UID_ORIGINAL_THREE_STAGE_SOURCE_PIN')
    exec(compile(ASSET_HELPER.mkdir_delta(raw), str(assets.__file__) + ':formal_uid_fresh_parent_only', 'exec'), scope)
    return scope['stage_three']


def selectors(stager, a, trajectory):
    need(a.trajectory == trajectory, 'FORMAL_UID_SAME_EXPLICIT_TRACK_NO_DEFAULT')
    contract = FORMAL.registered(stager, a.contract, a.contract_sha256)
    row = FORMAL.selected(contract, trajectory)
    return contract, row, Path(row['root']) / 'approved-final-runtime-assets-v1'


def stage_sources(stager, assets, a, contract, row):
    """PUBLIC source projection only, same fixed three physical identities."""
    metadata = stager.public(a.public_sources, a.public_sources_sha256)
    need(metadata.get('contract_sha256') == stager.digest(contract)
         and metadata.get('trajectory') == row['trajectory_id']
         and type(metadata.get('assets')) is dict
         and set(metadata['assets']) == set(ASSET_HELPER.EXACT_SOURCE_INODES),
         'FORMAL_UID_EXACT_THREE_PUBLIC_SOURCES_SAME_FORMAL_TRACK')
    selected = {Path(value['path']): name for name, value in metadata['assets'].items()}
    need(len(selected) == 3, 'FORMAL_UID_THREE_DISTINCT_EXACT_SOURCE_PATHS')
    return selected


def adapters(runtime, *, trajectory, shared_env=None):
    stager, assets, current_stage, current_deploy, fullcopy = FORMAL.adapters(
        runtime, trajectory=trajectory, shared_env=shared_env)
    # Compile both cold deltas at import verification without creating assets.
    compile_three_stage(current_stage, assets, {}, Path('/OWN-NO-ACTION'))
    native_builder = formal_native_builder()

    def stage_three(a):
        contract, row, home = selectors(stager, a, trajectory)
        selected = stage_sources(stager, assets, a, contract, row)
        return compile_three_stage(current_stage, assets, selected, home)(a)

    def deploy_with_staged(a):
        selectors(stager, a, trajectory)
        # Original complete provenance check runs before finite native selection.
        old_factory = current_deploy.__globals__['frozen_stager']
        original_with_current_stage = old_factory(a.original_stager)
        receipt, _ = current_deploy.__globals__['verify_receipt'](original_with_current_stage, a)
        if not a.reference_profile:
            a.reference_profile = receipt['profile_descriptor']['path']
            a.reference_profile_sha256 = assets.PROFILE_SHA256
        private = native_builder(stager, a)
        # CURRENT production AST/selectors/env retained; only private I/O graph.
        bindings = {name: private.__dict__[name] for name in ('regular', 'file_sha', 'public', 'copy_pinned', 'os')}
        private.stage = FORMAL.clone(original_with_current_stage.stage, **bindings)
        return FORMAL.clone(current_deploy, frozen_stager=lambda source=None: private)(a)

    return stager, assets, stage_three, deploy_with_staged, fullcopy


def main(argv=None):
    # Exact original CLI dispatch, preparation, aggregate and error projection.
    return FORMAL.clone(FORMAL.main, adapters=adapters)(argv)


if __name__ == '__main__':
    raise SystemExit(main())
