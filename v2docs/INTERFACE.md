# omcgitea Interface Contract v2

> "Hermes" below means a generic ACP agent. The default is `AGENT_KIND=claude`
> (`@agentclientprotocol/claude-agent-acp`); `AGENT_KIND=hermes` is a dormant compatibility
> option. The ACP wire contract itself does not distinguish kind. See CLAUDE.md.
>
> The parts of this contract that R7 superseded — SQLite events schema, ACP via `docker exec`,
> the `ROUTER_*` env block, the "router container alive" invariant — **have been removed rather
> than kept alongside**, and now cite [`DESIGN_R7_SIDECAR.md`](./DESIGN_R7_SIDECAR.md) instead:
> events table → MySQL (R7 §5), ACP path → unix socket via socat (R7 §4.3), single-instance
> router → per-agent mini-router sidecar with `AGENT_NAME / MYSQL_DSN / SECRET_SERVICE_URL /
> SECRET_SERVICE_AUTH` (R7 §4.1), token distribution → secret-service (R7 §4.2).
>
> Version: v2.3 | Date: 2026-04-28
> Companion: `REQUIREMENTS.md`, `DESIGN.md`, `DESIGN_R7_SIDECAR.md`

---

## 0. Key Decisions (finalized after measurement)

### 0.1 Gitea REST / SSE Dual Credentials

Measured on Gitea 1.22.6:

| Endpoint | Accepted credential | Rejected credential | Middleware |
|---|---|---|---|
| `/api/v1/notifications` (REST) | `Authorization: token <PAT>` / Basic / OAuth2 | session cookie → `401 token is required` | `reqToken` |
| `/user/events` (SSE) | `Cookie: i_like_gitea=<sess>` | `Authorization: token <PAT>` → `event: close, data: unauthorized` | web session |

**Conclusion**: router must hold dual credentials: PAT for REST, cookie for SSE. **Cannot be unified** — this is a side effect of Gitea's historical route tree split, following the "do not touch upstream" principle we do not work around.

### 0.2 What SSE Pushes

`/user/events` only pushes `notification-count` count:

```
event: notification-count
data: {"Count": 3}
```

**Does not push event body**. Body always goes through REST `/api/v1/notifications?since=<cursor>` pull.

### 0.3 Hermes Model Name Normalization

Hermes `agent/anthropic_adapter.py:normalize_model_name()` unconditionally `model.replace(".", "-")` on the `anthropic_messages` path. **Config uniformly writes hyphenated version**, e.g. `claude-opus-4-7`.

### 0.4 Hermes Prefix Cache Hit Conditions (M2-E.0)

`run_agent.py:744-747` cache gate: `provider == "anthropic"` + `api_mode == "anthropic_messages"`. **Cannot use `custom_providers`** — bypasses cache gate.

---

## 1. Communication Panorama

```
┌──────────────────┐                                ┌─────────────────────┐
│  Gitea (origin)  │                                │  mini-router-<X>    │
│  :3000           │                                │  (TS / Node 20+,    │
│                  │                                │   one per agent)    │
│  REST API ───────┼── PAT (Authorization: token) ─▶│ GiteaListener       │
│  /api/v1/        │   GET /api/v1/notifications    │  fetcher (REST pull)│
│  notifications   │   ?since=<cursor>              │                     │
│                  │                                │                     │
│  /user/events ═══┼══ Cookie (i_like_gitea) ══════▶│ GiteaSSE            │
│  (SSE)           │   GET /user/events             │  driver (trigger)   │
│                  │                                │                     │
│                  │                                │ events → MySQL      │
│                  │                                │ at-most-once        │
│                  │                                │  state machine      │
│                  │                                └────┬────────────────┘
│                  │                                     │ ACP JSON-RPC
│                  │                                     │ (unix socket,
│                  │                                     │  socat-forked)
│                  │                                ┌────▼────────────────┐
│                  │   stdio MCP child process     │  hermes-agent-<X>   │
│  REST API ◀──────┼── PAT (gitea-mcp -t stdio) ───┤  (ACP agent entry)  │
│                  │                                │  ┌───────────────┐  │
│                  │                                │  │stdio gitea-mcp│  │
│                  │   git push (token URL)         │  └───────────────┘  │
│                  │◀────────────────────────────────┤                     │
└──────────────────┘                                │  HTTPS POST         │
                                                    │  /v1/messages ──────┼──▶ Anthropic
                                                    └─────────────────────┘    Messages
                                                                               proxy
```

Four contracts:
- **§2** Agent → Gitea (write): MCP + git CLI
- **§3** Gitea → mini-router (read): REST PAT pull + SSE cookie trigger
- **§4** mini-router → Agent (delivery): ACP JSON-RPC
- **§5** Bootstrap: Gitea internal resource preparation contract
- **§6** Container/orchestration contract
- **§7** LLM inference contract

---

## 2. Hermes → Gitea Contract (write direction)

### 2.1 Medium

| Channel | Purpose |
|---|---|
| **stdio MCP subprocess** (`gitea-mcp -t stdio`) | Call Gitea REST API |
| **git CLI** (HTTPS + credential helper) | clone / commit / push |

### 2.2 Hermes-side MCP Configuration

File: `$HERMES_HOME/config.yaml` (in container `/opt/data/config.yaml`, rendered by entrypoint envsubst).

```yaml
mcp_servers:
  gitea:
    command: "/usr/local/bin/gitea-mcp"
    args: ["-t", "stdio"]
    env:
      GITEA_HOST: "http://gitea:3000"
      GITEA_ACCESS_TOKEN: "${GITEA_TOKEN}"
      GITEA_INSECURE: "true"
    timeout: 120
    connect_timeout: 60
```

### 2.3 Gitea MCP server

| Dimension | Value |
|---|---|
| Upstream | `https://gitea.com/gitea/gitea-mcp` |
| Binary | `gitea-mcp` |
| Docker image | `docker.gitea.com/gitea-mcp-server:latest` (multi-stage COPY source) |
| Startup | `gitea-mcp -t stdio` |
| Required env | `GITEA_HOST`, `GITEA_ACCESS_TOKEN`; optional `GITEA_INSECURE=true` |
| Assembly | hermes-agent Dockerfile multi-stage `COPY --from=docker.gitea.com/gitea-mcp-server:latest /usr/local/bin/gitea-mcp /usr/local/bin/gitea-mcp` |

Tools covered in actual runs: `list_repo_issues` / `get_issue_by_index` / `create_issue` / `edit_issue` / `create_issue_comment` / `list_repo_pull_requests` / `get_pull_request_by_index` / `create_pull_request` / `submit_pull_request_review` / `merge_pull_request`.

### 2.4 git CLI Credentials

Container entrypoint writes:

```
~/.git-credentials   (0600)
   http://<agent>:<token>@gitea:3000

git config --global credential.helper store
git config --global user.email "<agent>@omcgitea.local"
git config --global user.name "<agent>"
```

### 2.5 Gitea REST API Endpoints (used in actual runs)

All see [Gitea Swagger](https://docs.gitea.com/api/swagger):

| Operation | Endpoint |
|---|---|
| Create user | `POST /api/v1/admin/users` (admin Basic Auth) |
| Create token | `POST /api/v1/users/{username}/tokens` |
| Create repo | `POST /api/v1/admin/users/{user}/repos` |
| Notification pull | `GET /api/v1/notifications?since=<RFC3339>&all=&limit=` |
| Operate issue/PR | `/api/v1/repos/{o}/{r}/issues`, `/pulls`, `/comments`, `/reviews` |
| Branch protection | `POST /api/v1/repos/{o}/{r}/branch_protections` |
| Repo subscription | `PUT /api/v1/repos/{o}/{r}/subscription` body `{"subscribed":false}` (bootstrap unwatch) |

**No longer used**: `POST /api/v1/repos/{o}/{r}/hooks` (webhook creation). Bootstrap on startup reverse-calls `DELETE /api/v1/repos/{o}/{r}/hooks/{id}` to clean up leftover `hermes-agent-*:8644` hooks.

---

## 3. Gitea → mini-router Contract (read direction)

### 3.1 REST PAT pull

```
GET /api/v1/notifications?since=<RFC3339>&all=true&limit=50 HTTP/1.1
Host: gitea:3000
Authorization: token <PAT>
Accept: application/json
```

| Field | Description |
|---|---|
| **Credential** | PAT, required; scope `read:notification` mandatory |
| `since` | RFC3339 timestamp; first time null (omitted), subsequent = max(updated_at) in router cursor table |
| `all` | true includes read, default false |
| `limit` | Default 50; router default 50; beyond single page use `page` + `Link` header (not implemented for now, page≤50 is sufficient) |

**Response**: JSON array, sorted descending by `updated_at`. Failure 4xx/5xx throws typed error, cursor not advanced, retry on next wake.

### 3.2 SSE cookie trigger

`GiteaFormAuth` form login:

```
1. GET /user/login                        ← get i_like_gitea + _csrf cookies
2. POST /user/login                       ← form user_name/password/_csrf
   Cookie: i_like_gitea=<sess1>; _csrf=<csrf>
   Body:   user_name=<u>&password=<p>&_csrf=<csrf>
   Response: 303 See Other, Set-Cookie: i_like_gitea=<sess2>
3. Subsequent: Cookie: i_like_gitea=<sess2>
```

session cached 6h (`sessionTtlMs` default 21,600,000ms), on expiry `invalidate()` → next `ensureCredentials()` re-login. **Breaker**: 5 consecutive login failures (`maxConsecutiveFailures`) → lock 60s (`lockMs`), during which throws `AuthLockedError`, no longer accesses Gitea.

SSE long connection:

```
GET /user/events HTTP/1.1
Host: gitea:3000
Cookie: i_like_gitea=<sess>
Accept: text/event-stream

← (frames)
event: notification-count
data: {"Count": 3}

event: message
data: {"type":"close"}
```

router receives `notification-count` → `listener.trigger()` → short-circuits current wait → `pollOnce()`. Heartbeat watchdog: default 60s without any frame received → cancel connection, reconnect (exponential backoff + jitter).

### 3.3 events table (L2)

Schema lives in [`DESIGN_R7_SIDECAR.md`](./DESIGN_R7_SIDECAR.md) §5 (`events` / `cursors` /
`acp_sessions` in central MySQL). Two properties are contractual regardless of engine: the
`(dedup_key, agent)` unique constraint makes re-pull idempotent, and `ingest` + cursor
advancement commit in the same transaction.

### 3.4 Bidirectional Minimum Closed Loop (measured)

```
1. agent2 opens issue on omcgitea/test-sandbox with @agent1
2. Gitea drops notification (auto-skip doer == self)
3. agent1's sidecar SSE receives notification-count delta → triggers pollOnce
4. sidecar REST pull → ingest events (dedup_key=gitea:notif:<id>) → ACP prompt
5. agent1 LLM decides action; multi-prompt in same ACP session hits prefix cache
6. agent1 comments / opens PR / merges via MCP
```

---

## 4. mini-router → Agent Contract (delivery direction)

### 4.1 Medium: ACP JSON-RPC over unix socket

The sidecar connects `/var/run/acp/agent.sock`; `socat ... EXEC` inside the agent container forks
one `acp_adapter.entry` per connection. The sidecar drives it with `@agentclientprotocol/sdk`'s
`ClientSideConnection`, treating the socket as stdio. See
[`DESIGN_R7_SIDECAR.md`](./DESIGN_R7_SIDECAR.md) §4.3 / §9.

Session lifecycle, state machine, prompt template and watchdog semantics below are transport-
independent and hold unchanged.

### 4.2 Session Lifecycle

| Call | Timing | Description |
|---|---|---|
| `new_session(cwd=/opt/data)` | sidecar first run of an agent | Get session_id, drop to `acp_sessions` table |
| `load_session(session_id)` | sidecar restart / ACP process reconnect | Agent runtime automatically restores history from `state.db` |
| `prompt({sessionId, prompt})` | Each dispatcher tick delivers **a batch of events** | Long block; sidecar also listens to `sessionUpdate` to refresh activity timestamp |
| `cancel({sessionId})` | watchdog triggered (20min no update) | Interrupt current turn; `prompt` returns `stopReason="cancelled"` |

**Invariants**:
- Per agent **one** ACP long connection, **one** session_id
- Same agent **serial** (cache reuse prerequisite: session single-threaded)
- Different agents parallel
- Single batch `prompt` can carry N events merged text
- If ACP channel breaks reconnect immediately → `load_session(session_id)`, unfinished events continue to be taken from events table

### 4.3 prompt Template (sidecar render)

Single event (batch size = 1):

```
[notification] source=gitea kind={kind} summary={summary} url={details_url}
event_id={dedup_key}
You are agent {target_agent}. The environment just experienced the above change, please autonomously decide whether to respond and how to respond.
All gitea API operations go through gitea MCP tools.
If you have already handled the same event_id, you may ignore this entry.
```

Batch size > 1 (dispatcher merges all same-agent pending at once):

```
You have {N} new events (in time order):

--- event 1/N ---
[notification] source=... kind=... summary=...
event_id=...

--- event 2/N ---
...

Please holistically decide how to respond; if some event_id has already been handled, you may ignore that entry.
```

The prompt is an **environmental observation**, does not mandate the agent to reply — the agent decides autonomously.

### 4.4 State Machine (at-most-once + stuck self-healing)

```
pending → sending → sent
                 ↘ failed     (hard error: ACP connection exception / SDK throw)
                 ↘ cancelled  (20min no update, watchdog triggers cancel)
```

`sending`: stdio written, `prompt` not returned.

**Stuck self-healing (v2.3)**: dispatcher listens to the ACP `sessionUpdate` stream during `prompt()` and refreshes last activity timestamp. **Default 20 minutes with no update** → calls `connection.cancel(sessionId)`, marks **this batch** of sending events all as `cancelled` and writes log (agent / batch_id / events / how long since last update / trigger time), dispatcher **immediately takes next batch to continue delivery**.

Explicit tradeoffs:
- **session_id / agent process unchanged** → cache and history fully preserved
- **Do not auto-resend cancelled events** → avoids duplicate triggers (duplicate comments / PRs)
- **Subsequent pending events don't get the blame** → they weren't sent, not in cancelled scope
- **Do not notify humans** → log recorded, does not block delivery

### 4.5 /metrics Endpoint

Each sidecar embeds an HTTP server (default `:8645`, only within docker network):

```
GET /health   → 200 "ok\n"
GET /metrics  → 200 text/plain; version=0.0.4
```

The metric set is listed once in [`DESIGN_R7_SIDECAR.md`](./DESIGN_R7_SIDECAR.md) §11
(`mini_router_*`, all labelled `{agent}`).

---

## 5. Bootstrap Contract

### 5.1 Input

| Name | Required | Default | Description |
|---|---|---|---|
| `GITEA_HOST` | ✅ | `http://gitea:3000` | Gitea as seen from the bootstrap container |
| `GITEA_ADMIN_USER` | ✅ | `chairman` | admin username |
| `GITEA_ADMIN_PASSWORD` | ✅ | (provided by `.env.<profile>`) | admin password |
| `AGENTS` | ✅ | `agent1,agent2` | Comma-separated list of agent names |
| `REPOS` | ✅ | `test-sandbox` | Comma-separated list of repo names |
| `BOOTSTRAP_DATA_DIR` | ✅ | `/data` | In-container mount point; host-side bind from `../.claude-team-data/${PROFILE}/` |

### 5.2 Output (disk)

```
${DATA_DIR}/tokens/
├── admin.token              (0600)  chairman scoped token
├── agent-<name>.token       (0600)  per-agent PAT (router REST + hermes-agent use)
├── agent-<name>.password    (0600)  agent password (router form login + troubleshooting use)
└── .bootstrap-done          marker
```

**Deleted**: `webhook-<name>.secret` (webhook path taken down, bootstrap no longer generates). Leftover `webhook-*.secret` in old data directory cleaned up by `rm -f` at bootstrap startup.

### 5.3 Output (inside Gitea)

| Resource | Count | Description |
|---|---|---|
| User `chairman` | 1 | admin (created by `gitea-admin-init` container before bootstrap using `gitea admin user create`); **owner of `omcgitea` org** |
| Org `omcgitea` | 1 | **R5**: owner of all repos, contains `leads/reviewers/coders` three teams |
| User `<agent>` | N | Regular user + org member (belonging to corresponding team); **does not create repos** (REQUIREMENTS §4.3) |
| Token per user | 1 | scopes: `read:repository,read:issue,write:issue,read:user,read:notification` (agent token does not include `write:repository`) |
| Repo `omcgitea/<repo>` | M | Created under org, contains template first commit + `.gitea/workflows/closes-check.yml` |
| Branch protection | M | Each repo main branch: `required_approvals=1` + `approvals_whitelist_teams=["reviewers"]` + `merge_whitelist_teams=["leads","reviewers","coders"]` + `block_on_official_review_requests=true` + `enable_status_check=true status_check_contexts=["closes-issue-check"]` |
| Agent watch state | N×M | bootstrap explicit unwatch (`PUT /subscription {subscribed:false}`) |
| Webhook | **0** (from M2-E.1) | bootstrap reverse-**cleans up** leftover `hermes-agent-*:8644/webhooks/gitea` hooks |

### 5.4 Idempotence Contract

- Check `.bootstrap-done` → exists then exit 0 directly
- Even if `.bootstrap-done` missing, all create actions must be "if-not-exists":
  - User: `GET /admin/users/{name}` 200 → skip
  - Token: list existing by name comparison → don't reissue if exists
  - Repo: `GET /repos/{o}/{r}` 200 → skip push
  - Webhook cleanup: list + delete by url pattern, empty pass if none

### 5.5 Error Handling

Any API 4xx/5xx → exit non-zero + stderr, do not write `.bootstrap-done`.

---

## 6. Container and Orchestration Contract

### 6.1 mini-router Container Entry

One sidecar per agent. Image, ports, required env (`AGENT_NAME` / `GITEA_BASE_URL` /
`MYSQL_DSN` / `SECRET_SERVICE_URL` / `SECRET_SERVICE_AUTH`), the shared `/var/run/acp` mount and
the explicit prohibition on mounting `/var/run/docker.sock` are specified in
[`DESIGN_R7_SIDECAR.md`](./DESIGN_R7_SIDECAR.md) §4.1 and are not duplicated here.

The pre-R7 `ROUTER_*` env block (`ROUTER_AGENTS / ROUTER_DB_PATH / ROUTER_TOKENS_DIR /
ROUTER_PROJECT / ROUTER_USE_SUDO / ROUTER_GITEA_HOST_HEADER`) is gone.

### 6.2 hermes-agent Container Entry

| Dimension | Value |
|---|---|
| Base image | `FROM hermes-agent:local` (HERMES_HOME=`/opt/data`) |
| Extra installs | `gitea-mcp` binary (multi-stage COPY into `/usr/local/bin/`), git ca-certificates (one-line dependency in upstream Dockerfile) |
| Must mount | `../.claude-team-data/${PROFILE}/hermes/<agent>/` → `/opt/data` |
| Required env | `GITEA_HOST` / `AGENT_NAME` / `GITEA_TOKEN_FILE` / `ANTHROPIC_BASE_URL` / `ANTHROPIC_MODEL` / `ANTHROPIC_API_KEY` |
| Exposed port | **None** (webhook server taken down) |
| **Default CMD** | `["sleep", "infinity"]` (the ACP entry is forked per connection by socat) |
| restart | `unless-stopped` (agent main process dying auto-restarted by docker) |
| Network alias | **None** |

**Deleted**: `WEBHOOK_SECRET_FILE` env, entire `platforms.webhook` config section, `networks.default.aliases` block, `healthcheck`.

### 6.3 gitea-admin-init Container (one-time)

| Dimension | Value |
|---|---|
| Image | Same as `gitea` (`docker.gitea.com/gitea:1.22.6`) |
| restart | `"no"` |
| depends_on | `gitea: service_healthy` |
| user | `1000:1000` |
| volumes | `../.claude-team-data/${PROFILE}/gitea:/data` |
| entrypoint | inline shell: `gitea admin user list` checks existence, otherwise `gitea admin user create --admin` |
| email | `chairman@omcgitea.local` (cannot use `chairman@local`, Gitea rejects) |

### 6.4 Gitea Container

| Dimension | Value |
|---|---|
| Image | `docker.gitea.com/gitea:1.22.6` (pinned) |
| Mount | `../.claude-team-data/${PROFILE}/gitea/` → `/data` |
| Ports | **Not exposed externally**; only via `nginx-edge` reverse proxy. compose has commented-out `127.0.0.1:3000:3000` line for manual enable for local direct connection debugging |
| Health | `curl -fsS http://localhost:3000/api/v1/version` |

**Deleted**: `GITEA__webhook__ALLOWED_HOST_LIST` / `SKIP_TLS_VERIFY` / `DELIVER_TIMEOUT` three env vars (Gitea no longer sends any webhooks).

### 6.5 nginx-edge Container

| Dimension | Value |
|---|---|
| Image | `nginx:1.27-alpine` |
| Config | bind mount `docker/nginx-edge/{nginx.conf, conf.d/}` read-only to `/etc/nginx/` |
| Ports | `${EDGE_HTTP_PORT}:80` (**unique external port**; dev=28081 / prod=28080) |
| Routing | `Host: gitea.${EDGE_DOMAIN}` → `gitea:3000`; other Hosts → `444` |
| Health | `wget -qO- --header='Host: gitea.localhost' http://127.0.0.1/api/v1/version` |

### 6.6 docker-compose Contract

- All services share the default network (`omcgitea-<profile>_default` bridge)
- bind path uses `../.claude-team-data/${PROFILE}/...` (compose file located in `docker/` subdirectory)
- Image versions all pinned, `:latest` not allowed (except router / hermes-agent local build)
- Persistence all bind mount, named volume disabled
- bootstrap / gitea-admin-init `restart: "no"`, exit after run
- Other services `restart: unless-stopped`

### 6.7 Makefile Environment Isolation

```makefile
COMPOSE = env -u ANTHROPIC_BASE_URL -u ANTHROPIC_MODEL -u ANTHROPIC_API_KEY \
            -u AGENT_KIND -u COPILOT_PROVIDER_TYPE \
            -u HERMES_INFERENCE_PROVIDER -u HERMES_MODEL \
            -u GITEA_HOST -u GITEA_TOKEN \
            sudo -E docker compose -f $(COMPOSE_BASE) $(COMPOSE_OVERLAY) \
            --project-name omcgitea-$(PROFILE) \
            --env-file .env.$(PROFILE) --profile $(PROFILE)
```

Strips off host-only variables like `ANTHROPIC_BASE_URL=http://localhost:4141` from the user's `~/.bashrc`, preventing them from leaking into the container via `sudo -E`.

---

## 7. LLM Inference Contract

### 7.1 Hermes-side Configuration (M2-E.0 cache gate hit)

```yaml
model:
  default: "claude-opus-4-7"
  provider: "anthropic"             # required; hits run_agent.py:744-747 cache gate
  base_url: "${ANTHROPIC_BASE_URL}"
  api_mode: "anthropic_messages"

custom_providers: []                # must be empty; otherwise hermes takes custom path, bypasses cache gate
```

### 7.2 Model Name Constraints

- **Must be hyphenated**: Hermes `agent/anthropic_adapter.py:normalize_model_name()` unconditionally `model.replace(".", "-")` on `anthropic_messages` path
- Writing `claude-opus-4.7` will be sent as `claude-opus-4-7`
- Backend proxy must support hyphenated model names

### 7.3 Outbound HTTP Contract

```
POST <base_url>/v1/messages HTTP/1.1
x-api-key: <api_key>                     # sk-* shape uses x-api-key (_is_oauth_token detection)
                                         # OAuth token shape uses Authorization: Bearer
anthropic-version: 2023-06-01
Content-Type: application/json

{
  "model": "claude-opus-4-7",
  "messages": [...],
  "max_tokens": 128000,
  "system": "...",
  "tools": [...],
  "tool_choice": {...}
}
```

Proxy must support messages API streaming + tool calls, response must contain `cache_creation_input_tokens` / `cache_read_input_tokens` fields (M2-E.0 sanity check).

---

## 8. Invariants and Boundaries

### 8.1 Invariants (must hold after each `make up`)

- Gitea API `/api/v1/version` 200
- nginx-edge reverse-proxying Gitea responds `Host: gitea.${EDGE_DOMAIN}` 200
- Each agent container alive (`docker ps` running)
- Each `mini-router-<agent>` `/health` 200; `/metrics` shows `mini_router_sse_connected{agent}=1`
- `tokens/.bootstrap-done` exists
- `tokens/agent-<name>.{token,password}` complete for each agent
- **Per-repo `hermes-agent-*:8644/webhooks/gitea` hook count = 0**
- `acp_sessions` one row per agent; `cursors` one row per agent (cursor can be null = first time)

### 8.2 Boundaries (not stipulated by this contract)

- Agent-specific prompt engineering, skill content → Hermes team self-manages
- Business flows within Gitea (label / PR template / branch protection rules) → each team self-manages
- LLM selection / rate / cost / proxy form → deployer self-manages
