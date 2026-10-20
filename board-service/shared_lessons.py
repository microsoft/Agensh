"""
SharedLessons: live per-task context board for parallel solvers.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

VALID_TYPES = ("FACT", "OBSERVED", "FAIL", "CLAIM", "PATCH_SUMMARY")
MAX_CONTENT_CHARS = 100
# PATCH_SUMMARY uses the structured "files=A | idea=B | evidence=C | risk=D"
# schema, which doesn't fit the 100-char durable-note cap.
MAX_PATCH_SUMMARY_CHARS = 300
# A hard bound on the board itself, kept deliberately far above a normal run: a
# completed 6h 16-worker board holds roughly 1,200-2,200 entries, so this is
# nearly always inert. It is NOT what bounds per-turn context cost (the delta
# render in main.py does that); it exists so a 12h or 24h run cannot grow the
# board without limit.
#
# Applied at the single append site so every downstream reader -- prompt render,
# board_read, the mid-turn delta -- sees the same bounded list.
MAX_BOARD_ENTRIES = 2000


def _rel_min(seconds: float) -> float:
    """Seconds elapsed -> minutes, the unit of every "+{rel}m" an agent reads."""
    return seconds / 60.0

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
# A worker that goes quiet on the board while heads-down implementing is then
# read as missing and its issue reassigned, spawning competing implementations
# and discarded PRs, even while it is the busiest agent on the team.
#
# A claim is repeatable: refreshing it says the work is still live. Expiry
# reaps abandoned claims; every live claim remains visible in a full read.
#
# TTL is 1h. A sub-issue runs for tens of minutes to hours, agents post a claim
# once rather than renewing it on a timer, and nothing in either role prompt
# tells them to refresh, so a short TTL (e.g. 300s) makes a claim visible for
# the first few minutes of the work it describes and absent for the rest --
# expired by the time a lead goes looking for a liveness signal. 1h is the order
# of a real work item. The cost of the longer window is a stale claim from a
# crashed agent steering peers away for up to an hour, which is strictly better
# than a claim that is gone before anyone can act on it.
DEFAULT_CLAIM_TTL_SECONDS = 3600

# PATCH_SUMMARY: one current candidate-fix summary per (thread, delegation).
# The latest valid summary replaces the prior one in memory rather than being
# suppressed, so peers see refined evidence rather than a stale early candidate.
# Lines that explicitly mean "no notes this turn".
_NONE_TOKENS = ("(none)", "none", "-", "—")
_PATCH_SUMMARY_WEAK_EVIDENCE = (
    "pending", "not verified", "unverified", "should", "will verify",
    "to be verified", "tbd", "looks", "seems",
)
_PATCH_SUMMARY_SOLID_EVIDENCE_RE = re.compile(
    r"\b(pass(?:ed|es)?|verified|confirmed|no longer|now returns|now produces)\b",
    re.IGNORECASE,
)


def parse_patch_summary_field(content: str, field_name: str) -> Optional[str]:
    prefix = field_name.lower() + "="
    for part in str(content or "").split("|"):
        s = part.strip()
        if s.lower().startswith(prefix):
            return s[len(prefix):].strip()
    return None


class SharedLessonsError(ValueError):
    """Raised on invalid type or oversized content."""

class SharedLessons:
    """Per-task shared blackboard.

    All instances are scoped to a single task (one per task per run). Writes
    are serialized with an asyncio.Lock; reads grab a snapshot under the lock
    then deduplicate and expire claims outside it.
    """


    def __init__(self, task_id: str):
        self.task_id = task_id
        self._entries: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._start_time = time.time()
        self._render_counts: Dict[Tuple[Any, str], int] = {}

    async def note(self, thread_id: int, type: str, content: str,
                   delegation_id: Optional[int] = None,
                   ttl_seconds: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Append one entry. Returns the entry on success; raises on bad input.
        """
        if type not in VALID_TYPES:
            raise SharedLessonsError(
                f"invalid type {type!r}; must be one of {VALID_TYPES}"
            )
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
        async with self._lock:
            self._admit(entry)
        return entry

    def _admit(self, entry: Dict[str, Any]) -> None:
        """Put a validated entry on the board: the in-lock half of note().

        Sets the PATCH_SUMMARY lifecycle marks (a FAIL invalidates its
        delegation's live summary, and a summary carries the delegation's FAIL
        count), replaces a refined summary in place (latest-wins), appends, and
        trims to MAX_BOARD_ENTRIES. main.py's hydrate() re-admits the persisted
        rows through here, so the board rebuilt after a restart is the one the
        live writes built. A persisted replacement always remains latest-wins
        during replay, so a restart cannot resurrect its stale predecessor. The
        caller holds _lock, or runs before anything reads the board.
        """
        type = entry["type"]
        content = entry["content"]
        if (
            type == "PATCH_SUMMARY"
            and self._is_verified_patch_summary_checkpoint(content)
        ):
            entry["_verified_checkpoint"] = True
        norm_delegation = entry.get("delegation_id")
        norm_thread = entry["thread_id"]
        if type == "PATCH_SUMMARY":
            fail_count = self._delegation_fail_count(
                self._entries, norm_thread, norm_delegation
            )
            if fail_count:
                entry["_local_fail_count"] = fail_count
        if type == "FAIL":
            fail_count = self._delegation_fail_count(
                self._entries, norm_thread, norm_delegation
            ) + 1
            for e in reversed(self._entries):
                if (
                    e.get("type") == "PATCH_SUMMARY"
                    and e.get("thread_id") == norm_thread
                    and e.get("delegation_id") == norm_delegation
                ):
                    e.pop("_verified_checkpoint", None)
                    e["_invalidated_by_fail"] = content[:MAX_CONTENT_CHARS]
                    e["_local_fail_count"] = fail_count
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
                previous = self._entries[existing_idx]
                entry["_first_ts"] = previous.get("_first_ts", previous.get("ts", entry["ts"]))
                entry["_last_ts"] = entry["ts"]
                self._entries[existing_idx] = entry
                return
        self._entries.append(entry)
        # Drop the OLDEST past the bound. Newest-wins because a stale
        # observation is exactly what nobody needs re-read, and because
        # every cursor is monotonic: trimming the head can never resurrect
        # an entry a peer has already been shown.
        if len(self._entries) > MAX_BOARD_ENTRIES:
            del self._entries[: len(self._entries) - MAX_BOARD_ENTRIES]



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


    def _is_verified_patch_summary_checkpoint(self, content: str) -> bool:
        """
        True when a PATCH_SUMMARY has concrete local verification evidence.
        """
        evidence = parse_patch_summary_field(content, "evidence")
        if not evidence:
            return False
        low = evidence.strip().lower()
        if not low:
            return False
        if any(w in low for w in _PATCH_SUMMARY_WEAK_EVIDENCE):
            return False
        return bool(_PATCH_SUMMARY_SOLID_EVIDENCE_RE.search(evidence))

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


    def _patch_status_values(self, entry: Dict[str, Any]) -> List[str]:
        """
        Compact PATCH_SUMMARY lifecycle tags.
        """
        if entry.get("type") != "PATCH_SUMMARY":
            return []
        status: List[str] = []
        if entry.get("_verified_checkpoint"):
            status.append("verified")
        if entry.get("_invalidated_by_fail"):
            status.append("invalidated")
        fail_count = self._patch_failure_count(entry)
        if fail_count:
            status.append(f"local_failures={fail_count}")
        return status

    def _patch_status_suffix(self, entry: Dict[str, Any]) -> str:
        status = self._patch_status_values(entry)
        return f" [status={','.join(status)}]" if status else ""

    def _patch_lifecycle_fields(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Oracle-free PATCH_SUMMARY diagnostics for lifecycle.jsonl."""
        if entry.get("type") != "PATCH_SUMMARY":
            return {
                "patch_status": "",
                "is_verified_checkpoint": False,
                "local_failures": 0,
                "invalidated_by_fail": False,
                "invalidated_reason": "",
            }
        return {
            "patch_status": ",".join(self._patch_status_values(entry)),
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


    def _select_entries(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Render all deduplicated, live entries in chronological order."""
        now_ts = time.time()
        kept = [
            entry for entry in self._dedupe_entries(entries)
            if not self._is_expired_claim(entry, now_ts)
        ]
        kept.sort(key=lambda entry: entry["ts"])
        for entry in kept:
            key = self._render_count_key(entry)
            self._render_counts[key] = self._render_counts.get(key, 0) + 1
        return kept

    def _type_counts(self, entries: List[Dict[str, Any]]) -> Dict[str, int]:
        counts = {kind: 0 for kind in VALID_TYPES}
        for entry in entries:
            kind = entry.get("type")
            if kind in counts:
                counts[kind] += 1
        return counts


    async def read(self) -> List[Dict[str, Any]]:
        """Return the complete live board after deduplication and claim expiry."""
        async with self._lock:
            snap = list(self._entries)
        return self._select_entries(snap)

    async def read_all(self) -> List[Dict[str, Any]]:
        """Return all entries (no windowing). For diagnostics / end-of-task."""
        async with self._lock:
            return list(self._entries)



    def format_entry_line(self, e: Dict[str, Any], now_ts: float | None = None) -> str:
        """Render ONE entry exactly as it appears inside format_for_prompt.

        Board entries are also delivered mid-turn, appended to an MCP tool
        result by mcp-notice-shim. The requirement is
        that a mid-turn entry look identical to the same entry in the
        ``==== SHARED CONTEXT ====`` block the agent already holds -- so both
        paths call THIS function rather than keeping two copies of the format.
        Two copies would drift the first time either was touched, and the drift
        is invisible: both keep emitting plausible lines and nothing fails.

        ``now_ts`` exists so a caller rendering several entries computes the
        CLAIM TTL once (format_for_prompt does), and so tests can freeze it.
        """
        rel_min = _rel_min(e["ts"] - self._start_time)
        etype = e.get("type")

        if etype == "PATCH_SUMMARY":
            return (
                f"[t{e['thread_id']}/PATCH_SUMMARY +{rel_min:.1f}m] "
                f"{e['content']}{self._patch_status_suffix(e)}"
            )

        if etype == "CLAIM":
            exp = e.get("_expires_at")
            if exp is not None:
                if now_ts is None:
                    now_ts = time.time()
                left = max(0.0, _rel_min(float(exp) - now_ts))
                ttl_str = f", +{left:.1f}m left"
            else:
                ttl_str = ""
            return f"[t{e['thread_id']}/CLAIM +{rel_min:.1f}m{ttl_str}] {e['content']}"

        dup = e.get("_dup", 1)
        suffix = f" (x{dup})" if dup > 1 else ""
        return f"[t{e['thread_id']}/{etype} +{rel_min:.1f}m] {e['content']}{suffix}"

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
                parts.append(self.format_entry_line(e))

        if claims:
            if patches:
                parts.append("")
            parts.append("[Active claims — peer threads' current targets; pick a different angle if your plan duplicates theirs]")
            now_ts = time.time()
            for e in claims:
                parts.append(self.format_entry_line(e, now_ts))

        if durable:
            if patches or claims:
                parts.append("")
                parts.append("[Shared lessons]")
            for e in durable:
                parts.append(self.format_entry_line(e))
        return "\n".join(parts)


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
