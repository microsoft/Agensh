# omcgitea

## Project Goal

Have the **ACP agent** (default `claude-agent-acp`, with `copilot` opt-in)
do modern development based on self-hosted **Gitea**, with multi-agent parallelism + multiple
microservice repositories, using Gitea native PR + CI/CD (Gitea Actions) end-to-end, and
supporting local CD deployment.

See [`README.md`](./README.md) for how to build, configure and launch it.

## Scope and Boundaries

- **Self-hosted**: Gitea + act_runner + one-agent-per-container
- **Agent implementation is pluggable**: mini-router connects to the agent process via the ACP protocol, agent implementation selected by
  `AGENT_KIND`
  - `AGENT_KIND=claude` (**default**): `@agentclientprotocol/claude-agent-acp`
    (Anthropic Claude Agent SDK's ACP adapter layer)
  - `AGENT_KIND=copilot` (**opt-in**): official Copilot CLI native `copilot --acp --stdio`,
    using the deployer's BYOK endpoint, does not require GitHub login
- **Do not touch upstream code** (a veto line): Hermes, `claude-agent-acp` / Claude Agent SDK,
  Copilot CLI, and Gitea are all treated as external black boxes, **forbidden** any patch / fork / sed / monkey-patch
- **This repo only writes "glue"**: config + bootstrap scripts + docker-compose + docs + tests
  (add reverse proxy only when Plan B is enabled)
- **CI/CD**: uniformly use Gitea Actions
- **Not involving OMC**: OMC currently does not support the agent used by this project, this project is independent of OMC

## Current Stage

The only stack this repo runs is the ProgramBench fleet, one profile `PROFILE=pbench-<mode>-<task>`
per stack, written by `scripts/pbench_gen_env.sh`:

- `scripts/launch_single_node.sh` — a chain of tasks on this host, one Compose stack at a time
  (`pbench-single-node-<task>`)
- `scripts/launch_multi_node.sh [main|smoke]` — the 1,024-agent AKS fleet (`pbench-multi-node-<task>`,
  `pbench-multi-node-smoke-<task>`)
- `scripts/launch_single_agent.sh` — the single-agent Copilot baseline (`PROFILE=pbench-single-agent`)

Every agent runs with a mini-router sidecar, central MySQL and secret-service; the compose base is
rendered per profile by `tools/gen-compose-prod.py`.

- agent → Gitea: call APIs via Gitea official `gitea-mcp` (stdio)
- Gitea → agent: Gitea webhook (`type:"github"`) → mini-router → (ACP) → agent

### Why default claude-agent-acp (fact, not preference)

R-cache-bug investigation measured on prod1/prod2: hermes under real complex context + tool calls
has 100% prompt cache miss (cache_creation 280-340k/turn), causing the Databricks ITPM quota
to be blown → 429 rate limit → agent disabled. Same environment same backend using `claude-agent-acp`
(real reuse of the first 20 rounds of a 73-prompt director session) measured cache_read average 97%,
0 full cold writes. The gap is qualitative, not something tuning can bridge.

That measurement is why there is no hermes agent kind; no image this repo builds or runs comes from Hermes.
The generator's default `AGENT_KIND` is still `claude-agent-acp`; the kept pbench profiles opt into `copilot` (or `sim`).

## Working Principles

### ⛔⛔⛔ Container and Resource Safety (absolute prohibitions)

**Absolutely not allowed to delete/stop/operate on any docker container, image, volume, or network not built by this project.**

- Before killing a container, **must** confirm the container name starts with this project's prefix (`omcgitea*` / `omcgitea-*` / `docker_omcgitea*`)
- `docker stop/rm/kill/prune` is **absolutely forbidden** to act globally (no filter, `-a`, `prune` without filter are all forbidden)
- Seeing `teamharness-*`, `claude-team*`, or other user projects → **absolutely do not touch**, do not inspect or operate
- Images, volumes, networks likewise: if not part of this project, do not delete, modify, tag, or rename
- Unfamiliar containers: first `docker inspect` to see label/source, confirm not this project then exit the operation
- Existing incident record: previously accidentally deleted resources on other machines of the user, continuing to commit this in this project would be a serious incident

Clearing the environment is only allowed via: `make down PROFILE=pbench-<...>` / `make clean PROFILE=pbench-<...>`
(acting only on this project's compose project names `omcgitea-pbench-*`, including
`mysql` / `secret-service` / `mini-router-*` / `agent-*`; on AKS, `scripts/pbench_k8s_down.sh` for this
project's `pbench-*` namespace), and manually deleting this project's images
`omcgitea-*`, `omcgitea-mini-router:local`, `omcgitea-secret-service:local`,
`hermes-agent:local` (only after confirming they are built by this project).

### ⛔ TDD (strictly enforced)

**Any code change must be test-first**, and tests must be **real tests**, forbidden to mock out critical integration paths:

1. **Write failing test first** — red
2. **Write minimal code to make the test pass** — green
3. **Refactor** (keep green) — refactor

#### Hard Requirements for Real Tests

- **Real containers**: tests must run on real docker-started Gitea + agent + mini-router, not allowed to mock-replace the Gitea HTTP service, agent process, or webhook path
- **Real HTTP**: the webhook path must be triggered by real Gitea (`POST /repos/{o}/{r}/hooks` to create webhook, then actually open issue to trigger), not allowed to manually curl-simulate the Gitea webhook payload as a substitute
- **Real token / permissions**: use bootstrap-issued real scoped tokens, do not shortcut with admin token
- **Real git operations**: clone / push / PR go through real Gitea HTTP, not allowed to directly write Gitea sqlite
- **Real MCP**: agent calls to Gitea must go through the stdio MCP subprocess, not allowed to bypass MCP and directly call the Gitea API during tests

Scope where mocking is allowed: only **external LLM API** (for cost and rate reasons; use fixtures to record responses or stub the model). Everything else is real.

#### Things Not Allowed

- Writing code without writing tests
- Tests only running "internal functions" and not real integration paths
- Using mock / stub to replace any link in the Gitea / agent / webhook path
- Tests passing but actual docker compose does not come up / bidirectional does not connect
- Modifying bootstrap / Dockerfile / compose without a real launch of the path it changes

### Do Not Touch Upstream

- Modifying any source file in `hermes-agent/` → forbidden
- Modifying any source file inside the Gitea container → forbidden
- Modifying any source file of `@agentclientprotocol/claude-agent-acp` / Claude Agent SDK → forbidden
- Modifying Copilot CLI, or substituting it with the Copilot SDK, `copilot -p`, or headless private RPC in place of native ACP → forbidden
- sed / patch / overlay / monkey-patch injection of Hermes / claude-agent-acp / Copilot CLI / Gitea → forbidden
- Forking any of the above into a self-maintained branch → forbidden

Allowed: `FROM` upstream image as-is / `npm i` upstream package as-is; `COPY` **newly-added** configs / binaries / templates into the container; `RUN` to install new dependencies.

Any requirement that "must modify upstream" → first work around via sidecar / reverse proxy / config; if the workaround fails → file an issue with upstream, **do not bypass inside this project**.

> `hermes-agent/` carries two old local patches (`agent/prompt_caching.py` / `acp_adapter/server.py`); nothing this
> repo builds or runs uses it (the agent base, `docker/agent-base/Dockerfile`, is `FROM ubuntu:22.04`).

### Doc-Code Synchronization

- A change to how images are built, profiles are generated or runs are launched updates `README.md`
  in the same commit

### Repo Hygiene

- Do not automatically modify `.claude/settings.local.json` or local worktree / coordination data (already in `.gitignore`)
- `oh-my-claudecode/` and `hermes-agent/` are **external reference code**, read-only, do not modify, do not commit (already in `.gitignore` or add as appropriate)
- Before committing, confirm no local configs or secrets are carried
- `docker compose down && docker compose up -d` must be recoverable (all persistence goes through host bind mount, bootstrap is idempotent)
