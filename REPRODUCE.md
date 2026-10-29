# Reproducing Agensh experiments

This guide covers the released single-node team and standalone single-agent
baseline. Both use ProgramBench's v6 cleanroom and support Copilot (the default),
Pi, Codex and Claude Code, with selectable CLI versions. Copilot is the harness
used for our 1.0 experiments. Copilot exposes ACP directly; adapters connect
Pi's RPC, Codex's app-server and Claude Code's stream-json interface to ACP.
A **team** is a group of collaborating **agents**; **worker** refers to an
individual agent's runtime. A **peer** is another agent in the same team.
Run commands from the repository root, and record the release revision,
evaluator revision, image digests and configuration for each experiment.

Team launch defaults are 8 workers, 6 hours per task, `gpt-5.6-sol`, high reasoning
effort and a 272,000-token prompt window. Copilot, Pi and Codex use the Responses
API; Claude Code uses the Anthropic Messages API. The launch scripts check the
recorded model settings before starting.

The shared harness configuration defaults to the measured Copilot experiment
settings. Reasoning effort, context/output budgets and compaction are configurable
at startup. Changes to model, reasoning effort and budgets do not require a new
build. Changing the harness or CLI version still requires its matching worker
image, and runtime source changes require rebuilt images.
Skills remain enabled in every harness.

## Repository layout

| Component | Guide |
|---|---|
| Worker images, harnesses and shutdown archives | [agent/](agent/README.md) |
| Shared context and work claims | [board-service/](board-service/README.md) |
| Event routing and messaging | [mini-router/](mini-router/README.md) |
| Bootstrap-issued worker tokens | [secret-service/](secret-service/README.md) |
| Compose, provisioning and host guards | [docker/](docker/README.md) |
| Runtime instructions and launch messages | [prompts/](prompts/README.md) |
| Launch and lifecycle scripts | [scripts/](scripts/README.md) |
| Compose generation, submission export and scoring | [tools/](tools/README.md) |

## Prerequisites

Use Linux with Docker Engine, Compose v2, systemd and cgroup v2. Host tools
include Bash, Make, Python 3.11+, Git, curl, jq, `envsubst`, `flock` and `uv`.
The scripts require passwordless `sudo` for Docker and container-owned data.

Install the [memory slice](docker/pbench.slice) and
[reboot-guard unit](docker/pbench_reboot_guard.service) once, replacing the
unit's `/opt/agensh` path with this checkout:

```bash
sudo cp docker/pbench.slice /etc/systemd/system/
sed "s|/opt/agensh|$PWD|g" docker/pbench_reboot_guard.service \
  | sudo tee /etc/systemd/system/pbench-reboot-guard.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable pbench-reboot-guard.service
```

On a shared host, reuse working guards and their existing checkout path.
Do not restart Docker, move shared image tags or stop other experiments.
The [guard script](scripts/pbench_reboot_guard.sh) stops all running
`omcgitea-*` Compose projects after reboot, retaining their data; it does not
check driver liveness. Its `PBENCH_GUARD_DRY_RUN=1` mode previews that scope.
Preflight requires a configured slice and enabled guard.

Install ProgramBench separately. Release validation used v1.2.5 at this commit:

```bash
git clone https://github.com/facebookresearch/ProgramBench.git /path/to/programbench
git -C /path/to/programbench checkout 27f02157c785f8da3647aa6dbbe6b9137f99f10e
uv sync --project /path/to/programbench --frozen
export PROGRAMBENCH_REPO=/path/to/programbench
```

Follow the [upstream inference guide](https://github.com/facebookresearch/ProgramBench/blob/main/docs/README.md#inference)
for evaluator prerequisites. Download each selected task's blobs with
`uv run --project "$PROGRAMBENCH_REPO" programbench blob sync TASK_ID` before
inference to catch access and disk-space failures early.

## Configure the experiment

Choose one or more supported task IDs from `TASK_TABLE` in
[the profile generator](scripts/pbench_gen_env.sh). Set `TASKS` explicitly:
the generator, image builder and launcher have different built-in task lists.

Shared settings live in [`agent/config/harness.json`](agent/config/harness.json):

```json
{
  "harness": "copilot",
  "version": "1.0.70",
  "model": "gpt-5.6-sol",
  "reasoning_effort": "high",
  "prompt_tokens": 272000,
  "output_tokens": null,
  "tool_output_bytes": 1048576,
  "compact_fraction": 0.8
}
```

| Setting | Meaning |
|---|---|
| `harness`, `version` | The selected harness and an exact release or `latest`, resolved before use |
| `model` | Model identifier for the configured gateway |
| `reasoning_effort` | `none`, `minimal`, `low`, `medium`, `high`, `xhigh` or `max`, subject to harness and model support |
| `prompt_tokens` | Declared prompt/context budget; each harness retains its native headroom handling |
| `output_tokens` | Maximum generated response tokens, enforced by the shared model proxy; `null` leaves the native/provider default |
| `tool_output_bytes` | Tool-result text/preview budget in UTF-8 bytes; native tools can impose smaller limits |
| `compact_fraction` | Compaction fraction, with Claude's native-percentage semantics described below; `null` keeps native defaults |

Copilot, Pi and Codex target this fraction of `prompt_tokens`. Claude Code receives
the fraction directly as its native percentage: `0.7` sets
`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=70`, with `CLAUDE_CODE_AUTO_COMPACT_WINDOW` set to
`prompt_tokens`. Claude's actual threshold also depends on the selected release's
native headroom and model metadata, so it can differ from 70% of the declared
prompt budget. Agensh does not normalize that threshold using internal constants
such as the 20,000-token reserve cap and 13,000-token safety margin observed in
Claude Code 2.1.312; those values can change between past and future releases.

Codex's proxy enforces the tool-result text byte budget explicitly because its
native history truncation is approximate. Pi's native truncation notice is added
after its payload byte limit.

Edit that file, or select a JSON override file using
`--harness-config /absolute/path/to/harness.json`. Override files may specify
only the fields that differ from the defaults. Set `HARNESS_CONFIG` to reuse
the same file across preparation and launch:

```bash
export HARNESS_CONFIG="$PWD/agent/config/harness.json"
```

The environment variables `REASONING_EFFORT`, `PROMPT_TOKENS`, `OUTPUT_TOKENS`,
`TOOL_OUTPUT_BYTES` and `COMPACT_FRACTION` override the file. An empty
`OUTPUT_TOKENS` or `COMPACT_FRACTION` selects its native/default behavior.
Generated profiles record the effective settings; preflight checks them before
starting any model probes. The harness/version arguments below override the
selected file and environment values.

Choose the underlying single-agent harness with the `--agent-harness` argument.
Use the same argument when generating profiles, building worker images and
launching the team:

| Harness | Argument | Default version |
|---|---|---|
| Copilot (default) | `--agent-harness copilot` | 1.0.70 |
| Pi | `--agent-harness pi` | 1.4.0 |
| Codex | `--agent-harness codex` | 0.164.0 |
| Claude Code | `--agent-harness claude` | Latest release, resolved to an exact version |

The examples below set a shell variable so the chosen argument stays consistent:

```bash
AGENT_HARNESS=copilot        # Or pi, codex or claude
HARNESS_VERSION=1.0.70       # Set to the exact release you want to use
# Optional model override: export LLM_MODEL=gpt-6.1-sol
```

Pass `--harness-version "$HARNESS_VERSION"` alongside the harness argument to
select an exact release. Copilot 1.0.70 is the default used in our experiments;
Pi and Codex default to 1.4.0 and 0.164.0 when selected. The version argument
overrides `HARNESS_VERSION` and the selected harness's `COPILOT_CLI_VERSION`,
`PI_CLI_VERSION`, `CODEX_CLI_VERSION` or `CLAUDE_CLI_VERSION` environment variable.
Versions must be exact releases or `latest`. `latest` is resolved from the official npm registry
and recorded as an exact version before building or launching. Claude Code
defaults to `latest`; the other harness defaults retain the experiment releases.
Resolve `latest` once and reuse the exact version across preparation and launch;
the Claude Code sequence below shows how.

For the team scripts, harness selection uses `--agent-harness` first, then exported
`AGENT_HARNESS`, then the shared configuration, with Copilot as the shipped
default. Profiles record the selected version, and launch checks it against
the installed CLI. Images are named
`omcgitea-agent-<task-slug>-<agent-harness>:<tag>` and contain only the selected
harness. Preflight rejects missing, mismatched or combined harness installations.
Existing worker images must be rebuilt for this image layout.

Single-task example:

```bash
export TASKS='jgm__pandoc.5caad90'
export WORKERS=8 HOURS=6
export RUN_ID="$(date -u +%Y%m%dt%H%M%Sz)"
export PBENCH_EVAL_PYTEST_ADDOPTS='--rootdir=.'
```

The pytest option is appropriate for this example's branch-relative test
identities; review [evaluation options](#score) when selecting other tasks.

Example of a five-task team run:

```bash
export TASKS="\
jgm__pandoc.5caad90 \
gromacs__gromacs.665ea4c \
universal-ctags__ctags.243595e \
php__php-src.c891263 \
ffmpeg__ffmpeg.360a402"
```

Keep the same `TASKS`, `WORKERS` and `HOURS` for preparation and launch. Tasks
run in the listed order with a separate `HOURS` budget each. Evaluator options
apply to the whole sequence; use separate invocations when options differ.
For standalone baselines, prepare one configuration and fresh run ID per task.

Keep gateway credentials in `~/.pbench-upstream.env`, mode 600:

```dotenv
LLM_UPSTREAM=https://your-gateway.example
LLM_UPSTREAM_TOKEN=replace-with-your-bearer-token
```

`LLM_UPSTREAM` is the base URL without `/v1/responses`. Exported values override
this file. The egress proxy injects the real credential; workers receive only a
local proxy credential. Generated profiles contain secrets and must stay private.

Generate profiles with [pbench_gen_env.sh](scripts/pbench_gen_env.sh):

```bash
bash scripts/pbench_gen_env.sh --harness-config "$HARNESS_CONFIG" \
  --agent-harness "$AGENT_HARNESS" --harness-version "$HARNESS_VERSION"
```

The script derives task slugs, image names, ports and subnets, preserves local
passwords and writes mode-600 `.env.pbench-single-node-<task-slug>` files.
`PROFILE_SUFFIX` adds an optional suffix; each profile gets a separate data
root. For commands using `PROFILE`, set it to the `PROFILE` value in the
selected generated file. Regeneration rewrites generated settings and drops
manually added tuning keys; reapply intentional profile edits afterward.

### Model API routes

The model proxy appends the native client's request path to `LLM_UPSTREAM`.
With the shipped provider-base settings, the main generation paths are:

| Harness/mode | Request path |
|---|---|
| Copilot team | `/responses` |
| Copilot standalone, Pi and Codex | `/v1/responses` |
| Claude Code | `/v1/messages` |

Team preflight probes `/v1/responses` or `/v1/messages`, according to the selected
API family. For a Responses gateway exposing only `/v1/responses`, set
`ANTHROPIC_BASE_URL=http://egress-proxy:4180/v1` in each Copilot team profile
after generation. This aligns its native request path with the standard route.
Native paths can vary with the CLI release and provider-base settings.

### Host-loopback model APIs

A container cannot reach a host's loopback-only listener through its own
`127.0.0.1`. Use [strip_metadata_proxy.py](scripts/strip_metadata_proxy.py) as a
relay reachable from Docker. For example, in a persistent terminal or service:

```bash
UPSTREAM=http://127.0.0.1:8000 LISTEN_HOST=172.17.0.1 LISTEN_PORT=8000 \
UPSTREAM_RETRY_ATTEMPTS=1 python3 scripts/strip_metadata_proxy.py
```

Replace these example addresses with the API listener, Docker host gateway
(`ip -4 addr show docker0`) and an available relay port. Set `LLM_UPSTREAM` in
the launch environment to the relay's base URL. Leave `UPSTREAM_AUTH_TOKEN`
unset on this relay to preserve the incoming credential; the experiment's
own egress proxy supplies it. Keep the relay running through inference, and
verify the real model route from an egress container. A `/healthz` response
only verifies the relay listener.

## Build images

Reference extraction, worker builds and evaluation all use
`task_cleanroom_v6`. Replace `__` with `_1776_` in the task ID to get its
official image, `programbench/<mapped-task-id>:task_cleanroom_v6`.
Pull the images for the selected tasks before building workers.

Build the shared images from their checked-in Dockerfiles. The table supplies
the Dockerfile, output tag and build context for
`sudo docker build -f DOCKERFILE -t IMAGE CONTEXT`:

| Dockerfile | Default image | Context |
|---|---|---|
| [agent/Dockerfile.base](agent/Dockerfile.base) | `omcgitea-agent-base:pbench` | `agent/` |
| [mini-router/Dockerfile](mini-router/Dockerfile) | `omcgitea-mini-router:local` | `mini-router/` |
| [board-service/Dockerfile](board-service/Dockerfile) | `omcgitea-board:local` | `board-service/` |
| [secret-service/Dockerfile](secret-service/Dockerfile) | `omcgitea-secret-service:local` | `secret-service/` |
| [docker/bootstrap/Dockerfile](docker/bootstrap/Dockerfile) | `omcgitea-bootstrap:local` | `docker/bootstrap/` |

Then use [pbench_build_pertask_images.sh](scripts/pbench_build_pertask_images.sh)
for the selected workers:

```bash
JOBS=1 bash scripts/pbench_build_pertask_images.sh --harness-config "$HARNESS_CONFIG" \
  --agent-harness "$AGENT_HARNESS" --harness-version "$HARNESS_VERSION"
```

It builds `omcgitea-agent-<task-slug>-<agent-harness>:pbench`, records installed-tool checks and
writes per-task logs plus `out/pertask-build/summary.txt`. Require
`board=True harness=<selected-harness>` in each successful result, where the
harness is `copilot`, `pi`, `codex` or `claude`. The helper also verifies the
selected CLI version and absence of other harnesses.
`JOBS` limits build concurrency; use one build at a time on a shared host.
The helper builds worker images only and requires the base artifact above.
Compose builds bootstrap and secret-service during startup, but not the router
or board. Other third-party service images are pulled by Compose.

### Fresh builds and private image tags

For an uncached experiment, build each project image with `--no-cache` under
new tags. Record upstream image digests; on a shared host, pull a resolved
digest rather than moving shared tags. The artifact base contains the upstream
Gitea MCP binary; its first build needs access to `docker.gitea.com`.

The worker helper supports `TAG` for its output, but uses the fixed
`omcgitea-agent-base:pbench` artifact and Docker's build cache. To use a private
base or an uncached worker build, invoke [agent/Dockerfile](agent/Dockerfile)
directly. Set `AGENT_BASE_IMAGE` and `AGENT_IMAGE` to private output names and
`CLEANROOM_IMAGE` to the selected task's official v6 image:

```bash
sudo docker build --no-cache -f agent/Dockerfile.base -t "$AGENT_BASE_IMAGE" agent/
sudo docker build --no-cache -f agent/Dockerfile \
  --build-arg TASK_IMAGE="$CLEANROOM_IMAGE" \
  --build-arg AGENT_HARNESS="$AGENT_HARNESS" \
  --build-arg "${AGENT_HARNESS^^}_CLI_VERSION=$HARNESS_VERSION" \
  --build-arg AGENT_BASE_IMAGE="$AGENT_BASE_IMAGE" -t "$AGENT_IMAGE" .
```

Repeat the worker build for each selected task. Build the shared services
from the table with private tags and `--no-cache` as well. If Docker's default
build bridge is unavailable, `RUN` steps may need `--network host`.

The [profile generator](scripts/pbench_gen_env.sh) accepts these image overrides
when exported before generation:

| Setting | Value |
|---|---|
| `AGENT_IMAGE_TAG` | Tag used for every `omcgitea-agent-<task-slug>-<agent-harness>` image |
| `MINI_ROUTER_IMAGE` | Complete router image name |
| `BOARD_IMAGE` | Complete board image name |
| `BOOTSTRAP_IMAGE` | Complete bootstrap image name |
| `SECRET_SERVICE_IMAGE` | Complete token-service image name |

Build outputs and generated profile values must agree. `TAG` controls the
worker builder; `AGENT_IMAGE_TAG` controls profile generation. Preflight checks
the baked worker entrypoint and rejects stale router/board images. See the
[agent guide](agent/README.md) for runtime defaults and mounts.

## Launch

Use [launch_single_node.sh](scripts/launch_single_node.sh) for preflight and
team launch, with the configured environment still exported:

```bash
PREFLIGHT_ONLY=1 bash scripts/launch_single_node.sh --harness-config "$HARNESS_CONFIG" \
  --agent-harness "$AGENT_HARNESS" --harness-version "$HARNESS_VERSION"
mkdir -p out
setsid nohup bash scripts/launch_single_node.sh --harness-config "$HARNESS_CONFIG" \
  --agent-harness "$AGENT_HARNESS" --harness-version "$HARNESS_VERSION" \
  > out/single-node.launch.log 2>&1 < /dev/null &
```

Preflight checks all selected profiles, images, empty state, subnet capacity,
prompt mounts and rendered worker counts. It makes a small live model request
and starts temporary image-check containers. Launch only after it passes.

The launcher uses [lib_launch.sh](scripts/lib_launch.sh) and
[pbench_chain.sh](scripts/pbench_chain.sh) to sequence tasks and overlap
completed-task evaluation with the next task. [pbench_run.sh](scripts/pbench_run.sh)
handles service startup, task seeding, kickoff messages, reminders, idle nudges,
submission export and shutdown.

| Artifact | Location |
|---|---|
| Driver log | `out/single-node.driver.log` |
| Per-task chain logs | `out/chain-<profile>.{log,summary}` |
| Rollout log | `out/pbench-<task-id>-single-node.<RUN_ID>.log` |
| Trajectory | `${TRAJ_ROOT:-~/pbench-trajectories}/<task-id>.single-node.<RUN_ID>/` |

### Run with Pi, Codex or Claude Code

After completing the prerequisites, model credentials, shared-image builds and
task settings above, run one of these sequences in a persistent terminal.
Pi, with 1.4.0 shown as the default release:

```bash
HARNESS_VERSION=1.4.0
bash scripts/pbench_gen_env.sh --agent-harness pi --harness-version "$HARNESS_VERSION"
JOBS=1 bash scripts/pbench_build_pertask_images.sh --agent-harness pi --harness-version "$HARNESS_VERSION"
PREFLIGHT_ONLY=1 bash scripts/launch_single_node.sh --agent-harness pi --harness-version "$HARNESS_VERSION"
bash scripts/launch_single_node.sh --agent-harness pi --harness-version "$HARNESS_VERSION"
```

Codex, with 0.164.0 shown as the default release:

```bash
HARNESS_VERSION=0.164.0
bash scripts/pbench_gen_env.sh --agent-harness codex --harness-version "$HARNESS_VERSION"
JOBS=1 bash scripts/pbench_build_pertask_images.sh --agent-harness codex --harness-version "$HARNESS_VERSION"
PREFLIGHT_ONLY=1 bash scripts/launch_single_node.sh --agent-harness codex --harness-version "$HARNESS_VERSION"
bash scripts/launch_single_node.sh --agent-harness codex --harness-version "$HARNESS_VERSION"
```

Claude Code defaults to `latest`. Resolve it once, then use that exact version
for profile generation, image building and launch:

```bash
HARNESS_VERSION=$(python3 agent/harness_config.py --agent-harness claude --harness-version latest \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')
bash scripts/pbench_gen_env.sh --agent-harness claude --harness-version "$HARNESS_VERSION"
JOBS=1 bash scripts/pbench_build_pertask_images.sh --agent-harness claude --harness-version "$HARNESS_VERSION"
PREFLIGHT_ONLY=1 bash scripts/launch_single_node.sh --agent-harness claude --harness-version "$HARNESS_VERSION"
bash scripts/launch_single_node.sh --agent-harness claude --harness-version "$HARNESS_VERSION"
```

Change `HARNESS_VERSION` to the release you want. Each sequence builds and
launches only its selected harness. The launcher checks that both arguments
match every generated task profile and worker image. Other releases must retain
the native ACP/RPC interfaces, model-catalog support and Pi tool modules used by
the adapters; compatibility checks report changed layouts instead of rejecting
a release solely because its version differs from the defaults.
Use fresh profiles and state for each experiment as described below.

### Concurrent runs

Use a separate checkout fixed at a recorded commit for each run. Choose a
unique `RUN_ID` for archives and export `PROFILE_SUFFIX`, `PORT_BASE` and
`SUBNET_OCTET` before profile generation to isolate Compose state. For example:

| Workers | `PROFILE_SUFFIX` example | `PORT_BASE` | `SUBNET_OCTET` |
|---|---|---|---|
| 8 | `cohort-w8` | 24400 | 249 |
| 32 | `cohort-w32` | 24800 | 250 |

Check host routes, ports and generated profiles before using these example
ranges. Actual offsets and subnet sizes depend on the task and worker count.
Suffixes use lowercase letters, digits and hyphens, beginning with a letter or
digit. `RUN_ID` alone does not isolate Compose. Keep outputs and data empty,
use private image tags, and retain `PROFILE_SUFFIX` for preflight and launch.
Rendered Compose output contains credentials; keep it private with mode 600.

Delayed launches use host-managed systemd services/timers with the absolute
checkout path, explicit environment and `Restart=no`. Allow for archive and
evaluation overhead, and arrange startup after Docker and the reboot guard.
Record scheduled and actual start times and verify native agent activity.

For larger teams, set `MM_MAX_USERS_PER_TEAM` above the worker count plus
administrators; its default is 200. Review `MYSQL_MAX_CONNECTIONS` (default
1,000), since each router can use four connections. These settings do not
scale automatically with `WORKERS`; reapply them after profile regeneration.

## Standalone single-agent baseline

[launch_single_agent.py](scripts/launch_single_agent.py) runs the standalone
baseline from JSON. It handles cleanroom seeding, private prompts, isolation
checks, snapshots,
[ACP continuation](scripts/acp_driver.py), export and optional evaluation.
Use [the standalone prompt guide](prompts/README.md#standalone-baseline) for its timing
and prompt behavior.

Create a private model environment file, mode 600, with the selected gateway
or relay and credential:

```dotenv
UPSTREAM=https://your-gateway.example
UPSTREAM_AUTH_STYLE=bearer
UPSTREAM_AUTH_TOKEN=replace-with-your-bearer-token
```

Create `baseline.json`, also private, using this configuration template.
Replace angle-bracket fields and absolute paths. Match `hours` and
`deadline_seconds`, and choose unused Docker subnets:

```json
{
  "task": "<task-id>",
  "hours": 6,
  "deadline_seconds": 21600,
  "project": "omcgitea-pbench-single-agent-<run-id>",
  "agent_image": "omcgitea-agent-<task-slug>-copilot:<image-tag>",
  "cleanroom_image": "programbench/<mapped-task-id>:task_cleanroom_v6",
  "run_dir": "/absolute/path/to/new-run-directory",
  "model_env_file": "/absolute/path/to/model.env",
  "programbench_repo": "/absolute/path/to/pinned-programbench",
  "subnet_default": "10.177.242.0/24",
  "subnet_egress": "10.177.243.0/24"
}
```

Use a lowercase alphanumeric/hyphen run ID, a new run directory and the worker
image built for that task. Optional fields are `snapshot_seconds` (default
1200), `skip_eval` (default false) and `pytest_addopts` (see [Score](#score)).
Pass the chosen `--agent-harness` argument to the launcher and choose the matching
`agent_image` in JSON:

| Argument | `agent_image` |
|---|---|
| `--agent-harness copilot` | `omcgitea-agent-<task-slug>-copilot:<image-tag>` |
| `--agent-harness pi` | `omcgitea-agent-<task-slug>-pi:<image-tag>` |
| `--agent-harness codex` | `omcgitea-agent-<task-slug>-codex:<image-tag>` |
| `--agent-harness claude` | `omcgitea-agent-<task-slug>-claude:<image-tag>` |

The harness argument takes precedence over an optional `agent_harness` JSON field.
Use `--harness-version VERSION` to select the installed release; it overrides an
optional `harness_version` JSON field. When those fields and arguments are absent,
the shared file and environment determine the harness/version; the shipped
defaults are Copilot 1.0.70.
The same `--harness-config` option supplies the model, reasoning and budget
settings. Explicit values in the run JSON override the shared settings; these
fields are optional when the shared file already supplies them.
The launcher rejects image kind/version mismatches and
records the selected CLI and Node versions in `runtime.json`. Pi's native session files live under
`~/.pi/agent/sessions`; Copilot retains `~/.copilot/session-state`; Codex stores
native thread rollouts under `~/.codex/sessions`; Claude Code stores its sessions
under `~/.claude/projects`.
The effective configuration selects the model and reasoning effort. It starts only the worker
and proxy, publishes no host ports and reads credentials from `model_env_file`.

Run the entrypoint in a persistent terminal or a systemd service
with `Restart=no`; for a service, use the caller's UID/GID, this checkout as
working directory, `pbench.slice` and at least 12 minutes of stop grace:

```bash
python3 scripts/launch_single_agent.py --harness-config "$HARNESS_CONFIG" \
  --agent-harness copilot --harness-version 1.0.70 \
  --config /absolute/path/to/baseline.json
```

For Pi, Codex or Claude Code baselines, build the corresponding task image with
`pbench_build_pertask_images.sh --agent-harness pi`, `--agent-harness codex` or
`--agent-harness claude`, adding
`--harness-version VERSION` for your chosen release. Update `agent_image` in the
configuration, and use the same harness and version arguments on
`launch_single_agent.py`.

The launcher refuses reused state, records provenance in `run_dir/provenance.json`
and lifecycle in `status.json`, and writes native activity to `cc.log`.
Submission and evaluation are under `run_dir/out/<task-id>/`. Preserve the
recorded revision, image IDs and reference hash with these outputs.

## Score

Before accepting a result, check `RUN_FAILED`, `EXPORT_FAILED`, shutdown
archives, `error_code` and `test_branch_errors`. ProgramBench can exit zero
with incomplete branches, and the chain may evaluate after an inference or
export failure.

For pytest-based branches, submitted project configuration can change JUnit
test identities. The [Docker shim](scripts/pbench_docker_sudo.sh) can append
`PBENCH_EVAL_PYTEST_ADDOPTS='--rootdir=.'` when identities should be relative to
the branch working directory. For standalone runs, put the same value in
`pytest_addopts`; exported team options are not copied into the JSON config.
Choose options for the selected evaluator and inspect test-identity warnings.

The chain's `SCORE` line counts raw attempts. Use
[pbench_score_report.py](tools/pbench_score_report.py) for the canonical-kept
score computed by ProgramBench's own helpers. Set `TASK_ID` to the full task ID
and `RUN_DIR` to a directory containing `<task-id>/<task-id>.eval.json`:

```bash
uv run --project "$PROGRAMBENCH_REPO" \
  python tools/pbench_score_report.py "$RUN_DIR" "$TASK_ID"
```

For standalone runs, `RUN_DIR` is `run_dir/out`. Team archives store the JSON
at `<trajectory>/out/<task-id>.eval.json`; copy it into the expected nested
layout for reporting. Record the evaluator revision with the score.

Preserve the original JSON after evaluation failures. Resolve the external
error and rerun evaluation on the unchanged submission. ProgramBench v1.2.5
retries incomplete branches without `--force`; completed branches are retained.
Inference does not need to be repeated. Evaluation and archiving are implemented
in [pbench_chain.sh](scripts/pbench_chain.sh).

## Stop and recover

For team lifecycle operations, set `PROFILE` to the selected generated profile
and use the [Makefile](Makefile):

```bash
make down PROFILE="$PROFILE"   # Stop and preserve data.
make clean PROFILE="$PROFILE"  # Stop and delete this profile's data.
```

Stop a standalone service through its own systemd unit, or signal its launcher
when using a terminal. The launcher verifies shutdown before export and retains
state on failure.

[archive.py](agent/archive.py) seals and verifies HOME/workspace archives at
`agents/<worker>/shutdown/<boot-id>/state.tar.gz`, including Git and ignored
files. [pbench_chain.sh](scripts/pbench_chain.sh) copies trajectories, verifies
both copies and refuses cleanup after incomplete archives or failed copies.
Inspect those artifacts before destructive cleanup.

After `EXPORT_FAILED`, the repository remains in profile data or its archived
trajectory. Recover committed source with [pbench_submission.py](tools/pbench_submission.py)
before scoring. Existing output or profile data must be preserved before a
fresh launch; the runner rejects leftover state.

## Experimental conditions and release differences

The team budget includes staggered startup. The default ramp targets 30 seconds
per worker for the first 120 workers, then 3 seconds, with a serial 20-second
settle wait. Actual startup can exceed those targets; later workers get less
time. The ramp can overrun the budget and is followed by a minimum 60-second
wait. See [pbench_run.sh](scripts/pbench_run.sh) for
`PBENCH_WAKE_STAGGER_S`, `PBENCH_WAKE_FAST_STAGGER_S`,
`PBENCH_WAKE_RAMP_SUBJ_S` and `PBENCH_BRINGUP_SETTLE_S`. Deadline reminders start
after the ramp and can be skipped when their target time has passed.

The team idle watchdog checks every 60 seconds and nudges after 600 seconds of
inactivity when queue checks permit, with at least 600 seconds between nudges.
It uses the delivery prompt during the last 45 minutes of runs longer than
45 minutes, or the last five minutes of runs at most 45 minutes long. The standalone
[ACP driver](scripts/acp_driver.py) resumes immediately after a completed turn
and recovers silent requests after 600
seconds. The team ACP silence watchdog defaults to 20 minutes
(`MINI_ROUTER_STUCK_MS=1200000`).

The team exports committed Git HEAD before stopping routers, CI and workers;
workers then get up to 600 seconds to seal archives. Export duration can affect
the cutoff, but shutdown work does not enter that submitted HEAD. The standalone
launcher snapshots by staging and committing non-ignored changes, stops and
archives the worker, then commits remaining changes before export. Its final
submission can include work made during cancellation. Record these differences
and active prompt intervals when comparing team sizes or the standalone
baseline.

Agents share the same peer role. Bootstrap allows PR merges with zero required
approvals while restricting direct pushes to main; the CI merge gate is disabled.
See the [board guide](board-service/README.md) for shared-context behavior,
[router guide](mini-router/README.md) for messaging and notices, and
[worker configuration](agent/README.md#mcp-configuration) for tool exclusions.

The default harness releases are Copilot 1.0.70, Pi 1.4.0, Codex 0.164.0 and
Claude Code's latest release; `--harness-version` selects another compatible
release. Mattermost MCP defaults
to 0.5.1. By default, all four harnesses use a shared 1 MiB tool-output budget through
their native controls and model proxy, and shutdown archives are verified before cleanup.
Claude Code uses its native executable and stream-json sessions through an ACP
adapter. The shared proxy forwards its native Anthropic Messages requests to
the same configured gateway and records model, effort, and response limits.
The gateway must support `/v1/messages` for this harness. Native context/output
controls and the native compaction percentage are applied at startup. Coding tools,
inline skills and forked skills remain available; native base-agent definitions
support skill forks while general peer-agent, hosted web and human-input tools stay
excluded. Each worker image contains only the selected harness. The release uses the
recommended v6 cleanroom for reference extraction, workers and evaluation.
The historical main experiment seeded the older `task_cleanroom` reference;
its binary differs from v6 even when version strings match. These infrastructure
updates mean a new release run should record its own revision rather than claim
exact historical reproduction.

Workers run as UID/GID 10000 and can execute the root-owned, mode-0111 reference
at `/opt/pbench/executable` without reading its bytes. Worker networks restrict
external access to model egress. Workers have a 64 GiB limit and routers 8 GiB;
these are ceilings, not reservations. Team containers use the 80%-of-host-RAM
`pbench.slice`; the evaluation Docker shim separately caps memory per container.
Record host resources, competing load, gateway capacity, image digests and
rendered settings when comparing results. Keep prompts fixed; changes to
continuation or idle policy create a different experimental condition.

## Security and support

Report security vulnerabilities privately as described in
[SECURITY.md](SECURITY.md).
Use [GitHub Issues](https://github.com/microsoft/Agensh/issues) for bugs,
configuration questions and feature requests. Include the commit, launch path,
steps to reproduce and relevant logs with credentials removed. Support is
limited to these resources. This project is licensed under the [MIT License](LICENSE).

The token service reads bootstrap-issued tokens from its read-only mount. It
validates complete agent identifiers and checks that token paths resolve within
`SECRET_SERVICE_TOKENS_DIR`. Rejected HTTP requests close their connection;
startup logs omit the token storage path.

The board's `POST /board/{board_id}/lifecycle` export keeps the existing
`{board_id}.jsonl` filename under `BOARD_LIFECYCLE_DIR` (default
`/data/lifecycle`). Traversal and symlinks that resolve outside that directory
return HTTP 400 before creating directories or writing files. Board membership
and the operator exception still apply.

## Contributing

Repository-owned filenames use underscores between words. Keep conventional
tool-required names such as `Dockerfile` and `package-lock.json`. Component
directories retain their existing names. Harness-specific worker code lives in
`agent/copilot`, `agent/pi`, `agent/codex` and `agent/claude`; common runtime code
remains in `agent`.

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit [Contributor License Agreements](https://cla.opensource.microsoft.com).

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
