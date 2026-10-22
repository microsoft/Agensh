#!/usr/bin/env python3
# Report raw attempt-row and canonical-kept scores using ProgramBench's own helpers.
# Run in the evaluator's Python environment so registry filtering and deduplication
# match the recorded ProgramBench revision used for cross-run comparisons.

import sys
from pathlib import Path

from programbench.eval.eval import EvaluationResult
from programbench.eval.eval_batch import _summary_from_existing
from programbench.submission import score_instance, test_results_map
from programbench.utils.load_data import (
    get_active_branches,
    get_ignored_branches,
    get_ignored_tests,
    load_all_instances,
)


def report(run_dir: Path, iid: str, inst: dict) -> None:
    ej = run_dir / iid / f"{iid}.eval.json"
    if not ej.exists():
        print(f"{iid}: no eval.json under {run_dir}")
        return

    raw = EvaluationResult.model_validate_json(ej.read_text())
    if raw.error_code:
        print(f"{iid}: ERROR {raw.error_code}: {str(raw.error_details)[:120]}")
        return

    branches = get_active_branches(inst)
    bdata = inst.get("branches", {})
    summary = _summary_from_existing(
        iid,
        ej,
        get_ignored_tests(inst),
        current_branches=branches,
        tests_by_branch={b: bdata[b]["tests"] for b in branches if b in bdata},
        ignored_branches=get_ignored_branches(inst),
    )

    kept = test_results_map(ej, inst)
    # Canonical names collapse repeated attempts that remain separate in the raw view.
    canon = score_instance(ej, inst)

    print(f"{iid}")
    print(f"  RAW / CLI        {summary.n_resolved}/{summary.n_tests} = {summary.score * 100:.2f}"
          f"   (CLI table prints {summary.score * 100:.0f})")
    print(f"  CANONICAL-KEPT   {sum(kept.values())}/{len(kept)} = {canon * 100:.2f}")
    print(f"  dedup            {summary.n_tests} rows -> {len(kept)} canonical names")


def main() -> int:
    if len(sys.argv) < 2:
        print('Report BOTH scores ProgramBench can produce for one eval.json, using the\ntool\'s OWN functions rather than re-deriving either.\n\nWHY THIS EXISTS\nThe CLI prints one number and the leaderboard computes a different one from the\nsame file, and they are far apart -- the raw/CLI figure can be about twice\nthe canonical-kept one. Quoting the wrong one, or\nhand-rolling the arithmetic from a partial read of the source, is\nhow a run gets reported as roughly twice as good as it is.\n\n  RAW / CLI      programbench.eval.eval_batch._summary_from_existing\n                 -> n_resolved / n_tests over TEST ROWS, after active-branch and\n                    ignored-branch/test filtering. This is what `programbench\n                    eval` prints in its summary table.\n\n  CANONICAL-KEPT programbench.submission.score_instance\n                 -> the same filtering, then keyed into a dict by\n                    "<branch>/<test_name>". The dict COLLAPSES DUPLICATE\n                    full_names, so a test that appears on many rows counts once.\n                    This is the leaderboard\'s basis (score_run -> score_instance).\n\nThe gap is entirely that dedup: rows >> canonical names. Neither is "wrong";\nthey answer different questions. Report the canonical one for anything that gets\ncompared across runs.\n\nUsage:\n  uv run --project "${PROGRAMBENCH_REPO:-$HOME/programbench}"     python tools/pbench_score_report.py <run_dir> [instance_id ...]\n')
        return 2
    run_dir = Path(sys.argv[1])
    wanted = sys.argv[2:]
    by_id = {}
    for i in load_all_instances():
        key = i.get("instance_id") or i.get("id")
        if key:
            by_id[key] = i
    ids = wanted or sorted(d.name for d in run_dir.iterdir() if d.is_dir() and d.name in by_id)
    for iid in ids:
        if iid not in by_id:
            print(f"{iid}: not in the registry")
            continue
        report(run_dir, iid, by_id[iid])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
