# omcgitea Design Document R7 — Sidecar-ified Architecture

> Version: R7 | Date: 2026-05-07 | Status: **landed** — this is the deployed topology
> This document is authoritative for the delivery and persistence layers (mini-router sidecar,
> secret-service, MySQL events store, ACP over unix socket). The single-instance router,
> `docker exec` ACP and SQLite `router.db` it replaced have been **removed** from `DESIGN.md` /
> `INTERFACE.md` rather than left standing alongside it; §1 below keeps only the reasoning.
> Invariants it does not touch: REQUIREMENTS.md §1–§4, §5.1, §5.5, §6; UEM.md; TEAMCONFIG.md (see §13).
> Companion: `REQUIREMENTS.md`, `DESIGN.md`, `INTERFACE.md`, `UEM.md`

> "hermes-agent container" / "Hermes" below means a generic ACP agent container. The default
> `AGENT_KIND=claude` uses `@agentclientprotocol/claude-agent-acp`; the Hermes path is dormant.
> mini-router and the ACP wire protocol are unchanged either way.

---

## 1. Background and Problem

### 1.1 Explosion Radius of the Pre-R7 Architecture

The architecture R7 replaced was a **single-instance centralized router**:

- 1 `omcgitea-router` container (TS / Node 20+), located in the `router/` subdirectory
- Holds N ACP stdio long connections (one per agent `docker exec -i <agent> python -m acp_adapter.entry`)
- Holds N SSE long connections (one per agent `/user/events`)
- Holds N REST cursor pulls
- All state written to one `router.db` (SQLite WAL)
- Depends on `/var/run/docker.sock` to `docker exec`

**Explosion radius = N**: one router process death, all N agents lose connection simultaneously.

### 1.2 09:18 Incident (production-equivalent dev measured)

At 09:18 on 2026-05-07, on the dev profile it was observed:

1. Hermes `acp_adapter.entry` in one turn wrote a `WARNING: ...` log line to stdout
   (from some unsuppressed Python warning upstream)
2. The `@agentclientprotocol/sdk` stdio JSON-RPC parser on the router side threw on `JSON.parse` of that line
3. The exception was not caught at the dispatcher boundary, event loop threw upward
4. router process did not crash (systemd-style restart did not trigger either), but the ACP channel went completely silent
5. Within **6 hours** 10 agents did not respond to any new events
6. SSE / cursor were still running, events table still ingesting into `pending`, but no one consumed them

**Conclusion**: single-instance router amplified "one stdio parse exception" into **full team halted for 6h**.
The single point of failure is not just "process crash", but "process half-dead" — harder to spot than a crash (no docker restart signal).

### 1.3 Byproduct Problems

- **Horizontal scaling ceiling**: a single Node process holding 300+ stdio + SSE + REST connections = unrealistic
- **`/var/run/docker.sock` hard dependency**: router container must have host docker control;
  violates "principle of least privilege", and cannot be directly replicated on k8s
- **SQLite single write**: all agents writing the same `router.db`, concurrent contention + backup restore is non-trivial
- **Observability single point**: `/metrics` can only aggregate one copy, cannot per-agent isolated alert

### 1.4 Decision

Give up centralized router, rebuild as **per-agent sidecar** mode: each hermes-agent has its own
mini-router sidecar container; event persistence migrates to central MySQL; token distribution extracted into an independent
secret-service. One agent's sidecar dying only affects that agent.

---

## 2. Goals

| # | Goal | Metric |
|---|---|---|
| G1 | **per-agent fault isolation** | Any crash of a single agent's sidecar/hermes, the other N−1 agents unaffected |
| G2 | **Horizontal scale to 300+ agents** | sidecar pod is docker compose service template, add an agent = add a pair of containers; no central bottleneck |
| G3 | **No dependence on `/var/run/docker.sock`** | All inter-process communication through unix socket / TCP, sidecar does not mount docker.sock |
| G4 | **events persistent** | Central MySQL, unified backup; schema supports complete retry protocol |
| G5 | **Observability per-agent sliced** | Each sidecar independent `/metrics`; service discovery aggregation, slice alerts by `agent` label |

---

## 3. Overall Architecture

```
┌────────────────────────── host machine omcgitea/ ──────────────────────┐
│                                                                        │
│  .claude-team-data/<profile>/                                          │
│   ├─ gitea/        (Gitea data)                                        │
│   ├─ tokens/       (admin/agent token + pw; secret-service read source)│
│   ├─ hermes/<agent>/                                                   │
│   ├─ sidecar/<agent>/  (sidecar cursor cache / temp state; not authoritative)│
│   └─ mysql/        (events central storage)                            │
│                                                                        │
└────┬───────────────────────────────────────────────────────────────────┘
     │
┌────▼───────────┬──────────────┬──────────────┬─────────────────────┐
│  gitea         │ nginx-edge   │ act-runner   │ bootstrap (one-time)│
│  :3000         │ :28081       │              │                     │
│  (HA: prod can │              │              │                     │
│   dual-instance│              │              │                     │
│   + shared     │              │              │                     │
│   MySQL/Redis) │              │              │                     │
└────────────────┴──────────────┴──────────────┴─────────────────────┘
     │                                              │
     │                                ┌─────────────▼──────────────┐
     │                                │ secret-service             │
     │                                │ :8650 (Python, ~80 LOC)    │
     │                                │ GET /tokens/<agent>        │
     │                                └─────────────┬──────────────┘
     │                                              │
     │                                ┌─────────────▼──────────────┐
     │                                │ mysql :3306                │
     │                                │ events table (unique center)│
     │                                │ (prod: external RDS)        │
     │                                └─────────────▲──────────────┘
     │                                              │
     │   ┌──────────── agent-pod-1 ──────────────┐  │
     │   │ ┌──────────────────┐  ┌─────────────┐ │  │
     ├──▶│ │ mini-router-1    │  │ hermes-1    │ │  │
     │   │ │ (TS, sidecar)     │  │ (upstream   │ │  │
     │   │ │                   │  │  unchanged) │ │  │
     │   │ │  - SSE+pull       │  │  ┌────────┐ │ │  │
     │   │ │  - dispatch       │  │  │socat   │ │ │  │
     │   │ │  - retry sweep    │  │  │bridge  │ │ │  │
     │   │ │  - /metrics:8645  │  │  │(in-fg) │ │ │  │
     │   │ │  ─unix sock──────┼──┼─▶│fork acp│ │ │  │
     │   │ └──────────────────┘  │  │_adapter│ │ │  │
     │   │       │ MySQL          │  │.entry  │ │ │  │
     │   │       └────────────────┼──┴────────┘ │ │  │
     │   │                        └─────────────┘ │  │
     │   │  shared volume: emptyDir → /var/run/acp│  │
     │   │  (sidecar / hermes same compose group) │  │
     │   └────────────────────────────────────────┘  │
     │                                              │
     │   ┌──────────── agent-pod-2 ──────────────┐  │
     ├──▶│  …same shape…                          │──┘
     │   └────────────────────────────────────────┘
     │   …
     │   ┌──────────── agent-pod-N ──────────────┐
     └──▶│  …same shape…                          │
         └────────────────────────────────────────┘
```

**Key topology**:

- Central components (gitea / nginx-edge / act-runner / bootstrap / mysql / secret-service) = **shared singletons**
- agent-pod = **(mini-router sidecar + hermes container)** pair, expressed in docker-compose as two services
  + shared network (network_mode: "service:hermes-N") + shared emptyDir volume
- The "pod" concept on docker compose is emulated by **shared net ns + shared volume**, on k8s is a real Pod
- HA option: prod recommended Gitea dual-instance (shared MySQL + Redis session + S3 attachment),
  this design is independent of the number of Gitea instances; mini-router only sees one service name `gitea`

---

## 4. Components

### 4.1 mini-router (per-agent sidecar)

| Dimension | Value |
|---|---|
| Implementation | TypeScript / Node 20+, in `mini-router/` |
| Size | ~600 LOC (no multi-agent fan-out, no docker exec, no SQLite; MySQL client instead) |
| Image | `omcgitea-mini-router:local` |
| Single-container instances | **1 per agent** (docker-compose service `mini-router-<n>`) |
| Ports | `:8645/metrics` + `:8645/health` (in-container; prom pulled via service discovery) |
| Required env | `AGENT_NAME` / `GITEA_BASE_URL` / `MYSQL_DSN` / `SECRET_SERVICE_URL` / `SECRET_SERVICE_AUTH` |
| Must mount | shared emptyDir → `/var/run/acp` (shared with same-pod hermes container, holds unix socket) |
| Do not mount | `/var/run/docker.sock` (design explicitly forbidden) |
| restart | `unless-stopped` |

Responsibilities (see §8 internal loop for details):

1. boot: pull this agent's token from secret-service; connect MySQL; connect ACP unix socket; start SSE
2. SSE wake → REST `pollOnce` → write MySQL (`pending`)
3. dispatcher: scan this agent's `pending`, merge into batch → ACP `prompt` → mark `sent`/`failed`
4. retry sweeper: scan `failed` / `retrying` and `next_retry_at <= now` → resend
5. metrics: expose Prometheus text

### 4.2 secret-service

| Dimension | Value |
|---|---|
| Implementation | Python 3.12 stdlib `http.server`, ~80 LOC |
| Image | `omcgitea-secret-service:local` |
| Ports | `:8650` (only within docker network) |
| Mount | `.claude-team-data/<profile>/tokens/` → `/data/tokens` (ro) |
| Required env | `INTERNAL_AUTH_SECRET` (shared secret; compose injects from `.env.<profile>`; bootstrap writes) |

Interface (see §7 for details):

- `GET /tokens/<agent>` → 200 `text/plain` token string; requires `X-Internal-Auth: <secret>`
- `POST /tokens/<agent>` → write/replace; admin-only (same secret, but only bootstrap calls)
- `GET /healthz` → 200 `ok`

Token file hierarchy is completely consistent with current state (`/data/tokens/agent-<name>.token`), for smooth migration.

### 4.3 ACP bridge (socat, **located inside hermes container**)

> ⚠️ This section explicitly rejects the "socat runs in sidecar" scheme. Reason: once socat `EXEC`s a
> `python -m acp_adapter.entry`, that subprocess must **be in the same container as Hermes** — it depends on
> `/opt/hermes/.venv` Python virtualenv, `HERMES_HOME=/opt/data` data volume, Hermes
> package import path. Moving entry from hermes container to sidecar container violates "do not touch upstream".

**Final scheme**: bridge runs as a second process **inside the hermes container**.

- hermes container entrypoint changed to wrapper script (**glue-layer new script**, **does not modify upstream hermes**):
  ```sh
  #!/bin/sh
  # docker/hermes-agent/acp-bridge-entrypoint.sh
  socat UNIX-LISTEN:/var/run/acp/agent.sock,fork,unlink-early,mode=0660 \
        EXEC:"/opt/hermes/.venv/bin/python -m acp_adapter.entry",pty,stderr &
  exec "$@"           # original Hermes default CMD (sleep infinity or upstream entrypoint)
  ```
- `/var/run/acp/` = emptyDir shared with sidecar (compose `volumes: ["acp-sock-<n>:/var/run/acp"]`,
  sidecar mounts with same name)
- Each time sidecar `connect("/var/run/acp/agent.sock")` → socat `fork` → a brand-new
  `acp_adapter.entry` subprocess, stdio connected to this connection
- mini-router treats unix socket as stdio (`net.Socket` replaces original stdio Reader/Writer)
- `acp_adapter.entry` is upstream code, **0 modifications**

Why not run a server-mode acp_adapter directly in hermes container: upstream `acp_adapter.entry`
only supports stdio. `socat ... EXEC` is the standard Unix means to adapt stdio to socket, not a
hack (man socat first paragraph is this usage).

### 4.4 mysql

| Dimension | dev | prod |
|---|---|---|
| Provider | docker compose service `mysql` | External MySQL / Aurora / RDS |
| Image | `mysql:8.4` | — |
| Mount | `../.claude-team-data/<profile>/mysql/` → `/var/lib/mysql` | — |
| Ports | Only docker network (`3306`) | Via VPC |
| Schema | Defined in §5; bootstrap runs DDL | DBA provides connection string; DDL same as bootstrap |
| Backup | dev not backed up, can `down` delete | RDS snapshot |

mini-router uses `mysql2` driver (Node), connection pool size=4. **The writes of a single agent cannot become
the bottleneck of central MySQL** (order: single-digit events per second, 300 agents total ~kQPS).

---

## 5. Events MySQL Schema

```sql
CREATE TABLE events (
  id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  dedup_key       VARCHAR(255)    NOT NULL,
  source          VARCHAR(64)     NOT NULL,
  agent           VARCHAR(128)    NOT NULL,
  payload         JSON            NOT NULL,
  state           ENUM('pending','sending','sent','failed','retrying')
                                  NOT NULL DEFAULT 'pending',
  attempts        INT             NOT NULL DEFAULT 0,
  created_at      BIGINT          NOT NULL,         -- epoch ms
  sent_at         BIGINT          NULL,
  acked_at        BIGINT          NULL,
  last_error      TEXT            NULL,
  batch_id        CHAR(36)        NULL,             -- events of the same batch share UUID
  next_retry_at   BIGINT          NULL,             -- epoch ms; retry sweeper scans this
  PRIMARY KEY (id),
  UNIQUE KEY uniq_dedup_agent (dedup_key, agent),
  KEY idx_agent_state_id (agent, state, id),        -- dispatcher takes pending
  KEY idx_state_retry (state, next_retry_at)        -- retry sweeper full-table scan
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE cursors (
  agent       VARCHAR(128) NOT NULL,
  source      VARCHAR(64)  NOT NULL,
  cursor      VARCHAR(64)  NULL,                    -- RFC3339 since
  updated_at  BIGINT       NOT NULL,
  PRIMARY KEY (agent, source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE acp_sessions (
  agent       VARCHAR(128) NOT NULL,
  session_id  VARCHAR(128) NOT NULL,
  created_at  BIGINT       NOT NULL,
  PRIMARY KEY (agent)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Key points:

- `(dedup_key, agent)` UNIQUE guarantees re-pull idempotence; equivalent to current SQLite single-agent uniqueness
- mini-router **always only WHERE `agent = $self`**, row-level isolation = process-level isolation
- `state='retrying'` is intermediate state, avoiding sweeper re-claiming the same row (once claimed immediately set to `retrying`)
- payload uses JSON column: MySQL 8 native support + facilitates `jq`-like query audit

---

## 6. Retry Protocol

```
backoff = [1s, 5s, 30s, 2m, 10m]
attempts ∈ [0, 5]
```

Transition rules (dispatcher / sweeper inside mini-router):

```
# dispatch once fails:
UPDATE events
   SET state         = 'failed',
       attempts      = attempts + 1,
       last_error    = ?,
       next_retry_at = CASE
         WHEN attempts + 1 >= 5 THEN NULL          -- terminal state, no more retry
         ELSE :now + backoff[attempts]
       END
 WHERE id = ? AND agent = :self;

# sweeper periodic task (every 30s):
SELECT id FROM events
 WHERE agent = :self
   AND state IN ('failed','retrying')
   AND next_retry_at IS NOT NULL
   AND next_retry_at <= :now
 LIMIT 16;

# claim:
UPDATE events
   SET state = 'retrying'
 WHERE id IN (...) AND state = 'failed' AND agent = :self;
# (CAS by state to prevent concurrency; mini-router itself has only one process, but safety)

# then take the same dispatch path as pending
```

**Explicit invariants**:

- `attempts >= 5` → `state='failed'` + `next_retry_at=NULL` → **permanent terminal state**, requires human
- `cancelled` (watchdog) retained as terminal state, **does not enter retry** (avoiding duplicate side effects)
- retry success → `state='sent'`, `attempts` retained as audit

---

## 7. secret-service Protocol

### 7.1 Endpoints

| Method | Path | Auth | Purpose | Response |
|---|---|---|---|---|
| GET | `/tokens/<agent>` | `X-Internal-Auth: <INTERNAL_AUTH_SECRET>` | sidecar pulls token at startup | 200 `text/plain`, body = token; 404 if not present; 401 auth failure |
| POST | `/tokens/<agent>` | `X-Internal-Auth` | bootstrap write/replace | 204 No Content; body = token bytes (content-type irrelevant) |
| GET | `/healthz` | None | liveness | 200 `ok` |

### 7.2 Storage

Agent names must match the complete ASCII name grammar (1–64 letters, digits,
dots, underscores or hyphens). Token paths must resolve inside the configured
token directory; a symlink to a file outside that directory is rejected.
Writes use a newly created, private temporary file before the atomic replace,
so an existing temporary-path symlink cannot redirect a token write. Startup
logs report the listening port without printing the token storage path.
Rejected requests close their HTTP connection so unread token bodies cannot
be interpreted as another request and copied into an HTTP parser error log.

- On disk: `/data/tokens/agent-<name>.token`, `0600`
- Same layout as current state, bootstrap writes then directly mounts to secret-service (M1 compatible)
- secret-service process **only reads** this directory; POST also only atomic-writes this directory

### 7.3 Authentication

- `INTERNAL_AUTH_SECRET` generated once by bootstrap (`openssl rand -hex 32`), dropped to
  `tokens/internal-auth.secret`
- compose reads from that file, injects as env into `secret-service` and `mini-router-*`
- Shared secret is simple enough: all callers within docker network; threat model = other
  containers on the same host mistakenly calling; no external exposure

### 7.4 sidecar-side Cache

mini-router does one GET at startup, caches in memory. **Does not poll**. Token rotation = restart sidecar.
Brief secret-service unavailability ≠ affects already-running sidecars (§10.4).

---

## 8. mini-router Internal Loop

### 8.1 Startup Sequence

```
1. Read env: AGENT_NAME, GITEA_BASE_URL, MYSQL_DSN, SECRET_SERVICE_URL, SECRET_SERVICE_AUTH
2. GET {SECRET_SERVICE_URL}/tokens/{AGENT_NAME}     → token (in-mem)
3. mysql.connect(MYSQL_DSN)                          → pool size=4
4. ensureSchema()                                    → CREATE TABLE IF NOT EXISTS
5. UPDATE events SET state='pending' WHERE agent=:self AND state='sending'
   (startup corpse scan: half-delivered rows left by last kill rolled back)
6. acpConnect()  ← connect /var/run/acp/agent.sock; retry until success
   - If acp_sessions(:self) has session_id → load_session
   - Otherwise new_session → INSERT acp_sessions
7. sseStart()     ← Gitea form login + GET /user/events
8. pollOnce()     ← catch up backlog once at startup
9. Enter main loop:
     wake = race([sseTrigger, retryTimer(30s), shutdown])
     on sseTrigger  → pollOnce(); dispatchPending()
     on retryTimer  → retrySweep();   dispatchPending()
```

### 8.2 dispatchPending

```
rows = SELECT * FROM events
        WHERE agent=:self AND state='pending'
        ORDER BY id ASC
        LIMIT 32
if rows.empty: return
batch_id = uuid()
UPDATE events SET state='sending', batch_id=:bid WHERE id IN (rows.ids) AND state='pending'
prompt = renderBatch(rows)
try:
    stopReason = acp.prompt({sessionId, prompt})  // also listens to sessionUpdate to refresh liveness
    UPDATE events SET state='sent', sent_at=:now WHERE batch_id=:bid
except CancelledByWatchdog:
    UPDATE events SET state='cancelled', last_error='watchdog 20min' WHERE batch_id=:bid
except AcpError as e:
    failOne(rows, str(e))   // see §6 retry
```

### 8.3 retry sweeper

Every 30s tick; logic see §6. Note **only scans this agent** (`agent=:self`).

### 8.4 SSE Health Monitoring

- heartbeat 60s no frame → reconnect (exponential backoff + jitter)
- 5 consecutive form-login failures → breaker lock 60s (following current `gitea_form_auth.ts`)
- metrics: `mini_router_sse_connected{agent}=0/1`, `mini_router_sse_last_frame_age_seconds`

---

## 9. ACP Reconnection

| Scenario | Behavior |
|---|---|
| Normal batch end | Connection preserved; next batch reuses |
| socket EOF (hermes restart / socat fork subprocess exit) | mini-router catches; exponential backoff (1s,2s,5s,10s,30s,60s cap) reconnect |
| After reconnect | `load_session(session_id)` → hermes upstream built-in `state.db` restores complete history |
| N consecutive (default 10) unable to connect | Mark metric `mini_router_acp_unhealthy{agent}=1`; keep retrying, **do not exit process** |

Due to the `socat ... fork` model, every mini-router connect gets a **brand new**
`acp_adapter.entry` subprocess, **stdio isolated**. This means:

- The "long ACP session" mini-router maintains is, in hermes process semantics, **multiple short stdio processes + load_session strung together**
- Upstream hermes loads history from `state.db` → behavior equivalent; user unaware
- Difference from the pre-R7 `docker exec -i` single long stdio: there, a stdio break required going through docker
  exec to pull new process from scratch, new scheme is socat auto fork, link is much shorter

---

## 10. Faults and Isolation

### 10.1 hermes container crash

- socket EOF → sidecar triggers §9 reconnect
- docker `restart: unless-stopped` pulls hermes up
- After new hermes comes up, socat forks new acp_adapter.entry → load_session restores
- **Impact scope = that agent itself**; other agent-pods completely independent

### 10.2 sidecar crash

- docker `restart: unless-stopped` pulls up
- Startup sequence §8.1 step 5 scans `sending` back to `pending`
- cursor in MySQL, not lost; missed SSE triggers filled by `pollOnce()` startup catch-up
- **Impact scope = that agent itself**

### 10.3 mysql crash

- All sidecar connections reset
- mini-router **must not crash because of this** (catches driver exception, retry connection + exponential backoff)
- Online SSE triggered ingestion cannot happen → temporarily store in memory ring buffer (default 256 rows/agent)
- After mysql recovery flush ring buffer (dedup by dedup_key unique constraint)
- Ring buffer full → drop earliest + count metric `mini_router_ringbuf_dropped_total`
- **Tradeoff**: mysql down for long = degrade to at-most-once (already at-most-once) +
  event loss in extreme cases. But central MySQL crash probability << process crash. Acceptable.

### 10.4 secret-service crash

- Already-running sidecars use in-memory token, **unaffected**
- Newly-started / restarted sidecars cannot pull token → wait + retry (startup sequence blocks)
- Does not cause any already-running agent to be disabled

### 10.5 Single sidecar exception enters panic loop

- docker restart backoff (compose default backoff)
- Other agents unaffected = G1 achieved
- alert triggered by prometheus per `up{job="mini-router",agent="..."}=0`

---

## 11. Observability

Each mini-router exposes Prometheus text at container-internal `:8645`:

| Metric | Type | Labels | Description |
|---|---|---|---|
| `mini_router_events_pending` | gauge | `{agent}` | Current pending row count |
| `mini_router_events_failed` | gauge | `{agent}` | Terminal failed (attempts≥5) row count |
| `mini_router_events_retrying` | gauge | `{agent}` | Rows to retry |
| `mini_router_sse_connected` | gauge | `{agent}` | 0/1 |
| `mini_router_sse_last_frame_age_seconds` | gauge | `{agent}` | heartbeat |
| `mini_router_acp_unhealthy` | gauge | `{agent}` | ACP reconnect failure N times |
| `mini_router_retry_attempts_total` | counter | `{agent}` | Cumulative retry count |
| `mini_router_dispatch_inflight_age_seconds` | gauge | `{agent}` | Seconds current batch has been in flight |
| `mini_router_dispatch_cancelled_total` | counter | `{agent}` | Cumulative watchdog cancels |
| `mini_router_ringbuf_dropped_total` | counter | `{agent}` | Dropped during mysql unavailability |

Aggregation:

- **dev**: prometheus.yml hardcodes `mini-router-1:8645 ... mini-router-N:8645` (manual list)
- **prod / k8s**: ServiceMonitor auto-discovery by label `app=mini-router`

---

## 12. Acceptance

### 12.1 Smoke

```bash
make up PROFILE=dev
# wait 60s
curl -s http://mini-router-1:8645/health   # ok
for i in 1..N; do
  curl -s http://mini-router-$i:8645/metrics \
    | grep -q 'mini_router_sse_connected.*} 1'
done
# all 1 = pass
```

### 12.2 Isolation

```bash
docker kill omcgitea-dev-hermes-3
# wait 5s
# Expected: mini-router-3 metrics shows acp reconnecting;
#           new events in events table with agent='agent3' stay pending;
#           agent1/agent2/agent4..N normally sent
docker start omcgitea-dev-hermes-3
# Expected: agent3 events subsequently dispatched (load_session restores)
```

### 12.3 Recovery

```bash
docker kill omcgitea-dev-mini-router-3
# (compose restart unless-stopped auto pulls up)
# Expected: within 5s sidecar restarts, corpse scans, resumes;
#           SSE events arriving during this period filled by pollOnce() after restart;
#           events.dedup_key deduplication guarantees no duplicate delivery
```

### 12.4 Bulk

Team config: 1 lead + 3 reviewer + 26 coder = 30 agents.

```
Script: bulk create 52 issues on omcgitea/test-bulk by lead → assign to coder
Expected: within 30 min ≥48 PRs merged complete
Observations:
  - No mini-router enters panic-loop
  - All mini-router_acp_unhealthy always = 0
  - events table failed rows ≤ 5% of total rows
  - No "full team halt" incident
```

---

## 13. Unchanged Parts

R7 **does not affect** the following scope:

- **Hermes agent upstream code**: `hermes-agent/` 0 changes, `acp_adapter.entry` 0 changes
- **MCP Gitea integration**: `gitea-mcp` binary assembly method, stdio startup, env injection completely unchanged
- **AGENTS.md template**: UEM v0.1 protocol contract, agent behavior convention unchanged
- **Bootstrap flow**: user/team/repo/branch-protection/closes-check steps
  fully retained; adds two new steps "fill token to secret-service" + "fill mysql schema"
- **UEM payload format**: `event_id / source / kind / summary / observed_at /
  target_agent / raw` and ACP `prompt[].text` rendering completely unchanged
- **Gitea configuration**: `AUTO_WATCH_ON_CHANGES=false`, unwatch, branch protection
  rules unchanged word for word
- **LLM integration contract**: conditions for `provider=anthropic / api_mode=anthropic_messages` hitting
  cache gate unchanged
- **Do-not-touch upstream principle**: this design strictly maintains "zero patch / zero fork"

R7 = **refactor delivery layer and persistence layer**, business semantics, agent behavior, external contract completely untouched.
