# agensteam — omcgitea × ProgramBench (1-team)

A multi-agent harness that runs Meta's **ProgramBench** on a self-hosted **Gitea**
stack. Five Claude agents — one lead and four workers — collaborate through real
Gitea issues and pull requests, a Mattermost channel and a shared context board,
to reverse-engineer a black-box compiled binary back into a working codebase.

This snapshot is the **1-team / shared-board** arm (sweep 6.11, "method-2a").

## Method

The team is given a compiled reference binary and no source. It has to produce a
repo that builds and behaves the same way.

- **The binary is runnable, not readable.** It is bind-mounted at
  `/opt/pbench/executable` as `root:root 0111`; agents run as uid 10000. They can
  execute it and observe outputs, but cannot disassemble or dump it.
- **Each agent is a container** running `claude-agent-acp`, driven by a per-agent
  `mini-router` sidecar that turns Gitea and Mattermost webhooks into ACP prompts.
  Agents are passive — they act when an event wakes them.
- **Work is coordinated through the forge, not a scheduler.** The lead files goals
  as issues; workers claim them, open PRs, and merge their own. There is no
  reviewer and no approval gate. The lead's job is to keep all four workers loaded.
- **CI is the correctness signal.** Bootstrap commits a workflow that checks out
  base, counts failures, checks out head, counts again, and gates the merge on the
  delta. The lead writes the suite itself on a `tests` branch; `src/ci-list.txt`
  scopes which goals are graded.
- **A shared board** (`board-service`) carries typed notes — FACT / TRIED /
  OBSERVED / FAIL / CLAIM / PATCH_SUMMARY — so a finding by one worker survives
  another's context compaction. This board is what distinguishes method-2a.
- **Egress is locked to one proxy.** The agents' `ANTHROPIC_API_KEY` is a
  placeholder; `strip_metadata_proxy.py` discards it and injects the real upstream
  token, so no agent container ever holds a credential. Agents have no internet.
- **At the deadline** the run quiesces the agents, exports the repo HEAD as
  `submission.tar.gz`, and tears the stack down.

The agent image is built `FROM` the task's own ProgramBench cleanroom, so the
compiler, libraries and crate versions the agents build against are the grader's
by construction. One run is 18 containers: Gitea, MySQL, Mattermost, nginx-edge,
act-runner, bootstrap, secret-service, egress-proxy, board-service, 5 agents,
5 mini-routers.

## Smoke result

One task, **1-hour** budget (the arm's real budget is 6h), on a from-scratch build
of this tree. Score is the official ProgramBench metric.

| | |
|---|---|
| Task | `ffmpeg__ffmpeg.360a402` |
| Score | **8** |
| Tests | 359 passed / 3200 failed / 606 skipped |
| Pipeline | build → stack up → agents → CI gate → merges → export → eval → teardown, all clean |

Read the score with care — two things distort it:

- **One branch dominates.** 3242 of 3559 graded tests live in a single branch that
  passed 3.2%. The other nine branches passed **256/317 = 81%**, four of them at
  96–100%. The headline number mostly measures the one comprehensive suite that
  needs a near-complete implementation.
- **Two of twelve branches never ran.** They produced zero test rows, and the eval
  log shows them going straight from `patch_timeout_method` to `results_read` with
  no `run_tests` step. `test_branch_errors` was empty, so this failed silently.

This run also predates the `_v6` cleanroom fix, so it seeded the April reference
binary while compiling on the June toolchain. Treat it as evidence the pipeline
works end to end, not as a measurement.

## Requirements

- Docker (scripts call `sudo docker`; override with `PBENCH_DOCKER`)
- Python 3 with `pyyaml`
- A ProgramBench checkout at `$HOME/programbench` (override `PROGRAMBENCH_REPO`)
- An Anthropic-compatible endpoint and token
- Every task's cleanroom image pulled host-side — agents have **no internet**:
  ```
  sudo docker pull programbench/ffmpeg_1776_ffmpeg.360a402:task_cleanroom_v6
  ```
  Instance id `a__b.sha` maps to `programbench/a_1776_b.sha:task_cleanroom_v6`.
  The `_v6` suffix is not optional — ProgramBench ships several cleanroom tags per
  task and they are different builds, not rebuilds of each other.

For the 20-task sweep, two systemd units are also required, and the driver refuses
to launch without them:

```
sudo cp docker/pbench.slice /etc/systemd/system/
sudo cp docker/pbench-reboot-guard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pbench-reboot-guard.service
```

`pbench.slice` caps memory for every container (a prior sweep died with one
runaway at 474 GB of 503 GB). The reboot guard stops orphaned stacks at boot —
without it, a maintenance reboot kills the drivers while Docker's
`restart: unless-stopped` resurrects the agents, which then run headless.

## 1. Build the images

Support images. `make up` builds `bootstrap` and `secret-service` itself, but
`mini-router` and `board-service` are referenced by fixed tag and must exist first:

```
sudo docker build -t omcgitea-mini-router:local  mini-router
sudo docker build -t omcgitea-board:local        board-service
```

The agent runtime, which is where `gitea-mcp` and `claude-agent-acp` come from:

```
sudo docker build -f docker/hermes-agent/Dockerfile.v48-matched \
  -t omcgitea-hermes-agent:v48-matched .
```

The per-task agent images — one per task, each `FROM` that task's cleanroom.
Omit `TASKS` to build all 20 (~4 min and ~3.9 GB each, 6 at a time):

```
TAG=pertask-claude bash scripts/pbench_build_pertask_images.sh
```

The `pertask-claude` tag is required: the sweep driver's preflight looks for
`omcgitea-agent-<repo>:pertask-claude` by exact name.

Role prompts under `templates-claude-1team/roles/` are bind-mounted, so editing
one applies on the next run with no rebuild. `entrypoint.sh` is **not** — it is
`COPY`ed into the image, so any change to it needs the per-task images rebuilt.
`tests/pbench/test_agent_image_preflight.sh` compares the baked copy against the
repo's and tells you when they have drifted.

## 2. Mint the 20 profiles

Fill in the template as `.env.org-pbench-method-2a` (no suffix) — every
`CHANGEME`, plus your real `PBENCH_LLM_UPSTREAM` / `UPSTREAM_AUTH_TOKEN`:

```
cp .env.org-pbench-method-2a.example .env.org-pbench-method-2a
vim .env.org-pbench-method-2a
```

Then mint one profile per task. This allocates the host ports, the three pinned
`/24` subnets each stack needs, the data dirs and the per-task `AGENT_IMAGE`:

```
SLUG_BASE=s611 IMAGE_TAG=pertask-claude bash scripts/pbench_gen_env_sweep.sh
```

That writes `.env.org-pbench-method-2a-s611{a..t}`. The
`org-pbench-method-2a-` prefix is load-bearing — it is what makes the Makefile
layer the 1-team + shared-board overlays. Rename out of it and you silently get a
different topology.

## 3. Run all 20 tasks

Preflight first. It validates all 20 profiles, images, ports, subnets, the memory
slice, the reboot guard and a live upstream call, then stops without launching:

```
PREFLIGHT_ONLY=1 bash scripts/pbench_1team_sweep.sh
```

When it reports `preflight OK`, launch:

```
nohup bash scripts/pbench_1team_sweep.sh > out/sweep.out 2>&1 &
```

20 tasks as **4 concurrent chains of 5**, 6h each, 10-minute stagger between chain
starts — so only 4 stacks (20 agents) are ever live at once, and wall clock is
**~30h30m**. Four concurrent stacks is the footprint whose memory behaviour is
measured: peak 31.8 GB of the slice's 402 GB.

Knobs: `HOURS` (default 6), `STAGGER` (default 600s), `SLUG` (default `s611`),
`ROUND` (default 6.11). Edit the `CHAINS` array to run a subset.

Progress:

```
tail -f out/1team-sweep6.11b.driver.log      # the sweep driver
tail -f out/chain-sweep6.11-s611a.driver.log # one chain
```

If a reboot cuts the sweep, re-run the same command — the guard stops stacks
cleanly, `DATA_ROOT` survives, and `pbench_chain.sh` salvages an interrupted task.
A cut task's submission still exports offline from its Gitea repo.

## Run a single task

```
TASK=ffmpeg__ffmpeg.360a402 \
HOURS=6 \
PROFILE=org-pbench-method-2a-s611a \
  bash scripts/pbench_run_1team.sh 2>&1 | tee out/myrun.log
```

The runner narrates to **stderr** and nothing captures it for you, so redirect it
yourself. It refuses to start if `out/pbench/$TASK` or the profile's data dir
already exist — archive them before re-running.

```
make ps    PROFILE=org-pbench-method-2a-s611a
make logs  PROFILE=org-pbench-method-2a-s611a
```

Gitea is at `http://localhost:$EDGE_HTTP_PORT`, Mattermost at `$EDGE_MM_PORT`.

## Output

Under `out/pbench/$TASK/` (or `out/pbench-sweep6.11-<slug>/$TASK/` in a sweep):

- `submission.tar.gz` — repo HEAD, what ProgramBench grades
- `*.eval.json` — full per-test results, if the evaluator ran
- `bin/executable` — the reference binary as mounted (root-owned, `0111`)
- `_seed/`, `_push/` — the seeded workspace and the export staging area
- `export.log`, `board-lifecycle.log`

`scripts/pbench_traj_metrics.sh` and `scripts/board_report.py` summarise a
finished run's trajectory and board traffic.

## Layout

- `scripts/pbench_run_1team.sh` — one task end-to-end
- `scripts/pbench_1team_sweep.sh` — the 20-task sweep driver
- `scripts/pbench_chain.sh` — one chain's tasks back to back; salvages an interrupted run
- `scripts/pbench_gen_env_sweep.sh` — mints the per-task profiles
- `scripts/pbench_build_pertask_images.sh` — one agent image per task, from its cleanroom
- `scripts/pbench_reboot_guard.sh` — stops stacks whose driver did not survive a reboot
- `docker/` — compose stack (Gitea, agents, egress lock, anti-cheat bin isolation)
- `docker/hermes-agent/templates-claude-1team/` — role prompts; `pbench-brief.md` is the task statement
- `board-service/`, `mcp-board/` — the shared context board and its MCP interface
- `tests/pbench/` — isolation and contract tests
- `v2docs/` — requirements, design, interface, acceptance

## Tests

```
bash tests/pbench/test_role_fragments.sh        # prompt contract
bash tests/pbench/test_agent_image_preflight.sh # runner guards the image it runs
bash tests/pbench/test_cleanroom_tag.sh         # seed image == build image
bash tests/pbench/test_repo_relative_paths.sh   # scripts operate on this checkout
bash tests/pbench/test_gen_topology.sh          # compose topology
```

Isolation tests (`test_bin_isolation.sh`, `test_net_isolation.sh`,
`test_submission_export.sh`) need a live stack and run against a real compose
project, not mocks.

> Sanitized snapshot for sharing — real credentials and endpoints are **not**
> included. Copy `.env.org-pbench-method-2a.example` and fill in your own values.

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit [Contributor License Agreements](https://cla.opensource.microsoft.com).

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
