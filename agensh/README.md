# Team runtime

Task-neutral Python for running a team: task pack loading and the single-run
driver. Standard library only; requires Python 3.11 for `tomllib`.

| File | Purpose |
|---|---|
| `team_run.py` | Runs one task: prepare hook, services, seed push, Mattermost setup, task issue, staggered wake, idle watchdog, reminders, export hook, quiesce, archives, service logs, evaluate hook |
| `pack.py` | Loads and validates `tasks/<pack>/pack.toml` |
| `schedule.py` | Budget, staggered wake, idle phase, reminder and nudge timing as pure functions |
| `allocate.py` | Port and subnet slots for profiles: fixed for listed tasks, first free slot otherwise |
| `backlog.py` | Backlog synchronization: live board claims citing `#<n>` become issue assignees |
| `quality.py` | CI merge gate: the Actions workflow generated from acceptance commands, and the main-health timing rules and PR statuses |
| `project.py` | Project files for repository packs: `profile`, `build` and `run` (see the [software-project pack](../tasks/software-project/README.md)) |

[`scripts/team_run.sh`](../scripts/team_run.sh) runs the driver with
`python3 -m agensh.team_run`. The pack is `--pack`, else `AGENSH_PACK` from the
environment, else `AGENSH_PACK` from the profile (as the Makefile uses for
Compose), else `programbench`. Settings come from the environment as before: `TASK`, `PROFILE`, `HOURS`,
`OUT_DIR`, `SKIP_EVAL`, the `AGENSH_WAKE_*`, `AGENSH_BRINGUP_SETTLE_S`,
`AGENSH_START_RETRY_S`, `AGENSH_STAGGERED_BRINGUP` and `AGENSH_WATCHDOG_EARLY`
ramp settings, and the `WORKER_IDLE_*` and `WORKER_CHECK_INTERVAL` watchdog
settings. `AGENSH_MODE` is `run` (default), or `resume` / `finalize` for a
paused run of a resumable pack (see [run lifecycle](#run-lifecycle)). Packs with
`[acceptance] ci_gate` also run the main-health loop
(`AGENSH_HEALTH_INTERVAL_S`, default 15) described below. On failure or SIGTERM the driver quiesces workers, exports, saves
service logs and stops the profile only when shutdown archives verify.

## Pack hooks

Hooks are named in `pack.toml` and run on the host from the repository root,
`.py` hooks with the driver's Python and others with Bash. They receive the run's environment plus:

| Variable | Value |
|---|---|
| `AGENSH_ROOT`, `AGENSH_PACK_DIR` | Repository root and the pack directory |
| `AGENSH_TASK`, `AGENSH_PROFILE`, `AGENSH_ENV_FILE` | Task ID, profile name and profile file |
| `AGENSH_OUT_DIR`, `AGENSH_TASK_OUT` | Output root and this task's output directory |
| `AGENSH_GITEA_URL` | Team repository clone URL with admin credentials (keep private) |
| `AGENSH_GITEA_REPO`, `AGENSH_GITEA_PUBLIC_URL` | `<org>/<repo>` and the credential-free URL, for messages |

| Hook | When | Contract |
|---|---|---|
| `prepare` | Before services start | May write the seed tree path to `$AGENSH_TASK_OUT/.seed_path`, or a git clone whose `HEAD` becomes `main` with its history to `.seed_git`; `KEY=VALUE` Compose settings to `compose.env` (a pack with `network = "auto"` must set `AGENSH_RUN_NETWORK` there); extra task-brief variables to `brief_vars.json`; non-zero stops the run |
| `sync` | `[lifecycle] sync_before_end` (default 30m) before the end, and before `export` on the normal path, with `AGENSH_SYNC_PHASE=scheduled` or `final` | Brings upstream changes into the team's `main`; failures are logged, and `main` is delivered as it is |
| `export` | After the budget, and on the failure path | Delivers the team's result; its exit status is logged, not fatal |
| `evaluate` | After shutdown unless `SKIP_EVAL=1` | Scores the result; non-zero makes the run exit 1 |

## CI merge gate

A pack sets `[acceptance] ci_gate = true` and may list `protected_paths`. Then:

- Its prepare hook commits `.gitea/workflows/agensh.yml` from
  `quality.render_workflow` on top of the seed: PRs run the fast checks as
  `agensh / pr`, pushes to `main` run the full suite as `agensh / main`. Steps are
  `run:` only, so offline teams need no actions from the internet. Its export hook
  removes the file before delivery.
- Bootstrap makes `agensh / pr (pull_request)` and `agensh/main-health` required
  checks on `main` and creates the `fix-main` label. After the seed push the
  driver sets the protected paths (the profile's `AGENSH_PROTECTED_FILES`, else
  the pack's) as Gitea protected files, which only the administrator can change;
  Gitea 1.22 cannot check protected files on the push that creates `main`.
- The driver posts `agensh/main-health` on every open PR head. While `main` passes
  it is `success`. When the full suite fails on `main`, the merge author is sent
  [`prompts/main_health/broken.txt`](../prompts/main_health/broken.txt) (every
  worker, for a direct push), a `FAIL` entry goes on the board, and only PRs
  labeled `fix-main` or titled `[fix-main] ...` get `success`; the rest are
  `pending`. After 15 minutes every worker is alerted; after 60 minutes the
  restriction lifts with a `NOTICE` in the run log and a channel message, so a
  flaky suite cannot stall the team. Recovery posts a `FACT` and a channel message.
  The timeline is recorded in `$AGENSH_TASK_OUT/main-health.json`.

## Backlog synchronization

With `[coordination] backlog = "issues"`, the driver reads the board every
`AGENSH_BACKLOG_INTERVAL_S` (default 30) seconds. A live `CLAIM` whose text cites
`#<n>` makes its author an assignee of issue `n`; when the claim expires, the
driver removes only the assignments it made. Closed issues keep their
assignees as the record of who did the work. Synchronization is one-way: the
board stays the source of truth for who is working on what.

## Run lifecycle

A pack with `[lifecycle] resumable = true` keeps its state between run segments.
A segment ends on the first of its `stop_when` conditions: `budget` (the
wall-clock `HOURS`), `tokens` (the profile's `AGENSH_MAX_MODEL_TOKENS`, input
plus output across the team), `issue_closed` (issue #1 closed), or a request
written to `$AGENSH_TASK_OUT/control` by `python3 -m agensh.project pause` or
`finalize`.

| Outcome | When | Does |
|---|---|---|
| pause | a pause request or the token budget | Tells workers to push and record their work (`AGENSH_PAUSE_GRACE_S`, default 120; none when tokens are spent), seals archives, stops the containers and keeps all data |
| finalize | the wall clock, issue #1 closed, or a finalize request | Tells workers to wrap up `finalize_notice` before a timed end (or for the grace period otherwise), syncs upstream, exports, stops and evaluates |

At 90% of the token budget every worker gets
[`prompts/lifecycle/budget_warning.txt`](../prompts/lifecycle/budget_warning.txt);
at 100% the egress proxy refuses model requests with HTTP 429 and the driver
pauses. `resume` brings the services back, syncs upstream, clears the stored
ACP session ids so every worker starts a fresh native session, and wakes each
worker with [`prompts/lifecycle/resume.txt`](../prompts/lifecycle/resume.txt):
the task brief plus a state summary of open issues and PRs, recent merges,
`main`'s CI and the sync result. A crash restart inside a segment still restores
the stored session, as the router always did. `run_state.json` records each
segment and the state (`running`, `paused`, `finalized` or `failed`);
`service-logs-<n>` keeps each later segment's logs.
