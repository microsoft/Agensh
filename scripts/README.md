# Launch, validation and analysis scripts

Host-side entrypoints and helpers for the released single-node fleet and
standalone baseline. Run commands from the repository root; full prerequisites
and configuration examples are in the [reproduction guide](../REPRODUCE.md).

| File(s) | Responsibility |
|---|---|
| `pbench_gen_env.sh` | Writes private per-task profiles, preserving passwords and allocating ports/subnets |
| `launch_single_node.sh` | Checks all fleet profiles, images, host guards and the live model route before launch |
| `lib_launch.sh` | Profile/run naming, environment precedence and inference/evaluation sequencing |
| `pbench_run.sh` | Seeds one task, activates peers, sends reminders/idle nudges, exports and stops workers |
| `pbench_chain.sh` | Separates run/eval phases, salvages interrupted output and verifies trajectory copies before cleanup |
| `pbench_build_pertask_images.sh`, `lib_pbench_images.sh` | Builds v6-based worker images and enforces the reference cleanroom tag |
| `lib_prompts.sh` | Renders launch messages with an explicit substitution allowlist |
| `launch_single_agent.py` | Runs the standalone baseline from JSON config with provenance, snapshots and export |
| `acp_driver.py`, `single_agent_stdio.py` | Drives immediate ACP continuation through the worker's Unix socket |
| `strip_metadata_proxy.py` | Relays model HTTP traffic, removes unsupported fields, injects auth and retries selected failures |
| `pbench-docker-sudo.sh` | Evaluator Docker shim for memory/network settings and appended pytest options |
| `pbench_reboot_guard.sh` | Stops labeled orphan stacks after reboot while retaining their data |
| `pbench_rpm_dashboard.py` | Reads proxy logs/cgroup counters and serves request-rate telemetry |
| `pbench_action_mix.py` | Heuristically categorizes tool requests in archived Copilot logs |
| `pbench_turns_prs.py`, `pbench_gitea_facts.sh` | Reports transcript activity and recorded Gitea issue/PR integration |
| `test_single_agent.py` | Docker integration check using a local model fixture and real Copilot tools |
| `test_eval_pytest_root.py` | Checks official Pandoc JUnit test identities with real cached test blobs |

Fleet inference runs one task at a time; completed-task evaluation can overlap
the next task. `RUN_ID` names trajectories, while profile suffixes, ports,
subnets and data roots isolate concurrent stacks. The normal fleet deadline
exports committed Git HEAD before graceful worker shutdown; final state archives
are recovery artifacts and can contain later work.

The standalone driver immediately resumes completed turns and reloads native
sessions after failures. The fleet waits for queued events and uses a separate
idle watchdog. Both paths use [`agent/archive.py`](../agent/archive.py) to
verify shutdown archives. Canonical comparison scores come from
[`tools/pbench_score_report.py`](../tools/pbench_score_report.py); the chain's
`SCORE` line counts raw attempt rows.

The integration scripts require prepared Docker images; the pytest identity
check also takes `--submission` and `--blob-dir`. Telemetry and trajectory
analysis read existing activity without issuing model requests.
