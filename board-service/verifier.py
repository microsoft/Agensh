from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from shared_lessons import (
    VALID_TYPES,
    MAX_CONTENT_CHARS,
    MAX_PATCH_SUMMARY_CHARS,
    parse_note_body,
)

_INVALID_EVIDENCE_PHRASES = (
    "tbd",
    "pending",
    "not verified",
    "unverified",
    "should work",
    "should pass",
    "looks right",
    "looks correct",
    "seems to work",
    "to be verified",
    "will verify",
    "n/a",
)

def _parse_schema_field(content: str, field_name: str) -> Optional[str]:
    if not content:
        return None
    prefix = field_name.lower() + "="
    for part in content.split("|"):
        s = part.strip()
        if s.lower().startswith(prefix):
            return s[len(prefix):].strip()
    return None

def _is_invalid_patch_summary_evidence(content: str) -> bool:
    ev = _parse_schema_field(content, "evidence")
    if ev is None:
        return True
    norm = ev.strip().lower()
    if not norm:
        return True
    for p in _INVALID_EVIDENCE_PHRASES:
        if norm == p:
            return True
        if norm.startswith(p):
            tail = norm[len(p):]
            if not tail or not tail[0].isalpha():
                return True
    return False

def verify_notes(notes: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], str]:
    """Deterministic note hygiene. Returns (clean_notes, status).

    - normalizes/validates each note's TYPE (case-insensitive → upper, must be
      in VALID_TYPES);
    - drops empty or over-length content (length is also enforced by
      SharedLessons.note, this is a defensive early trim);
    - applies the PER-TYPE size cap. #3: this used
      to hardcode MAX_CONTENT_CHARS for ALL types, silently truncating a
      300-char PATCH_SUMMARY to 100 and dropping `evidence=` / `risk=`
      fields before the entry ever reached storage.
    - collapses exact-duplicate (type, content) entries within the batch.

    status: "ok:{kept}/{seen}" — e.g. "ok:2/3" means 2 of 3 input notes kept.
    No LLM call; never raises.
    """
    seen = set()
    clean: List[Dict[str, str]] = []
    n_in = len(notes or [])
    ps_dropped_invalid_evidence = 0  # #4 metric
    for note in notes or []:
        t = str(note.get("type", "")).strip().upper()
        c = str(note.get("content", "")).strip()
        if t not in VALID_TYPES or not c:
            continue
        cap = MAX_PATCH_SUMMARY_CHARS if t == "PATCH_SUMMARY" else MAX_CONTENT_CHARS
        if len(c) > cap:
            c = c[:cap]
        if t == "PATCH_SUMMARY" and _is_invalid_patch_summary_evidence(c):
            ps_dropped_invalid_evidence += 1
            continue
        key = (t, c)
        if key in seen:
            continue
        seen.add(key)
        clean.append({"type": t, "content": c})
    status = f"ok:{len(clean)}/{n_in}"
    if ps_dropped_invalid_evidence:
        status += f",ps_invalid_ev={ps_dropped_invalid_evidence}"
    return clean, status

_PS_INVALID_EV_RE = re.compile(r"\bps_invalid_ev\s*=\s*(\d+)(?=[\s,]|$)")

def parse_invalid_evidence_count(status: Optional[str]) -> int:
    if not status:
        return 0
    m = _PS_INVALID_EV_RE.search(status)
    if not m:
        return 0
    try:
        return int(m.group(1))
    except (TypeError, ValueError):
        return 0

# ---------------------------------------------------------------------------
# Opt-in LLM-based verifier — a drop-in alternative to verify_notes().
# Selected with note_verifier_mode="llm"; the deterministic path stays default.
# ---------------------------------------------------------------------------

_LLM_VERIFIER_PROMPT = """A coding agent wants to publish PATCH_SUMMARY notes (candidate fixes) to a shared blackboard that peer agents rely on. A PATCH_SUMMARY is trustworthy only if its `evidence=` field reports a check the agent ACTUALLY ran, with a concrete result (e.g. "ran tests/test_x.py::y and it PASSED", "repro.py now prints 5, no error"). It is NOT trustworthy if the evidence is missing, a placeholder, or a promise/guess (e.g. "TBD", "pending", "not verified", "should work", "looks right", "will verify").

Candidate PATCH_SUMMARY notes (index: content):
{listing}

Reply with ONLY a JSON array of the indices whose evidence is a real, already-run verification (the ones to KEEP), e.g. [0,2]. Use [] if none qualify. Output nothing else."""


def _mechanical_clean(notes: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Type-normalize, enforce the per-type size cap, drop invalid-type/empty,
    and exact-dedupe — the hygiene shared by both verifiers, WITHOUT any
    semantic (evidence) judgment."""
    seen = set()
    clean: List[Dict[str, str]] = []
    for note in notes or []:
        t = str(note.get("type", "")).strip().upper()
        c = str(note.get("content", "")).strip()
        if t not in VALID_TYPES or not c:
            continue
        cap = MAX_PATCH_SUMMARY_CHARS if t == "PATCH_SUMMARY" else MAX_CONTENT_CHARS
        if len(c) > cap:
            c = c[:cap]
        key = (t, c)
        if key in seen:
            continue
        seen.add(key)
        clean.append({"type": t, "content": c})
    return clean


def _parse_keep_indices(resp: str, n: int) -> Optional[List[int]]:
    """Pull a JSON array of ints out of the LLM reply. Returns the sorted,
    unique, in-range indices ([] means "keep none"), or None when no array
    could be parsed (so the caller can fall back)."""
    if not resp:
        return None
    m = re.search(r"\[[\s\d,]*\]", resp)
    if not m:
        return None
    try:
        arr = json.loads(m.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(arr, list):
        return None
    return sorted({
        int(x) for x in arr
        if isinstance(x, (int, float)) and 0 <= int(x) < n
    })


async def verify_notes_llm(
    notes: List[Dict[str, str]],
    llm: Any,
) -> Tuple[List[Dict[str, str]], str]:
    """LLM-based note hygiene — opt-in alternative to verify_notes() with the
    SAME purpose, not a broader quality filter.

    The deterministic verify_notes() makes exactly one semantic decision: drop a
    PATCH_SUMMARY whose `evidence=` is unverified (everything else is mechanical
    hygiene, and all other note types are kept). This mirrors that: it applies
    the same mechanical hygiene (type/size/dedupe via _mechanical_clean), then
    asks `llm` ONLY which PATCH_SUMMARY entries have real, already-run evidence —
    replacing the brittle phrase-list in _is_invalid_patch_summary_evidence().
    Non-PATCH_SUMMARY notes are kept verbatim, exactly as the deterministic path.

    The LLM is consulted only when the batch contains a PATCH_SUMMARY; with none
    to judge, or on no-llm / LLM error / unparseable reply, it returns the
    deterministic verify_notes() result. So enabling this never changes
    non-PATCH_SUMMARY handling and never drops notes on an infra hiccup.

    status: "llm:{kept}/{seen}" (+ ",ps_invalid_ev=N" for dropped PATCH_SUMMARY,
    so the runner's existing metric keeps working).
    """
    n_in = len(notes or [])
    mechanically = _mechanical_clean(notes)
    ps_positions = [i for i, n in enumerate(mechanically) if n["type"] == "PATCH_SUMMARY"]
    if not ps_positions or llm is None:
        # Nothing for the LLM to judge (or no LLM) -> identical to deterministic.
        return verify_notes(notes)

    ps_notes = [mechanically[i] for i in ps_positions]
    listing = "\n".join(f"{j}: {n['content']}" for j, n in enumerate(ps_notes))
    try:
        resp = await llm(
            _LLM_VERIFIER_PROMPT.format(listing=listing),
            max_tokens=100,
            role_override="Verifier",
        )
        keep = _parse_keep_indices(resp, len(ps_notes))
    except Exception:
        return verify_notes(notes)
    if keep is None:
        return verify_notes(notes)

    keep_set = set(keep)
    drop_positions = {
        ps_positions[j] for j in range(len(ps_notes)) if j not in keep_set
    }
    kept = [n for i, n in enumerate(mechanically) if i not in drop_positions]
    status = f"llm:{len(kept)}/{n_in}"
    if drop_positions:
        status += f",ps_invalid_ev={len(drop_positions)}"
    return kept, status


__all__ = [
    "verify_notes",
    "verify_notes_llm",
    "parse_note_body",
    "parse_invalid_evidence_count",
]
