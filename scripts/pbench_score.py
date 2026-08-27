#!/usr/bin/env python3
"""pbench_score.py — canonical-kept scoring for a sweep's trajectory tree.

WHY THIS EXISTS
`*.eval.json` records every test the grader ran, including tests on branches
that ProgramBench has since marked `ignored: true`. Scoring those raw files
overstates the denominator and understates the rate. The canonical score is
what `programbench info` reports:

    result.for_branches(active).without_ignored(ignored_tests)
    # src/programbench/cli/main.py:142-145

This script applies exactly that filter — by importing ProgramBench's own
helpers rather than reimplementing them, so the two cannot drift — and reports
per-task passed / total / rate plus the sweep aggregate.

It reads eval.json files out of a trajectory tree (`<traj>/<task>.<suffix>/out/
<task>.eval.json`), which is where the chain driver files them, so a sweep can
be scored after its `out/` dirs have been archived or wiped.

Usage (must run inside the ProgramBench uv env):
    cd ~/programbench && uv run python ~/agensteam/scripts/pbench_score.py \
        --traj ~/agensteam_traj_eng_sweep_6.2_1_team
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--traj", required=True, type=Path, help="trajectory root")
    ap.add_argument("--pb-repo", type=Path, default=Path.home() / "programbench")
    ap.add_argument("--json-out", type=Path, default=None)
    args = ap.parse_args()

    sys.path.insert(0, str(args.pb_repo / "src"))
    try:
        from programbench.eval.eval import EvaluationResult
        from programbench.utils.load_data import (
            get_active_branches,
            get_ignored_tests,
            load_all_instances,
        )
    except ImportError as exc:  # pragma: no cover - environment problem
        print(
            f"FATAL: cannot import programbench ({exc}).\n"
            f"Run under its env:  cd {args.pb_repo} && uv run python {sys.argv[0]} ...",
            file=sys.stderr,
        )
        return 2

    # Two trajectory layouts, because the two arms archive differently:
    #   team runs (pbench_chain.sh):        <traj>/<task>.<suffix>/out/<task>.eval.json
    #   single-agent (pbench_sweep64_eval): <traj>/<task>/<task>.eval.json
    # The 1-vs-5 comparison has to score both with the same canonical filter,
    # so accept either rather than making the caller normalise the tree.
    # `a or b` silently dropped every file in the second layout as soon as one
    # file matched the first. A mixed tree (9 team-layout + 1 agent-layout)
    # reported n=9 and never mentioned the tenth. Union them.
    evals = sorted(
        {*args.traj.glob("*/out/*.eval.json"), *args.traj.glob("*/*.eval.json")}
    )
    if not evals:
        print(f"no eval.json under {args.traj}", file=sys.stderr)
        return 1

    instances = {i["instance_id"]: i for i in load_all_instances(include_tests=True)}

    rows: list[dict] = []
    for p in evals:
        iid = p.name[: -len(".eval.json")]
        # The eval filename is the bare instance id, so five arms of the same
        # task rendered as five identical rows and were averaged as if they were
        # five different tasks. Keep the run dir to tell them apart.
        run_path = p.parent.parent if p.parent.name == "out" else p.parent
        run_dir = run_path.name
        # An EXPORT_FAILED marker means the submission never made it out of Gitea, so this
        # eval graded an empty tarball. Sweep 6.11 lost ctags and pandoc exactly this way and
        # both surfaced as a clean 0.00% — a number that reads like a result. It is not one:
        # the repos were intact and re-exported offline to 99 and 148 files. Never fold these
        # into the macro. See scripts/pbench_run_1team.sh:export_submission.
        export_failed = (run_path / "EXPORT_FAILED").exists() or (
            run_path / "out" / "EXPORT_FAILED"
        ).exists()
        label = iid if run_dir.startswith(iid) and run_dir == iid else run_dir
        result = EvaluationResult.model_validate_json(p.read_text())
        raw_passed, raw_total = result.n_resolved, len(result)

        inst = instances.get(iid)
        if inst is None:
            # Unknown instance: report raw and flag it rather than silently
            # presenting an unfiltered number as canonical.
            rows.append(
                {
                    "task": label,
                    "instance": iid,
                    "passed": raw_passed,
                    "total": raw_total,
                    "rate": 100.0 * raw_passed / raw_total if raw_total else 0.0,
                    "error": result.error_code,
                    "canonical": False,
                    "export_failed": export_failed,
                }
            )
            continue

        kept = result.for_branches(get_active_branches(inst)).without_ignored(
            get_ignored_tests(inst)
        )
        total = len(kept)
        rows.append(
            {
                "task": label,
                "instance": iid,
                "passed": kept.n_resolved,
                "total": total,
                "rate": 100.0 * kept.n_resolved / total if total else 0.0,
                "error": kept.error_code,
                "canonical": True,
                "export_failed": export_failed,
                "raw_passed": raw_passed,
                "raw_total": raw_total,
            }
        )

    # A task that ran and submitted but was never evaluated has no eval.json, so
    # it vanished from the table AND from n. Sweep 6.6 reported "n=9" over ten
    # completed tasks; treating the missing one as 0 moved the macro from 17.42%
    # to 15.68% and cut the team-over-agent gap by 28% relative. Find them.
    scored_dirs = {
        (p.parent.parent if p.parent.name == "out" else p.parent) for p in evals
    }
    unevaluated = sorted(
        d.name
        for d in args.traj.iterdir()
        if d.is_dir()
        and d not in scored_dirs
        and (list(d.glob("out/submission.tar.gz")) or list(d.glob("submission.tar.gz")))
    )

    rows.sort(key=lambda r: r["task"])
    width = max(len(r["task"]) for r in rows)
    print(f"\n=== CANONICAL-KEPT SCORES — {args.traj.name} ===\n")
    print(f"{'task'.ljust(width)}  {'passed':>7} {'total':>7} {'rate':>8}  error")
    print("-" * (width + 36))
    for r in rows:
        flag = "" if r["canonical"] else "  [RAW — instance not in dataset]"
        if r.get("export_failed"):
            flag += "  [EXPORT FAILED — no submission was graded; NOT a score]"
        print(
            f"{r['task'].ljust(width)}  {r['passed']:>7} {r['total']:>7} "
            f"{r['rate']:>7.2f}%  {r['error'] or '-'}{flag}"
        )

    # Aggregate over CANONICAL rows only. A row flagged [RAW] is an unfiltered
    # number (instance missing from the dataset, e.g. after a version bump) and
    # folding it in overstated one task by +7.68pp with no marker on the total.
    # Rows whose export failed are excluded outright: their 0.00% measures the
    # harness, not the team, and averaging it in silently depresses the macro.
    canon = [r for r in rows if r["canonical"] and not r.get("export_failed")]
    dropped = [r for r in rows if r.get("export_failed")]
    if dropped:
        print(
            f"\n!! {len(dropped)} task(s) EXCLUDED from the aggregate — export failed, "
            f"no submission was graded: {', '.join(r['task'] for r in dropped)}"
        )
        print("   The Gitea repo under DATA_ROOT is intact; re-export and re-evaluate.")
    n = len(canon)
    tot_p = sum(r["passed"] for r in canon)
    tot_t = sum(r["total"] for r in canon)
    macro = sum(r["rate"] for r in canon) / n if n else 0.0
    micro = 100.0 * tot_p / tot_t if tot_t else 0.0
    print("-" * (width + 36))
    # Macro first: ProgramBench's own aggregate is the mean of per-task rates
    # (BatchEvalSummary.average_pass_rate). Micro reorders sweeps against it.
    print(f"{'MEAN'.ljust(width)}  {'':>7} {'':>7} {macro:>7.2f}%  (macro, n={n})")
    print(f"{'TOTAL'.ljust(width)}  {tot_p:>7} {tot_t:>7} {micro:>7.2f}%  (micro)")
    if len(rows) != n:
        print(f"  NOTE: {len(rows) - n} row(s) excluded from the aggregate as [RAW]")
    if unevaluated:
        macro0 = sum(r["rate"] for r in canon) / (n + len(unevaluated))
        print(
            f"  WARNING: {len(unevaluated)} task(s) ran and submitted but were never "
            f"evaluated, so they are NOT in n: {', '.join(unevaluated)}"
        )
        print(f"  scoring them 0 gives macro {macro0:.2f}% (n={n + len(unevaluated)})")

    if args.json_out:
        args.json_out.write_text(
            json.dumps(
                {
                    "rows": rows,
                    "macro": macro,
                    "micro": micro,
                    "n": n,
                    "unevaluated": unevaluated,
                },
                indent=2,
            )
            + "\n"
        )
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
