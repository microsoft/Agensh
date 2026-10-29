# Launch scripts

Host-side setup, launch, evaluation and recovery for the released single-node
team and standalone baseline. Run commands from the repository root; full
prerequisites and configuration examples are in the
[reproduction guide](../REPRODUCE.md).

| File(s) | Responsibility |
|---|---|
| `pbench_gen_env.sh` | Writes private per-task profiles, preserving passwords and allocating ports/subnets |
| `launch_single_node.sh` | Checks all team profiles, images, host guards and the live model route before launch |
| `lib_launch.sh` | Profile/run naming, environment precedence and inference/evaluation sequencing |
| `pbench_run.sh` | Seeds one task, starts workers, sends reminders/idle nudges, exports and stops workers |
| `pbench_chain.sh` | Separates run/eval phases, salvages interrupted output and verifies trajectory copies before cleanup |
| `pbench_build_pertask_images.sh`, `lib_pbench_images.sh` | Builds v6-based worker images and enforces the reference cleanroom tag |
| `launch_single_agent.py` | Runs the standalone baseline from JSON config with provenance, snapshots and export |
| `acp_driver.py`, `single_agent_stdio.py` | Drives immediate ACP continuation through the worker's Unix socket |
| `strip_metadata_proxy.py` | Relays model HTTP traffic, removes unsupported fields, injects auth and retries selected failures |
| `code_mode_limits.py` | Supplies native Code Mode defaults and the strict Codex tool-result text byte guard |
| `pbench_docker_sudo.sh` | Evaluator Docker shim for memory/network settings and appended pytest options |
| `pbench_reboot_guard.sh` | Stops labeled orphan stacks after reboot while retaining their data |

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
[`agent/archive.py`](../agent/archive.py) to verify shutdown archives.
Canonical comparison scores come from
[`tools/pbench_score_report.py`](../tools/pbench_score_report.py); the chain's
`SCORE` line counts raw attempt rows.

`pbench_build_pertask_images.sh` uses `TAG` (default `pbench`) for output images
and the fixed `omcgitea-agent-base:pbench` artifact. Profile generation instead
uses `AGENT_IMAGE_TAG`; exporting that variable alone does not retag builds.
All launchers resolve shared settings through
[`agent/harness_config.py`](../agent/harness_config.py), using
[`agent/config/harness.json`](../agent/config/harness.json) by default.
`--harness-config` selects an override file for model, reasoning effort, prompt
and output budgets, and compaction. Profiles retain those settings, and preflight
validates them instead of forcing high reasoning or a fixed context budget.
Pass `--agent-harness copilot`, `--agent-harness pi`, `--agent-harness codex` or
`--agent-harness claude` consistently
to both scripts and `launch_single_node.sh`, with `--harness-version VERSION`
to select an exact release. The arguments override the environment; defaults
are Copilot 1.0.70, Pi 1.4.0, Codex 0.164.0 and the latest Claude Code release.
Latest versions are resolved to exact package versions before launch. Image names include the
harness: `omcgitea-agent-<task-slug>-<harness>:<tag>`. The standalone launcher accepts
the same arguments, overriding its optional `agent_harness` and `harness_version`
JSON fields. Each image contains
only the selected harness; private Node also serves the team's MCP helpers.
The image checks reject combined or mismatched installations.
Pi output limits and the Codex catalog are prepared at runtime from the selected
configuration. Both proxy Compose paths mount
`code_mode_limits.py`, apply a 600-second total request deadline and use low
response verbosity. Unsupported question-tool filtering remains enabled.
Proxy retries are separate from native harness retries.
`UPSTREAM_RETRY_ATTEMPTS` counts total proxy attempts, with a default of four;
one disables proxy retries. Selected HTTP 429/5xx and non-timeout transport
failures can retry; local connect/read timeouts end the proxy request.
Both model-proxy Compose paths filter human-question tool declarations and their
pinned Codex system/developer guidance for headless workers. User messages are
preserved. For Codex, `UPSTREAM_AGENT_HARNESS=codex` enables the exact UTF-8 byte
ceiling on tool-result text in Responses and compaction requests; explicit smaller
tool budgets remain effective. Copilot and Pi keep their native Responses
tool-output handling; Claude uses the Messages tool-result guard.
The shared MCP allowlist is in
[`agent/config/mcp_allowed_tools.json`](../agent/config/mcp_allowed_tools.json).

Team runs save each container's timestamped stdout/stderr under the task output's
`service-logs/` before teardown, including the model proxy and all routers.
For private cohort/base-image tags and uncached builds, use the explicit Docker
commands in the reproduction guide.

The team watchdog scans native journal metadata with sudo without an unprivileged
directory check, so UID10000 mode0700 Pi/Codex/Claude directories do not suppress idle
recovery. Defaults remain 600 seconds idle, 600 seconds between nudges and a
60-second scan. Nudges respect the delivery phase: the final 45 minutes for long
runs or the final five minutes for runs at most 45 minutes long.
