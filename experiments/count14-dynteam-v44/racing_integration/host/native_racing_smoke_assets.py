#!/usr/bin/env python3
"""RACING-only cold selectors around the ORIGINAL three-asset/deploy CLI.

Identical approved assets, profile8530, source pins, exact old KEEP whitelist,
opaque copy and config/schema/formulas. Only selected arm changes; original
arms[0] package/key root guards stay exact. No baseline file/module/global is edited; no target asset is
opened by verification. Real stage/deploy must be executed solely by OPS.
"""
from __future__ import annotations

from pathlib import Path
from types import FunctionType, SimpleNamespace
import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import sys
import textwrap

ORIGINAL_ASSET_ADAPTER_SHA256 = '16e6ab60b88ab4c0d86e4790f461b0fd330a0313bf7071b6dafb30bec7877a16'


def need(ok, code):
    if not ok:
        raise RuntimeError(code)


def _function(function, **bindings):
    result = FunctionType(function.__code__, dict(function.__globals__, **bindings),
                          function.__name__, function.__defaults__, function.__closure__)
    result.__kwdefaults__ = function.__kwdefaults__
    return result


def _racing_arm_root(contract):
    rows = [arm for arm in contract['arms'] if arm['arm'] == 'DYNTEAM_RACING']
    need(len(rows) == 1, 'RACING_ASSETS_ONE_REGISTERED_ARM_ROOT')
    return rows[0]['root']


def _selectors(function, *, arm_sites, root_sites):
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    prior = copy.deepcopy(tree)
    wanted = ast.parse("contract['arms'][0]['root']", mode='eval').body
    found = dict(arm=0, root=0)

    class Select(ast.NodeTransformer):
        def visit_Compare(self, node):
            if (len(node.ops) == len(node.comparators) == 1 and isinstance(node.ops[0], ast.Eq) and
                isinstance(node.comparators[0], ast.Constant) and node.comparators[0].value == 'DYNTEAM'):
                node.comparators[0].value = 'DYNTEAM_RACING'
                found['arm'] += 1
            return self.generic_visit(node)

        def visit_Subscript(self, node):
            if root_sites and ast.dump(node, include_attributes=False) == ast.dump(wanted, include_attributes=False):
                found['root'] += 1
                return ast.copy_location(ast.Call(func=ast.Name(id='_racing_registered_arm_root', ctx=ast.Load()),
                    args=[ast.Name(id='contract', ctx=ast.Load())], keywords=[]), node)
            return self.generic_visit(node)

    tree = Select().visit(tree)
    need(found == dict(arm=arm_sites, root=root_sites), 'RACING_ASSETS_EXACT_ARM_ROOT_SELECTOR_SITES')
    restored = copy.deepcopy(tree)
    reversed_sites = dict(arm=0, root=0)

    class Undo(ast.NodeTransformer):
        def visit_Compare(self, node):
            if (len(node.ops) == len(node.comparators) == 1 and isinstance(node.ops[0], ast.Eq) and
                isinstance(node.comparators[0], ast.Constant) and node.comparators[0].value == 'DYNTEAM_RACING'):
                node.comparators[0].value = 'DYNTEAM'
                reversed_sites['arm'] += 1
            return self.generic_visit(node)

        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id == '_racing_registered_arm_root':
                reversed_sites['root'] += 1
                return copy.deepcopy(wanted)
            return self.generic_visit(node)

    restored = Undo().visit(restored)
    need(reversed_sites == found and ast.dump(restored, include_attributes=False) ==
         ast.dump(prior, include_attributes=False),
         'RACING_ASSETS_INVERSE_ORIGINAL_AST_NO_PIN_WHITELIST_OR_FORMULA_DELTA')
    namespace = dict(function.__globals__, _racing_registered_arm_root=_racing_arm_root)
    exec(compile(ast.fix_missing_locations(tree), __file__ + ':exact-arm-root-selectors', 'exec'), namespace)
    return namespace[function.__name__]


def build_adapters():
    path = Path(__file__).with_name('smoke_checkpoint_final_newroot_assets_v1.py').resolve()
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink() and
         hashlib.sha256(path.read_bytes()).hexdigest() == ORIGINAL_ASSET_ADAPTER_SHA256,
         'RACING_ASSETS_EXACT_FROZEN_ORIGINAL_ASSET_ADAPTER_PIN')
    spec = importlib.util.spec_from_file_location('count14_original_three_asset_adapter_for_racing', path)
    assets = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(assets)
    scope = _selectors(assets.contract_scope, arm_sites=2, root_sites=0)

    def frozen_stager(source=None):
        original = assets.frozen_stager(source)
        # A fresh private namespace; original stager module and stage are never
        # mutated, including its original exact KEEP13 paths/opaque copier.
        return SimpleNamespace(**dict(original.__dict__, stage=_selectors(original.stage,
            arm_sites=1, root_sites=0)))

    verify = _function(assets.verify_receipt, contract_scope=scope)
    stage = _function(assets.stage_three, contract_scope=scope, frozen_stager=frozen_stager)
    deploy = _function(assets.deploy_with_staged, verify_receipt=verify, frozen_stager=frozen_stager)
    # Verify both cold selector closures now, without touching any target asset.
    frozen_stager()
    return assets, stage, deploy


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        assets, stage, deploy = build_adapters()
        if argv == ['--verify-only']:
            print(json.dumps(dict(RACING_ASSET_ADAPTER_IMPORT_AND_INVERSE_PASS=True,
                stage_arm_sites=1, stage_exact_root_sites=0, asset_scope_arm_sites=2,
                target_assets_opened=False, model_calls=0, owners=0), sort_keys=True))
            return 0
        args = assets.parser().parse_args(argv)
        result = stage(args) if args.command == 'stage-three' else deploy(args)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        locations, tb = [], error.__traceback__
        while tb:
            locations.append(dict(file=tb.tb_frame.f_code.co_filename, line=tb.tb_lineno,
                                  function=tb.tb_frame.f_code.co_name))
            tb = tb.tb_next
        print(json.dumps(dict(PUBLIC_code='RACING_ASSET_SELECTOR_REFUSED_RETAIN_NO_RETRY',
            exception_type=type(error).__name__, locations=locations), sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
