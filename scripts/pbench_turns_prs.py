#!/usr/bin/env python3
"""pbench_turns_prs.py — per-task turn and PR counts for trajectories, by run.

Two independent sources, both captured in every trajectory snapshot:

  turns  Copilot's persistent session event log:
           data-root/agents/<agent>/home/.copilot/session-state/<uuid>/events.jsonl
         `assistant.turn_start` is one model turn. Sessions across reconnects
         are summed per agent.

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



def split_name(d: Path) -> tuple[str, str]:
    """`<task>.<mode>.<RUN_ID>` -> (`<task>`, `<mode>.<RUN_ID>`).

    A task id is `<owner>__<repo>.<commit>`, so it is the first two dot fields.
    """
    parts = d.name.split(".", 2)
    return ".".join(parts[:2]), (parts[2] if len(parts) > 2 else "")


def count_events(root: Path) -> dict[str, int]:
    """Sum Copilot activity across all persisted sessions in the snapshot."""
    c: Counter[str] = Counter()
    for f in root.glob("agents/*/home/.copilot/session-state/*/events.jsonl"):
        for line in f.read_text(errors="replace").splitlines():
            try:
                c[json.loads(line).get("type", "?")] += 1
            except Exception:
                pass
    counts = {
        "turns": c.get("assistant.turn_start", 0),
        "tools": c.get("tool.execution_start", 0),
        "compactions": c.get("session.compaction_start", 0),
    }
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
    top = root / "agents"
    if not top.is_dir():
        return
    try:
        agents = list(top.iterdir())
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


def count_prs(root: Path) -> dict[str, int]:
    db = root / "gitea/gitea/gitea.db"
    if not db.exists():
        return {"prs": 0, "merged": 0}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        q = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
        return {
            "prs": q("select count(*) from issue where is_pull=1"),
            "merged": q("select count(*) from pull_request where has_merged=1"),
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
