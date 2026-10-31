# Team runtime

Task-neutral Python for running a team: task pack loading and the single-run
driver. Standard library only; requires Python 3.11 for `tomllib`.

| File | Purpose |
|---|---|
| `team_run.py` | Runs one task: prepare hook, services, seed push, Mattermost setup, task issue, staggered wake, idle watchdog, reminders, export hook, quiesce, archives, service logs, evaluate hook |
| `pack.py` | Loads and validates `tasks/<pack>/pack.toml` |
| `schedule.py` | Budget, staggered wake, idle phase, reminder and nudge timing as pure functions |
| `allocate.py` | Port and subnet slots for profiles: fixed for listed tasks, first free slot otherwise |

[`scripts/pbench_run.sh`](../scripts/pbench_run.sh) runs the driver with
`python3 -m agensh.team_run`. The pack is `--pack`, else `AGENSH_PACK` from the
environment, else `AGENSH_PACK` from the profile (as the Makefile uses for
Compose), else `programbench`. Settings come from the environment as before: `TASK`, `PROFILE`, `HOURS`,
`OUT_DIR`, `SKIP_EVAL`, the `PBENCH_WAKE_*`, `PBENCH_BRINGUP_SETTLE_S`,
`PBENCH_START_RETRY_S`, `PBENCH_STAGGERED_BRINGUP` and `PBENCH_WATCHDOG_EARLY`
ramp settings, and the `WORKER_IDLE_*` and `WORKER_CHECK_INTERVAL` watchdog
settings. On failure or SIGTERM the driver quiesces workers, exports, saves
service logs and stops the profile only when shutdown archives verify.

## Pack hooks

Hooks are executables named in `pack.toml` and run on the host from the
repository root. They receive the run's environment plus:

| Variable | Value |
|---|---|
| `AGENSH_ROOT`, `AGENSH_PACK_DIR` | Repository root and the pack directory |
| `AGENSH_TASK`, `AGENSH_PROFILE`, `AGENSH_ENV_FILE` | Task ID, profile name and profile file |
| `AGENSH_OUT_DIR`, `AGENSH_TASK_OUT` | Output root and this task's output directory |
| `AGENSH_GITEA_URL` | Team repository clone URL with admin credentials (keep private) |
| `AGENSH_GITEA_REPO`, `AGENSH_GITEA_PUBLIC_URL` | `<org>/<repo>` and the credential-free URL, for messages |

| Hook | When | Contract |
|---|---|---|
| `prepare` | Before services start | May write the seed tree path to `$AGENSH_TASK_OUT/.seed_path` and `KEY=VALUE` Compose settings to `$AGENSH_TASK_OUT/compose.env`; non-zero stops the run |
| `export` | After the budget, and on the failure path | Delivers the team's result; its exit status is logged, not fatal |
| `evaluate` | After shutdown unless `SKIP_EVAL=1` | Scores the result; non-zero makes the run exit 1 |
