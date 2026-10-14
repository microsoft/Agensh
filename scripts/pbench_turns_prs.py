#!/usr/bin/env python3
"""pbench_turns_prs.py — per-task turn and PR counts for trajectories, by run.

Two independent sources, both captured in every trajectory snapshot:

  turns  the agent's own session event log, whichever backend wrote it:
           AGENT_KIND=copilot
             data-root/agents/<agent>/home/.copilot/session-state/<uuid>/events.jsonl
             `assistant.turn_start` is one model turn.
         An agent may have several session ids (the ACP bridge re-spawns the
         child on reconnect), so all of them are summed per agent, and both
         layouts are summed so a mixed or unknown arm cannot silently report 0.
         The agent dir is data-root/agents/<agent>, or data-root/hermes/<agent>
         in trajectories archived before the rename; both are read.

  PRs    gitea's sqlite, data-root/gitea/gitea/gitea.db
         `issue.is_pull=1` counts PRs opened; `pull_request.has_merged=1`
         counts those that reached main. Both matter: opened-but-unmerged is
         the failure mode where correct work never lands.

A trajectory directory is <task>.<mode>.<RUN_ID>. Each run is one column,
each task one row, with a per-run aggregate, so runs can be compared directly.
Each argument is a trajectories root or a single trajectory directory.

Usage:
    sudo python3 scripts/pbench_turns_prs.py ~/pbench-trajectories
    sudo python3 scripts/pbench_turns_prs.py ~/pbench-trajectories/*.single-node.<RUN_ID>
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path


# data-root/<layout>/<agent>/...: agents/, or hermes/ in older trajectories.
LAYOUTS = ("agents", "hermes")


def agent_glob(root: Path, pattern: str):
    """Every `<layout>/<agent>/<pattern>` match under root, for both layouts."""
    for layout in LAYOUTS:
        yield from root.glob(f"{layout}/*/{pattern}")


def split_name(d: Path) -> tuple[str, str]:
    """`<task>.<mode>.<RUN_ID>` -> (`<task>`, `<mode>.<RUN_ID>`).

    A task id is `<owner>__<repo>.<commit>`, so it is the first two dot fields.
    """
    parts = d.name.split(".", 2)
    return ".".join(parts[:2]), (parts[2] if len(parts) > 2 else "")


def count_events(root: Path) -> dict[str, int]:
    """Sum agent activity across every backend layout present in the snapshot.

    A trajectory holds exactly one arm's logs, but which one depends on
    AGENT_KIND, so both are scanned and summed rather than selected. Reporting
    zeros for an unrecognised layout is the dangerous failure here: the PR
    counts come from gitea regardless, so an unread arm would show real PRs
    beside turns=0 and read as "the agents barely ran".
    """
    c: Counter[str] = Counter()
    for f in agent_glob(root, "home/.copilot/session-state/*/events.jsonl"):
        for line in f.read_text(errors="replace").splitlines():
            try:
                c[json.loads(line).get("type", "?")] += 1
            except Exception:
                pass
    counts = {
        "turns": c.get("assistant.turn_start", 0),
        "prompts": c.get("user.message", 0),
        "tools": c.get("tool.execution_start", 0),
        "compactions": c.get("session.compaction_start", 0),
    }
    for k, v in count_claude(root).items():
        counts[k] = counts.get(k, 0) + v
    if counts["turns"] == 0:
        warn_if_unreadable(root)
    return counts


def warn_if_unreadable(root: Path) -> None:
    """Distinguish "the agents did nothing" from "we cannot read their logs".

    Agent transcripts under data-root are root-owned. Run without sudo, Path.glob
    skips the unreadable directories silently and every count comes back 0 — a
    result that looks exactly like agents that never ran. That fabricated
    absence reads as a real result, so say so out loud.
    """
    agents = []
    for layout in LAYOUTS:
        top = root / layout
        if not top.is_dir():
            continue
        try:
            agents += list(top.iterdir())
        except PermissionError:
            print(f"WARNING: {top} is unreadable — rerun with sudo; 0 is not a result",
                  file=sys.stderr)
            return
    for a in agents:
        home = a / "home"
        if not home.is_dir():
            continue
        try:
            next(home.iterdir(), None)
        except PermissionError:
            print(
                f"WARNING: {home} is unreadable (transcripts are root-owned) — "
                "rerun with sudo; the 0 turns reported here is a permission "
                "artifact, not a measurement",
                file=sys.stderr,
            )
            return


def count_claude(root: Path) -> dict[str, int]:
    """Count turns/tools/prompts from Claude Agent SDK transcripts.

    Layout: home/.claude/projects/<slug>/*.jsonl, one JSON object per line.

    Without it a claude trajectory reports turns=0 while its PR counts come
    through normally from gitea — a row that reads as "the agents barely ran".

    Mapping, chosen to be comparable with the other two backends:
      turns    one API RESPONSE == one turn, deduplicated on `message.id`.
               The SDK writes ONE ENTRY PER CONTENT BLOCK -- a response with
               thinking + text + two tool_use blocks becomes four entries
               sharing one id -- so counting entries overstates turns nearly
               2x. Entries are never mixed-block, confirming the split.
               The copilot session log does NOT do this (one message per
               messageId), so counting entries would be a one-sided error that
               inflates claude alone.
      tools    tool_use blocks inside those entries. Counted PER BLOCK, not per
               response: deduping turns must not dedupe the work.
      prompts  `user` entries that are NOT tool results; a tool result is
               delivered as a user message and is not a prompt.
      compactions
               entries with subtype `compact_boundary`. One event, matching
               copilot's session.compaction_start, so the columns compare.
               Omitting this key does not read as "unmeasured": Counter.get
               returns 0, so a claude arm would report `compactions=0` and look
               like an arm that never compacts.
               Do NOT also count isCompactSummary — it rides on the same entry
               and would double every figure.

    Sanity check on real data: tool_use blocks == tool_result entries exactly,
    which is what a correct parse of this format must produce.
    """
    c: Counter[str] = Counter()
    for f in agent_glob(root, "home/.claude/projects/*/*.jsonl"):
        # Per FILE: ids are unique within a session, and holding one set for the
        # whole tree would let two agents' ids collide into one another.
        seen_ids: set[str] = set()
        for line in f.read_text(errors="replace").splitlines():
            try:
                o = json.loads(line)
            except Exception:
                continue
            # Real transcripts contain lines that are valid JSON but not
            # objects (bare scalars turn up in the wild), so a successful parse
            # is not enough to start calling .get on it.
            if not isinstance(o, dict):
                continue
            # A compaction is its own entry, not an assistant/user one, so it
            # has to be counted before the type filter below discards it.
            if o.get("subtype") == "compact_boundary":
                c["compactions"] += 1
                continue
            t = o.get("type")
            if t not in ("assistant", "user"):
                continue
            content = (o.get("message") or {}).get("content")
            blocks = content if isinstance(content, list) else []
            if t == "assistant":
                # One API response may span several entries sharing an id.
                # An entry WITHOUT an id counts on its own: falling back to
                # per-entry is wrong-but-loud, whereas letting them all collapse
                # under a single missing key would silently report 1 turn for a
                # whole run.
                mid = (o.get("message") or {}).get("id")
                if not mid:
                    c["turns"] += 1
                elif mid not in seen_ids:
                    seen_ids.add(mid)
                    c["turns"] += 1
                c["tools"] += sum(
                    1
                    for b in blocks
                    if isinstance(b, dict) and b.get("type") == "tool_use"
                )
            else:
                is_tool_result = any(
                    isinstance(b, dict) and b.get("type") == "tool_result"
                    for b in blocks
                )
                if not is_tool_result:
                    c["prompts"] += 1
    return dict(c)


def count_prs(root: Path) -> dict[str, int]:
    db = root / "gitea/gitea/gitea.db"
    if not db.exists():
        return {"prs": 0, "merged": 0, "issues": 0}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        q = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
        return {
            "prs": q("select count(*) from issue where is_pull=1"),
            "merged": q("select count(*) from pull_request where has_merged=1"),
            "issues": q("select count(*) from issue where is_pull=0"),
        }
    finally:
        con.close()


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2

    per_run: dict[str, dict[str, dict]] = {}
    for arg in argv[1:]:
        root = Path(arg).expanduser()
        dirs = [root] if (root / "data-root").is_dir() else sorted(root.iterdir())
        for d in dirs:
            dr = d / "data-root"
            if not dr.is_dir():
                continue
            task, run = split_name(d)
            per_run.setdefault(run, {})[task] = {**count_events(dr), **count_prs(dr)}
    if not per_run:
        print(f"no trajectories (no */data-root) under: {' '.join(argv[1:])}", file=sys.stderr)
        return 1

    names = sorted(per_run)
    tasks = sorted({t for r in per_run.values() for t in r})
    w = max(len(t) for t in tasks)
    cw = max([22] + [len(n) for n in names])

    hdr = "task".ljust(w)
    for n in names:
        hdr += f" | {n:>{cw}}"
    print("\n" + hdr)
    print("-" * len(hdr))
    print("".ljust(w) + "".join(f" | {'turns  PRs  merged':>{cw}}" for _ in names))
    print("-" * len(hdr))

    pad = " " * (cw - 19)
    for t in tasks:
        line = t.ljust(w)
        for n in names:
            r = per_run[n].get(t)
            line += (
                f" | {pad}{r['turns']:>7} {r['prs']:>4} {r['merged']:>6}"
                if r
                else f" | {'—':>{cw}}"
            )
        print(line)

    print("-" * len(hdr))
    for label, fn in (
        ("TOTAL", sum),
        ("MEAN", lambda xs: sum(xs) / len(xs) if xs else 0),
    ):
        line = label.ljust(w)
        for n in names:
            rs = list(per_run[n].values())
            tu = fn([r["turns"] for r in rs])
            pr = fn([r["prs"] for r in rs])
            mg = fn([r["merged"] for r in rs])
            line += f" | {pad}{tu:>7.0f} {pr:>4.0f} {mg:>6.0f}"
        print(line)

    print()
    for n in names:
        rs = list(per_run[n].values())
        prs = sum(r["prs"] for r in rs)
        mg = sum(r["merged"] for r in rs)
        print(
            f"{n}: n={len(rs)}  turns={sum(r['turns'] for r in rs)}  "
            f"tools={sum(r['tools'] for r in rs)}  "
            f"compactions={sum(r['compactions'] for r in rs)}  "
            f"PRs={prs} merged={mg} "
            f"({100 * mg / prs if prs else 0:.1f}% merge rate)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
