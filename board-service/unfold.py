# Resolve G-labels to optional full details stored behind short board gists.
# Rendering an expansion does not publish it back to the shared board.

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

MAX_UNFOLD_LABELS = 100
_LABEL_RE = re.compile(r"G(\d+)")


def parse_label(label: str) -> Optional[int]:
    match = _LABEL_RE.fullmatch((label or "").strip())
    return int(match.group(1)) if match else None


def unfold(labels: List[str], details: Dict[int, str]) -> Dict[str, Any]:
    requested = [label.strip() for label in labels if label and label.strip()]
    kept, dropped = requested[:MAX_UNFOLD_LABELS], requested[MAX_UNFOLD_LABELS:]
    blocks: List[str] = []
    resolved: List[str] = []
    unknown: List[str] = []
    for label in kept:
        gid = parse_label(label)
        detail = details.get(gid) if gid is not None else None
        if not detail:
            unknown.append(label)
            continue
        blocks.append(f"[G{gid}] full detail:\n{detail}")
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
        "resolved": resolved,
        "unknown": unknown,
        "dropped_over_cap": dropped,
    }


def render_index(entries: List[Dict[str, Any]]) -> str:
    labelled = [e for e in entries if e.get("_label") and e.get("_has_detail")]
    if not labelled:
        return ""
    lines = [
        "[Unfoldable — these gists have full detail stored outside the board. "
        f"Call board_unfold with up to {MAX_UNFOLD_LABELS} labels to expand them for one step.]"
    ]
    for entry in labelled:
        excerpt = " ".join(str(entry.get("content", "")).split())
        if len(excerpt) > 90:
            excerpt = excerpt[:90].rstrip() + " ..."
        lines.append(f"  {entry['_label']}  {entry.get('type')}  {excerpt}")
    return "\n".join(lines)
