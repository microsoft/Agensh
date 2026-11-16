"""Anonymous projections of framework lifecycle controls, not a SEARCH loop.

No filesystem/network/SQL/model access, logging threads or callbacks. The owner
must persist returned records outside ALL scientific/ledger locks. A successful
native birth/end is the input, never a desired spawn, CLAIM or model verdict.
Metadata publication failures must HOLD new admission, not replay native work.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import threading

COMMIT = "70e2ca54c078597e3314755064d2ef1a83344c8e"


class ControlRefused(ValueError):
    """Fixed PUBLIC code only; never interpolate an input into the message."""


def need(condition, code):
    if not condition:
        raise ControlRefused(code)


def integer(value, code, minimum=0):
    need(type(value) is int and value >= minimum, code)
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def catalogue(worker_slots=32, *, racing_players=0):
    integer(worker_slots, "DYNTEAM_NATIVE_SLOT_COUNT", 1)
    need(type(racing_players) is int and racing_players in (0, 7), "DYNTEAM_PINNED_RACING_PLAYERS")
    # Native slot capacity is independent of the external FP8 inflight limit.
    roles = {**{f"worker-{i:02d}": "worker" for i in range(worker_slots)},
             "checker-00": "checker", "tester-00": "tester"}
    if racing_players:
        roles.update({"racing-background-00": "racing_background",
                      **{f"racing-player-{i:02d}": "racing_player" for i in range(racing_players)}})
    return roles


@dataclass(frozen=True)
class BudgetAnchor:
    """Values supplied by the ORIGINAL relay's public projection, not estimated."""
    actual_search_tokens: int
    original_event_sequence: int
    utc_ns: int
    monotonic_ns: int

    def checked(self):
        for value in (self.actual_search_tokens, self.original_event_sequence,
                      self.utc_ns, self.monotonic_ns):
            integer(value, "DYNTEAM_ORIGINAL_RELAY_ANCHOR")
        return self


class RosterProjection:
    """Bounded LIVE catalogue, unlimited cumulative logical agent births.

    A metadata lock protects pure in-memory operations only. No wait on native
    capacity, I/O or callable is performed while holding it (ABBA regression).
    New checker conversations use session(), not birth(). A slot reused after
    normal end MUST have a new opaque native birth key.
    """
    def __init__(self, *, block, worker_slots=32, racing_players=0, arm="DYNTEAM",
                 observation_basis="FRAMEWORK_NATIVE_BIRTH_END", complete_history=True):
        need(type(block) is int and block in (1, 2, 3), "DYNTEAM_BLOCK")
        need((arm, racing_players) in (("DYNTEAM", 0), ("DYNTEAM_RACING", 7)),
             "DYNTEAM_EXPLICIT_ANONYMOUS_ARM_CATALOGUE")
        need(observation_basis in ("FRAMEWORK_NATIVE_BIRTH_END", "NATIVE_SESSION_READY") and
             type(complete_history) is bool, "DYNTEAM_EXPLICIT_ROSTER_OBSERVATION_BASIS")
        self.block = block
        self.arm = arm
        self.observation_basis = observation_basis
        self.complete_history = complete_history
        self.roles = catalogue(worker_slots, racing_players=racing_players)
        self._lock = threading.Lock()
        self._live = {}
        self._seen = set()
        self._births = 0
        self._worker_births = 0
        self._sessions = 0
        self._sequence = 0
        self._previous = "0" * 64
        self._anchor = None

    def _identity(self, role, native_birth_key):
        need(type(role) is str and role in self.roles, "DYNTEAM_REGISTERED_ROLE")
        need(type(native_birth_key) is str and 0 < len(native_birth_key) <= 256,
             "DYNTEAM_NATIVE_BIRTH_CONTROL_KEY")
        identity = [COMMIT, self.block, role, native_birth_key]
        return digest(identity if self.arm == "DYNTEAM" else [self.arm, *identity])

    def _check_anchor(self, anchor):
        need(type(anchor) is BudgetAnchor, "DYNTEAM_TYPED_BUDGET_ANCHOR")
        anchor.checked()
        if self._anchor is not None:
            old = self._anchor
            # Never impose a new financial rule: an authorized append-only
            # reconciliation may lower effective charged tokens. Preserve the
            # original value; only CONTROL sequence/time must not regress.
            need(anchor.original_event_sequence >= old.original_event_sequence and
                 anchor.monotonic_ns >= old.monotonic_ns,
                 "DYNTEAM_ANCHOR_REGRESSION_RETAIN_NO_FILL")
        # Wall clock may step backwards; monotonic ordering stays authoritative.

    def _emit(self, kind, role, key, anchor, **extra):
        self._sequence += 1
        self._anchor = anchor
        row = dict(schema="count14-dynteam-anonymous-roster-v1", source_commit=COMMIT,
                   arm=self.arm,
                   block=self.block, sequence=self._sequence, event=kind,
                   role_kind=self.roles[role], role_slot=role, birth_sha256=key,
                   live_workers=sum(self.roles[r] == "worker" for r in self._live),
                   live_model_agents=len(self._live),
                   cumulative_agent_births=self._births,
                   cumulative_worker_births=self._worker_births,
                   cumulative_native_sessions=self._sessions,
                   actual_search_tokens=anchor.actual_search_tokens,
                   original_relay_event_sequence=anchor.original_event_sequence,
                   utc_ns=anchor.utc_ns, monotonic_ns=anchor.monotonic_ns,
                   previous_metadata_sha256=self._previous,
                   observation_basis=self.observation_basis,
                   history_complete_since_scope_birth=self.complete_history, **extra)
        self._previous = digest(row)
        return {**row, "metadata_sha256": self._previous}

    def birth(self, role, native_birth_key, anchor):
        key = self._identity(role, native_birth_key)
        with self._lock:
            if self._live.get(role, {}).get("birth") == key:
                return None  # duplicate observation, not another native birth
            self._check_anchor(anchor)
            need(role not in self._live, "DYNTEAM_OLD_SLOT_NOT_NORMALLY_ENDED")
            need(key not in self._seen, "DYNTEAM_ENDED_AGENT_CANNOT_BE_REVIVED")
            self._live[role] = {"birth": key, "session": None}
            self._seen.add(key)
            self._births += 1
            self._worker_births += self.roles[role] == "worker"
            return self._emit("NATIVE_BIRTH_CONFIRMED", role, key, anchor)

    def session(self, role, native_birth_key, native_session_uuid, anchor):
        import uuid
        key = self._identity(role, native_birth_key)
        need(type(native_session_uuid) is str, "DYNTEAM_NATIVE_SESSION_UUID")
        try:
            canonical = str(uuid.UUID(native_session_uuid))
        except (ValueError, AttributeError):
            raise ControlRefused("DYNTEAM_NATIVE_SESSION_UUID") from None
        need(canonical == native_session_uuid, "DYNTEAM_NATIVE_SESSION_UUID")
        anonymous = digest([COMMIT, self.block, key, canonical])
        with self._lock:
            row = self._live.get(role)
            need(row is not None and row["birth"] == key, "DYNTEAM_SESSION_EXACT_LIVE_BIRTH")
            if row["session"] == anonymous:
                return None
            self._check_anchor(anchor)
            row["session"] = anonymous
            self._sessions += 1
            # Include this anonymous control field BEFORE hashing the record.
            return self._emit("NATIVE_SESSION_BOUND", role, key, anchor,
                              session_sha256=anonymous)

    def end(self, role, native_birth_key, anchor, *, physical_terminal):
        key = self._identity(role, native_birth_key)
        need(physical_terminal is True, "DYNTEAM_NORMAL_PHYSICAL_END_REQUIRED")
        with self._lock:
            row = self._live.get(role)
            need(row is not None and row["birth"] == key, "DYNTEAM_END_EXACT_LIVE_BIRTH")
            self._check_anchor(anchor)
            del self._live[role]
            return self._emit("NATIVE_END_CONFIRMED", role, key, anchor)
