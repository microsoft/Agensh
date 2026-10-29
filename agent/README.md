# Agent runtime

Builds and supervises the selected Copilot, Pi, Codex or Claude Code harness. The router supplies
events over ACP; the [agent prompt](../prompts/README.md) supplies the cooperation
loop described in [the report](../agensh.pdf).

| Path | Purpose |
|---|---|
| `Dockerfile.base` | Caches the upstream Gitea MCP binary in an artifact image |
| `Dockerfile` | Extends a v6 cleanroom with one selected harness, private Node and MCP tools |
| `entrypoint.sh` | Configures team or standalone workers and starts the shared supervisor |
| [copilot/](copilot/) | Copilot team and standalone setup, using its native ACP runtime |
| [pi/](pi/) | Pi configuration and native RPC-to-ACP adapter |
| [codex/](codex/) | Codex configuration and native app-server-to-ACP adapter |
| [claude/](claude/) | Native Claude Code stream-json sessions and ACP adapter |
| `acp_bridge.py` | Serves the configured Unix socket, starts the non-root ACP child and handles cancellation |
| `archive.py` | Saves HOME/workspace state and validates shutdown archives before cleanup |
| `check_harness.py` | Rejects missing, mismatched or combined harness installations |
| `harness_config.py` | Shared settings, versions, private config writes and native output preparation |
| `config/harness.json` | Selected harness/version, model, reasoning, prompt/output budgets and compaction |
| [config/](config/) | MCP server template and tool exclusions |

The root supervisor launches the harness as UID/GID 10000. Team workers use
`HOME=/opt/data/home` and workspace `/work`. Standalone workers use
`HOME=/home/ccagent` and workspace `/workspace`, with the same data also mounted
at `/opt/data/home` and `/work` for archiving. The reference executable is mounted
separately so the child can run it without reading its bytes. Private Node is
installed under `/opt/agentrt` to preserve the task's existing toolchain.

Use `--agent-harness copilot`, `pi`, `codex` or `claude` for preparation and launch;
the shipped configuration selects Copilot.
The scripts also accept `AGENT_HARNESS`; direct Docker builds use
`--build-arg AGENT_HARNESS=copilot|pi|codex|claude`. The standalone launcher accepts the
same argument or an `agent_harness` JSON field. Use `--harness-version VERSION` for
an exact release or `latest`; defaults are Copilot 1.0.70, Pi 1.4.0, Codex 0.164.0
and the latest Claude Code release. The selected latest release is resolved and
recorded as an exact version for the run.
Direct Docker builds accept `COPILOT_CLI_VERSION`, `PI_CLI_VERSION`,
`CODEX_CLI_VERSION` and `CLAUDE_CLI_VERSION` build arguments. Docker's final stage
contains only the selected harness. Pi uses `@earendil-works/pi-coding-agent`;
Copilot uses `@github/copilot`. Their default private Node versions are 22.19.0
and 22.14.0, respectively. Codex uses the native executable and its native Code
Mode host, copied from the selected npm artifact without its JavaScript launcher
or voice runtime.
Pi and Copilot need Node for their CLIs. Codex and Claude Code use native
executables but retain private Node (22.19.0 by default) for MCP helpers. Claude's
adapter retains stream-json sessions, tool events, interruption and resume.
Claude Code requires the Anthropic Messages API; the other harnesses require
Responses. A gateway used across all four harnesses needs both APIs. The
[reproduction guide](../REPRODUCE.md#model-api-routes) lists the default paths.
npm is used only in install stages and is not added to the private runtime.
The task cleanroom's own tools are preserved.

Each image copies only its selected harness directory into `/opt/omcgitea`.
The bridge, archives, resource policy and MCP configuration stay shared at the
agent root. The shared MCP deny list is `config/mcp_deny_tools.json`; its
Copilot selector syntax is translated for Pi and Codex.

Shared defaults follow the Copilot experiment: a 272,000-token prompt budget,
80% compaction and a 1 MiB text-output budget. Copilot, Pi and Codex use a 95%
effective boundary (258,400 tokens at the default prompt budget) and the
600-second/five-native-retry reference profile;
Claude Code uses its native context and SDK retry behavior under the same
proxy deadline. The default `output_tokens: null` adds no Agensh generation-cap
override; native/provider limits still apply.
Pi's published ESM RPC entry runs the
reviewed native output-limit adjustments, including its separate MCP result cap.
Native truncation notices and full-output temporary files are preserved.
Codex retains its complete native catalog and Code Mode host, with native history
truncation and supported cell-budget defaults. Its model proxy additionally caps
each tool result's text to the configured UTF-8 byte budget, including the
truncation notice; images and tool-call IDs are preserved. This extra guard is
scoped to Codex in both standalone and team runs.
`config/harness.json` or `--harness-config` selects the model, reasoning effort,
prompt/output/tool budgets and compaction; timeout and retry controls are not
fields in that file. Pi's reviewed JS output constants and Codex's native catalog
are prepared in the container's writable layer before startup; changing budgets
does not require rebuilding.
Rebuild worker images after upgrading Agensh; launchers reject older configuration
profiles so stale images cannot silently keep the previous behavior.
Copilot uses its native provider, large-output and background-compaction controls.
The shared model proxy applies an optional generated-output token cap to Responses
generation and Messages requests while preserving smaller per-request caps.
Setting `compact_fraction` to `null` leaves
each harness's native compaction settings in place.
Claude receives `compact_fraction * 100` as its native compaction percentage.
Its actual threshold follows the selected release's native headroom and model
metadata; the adapter does not compensate using version-specific internal buffer
constants. See [the reproduction guide](../REPRODUCE.md) for this difference.

Pi runs offline with the Responses API and direct MCP tool exposure. The same
MCP notice wrappers and tool exclusions apply to all harnesses. Pi's MCP
timeouts are converted from milliseconds to seconds. Sessions remain native
JSONL files under `~/.pi/agent/sessions`; ACP prompt completion waits for Pi's
`agent_settled` event, including native retries and compaction recovery.

Codex uses its native model catalog, including Code Mode and Responses Lite
when selected by the model. Its [app-server](https://learn.chatgpt.com/docs/app-server)
is configured for the local Responses proxy with external tool access limited
by the container. MCP timeouts are converted to seconds and excluded tools
become `disabled_tools`. The adapter waits for `turn/completed`, preserves
failure/interruption status and restores saved threads with `thread/resume`.
Native multi-agent tools, web search, app connectors and automatic updates
are disabled for the experiment.

The shared tool policy applies one MCP allowlist
across all harnesses. The shared wrapper hides and blocks unreviewed tools.
Codex persisted goals are disabled so the launcher/router own continuation;
the experiment proxy removes unsupported human-question tool declarations.
Copilot excludes cloud-session history and background-agent reads.
Skills are enabled in all four harnesses. Copilot exposes its native `skill`
tool; Pi and Codex discover skill instructions and load them with their file tools.
Claude exposes `Skill` and retains native base-agent definitions for forked skills;
its general `Agent` tool remains excluded.
Pi also passes workspace `.pi/skills` and ancestor `.agents/skills` directories
explicitly, so unattended project trust does not suppress those skills.

## MCP configuration

Standalone baselines do not configure the team MCP servers.

| File | Purpose |
|---|---|
| `config/mcp.json.tmpl` | Stdio Gitea, Mattermost and board servers, rendered to `/work/.mcp.json` |
| `config/mcp_allowed_tools.json` | Model-visible allowlist enforced by the notice wrapper |
| `config/mcp_deny_tools.json` | Native client exclusions for Copilot, Pi and Codex |
| `config/mcp_tool_metadata.json` | Reviewed description overrides for retained tools |

The entrypoint substitutes credentials, converts MCP timeouts to numbers and
omits the board server when `BOARD_SERVICE_URL` is unset. Server commands use
the private `${AGENT_NODE}` runtime. Copilot applies permission denials and
model-visible exclusions; Pi marks excluded tools `hidden` and retained tools
`direct`; Codex uses each MCP server's `disabled_tools` list. The wrapper also
filters advertised tools and rejects disabled calls before forwarding them for
all four harnesses, including Claude Code.
The policy keeps 13 Gitea, 12 Mattermost and 4 board tools. Description overrides
leave parameter schemas and results intact; stale override paths fail explicitly.
Codex's model catalog is generated in `/opt/omcgitea/codex/models.json` at build
time and is not checked into the repository.

## Shutdown and validation

The bridge serializes connections and lets active prompts cancel before
stopping child processes. Shutdown writes a private
`shutdown/<boot-id>/state.tar.gz` containing HOME and the complete workspace,
including Git and ignored files. A manifest becomes complete only after the
archive is sealed and its size/checksum recorded. The launcher checks these
manifests before automatic cleanup.

The team uses `/var/run/acp/agent.sock`; the standalone Compose entrypoint
uses `/opt/data/acp.sock` and mounts its workspace at both `/workspace` and `/work`.

Build `Dockerfile` from the repository root, or use
[`scripts/pbench_build_pertask_images.sh`](../scripts/pbench_build_pertask_images.sh).
For direct builds, pass `--build-arg AGENT_HARNESS=copilot`, `pi`, `codex` or `claude` alongside
`TASK_IMAGE`. Team image names include the selected harness to avoid tag collisions.
The [generated Compose stack](../tools/README.md) also mounts prompts, config,
the bridge, archive helper and MCP adapters from the checkout.

Check an installed worker image without model credentials or network access:

```bash
docker run --rm --network none --entrypoint python3 IMAGE /opt/omcgitea/check_harness.py
```
