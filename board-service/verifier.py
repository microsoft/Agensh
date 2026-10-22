# Normalize and cap board gists, rejecting patch summaries with placeholder evidence.
# Verification is a deterministic text check; it does not execute the claimed tests.

from __future__ import annotations

from typing import Dict, Tuple

from shared_lessons import (
    VALID_TYPES,
    MAX_CONTENT_CHARS,
    MAX_PATCH_SUMMARY_CHARS,
    parse_patch_summary_field,
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

def _is_invalid_patch_summary_evidence(content: str) -> bool:
    ev = parse_patch_summary_field(content, "evidence")
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

def verify_note(note: Dict[str, str]) -> Tuple[Dict[str, str] | None, str]:
    kind = str(note.get("type", "")).strip().upper()
    content = str(note.get("content", "")).strip()
    if kind not in VALID_TYPES or not content:
        return None, "ok:0/1"
    cap = MAX_PATCH_SUMMARY_CHARS if kind == "PATCH_SUMMARY" else MAX_CONTENT_CHARS
    # Check the text that will actually be stored after truncation.
    content = content[:cap]
    if kind == "PATCH_SUMMARY" and _is_invalid_patch_summary_evidence(content):
        return None, "ok:0/1,ps_invalid_ev=1"
    return {"type": kind, "content": content}, "ok:1/1"
