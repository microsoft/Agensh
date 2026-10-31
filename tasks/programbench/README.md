# ProgramBench task pack

The task-specific parts of the ProgramBench experiments: agents rebuild a
reference program from its behavior and bundled documentation. The core
cooperation instructions are in [`prompts/`](../../prompts/README.md), and the
[team driver](../../agensh/README.md) runs the lifecycle. Its launch
scripts, tools and the standalone baseline are also here (see
[Launch scripts and tools](#launch-scripts-and-tools)).

## Pack file and hooks

[`pack.toml`](pack.toml) names the hooks, the runner messages and their
timing, and the issue title and seed commit message.

| Hook | Does |
|---|---|
| [`hooks/prepare.sh`](hooks/prepare.sh) | Pulls the `task_cleanroom_v6` image, extracts `/workspace` as the seed, stages the reference binary mode 0111 as root outside the seed, records `reference.json`, and passes `PBENCH_BIN` to Compose |
| [`hooks/export.sh`](hooks/export.sh) | Exports committed `main` as `submission.tar.gz` with three attempts; leaves `EXPORT_FAILED` and an empty archive on failure |
| [`hooks/evaluate.sh`](hooks/evaluate.sh) | Runs `programbench eval` inside `agensh.slice` through the Docker shim |

The deadline reminders fire 45 and 5 minutes before the end and are skipped when
their time has already passed at the start of the budget. `[environment]` keeps
workers on the internal network (`network = "offline"`) and mounts the staged
reference binary at `/opt/pbench/executable`; `board_id = "pbench-top"` names
the shared context board.

## Launch scripts and tools

Run these from the repository root; the [reproduction guide](../../REPRODUCE.md)
has the full sequence.

| File(s) | Responsibility |
|---|---|
| `scripts/gen_env.sh` | Writes private per-task profiles (`.env.programbench-<task-slug>`), preserving passwords and allocating ports/subnets |
| `scripts/launch.sh` | Checks all team profiles, images, host guards and the live model route, then runs the tasks |
| `scripts/lib_launch.sh` | Profile/run naming, environment precedence and inference/evaluation sequencing |
| `scripts/chain.sh` | Separates run/eval phases, salvages interrupted output and verifies trajectory copies before cleanup |
| `scripts/build_images.sh`, `scripts/lib_images.sh` | Builds v6-based worker images and enforces the reference cleanroom tag |
| `scripts/eval_docker_shim.sh` | Evaluator Docker shim for memory/network settings and appended pytest options |
| `scripts/launch_single_agent.py` | Runs the standalone baseline from JSON config with provenance, snapshots and export |
| `scripts/acp_driver.py`, `scripts/single_agent_stdio.py` | Drives immediate ACP continuation through the worker's Unix socket |
| `docker/single_agent.yml` | Standalone selected harness, proxy, private mounts and subnets |
| `tools/submission.py` | Extracts cleanroom workspace assets and exports committed source as `submission.tar.gz` |
| `tools/score_report.py` | Reports raw/CLI and canonical-kept scores through ProgramBench's own helpers |

Team inference runs one task at a time; completed-task evaluation can overlap
the next task. `RUN_ID` names trajectories, while profile suffixes, ports,
subnets and data roots isolate concurrent stacks. The normal team deadline
exports committed Git HEAD before graceful worker shutdown; final state archives
are recovery artifacts and can contain later work.

The standalone driver immediately resumes completed turns while more than
60 seconds remain, and tries to reload native sessions after transport failures.
Its periodic and final snapshots stage and commit non-ignored workspace changes
before source export. The team exports Gitea HEAD before shutdown, waits for
queued events between turns and uses a separate idle watchdog. Both paths use
[`agent/archive.py`](../../agent/archive.py) to verify shutdown archives.
Canonical comparison scores come from
[`tools/score_report.py`](tools/score_report.py); the chain's
`SCORE` line counts raw attempt rows.

`scripts/build_images.sh` uses `TAG` (default `pbench`) for output images
and the fixed `omcgitea-agent-base:pbench` artifact. Profile generation instead
uses `AGENT_IMAGE_TAG`; exporting that variable alone does not retag builds.
All launchers resolve shared settings through
[`agent/harness_config.py`](../../agent/harness_config.py), using
[`agent/config/harness.json`](../../agent/config/harness.json) by default.
`--harness-config` selects an override file for model, reasoning effort, prompt
and output budgets, and compaction. Profiles retain those settings, and preflight
validates them instead of forcing high reasoning or a fixed context budget.
Pass `--agent-harness copilot`, `--agent-harness pi`, `--agent-harness codex` or
`--agent-harness claude` consistently
to both scripts and `scripts/launch.sh`, with `--harness-version VERSION`
to select an exact release. The arguments override the environment; defaults
are Copilot 1.0.70, Pi 1.4.0, Codex 0.164.0 and the latest Claude Code release.
Latest versions are resolved to exact package versions before launch. Image names include the
harness: `omcgitea-agent-<task-slug>-<harness>:<tag>`. The standalone launcher accepts
the same arguments, overriding its optional `agent_harness` and `harness_version`
JSON fields. Each image contains
only the selected harness; private Node also serves the team's MCP helpers.
The image checks reject combined or mismatched installations.

Submission `seed` copies `/workspace` from a created cleanroom container,
moves the reference executable outside the source tree and removes inherited
Git metadata. `export` archives Git HEAD, removes a root `executable`, and
ensures root `compile.sh` exists, supplying a Make/C fallback when absent.
Only committed source is exported; build output is recreated during evaluation.

Set `RUN_DIR` to the completed results directory and `TASK_ID` to the selected
task. Run the score reporter in the pinned ProgramBench environment:

```bash
uv run --project "$PROGRAMBENCH_REPO" \
  python tasks/programbench/tools/score_report.py "$RUN_DIR" "$TASK_ID"
```

Its canonical-kept result collapses repeated test identities and is the score
used for comparisons. Record the evaluator revision alongside that result.


## Prompts

| Path | Consumer and purpose |
|---|---|
| `prompts/objective.txt` | `${TASK_OBJECTIVE}` in the worker instructions: reference-program goal, offline constraints and root build contract |
| `prompts/focus.txt` | `${TASK_FOCUS}`: keep reproducing the reference |
| `prompts/work_cycle.txt` | `${TASK_WORK_CYCLE}`: observe the reference, claim, rebuild, compare, merge, publish |
| `prompts/delivery.txt` | `${TASK_DELIVERY}`: commit what the grader's fresh-clone build needs |
| `prompts/task_brief.txt` | Task issue and kickoff: task/repository identifiers and Mattermost team/channel IDs |
| `prompts/idle.txt` | Prompts idle agents to continue working |
| `prompts/idle_delivery.txt` | Keeps idle recovery focused on integration during the final delivery phase |
| `prompts/deadline_45m.txt`, `prompts/deadline_5m.txt` | Channel reminders to integrate work and confirm buildability |
| [`prompts/single-agent/`](prompts/single-agent/) | Standalone baseline brief, rules and immediate-continuation text |

The worker instructions rendered from these fragments are byte-identical to the
earlier single-file `prompts/agents.txt` with `pbench_brief.txt`; the render
check compares both layouts.

## Standalone baseline

The standalone launcher and ACP driver use these templates:

| File | Purpose |
|---|---|
| `single-agent/brief.txt` | Task objective, reference location, source/build contract and budget |
| `single-agent/rules.txt` | Behavioral-observation requirements and source/binary reuse restrictions |
| `single-agent/resume.txt` | Continuation after a completed prompt while more than 60 seconds remain |

The launcher substitutes `${TASK}` and `${HOURS}`, installs private copies under
`~/.pbench/` and records template hashes. The first prompt combines rules and
brief; later prompts use the resume text in the same ACP session. The budget
starts after session initialization. Pi waits for native retries and compaction
to settle. At a prompt boundary with at most 15 minutes left, the driver adds
one deadline notice; at 60 seconds or less it starts no more prompts. A pending
prompt remains bounded by the deadline. Transport recovery tries to reload the
same session; a fresh session receives the complete initial prompt again.

These templates preserve the standalone condition. Team runs use collaboration
instructions and ten-minute idle nudges.
