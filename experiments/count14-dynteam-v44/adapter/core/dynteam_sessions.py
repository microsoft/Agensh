"""Mapping consumed by the ORIGINAL scientific relay's affinity lookup.

Native UUIDs are supplied by framework metadata, never parsed from prompts or
model output. No HTTP, CLI/session creation, directory reads or ledger edits.
Only owner-side normal lifecycle hooks may call bind/end, after original relay
inflight for that birth is physically clear. Integration is not yet installed.
"""
from collections.abc import Mapping
from contextlib import contextmanager
import threading
import uuid

from dynteam_metadata import need, catalogue


class AffinityDomain:
    """One shared domain for ALL trajectories in the same original relay."""
    def __init__(self):
        self.lock = threading.Lock()
        self.used = set()

    def claim(self, canonical):
        with self.lock:
            need(canonical not in self.used, "DYNTEAM_SESSION_REUSE_REFUSED")
            self.used.add(canonical)


class DynamicSessions(Mapping):
    def __init__(self, trajectory, *, worker_slots=32, racing_players=0, domain=None):
        need(type(trajectory) is str and 0 < len(trajectory) <= 256, "DYNTEAM_TRAJECTORY")
        self.trajectory = trajectory
        self.roles = catalogue(worker_slots, racing_players=racing_players)
        self._lock = threading.Lock()
        self._current = {}
        # A standalone domain is for OWN/unit use. The cold owner must supply
        # the SAME AffinityDomain to all three mappings before any admission.
        self.domain = AffinityDomain() if domain is None else domain
        need(type(self.domain) is AffinityDomain, "DYNTEAM_SHARED_AFFINITY_DOMAIN")

    def __iter__(self):
        with self._lock:
            return iter(tuple(self._current))

    def __len__(self):
        with self._lock:
            return len(self._current)

    def __getitem__(self, key):
        with self._lock:
            if type(key) is not tuple or len(key) != 2 or key not in self._current:
                raise KeyError(key)
            return self._current[key][1]

    def bind(self, role, birth_sha256, native_session_uuid, *, previous_physical_clear):
        need(role in self.roles, "DYNTEAM_REGISTERED_ROLE")
        need(type(birth_sha256) is str and len(birth_sha256) == 64 and
             all(c in "0123456789abcdef" for c in birth_sha256), "DYNTEAM_BIRTH_DIGEST")
        need(type(native_session_uuid) is str, "DYNTEAM_NATIVE_SESSION_UUID")
        try:
            canonical = str(uuid.UUID(native_session_uuid))
        except (ValueError, AttributeError):
            canonical = None
        need(canonical == native_session_uuid, "DYNTEAM_NATIVE_SESSION_UUID")
        with self._lock:
            key = (self.trajectory, role)
            new = (birth_sha256, canonical)
            if self._current.get(key) == new:
                return False
            need(previous_physical_clear is True, "DYNTEAM_OLD_SESSION_INFLIGHT_RETAIN")
            self.domain.claim(canonical)
            self._current[key] = new
            return True

    def end(self, role, birth_sha256, *, physical_terminal):
        with self._lock:
            key = (self.trajectory, role)
            need(key in self._current and self._current[key][0] == birth_sha256,
                 "DYNTEAM_END_EXACT_SESSION_BIRTH")
            need(physical_terminal is True, "DYNTEAM_NORMAL_PHYSICAL_END_REQUIRED")
            del self._current[key]


class CohortSessions(Mapping):
    """Paired smoke(two), one arm(three) or paired six, one affinity domain."""
    def __init__(self, trajectories, *, worker_slots=32, racing_trajectories=()):
        need(type(trajectories) in (tuple, list) and len(trajectories) in (2, 3, 6) and
             len(set(trajectories)) == len(trajectories), "DYNTEAM_THREE_OR_SIX_DISTINCT_TRAJECTORIES")
        need(type(racing_trajectories) in (tuple, list) and len(set(racing_trajectories)) == len(racing_trajectories)
             and set(racing_trajectories) <= set(trajectories) and
             len(racing_trajectories) in ((1,) if len(trajectories) == 2 else (0, 3)),
             "DYNTEAM_EXPLICIT_PAIRED_RACING_COHORT")
        need(len(trajectories) != 6 or len(racing_trajectories) == 3,
             "DYNTEAM_SIX_TRACKS_REQUIRE_EXACT_PAIRED_ARM")
        domain = AffinityDomain()
        self.tracks = {t: DynamicSessions(t, worker_slots=worker_slots,
                                       racing_players=7 if t in racing_trajectories else 0, domain=domain)
                       for t in trajectories}
        self._request_scope = threading.local()

    def __getitem__(self, key):
        if type(key) is not tuple or len(key) != 2 or key[0] not in self.tracks:
            raise KeyError(key)
        captured = getattr(self._request_scope, "value", None)
        if captured is not None and captured[0] == key:
            return captured[1]
        return self.tracks[key[0]][key]

    def __iter__(self):
        return iter(tuple(key for track in self.tracks.values() for key in track))

    def __len__(self):
        return sum(len(track) for track in self.tracks.values())

    @contextmanager
    def original_request(self, identity):
        """Capture before reserve, retain SAME affinity through physical send.

        No lock is held while the original request waits/runs. An owner metadata
        update cannot change the identity of an already accepted request.
        """
        need(getattr(self._request_scope, "value", None) is None, "DYNTEAM_NO_NESTED_MODEL_SCOPE")
        session = self[identity]  # missing native control is refused before SENT
        self._request_scope.value = (identity, session)
        try:
            yield
        finally:
            del self._request_scope.value
