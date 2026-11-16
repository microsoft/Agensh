#!/usr/bin/env python3
"""Private ORIGINAL input compiler selectors for the prospective formal cohort.

No task/key/asset/private configuration read. Real missing OPS facts stay draft.
All original GLM invocation, CLI/source/host/environment/bounds guards retained.
"""
from pathlib import Path
from types import SimpleNamespace
import argparse
import ast
import copy
import json
import sys

# Explicit framework file, not cwd/ambient PYTHONPATH. New cold script only.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from formal_public_common import (need, sha, digest, original_module, clone_into, read_contract,
    save, INPUTS_SHA, BINDINGS_SCHEMA, LAYOUT_SCHEMA)
from formal_public_factory import base_helper, validate_base_bindings, validate_game_sources


def private_compiler():
    compiler = original_module('smoke_bootstrap_task_inputs.py', INPUTS_SHA)
    original_helper = compiler.helper
    def helper():
        value = original_helper()
        value.validate_bindings = lambda b, *, code_root: validate_base_bindings(value, b, code_root=code_root)
        return value
    compiler.helper = helper
    constants = {
        'count14-dynteam-smoke-code-layout-v1': LAYOUT_SCHEMA,
        'SMOKE_PUBLIC_CONTRACT.json': 'PRODUCTION_PUBLIC_CONTRACT.json',
        'smoke': 'production',
        'count14-dynteam-baseline-smoke-bindings-v1': BINDINGS_SCHEMA,
        'baseline_smoke_sources': 'formal_cohort_sources',
        'count14-native-cycle0-only-smoke-reference-scope-v1': 'count14-native-task-aware-no-reference-scope-v1',
        'formal_100M_reference_adaptation_still_required': 'actual_public_program_binding_qualification_still_required',
        'count14-dynteam-smoke-derived-static-draft-v1': 'count14-dynteam-formal100m-derived-static-draft-v1',
        'count14-dynteam-smoke-exact-facts-request-v1': 'count14-dynteam-formal100m-exact-facts-request-v1',
        'smoke_only_reference_scope': 'no_reference_scientific_tester_scope',
        'unused_wrapper_descriptor_not_required_for_this_cycle0_only_smoke': 'unused_official_wrapper_descriptor_not_required',
        'count14-dynteam-smoke-inputs-compile-result-v1': 'count14-dynteam-formal100m-inputs-compile-result-v1',
        'count14-dynteam-smoke-fresh-host-facts-v1': 'count14-dynteam-formal100m-fresh-host-facts-v1',
    }
    expressions = {
        "len(contract['trajectories'])==2": "len(contract['trajectories'])==6",
        "r['checkpoints_tokens']==[500000,1000000]": "r['checkpoints_tokens']==[10000000,20000000,50000000,100000000]",
        "r['search_tokens']==1000000": "r['search_tokens']==100000000",
    }
    expected = {'const:' + key: 1 for key in constants}
    expected['const:smoke_only_reference_scope'] = 2
    expected.update({'expr:' + key: 1 for key in expressions})
    clone_into(compiler, compiler.compile_inputs, constants=constants,
               expressions=expressions, expected=expected)
    return compiler


def compile_inputs(layout_path, layout_sha256, *, destination, host_facts_path=None, host_facts_sha256=None):
    compiler, guard = private_compiler(), base_helper()
    layout = guard.public(layout_path, layout_sha256)
    need(type(layout) is dict and set(layout) == compiler.LAYOUT_FIELDS | {'racing_game_sources'} and
         layout['schema'] == LAYOUT_SCHEMA, 'FORMAL_INPUTS_EXACT_LAYOUT_PLUS_THREE_GAME_DESCRIPTORS')
    root = Path(layout['code_root'])
    need(root.is_absolute() and root.resolve() == root and root.is_dir(), 'FORMAL_INPUTS_CANONICAL_CODE_ROOT')
    directory = Path(layout['contract_directory'])
    need(directory.is_absolute() and directory.resolve() == directory and directory.is_dir() and
         directory.is_relative_to(root), 'FORMAL_INPUTS_CONTRACT_DIRECTORY_IN_DECLARED_CODE_ROOT')
    cp = directory / 'PRODUCTION_PUBLIC_CONTRACT.json'
    index = Path(layout['contract_directory']) / 'CONTRACT_AND_NATIVE_ROLE_DIRECTORY_PINS_PUBLIC.json'
    need(cp.resolve() == cp and index.resolve() == index and not cp.is_symlink() and not index.is_symlink(),
         'FORMAL_INPUTS_FIXED_PUBLIC_CONTRACT_AND_INDEX_FILES')
    contract_descriptor = dict(directory=layout['contract_directory'], filename=cp.name,
        sha256=sha(cp), canonical_sha256=digest(json.loads(cp.read_bytes())), index_sha256=sha(index))
    contract = read_contract(guard, contract_descriptor, code_root=root)
    validate_game_sources(guard, layout['racing_game_sources'], code_root=root, contract=contract)
    projection = {k: copy.deepcopy(v) for k, v in layout.items() if k != 'racing_game_sources'}
    original_helper = compiler.helper
    expected_path = Path(layout_path)
    def helper():
        module = original_helper()
        original_public = module.public
        def public(path, pin, maximum=1048576):
            value = original_public(path, pin, maximum)
            if Path(path) == expected_path and pin == layout_sha256:
                need(value == layout, 'FORMAL_INPUTS_LAYOUT_STILL_EXACT')
                return copy.deepcopy(projection)
            return value
        module.public = public
        return module
    compiler.helper = helper
    result = compiler.compile_inputs(layout_path, layout_sha256, destination=destination,
        host_facts_path=host_facts_path, host_facts_sha256=host_facts_sha256)
    draft = guard.public(result['static_draft']['path'], result['static_draft']['sha256'])
    base = draft['factory_bindings']
    if result['bindings'] is not None:
        base = guard.public(result['bindings']['path'], result['bindings']['sha256'])
    formal = copy.deepcopy(base)
    formal['racing_game_sources'] = copy.deepcopy(layout['racing_game_sources'])
    output = Path(destination)
    projected = save(output / 'FORMAL_FACTORY_DRAFT_PUBLIC.json', dict(
        schema='count14-formal100m-factory-derived-draft-v1', factory_bindings=formal,
        original_guarded_static_draft=result['static_draft'], missing_fact_codes=result['missing_fact_codes'],
        original_scientific_model_accounting_values_changed=False,
        actual_owner_or_models_created=False, native_idle_watchdog_remaining=True,
        formal_natural_first_point_remaining=True, formal_runtime_qualification=False))
    bindings = None
    if result['ready_to_instantiate_factory']:
        need(formal['template_only'] is False, 'FORMAL_INPUTS_NO_TEMPLATE_ACTIVATION')
        bindings = save(output / 'FORMAL_FACTORY_BINDINGS_PUBLIC.json', formal)
    return dict(schema='count14-formal100m-public-inputs-result-v1', bindings=bindings, static_draft=projected,
        ready_to_instantiate_factory=bindings is not None, required_facts=result['required_facts'],
        missing_fact_codes=result['missing_fact_codes'], owner_created=False, models=0,
        formal_runtime_qualification=False, native_idle_watchdog_remaining=True)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--code-layout', required=True); p.add_argument('--code-layout-sha256', required=True)
    p.add_argument('--destination', required=True)
    p.add_argument('--host-facts'); p.add_argument('--host-facts-sha256')
    a = p.parse_args(argv)
    try:
        print(json.dumps(compile_inputs(a.code_layout, a.code_layout_sha256, destination=a.destination,
            host_facts_path=a.host_facts, host_facts_sha256=a.host_facts_sha256), sort_keys=True)); return 0
    except Exception as error:
        frames, tb = [], error.__traceback__
        while tb:
            frames.append(dict(file=tb.tb_frame.f_code.co_filename, line=tb.tb_lineno, function=tb.tb_frame.f_code.co_name)); tb=tb.tb_next
        print(json.dumps(dict(PUBLIC_code='FORMAL_INPUT_COMPILATION_REFUSED', exception_type=type(error).__name__,
            locations=frames), sort_keys=True)); return 2


if __name__ == '__main__':
    raise SystemExit(main())
