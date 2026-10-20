# Agensh — single-node ProgramBench agent fleet

This release includes selected infrastructure updates after the main experiment:
1 MiB inline Copilot tool output, native delegation/tool exclusions, file-backed
group-message backlogs and verified graceful shutdown archives. Reference
extraction now uses the recommended v6 cleanroom alongside worker builds and
evaluation. These updates are documented below; new runs should record the
release revision rather than claim exact historical reproduction.

This release contains the **single-node setup used for the main experiment**.
`scripts/launch_single_node.sh` runs a team of peer coding agents in Docker
Compose, one ProgramBench task at a time. Agents collaborate through Gitea,
Mattermost and a shared board; each has a mini-router sidecar and a native
Copilot ACP process. Kubernetes, simulation and standalone baseline launchers
are outside this release. The agent runtime is Copilot only; the router uses
the experiment's batch dispatcher. Alternate adapters and the separate
step-loop experiment are removed.

Peer workers coordinate through Gitea issues and PRs, Mattermost, and context-board
notes. The DeLM task-delegation queue and planner role are removed; the board's
`CLAIM` notes, mid-turn notices and normal event delivery remain supported.
The board uses the experiment's full renderer, with claims, patch replacement
and failure tracking always enabled. Turn-start delivery sends new gists;
`board_read` retrieves the full live board. Unfolding has two levels: the short
gist and its full stored detail. Search covers the complete persisted history.

The experiment defaults are 8 workers, 6 hours per task, `gpt-5.6-sol`, the
Responses API, high reasoning effort and a 272,000-token prompt window. The
launcher checks these profile settings before starting the run. Its default
five-task sequence is Pandoc, GROMACS, Universal Ctags, PHP and FFmpeg.

## Repository layout

Runtime code and image definitions live with their component:

```text
agent/                         Agent runtime, config, Dockerfile and Dockerfile.base
board-service/                 Shared context-board HTTP service
  mcp.cjs                      Board MCP adapter used by the agents
mini-router/                   Event routing and ACP delivery
  mcp-notice-shim.cjs           Mid-turn notice delivery through MCP tool results
secret-service/                Scoped token service
docker/                        Compose, bootstrap, edge proxy and host guards
prompts/                  Shared agent instructions and launch messages
scripts/                       Launch, build and analysis commands
tools/                         Compose generation and benchmark I/O
```

## Prerequisites

Run on a Linux host with Docker Engine, Docker Compose v2, systemd and cgroup
v2. Host tools include Bash, Make, Python 3, Git, curl, jq, `envsubst`
(`gettext-base`), `flock` and `uv`. The scripts use passwordless `sudo` for
Docker and profile data owned by container users. Install ProgramBench and its
Python dependencies in a separate checkout, by default `~/programbench`; set
`PROGRAMBENCH_REPO` to use another location. Evaluation needs its cleanroom
images and task data.

Each agent has a 64 GiB memory ceiling and each mini-router an 8 GiB ceiling;
these are limits, not reserved memory. The stack and host evaluation share the
`pbench.slice` aggregate ceiling (80% of host RAM, no swap). Available CPU,
physical memory, competing workloads and model latency affect throughput;
record them when comparing runs.

Install the host guards from the checkout root:

```bash
sudo cp docker/pbench.slice /etc/systemd/system/
sed "s|/opt/agensh|$PWD|g" docker/pbench-reboot-guard.service \
  | sudo tee /etc/systemd/system/pbench-reboot-guard.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable pbench-reboot-guard.service
systemctl show pbench.slice -p MemoryMax
systemctl is-enabled pbench-reboot-guard.service
```

The generated service contains this checkout's absolute path. Reinstall it if
the checkout moves. The reboot guard stops orphaned project stacks while
preserving their data. `PBENCH_SKIP_HOST_GUARDS=1` allows preflight on a host
without the guards, but removes those protections.

## Configure the experiment

Keep credentials in `~/.pbench-upstream.env`, with mode 600:

```dotenv
LLM_UPSTREAM=https://your-gateway.example
LLM_UPSTREAM_TOKEN=replace-with-your-bearer-token
REASONING_EFFORT=high
```

`LLM_UPSTREAM` is the gateway base URL, without `/v1/responses`. The egress
proxy injects the upstream credential; agents receive a local proxy credential.
The same variables supplied in the environment override this credentials file.
Never commit credentials or generated profiles.

Use the same task list and worker count for profile generation, image building
and launch. These are the main experiment defaults:

```bash
export TASKS="jgm__pandoc.5caad90 gromacs__gromacs.665ea4c universal-ctags__ctags.243595e php__php-src.c891263 ffmpeg__ffmpeg.360a402"
export WORKERS=8
export HOURS=6
bash scripts/pbench_gen_env.sh
```

For a Pandoc-only run, set `TASKS=jgm__pandoc.5caad90` before these steps.
`MODE=single-node` is optional; other modes are rejected. The profile generator
alone defaults to Pandoc, whereas the launcher defaults to all five tasks.

Each task gets `.env.pbench-single-node-<task>`, for example
`.env.pbench-single-node-pandoc`. Profiles are mode 600, contain secrets, and
retain their local passwords when regenerated. Each has its own ports, subnet
and data directory under `.claude-team-data/`. Do not mix profiles generated
with different worker counts in a concurrent run.

### Reference and evaluation images

Reference extraction and worker image builds use the `task_cleanroom_v6` images
recommended by [ProgramBench's official inference guide](https://github.com/facebookresearch/ProgramBench/blob/main/docs/README.md#inference):

| Purpose | Default tag |
|---|---|
| Seed documentation/assets and the executable agents query | `task_cleanroom_v6` |
| Per-task agent image base | `task_cleanroom_v6` |
| ProgramBench evaluation | `task_cleanroom_v6` (passed explicitly with `--image-tag`) |

Profiles explicitly carry `PBENCH_CLEANROOM_TAG=task_cleanroom_v6`; the launcher
and direct runner reject a conflicting tag. The runner extracts the reference
from its resolved image ID and records the image, ID, executable SHA-256 and
size in `out/<profile>/<task>/reference.json`. Record the evaluator revision
and image digests alongside results.

The historical main experiment seeded `task_cleanroom` while workers used v6.
Those tags contain different executable builds, including when their version
strings match. The current v6 reference changes that experimental condition;
do not describe new runs as exact reproductions of the historical reference.

The reference is mounted at `/opt/pbench/executable`, owned by root with mode
0111. Agent ACP children run as UID/GID 10000 so they can execute the reference
without reading it. Agent networks restrict external access to the LLM egress
proxy.

## Build images

A task id maps to its cleanroom image by replacing `__` with `_1776_`, for
example `programbench/jgm_1776_pandoc.5caad90:task_cleanroom_v6`. Pull the v6
image for each selected task before building. The runner pulls the seed image
on first use if necessary.

```bash
for task in $TASKS; do
  sudo docker pull "programbench/${task/__/_1776_}:task_cleanroom_v6"
done
sudo docker build -f agent/Dockerfile.base -t omcgitea-agent-base:pbench agent/
JOBS=2 bash scripts/pbench_build_pertask_images.sh
sudo docker build -t omcgitea-mini-router:local mini-router/
sudo docker build -t omcgitea-board:local board-service/
sudo docker build -t omcgitea-secret-service:local secret-service/
sudo docker build -t omcgitea-bootstrap:local docker/bootstrap/
```

The base is an artifact image containing only the unmodified upstream Gitea
MCP binary. A fresh build needs access to `docker.gitea.com`; a cached base
also works. Toolchains come from each task's cleanroom, and Copilot, Node and
Mattermost MCP are installed only in the per-task image. It pins Copilot CLI to
1.0.70 and Mattermost MCP to 0.5.1, matching the experiment image.
Copilot's native inline tool-output threshold is 1 MiB
(`COPILOT_LARGE_OUTPUT_THRESHOLD_BYTES=1048576`); larger results use files.
Native `task` and `list_agents` tools are excluded. Denied MCP tools retain
their permission-denial rules and are also excluded from the advertised tool set.
Check `out/pertask-build/summary.txt` for
`OK … board=True copilot=yes` for every task.

The board MCP server and notice shim run directly with the agent's private
Node runtime; their sources are `board-service/mcp.cjs` and
`mini-router/mcp-notice-shim.cjs`, and neither needs an npm installation. Compose
mounts them into the agent at `/opt/mcp-board.cjs` and `/opt/mcp-notice-shim.cjs`.
Their `.cjs` extension declares CommonJS, including inside the router's ES module
package, without a separate package manifest.

Agent images are named `omcgitea-agent-<task>:pbench`. The launcher compares
their baked entrypoint against this checkout and rejects stale images. Rebuild
after editing `agent/entrypoint.sh`. Prompts, config templates and the
bridge are mounted from the checkout at run time; prompt edits need no image
rebuild. Mini-router and board images must be rebuilt after changing their
sources; preflight checks their build timestamps.

Compose builds bootstrap and secret-service on `make up`, but does not build
mini-router or board. Third-party service images are
`docker.gitea.com/gitea:1.22.6`, `mysql:8.4`,
`mattermost/mattermost-team-edition:10.6`, `nginx:1.27-alpine`,
`gitea/act_runner:0.2.11` and `python:3.13-slim`.

If Docker's default bridge is unavailable, build commands that execute `RUN`
steps may need `--network host`; use the corresponding Dockerfile directly.

## Launch

Check a generated profile, then run preflight:

```bash
make check-env PROFILE=pbench-single-node-pandoc
make -n up PROFILE=pbench-single-node-pandoc
PREFLIGHT_ONLY=1 bash scripts/launch_single_node.sh
```

Preflight checks images, profile values, clean state, network capacity, prompt
mounts and rendered worker/account counts. It also makes a small live model
request to each distinct gateway and starts short-lived image-check
containers. `PREFLIGHT_ONLY=1` skips benchmark launch after those checks.

Launch from the checkout root, keeping the configured `TASKS`, `WORKERS` and
`HOURS` in the environment:

```bash
mkdir -p out
setsid nohup bash scripts/launch_single_node.sh \
  > out/single-node.launch.log 2>&1 < /dev/null &
```

The launcher unsets shell variables whose values would shadow profile keys,
logging keys without their secret values. Every launch gets a UTC `RUN_ID`;
set it explicitly to give the run a distinct name. Tasks run sequentially;
evaluation of one task runs alongside the next task's rollout.

When more than 32 channel/group-DM messages are queued, the router saves the
complete backlog, including full message text, under the worker's
`$HOME/group-messages/`. It shows the latest 32 plus the archive path, omitted
message count and exact mentions of that worker. The worker and its own router
share only that history directory. Direct messages keep their existing fast
delivery path. An archive failure cannot acknowledge the backlog, and retries
retain every affected group message.

- Driver log: `out/single-node.driver.log`.
- Per-task logs: `out/chain-<profile>.{log,summary}` and
  `out/pbench-<task>-single-node.<RUN_ID>.log`.
- Trajectories: `~/pbench-trajectories/<task>.single-node.<RUN_ID>/` by default;
  set `TRAJ_ROOT` to change the root. They include profile data, output and the
  evaluation JSON. `scripts/pbench_turns_prs.py`, `pbench_action_mix.py` and
  `pbench_gitea_facts.sh` summarize activity and repository history.

### Timing and comparison conditions

The six-hour budget includes staggered startup: the runner starts each
agent/router pair, allows time for its ACP process and sends a kickoff DM. The
initial interval is 30 seconds, including container startup, with a default
20-second settle wait. Later workers therefore receive less working time.
The ramp completes even if it overruns the budget, followed by a minimum
60-second wait. At the normal deadline, the runner exports the Git submission
before stopping agents. Export duration can therefore affect the effective
cutoff. These behaviors are preserved from the experiment.
After export, routers and CI runners stop first. Workers then receive up to
600 seconds to cancel native work, stop detached tools and seal final state;
this shutdown grace does not extend the submitted Git cutoff.

All workers receive the same peer-coder role and tool configuration. The CI
merge gate is disabled. Bootstrap creates only the peer-coder team and sets required approvals to
**0**. Direct agent pushes to main are restricted; peers collaborate through
PRs. Compare rendered configuration when auditing a run.

Hold worker count, prompts, cleanroom digests, hardware, gateway capacity and
model configuration constant when comparing results. A shared upstream can
rate-limit larger teams or concurrent evaluations differently. Agent
trajectories contain Copilot usage events for inspecting latency; the optional
`scripts/pbench_rpm_dashboard.py` observes proxy request rates without making
model calls.

## Score

The chain's `SCORE` line and `programbench info` count rerun attempts separately.
For the canonical-kept score, use the reporting tool, which calls
ProgramBench's `score_instance`:

```bash
T=jgm__pandoc.5caad90
TRAJ="$HOME/pbench-trajectories/$T.single-node.<RUN_ID>"
SCORE_DIR=$(mktemp -d)
mkdir -p "$SCORE_DIR/$T"
cp "$TRAJ/out/$T.eval.json" "$SCORE_DIR/$T/"
uv run --project "${PROGRAMBENCH_REPO:-$HOME/programbench}" \
  python tools/pbench_score_report.py "$SCORE_DIR" "$T"
```

Replace `<RUN_ID>` with the launch id. The tool prints both the raw attempt
score and canonical-kept score. Record the ProgramBench revision with the
reported result.

## Stop and recover

Successful runs export, stop the profile and archive trajectories. Use scoped
commands for manual teardown:

```bash
make down PROFILE=pbench-single-node-pandoc   # stop, preserve profile data
make clean PROFILE=pbench-single-node-pandoc # stop and delete this profile's data
```

Each bridge boot saves HOME and the complete `/work` tree, including Git state,
untracked and ignored files, to the private
`agents/<worker>/shutdown/<boot-id>/state.tar.gz` under profile data. Its manifest
is marked complete only after the archive is sealed and its size/checksum are
recorded. No retirement, cloning or session reset is introduced.
The runner retains stopped containers and profile data if shutdown validation
fails. The chain refuses automatic cleanup after an incomplete archive, failed
trajectory copy or source/destination checksum mismatch. Inspect and preserve
these artifacts before using the explicitly destructive `make clean` command.

A failed export writes `EXPORT_FAILED` and the runner still stops containers;
the Gitea repository remains in profile data for recovery. The chain may then
archive that data in its trajectory before cleaning the profile. Inspect the
export log and recover the repository before scoring that run. The runner
rejects leftover output or profile state to prevent it leaking into a new
experiment; preserve the earlier trajectory before cleaning and restarting.

## Security and support

See [SECURITY.md](SECURITY.md) for private vulnerability reporting and
[SUPPORT.md](SUPPORT.md) for project help. This project is licensed under the
[MIT License](LICENSE).

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
