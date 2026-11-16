"""Append-only PUBLIC anonymous metadata, never a financial ledger.

No prompts/claims/accounts/native UUIDs/response bodies/PKL are stored. No
financial SQL is issued here. The SINGLE owner publishes prospective metadata
durably BEFORE replacing its in-memory projection. A failed publication cannot
leave a RAM-only first/birth/session marker and silently skip it on retry.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import sqlite3
import threading

from dynteam_metadata import BudgetAnchor, RosterProjection, catalogue, digest, need


def snapshot(projection):
    # These are only OUR newly defined anonymous roster control fields, NOT
    # native/scientific object state or private context.
    with projection._lock:
        return {"schema": "count14-dynteam-anonymous-projection-control-v1", "block": projection.block,
                "arm": projection.arm,
                "observation_basis": projection.observation_basis, "complete_history": projection.complete_history,
                "roles": dict(projection.roles),
                "live": {k: dict(v) for k, v in projection._live.items()},
                "seen": sorted(projection._seen), "births": projection._births,
                "worker_births": projection._worker_births, "sessions": projection._sessions,
                "sequence": projection._sequence, "previous": projection._previous,
                "anchor": None if projection._anchor is None else asdict(projection._anchor)}


def restore(state):
    fields = {"schema", "block", "arm", "roles", "live", "seen", "births", "worker_births", "sessions",
              "observation_basis", "complete_history",
              "sequence", "previous", "anchor"}
    sha = lambda v: type(v) is str and len(v) == 64 and all(c in "0123456789abcdef" for c in v)
    need(type(state) is dict and set(state) == fields and
         state["schema"] == "count14-dynteam-anonymous-projection-control-v1" and
         state["arm"] in ("DYNTEAM", "DYNTEAM_RACING") and
         state["roles"] == catalogue(racing_players=7 if state["arm"] == "DYNTEAM_RACING" else 0),
         "DYNTEAM_EXACT_ANONYMOUS_CONTROL_SCHEMA")
    p = RosterProjection(block=state["block"], arm=state["arm"],
                         racing_players=7 if state["arm"] == "DYNTEAM_RACING" else 0,
                         observation_basis=state["observation_basis"],
                         complete_history=state["complete_history"])
    need(type(state["seen"]) is list and all(sha(s) for s in state["seen"]) and
         len(set(state["seen"])) == len(state["seen"]), "DYNTEAM_ANONYMOUS_BIRTH_SET")
    for k in ("births", "worker_births", "sessions", "sequence"):
        need(type(state[k]) is int and state[k] >= 0, "DYNTEAM_ANONYMOUS_COUNTER")
    need(state["births"] == len(state["seen"]) and state["worker_births"] <= state["births"] and
         sha(state["previous"]), "DYNTEAM_ANONYMOUS_COUNTER_INTEGRITY")
    need(type(state["live"]) is dict and set(state["live"]) <= set(p.roles), "DYNTEAM_ANONYMOUS_LIVE_SLOTS")
    for role, value in state["live"].items():
        need(type(value) is dict and set(value) == {"birth", "session"} and
             value["birth"] in state["seen"] and (value["session"] is None or sha(value["session"])),
             "DYNTEAM_ANONYMOUS_LIVE_CONTROL")
    anchor = None
    if state["anchor"] is not None:
        need(type(state["anchor"]) is dict and set(state["anchor"]) == {
            "actual_search_tokens", "original_event_sequence", "utc_ns", "monotonic_ns"}, "DYNTEAM_ANONYMOUS_ANCHOR_FIELDS")
        anchor = BudgetAnchor(**state["anchor"]).checked()
    p._live = {k: dict(v) for k, v in state["live"].items()}
    p._seen = set(state["seen"])
    p._births, p._worker_births, p._sessions = state["births"], state["worker_births"], state["sessions"]
    p._sequence, p._previous, p._anchor = state["sequence"], state["previous"], anchor
    return p


class AnonymousRosterJournal:
    def __init__(self, path, *, block, arm="DYNTEAM", qualification_only=False, lifecycle_complete=False):
        from dynteam_manifest import ROOT, SMOKE_ROOT
        self.path = Path(path)
        RosterProjection(block=block, arm=arm, racing_players=7 if arm == "DYNTEAM_RACING" else 0)
        need(type(qualification_only) is bool and type(lifecycle_complete) is bool and
             self.path.name == "DYNTEAM_ROSTER_PUBLIC_METADATA.sqlite",
             "DYNTEAM_PUBLIC_METADATA_FILENAME_NOT_FINANCIAL_DB")
        roots = (ROOT, SMOKE_ROOT) if arm == "DYNTEAM" else (
            "/mnt/ptb-scratch2/count14-dynteam-racing-70e2ca54-21a0413e-20261105",
            "/mnt/ptb-scratch2/count14-dynteam-racing-70e2ca54-21a0413e-smoke-20261105")
        scopes = [Path(root) / f"b{block}" / "metadata" for root in roots]
        if type(block) is int and block == 1 and arm in ('DYNTEAM','DYNTEAM_RACING'):
            scopes.append(Path('/mnt/ptb-scratch2/ct14-dynteam-racing-smoke-msg232-20261109-v1')/('u' if arm=='DYNTEAM' else 'r')/'b1/metadata')
        # Exact registered formal six-track namespace, not arbitrary ancestors.
        if type(block) is int and block in (1, 2, 3) and arm in ("DYNTEAM", "DYNTEAM_RACING"):
            scopes.append(Path("/mnt/ptb-scratch2/ct14-dynteam-formal-msg237-20261110-v33") /
                          ("u" if arm == "DYNTEAM" else "r") / f"b{block}" / "metadata")
        own_fixture = any(part.startswith("OWN-") for part in self.path.parts)
        need((qualification_only and own_fixture) or (not qualification_only and self.path.parent in scopes),
             "DYNTEAM_ONLY_NEW_SCOPE_ANONYMOUS_METADATA_DB")
        need(self.path.is_absolute() and self.path.parent.resolve() == self.path.parent and
             not self.path.is_symlink(), "DYNTEAM_ANONYMOUS_JOURNAL_CANONICAL")
        self.qualification_only = qualification_only
        if self.path.exists():
            readonly = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)
            try:
                names = {row[0] for row in readonly.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                need(names == {"roster_batches"}, "DYNTEAM_EXISTING_ONLY_OWN_METADATA_SCHEMA")
            finally:
                readonly.close()
        self.db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False, timeout=0.2)
        os.chmod(self.path, 0o600)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS roster_batches(
            id INTEGER PRIMARY KEY, envelope_sha256 TEXT UNIQUE NOT NULL,
            anonymous_state TEXT NOT NULL, state_sha256 TEXT NOT NULL, anonymous_records TEXT NOT NULL);
          CREATE TRIGGER IF NOT EXISTS roster_no_update BEFORE UPDATE ON roster_batches
            BEGIN SELECT RAISE(ABORT,'append only'); END;
          CREATE TRIGGER IF NOT EXISTS roster_no_delete BEFORE DELETE ON roster_batches
            BEGIN SELECT RAISE(ABORT,'append only'); END;
        ''')
        self.block, self.arm = block, arm
        # SESSION_READY proves model-ready membership, not exact Popen birth or
        # native retirement. Full birth/end hooks are still a separate runtime
        # requirement; do not silently claim a complete physical team timeline.
        self.lifecycle_complete = lifecycle_complete
        self.projection = RosterProjection(block=block, arm=arm, racing_players=7 if arm == "DYNTEAM_RACING" else 0,
                                          observation_basis="FRAMEWORK_NATIVE_BIRTH_END" if lifecycle_complete else "NATIVE_SESSION_READY",
                                          complete_history=lifecycle_complete)
        try:
            row = self.db.execute("SELECT anonymous_state,state_sha256 FROM roster_batches ORDER BY id DESC LIMIT 1").fetchone()
            if row:
                state = json.loads(row[0])
                need(digest(state) == row[1] and state["block"] == block and state["arm"] == arm,
                     "DYNTEAM_ANONYMOUS_JOURNAL_STATE_PIN")
                need(state["complete_history"] is lifecycle_complete,
                     "DYNTEAM_NO_RETROSPECTIVE_FULL_LIFECYCLE_CLAIM")
                self.projection = restore(state)
        except BaseException:
            self.db.close()  # OWN metadata connection only; never a financial handle
            raise
        self._owner_thread = None

    def record_native_session(self, envelope, anchor):
        from native_session_control import checked
        checked(envelope)
        thread = threading.get_ident()
        if self._owner_thread is None:
            self._owner_thread = thread
        need(self._owner_thread == thread and envelope["block"] == self.block,
             "DYNTEAM_SINGLE_ORIGINAL_OWNER_METADATA_PUBLISHER")
        key = digest(envelope)  # hash only; raw native UUID is NOT stored
        staged = restore(snapshot(self.projection))
        records = []
        if self.lifecycle_complete:
            expected = staged._identity(envelope["role_slot"], envelope["logical_birth_sha256"])
            need(staged._live.get(envelope["role_slot"], {}).get("birth") == expected,
                 "DYNTEAM_NATIVE_BIRTH_MUST_BE_DURABLE_BEFORE_MODEL_READY")
        else:
            row = staged.birth(envelope["role_slot"], envelope["logical_birth_sha256"], anchor)
            if row is not None:
                records.append(row)
        row = staged.session(envelope["role_slot"], envelope["logical_birth_sha256"], envelope["native_session_uuid"], anchor)
        if row is not None:
            records.append(row)
        state = snapshot(staged)
        old = self.db.execute("SELECT state_sha256 FROM roster_batches WHERE envelope_sha256=?", (key,)).fetchone()
        if old is not None:
            # A native prompt may use the same session many times. Never emit
            # another birth/session or change historical records for an ACK.
            return self.projection._identity(envelope["role_slot"], envelope["logical_birth_sha256"]), []
        self._commit_batch(key, staged, records)
        return self.projection._identity(envelope["role_slot"], envelope["logical_birth_sha256"]), records

    def _commit_batch(self, key, staged, records):
        state = snapshot(staged)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("INSERT INTO roster_batches(envelope_sha256,anonymous_state,state_sha256,anonymous_records) VALUES(?,?,?,?)",
                            (key, json.dumps(state, sort_keys=True), digest(state), json.dumps(records, sort_keys=True)))
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")  # OWN metadata only, never financial DB
            raise
        self.projection = staged  # only AFTER durable metadata commit

    def record_lifecycle(self, event, role, native_birth_sha256, anchor, *, physical_terminal=False):
        """Sole ORIGINAL owner, after actual launcher/custody proof.

        Idempotent metadata only. Does not launch/stop anything or infer native
        physical evidence from the ledger's financial state.
        """
        need(self.lifecycle_complete and event in ("BIRTH", "END") and
             type(physical_terminal) is bool and type(anchor) is BudgetAnchor and
             type(native_birth_sha256) is str and len(native_birth_sha256) == 64 and
             all(c in "0123456789abcdef" for c in native_birth_sha256),
             "DYNTEAM_EXPLICIT_FULL_LIFECYCLE_EVENT")
        thread = threading.get_ident()
        if self._owner_thread is None:
            self._owner_thread = thread
        need(self._owner_thread == thread, "DYNTEAM_SINGLE_ORIGINAL_OWNER_METADATA_PUBLISHER")
        anchor.checked()
        key = digest(["NATIVE_LIFECYCLE", event, self.arm, self.block, role, native_birth_sha256])
        if self.db.execute("SELECT 1 FROM roster_batches WHERE envelope_sha256=?", (key,)).fetchone():
            return []
        staged = restore(snapshot(self.projection))
        if event == "BIRTH":
            row = staged.birth(role, native_birth_sha256, anchor)
        else:
            row = staged.end(role, native_birth_sha256, anchor, physical_terminal=physical_terminal)
        records = [] if row is None else [row]
        self._commit_batch(key, staged, records)
        return records

    def close(self):
        self.db.close()
