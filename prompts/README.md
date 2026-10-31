# Runtime prompt templates

Task-neutral runtime instructions for the peer cooperation loop in
[the report](../agensh.pdf). Each task pack fills in the task-specific parts;
the ProgramBench pack's prompts are in
[`tasks/programbench/prompts/`](../tasks/programbench/README.md).
Template contents are experiment inputs; keep them fixed when comparing runs.

| Path | Consumer and purpose |
|---|---|
| `agents.txt` | Core worker instructions: identity, shared services, events and the observe/claim/build/verify/merge/publish cycle |
| `kickoff.txt` | Wraps the task brief for initial agent DMs and the task-channel record |
| `planning.txt` | Worker 1's brief in the optional planning phase: architecture and issue breakdown in a `[plan]` PR before the others wake |
| `lifecycle/` | Messages for resumable packs: token budget nearly spent, before a pause, before a finalize, and the resume brief with the project-state summary |
| `main_health/` | Messages from the CI merge gate when `main` breaks, stays broken, has the restriction lifted, or recovers (packs with `ci_gate` only) |

`agents.txt` leaves four places for the task pack, each filled from a file in
the pack's prompt directory:

| Placeholder | Pack file | Content |
|---|---|---|
| `${TASK_OBJECTIVE}` | `objective.txt` | The task's goal, rules and delivery contract |
| `${TASK_FOCUS}` | `focus.txt` | What workers should keep focusing on, completing "Always focus on …;" |
| `${TASK_WORK_CYCLE}` | `work_cycle.txt` | The numbered steps of the work cycle |
| `${TASK_DELIVERY}` | `delivery.txt` | What must be committed for the result to count |

[`agent/render_agents.sh`](../agent/render_agents.sh) builds `/work/AGENTS.md`
from these at worker start: a missing fragment renders empty, each fragment's
trailing newlines are dropped, and identity and team variables are expanded as
before. The image and Compose provide `agents.txt` under its runtime name
`/opt/omcgitea/prompts/agents.md` and the pack's prompt directory at
`/opt/omcgitea/task-prompts`.

Launch messages are rendered with `render_prompt` from
[`scripts/lib_prompts.sh`](../scripts/lib_prompts.sh), which substitutes only
names explicitly supplied by the runner. The runner opens the task issue, sends
staggered kickoff DMs, posts the pack's deadline reminders and nudges idle
workers with the pack's idle messages. Cooperation is defined by these prompts;
the router transports service events and context between native harness turns.

[`tools/render_snapshot.py`](../tools/render_snapshot.py) renders all of these
with the same code paths; use [`scripts/render_check.sh`](../scripts/render_check.sh)
to confirm that a change to the templates or their rendering is intended.
