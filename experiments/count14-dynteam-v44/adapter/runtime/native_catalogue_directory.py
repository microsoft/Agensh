"""Bind the approved cardinality guard to the actual FROZEN role directory.

Only fixed PUBLIC control JSON files are opened, with pin/size/NOFOLLOW and
before-after identity checks. No target, session, model, archive or financial
body is read here. Cold wrapper only; it cannot release a model gate.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat

from common import need, private_dir
from dynteam_metadata import digest
from new_scope_ledger import native_catalogue, open_new_scope_ledger


def _read_pinned(path, pin, maximum):
    path = Path(path)
    need(path.is_absolute() and path.parent.resolve() == path.parent,
         "DYNTEAM_FROZEN_CATALOGUE_CANONICAL_PARENT")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= maximum,
             "DYNTEAM_FROZEN_CATALOGUE_REGULAR_BOUNDED_FILE")
        raw = os.read(fd, maximum + 1)
        after = os.fstat(fd)
        pathname = os.stat(path, follow_symlinks=False)
        fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        need(fields(before) == fields(after) == fields(pathname) and stat.S_ISREG(pathname.st_mode) and
             len(raw) == before.st_size and hashlib.sha256(raw).hexdigest() == pin,
             "DYNTEAM_FROZEN_CATALOGUE_EXACT_UNCHANGED_FILE_PIN")
        return raw
    finally:
        os.close(fd)


@dataclass(frozen=True)
class FrozenCatalogues:
    contract_sha256: str
    directory_pin_index_sha256: str
    owner_root: str
    mode: str
    trajectories: tuple
    canonical_contract_sha256: str

    def as_registry(self):
        return {t: list(roles) for t, roles in self.trajectories}


def read_frozen_catalogues(directory, *, contract_filename, contract_sha256, index_sha256):
    directory = Path(directory)
    need(directory.is_absolute() and directory.resolve() == directory and directory.is_dir(),
         "DYNTEAM_FROZEN_NATIVE_DIRECTORY_CANONICAL")
    need(contract_filename in ("PRODUCTION_PUBLIC_CONTRACT.json", "SMOKE_PUBLIC_CONTRACT.json"),
         "DYNTEAM_FIXED_PUBLIC_CONTRACT_FILENAME")
    index = json.loads(_read_pinned(directory / "CONTRACT_AND_NATIVE_ROLE_DIRECTORY_PINS_PUBLIC.json",
                                   index_sha256, 200000))
    contract_raw = _read_pinned(directory / contract_filename, contract_sha256, 200000)
    contract = json.loads(contract_raw)
    need(contract["schema"] == "count14-dynteam-two-arm-public-contract-v1" and
         contract["mode"] in ("production", "smoke") and contract_filename == contract["mode"].upper() + "_PUBLIC_CONTRACT.json" and
         [(a["arm"], len(a["trajectories"])) for a in contract["arms"]] ==
         [("DYNTEAM", 3 if contract["mode"] == "production" else 1),
          ("DYNTEAM_RACING", 3 if contract["mode"] == "production" else 1)],
         "DYNTEAM_FROZEN_PAIRED_CONTRACT")
    need(index["files"][contract_filename]["sha256"] == contract_sha256,
         "DYNTEAM_FROZEN_CONTRACT_BOUND_TO_ROLE_DIRECTORY_INDEX")
    registry = []
    root = directory / "native-role-directory"
    need(root.resolve() == root and {p.name for p in root.iterdir()} == {"DYNTEAM", "DYNTEAM_RACING"},
         "DYNTEAM_EXACT_TWO_FROZEN_NATIVE_ARMS")
    for arm in contract["arms"]:
        expected = native_catalogue(arm=arm["arm"])
        role_dir = root / arm["arm"]
        need(role_dir.resolve() == role_dir and role_dir.is_dir() and
             {p.name for p in role_dir.iterdir()} == {r + ".json" for r in expected},
             "DYNTEAM_EXACT_FROZEN_NATIVE_ROLE_FILES_NO_EXTRAS")
        actual = []
        for role, kind in expected.items():
            path = role_dir / (role + ".json")
            pin = index["files"][str(path.relative_to(directory))]
            raw = _read_pinned(path, pin["sha256"], 4096)
            value = json.loads(raw)
            need(len(raw) == pin["bytes"] and set(value) == {
                "schema", "arm", "role", "kind", "model_fee_domain", "stable_slot_not_lifetime_birth_cap",
                "external_request_cap13_not_population_cap", "source_commit"} and
                value == dict(schema="count14-native-charged-role-slot-v1", arm=arm["arm"], role=role, kind=kind,
                              model_fee_domain="SEARCH", stable_slot_not_lifetime_birth_cap=True,
                              external_request_cap13_not_population_cap=True, source_commit=arm["source_commit"]),
                "DYNTEAM_FROZEN_NATIVE_ROLE_EXACT_CHARGED_CONTROL_FIELDS")
            actual.append(role)
        for t in arm["trajectories"]:
            rows = [r for r in contract["trajectories"] if r["trajectory_id"] == t]
            need(len(rows) == 1 and rows[0]["roles"] == actual and rows[0]["arm"] == arm["arm"] and
                 rows[0]["role_kinds"] == expected and rows[0]["request_cap"] == 13,
                 "DYNTEAM_FROZEN_DIRECTORY_DERIVED_ACCOUNT_ROSTER")
            registry.append((t, tuple(actual)))
    need(len(registry) == len(contract["trajectories"]) == len(set(t for t, _ in registry)),
         "DYNTEAM_FROZEN_EACH_TRAJECTORY_EXACTLY_ONCE")
    return FrozenCatalogues(contract_sha256, index_sha256, contract["arms"][0]["root"],
                            contract["mode"], tuple(registry), digest(contract))


def open_from_frozen_directory(home, directory, *, contract_filename, contract_sha256,
                               index_sha256, qualification_only=False):
    """Cold wrapper intended for the actual owner constructor; no activation."""
    proof = read_frozen_catalogues(directory, contract_filename=contract_filename,
                                  contract_sha256=contract_sha256, index_sha256=index_sha256)
    need(qualification_only or Path(home) == Path(proof.owner_root) / "owner" / "ledger",
         "DYNTEAM_EXACT_PAIRED_OWNER_FROZEN_ROOT")
    # This is the only wider roster source: verified actual role files, not a
    # caller-selected integer or an agent's self-reported team population.
    if qualification_only:
        registry = {"OWN-" + str(i): list(roles) for i, (_, roles) in enumerate(proof.trajectories)}
    else:
        registry = proof.as_registry()
    private_dir(Path(home).parent, create=True)
    ledger = open_new_scope_ledger(home, registry, qualification_only=qualification_only)
    ledger._dynteam_frozen_directory_proof = proof
    return ledger
