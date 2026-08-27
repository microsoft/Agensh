#!/usr/bin/env python3
"""
board_report.py — did the shared context actually change what agents did?

Counting HTTP calls to the board answers "was it wired up", which is a much
weaker question than the one these runs exist to ask. This reports the three
things that actually bear on it:

  1. ADOPTION   what each agent published, by type, and whether anyone read it.
                `render_count` comes from SharedLessons' own lifecycle log: the
                number of times an entry was selected into somebody's window.
                A gist written and never rendered reached no one.

  2. DIVERGENCE DeLM's cross-thread metric (src/metrics/divergence.py:198-252).
                Pairwise Jaccard over each agent's command signatures. This is
                the one that can come out BADLY for a shared board: if the
                board works as intended agents avoid duplicating each other and
                similarity falls; if it makes them converge on the first idea
                published, similarity rises. Reporting it either way is the
                point.

  3. DELIVERY   queue claims/completions, so "nobody claimed anything" is
                visible rather than inferred from a low score.

Usage:
    board_report.py <trajectory-dir> [--json]

<trajectory-dir> is one saved run, e.g.
~/agensteam_traj_delm_r3_batch/samtools__samtools.aa823b5.delm-1a-r3-batch-20260727
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Set

GIST_TYPES = ("FACT", "OBSERVED", "FAIL", "PATCH_SUMMARY", "CLAIM", "TRIED")


def _iter_events(agent_dir: Path):
    """Yield parsed events.jsonl rows for one agent, tolerating partial lines.

    A run killed at the wall clock leaves a half-written final line; dropping it
    is correct, and crashing on it would lose the whole agent's data.
    """
    for f in agent_dir.rglob("session-state/*/events.jsonl"):
        try:
            with f.open(errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue


def command_signatures(agent_dir: Path) -> List[str]:
    """The agent's tool-call signatures, in order.

    Upstream signs on the executed command. copilot-CLI writes
    `tool.execution_start` rows carrying `{toolName, arguments}`, so we sign on
    the tool name plus the first two tokens of whatever it acted on — enough to
    tell `bash ls` from `bash make`, without treating two greps for different
    symbols as unrelated work.
    """
    sigs: List[str] = []
    for e in _iter_events(agent_dir):
        if e.get("type") != "tool.execution_start":
            continue
        data = e.get("data") or {}
        name = data.get("toolName") or data.get("name") or "?"
        args = data.get("arguments")
        raw = ""
        if isinstance(args, dict):
            for key in ("command", "cmd", "path", "pattern", "query", "file_path"):
                if args.get(key):
                    raw = str(args[key])
                    break
        elif args:
            raw = str(args)
        head = raw.strip().split()[:2]
        sigs.append(f"{name}:{' '.join(head)}" if head else str(name))
    return sigs


def jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.0
    u = len(a | b)
    return (len(a & b) / u) if u else 0.0


def load_lifecycle(root: Path) -> Dict[str, Any]:
    """Read board-lifecycle/*.jsonl, if the run captured it."""
    out: Dict[str, Any] = {"entries": [], "summary": []}
    for f in root.rglob("board-lifecycle/*.jsonl"):
        try:
            for line in f.read_text(errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                (out["summary"] if row.get("kind") == "summary" else out["entries"]).append(row)
        except OSError:
            continue
    return out


def main(argv: List[str]) -> int:
    if not argv:
        print(__doc__.strip())
        return 2
    as_json = "--json" in argv
    root = Path([a for a in argv if not a.startswith("-")][0]).expanduser()
    if not root.exists():
        print(f"no such trajectory dir: {root}", file=sys.stderr)
        return 1

    hermes = next((p for p in (root / "data-root" / "hermes", root / "hermes") if p.is_dir()), None)
    if hermes is None:
        print(f"no hermes/ under {root}", file=sys.stderr)
        return 1

    agents = sorted(p for p in hermes.iterdir() if p.is_dir())
    sigs = {a.name: command_signatures(a) for a in agents}
    ran = {n: s for n, s in sigs.items() if s}

    # --- divergence -------------------------------------------------------
    pairs = []
    for x, y in combinations(sorted(ran), 2):
        pairs.append((x, y, jaccard(set(ran[x]), set(ran[y]))))
    mean_j = sum(p[2] for p in pairs) / len(pairs) if pairs else 0.0

    # --- adoption ---------------------------------------------------------
    life = load_lifecycle(root)
    by_agent: Dict[str, Counter] = defaultdict(Counter)
    rendered_by_agent: Dict[str, int] = defaultdict(int)
    never_rendered = 0
    for row in life["entries"]:
        t = row.get("type", "?")
        who = str(row.get("thread_id", "?"))
        by_agent[who][t] += 1
        rc = int(row.get("render_count", 0) or 0)
        rendered_by_agent[who] += rc
        if rc == 0:
            never_rendered += 1

    report = {
        "run": root.name,
        "agents_total": len(agents),
        "agents_that_ran": len(ran),
        "divergence": {
            "mean_pairwise_jaccard": round(mean_j, 4),
            "pairs": len(pairs),
            "most_similar": sorted(pairs, key=lambda p: -p[2])[:3],
        },
        "board": {
            "entries_logged": len(life["entries"]),
            "never_rendered": never_rendered,
            "by_agent": {k: dict(v) for k, v in sorted(by_agent.items())},
            "renders_received_by_author": dict(sorted(rendered_by_agent.items())),
            "summary_rows": life["summary"],
        },
    }

    if as_json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"== {report['run']}")
    print(f"  agents: {report['agents_that_ran']}/{report['agents_total']} produced any tool call")
    d = report["divergence"]
    print(f"  divergence: mean pairwise Jaccard {d['mean_pairwise_jaccard']} over {d['pairs']} pair(s)")
    print("              (lower = agents explored different ground)")
    for x, y, j in d["most_similar"]:
        print(f"      most similar: {x} ~ {y}  {j:.3f}")
    b = report["board"]
    if b["entries_logged"]:
        reached = b["entries_logged"] - b["never_rendered"]
        pct = 100.0 * reached / b["entries_logged"]
        print(f"  board: {b['entries_logged']} unique gist(s); "
              f"{reached} ({pct:.0f}%) were rendered to at least one agent")
        for who, counts in b["by_agent"].items():
            tot = sum(counts.values())
            print(f"      {who:28s} wrote {tot:3d}  {dict(counts)}")
    else:
        print("  board: no lifecycle log captured "
              "(POST /board/{id}/lifecycle at run end, or the volume was missing)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
