"""Approved cold, INSTANCE-ONLY roster guard; original SQL/arithmetic intact.

Not an experiment launcher. Production paths and trajectories must come from
the frozen two-arm contract. OWN fixtures are explicit and cannot activate.
The upstream Ledger class and all previously constructed instances are untouched.
"""
from __future__ import annotations

import ast
import hashlib
import inspect
from pathlib import Path
import textwrap
from types import MethodType

from budget import Ledger
from common import need

BASE_REGISTER_SHA256 = "9304c5da778ee03923c6b6495f5ac8aff5b2a65ebddbcd96ee1a0e979503e14f"
ROOTS = (
    '/mnt/ptb-scratch2/ct14-dynteam-formal-msg237-20261110-v33/u',
    '/mnt/ptb-scratch2/ct14-dynteam-formal-msg237-20261110-v33/r',
    "/mnt/ptb-scratch2/count14-dynteam-70e2ca54-20261105",
    "/mnt/ptb-scratch2/count14-dynteam-70e2ca54-smoke-20261105",
    "/mnt/ptb-scratch2/count14-dynteam-racing-70e2ca54-21a0413e-20261105",
    "/mnt/ptb-scratch2/count14-dynteam-racing-70e2ca54-21a0413e-smoke-20261105",
    '/mnt/ptb-scratch2/ct14-dtr-smoke-20261105/u',
)


def native_catalogue(*, arm, worker_slots=32, racing_players=7):
    """Rendered native catalogue, NOT the external model inflight limit.

    Freeze this directory before deployment. Every role has a charged stable
    slot; native identity reuse never creates a fresh budget account.
    """
    need(arm in ("DYNTEAM", "DYNTEAM_RACING") and type(worker_slots) is int and
         worker_slots == 32 and type(racing_players) is int and racing_players == 7,
         "DYNTEAM_PINNED_NATIVE_CATALOGUE_PARAMETERS")
    result = {**{f"worker-{n:02d}": "worker" for n in range(worker_slots)},
              "checker-00": "checker", "tester-00": "tester"}
    if arm == "DYNTEAM_RACING":
        result.update({"racing-background-00": "racing_background",
                       **{f"racing-player-{n:02d}": "racing_player" for n in range(racing_players)}})
    from dynteam_metadata import catalogue
    need(result == catalogue(worker_slots, racing_players=7 if arm == "DYNTEAM_RACING" else 0),
         "DYNTEAM_METADATA_AND_NATIVE_BILLING_CATALOGUES_EQUAL")
    return result


def compiled_register():
    """Compile exactly ONE changed comparison operand, verified structurally."""
    source = textwrap.dedent(inspect.getsource(Ledger.register))
    need(hashlib.sha256(source.encode()).hexdigest() == BASE_REGISTER_SHA256,
         "DYNTEAM_FROZEN_ORIGINAL_REGISTER_PIN")
    original = ast.parse(source)
    revised = ast.parse(source)
    sites = []
    for node in ast.walk(revised):
        if (isinstance(node, ast.Compare) and
                ast.dump(node, include_attributes=False) == ast.dump(
                    ast.parse("1 <= len(roles) <= 16", mode="eval").body, include_attributes=False)):
            sites.append(node)
    need(len(sites) == 1, "DYNTEAM_ONE_CARDINALITY_COMPARISON_ONLY")
    sites[0].comparators[-1] = ast.parse("self._dynteam_catalogue_limit(t, roles)", mode="eval").body
    ast.fix_missing_locations(revised)
    # Reverse the one approved replacement and demand exact original AST.
    import copy
    reversed_tree = copy.deepcopy(revised)
    replacements = [n for n in ast.walk(reversed_tree) if isinstance(n, ast.Call) and
                    isinstance(n.func, ast.Attribute) and n.func.attr == "_dynteam_catalogue_limit"]
    need(len(replacements) == 1, "DYNTEAM_ONE_GUARD_REPLACEMENT")
    for n in ast.walk(reversed_tree):
        if isinstance(n, ast.Compare) and n.comparators[-1] is replacements[0]:
            n.comparators[-1] = ast.Constant(16)
    need(ast.dump(reversed_tree, include_attributes=False) == ast.dump(original, include_attributes=False),
         "DYNTEAM_NO_SQL_SCHEMA_OR_ARITHMETIC_DIFFERENCE")
    namespace = {}
    exec(compile(revised, __file__ + ":approved_register", "exec"), Ledger.register.__globals__, namespace)
    return namespace["register"]


def open_new_scope_ledger(home, catalogues, *, qualification_only=False):
    """Cold-create/reopen ONLY our explicit scope; does not release a model gate.

    catalogues is the immutable contract's t -> ordered role catalogue. The
    caller must also pin that contract and all native catalogue files before
    activation. This factory alone never establishes runtime qualification.
    """
    home = Path(home)
    need(type(qualification_only) is bool and home.is_absolute() and
         home.resolve() == home, "DYNTEAM_CANONICAL_NEW_LEDGER_PATH")
    own = qualification_only and any(p.startswith("OWN-") for p in home.parts)
    allowed = any(home == Path(r) / "owner" / "ledger" for r in ROOTS)
    need(own or (not qualification_only and allowed), "DYNTEAM_NEW_ROOT_ONLY_LEDGER")
    need(type(catalogues) is dict and 1 <= len(catalogues) <= 6,
         "DYNTEAM_ONE_SIX_TRACK_OWNER_CATALOGUE")
    canonical = []
    for arm in ("DYNTEAM", "DYNTEAM_RACING"):
        canonical.append(tuple(native_catalogue(arm=arm)))
    if not qualification_only:
        need(all(type(t) is str and t.startswith("count14-dynteam") and tuple(roles) in canonical
                 for t, roles in catalogues.items()), "DYNTEAM_EXACT_NATIVE_ROLE_DIRECTORY_REQUIRED")
    else:
        need(all(type(t) is str and t.startswith("OWN-") and
                 (tuple(roles) in canonical or 1 <= len(roles) <= 16) for t, roles in catalogues.items()),
             "DYNTEAM_EXPLICIT_OWN_CATALOGUE")
    register = compiled_register()  # fail before opening a financial database
    frozen = {t: tuple(roles) for t, roles in catalogues.items()}
    ledger = Ledger(home)

    def limit(self, t, roles):
        need(t in frozen, "DYNTEAM_ONLY_REGISTERED_NEW_TRAJECTORIES")
        # <=16-role paths retain the exact original roster validation. A wider
        # path must match the complete, ordered native catalogue, not a number.
        return len(frozen[t]) if tuple(roles) == frozen[t] else 16

    ledger._dynteam_catalogue_limit = MethodType(limit, ledger)
    ledger.register = MethodType(register, ledger)
    ledger._dynteam_qualification_only = qualification_only
    ledger._dynteam_catalogues = frozen
    return ledger
