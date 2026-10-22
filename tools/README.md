# Compose and benchmark utilities

Host utilities used by the [launch scripts](../scripts/README.md) to assemble
the fleet and exchange artifacts with ProgramBench.

| File | Purpose |
|---|---|
| `gen-compose-prod.py` | Emits the shared-service base and one worker/router pair per configured peer |
| `pbench_submission.py` | Extracts cleanroom workspace assets and exports committed source as `submission.tar.gz` |
| `pbench_score_report.py` | Reports raw/CLI and canonical-kept scores through ProgramBench's own helpers |

The generator reads `PBENCH_WORKERS_PER_TEAM` (default 16 when called directly)
and leaves Compose `${…}` placeholders for profile substitution. Make writes
its output to ignored `docker/_gen-prod.<profile>.yml` and applies the
[fleet overlay](../docker/docker-compose.pbench.yml). Profile generation
normally supplies the experiment's worker count explicitly.

Submission `seed` copies `/workspace` from a created cleanroom container,
moves the reference executable outside the source tree and removes inherited
Git metadata. `export` archives Git HEAD, removes a root `executable`, and
ensures root `compile.sh` exists, supplying a Make/C fallback when absent.
Only committed source is exported; build output is recreated during evaluation.

Run the score reporter in the pinned ProgramBench environment, for example:

```bash
uv run --project "$PROGRAMBENCH_REPO" \
  python tools/pbench_score_report.py <run-dir> <task-id>
```

Its canonical-kept result collapses repeated test identities and is the score
used for comparisons. Record the evaluator revision alongside that result.
