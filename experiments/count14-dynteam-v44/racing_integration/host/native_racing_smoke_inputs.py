#!/usr/bin/env python3
"""RACING deployment-only PUBLIC projection of the ORIGINAL input compiler.

Original contract/policy/invocation/bounds/host/route/key-stat/absence guards and
all derived values remain unchanged. No task/private config/provider secret or
scientific file is opened here. Missing facts still produce only drafts. The
new explicit schema and Game descriptors never rewrite the intermediate or
original bindings, ledger, history or scientific contract.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import argparse
import copy
import hashlib
import importlib.util
import json
import os

ORIGINAL_COMPILER_SHA256 = 'ee70a45a74b0a4375034f1d605232a0afccf8f396e56027dc2ba2a662a7e2b5d'


def _original():
    path = Path(__file__).with_name('smoke_bootstrap_task_inputs.py').resolve()
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != ORIGINAL_COMPILER_SHA256:
        raise ValueError('RACING_INPUTS_EXACT_ORIGINAL_COMPILER_SOURCE_PIN')
    spec = importlib.util.spec_from_file_location('count14_original_input_compiler_racing_private_scope', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_game_descriptor(helper, value, *, code_root):
    helper.require(type(value) is dict and set(value) == {'code_directory', 'code_map_sha256',
        'custodian_path', 'custodian_sha256', 'public_tool_scope'},
        'RACING_INPUTS_EXACT_FIVE_GAME_DESCRIPTOR_FIELDS')
    root = Path(code_root)
    for key in ('code_directory', 'custodian_path'):
        path = Path(value[key])
        helper.require(path.is_absolute() and path.resolve() == path and path.is_relative_to(root) and
            not path.is_symlink() and (path.is_dir() if key == 'code_directory' else path.is_file()),
            'RACING_INPUTS_ONLY_INSTALLED_FROZEN_GAME_FRAMEWORK_PATHS')
    for key in ('code_map_sha256', 'custodian_sha256'):
        helper._sha(value[key])
    fields = {'original_v2_tool_binding_sha256', 'original_count14_catalogue_sha256',
        'native_scope_sha256', 'original_public_tools_only', 'official_evaluator_access', 'private_reference_access'}
    scope = value['public_tool_scope']
    helper.require(type(scope) is dict and set(scope) == fields and
        scope['original_public_tools_only'] is True and scope['official_evaluator_access'] is False and
        scope['private_reference_access'] is False, 'RACING_INPUTS_EXACT_PUBLIC_TOOLS_NO_ORACLE_SCOPE')
    for key in ('original_v2_tool_binding_sha256', 'original_count14_catalogue_sha256', 'native_scope_sha256'):
        helper._sha(scope[key])
    return copy.deepcopy(value)


def project_bindings(helper, original_bindings, game):
    helper.require(type(original_bindings) is dict and set(original_bindings) == helper.FIELDS and
        original_bindings['schema'] == 'count14-dynteam-baseline-smoke-bindings-v1' and
        type(original_bindings['template_only']) is bool,
        'RACING_INPUTS_ONLY_EXACT_ORIGINAL_COMPILER_PARAMETER_VIEW')
    result = copy.deepcopy(original_bindings)
    result['schema'] = 'count14-dynteam-racing-smoke-bindings-v1'
    result['racing_game_sources'] = copy.deepcopy(game)
    restored = {key: copy.deepcopy(value) for key, value in result.items() if key != 'racing_game_sources'}
    restored['schema'] = 'count14-dynteam-baseline-smoke-bindings-v1'
    helper.require(restored == original_bindings,
        'RACING_INPUTS_NO_SCIENTIFIC_MODEL_OR_ACCOUNTING_PARAMETER_DELTA')
    return result


def compile_inputs(layout_path, layout_sha256, *, destination, host_facts_path=None, host_facts_sha256=None):
    compiler = _original()
    original_helper = compiler.helper
    helper = original_helper()
    layout = helper.public(layout_path, layout_sha256)
    helper.require(type(layout) is dict and set(layout) == compiler.LAYOUT_FIELDS | {'racing_game_sources'} and
        layout['schema'] == 'count14-dynteam-racing-smoke-code-layout-v1',
        'RACING_INPUTS_EXACT_INSTALLED_NEW_RACING_LAYOUT')
    game = validate_game_descriptor(helper, layout['racing_game_sources'], code_root=layout['code_root'])
    projection = {key: copy.deepcopy(value) for key, value in layout.items() if key != 'racing_game_sources'}
    projection['schema'] = 'count14-dynteam-smoke-code-layout-v1'
    expected_path = Path(layout_path)

    def scoped_helper():
        native = original_helper()  # new private namespace, not a loaded live module
        original_public = native.public
        def public(path, pin, maximum=1048576):
            value = original_public(path, pin, maximum)
            if Path(path) == expected_path and pin == layout_sha256:
                native.require(value == layout, 'RACING_INPUTS_LAYOUT_STILL_EXACT_PINNED_OBJECT')
                return copy.deepcopy(projection)
            return value
        return SimpleNamespace(**dict(native.__dict__, public=public))

    # This module instance is newly loaded above, NOT an original imported live
    # compiler/module. Only the PUBLIC layout transport selector is rebound;
    # original code_file/CLI AST/Bounds/invocation/unknown guards run unchanged.
    compiler.helper = scoped_helper
    original_result = compiler.compile_inputs(layout_path, layout_sha256, destination=destination,
        host_facts_path=host_facts_path, host_facts_sha256=host_facts_sha256)
    output = Path(destination)
    draft = helper.public(original_result['static_draft']['path'], original_result['static_draft']['sha256'])
    original_bindings = draft['factory_bindings']
    if original_result['bindings'] is not None:
        original_bindings = helper.public(original_result['bindings']['path'], original_result['bindings']['sha256'])
    racing = project_bindings(helper, original_bindings, game)

    def save(name, value):
        path = output / name
        raw = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
        try:
            with os.fdopen(fd, 'wb', closefd=False) as out:
                out.write(raw)
                out.flush()
                os.fchmod(fd, 0o444)
                os.fsync(fd)
        finally:
            os.close(fd)
        return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest())

    projected_draft = save('RACING_FACTORY_DRAFT_PUBLIC.json', dict(
        schema='count14-racing-derived-static-draft-v1', factory_bindings=racing,
        original_static_draft=original_result['static_draft'], source_layout_sha256=layout_sha256,
        missing_fact_codes=original_result['missing_fact_codes'], scientific_parameter_delta=False,
        final_private_configuration_body_read=False, owner_created=False, models=0))
    final = None
    if original_result['ready_to_instantiate_factory']:
        helper.require(not racing['template_only'], 'RACING_INPUTS_NO_TEMPLATE_ACTIVATION')
        final = save('RACING_FACTORY_BINDINGS_PUBLIC.json', racing)
    receipt = save('RACING_INPUT_PROJECTION_PUBLIC.json', dict(
        schema='count14-racing-original-input-projection-receipt-v1', source_layout_sha256=layout_sha256,
        original_compile_result=original_result, projected_draft=projected_draft, projected_bindings=final,
        original_compiler_sha256=ORIGINAL_COMPILER_SHA256,
        fields_added=['racing_game_sources'], schema_selector_changed=True,
        contract_model_budget_accounting_or_host_values_changed=False,
        intermediate_original_files_unchanged=True, final_private_configuration_body_read=False))
    return dict(schema='count14-racing-smoke-inputs-compile-result-v1',
        ready_to_instantiate_factory=final is not None, bindings=final, static_draft=projected_draft,
        required_facts=original_result['required_facts'], missing_fact_codes=original_result['missing_fact_codes'],
        projection_receipt=receipt, owner_created=False, models=0, scientific_smoke_pass=False)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--code-layout', required=True)
    parser.add_argument('--code-layout-sha256', required=True)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--host-facts')
    parser.add_argument('--host-facts-sha256')
    args = parser.parse_args(argv)
    try:
        value = compile_inputs(args.code_layout, args.code_layout_sha256, destination=args.destination,
            host_facts_path=args.host_facts, host_facts_sha256=args.host_facts_sha256)
        print(json.dumps(value, sort_keys=True))
        return 0
    except Exception as error:
        locations, tb = [], error.__traceback__
        while tb:
            locations.append(dict(file=tb.tb_frame.f_code.co_filename, line=tb.tb_lineno,
                                  function=tb.tb_frame.f_code.co_name))
            tb = tb.tb_next
        print(json.dumps(dict(PUBLIC_code='RACING_INPUTS_COMPILATION_REFUSED', exception_type=type(error).__name__,
                             locations=locations), sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
