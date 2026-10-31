# Compose and render utilities

Host utilities that generate and check the team's Compose configuration. The
ProgramBench submission and score tools are in
[`tasks/programbench/tools/`](../tasks/programbench/README.md#launch-scripts-and-tools).

| File | Purpose |
|---|---|
| `gen_compose_prod.py` | Emits the shared-service base and one worker/router pair per configured agent |
| `render_snapshot.py` | Renders prompts, profiles and Compose files for a checkout with fixed fixtures |

The generator reads `AGENSH_WORKERS` (default 16 when called directly)
and leaves Compose `${…}` placeholders for profile substitution. Make writes
its output to ignored `docker/_gen_prod.<profile>.yml` and applies the
[team overlay](../docker/docker_compose.team.yml). Profile generation
normally supplies the experiment's worker count explicitly.

The render snapshot writes what workers and the runner would receive: the
worker `AGENTS.md` and MCP configuration, the task issue, kickoff, idle,
delivery and deadline messages, the standalone baseline prompts, and the
generated profile, Compose base and resolved Compose file for each harness.
It runs the checkout's own profile and Compose generators with a fixed task
and placeholder passwords, for every selected harness and worker count.
`--workers` takes counts and ranges such as `1-4,8,16` (default `1-16`),
`--harness` limits the harnesses, and `--harness-version HARNESS=VERSION`
overrides the pinned releases (Copilot 1.0.70, Pi 1.4.0, Codex 0.164.0,
Claude Code 2.1.312). Exact versions keep rendering offline; `fixtures.json`
records the inputs used. It needs `envsubst` and the Docker Compose CLI but
no running containers. Checkout paths are normalized to `<ROOT>` and the model
credential is redacted. Use [render_check.sh](../scripts/render_check.sh) to
compare two revisions; options after the base revision are passed to both
renders.
