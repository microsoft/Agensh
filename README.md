# omcgitea — ProgramBench agent fleet

Three launch paths are kept:

| Path | Where it runs | Launcher |
|---|---|---|
| Single-node | docker compose on this host | `scripts/launch_single_node.sh` |
| Multi-node | AKS (1024 agents, 16 nodes) | `scripts/launch_multi_node.sh` |
| Single-agent Copilot ACP baseline | docker on this host | `make pbench-single-agent` |

All three run `AGENT_KIND=copilot`. Each launcher's preflight refuses to start on
a wrong profile, a stale image or a missing prerequisite, so read its FATAL
lines rather than working around them.

Credentials are never committed. Keep them in `~/.pbench-upstream.env` (mode
600): `LLM_UPSTREAM` (gateway base URL), `LLM_UPSTREAM_TOKEN` (bearer key) and
`REASONING_EFFORT=high`. The profile generator reads it; the profiles it writes
contain the token and are mode 600.

---

## 1. Build the images

Every `omcgitea-*` image is built from this repo. Everything else is pulled.
A ProgramBench task id such as `jgm__pandoc.5caad90` names the cleanroom
`programbench/jgm_1776_pandoc.5caad90:<tag>` (`__` becomes `_1776_`).

| Image | Source | Built or pulled by | Used by |
|---|---|---|---|
| cleanroom `:task_cleanroom_v6` | ProgramBench | you (`docker pull`) | agent images' base; single-node and multi-node preflight |
| cleanroom `:task_cleanroom` | ProgramBench | runner / single-agent launcher, on first use | workspace seed on every path; single-agent image's base |
| `omcgitea-agent-base:pbench` | `docker/agent-base/Dockerfile` | frozen, see below | agent and sim-agent images' base |
| `omcgitea-agent-<repo>:pbench` | `docker/agent/Dockerfile` | `scripts/pbench_build_pertask_images.sh` | single-node; multi-node from ACR |
| `omcgitea-mini-router:local` | `mini-router/` | you | single-node; multi-node as ACR `:pbench` |
| `omcgitea-board:local` | `board-service/` | you | single-node; multi-node as ACR `:pbench` |
| `omcgitea-bootstrap:local` | `docker/bootstrap/` | you or `make up` | single-node; multi-node as ACR `:pbench` |
| `omcgitea-secret-service:local` | `secret-service/` | you or `make up` | single-node; multi-node as ACR `:pbench` |
| `omcgitea-single-agent:<task>` | `docker/single-agent/Dockerfile` | the single-agent launcher, every run | single-agent |
| `omcgitea-sim-agent:local`, `omcgitea-mini-router:sim` | `docker/sim-agent/Dockerfile`, `mini-router/` | you | the sim profile |
| third-party (below) | Docker Hub, `docker.gitea.com` | compose on `make up`; the AKS nodes | as listed |

The pulled third-party images are `docker.gitea.com/gitea:1.22.6`, `mysql:8.4`,
`mattermost/mattermost-team-edition:10.6`, `nginx:1.27-alpine`,
`gitea/act_runner:0.2.11` and `python:3.13-slim` (the egress proxy) on the team
paths, plus `curlimages/curl:8.11.1` on AKS. The single-agent stack pulls only
`python:3.13-slim`.

### Cleanroom and base images

- `programbench/<task>:task_cleanroom_v6` for every team task you run. Pull it
  before building the agent image; both team launchers refuse to start without
  it:

  ```bash
  sudo docker pull programbench/jgm_1776_pandoc.5caad90:task_cleanroom_v6
  ```

- `programbench/<task>:task_cleanroom` is a different build of the same task.
  The workspace is seeded from it, and the runner and the single-agent launcher
  pull it themselves when it is missing.
- `omcgitea-agent-base:pbench` holds the `gitea-mcp` binary and
  `claude-agent-acp`. Its recipe is `docker/agent-base/Dockerfile`. The image is
  frozen because `docker.gitea.com` is unreachable from this host. The header of
  that Dockerfile explains why, and gives the command for a host that can reach
  it:

  ```bash
  sudo docker build -t omcgitea-agent-base:pbench docker/agent-base
  ```

### Agent images (single-node and multi-node)

There is one image per task, built `FROM` that task's `:task_cleanroom_v6`, so
the agent builds with the same toolchain it is graded with. Both team paths run
the same image:

```bash
TASKS="jgm__pandoc.5caad90 php__php-src.c891263" JOBS=2 \
  bash scripts/pbench_build_pertask_images.sh
```

- **Name:** `omcgitea-agent-<repo>:pbench`, e.g. `omcgitea-agent-pandoc:pbench`.
- **Logs:** `out/pertask-build/`. After the build, the script checks each image
  with `--network none`, and `out/pertask-build/summary.txt` must show
  `OK … board=True acp=yes` for every task.

**What is baked in:**
- `docker/agent/` and the two prompts the entrypoint reads,
  `prompts/team/agents.md` and `pbench-brief.md`.
- The other files under `prompts/` are not. `scripts/lib_prompts.sh` renders
  them on the host and the launchers send them, so a change to them needs no
  rebuild.

**When to rebuild:** both launchers mount the prompts, the config templates and
the bridge over the baked copies, but not the entrypoint, so **a change to
`docker/agent/entrypoint.sh` requires a rebuild**. Both launchers compare the
baked entrypoint with the checkout's and refuse to launch on a stale image.
These in-image reads run with `--network none`, so they work even when the
host's default docker bridge is gone.

### Support images (single-node)

```bash
sudo docker build -t omcgitea-mini-router:local    mini-router/
sudo docker build -t omcgitea-board:local          board-service/
sudo docker build -t omcgitea-secret-service:local secret-service/
sudo docker build -t omcgitea-bootstrap:local      docker/bootstrap/
```

`make up` runs `docker compose up --build`, which builds only bootstrap and
secret-service. Compose has no build for mini-router or board, so build those
two by hand:
- before the first run;
- after any change to their source.

The single-node preflight refuses either image if it is missing or older than
its build inputs: the Dockerfile and every file it copies in (for mini-router,
`package.json`, `package-lock.json`, `tsconfig.json`, `src/` and `sql/`).

### Single-agent image

`make pbench-single-agent` builds `omcgitea-single-agent:<task>` on every run,
before its stack comes up. The build uses `docker/single-agent/Dockerfile`:
`FROM` the task's `:task_cleanroom`, plus Node 22.14.0 and
`@github/copilot@1.0.70`.

The build downloads both from nodejs.org and the npm registry, so it needs
network access, even though the running agent has none. Nothing is built by
hand. `SINGLE_AGENT_IMAGE` overrides the tag.

### Sim images (no-LLM pipeline check)

```bash
sudo docker build -t omcgitea-sim-agent:local -f docker/sim-agent/Dockerfile .
sudo docker build -t omcgitea-mini-router:sim mini-router/
```

- **What they run:** `omcgitea-sim-agent:local` runs `AGENT_KIND=sim`, with no
  LLM, on top of `omcgitea-agent-base:pbench`.
- **Who uses them:** `.env.pbench-sim.example`, the sim profile, names both
  images.

### Push to ACR (multi-node only)

The AKS path pulls from `$PBENCH_ACR.azurecr.io` (default `agensteamacr`). The
agent image keeps its `:pbench` tag. The support images are pushed as `:pbench`;
`SUPPORT_IMAGES` at the top of `scripts/launch_multi_node.sh` lists them.
**Do not overwrite `:local` in ACR**: other fleets pull it by mutable tag.

```bash
az acr login -n agensteamacr
R=agensteamacr.azurecr.io
push() { sudo docker tag "$1" "$R/$2" && sudo docker push "$R/$2"; }
push omcgitea-agent-pandoc:pbench        omcgitea-agent-pandoc:pbench
push omcgitea-mini-router:local          omcgitea-mini-router:pbench
push omcgitea-board:local                omcgitea-board:pbench
push omcgitea-bootstrap:local            omcgitea-bootstrap:pbench
push omcgitea-secret-service:local       omcgitea-secret-service:pbench
```

The preflight resolves each tag to a digest and pins it. It refuses a tag in
either case:
- the tag is not in ACR;
- the tag was pushed before the last git commit under its source:
  - `docker/agent/` for the agent image;
  - `mini-router`, `board-service`, `secret-service` and `docker/bootstrap`
    for the support images.

So commit, then build and push.

### When the default docker bridge is missing

Build steps that `RUN` a command use docker's default bridge. If the bridge is
gone, a build fails with `failed to create endpoint … docker0 … Device does not
exist`. Add `--network host` to the `docker build` command. The scripts do not
pass it, so run their build command by hand. Its layer cache is separate, so
the first such build starts from scratch.

---

## 2. Profiles

A run is configured by an untracked `.env.pbench-<mode>-<task>` at the repo
root, e.g. `.env.pbench-single-node-pandoc`. The mode is `single-node`,
`multi-node` or `multi-node-smoke`; the task is the short name of the
ProgramBench task (`pandoc` for `jgm__pandoc.5caad90`).

- **Single-node and multi-node:** generate the profiles rather than writing them
  by hand. `TASKS` lists the tasks (default pandoc) and `WORKERS` the agents per
  stack (default 8 single-node, 1024 multi-node). Regenerating keeps the
  profile's local passwords.

  ```bash
  MODE=single-node WORKERS=8 bash scripts/pbench_gen_env.sh
  MODE=multi-node             bash scripts/pbench_gen_env.sh
  MODE=multi-node-smoke       bash scripts/pbench_gen_env.sh
  ```

  Each task gets its own ports and subnets, the same whichever tasks are
  generated together. Single-node subnets are sized from the worker count.

  When the AKS namespace reaches the gateway through the local reverse-SSH
  relay (`scripts/pbench_k8s_gateway_relay.sh`), set `LLM_UPSTREAM` to the
  relay's in-cluster endpoint while generating,
  `http://<relay-name>.<namespace>.svc.cluster.local:18080`.

  The multi-node preflight additionally requires:
  - `AGENT_IMAGE=omcgitea-agent-<repo>:pbench`;
  - `AGENT_KIND=copilot`, `ANTHROPIC_MODEL=gpt-5.6-sol`;
  - `COPILOT_PROVIDER_WIRE_API=responses`, `COPILOT_AGENT_REASONING_EFFORT=high`;
  - `COPILOT_PROVIDER_MAX_PROMPT_TOKENS=272000`;
  - a `COPILOT_STATE_DIR` that is not on the Azure Files share;
  - the 1,024-agent capacity keys (MySQL, Gitea, Mattermost, file share).

  The runner takes the agent image from the profile's `AGENT_IMAGE`; a shell
  `AGENT_IMAGE` overrides it, as it does for compose. There is no default. A
  single-node run stops before bringing up the stack if the image is not built.

- **Single-agent baseline:** `.env.pbench-single-agent` holds
  `PBENCH_LLM_UPSTREAM`, `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL`. Values in this
  file win over the shell. For `gpt-5.6-sol` it also needs
  `COPILOT_PROVIDER_WIRE_API=responses` and `COPILOT_PROVIDER_MAX_PROMPT_TOKENS=272000`:
  the gateway refuses that model on chat/completions, and only the responses
  transport carries the effort. The effort is `PBENCH_ACP_EFFORT`, default `high`.

Check that a single-node profile renders before launching it:

```bash
make check-env PROFILE=pbench-single-node-pandoc
make -n up     PROFILE=pbench-single-node-pandoc
```

---

## 3. Launch

Launch from a clean shell. The launchers unset any shell variable that shadows a
profile key, and log each one. Detach with `setsid nohup` so the run survives the
terminal.

The request rate scales with agent count. An 8-agent pandoc run makes 3–5
requests per minute per agent, so 1024 agents need roughly 3,200–5,500 RPM.
Confirm the gateway can serve that before a large run.

Every launch has a `RUN_ID` (default: the UTC start time) that names its logs
and trajectories, so a rerun never overwrites an earlier one.

### Single-node (compose)

```bash
setsid nohup env TASKS=jgm__pandoc.5caad90 WORKERS=8 HOURS=6 \
  bash scripts/launch_single_node.sh > out/single-node.launch.log 2>&1 < /dev/null &
```

- **Knobs:** `HOURS` is wall-clock per task. `WORKERS` must match the profiles.
  `TASKS` defaults to five tasks run one after another (pandoc, gromacs, ctags,
  php-src, ffmpeg). `PREFLIGHT_ONLY=1` checks everything and launches nothing.
- **Logs:** `out/single-node.driver.log`. Per task, `out/chain-<profile>.log`
  and `.summary`, and the runner's `out/pbench-<task>-single-node.<RUN_ID>.log`.
- **Trajectories:** `~/pbench-trajectories/<task>.single-node.<RUN_ID>/`, with
  the task's `out/<task>.eval.json` copied in.
- **Last validated:** 2026-09-23 (8 agents, 6h, pandoc, gpt-5.6-sol high), end
  to end: 32.41% canonical-kept.

### Multi-node (AKS)

```bash
az aks get-credentials -g h100 -n agensteam-aks --overwrite-existing
setsid nohup env HOURS=6 bash scripts/launch_multi_node.sh main \
  > out/multi-node.launch.log 2>&1 < /dev/null &      # or: smoke
```

- **`main`:** 1024 agents, 6h, profile `pbench-multi-node-<task>`.
- **`smoke`:** a bounded 10-minute run on profile `pbench-multi-node-smoke-<task>`.
  Run it first after any image or profile change.
- **Namespace:** the profile name.
- **Registry and subscription:** `PBENCH_ACR` and `AZ_SUBSCRIPTION` select them.
- **Logs:** `out/multi-node.driver.log` (`out/multi-node-smoke.driver.log`).
- **Board rollout:** `board-service` is a one-replica, in-memory board over a MySQL
  WAL and uses the Kubernetes `Recreate` strategy; never overlap two board pods.
  Its MySQL-backed pending-delivery lease still survives a pod restart and
  serializes the independent MCP notice shims for each agent.

### Single-agent Copilot ACP baseline

```bash
make pbench-single-agent TASK=jgm__pandoc.5caad90 HOURS=6
# optional: OUT_DIR=out/pbench-single-agent/<name>
```

This builds its own per-task image, `omcgitea-single-agent:<task>`, from
`docker/single-agent/Dockerfile`. It runs one ACP session behind the
egress proxy, then exports and scores the submission into `OUT_DIR` (default
`out/pbench-single-agent`). Set `PBENCH_SKIP_EVAL=1` to skip scoring.

---

## 4. Score and throughput

The chain's `SCORE` line (in `out/chain-<profile>.summary`) and
`programbench info` count every `--reruns=2` attempt as its own test, so they
overstate the result, by more than 2x on pandoc. Report canonical-kept, which
is ProgramBench's `score_instance`:

```bash
T=jgm__pandoc.5caad90
TRAJ=~/pbench-trajectories/$T.single-node.<RUN_ID>
mkdir -p /tmp/score/$T && cp "$TRAJ/out/$T.eval.json" /tmp/score/$T/
uv run --project ~/programbench python tools/pbench_score_report.py /tmp/score $T
```

The tool prints both numbers. It reads `<run_dir>/<task>/<task>.eval.json`. The
chain renames its run dir to `*.archived`, so copy the eval.json under the real
task id as above.

The score tracks LLM latency: slower calls mean fewer iterations. Before
auditing the harness over a low score, compare per-call latency. Each agent's
`data-root/agents/pbench-worker<N>/home/.copilot/session-store.db` (under
`data-root/hermes/pbench-team1-worker<N>/` in older trajectories) has an
`assistant_usage_events` table (`duration_ms`, `output_tokens`, `created_at`).
Copy it with its `-wal`/`-shm` files before opening it. On a healthy upstream
the median call takes about 8 s and decoding about 8 ms per output token; at
12.6 s and 27 ms per token an 8-agent pandoc run makes ~40% fewer calls in its
6h and scores accordingly lower.

The egress proxy retries 429/5xx silently and buffers each response, so upstream
trouble never shows on the client side, and its logs are lost at teardown. On a
slow upstream, a call that runs past ~600 s trips Copilot's `Native model HTTP
stream timed out`, and each costs the worker the time it waited.

---

## 5. Tear down

Use only this project's scoped commands. Never run a global `docker stop`, `rm`
or `prune`.

```bash
make down  PROFILE=pbench-single-node-pandoc   # stop, keep data
make clean PROFILE=pbench-single-node-pandoc   # stop and wipe this profile's data
PROFILE=pbench-multi-node-pandoc bash scripts/pbench_k8s_down.sh   # AKS namespace (KEEP=1 keeps PVCs)
```

A successful run tears itself down after export. A failed export leaves the
stack or namespace up so it can be inspected.

## Security and support

See [SECURITY.md](SECURITY.md) for private vulnerability reporting and
[SUPPORT.md](SUPPORT.md) for project help. This project is licensed under the
[MIT License](LICENSE).

The token service validates complete agent identifiers and checks that token
paths resolve within `SECRET_SERVICE_TOKENS_DIR`. Token writes use private
temporary files and an atomic replace. Rejected HTTP requests close their
connection so unread token bodies cannot enter parser error logs; startup logs
omit the token storage path.

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
