"""
SharedLessons: per-task append-only blackboard for parallel solvers.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

VALID_TYPES = ("FACT", "TRIED", "OBSERVED", "FAIL", "CLAIM", "PATCH_SUMMARY")
MAX_CONTENT_CHARS = 100
# PATCH_SUMMARY uses the structured "files=A | idea=B | evidence=C | risk=D"
# schema, which doesn't fit the 100-char durable-note cap.
MAX_PATCH_SUMMARY_CHARS = 300
_CHARS_PER_TOKEN = 4
_FORMAT_OVERHEAD_CHARS = 25  # "[t{thread}/{TYPE} +{rel_min:.1f}m] " overhead per rendered entry

# CLAIMs: short-lived "thread t is currently working on target X" notes,
# used so peer threads can pick a different angle. TTL'd so abandoned claims
# don't permanently block peers.
#
# The claim is also our only liveness signal. Upstream caps claims per
# (thread, delegation) and suppresses the rest, which is fine there: DeLM gives
# every thread its own container and repo, so nobody needs to know whether a
# peer is alive. We share one repo and one lead, and that lead reassigns an
# issue after 60 minutes of "no action" — where "action" means a pushed branch,
# an opened PR, or a board write. A capped claim plus a 300s TTL gives a worker
# roughly ten visible minutes out of a six-hour task; after that it is
# indistinguishable from a dead one.
#
# Measured on sweep_6.2/typst: worker3 held issue #4 (the eval interpreter),
# went quiet on the board at +4.1m because it was heads-down implementing, and
# was recorded by the lead at +64.8m as "worker3 MIA 60min" and reassigned —
# while running 63-81 tool calls per 15 minutes, the busiest agent on the team.
# The issue was reassigned three times, two competing implementations were
# started, and all five of worker3's PRs were discarded. Its PR #23 arrived at
# +114.6m with 3089 additions and passed 82/85 of the lead's own checks.
#
# So a claim must be repeatable: refreshing it is how a worker says "still on
# it". Expiry still reaps genuinely abandoned claims, and the render path is
# bounded by _MAX_RENDERED_CLAIMS, so removing the cap costs nothing visible.
#
# TTL is 1h, not the original 300s. 300s was never matched to anything real: a
# sub-issue runs for tens of minutes to hours, agents post a claim once rather
# than renewing it on a timer, and nothing in either role prompt tells them to
# refresh. So a claim was visible for the first ~5 minutes of the work it
# described and absent for the rest -- which is precisely the worker3 incident
# above, where the claim had long expired by the time the lead went looking for
# a liveness signal. 1h is the order of a real work item. The cost of the longer
# window is a stale claim from a crashed agent steering peers away for up to an
# hour; that is strictly better than the current behaviour, where the claim is
# gone before anyone can act on it.
DEFAULT_CLAIM_TTL_SECONDS = 3600
DEFAULT_CLAIM_WINDOW_TOKENS = 100
_MAX_RENDERED_CLAIMS = 6

# PATCH_SUMMARY: one current candidate-fix summary per (thread, delegation).
# The latest valid summary replaces the prior one in memory rather than being
# suppressed, so peers see refined evidence rather than a stale early candidate.
MAX_PATCH_SUMMARIES_PER_DELEGATION = 1
DEFAULT_PATCH_SUMMARY_WINDOW_TOKENS = 200  # separate from claims/durable budgets
_MAX_RENDERED_PATCH_SUMMARIES = 4
_MAX_SELECTIVE_UNFOLDED_FAILURES = 5

# Concrete-evidence markers used to mark an OBSERVED note as worth keeping
# in the sticky tier (i.e. it names a path/symbol/test/error).
_CONCRETE_TOKENS = ("::", "FAILED", "PASSED", "ERROR", "Exception", "Traceback", ".py", "/", "()")
_CONCRETE_PATTERNS = (
    re.compile(r"\b(?:exit|status|code)\s*[=:]?\s*\d+\b", re.IGNORECASE),
    re.compile(r"\bline\s+\d+\b", re.IGNORECASE),
    re.compile(r"\b[\w./-]+\.py(?::\d+)?\b"),
)

# Lines that explicitly mean "no notes this turn".
_NONE_TOKENS = ("(none)", "none", "-", "—")
_PEER_DIGEST_SPECULATIVE_HINTS = (
    "likely", "probably", "maybe", "might", "suspect", "speculative",
    "candidate", "guess", "appears", "seems",
)
_PATCH_SUMMARY_WEAK_EVIDENCE = (
    "pending", "not verified", "unverified", "should", "will verify",
    "to be verified", "tbd", "looks", "seems",
)
_PATCH_SUMMARY_SOLID_EVIDENCE_RE = re.compile(
    r"\b(pass(?:ed|es)?|verified|confirmed|no longer|now returns|now produces)\b",
    re.IGNORECASE,
)
_MAX_PEER_DIGEST_ENTRIES = 12
_MAX_PEER_DIGEST_BY_TYPE = {
    "PATCH_SUMMARY": 2,
    "FAIL": 3,
    "OBSERVED": 5,
    "FACT": 6,
}

_TRIED_ROUTINE_VERB_PREFIXES = (
    "search", "searched", "searching", "search_file",
    "grep", "grepped", "grepping",
    "find", "found", "finding",
    "ls", "list", "listed", "listing",
    "open", "opened", "opening",
    "view", "viewed", "viewing",
    "cat", "less", "head", "tail",
    "look", "looked", "looking",
    "ran ls", "ran grep", "ran find", "ran search", "ran search_file",
)

_TRIED_FAILURE_HINTS = (
    "fail", "failed", "incorrect", "wrong", "invalid",
    "no match", "no matches", "not found", "no result", "no results",
    "empty", "could not", "couldn't", "doesn't exist", "no such",
    "0 result", "exception", "error", "broke", "broken",
)

def _parse_patch_summary_field(content: str, field_name: str) -> Optional[str]:
    prefix = field_name.lower() + "="
    for part in str(content or "").split("|"):
        s = part.strip()
        if s.lower().startswith(prefix):
            return s[len(prefix):].strip()
    return None

def _compact_text(text: Any, limit: int) -> str:
    s = " ".join(str(text or "").split())
    if limit > 0 and len(s) > limit:
        return s[:limit].rstrip()
    return s


def parse_note_body(text: str) -> List[Dict[str, str]]:
    notes: List[Dict[str, str]] = []
    if not text:
        return notes
    for raw in str(text).strip().split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.lower() in _NONE_TOKENS:
            continue
        if line.startswith("#") or line.startswith("("):
            continue
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        t = parts[0].upper()
        if t not in VALID_TYPES:
            continue
        content = parts[1].strip()
        if content.lower() in _NONE_TOKENS:
            continue
        notes.append({"type": t, "content": content})
    return notes

class SharedLessonsError(ValueError):
    """Raised on invalid type or oversized content."""

class SharedLessons:
    """Per-task shared blackboard.

    All instances are scoped to a single task (one per task per run). Writes
    are serialized with an asyncio.Lock; reads grab a snapshot under the lock
    then window outside it.
    """

    DEFAULT_FEATURE_FLAGS = {
        "tried_admission_filter": True,
        "patch_summary_enabled": True,
        "claims_enabled": True,
        "patch_summary_latest_wins_enabled": False,
        "patch_summary_lifecycle_enabled": False,
    }

    def __init__(self, task_id: str, file_path: Optional[Path] = None,
                 feature_flags: Optional[Dict[str, bool]] = None):
        self.task_id = task_id
        self._entries: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._start_time = time.time()
        self._file_path = Path(file_path) if file_path else None
        # Merge caller's flags onto the defaults; unknown keys are ignored.
        self.feature_flags: Dict[str, bool] = dict(self.DEFAULT_FEATURE_FLAGS)
        if feature_flags:
            for k, v in feature_flags.items():
                if k in self.feature_flags:
                    self.feature_flags[k] = bool(v)
        self._render_counts: Dict[Tuple[Any, str], int] = {}

    async def note(self, thread_id: int, type: str, content: str,
                   delegation_id: Optional[int] = None,
                   ttl_seconds: Optional[float] = None,
                   task_instruction: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Append one entry. Returns the entry on success; raises on bad input.
        """
        if type not in VALID_TYPES:
            raise SharedLessonsError(
                f"invalid type {type!r}; must be one of {VALID_TYPES}"
            )
        if type == "PATCH_SUMMARY" and not self.feature_flags.get("patch_summary_enabled", False):
            return None
        if type == "CLAIM" and not self.feature_flags.get("claims_enabled", False):
            return None
        content = (content or "").strip()
        if not content:
            raise SharedLessonsError("content is empty after strip()")
        if content.lower() in _NONE_TOKENS:
            return None
        type_cap = MAX_PATCH_SUMMARY_CHARS if type == "PATCH_SUMMARY" else MAX_CONTENT_CHARS
        if len(content) > type_cap:
            raise SharedLessonsError(
                f"content too long for {type}: {len(content)} > {type_cap} chars"
            )
        if (type == "TRIED"
                and self.feature_flags.get("tried_admission_filter", True)
                and self._is_routine_tried(content)):
            try:
                from base.engine.logs import logger as _logger
                _logger.info(
                    f"[SharedLessons] [{self.task_id}] suppressed routine TRIED "
                    f"from t{thread_id}: {content[:80]!r}"
                )
            except Exception:
                pass
            return None
        now_ts = time.time()
        expires_at: Optional[float] = None
        if type == "CLAIM":
            ttl = float(ttl_seconds) if ttl_seconds is not None else DEFAULT_CLAIM_TTL_SECONDS
            expires_at = now_ts + max(0.0, ttl)
        entry = {
            "ts": now_ts,
            "thread_id": thread_id,
            "type": type,
            "content": content,
            "delegation_id": (delegation_id if delegation_id is not None else None),
            "_expires_at": expires_at,  # None for non-CLAIM (and CLAIM with ttl=None should also default)
        }
        if task_instruction:
            entry["task"] = _compact_text(task_instruction, 300)
        patch_lifecycle_enabled = self.feature_flags.get("patch_summary_lifecycle_enabled", False)
        if (
            patch_lifecycle_enabled
            and type == "PATCH_SUMMARY"
            and self._is_verified_patch_summary_checkpoint(content)
        ):
            entry["_verified_checkpoint"] = True
        norm_delegation = delegation_id if delegation_id is not None else None
        norm_thread = thread_id
        async with self._lock:
            if type == "PATCH_SUMMARY" and patch_lifecycle_enabled:
                fail_count = self._delegation_fail_count(
                    self._entries, norm_thread, norm_delegation
                )
                if fail_count:
                    entry["_local_fail_count"] = fail_count
            if type == "FAIL" and patch_lifecycle_enabled:
                fail_count = self._delegation_fail_count(
                    self._entries, norm_thread, norm_delegation
                ) + 1
                for e in reversed(self._entries):
                    if (
                        e.get("type") == "PATCH_SUMMARY"
                        and e.get("thread_id") == norm_thread
                        and e.get("delegation_id") == norm_delegation
                        and not e.get("_finalized")
                    ):
                        e.pop("_verified_checkpoint", None)
                        e["_invalidated_by_fail"] = content[:MAX_CONTENT_CHARS]
                        e["_invalidated_ts"] = now_ts
                        e["_local_fail_count"] = fail_count
                        entry["_grounded_patch_fail"] = True
                        break
            if type == "PATCH_SUMMARY":
                existing_idx: Optional[int] = None
                for i in range(len(self._entries) - 1, -1, -1):
                    e = self._entries[i]
                    if (
                        e.get("type") == "PATCH_SUMMARY"
                        and e.get("thread_id") == norm_thread
                        and e.get("delegation_id") == norm_delegation
                    ):
                        existing_idx = i
                        break
                if existing_idx is not None:
                    if not self.feature_flags.get("patch_summary_latest_wins_enabled", False):
                        try:
                            from base.engine.logs import logger as _logger
                            _logger.info(
                                f"[SharedLessons] [{self.task_id}] suppressed PATCH_SUMMARY "
                                f"from t{norm_thread}/d{norm_delegation} (cap "
                                f"{MAX_PATCH_SUMMARIES_PER_DELEGATION} reached): {content[:80]!r}"
                            )
                        except Exception:
                            pass
                        return None
                    previous = self._entries[existing_idx]
                    entry["_first_ts"] = previous.get("_first_ts", previous.get("ts", entry["ts"]))
                    entry["_last_ts"] = entry["ts"]
                    entry["_replaces_ts"] = previous.get("ts")
                    self._entries[existing_idx] = entry
                    if self._file_path is not None:
                        try:
                            self._file_path.parent.mkdir(parents=True, exist_ok=True)
                            with self._file_path.open("a", encoding="utf-8") as f:
                                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                        except Exception:
                            pass
                    return entry
            self._entries.append(entry)
            if self._file_path is not None:
                try:
                    self._file_path.parent.mkdir(parents=True, exist_ok=True)
                    with self._file_path.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                except Exception:
                    # Disk failure must not break in-memory state — the
                    # in-memory copy is the authoritative read path.
                    pass
        return entry

    async def mark_patch_summary_final(
        self,
        thread_id: int,
        delegation_id: Optional[int],
        content: Optional[str] = None,
    ) -> bool:
        """Mark this delegation's latest PATCH_SUMMARY as finish-done handoff.

        ImplementerAgents may write PATCH_SUMMARY before they finish so PlannerAgent can
        see a local candidate, but peer threads should trust summaries more
        when they came from an explicit `finish done` handoff. This metadata is
        oracle-free: it records only the agent's own lifecycle status, not
        grader/eval success.
        """
        if not self.feature_flags.get("patch_summary_lifecycle_enabled", False):
            return False
        norm_thread = thread_id
        norm_delegation = delegation_id if delegation_id is not None else None
        wanted = (content or "").strip()
        now_ts = time.time()
        updated: Optional[Dict[str, Any]] = None
        async with self._lock:
            for e in reversed(self._entries):
                if (
                    e.get("type") == "PATCH_SUMMARY"
                    and e.get("thread_id") == norm_thread
                    and e.get("delegation_id") == norm_delegation
                    and (not wanted or str(e.get("content", "")).strip() == wanted)
                ):
                    e["_finalized"] = True
                    e["_finalized_ts"] = now_ts
                    updated = dict(e)
                    break
        if updated is None:
            return False
        if self._file_path is not None:
            try:
                self._file_path.parent.mkdir(parents=True, exist_ok=True)
                with self._file_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(updated, ensure_ascii=False) + "\n")
            except Exception:
                pass
        return True

    def _is_concrete(self, content: str) -> bool:
        """Heuristic: does an OBSERVED note name concrete, expensive-to-rediscover
        evidence (path / symbol / test / error) vs vague progress chatter?"""
        lowered = content.lower()
        return (
            any(t.lower() in lowered for t in _CONCRETE_TOKENS)
            or any(p.search(content) for p in _CONCRETE_PATTERNS)
        )

    @staticmethod
    def _is_expired_claim(entry: Dict[str, Any], now_ts: Optional[float] = None) -> bool:
        """True if this is a CLAIM whose `_expires_at` has passed.

        Non-CLAIM entries (and CLAIMs with `_expires_at=None`, which would
        signal "never expires" — currently unused but allowed) return False.
        Used to filter expired claims out of selection / render so abandoned
        claims don't permanently block peer work.
        """
        if entry.get("type") != "CLAIM":
            return False
        exp = entry.get("_expires_at")
        if exp is None:
            return False
        return (now_ts if now_ts is not None else time.time()) > float(exp)

    def _is_routine_tried(self, content: str) -> bool:
        """should this TRIED note be SUPPRESSED at write time?

        True iff the content is pure search/open verb chatter with no
        concrete evidence (path/symbol/error/line) and no reusable
        failure language. False otherwise (admit). Conservative —
        default-admit when uncertain. Only consulted for TRIED type.
        """
        if not content:
            return False  # let the existing empty-content guard reject it
        if self._is_concrete(content):
            return False  # reusable concrete result
        low = content.lower().strip()
        if any(h in low for h in _TRIED_FAILURE_HINTS):
            return False  # reusable failure (dead end peers should avoid)
        # First 2 words = the "verb phrase". Catches "ran grep" / "search_file".
        first_two = " ".join(low.split()[:2])
        first_one = first_two.split(" ")[0] if first_two else ""
        return any(first_two.startswith(v) or first_one == v
                   for v in _TRIED_ROUTINE_VERB_PREFIXES)

    def _is_verified_patch_summary_checkpoint(self, content: str) -> bool:
        """
        True when a PATCH_SUMMARY has concrete local verification evidence.
        """
        evidence = _parse_patch_summary_field(content, "evidence")
        if not evidence:
            return False
        low = evidence.strip().lower()
        if not low:
            return False
        if any(w in low for w in _PATCH_SUMMARY_WEAK_EVIDENCE):
            return False
        return bool(_PATCH_SUMMARY_SOLID_EVIDENCE_RE.search(evidence))

    def _priority(self, e: Dict[str, Any]) -> int:
        t = e.get("type")
        if t == "PATCH_SUMMARY":
            return -1
        if t == "FACT" or (t == "OBSERVED" and self._is_concrete(str(e.get("content", "")))):
            return 0   # durable evidence
        if t == "FAIL":
            return 1   # dead ends worth avoiding
        if t == "OBSERVED":
            return 2
        if t == "TRIED":
            return 3   # TRIED — most ephemeral / coordination noise
        return 4       # CLAIM — coordination only, normally rendered in its
                       # own section and stripped before this function runs;
                       # this value only matters as a defensive fallback.

    @staticmethod
    def _dedupe_key(entry: Dict[str, Any]) -> Tuple[Any, str]:
        return (entry.get("type"), " ".join(str(entry.get("content", "")).split()))

    @staticmethod
    def _render_count_key(entry: Dict[str, Any]) -> Tuple:
        if entry.get("type") == "CLAIM":
            return (
                "CLAIM",
                entry.get("thread_id"),
                entry.get("delegation_id"),
                float(entry.get("_first_ts", entry.get("ts", 0.0))),
            )
        return SharedLessons._dedupe_key(entry)

    @staticmethod
    def _delegation_fail_count(
        entries: List[Dict[str, Any]],
        thread_id: int,
        delegation_id: Optional[int],
    ) -> int:
        return sum(
            1 for e in entries
            if e.get("type") == "FAIL"
            and e.get("thread_id") == thread_id
            and e.get("delegation_id") == delegation_id
        )

    @staticmethod
    def _patch_failure_count(entry: Dict[str, Any]) -> int:
        try:
            return max(0, int(entry.get("_local_fail_count", 0) or 0))
        except (TypeError, ValueError):
            return 0

    def _patch_failure_suffix(self, entry: Dict[str, Any]) -> str:
        fail_count = self._patch_failure_count(entry)
        return f" [local_failures={fail_count}]" if fail_count else ""

    def _patch_status_values(self, entry: Dict[str, Any]) -> List[str]:
        """
        Compact PATCH_SUMMARY lifecycle tags.
        """
        if entry.get("type") != "PATCH_SUMMARY":
            return []
        status: List[str] = []
        if entry.get("_finalized"):
            status.append("final")
        if entry.get("_verified_checkpoint"):
            status.append("verified")
        if entry.get("_invalidated_by_fail") and not entry.get("_finalized"):
            status.append("invalidated")
        fail_count = self._patch_failure_count(entry)
        if fail_count:
            status.append(f"local_failures={fail_count}")
        return status

    def _patch_status_suffix(self, entry: Dict[str, Any]) -> str:
        if not self.feature_flags.get("patch_summary_lifecycle_enabled", False):
            return ""
        status = self._patch_status_values(entry)
        return f" [status={','.join(status)}]" if status else ""

    def _patch_lifecycle_fields(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Oracle-free PATCH_SUMMARY diagnostics for lifecycle.jsonl."""
        if entry.get("type") != "PATCH_SUMMARY":
            return {
                "patch_status": "",
                "is_finalized": False,
                "is_verified_checkpoint": False,
                "local_failures": 0,
                "invalidated_by_fail": False,
                "invalidated_reason": "",
            }
        return {
            "patch_status": ",".join(self._patch_status_values(entry)),
            "is_finalized": bool(entry.get("_finalized")),
            "is_verified_checkpoint": bool(entry.get("_verified_checkpoint")),
            "local_failures": self._patch_failure_count(entry),
            "invalidated_by_fail": bool(entry.get("_invalidated_by_fail")),
            "invalidated_reason": str(entry.get("_invalidated_by_fail", "") or ""),
        }

    _SEM_FILE_RE = re.compile(r"\b([A-Za-z0-9_./\-]+\.py)\b")
    _SEM_DEFCLASS_RE = re.compile(r"\b(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)")
    _SEM_LINE_RE = re.compile(r"(?:\bline\s+(\d+)\b|\.py:(\d+)\b)", re.IGNORECASE)
    _SEM_ERROR_RE = re.compile(r"\b([A-Z][A-Za-z]*(?:Error|Exception|Warning))\b")
    _SEM_TEST_RE = re.compile(r"\b(test_[A-Za-z0-9_]+(?:\.py)?(?:::[A-Za-z0-9_:]+)?)\b")

    def _semantic_key(self, entry: Dict[str, Any]) -> Optional[Tuple]:
        """canonical signature for cross-paraphrase dedupe.

        Returns a hashable key derived from extracted features
        (file paths, def/class names, line numbers, error classes,
        pytest targets) along with the entry's type. Returns None when
        the extracted features are too WEAK to safely identify
        "same fact" — those entries fall back to exact-dedupe only.
        """
        content = str(entry.get("content", ""))
        files = tuple(sorted(set(m.group(1) for m in self._SEM_FILE_RE.finditer(content))))
        syms = tuple(sorted(set(m.group(1) for m in self._SEM_DEFCLASS_RE.finditer(content))))
        # The line regex has two alternative capture groups; pick whichever fired.
        lines_raw = []
        for m in self._SEM_LINE_RE.finditer(content):
            for g in m.groups():
                if g is not None:
                    try:
                        lines_raw.append(int(g))
                    except ValueError:
                        pass
        lines = tuple(sorted(set(lines_raw)))
        errors = tuple(sorted(set(m.group(1) for m in self._SEM_ERROR_RE.finditer(content))))
        tests = tuple(sorted(set(m.group(1) for m in self._SEM_TEST_RE.finditer(content))))

        has_file, has_sym, has_line = bool(files), bool(syms), bool(lines)
        has_err, has_test = bool(errors), bool(tests)
        strong = (
            (has_file and has_sym)
            or (has_file and has_line)
            or (has_file and has_test)
            or (has_err and (has_file or has_line or has_test))
            or has_test  # pytest target is itself precise
        )
        if not strong:
            return None
        return (entry.get("type"), files, syms, lines, errors, tests)

    def _dedupe_entries(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Collapse exact + semantic duplicate notes without mutating
        append-only storage.

        Pass 1 — exact dedupe (legacy behavior): collapses entries with
        identical (type, normalized-content) pairs. First occurrence is
        the displayed entry; subsequent identicals bump the `_dup`
        counter and merge thread/delegation ids.

        Pass 2 — semantic dedupe (): groups entries of the SAME
        type whose `_semantic_key` matches. Different paraphrases of the
        same fact collapse into the FIRST one seen; subsequent matches
        bump `_dup` on the survivor. Entries with no extractable
        features (`_semantic_key` returns None) skip this pass and stay
        as separate renderable entries — exactly the legacy behavior.
        Cross-type collapse is NOT possible (the type is in the key).
        """
        non_claims = [e for e in entries
                      if e.get("type") not in ("CLAIM", "PATCH_SUMMARY")]
        claims_raw = [e for e in entries if e.get("type") == "CLAIM"]
        patches_raw = [e for e in entries if e.get("type") == "PATCH_SUMMARY"]
        deduped: List[Dict[str, Any]] = []
        index: Dict[Tuple[Any, str], Dict[str, Any]] = {}
        for e in non_claims:
            key = self._dedupe_key(e)
            ts = float(e.get("ts", 0.0))
            if key in index:
                prior = index[key]
                prior["_dup"] = prior.get("_dup", 1) + 1
                prior["_last_ts"] = max(float(prior.get("_last_ts", prior.get("ts", 0.0))), ts)
                thread_ids = prior.setdefault("_thread_ids", [])
                tid = e.get("thread_id")
                if tid not in thread_ids:
                    thread_ids.append(tid)
                deleg_ids = prior.setdefault("_delegation_ids", [])
                did = e.get("delegation_id")
                if did not in deleg_ids:
                    deleg_ids.append(did)
            else:
                ee = dict(e)
                ee["_dup"] = 1
                ee["_first_ts"] = ts
                ee["_last_ts"] = ts
                ee["_thread_ids"] = [e.get("thread_id")]
                ee["_delegation_ids"] = [e.get("delegation_id")]
                index[key] = ee
                deduped.append(ee)

        sem_index: Dict[Tuple, Dict[str, Any]] = {}
        final: List[Dict[str, Any]] = []
        for ee in deduped:
            sk = self._semantic_key(ee)
            if sk is None:
                final.append(ee)
                continue
            prior = sem_index.get(sk)
            if prior is None:
                sem_index[sk] = ee
                final.append(ee)
                continue
            # Semantic collapse: merge ee into prior. Bump _dup by ee's
            # current _dup (carries any exact-dedupe count it accrued).
            prior["_dup"] = int(prior.get("_dup", 1)) + int(ee.get("_dup", 1))
            prior["_last_ts"] = max(
                float(prior.get("_last_ts", prior.get("ts", 0.0))),
                float(ee.get("_last_ts", ee.get("ts", 0.0))),
            )
            for tid in (ee.get("_thread_ids") or []):
                if tid not in prior.setdefault("_thread_ids", []):
                    prior["_thread_ids"].append(tid)
            for did in (ee.get("_delegation_ids") or []):
                if did not in prior.setdefault("_delegation_ids", []):
                    prior["_delegation_ids"].append(did)

        for e in claims_raw + patches_raw:
            ee = dict(e)
            ts = float(e.get("ts", 0.0))
            ee.setdefault("_dup", 1)
            ee.setdefault("_first_ts", ts)
            ee.setdefault("_last_ts", ts)
            ee.setdefault("_thread_ids", [e.get("thread_id")])
            ee.setdefault("_delegation_ids", [e.get("delegation_id")])
            final.append(ee)
        return final

    def _matched_self(self, e: Dict[str, Any], viewer_thread_id: Optional[int],
                      viewer_delegation_id: Optional[int], self_policy: str) -> bool:
        """True if a (deduped) note group is EXCLUSIVELY the viewer's own — so it's
        safe to demote/exclude (the viewer already has it in local memory). A group
        corroborated by ANY peer thread is never treated as self. Backward-compat:
        entries without delegation_id are never matched by the current-delegation
        policies (kept), since we can't prove they're the current run."""
        if viewer_thread_id is None:
            return False
        tids = e.get("_thread_ids") or [e.get("thread_id")]
        if set(tids) != {viewer_thread_id}:
            return False
        if self_policy == "demote_thread":
            return True  # any delegation on this thread (fallback when no delegation id)
        if viewer_delegation_id is None:
            return False
        raw_dids = e.get("_delegation_ids") or [e.get("delegation_id")]
        if any(d is None for d in raw_dids):
            return False
        dids = [d for d in raw_dids if d is not None]
        return bool(dids) and set(dids) == {viewer_delegation_id}

    def _select_entries(
        self,
        entries: List[Dict[str, Any]],
        window_tokens: int = 500,
        viewer_thread_id: Optional[int] = None,
        viewer_delegation_id: Optional[int] = None,
        self_policy: str = "include",
        count_render: bool = True,
        claim_window_tokens: int = DEFAULT_CLAIM_WINDOW_TOKENS,
        patch_summary_window_tokens: int = DEFAULT_PATCH_SUMMARY_WINDOW_TOKENS,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        # window_tokens <= 0 means UNLIMITED: render the whole board.
        #
        # Sweep 6.3 measured 91 overlap incidents (169,566 wasted lines) in which
        # the second agent never saw a peer's CLAIM on the work it was starting.
        # A windowed render made an absent CLAIM ambiguous between "nobody
        # claimed this" and "it was dropped by the budget or the 6-claim cap",
        # which is fatal to the rule the lead is given ("a fresh CLAIM means they
        # are mid-implementation, not stuck") — absence carried no information.
        # A whole run's board is small: 126 entries / ~4k tokens over 6 hours.
        # See tests/pbench-board/test_full_board.py.
        unlimited = window_tokens <= 0
        # A large int rather than math.inf: these budgets flow into int() and
        # into arithmetic downstream (e.g. the PROTECTED_RESERVE_FRACTION
        # reserve), and infinity raises OverflowError there.
        _NO_LIMIT = 10 ** 12
        chars_budget = _NO_LIMIT if unlimited else window_tokens * _CHARS_PER_TOKEN
        claim_chars_budget = _NO_LIMIT if unlimited else max(claim_window_tokens, 0) * _CHARS_PER_TOKEN
        patch_chars_budget = _NO_LIMIT if unlimited else max(patch_summary_window_tokens, 0) * _CHARS_PER_TOKEN
        deduped_pre_expiry = self._dedupe_entries(entries)

        now_ts = time.time()
        deduped = [e for e in deduped_pre_expiry if not self._is_expired_claim(e, now_ts)]

        pool = deduped
        self_excluded: List[Dict[str, Any]] = []
        if self_policy == "exclude_current":
            self_excluded = [
                e for e in deduped
                if self._matched_self(e, viewer_thread_id, viewer_delegation_id, self_policy)
            ]
            self_excluded_ids = {id(e) for e in self_excluded}
            pool = [e for e in deduped if id(e) not in self_excluded_ids]

        claim_self_excluded = [
            e for e in pool
            if e.get("type") == "CLAIM"
            and self_policy in ("demote_current", "demote_thread", "exclude_current")
            and self._matched_self(
                e,
                viewer_thread_id,
                viewer_delegation_id,
                "demote_thread" if self_policy == "exclude_current" else self_policy,
            )
        ]
        if claim_self_excluded:
            self_excluded.extend(claim_self_excluded)
        claim_self_excluded_ids = {id(e) for e in claim_self_excluded}
        claim_pool = [
            e for e in pool
            if e.get("type") == "CLAIM"
            and id(e) not in claim_self_excluded_ids
        ]
        claim_pool.sort(key=lambda x: -float(x.get("_last_ts", x.get("ts", 0.0))))
        claim_kept: List[Dict[str, Any]] = []
        claim_used = 0
        claim_cap = len(claim_pool) if unlimited else _MAX_RENDERED_CLAIMS
        for e in claim_pool[:claim_cap]:
            sz = self._entry_size(e)
            if claim_used + sz > claim_chars_budget:
                continue
            claim_used += sz
            claim_kept.append(e)
        pool = [e for e in pool if e.get("type") != "CLAIM"]

        patch_self_excluded = [
            e for e in pool
            if e.get("type") == "PATCH_SUMMARY"
            and self_policy in ("demote_current", "demote_thread", "exclude_current")
            and self._matched_self(
                e,
                viewer_thread_id,
                viewer_delegation_id,
                "demote_thread" if self_policy == "exclude_current" else self_policy,
            )
        ]
        if patch_self_excluded:
            self_excluded.extend(patch_self_excluded)
        patch_self_excluded_ids = {id(e) for e in patch_self_excluded}
        patch_pool = [
            e for e in pool
            if e.get("type") == "PATCH_SUMMARY"
            and id(e) not in patch_self_excluded_ids
        ]
        patch_pool.sort(key=lambda x: -float(x.get("_last_ts", x.get("ts", 0.0))))
        patch_kept: List[Dict[str, Any]] = []
        patch_used = 0
        # Same conditional as claim_cap above; this one was missed. With
        # BOARD_WINDOW_TOKENS unset (unlimited -- the shipped config) the whole
        # board rendered EXCEPT patch summaries, still capped at 4. The pool is
        # sorted newest-first, so the OLDEST summaries silently vanished from
        # every prompt while staying visible in /read_all.
        patch_cap = len(patch_pool) if unlimited else _MAX_RENDERED_PATCH_SUMMARIES
        for e in patch_pool[:patch_cap]:
            sz = self._entry_size(e)
            if patch_used + sz > patch_chars_budget:
                continue
            patch_used += sz
            patch_kept.append(e)
        pool = [e for e in pool if e.get("type") != "PATCH_SUMMARY"]

        def _key(x: Dict[str, Any]):
            demote = (self_policy in ("demote_current", "demote_thread")
                      and self._matched_self(x, viewer_thread_id, viewer_delegation_id, self_policy))
            base_prio = self._priority(x) + (1000 if demote else 0)
            recency = -float(x.get("_last_ts", x.get("ts", 0.0)))
            return (base_prio, recency)

        PROTECTED_RESERVE_FRACTION = 0.35
        reserve_chars = int(chars_budget * PROTECTED_RESERVE_FRACTION)

        def _is_protected(e: Dict[str, Any]) -> bool:
            t = e.get("type")
            if t == "FAIL":
                return True
            if t == "OBSERVED" and self._is_concrete(str(e.get("content", ""))):
                return True
            return False

        kept: List[Dict[str, Any]] = []
        used = 0
        kept_ids: set = set()
        if reserve_chars > 0:
            protected_pool = [
                e for e in pool
                if _is_protected(e)
                and not (
                    self_policy in ("demote_current", "demote_thread")
                    and self._matched_self(e, viewer_thread_id, viewer_delegation_id, self_policy)
                )
            ]
            protected_pool.sort(key=lambda x: -float(x.get("_last_ts", x.get("ts", 0.0))))
            reserve_used = 0
            for e in protected_pool:
                sz = self._entry_size(e)
                if reserve_used + sz > reserve_chars:
                    continue
                reserve_used += sz
                kept.append(e)
                kept_ids.add(id(e))
            used = reserve_used

        for e in sorted(pool, key=_key):
            if id(e) in kept_ids:
                continue
            sz = self._entry_size(e)
            if used + sz > chars_budget:
                continue
            used += sz
            kept.append(e)
            kept_ids.add(id(e))

        kept.extend(claim_kept)
        kept.extend(patch_kept)

        if count_render:
            for e in kept:
                key = self._render_count_key(e)  # 
                self._render_counts[key] = self._render_counts.get(key, 0) + 1

        kept_ids = {id(e) for e in kept}
        kept.sort(key=lambda e: e["ts"])
        stats = self._build_stats(
            entries=entries,
            deduped=deduped,
            kept=kept,
            kept_ids=kept_ids,
            used_chars=used,
            chars_budget=chars_budget,
            window_tokens=window_tokens,
            viewer_thread_id=viewer_thread_id,
            viewer_delegation_id=viewer_delegation_id,
            claim_used_chars=claim_used,
            claim_chars_budget=claim_chars_budget,
            deduped_pre_expiry=deduped_pre_expiry,
            self_excluded=self_excluded,
            patch_used_chars=patch_used,
            patch_chars_budget=patch_chars_budget,
        )
        return kept, stats

    def _type_counts(self, entries: List[Dict[str, Any]], raw_dups: bool = False) -> Dict[str, int]:
        counts = {t: 0 for t in VALID_TYPES}
        for e in entries:
            t = e.get("type")
            if t in counts:
                counts[t] += int(e.get("_dup", 1)) if raw_dups else 1
        return counts

    def _build_stats(
        self,
        entries: List[Dict[str, Any]],
        deduped: List[Dict[str, Any]],
        kept: List[Dict[str, Any]],
        kept_ids: set,
        used_chars: int,
        chars_budget: int,
        window_tokens: int,
        viewer_thread_id: Optional[int],
        viewer_delegation_id: Optional[int] = None,
        claim_used_chars: int = 0,
        claim_chars_budget: int = 0,
        deduped_pre_expiry: Optional[List[Dict[str, Any]]] = None,
        self_excluded: Optional[List[Dict[str, Any]]] = None,
        patch_used_chars: int = 0,
        patch_chars_budget: int = 0,
    ) -> Dict[str, Any]:
        if deduped_pre_expiry is None:
            deduped_pre_expiry = deduped
        if self_excluded is None:
            self_excluded = []
        self_excluded_ids = {id(e) for e in self_excluded}
        # Only budget/window omissions are "dropped". Entries intentionally
        # hidden by viewer self-policy are tracked separately so they do not
        # create false overflow in ImplementerAgent render stats.
        dropped_unique = [
            e for e in deduped
            if id(e) not in kept_ids and id(e) not in self_excluded_ids
        ]
        dropped_raw_count = sum(int(e.get("_dup", 1)) for e in dropped_unique)
        stats: Dict[str, Any] = {
            "task_id": self.task_id,
            "window_tokens": int(window_tokens),
            "budget_chars": chars_budget,
            "claim_budget_chars": int(claim_chars_budget),
            "patch_summary_budget_chars": int(patch_chars_budget),
            "durable_rendered_chars_estimate": int(used_chars),
            "claim_rendered_chars_estimate": int(claim_used_chars),
            "patch_summary_rendered_chars_estimate": int(patch_used_chars),
            # Headline is the FULL prompt footprint: durable + claim + patch.
            "rendered_chars_estimate": int(used_chars) + int(claim_used_chars) + int(patch_used_chars),
            "stored_entries": len(entries),
            # Dedupe-collapse view (legacy semantics, expiry-agnostic):
            "unique_entries": len(deduped_pre_expiry),
            "duplicates_suppressed": max(0, len(entries) - len(deduped_pre_expiry)),
            "stored_by_type": self._type_counts(entries),
            "unique_by_type": self._type_counts(deduped_pre_expiry),
            # Post-expiry view (what selection actually operates on):
            "live_unique_entries": len(deduped),
            "live_unique_by_type": self._type_counts(deduped),
            "expired_claims_excluded": max(0, len(deduped_pre_expiry) - len(deduped)),
            "self_excluded_entries": len(self_excluded),
            "self_excluded_by_type": self._type_counts(self_excluded),
            "rendered_entries": len(kept),
            "dropped_unique_entries": len(dropped_unique),
            "dropped_raw_entries": dropped_raw_count,
            "overflow": bool(dropped_unique),
            "rendered_by_type": self._type_counts(kept),
            "dropped_unique_by_type": self._type_counts(dropped_unique),
            "dropped_raw_by_type": self._type_counts(dropped_unique, raw_dups=True),
        }
        if viewer_thread_id is not None:
            stats["viewer_thread_id"] = viewer_thread_id
            stats["viewer_self_entries_rendered"] = sum(
                1 for e in kept if e.get("thread_id") == viewer_thread_id
            )
            # Precise (use _matched_self, the same logic the self_policy applies):
            # same_thread: any delegation on the viewer thread, exclusively;
            # current_self: exclusively the viewer's CURRENT delegation.
            same_thread = lambda e: self._matched_self(  # noqa: E731
                e, viewer_thread_id, viewer_delegation_id, "demote_thread")
            current_self = lambda e: self._matched_self(  # noqa: E731
                e, viewer_thread_id, viewer_delegation_id, "demote_current")
            stats["viewer_same_thread_entries_rendered"] = sum(1 for e in kept if same_thread(e))
            stats["viewer_current_self_entries_rendered"] = sum(1 for e in kept if current_self(e))
            stats["viewer_same_thread_entries_excluded"] = sum(1 for e in self_excluded if same_thread(e))
            stats["viewer_current_self_entries_excluded"] = sum(1 for e in self_excluded if current_self(e))
            stats["viewer_current_self_entries_dropped"] = sum(1 for e in dropped_unique if current_self(e))
        return stats

    async def read(
        self,
        window_tokens: int = 500,
        viewer_thread_id: Optional[int] = None,
        viewer_delegation_id: Optional[int] = None,
        self_policy: str = "include",
    ) -> List[Dict[str, Any]]:
        """Return a DEDUPED, PRIORITY-SELECTED view that fits window_tokens.

        Deterministic (no LLM summarizer). Steps:
          1) collapse exact (type, normalized-content) duplicates (12-14% of entries),
             counting repeats so they don't consume budget;
          2) fill the budget in PRIORITY order — FACT / concrete-OBSERVED > FAIL >
             OBSERVED > TRIED — newest-first within each priority, so durable evidence
             survives and low-value TRIED chatter is dropped first.
        Returned in chronological order. Storage (_entries) stays append-only; this
        only changes the rendered selection.
        """
        async with self._lock:
            snap = list(self._entries)
        entries, _ = self._select_entries(
            snap, window_tokens=window_tokens,
            viewer_thread_id=viewer_thread_id,
            viewer_delegation_id=viewer_delegation_id,
            self_policy=self_policy,
        )
        return entries

    async def read_with_stats(
        self,
        window_tokens: int = 500,
        viewer_thread_id: Optional[int] = None,
        viewer_delegation_id: Optional[int] = None,
        self_policy: str = "include",
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Return selected entries plus render/overflow/dedupe stats."""
        async with self._lock:
            snap = list(self._entries)
        return self._select_entries(
            snap,
            window_tokens=window_tokens,
            viewer_thread_id=viewer_thread_id,
            viewer_delegation_id=viewer_delegation_id,
            self_policy=self_policy,
        )

    async def read_all(self) -> List[Dict[str, Any]]:
        """Return all entries (no windowing). For diagnostics / end-of-task."""
        async with self._lock:
            return list(self._entries)

    async def get_stats(self, window_tokens: Optional[int] = None) -> Dict[str, Any]:
        """Return storage stats, optionally including current render-selection stats."""
        async with self._lock:
            snap = list(self._entries)
        if window_tokens is None:
            deduped = self._dedupe_entries(snap)
            return {
                "task_id": self.task_id,
                "stored_entries": len(snap),
                "unique_entries": len(deduped),
                "duplicates_suppressed": max(0, len(snap) - len(deduped)),
                "stored_by_type": self._type_counts(snap),
                "unique_by_type": self._type_counts(deduped),
            }
        # get_stats is a DIAGNOSTIC; passing count_render=False
        # so end-of-task stats logging doesn't inflate _render_counts (the
        # orchestrator currently calls get_stats twice per task before writing
        # the lifecycle summary — ~10% overcount in the ).
        _, stats = self._select_entries(snap, window_tokens=window_tokens, count_render=False)
        return stats

    def _entry_size(self, entry: Dict[str, Any]) -> int:
        dup = int(entry.get("_dup", 1))
        suffix_len = len(f" (x{dup})") if dup > 1 else 0
        suffix_len += len(self._patch_status_suffix(entry))
        return _FORMAT_OVERHEAD_CHARS + len(entry["content"]) + suffix_len

    def format_for_prompt(self, entries: List[Dict[str, Any]]) -> str:
        """Render entries as a compact `[t{i}/{TYPE} +{m}m] content` block.

        Render order ():
          1. `[Patch summaries]` — candidate fixes from peer threads
             (most action-relevant signal; rendered FIRST so the
             reader sees them before durable knowledge).
          2. `[Active claims]` — peer threads' current targets (3.1).
          3. `[Shared lessons]` — durable FACT/TRIED/OBSERVED/FAIL.

        PATCH_SUMMARY and CLAIM entries are NEVER suffixed with `(xN)`
        — each is its own thread's distinct statement (see
        _dedupe_entries: both types skip exact + semantic dedupe).
        """
        if not entries:
            return "(no shared lessons yet)"
        patches = [e for e in entries if e.get("type") == "PATCH_SUMMARY"]
        claims = [e for e in entries if e.get("type") == "CLAIM"]
        durable = [e for e in entries
                   if e.get("type") not in ("PATCH_SUMMARY", "CLAIM")]

        parts: List[str] = []
        if patches:
            parts.append(
                "[Patch summaries — candidate fixes proposed by peer threads; "
                "review BEFORE deciding to submit or to propose your own]"
            )
            for e in patches:
                rel_min = (e["ts"] - self._start_time) / 60.0
                parts.append(
                    f"[t{e['thread_id']}/PATCH_SUMMARY +{rel_min:.1f}m] "
                    f"{e['content']}{self._patch_status_suffix(e)}"
                )

        if claims:
            if patches:
                parts.append("")
            parts.append("[Active claims — peer threads' current targets; pick a different angle if your plan duplicates theirs]")
            now_ts = time.time()
            for e in claims:
                rel_min = (e["ts"] - self._start_time) / 60.0
                exp = e.get("_expires_at")
                if exp is not None:
                    left = max(0.0, (float(exp) - now_ts) / 60.0)
                    ttl_str = f", +{left:.1f}m left"
                else:
                    ttl_str = ""
                parts.append(
                    f"[t{e['thread_id']}/CLAIM +{rel_min:.1f}m{ttl_str}] {e['content']}"
                )

        if durable:
            if patches or claims:
                parts.append("")
                parts.append("[Shared lessons]")
            for e in durable:
                rel_min = (e["ts"] - self._start_time) / 60.0
                dup = e.get("_dup", 1)
                suffix = f" (x{dup})" if dup > 1 else ""
                parts.append(
                    f"[t{e['thread_id']}/{e['type']} +{rel_min:.1f}m] {e['content']}{suffix}"
                )
        return "\n".join(parts)

    def _patch_task_text(self, entry: Dict[str, Any]) -> str:
        task = _compact_text(entry.get("task", ""), 240)
        return task or "(delegated task unavailable)"

    def _patch_summary_overview_line(self, index: int, entry: Dict[str, Any]) -> str:
        rel_min = (float(entry.get("ts", 0.0)) - self._start_time) / 60.0
        did = entry.get("delegation_id")
        return (
            f"[{index}] [t{entry.get('thread_id')}/d{did} +{rel_min:.1f}m] "
            f"Task: {self._patch_task_text(entry)}\n"
            f"    PATCH_SUMMARY: {entry.get('content', '')}{self._patch_status_suffix(entry)}"
        )

    def _important_failures_for_selective_unfold(
        self,
        entries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        failures = [e for e in entries if e.get("type") == "FAIL"]
        failures.sort(
            key=lambda e: float(e.get("_last_ts", e.get("ts", 0.0))),
            reverse=True,
        )
        kept = failures[:_MAX_SELECTIVE_UNFOLDED_FAILURES]
        kept.sort(key=lambda e: float(e.get("_last_ts", e.get("ts", 0.0))))
        return kept

    def _format_selective_failure(self, entry: Dict[str, Any]) -> str:
        rel_min = (float(entry.get("ts", 0.0)) - self._start_time) / 60.0
        did = entry.get("delegation_id")
        return (
            f"[t{entry.get('thread_id')}/d{did}/FAIL +{rel_min:.1f}m] "
            f"{entry.get('content', '')}"
        )

    async def render_patch_selective_unfold(self) -> str:
        """Render patch summaries plus the most recent FAIL details.

        This path is used only by shared_lessons_render_mode=
        "patch_selective_unfold". It intentionally does not change the legacy
        render() or render_peer_digest() behavior.
        """
        async with self._lock:
            snap = list(self._entries)
        return self.render_patch_selective_unfold_from(snap)

    def render_patch_selective_unfold_from(
        self, snap: List[Dict[str, Any]]
    ) -> str:
        """Snapshot-taking seam for the above.

        Local addition (not upstream): the multi-board /snapshot endpoint copies
        every board's entries under one critical section and renders afterwards,
        so it needs a render that accepts a snapshot instead of taking the lock
        itself. Body below is upstream's verbatim.
        """
        now_ts = time.time()
        entries = [
            e for e in self._dedupe_entries(snap)
            if not self._is_expired_claim(e, now_ts)
        ]
        patches = [e for e in entries if e.get("type") == "PATCH_SUMMARY"]
        patches.sort(key=lambda e: float(e.get("ts", 0.0)))
        failures = self._important_failures_for_selective_unfold(entries)

        if not patches and not failures:
            return "(no shared lessons yet)"

        patch_lines = [
            self._patch_summary_overview_line(i, e)
            for i, e in enumerate(patches)
        ]
        failure_lines = [self._format_selective_failure(e) for e in failures]
        parts: List[str] = []
        if patch_lines:
            parts.append(
                "[Patch summaries - candidate fixes proposed by solver threads]"
            )
            parts.extend(patch_lines)

        if failure_lines:
            if parts:
                parts.append("")
            parts.append("[Recent failure details - reusable dead ends to avoid]")
            parts.extend(failure_lines)

        return "\n".join(parts)

    def _has_peer_writer(self, entry: Dict[str, Any], viewer_thread_id: Optional[int]) -> bool:
        """True if the selected/deduped entry contains information from a peer thread."""
        if viewer_thread_id is None:
            return True
        tids = entry.get("_thread_ids") or [entry.get("thread_id")]
        return any(tid != viewer_thread_id for tid in tids)

    def _is_invalidated_patch_warning(self, entry: Dict[str, Any]) -> bool:
        return (
            entry.get("type") == "PATCH_SUMMARY"
            and bool(entry.get("_invalidated_by_fail"))
            and not entry.get("_finalized")
        )

    def _peer_digest_render_type(self, entry: Dict[str, Any]) -> str:
        if self._is_invalidated_patch_warning(entry):
            return "FAIL"
        return str(entry.get("type", ""))

    def _peer_digest_render_content(self, entry: Dict[str, Any]) -> str:
        content = str(entry.get("content", ""))
        if not self._is_invalidated_patch_warning(entry):
            return content
        files = _parse_patch_summary_field(content, "files") or "unknown"
        idea = _parse_patch_summary_field(content, "idea")
        if not idea:
            idea = content
        idea = " ".join(str(idea).split())
        if len(idea) > MAX_CONTENT_CHARS:
            idea = idea[:MAX_CONTENT_CHARS].rstrip()
        reason = str(entry.get("_invalidated_by_fail", "")).strip()
        parts = [
            f"invalidated peer patch: files={files}",
            f"rejected_idea={idea}",
        ]
        if reason:
            parts.append(f"failed={reason}")
        return " | ".join(parts)

    def _peer_digest_entry_size(self, entry: Dict[str, Any]) -> int:
        dup = int(entry.get("_dup", 1))
        suffix_len = len(f" (x{dup})") if dup > 1 else 0
        suffix_len += len(self._patch_status_suffix(entry))
        return (
            _FORMAT_OVERHEAD_CHARS
            + len(self._peer_digest_render_content(entry))
            + suffix_len
        )

    def _peer_digest_priority(
        self,
        entry: Dict[str, Any],
        allowed_types: Optional[Tuple[str, ...]] = None,
    ) -> int:
        """Priority for compact cross-thread digest rendering.

        This intentionally keeps only high-signal notes: candidate patches,
        reusable failures, concrete observations, and concrete facts. It drops
        CLAIM and TRIED because this digest is meant to transfer useful
        knowledge, not narrate another thread's action stream.
        """
        t = entry.get("type")
        if self._is_invalidated_patch_warning(entry):
            if allowed_types is not None and not (
                "PATCH_SUMMARY" in allowed_types or "FAIL" in allowed_types
            ):
                return 99
            return 1
        if allowed_types is not None and t not in allowed_types:
            return 99
        content = str(entry.get("content", ""))
        low = content.strip().lower()
        if low in _NONE_TOKENS:
            return 99
        if t == "PATCH_SUMMARY":
            return 0 if (entry.get("_finalized") or entry.get("_verified_checkpoint")) else 99
        if t == "FAIL":
            return 1
        if t == "OBSERVED" and self._is_concrete(str(entry.get("content", ""))):
            return 2
        if t == "FACT":
            if any(h in low for h in _PEER_DIGEST_SPECULATIVE_HINTS):
                return 99
            if self._is_concrete(content):
                return 3
        return 99

    def format_peer_digest_for_prompt(
        self,
        entries: List[Dict[str, Any]],
        viewer_thread_id: Optional[int] = None,
    ) -> str:
        """Render a compact, high-signal digest of peer-thread lessons."""
        if not entries:
            return "(no peer shared lessons yet)"
        parts = ["[Peer shared lessons - only high-signal notes from other threads]"]
        for e in entries:
            rel_min = (e["ts"] - self._start_time) / 60.0
            tids = e.get("_thread_ids") or [e.get("thread_id")]
            peer_tids = [tid for tid in tids if viewer_thread_id is None or tid != viewer_thread_id]
            tid_text = ",".join(f"t{tid}" for tid in peer_tids) or f"t{e.get('thread_id')}"
            dup = e.get("_dup", 1)
            suffix = f" (x{dup})" if dup > 1 else ""
            suffix += self._patch_status_suffix(e)
            render_type = self._peer_digest_render_type(e)
            content = self._peer_digest_render_content(e)
            parts.append(f"[{tid_text}/{render_type} +{rel_min:.1f}m] {content}{suffix}")
        return "\n".join(parts)

    async def render_peer_digest(
        self,
        window_tokens: int = 500,
        viewer_thread_id: Optional[int] = None,
        allowed_types: Optional[Tuple[str, ...]] = None,
        fail_requires_finalized_patch: bool = False,
        patch_requires_no_fail: bool = False,
    ) -> str:
        """Render compact peer-only knowledge instead of the full raw blackboard.

        Unlike `render(..., self_policy=exclude_thread)`, this does not simply
        replay every peer note. It first dedupes, keeps only notes with at least
        one peer writer, drops low-signal action narration, and then fits the
        remaining entries into the normal token budget by utility priority.
        """
        async with self._lock:
            snap = list(self._entries)
        return self.render_peer_digest_from(
            snap,
            window_tokens=window_tokens,
            viewer_thread_id=viewer_thread_id,
            allowed_types=allowed_types,
            fail_requires_finalized_patch=fail_requires_finalized_patch,
            patch_requires_no_fail=patch_requires_no_fail,
        )

    def render_peer_digest_from(
        self,
        snap: List[Dict[str, Any]],
        window_tokens: int = 500,
        viewer_thread_id: Optional[int] = None,
        allowed_types: Optional[Tuple[str, ...]] = None,
        fail_requires_finalized_patch: bool = False,
        patch_requires_no_fail: bool = False,
    ) -> str:
        """Snapshot-taking seam for the above (local addition; body verbatim)."""
        now_ts = time.time()
        finalized_patch_keys = set()
        if fail_requires_finalized_patch:
            finalized_patch_keys = {
                (e.get("thread_id"), e.get("delegation_id"))
                for e in snap
                if e.get("type") == "PATCH_SUMMARY"
                and e.get("_finalized")
            }
        candidates = [
            e for e in self._dedupe_entries(snap)
            if not self._is_expired_claim(e, now_ts)
            and self._has_peer_writer(e, viewer_thread_id)
            and self._peer_digest_priority(e, allowed_types=allowed_types) < 99
            and (
                e.get("type") != "PATCH_SUMMARY"
                or not patch_requires_no_fail
                or self._patch_failure_count(e) == 0
            )
            and (
                e.get("type") != "FAIL"
                or not fail_requires_finalized_patch
                or e.get("_grounded_patch_fail")
                or (e.get("thread_id"), e.get("delegation_id")) in finalized_patch_keys
            )
        ]
        candidates.sort(
            key=lambda e: (
                self._peer_digest_priority(e, allowed_types=allowed_types),
                self._patch_failure_count(e) if e.get("type") == "PATCH_SUMMARY" else 0,
                -float(e.get("_last_ts", e.get("ts", 0.0))),
            )
        )
        budget = max(window_tokens, 0) * _CHARS_PER_TOKEN
        kept: List[Dict[str, Any]] = []
        used = 0
        for e in candidates:
            if len(kept) >= _MAX_PEER_DIGEST_ENTRIES:
                break
            render_type = self._peer_digest_render_type(e)
            type_count = sum(
                1 for kept_e in kept
                if self._peer_digest_render_type(kept_e) == render_type
            )
            if type_count >= _MAX_PEER_DIGEST_BY_TYPE.get(render_type, _MAX_PEER_DIGEST_ENTRIES):
                continue
            sz = self._peer_digest_entry_size(e)
            if used + sz > budget:
                continue
            used += sz
            kept.append(e)
        for e in kept:
            key = self._render_count_key(e)
            self._render_counts[key] = self._render_counts.get(key, 0) + 1
        kept.sort(key=lambda e: e["ts"])
        return self.format_peer_digest_for_prompt(kept, viewer_thread_id=viewer_thread_id)

    async def render(
        self,
        window_tokens: int = 500,
        viewer_thread_id: Optional[int] = None,
        viewer_delegation_id: Optional[int] = None,
        self_policy: str = "include",
    ) -> str:
        """Convenience: read(window) + format."""
        entries = await self.read(
            window_tokens=window_tokens,
            viewer_thread_id=viewer_thread_id,
            viewer_delegation_id=viewer_delegation_id,
            self_policy=self_policy,
        )
        return self.format_for_prompt(entries)

    async def render_with_stats(
        self,
        window_tokens: int = 500,
        viewer_thread_id: Optional[int] = None,
        viewer_delegation_id: Optional[int] = None,
        self_policy: str = "include",
    ) -> Tuple[str, Dict[str, Any]]:
        """Render prompt text plus measurement stats. `render()` remains str-only."""
        entries, stats = await self.read_with_stats(
            window_tokens=window_tokens,
            viewer_thread_id=viewer_thread_id,
            viewer_delegation_id=viewer_delegation_id,
            self_policy=self_policy,
        )
        rendered = self.format_for_prompt(entries)
        stats = dict(stats)
        stats["rendered_chars_actual"] = len(rendered)
        return rendered, stats

    async def write_lifecycle_summary(self, out_path: Path) -> None:
        """dump a per-task lesson-lifecycle summary to `out_path`.

        One JSON line per unique (deduped) entry with:
          - type, content, thread_id, delegation_id (the entry's representative
            fields), first_ts / last_ts (relative seconds);
          - written_count (raw appends collapsed into this entry — i.e. _dup);
          - render_count (number of times this unique entry was selected into
            the rendered window during the task).
        Followed by one `kind: "summary"` row with totals by type:
          stored, unique, ever_rendered, total_render_count.
        """
        try:
            async with self._lock:
                snap = list(self._entries)
            deduped = self._dedupe_entries(snap)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open("w", encoding="utf-8") as f:
                for e in deduped:
                    key = self._render_count_key(e)  # 
                    rc = int(self._render_counts.get(key, 0))
                    first_ts = float(e.get("_first_ts", e.get("ts", 0.0)))
                    last_ts = float(e.get("_last_ts", e.get("ts", 0.0)))
                    row = {
                        "kind": "entry",
                        "task_id": self.task_id,
                        "type": e.get("type"),
                        "content": e.get("content"),
                        "thread_id": e.get("thread_id"),
                        "delegation_id": e.get("delegation_id"),
                        "thread_ids": list(e.get("_thread_ids") or []),
                        "delegation_ids": list(e.get("_delegation_ids") or []),
                        "written_count": int(e.get("_dup", 1)),
                        "render_count": rc,
                        "first_rel_s": round(first_ts - self._start_time, 2),
                        "last_rel_s": round(last_ts - self._start_time, 2),
                    }
                    row.update(self._patch_lifecycle_fields(e))
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                # Aggregate totals row.
                total_render = sum(int(v) for v in self._render_counts.values())
                ever_rendered = sum(
                    1 for k in self._render_counts
                    if int(self._render_counts.get(k, 0)) > 0
                )
                f.write(json.dumps({
                    "kind": "summary",
                    "task_id": self.task_id,
                    "stored_by_type": self._type_counts(snap),
                    "unique_by_type": self._type_counts(deduped),
                    "stored_total": len(snap),
                    "unique_total": len(deduped),
                    "ever_rendered": ever_rendered,
                    "total_render_count": total_render,
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass
