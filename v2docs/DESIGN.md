# omcgitea Design Document v2

> The router path originally described here (single-instance `omcgitea-router`, `docker exec`
> ACP, SQLite events table) was superseded by [`DESIGN_R7_SIDECAR.md`](./DESIGN_R7_SIDECAR.md):
> per-agent mini-router sidecar + central MySQL + secret-service. **The superseded text has been
> removed rather than kept alongside** — what remains below is what R7 left standing: bootstrap,
> the write direction, the Gitea quirks, persistence and the upstream boundary.
>
> "Hermes" / "hermes-agent" below means the generic ACP agent. The default is
> `AGENT_KIND=claude` (`@agentclientprotocol/claude-agent-acp`); `AGENT_KIND=hermes` is a dormant
> compatibility option. Switching changes neither the ACP protocol layer nor the mini-router
> interface. See CLAUDE.md for the decision and its factual basis.
>
> Version: v2.3 | Date: 2026-04-28
> Companion: `REQUIREMENTS.md`, `INTERFACE.md`, `DESIGN_R7_SIDECAR.md`

---

## 0. Key Facts

### 0.1 Directly Use Upstream Capabilities (zero code)

| Capability | Provided by | Assembly point |
|---|---|---|
| MCP client (stdio + HTTP) | Hermes (`tools/mcp_tool.py`) | `~/.hermes/config.yaml` top-level `mcp_servers:` |
| ACP stdio JSON-RPC server | Hermes (`acp_adapter/`, built-in entry) | Container CMD: `python -m acp_adapter.entry` |
| Anthropic prefix cache hit | Hermes (`run_agent.py:744-747` cache gate) | `provider="anthropic"` + `api_mode="anthropic_messages"` |
| Docker base image + entrypoint | Hermes (built-in `Dockerfile` + `docker/entrypoint.sh`) | Directly `FROM` |
| Session persistence / cross-process restore | Hermes (`acp_adapter/session.py`, drops to `state.db`) | Automatic |
| git credential helper | git CLI standard | entrypoint writes `~/.git-credentials` |
| Gitea per-user notification | Gitea (`/api/v1/notifications` + `/user/events` SSE) | mini-router direct connection |

### 0.2 Must Do Ourselves

| Item | Implementation |
|---|---|
| **mini-router** | TS / Node 20+ sidecar, one per agent; holds one ACP connection + one SSE long connection + cursor pull; events drop to central MySQL; at-most-once delivery |
| **Gitea MCP server integration** | Use official `docker.gitea.com/gitea-mcp-server`, multi-stage `COPY --from=...` to install `/usr/local/bin/gitea-mcp` into the agent image |
| **Write back to Gitea** | Agents call issue / PR / review / merge tools themselves via MCP |
| **Multi-agent = multi-container** | One agent process = one agent identity = one `HERMES_HOME` = one token; architectural necessity |
| **gitea-admin-init sidecar** | Gitea 1.22 no longer auto-creates admin from env vars; one-time container runs `gitea admin user create` |
| **Bootstrap script** | Create users / tokens / repos, write `tokens/`, idempotent; also **delete leftover** hermes-agent webhooks |
| **LLM integration** | `provider="anthropic"` + `api_mode="anthropic_messages"`, hits cache gate |
| **shell environment isolation** | Makefile uses `env -u ANTHROPIC_*` to strip the user's `~/.bashrc` same-name variables |

**Do-not-touch-upstream principle**: this repo **does not modify** any source code of the agent
runtime or Gitea. All differences are smoothed over via external glue. See §8.

---

## 1. Architecture Overview

The deployed topology is the R7 sidecar one — see [`DESIGN_R7_SIDECAR.md`](./DESIGN_R7_SIDECAR.md) §3
for the diagram: central singletons (gitea / nginx-edge / act-runner / bootstrap / mysql /
secret-service) plus one `(mini-router, agent)` pod per agent.

**Two data paths**:

- **Agent → Gitea (write)**: in-container stdio MCP (does not leave the container)
- **Gitea → Agent (read)**: the agent's own mini-router holds SSE (cookie) as trigger + REST (PAT) pulls the body → ACP `session/prompt` delivered to the agent

**Invariants**:

- Each agent container: 1 ACP agent process + 1 `gitea-mcp` stdio subprocess
- Agent container **listens on no HTTP port** (the webhook server has been taken down)
- One agent container binds to only one Gitea user token
- **Do not modify any source code of the agent runtime / Gitea**

---

## 2. Module Inventory

### 2.1 Container Services

| Service | Image | Responsibility |
|---|---|---|
| `gitea` | `docker.gitea.com/gitea:1.22.6` | Gitea itself |
| `gitea-admin-init` | Same as gitea, different entrypoint | One-time admin creation |
| `bootstrap` | Self-built (alpine + curl/jq) | Create users/tokens/repos + delete leftover webhooks |
| `nginx-edge` | `nginx:1.27-alpine` | Unique external port; reverse proxy Gitea |
| `mysql` | `mysql:8.4` | Central `events` / `cursors` / `acp_sessions` store (R7 §4.4) |
| `secret-service` | Self-built (Python 3.12 stdlib) | Hands each sidecar its agent token (R7 §4.2) |
| `mini-router-<agent>` | Self-built (TS / Node 20+) | One event-delivery sidecar per agent (R7 §4.1) |
| `hermes-agent-<agent>` | Self-built (FROM agent runtime + COPY gitea-mcp) | One agent per container |
| `gitea-runner` | `gitea/act_runner:0.2.11` | Actions runner |

The ProgramBench overlays (`docker/docker-compose.pbench*.yml`) layer on top of this set; the
agent roster itself is generated per-profile by `tools/gen-compose-prod.py`.

### 2.2 Repo Structure

```
omcgitea/
├── CLAUDE.md / Makefile / .env.<profile>
├── v2docs/{REQUIREMENTS,DESIGN,DESIGN_R7_SIDECAR,INTERFACE,TESTING,UEM,TEAMCONFIG}.md
├── docker/
│   ├── docker-compose.yml            ← dev/base stack
│   ├── docker-compose.prod.yml       ← frozen 37-agent template
│   ├── docker-compose.pbench*.yml    ← ProgramBench overlays
│   ├── nginx-edge/                   ← reverse proxy config
│   ├── hermes-agent/                 ← Dockerfiles + entrypoint + acp-bridge + templates
│   └── bootstrap/
├── mini-router/                      ← TS source + unit tests (vitest)
├── secret-service/                   ← token distribution (Python)
├── board-service/ + mcp-board/       ← shared context board (ProgramBench 1-team arm)
├── tools/gen-compose-prod.py         ← renders the per-profile agent roster
├── scripts/                          ← sweep drivers / chain / per-task runner / scoring
└── tests/{pbench,f8_sidecar}/        ← real-container integration tests
```

---

## 3. Communication Details

### 3.1 Agent → Gitea (write direction)

#### 3.1.1 Medium: Gitea MCP server (stdio)

One stdio subprocess is started inside each agent container, loaded via `$HERMES_HOME/config.yaml`:

```yaml
mcp_servers:
  gitea:
    command: "/usr/local/bin/gitea-mcp"
    args: ["-t", "stdio"]
    env:
      GITEA_HOST: "http://gitea:3000"
      GITEA_ACCESS_TOKEN: "${GITEA_TOKEN}"   # entrypoint reads from token file
      GITEA_INSECURE: "true"
    timeout: 120
```

Token is read in via bind-mount file + entrypoint (0600).

#### 3.1.2 Enabled MCP Tools (actually run and covered)

`list_repo_issues` / `get_issue_by_index` / `create_issue` / `edit_issue` / `create_issue_comment` / `list_repo_pull_requests` / `get_pull_request_by_index` / `create_pull_request` / `submit_pull_request_review` / `merge_pull_request`

#### 3.1.3 git CLI Credentials

Image entrypoint writes `~/.git-credentials` (0600) `http://<agent>:<token>@gitea:3000`, `git config --global credential.helper store`. clone/push goes through container internal network `http://gitea:3000`.

### 3.2 Gitea → Agent (read direction)

#### 3.2.1 Medium: mini-router sidecar (cursor pull + SSE trigger → ACP)

**webhook is gone**. The unique entry for events is the agent's own mini-router:

```
Gitea  ─[L1 upstream]─→  Listener  ─[L2 internal]─→  Core  ─[L3 downstream]─→  Agent
       SSE / REST                     MySQL                  unix socket / ACP
```

Each agent has two Gitea connections hung within its sidecar:

| Connection | Endpoint | Credential | Purpose |
|---|---|---|---|
| **REST pull** | `GET /api/v1/notifications?since=<cursor>` | **PAT** (`agent-<n>.token`) | Get event body |
| **SSE trigger** | `GET /user/events` | **session cookie** (`GiteaFormAuth` form login) | Receive `notification-count` sideband trigger |

The two halves of one workflow are hung under two mutually incompatible auth systems — a
side-effect of Gitea's historical route tree split, **which cannot be unified from our side**.
The measured endpoint/credential matrix and what SSE actually pushes (a bare count, no body)
are specified once in [`INTERFACE.md`](./INTERFACE.md) §0.1 / §0.2 and are not repeated here.

Because SSE carries no body, the listener topology is:

```
SSE notification-count event  →  trigger()  →  pollOnce()
                                                 │
                                                 ▼
                                  GET /api/v1/notifications?since=<cursor>
                                                 │
                                                 ▼
                                  ingest UEM → events table → advance cursor
```

`UpstreamAuth` serves SSE only (`GiteaFormAuth`), with a failure breaker (5 consecutive
failures → lock 60s) to prevent reconnection storms.

#### 3.2.2 ACP Delivery

Delivery runs mini-router → unix socket → the `acp_adapter.entry` that socat forks inside the
agent container. Session lifecycle, same-agent batch merge, the at-most-once state machine and
the 20-minute no-update watchdog are specified in [`INTERFACE.md`](./INTERFACE.md) §4 and
[`DESIGN_R7_SIDECAR.md`](./DESIGN_R7_SIDECAR.md) §4.3 / §8 / §9.

Why ACP instead of webhook: the webhook platform hardcodes `chat_id = webhook:{route}:{delivery_id}`,
so each delivery is a new session and **never hits prefix cache**. An ACP session_id held by us
accumulates history → hits the Anthropic prefix cache. M2-E.0 fixed `provider="anthropic"` hitting
the cache gate (`run_agent.py:744-747`).

The prompt is an **environmental observation** and does not mandate a reply — the agent decides
autonomously. Its exact rendering is in [`INTERFACE.md`](./INTERFACE.md) §4.3.

#### 3.2.3 Delivery Correctness: 100% Delegated to Gitea

The router layer makes no delivery semantic judgment — "which agent receives which event" is
entirely determined by the Gitea notification model. The source-code proof, and the three
bootstrap settings that keep agents out of the watcher set, are in
[`REQUIREMENTS.md`](./REQUIREMENTS.md) §5.4.

### 3.3 LLM Inference Channel

```yaml
model:
  default: "claude-opus-4-7"        # Hermes forces . → -, config directly writes hyphenated
  provider: "anthropic"             # hits run_agent.py:744-747 cache gate
  base_url: "${ANTHROPIC_BASE_URL}"
  api_mode: "anthropic_messages"

custom_providers: []                # cannot use custom_providers, would bypass cache gate
```

Key points:
- `provider: "anthropic"` is a necessary condition to hit prefix cache (measured)
- `ANTHROPIC_API_KEY` goes through `_is_oauth_token` shape detection, sk-* shape is sent with `x-api-key` header

---

## 4. Bootstrap Flow

The `bootstrap` container (one-time) executes:

1. Wait for Gitea healthy
2. Use admin token (on first launch create scoped token via admin Basic Auth, drop to `tokens/admin.token`)
3. For each agent name create Gitea user `<agent>`
4. For each agent generate scoped token, drop to `tokens/agent-<n>.token` (0600); scopes: `read:repository,read:issue,write:issue,read:user,read:notification` (**does not include `write:repository`** — REQUIREMENTS §4.3, agents forbidden to create repos)
5. Set password for each agent (used for form login), drop to `tokens/agent-<n>.password` (0600)
6. **As chairman**, create repos `chairman/<repo>`, push templates to main, add each agent as collaborator (write)
7. **Configure branch protection** (REQUIREMENTS §5.5): `POST /repos/{o}/{r}/branch_protections`, required_approvals=1 + merge_whitelist includes all agents
8. **agent unwatch**: for each agent for each repo call `PUT /repos/{o}/{r}/subscription {subscribed:false}` once (turn off residual auto-watch; REQUIREMENTS §5.4)
9. **Delete leftover hermes-agent webhook**: list each repo's hooks, match `config.url ~ "hermes-agent-.*:8644/webhooks/gitea"` and DELETE all (M2-E.1 cleanup; this step is a no-op on fresh install)
10. Mark `tokens/.bootstrap-done`, exit

Idempotent: all create actions first GET check; webhook cleanup + unwatch + branch protection are write-to-desired-state.

---

## 5. Data Persistence

| Path | Content | Who writes |
|---|---|---|
| `.claude-team-data/<profile>/gitea/` | All Gitea data | gitea container |
| `.claude-team-data/<profile>/tokens/` | admin/agent token + password | bootstrap |
| `.claude-team-data/<profile>/hermes/<agent>/` | `HERMES_HOME` (`/opt/data`): memories/skills/sessions/state.db | agent container |
| `.claude-team-data/<profile>/mysql/` | `events` / `cursors` / `acp_sessions` tables (R7 §5) | mysql |
| `.claude-team-data/<profile>/sidecar/<agent>/` | mini-router cursor cache / temp state (**not** authoritative) | mini-router |

`docker compose down` does not lose; `up -d` restores.

### 5.A Profile Isolation

The same code can run multiple profiles in parallel, **data / containers / networks / ports, along with the set of agents to start** are all isolated:

| Dimension | Isolation method |
|---|---|
| Data | `.claude-team-data/<profile>/` (or `${DATA_ROOT}/<profile>` for `org-*`), bind path inlines `${PROFILE}` |
| Compose project | `--project-name omcgitea-<profile>` (automatically prefixed) |
| Network | Each project has an independent docker bridge |
| Port | `EDGE_HTTP_PORT` determined by `.env.<profile>` |
| Config | one `.env.<profile>` each |
| Agent set | docker-compose `profiles:` tag, plus the per-profile roster rendered by `tools/gen-compose-prod.py` |

Entry: `make up PROFILE=<p>`, `make down PROFILE=<p>`, `make clean PROFILE=<p>` (only cleans its own profile).

---

## 6. External Access / Boundary Exposure

**`nginx-edge` is the unique external entry**, exposing externally the **single port `${EDGE_HTTP_PORT}`**:

```
public :EDGE_HTTP_PORT
        │
┌───────▼───────┐
│  nginx-edge   │  ← unique external port
└───────┬───────┘
        │   docker network omcgitea-<profile>_default
        └──── gitea.<EDGE_DOMAIN>  → gitea:3000
              other Hosts          → 444 (deny)
```

Lockdown decisions:
- gitea has all host ports removed; if local direct connection is needed, the compose file has a commented-out `127.0.0.1:3000:3000` line
- agent / mini-router are not exposed externally at all (event flow all within docker network)
- `default_server` denies unknown Host (`return 444`)
- Port chosen 28080/28081 (avoids 80/443)

---

## 7. Known Constraints / Risks

| Topic | Current handling | Subsequent |
|---|---|---|
| Gitea REST / SSE dual credentials | sidecar holds PAT + cookie; `UpstreamAuth` only serves SSE; upstream quirk, cannot be unified | Leave unchanged (unless Gitea moves SSE to `/api/v1/events` or adds reqToken exemption) |
| Token leakage surface | Same uid in container, mutually `/proc/<pid>/environ` readable | Multi uid / k8s secret, post-audit |
| ACP process crash | Monitor exit code, `load_session` restores on restart | agent runtime already drops `state.db`, 0 data loss |
| session infinite growth | Agent runtime has a built-in context compressor | No router intervention needed |
| LLM model name `.` forced to `-` | Directly write hyphenated version | Upstream PR proposing to add `preserve_dots` |

Per-agent fault isolation (the old single-point router risk) is handled by the sidecar
topology — see [`DESIGN_R7_SIDECAR.md`](./DESIGN_R7_SIDECAR.md) §10.

---

## 8. Do-Not-Touch Upstream Boundary (a veto line)

The veto line and its exact prohibitions are stated once, authoritatively, in **CLAUDE.md**
("Do Not Touch Upstream"). It is not restated here.

In one line: `FROM` upstream images as-is and `COPY` newly-added files in; never patch, sed,
overlay or fork Hermes / claude-agent-acp / Copilot CLI / Gitea. Any requirement that "must
modify upstream" is worked around via sidecar / reverse proxy / config, or filed upstream.
