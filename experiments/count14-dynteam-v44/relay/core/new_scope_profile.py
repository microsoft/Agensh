"""Instantiate ORIGINAL v2 sampling/RNG policy for the new native role grid.

No sampling/billing/RNG key-formula changes. Only new-root role/checkpoint
enumerations and the pure manifest compiler are adapted before construction.
Original class and global functions are never monkeypatched.
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import textwrap
from types import FunctionType, MethodType

from common import need, digest
from scientific_profile import SearchProfile, action_seed, RNG_POLICY_SHA


FORMAL_CUTS=(10000000,20000000,50000000,100000000)
SMOKE_CUTS=(500000,1000000)


def expanded_action_seed(roles,*,checkpoints=FORMAL_CUTS):
    need(type(checkpoints) is tuple and checkpoints in (FORMAL_CUTS,SMOKE_CUTS),
         'DYNTEAM_EXACT_FORMAL_OR_SYSTEM_SMOKE_RNG_ENUMERATION')
    source = textwrap.dedent(inspect.getsource(action_seed))
    tree = ast.parse(source)
    comparisons = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and
                   isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and
                   n.func.value.id == "re" and n.func.attr == "fullmatch"]
    need(len(comparisons) == 1, "DYNTEAM_ONE_ORIGINAL_SEARCH_RNG_ROLE_ENUMERATION")
    matcher = comparisons[0]
    replacement = ast.parse("role in _dynteam_frozen_roles", mode="eval").body
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.BoolOp):
            for i, value in enumerate(node.values):
                if value is matcher:
                    node.values[i] = replacement
                    found = True
    need(found, "DYNTEAM_ORIGINAL_RNG_ROLE_MATCHER_SITE")
    # Original 100M authorization changes this enumeration only, not the key.
    cuts = [n for n in ast.walk(tree) if isinstance(n, ast.Tuple) and
            [x.value for x in n.elts if isinstance(x, ast.Constant)] == [10000000, 20000000]]
    need(len(cuts) == 1, "DYNTEAM_ORIGINAL_RNG_FINAL_CHECKPOINT_ENUMERATION")
    cuts[0].elts=[ast.Constant(c) for c in checkpoints]
    ast.fix_missing_locations(tree)
    scope = dict(action_seed.__globals__, _dynteam_frozen_roles=frozenset(roles))
    namespace = {}
    exec(compile(tree, __file__ + ":unchanged_rng_formula_expanded_roles", "exec"), scope, namespace)
    return namespace["action_seed"]


def original_search_profile(contract, original_policy, *, original_policy_sha256):
    need(contract["schema"] == "count14-dynteam-two-arm-public-contract-v1" and
         digest(original_policy) == original_policy_sha256,
         "DYNTEAM_FROZEN_ORIGINAL_MODEL_POLICY_PIN")
    rows = contract["trajectories"]
    need(len(rows) in (2, 6) and all(r["request_cap"] == 13 for r in rows),
         "DYNTEAM_NEW_PAIRED_PROFILE_SCOPE")
    protocol = dict(contract["v2_baseline_reference_protocol"])
    # Already validated original values must agree; do not overwrite a mismatch.
    need(protocol.get("rng_policy") in (None, RNG_POLICY_SHA) and
         protocol.get("model_configuration") in (None, original_policy_sha256),
         "DYNTEAM_ORIGINAL_PROTOCOL_RNG_AND_MODEL_EQUAL")
    protocol.update(rng_policy=RNG_POLICY_SHA, model_configuration=original_policy_sha256)
    manifest = {"protocol": protocol, "root": contract["arms"][0]["root"], "new_scope_contract": contract}
    compiled = {"manifest_sha256": digest(manifest),
                "trajectories": [{**r, "seed": r["search_seed"]} for r in rows]}
    def compile_frozen(value):
        need(value is manifest, "DYNTEAM_EXACT_COLD_PROFILE_MANIFEST_OBJECT")
        return compiled
    initializer = SearchProfile.__init__
    cold_init = FunctionType(initializer.__code__, dict(initializer.__globals__, compile_manifest=compile_frozen),
                             initializer.__name__, initializer.__defaults__, initializer.__closure__)
    result = SearchProfile.__new__(SearchProfile)
    cold_init(result, manifest, original_policy, original_policy_sha256)
    # Retain exact original reserve_rng body/event/SQL. Extend only the pure
    # action_seed role enum in this instance's function globals.
    original = SearchProfile.reserve_rng
    all_roles = set(role for row in rows for role in row["roles"])
    rng = expanded_action_seed(all_roles,checkpoints=SMOKE_CUTS if contract['mode']=='smoke' else FORMAL_CUTS)
    bound = FunctionType(original.__code__, dict(original.__globals__, action_seed=rng),
                         original.__name__, original.__defaults__, original.__closure__)
    result.reserve_rng = MethodType(bound, result)
    result._dynteam_contract_sha256 = digest(contract)
    result._dynteam_action_seed=rng
    return result
