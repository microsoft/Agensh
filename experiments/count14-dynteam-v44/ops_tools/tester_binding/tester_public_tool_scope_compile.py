#!/usr/bin/env python3
"""Prospective metadata for each formal tester, NOT Game/runtime permission.

Reuses the original public reference/catalogue/hash formulas unchanged. The
private compiler differs only in the registered arm selector, tester execution
source-name enumeration and its explicit role-specific prospective POLICY.
It does not read programs, tests, task/source, private configs or output bodies.
"""
from pathlib import Path, PurePosixPath
import argparse
import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import textwrap

ORIGINAL_COMPILER_SHA256 = '6dcf60b98f1fe05e3cc605958e26d17ff5234e4fed003246f3f8c93cbd9be1f7'
PRODUCTION_CONTRACT_RAW_SHA256 = '9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'
PRODUCTION_CONTRACT_CANONICAL_SHA256 = '9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'
CATALOGUE_SHA256 = '3ac1d9773892c87fcd858ecafcee996a1083097f3052454c191b830685b4aca7'


def need(ok):
    if not ok:
        raise ValueError('FORMAL_TESTER_PROSPECTIVE_METADATA_REFUSED')


def original(root):
    path = Path(root) / 'runtime-v1/racing_public_tool_scope_compile_v1.py'
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink() and
         hashlib.sha256(path.read_bytes()).hexdigest() == ORIGINAL_COMPILER_SHA256)
    spec = importlib.util.spec_from_file_location('formal_tester_original_metadata_compiler', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def relative(value, suffix):
    p = PurePosixPath(value)
    need(not p.is_absolute() and str(p) == value and '..' not in p.parts and
         not {'private-context', 'evaluator-private', 'requests', 'responses', 'candidates',
              'count14_candidates', 'snapshots', 'credentials'}.intersection(p.parts) and
         p.suffix in suffix)
    return value


def tester_compiler(module, *, binding_module, protocol, runner, protocol_sha256):
    binding_module = relative(binding_module, ('.py',))
    protocol = relative(protocol, ('.json', '.md'))
    runner = relative(runner, ('.cjs',))
    need(PurePosixPath(runner).name == 'smoke_racing_tools_public_runner.cjs')
    sources = (runner,
               'runtime-v1/smoke_racing_tools_public_exec.py',
               'runtime-v1/formal_count14_tester_public.py', binding_module, protocol)
    need(len(set(sources)) == 5 and type(protocol_sha256) is str and
         len(protocol_sha256) == 64 and all(c in '0123456789abcdef' for c in protocol_sha256))
    tree = ast.parse(textwrap.dedent(inspect.getsource(module.compile_scope)))
    before = copy.deepcopy(tree)
    changes = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Compare) and len(node.ops) == len(node.comparators) == 1 and
            isinstance(node.ops[0], ast.Eq) and isinstance(node.comparators[0], ast.Constant) and
            node.comparators[0].value == 'DYNTEAM_RACING'):
            changes.append((node, copy.deepcopy(node)))
            node.ops = [ast.In()]
            node.comparators = [ast.Tuple(elts=[ast.Constant('DYNTEAM'), ast.Constant('DYNTEAM_RACING')],
                                          ctx=ast.Load())]
        elif (isinstance(node, ast.Assign) and len(node.targets) == 1 and
              isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'source_names'):
            changes.append((node, copy.deepcopy(node)))
            node.value = ast.Name(id='_formal_tester_source_names', ctx=ast.Load())
    need(len(changes) == 2)
    restored = copy.deepcopy(tree)
    for target, old in changes:
        found = [n for n in ast.walk(restored) if ast.dump(n, include_attributes=False) ==
                 ast.dump(target, include_attributes=False)]
        need(len(found) == 1)
        found[0].__dict__.update(copy.deepcopy(old.__dict__))
    need(ast.dump(restored, include_attributes=False) == ast.dump(before, include_attributes=False))
    policy = dict(module.POLICY, allowed_program_workspace='/work',
        approved_public_input_view='/opt/tester-input/approved-input', role='tester-00',
        runner_mount='/opt/count14-public-probe/runner.cjs',
        program_registration_pattern='/work/tests/.count14-public-probe/registrations/slot-XX.PUBLIC.json',
        runner_temporary_workspace='/work/tests/.git/count14-public-probes',
        program_binding_kind='EXISTING_REGULAR_PUBLIC_EXECUTABLE_STAT_ONLY',
        registration_protocol_sha256=protocol_sha256,
        native_program_body_not_read_by_coordinator=True)
    namespace = dict(module.compile_scope.__globals__, POLICY=policy, _formal_tester_source_names=sources)
    exec(compile(ast.fix_missing_locations(tree), __file__ + ':tester-metadata-selectors', 'exec'), namespace)
    return namespace['compile_scope']


def compile_tester(module, *, contract, profile, manifest, manifest_sha256, trajectory,
                   binding_module, protocol, runner):
    need(module.digest(contract) == PRODUCTION_CONTRACT_CANONICAL_SHA256 and
         contract.get('mode') == 'production')
    compile_scope = tester_compiler(module, binding_module=binding_module, protocol=protocol, runner=runner,
                                   protocol_sha256=manifest['files'][protocol]['sha256'])
    scope, provenance = compile_scope(contract=contract, contract_sha256=module.digest(contract),
        profile=profile, manifest=manifest, manifest_sha256=manifest_sha256, trajectory=trajectory)
    need(scope['original_count14_catalogue_sha256'] == CATALOGUE_SHA256)
    # Companion provenance names the role; no fake live program/UID/caps proof.
    provenance.update(formal_role='tester-00', Game_scope_reused=False,
        original_compiler_sha256=ORIGINAL_COMPILER_SHA256, original_reference_catalogue_formulas_unchanged=True,
        private_metadata_selector_inverse_AST=True)
    return scope, provenance


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('code-root', 'manifest-sha256', 'contract', 'contract-sha256', 'trajectory',
                'binding-module-relative', 'protocol-relative', 'runner-relative', 'destination'):
        p.add_argument('--' + key, required=True)
    args = p.parse_args(argv)
    try:
        root, contract_path, dest = Path(args.code_root), Path(args.contract), Path(args.destination)
        need(root.is_absolute() and root.resolve() == root and root.is_dir() and
             contract_path.is_relative_to(root) and args.contract_sha256 == PRODUCTION_CONTRACT_RAW_SHA256 and
             dest.is_absolute() and dest.parent.resolve() == dest.parent and dest.is_relative_to(root.parent) and
             not dest.exists() and not dest.is_symlink())
        module = original(root)
        manifest = module.public(root / 'FROZEN_FILES_PUBLIC.json', args.manifest_sha256)
        contract = module.public(contract_path, args.contract_sha256)
        profile = module.public(root / 'ORIGINAL_FINAL_PROFILE_8530_PUBLIC.json', module.PROFILE_SHA256)
        scope, provenance = compile_tester(module, contract=contract, profile=profile, manifest=manifest,
            manifest_sha256=args.manifest_sha256, trajectory=args.trajectory,
            binding_module=args.binding_module_relative, protocol=args.protocol_relative, runner=args.runner_relative)
        dest.mkdir(mode=0o700)
        descriptor = module.write_new(dest / 'TESTER_PUBLIC_TOOL_SCOPE.json', scope)
        companion = module.write_new(dest / 'TESTER_PUBLIC_TOOL_SCOPE_PROVENANCE_PUBLIC.json', provenance)
        print(json.dumps({'schema': 'count14-formal-tester-prospective-tool-scope-compiled-v1',
            'scope': descriptor, 'provenance': companion, 'models': 0, 'owners': 0,
            'runtime_qualified': False}, sort_keys=True))
        return 0
    except Exception as error:
        locations, tb = [], error.__traceback__
        while tb:
            locations.append({'file': tb.tb_frame.f_code.co_filename, 'line': tb.tb_lineno,
                              'function': tb.tb_frame.f_code.co_name})
            tb = tb.tb_next
        print(json.dumps({'PUBLIC_code': 'FORMAL_TESTER_SCOPE_COMPILE_REFUSED_RETAIN_PREFIX',
            'exception_type': type(error).__name__, 'locations': locations, 'models': 0, 'owners': 0}, sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
