# Compose and benchmark utilities

Host utilities used by the [launch scripts](../scripts/README.md) to configure
team runs and exchange artifacts with ProgramBench.

| File | Purpose |
|---|---|
| `gen-compose-prod.py` | Emits the shared-service base and one worker/router pair per configured agent |
| `pbench_submission.py` | Extracts cleanroom workspace assets and exports committed source as `submission.tar.gz` |
| `pbench_score_report.py` | Reports raw/CLI and canonical-kept scores through ProgramBench's own helpers |
| `coordination_probe.py` | Offline synthetic shared-context portability probe; no model or service execution |

The generator reads `PBENCH_WORKERS_PER_TEAM` (default 16 when called directly)
and leaves Compose `${…}` placeholders for profile substitution. Make writes
its output to ignored `docker/_gen-prod.<profile>.yml` and applies the
[team overlay](../docker/docker-compose.pbench.yml). Profile generation
normally supplies the experiment's worker count explicitly.

Submission `seed` copies `/workspace` from a created cleanroom container,
moves the reference executable outside the source tree and removes inherited
Git metadata. `export` archives Git HEAD, removes a root `executable`, and
ensures root `compile.sh` exists, supplying a Make/C fallback when absent.
Only committed source is exported; build output is recreated during evaluation.

Set `RUN_DIR` to the completed results directory and `TASK_ID` to the selected
task. Run the score reporter in the pinned ProgramBench environment:

```bash
uv run --project "$PROGRAMBENCH_REPO" \
  python tools/pbench_score_report.py "$RUN_DIR" "$TASK_ID"
```

Its canonical-kept result collapses repeated test identities and is the score
used for comparisons. Record the evaluator revision alongside that result.

## Proposed coordination portability experiment

The [proposed ADR](../docs/adrs/adr-001-coordination-portability-validation.md)
describes a bounded experiment for reusing coordination patterns in another
agent stack. Run `python3 tools/coordination_probe.py` from the repository root
with Python 3.11 or newer. All nine cases must execute with zero failures,
errors or skips. The probe uses the actual in-process board implementations and
synthetic inputs; it does not qualify distributed recovery, task quality, AWS
deployment or the paper's scaling results.
