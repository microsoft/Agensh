# Runtime prompt templates

Runtime instructions for the peer cooperation loop in [the report](../agensh.pdf).
Template contents are experiment inputs; keep them fixed when comparing runs.

| Path | Consumer and purpose |
|---|---|
| `agents.txt` | Agent identity, shared services and the observe/claim/build/verify/merge/publish cycle |
| `pbench_brief.txt` | Reference-program objective, offline constraints and root build contract |
| `task_brief.txt` | Task/repository identifiers and concrete Mattermost team/channel IDs |
| `kickoff.txt` | Wraps the task brief for initial agent DMs and the task-channel record |
| `idle.txt` | Prompts idle agents to continue working |
| `idle_delivery.txt` | Keeps idle recovery focused on integration during the final delivery phase |
| `deadline_45m.txt`, `deadline_5m.txt` | Channel reminders to integrate work and confirm buildability |
| [single-agent/](single-agent/) | Standalone baseline brief, rules and immediate-continuation text |

The image and Compose mount `agents.txt` and `pbench_brief.txt` under their
runtime `.md` names. [`agent/entrypoint.sh`](../agent/entrypoint.sh) expands
identity and the benchmark brief into `/work/AGENTS.md`. Launch messages are
rendered by [`pbench_run.sh`](../scripts/pbench_run.sh), which substitutes
only names explicitly supplied by the runner.

The runner opens the task issue, sends staggered kickoff DMs, posts deadline
reminders and nudges idle workers. Cooperation is defined by these prompts;
the router transports service events and context between native harness turns.

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
