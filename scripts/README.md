# Core scripts

Task-neutral host scripts for running a team and its model proxy. Task packs
bring their own launch scripts; the ProgramBench ones are in
[`tasks/programbench/`](../tasks/programbench/README.md). Run commands from the
repository root; full prerequisites and configuration examples are in the
[reproduction guide](../REPRODUCE.md).

| File(s) | Responsibility |
|---|---|
| `team_run.sh` | Runs one task with the [team driver](../agensh/README.md) and the profile's task pack |
| `team_status.py` | Summarizes a running profile: containers, native activity, events, token usage, board entries and PRs |
| `strip_metadata_proxy.py` | Relays model HTTP traffic, removes unsupported fields, injects auth and retries selected failures |
| `code_mode_limits.py` | Supplies native Code Mode defaults and the strict Codex tool-result text byte guard |
| `egress_filter.py` | Forward proxy for the `allowlist` network: package registries plus project domains, every decision logged |
| `usage_meter.py` | Parses token usage from buffered model responses and keeps per-agent totals for the proxy |
| `agensh_reboot_guard.sh` | Stops labeled orphan stacks after reboot while retaining their data |
| `lib_prompts.sh` | `render_prompt`, shared by the runner and the render snapshot |
| `render_check.sh` | Diffs rendered prompts, profiles and Compose files against a base revision (default `upstream/main`, then `origin/main`); exits 3 on differences |

Pi output limits and the Codex catalog are prepared at runtime from the selected
configuration. Both proxy Compose paths mount
`code_mode_limits.py`, apply a 600-second total request deadline and use low
response verbosity. Unsupported question-tool filtering remains enabled.
Responses reasoning items and the `reasoning.encrypted_content` include are
forwarded, so stateless (`store: false`) clients such as Copilot keep the
model's earlier reasoning across tool calls. Set `STRIP_REASONING=1` at launch
only for an upstream that rejects reasoning replay. The proxy's `REQUEST` log
line reports `reasoning_items` per request.
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

The proxy accounts token usage per agent. Each team worker sends
`local-proxy-<agent>` as its proxy key, which labels requests for metering and is
not a credential; the proxy is reachable only on the private network and
replaces the key with the upstream credential. Requests with any other key are
counted as `unlabelled`. Usage comes from the buffered response's `usage` fields
(Responses, Chat Completions and Anthropic Messages, as JSON or SSE). Responses
and Chat Completions include cached tokens in `input_tokens`; Messages keep cache
reads and writes in `cached_input_tokens` and `cache_creation_input_tokens`.
Team runs append one record per model request, without prompt content, to
`$DATA_ROOT/<profile>/usage/usage.jsonl`, and the proxy serves current totals at
`GET /usage` on port 4180. Accounting failures never block forwarding.

While a team runs, summarize it with:

```bash
python3 scripts/team_status.py "$PROFILE"         # table
python3 scripts/team_status.py --json "$PROFILE"  # machine-readable
```

It reads the profile file and queries the containers through `sudo -n docker`
(set `DOCKER` to override), without changing anything. Idle time comes from the
same native journals the watchdog scans.

Team runs save each container's timestamped stdout/stderr under the task output's
`service-logs/` before teardown, including the model proxy and all routers.
For private cohort/base-image tags and uncached builds, use the explicit Docker
commands in the reproduction guide.

The team watchdog scans native journal metadata with sudo without an unprivileged
directory check, so UID10000 mode0700 Pi/Codex/Claude directories do not suppress idle
recovery. Defaults remain 600 seconds idle, 600 seconds between nudges and a
60-second scan. Nudges respect the delivery phase: the final 45 minutes for long
runs or the final five minutes for runs at most 45 minutes long.
