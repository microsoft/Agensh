# ProgramBench task pack

The task-specific parts of the ProgramBench experiments: agents rebuild a
reference program from its behavior and bundled documentation. The core
cooperation instructions are in [`prompts/`](../../prompts/README.md), and the
[team driver](../../agensh/README.md) runs the lifecycle. The ProgramBench-only
tools and launch scripts still live under `tools/` and `scripts/`; they move
here with the naming migration in the [task pack design](../../docs/task_pack_design.md).

## Pack file and hooks

[`pack.toml`](pack.toml) names the hooks, the runner messages and their
timing, and the issue title and seed commit message.

| Hook | Does |
|---|---|
| [`hooks/prepare.sh`](hooks/prepare.sh) | Pulls the `task_cleanroom_v6` image, extracts `/workspace` as the seed, stages the reference binary mode 0111 as root outside the seed, records `reference.json`, and passes `PBENCH_BIN` to Compose |
| [`hooks/export.sh`](hooks/export.sh) | Exports committed `main` as `submission.tar.gz` with three attempts; leaves `EXPORT_FAILED` and an empty archive on failure |
| [`hooks/evaluate.sh`](hooks/evaluate.sh) | Runs `programbench eval` inside `pbench.slice` through the Docker shim |

The deadline reminders fire 45 and 5 minutes before the end and are skipped when
their time has already passed at the start of the budget.

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
