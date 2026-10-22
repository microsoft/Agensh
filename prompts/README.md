# Fleet prompt templates

Runtime instructions for the peer cooperation loop in [the report](../agensh.pdf).
Template contents are experiment inputs; keep them fixed when comparing runs.

| Path | Consumer and purpose |
|---|---|
| `agents.txt` | Worker identity, shared services and the observe/claim/build/verify/merge/publish cycle |
| `pbench-brief.txt` | Reference-program objective, offline constraints and root build contract |
| `task-brief.txt` | Task/repository identifiers and concrete Mattermost team/channel IDs |
| `kickoff.txt` | Wraps the task brief for initial worker DMs and the task-channel record |
| `idle.txt` | Encourages another useful task after fleet inactivity |
| `deadline-45m.txt`, `deadline-5m.txt` | Channel reminders to integrate work and confirm buildability |
| [single-agent/](single-agent/README.md) | Standalone baseline brief, rules and immediate-continuation text |

The image and Compose mount `agents.txt` and `pbench-brief.txt` under their
historical `.md` names. [`agent/entrypoint.sh`](../agent/entrypoint.sh) expands
identity and the benchmark brief into `/work/AGENTS.md`. Launch messages are
rendered by [`lib_prompts.sh`](../scripts/lib_prompts.sh), which substitutes
only names explicitly supplied by the runner.

The runner opens the task issue, sends staggered kickoff DMs, posts deadline
reminders and nudges idle workers. Cooperation is defined by these prompts;
the router transports service events and context between native Copilot turns.
