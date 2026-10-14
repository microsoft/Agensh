"""
unfold — the G → S → raw layer from the DeLM paper, Appendix A.1 / A.2.

WHY THIS IS WRITTEN RATHER THAN PORTED
--------------------------------------
DeLM's repo does not implement this. `benchmark/long_source/modules/unfolder/`
holds exactly one file — a prompt template — with no `DefaultUnfolder`, no
`L[l]`/`R[l]` stores, no label resolver, no directive parser, and no caller
anywhere in the tree. `K_COARSE = 5` is a sentence inside a prompt string; no
code enforces it. So the mechanism below follows the paper's spec, not upstream
source, and the constants that DO exist upstream are reused verbatim.

(The similarly-named `render_patch_selective_unfold` in src/shared_lessons.py is
a different thing — a fixed render mode with no labels and no agent-initiated
request. It is ported separately and exposed as a render_mode.)

THE MODEL (paper A.1)
---------------------
A source unit r_i has three representations, r_i -> S_i -> G_i:

  C     the shared context. Stores ONLY the compact gist (label, G_i).
        This is what every peer sees by default.
  L[l]  the evidence map S_i — bullets, each anchored to a verbatim span.
  R[l]  the raw source unit.

L and R live OUTSIDE C. That separation is the whole point: peers pay gist-sized
tokens to know a thing exists, and pay full price only for the slice they
actually need.

SELECTIVE UNFOLDING (paper A.2)
-------------------------------
  Stage 1  G -> S    agent requests labels; orchestrator inlines their evidence
                     maps into that one call.
  Stage 2  S -> raw  agent requests again; orchestrator returns raw content.

Two properties from the paper that we implement literally:

  - "Raw retrieval is neighborhood-aware: requesting sub-chunk n returns n +/- 1
    as well", which absorbs off-by-one citation errors.
  - "Unfolded content is local to the requesting call and is not written back
    to the shared context C, so subsequent agents still observe only the gist
    layer." Nothing here mutates the board.

ADAPTATION TO OUR DOMAIN
------------------------
The paper's units are document chunks and its S layer is built by an LLM
(phi_1). board-service has no LLM and our units are agent findings, so:

  - The writing agent supplies both layers directly: `content` is G (already
    capped and verifier-checked, admitted to C) and `detail` is the raw unit,
    stored in R. Asking the author for the detail it already has is cheaper and
    more faithful than paying a second model to reconstruct it.
  - S is derived deterministically as a per-sub-chunk head excerpt. That is a
    weaker evidence map than phi_1's anchored bullets, but it preserves the
    load-bearing property: a cheap intermediate that localizes WHICH sub-chunk
    to pay for, without spending the raw budget to find out.
  - Labels are `G<gist_id>` (stable, monotonic, MySQL-assigned) rather than
    `W<n> S<j>`; sub-chunks address as `G<id>.<n>`, mirroring the paper's
    `S72.2`.

K_COARSE is ENFORCED here, unlike upstream where it is only requested in prose.
A model that ignores the cap would otherwise unfold the entire board and undo
the compression the design exists to provide.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Tuple

# Upstream constants, reused verbatim.
# Upstream's unfolder/prompts.py:11 sets this to 5. Raised because our stored
# details are far smaller than the long-source documents upstream unfolds: on a
# 32-worker board they run a median of ~190 chars, max ~1,250 (~314 tokens).
# 100 labels at the median is ~19k chars (~5k tokens) -- the same order as one
# board injection, and well under what a full board_read costs. The cap exists so a model cannot
# unfold the entire board in one call and undo the compression.
K_COARSE = 100                     # max labels per request (upstream: 5)
_SUBCHUNK_TARGET_CHARS = 2500      # summarizer/prompts.py:30
_MIN_SUBCHUNKS = 3                 # summarizer/prompts.py:30
_MAX_SUBCHUNKS = 12                # summarizer/prompts.py:30
_GIST_MAX_TOKENS = 100             # summarizer/prompts.py:16 (DOC_GIST_MAX_TOKENS)

# S-layer excerpt size. Chosen so a full summary unfold of K_COARSE labels at
# the max sub-chunk count stays near a 2500-token budget:
# 5 labels * 12 sub-chunks * 160 chars ~= 9.6k chars ~= 2.4k tokens, which is
# DOC_SUMMARY_MAX_TOKENS (summarizer/prompts.py:14).
_S_EXCERPT_CHARS = 160

_LABEL_RE = re.compile(r"^G(\d+)(?:\.(\d+))?$")
_WS_RE = re.compile(r"\s+")


def parse_label(label: str) -> Optional[Tuple[int, Optional[int]]]:
    """`G12` -> (12, None); `G12.3` -> (12, 3). None when malformed.

    Returning None rather than raising matters: labels come from a model, and a
    hallucinated one should degrade to "not found" alongside the valid ones
    rather than failing the whole request.
    """
    m = _LABEL_RE.match((label or "").strip())
    if not m:
        return None
    gid = int(m.group(1))
    sub = int(m.group(2)) if m.group(2) is not None else None
    return gid, sub


def n_subchunks(text: str) -> int:
    """Upstream's fan-out: max(3, min(12, ceil(chars / 2500)))."""
    n_chars = len(text or "")
    return max(_MIN_SUBCHUNKS, min(_MAX_SUBCHUNKS,
                                   math.ceil(n_chars / _SUBCHUNK_TARGET_CHARS) or 1))


def split_subchunks(text: str) -> List[str]:
    """Split raw detail into 1-indexed sub-chunks on whitespace boundaries.

    Splitting mid-token would corrupt the identifiers and paths that make a
    coding finding useful, so each cut is nudged to the nearest whitespace
    within a small window of the ideal offset.
    """
    text = text or ""
    if not text:
        return []
    n = n_subchunks(text)
    size = math.ceil(len(text) / n)
    out: List[str] = []
    pos = 0
    while pos < len(text):
        end = min(len(text), pos + size)
        if end < len(text):
            window = text[end:min(len(text), end + 120)]
            m = _WS_RE.search(window)
            if m:
                end += m.start()
        out.append(text[pos:end])
        pos = end
    return [c for c in out if c.strip()]


def _excerpt(chunk: str, limit: int = _S_EXCERPT_CHARS) -> str:
    s = _WS_RE.sub(" ", chunk or "").strip()
    return s if len(s) <= limit else s[:limit].rstrip() + " ..."


def render_summary(label_base: str, detail: str) -> str:
    """S layer for one label: one addressable line per sub-chunk.

    This is what an agent reads to decide which sub-chunk is worth raw budget —
    the paper's coarse-to-fine hop.
    """
    chunks = split_subchunks(detail)
    if not chunks:
        return f"[{label_base}] (no detail stored)"
    lines = [f"[{label_base}] {len(chunks)} sub-chunk(s), {len(detail)} chars:"]
    for i, c in enumerate(chunks, start=1):
        lines.append(f"  [{label_base}.{i}] {_excerpt(c)}")
    return "\n".join(lines)


def render_raw(label_base: str, detail: str, sub: Optional[int]) -> str:
    """R layer. Neighborhood-aware: sub-chunk n returns n-1, n, n+1 (paper A.2).

    With no sub-chunk given, return everything — the agent asked for the unit,
    not a slice of it.
    """
    chunks = split_subchunks(detail)
    if not chunks:
        return f"[{label_base}] (no detail stored)"
    if sub is None:
        body = "\n".join(
            f"  [{label_base}.{i}] {c.strip()}" for i, c in enumerate(chunks, start=1)
        )
        return f"[{label_base}] full detail ({len(chunks)} sub-chunk(s)):\n{body}"

    lo = max(1, sub - 1)
    hi = min(len(chunks), sub + 1)
    if sub < 1 or sub > len(chunks):
        return (f"[{label_base}] sub-chunk {sub} out of range "
                f"(1..{len(chunks)}); nothing returned")
    picked = [
        f"  [{label_base}.{i}]{' <-- requested' if i == sub else ''} {chunks[i - 1].strip()}"
        for i in range(lo, hi + 1)
    ]
    return (f"[{label_base}] raw sub-chunks {lo}-{hi} "
            f"(requested {sub}, neighbors included):\n" + "\n".join(picked))


def unfold(
    labels: List[str],
    details: Dict[int, str],
    depth: str = "summary",
    max_labels: int = K_COARSE,
) -> Dict[str, Any]:
    """Resolve labels against the detail store.

    `details` maps gist_id -> raw detail. Returns the rendered block plus which
    labels resolved, which were unknown, and which were dropped by the cap — the
    caller surfaces all three so a model that over-asks or invents a label finds
    out instead of silently getting less than it requested.
    """
    if depth not in ("summary", "raw"):
        raise ValueError(f"depth must be 'summary' or 'raw', got {depth!r}")

    requested = [l.strip() for l in labels if l and l.strip()]
    kept, dropped = requested[:max_labels], requested[max_labels:]

    blocks: List[str] = []
    resolved: List[str] = []
    unknown: List[str] = []
    for label in kept:
        parsed = parse_label(label)
        if parsed is None:
            unknown.append(label)
            continue
        gid, sub = parsed
        detail = details.get(gid)
        if not detail:
            unknown.append(label)
            continue
        base = f"G{gid}"
        blocks.append(
            render_summary(base, detail) if depth == "summary"
            else render_raw(base, detail, sub)
        )
        resolved.append(label)

    if not blocks:
        rendered = "(nothing unfolded: no requested label resolved to stored detail)"
    else:
        header = (
            "==== UNFOLDED DETAIL ====\n"
            "Expanded for THIS step only. It is not added to the shared board, "
            "and peers still see only the gist layer — if something here matters "
            "to them, publish it as a gist yourself."
        )
        rendered = header + "\n\n" + "\n\n".join(blocks)

    return {
        "rendered": rendered,
        "depth": depth,
        "resolved": resolved,
        "unknown": unknown,
        "dropped_over_cap": dropped,
    }


def render_index(entries: List[Dict[str, Any]]) -> str:
    """Advertise which rendered gists have detail behind them.

    format_for_prompt() is a verbatim port and emits no ids, so without this an
    agent has no handle to unfold by. Appending an index keeps the ported
    renderer untouched while still making labels reachable.
    """
    labelled = [
        e for e in entries
        if e.get("_label") and e.get("_has_detail")
    ]
    if not labelled:
        return ""
    lines = [
        "[Unfoldable — these gists have full detail stored outside the board. "
        f"Call board_unfold with up to {K_COARSE} labels to expand them for one step.]"
    ]
    for e in labelled:
        lines.append(
            f"  {e['_label']}  {e.get('type')}  {_excerpt(str(e.get('content', '')), 90)}"
        )
    return "\n".join(lines)
