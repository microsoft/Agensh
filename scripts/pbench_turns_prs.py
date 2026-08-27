#!/usr/bin/env python3
"""pbench_turns_prs.py — per-task turn and PR counts for a sweep's trajectories.

Two independent sources, both captured in every trajectory snapshot:

  turns  copilot's own session event log,
         data-root/hermes/<agent>/home/.copilot/session-state/<uuid>/events.jsonl
         `assistant.turn_start` is one model turn. An agent may have several
         session-state UUIDs (the ACP bridge re-spawns copilot on reconnect),
         so all of them are summed per agent.

  PRs    gitea's sqlite, data-root/gitea/gitea/gitea.db
         `issue.is_pull=1` counts PRs opened; `pull_request.has_merged=1`
         counts those that reached main. Both matter: opened-but-unmerged is
         the failure mode where correct work never lands.

Reported per task and as a sweep aggregate, so two sweeps can be compared
directly.

Usage:
    python3 scripts/pbench_turns_prs.py ~/agensteam_traj_eng_sweep_6_1_team ...
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path


def task_of(d: Path) -> str:
    """`<task>.<suffix>` -> `<task>` (task ids contain dots, suffixes start 2a-)."""
    name = d.name
    for marker in (".2a-", ".2b-", ".2ab-", ".opus"):
        if marker in name:
            return name.split(marker)[0]
    return name


def count_events(root: Path) -> dict[str, int]:
    c: Counter[str] = Counter()
    for f in root.glob("hermes/*/home/.copilot/session-state/*/events.jsonl"):
        for line in f.read_text(errors="replace").splitlines():
            try:
                c[json.loads(line).get("type", "?")] += 1
            except Exception:
                pass
    return {
        "turns": c.get("assistant.turn_start", 0),
        "prompts": c.get("user.message", 0),
        "tools": c.get("tool.execution_start", 0),
        "compactions": c.get("session.compaction_start", 0),
    }


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

    per_sweep: dict[str, dict[str, dict]] = {}
    for arg in argv[1:]:
        root = Path(arg).expanduser()
        rows: dict[str, dict] = {}
        for d in sorted(root.iterdir()):
            dr = d / "data-root"
            if not dr.is_dir():
                continue
            rows[task_of(d)] = {**count_events(dr), **count_prs(dr)}
        per_sweep[root.name] = rows

    names = list(per_sweep)
    tasks = sorted({t for r in per_sweep.values() for t in r})
    w = max(len(t) for t in tasks)

    hdr = "task".ljust(w)
    for n in names:
        tag = n.replace("agensteam_traj_eng_", "").replace("_1_team", "")
        hdr += f" | {tag:>22}"
    print("\n" + hdr)
    print("-" * len(hdr))
    print("".ljust(w) + "".join(f" | {'turns  PRs  merged':>22}" for _ in names))
    print("-" * len(hdr))

    for t in tasks:
        line = t.ljust(w)
        for n in names:
            r = per_sweep[n].get(t)
            line += (
                f" | {r['turns']:>7} {r['prs']:>4} {r['merged']:>6}"
                if r
                else f" | {'—':>22}"
            )
        print(line)

    print("-" * len(hdr))
    for label, fn in (
        ("TOTAL", sum),
        ("MEAN", lambda xs: sum(xs) / len(xs) if xs else 0),
    ):
        line = label.ljust(w)
        for n in names:
            rs = list(per_sweep[n].values())
            if not rs:
                line += f" | {'—':>22}"
                continue
            tu = fn([r["turns"] for r in rs])
            pr = fn([r["prs"] for r in rs])
            mg = fn([r["merged"] for r in rs])
            line += f" | {tu:>7.0f} {pr:>4.0f} {mg:>6.0f}"
        print(line)

    print()
    for n in names:
        rs = list(per_sweep[n].values())
        if not rs:
            continue
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
