# ProgramBench task pack

The task-specific parts of the ProgramBench experiments: agents rebuild a
reference program from its behavior and bundled documentation. The core
cooperation instructions are in [`prompts/`](../../prompts/README.md). The
pack's runner hooks, tools and `pack.toml` follow with the pack-loading step of
the [task pack design](../../docs/task_pack_design.md).

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
