# Per-worker event router

One TypeScript sidecar per worker connects Gitea/Mattermost activity to the
selected harness over ACP. Routing and retry are infrastructure behavior; agents
choose and coordinate their work through the shared services and prompts.

| Path | Purpose |
|---|---|
| [src/](src/) | Listeners, MySQL event store, serialized dispatcher and ACP client |
| [sql/](sql/) | Initial event, cursor, Mattermost and board database schemas |
| `mcp_notice_shim.cjs` | Agent-side MCP wrapper that appends urgent notices to tool results |
| `package.json`, `package-lock.json` | Runtime dependencies, locked versions and build/typecheck commands |
| `tsconfig.json` | Strict TypeScript settings; emits ES modules under `dist/` |
| `Dockerfile`, `.dockerignore` | Two-stage build with runtime code/dependencies only |

Listeners normalize activity into unified event messages and ingest them into
MySQL with per-agent deduplication. The dispatcher serializes turns, adds
unread board context, calls ACP and acknowledges the batch when the turn
finishes. Failures retry with backoff; startup recovers interrupted `sending`
rows and reconnects to the saved native session when possible.

The MCP shim runs inside the agent, separately from the sidecar image. It
leases new direct-message posts and unread peer gists from the board service,
appends them to infrastructure `tools/call` results, then reports them shown.
The wrapper also enforces the shared MCP allowlist before advertising or
forwarding tools; it blocks unreviewed upstream additions by default.
Reviewed description overrides also remove instructions to call unavailable
tools while preserving their parameter schemas and results.
Group messages wait for a turn boundary. Delivered batches containing more than
32 group messages are saved as complete JSONL files in the worker/router shared
`home/group-messages/` directory, with the newest 32 kept inline.

For local development, use Node.js 20.10 or newer and run `npm ci`, then
`npm run typecheck` or `npm run build` in this folder. Docker builds supply
their own Node runtime.
[`tools/gen_compose_prod.py`](../tools/gen_compose_prod.py) supplies service
URLs, identity, database credentials and socket mounts. `/healthz` on port 8645
reports Gitea SSE connectivity.

## Runtime and event delivery

| Source | Responsibility |
|---|---|
| `src/main.ts` | Configuration, tokens, loop startup, retries and health endpoint |
| `src/state.ts` | Event states, deduplication, retry claims, cursors and session IDs |
| `src/dispatcher.ts` | Serialized delivery, shown-event reconciliation and board context |
| `src/acp_socket_channel.ts` | ACP handshake, session restoration and silence watchdog |
| `src/board_client.ts` | Board snapshots, read fallback and latest-own-gist lookup |
| `src/group_messages.ts` | Group-message classification and durable JSONL backlogs |
| `src/gitea_form_auth.ts` | Browser-form authentication and cached SSE cookies |
| `src/uem.ts`, `src/uem_render.ts` | Event shape and run-relative prompt summaries |
| `src/runtime.ts` | Error formatting and abort-aware delays |

Delivery follows `pending → sending → sent`. Failed attempts enter `failed`,
then `retrying` when due, with at most five recorded attempts. Startup returns
interrupted `sending` rows to `pending`. Normal delivery and retries share one
serialization chain. The ACP session ID is stored under
`acp_session_id:<harness>` in `agent_kv`; native rollouts remain in worker HOME.
`PBENCH_RUN_START_MS` aligns event timestamps across workers, otherwise router
startup supplies the time origin.

Gitea listeners under `src/listeners/gitea/` use cookie-authenticated
`/user/events` SSE as a wakeup for token-authenticated notification fetches.
A fetch keeps one `since` bound across up to 20 pages of 50 items, persists
the cursor after ingestion and retains wakeups received during a fetch.

Mattermost listeners under `src/listeners/mattermost/` combine WebSocket
events with staggered REST catch-up. New DM summaries preserve their complete
bodies on one line. Channel/group summaries cap the body at 200 characters,
while raw events retain full text. Edits, deletions and reactions wait for a
queued turn. Self-authored and system posts are filtered when identity is known.
The process-local catch-up cursor initially looks back ten minutes; cached
channels are reused, and REST catch-up does not replay reaction/deletion events.
Both listeners reconnect with backoff and use stable event IDs for deduplication.

## Database schema

MySQL mounts `sql/` at `/docker-entrypoint-initdb.d` and runs the numbered files
when initializing an empty data directory:

| File | Purpose |
|---|---|
| `sql/01_events_schema.sql` | Event rows, retry indexes and source cursors |
| `sql/02_mattermost_db.sql` | Mattermost database and application-user grants |
| `sql/03_board_schema.sql` | Board gists, work labels, claim expiry and full details |

`EventStore.ensureSchema()` also creates `agent_kv` and upgrades the batch/state
index under a database lock. The board service applies compatibility columns
and creates notice leases, shown-event records and board cursors at startup.
Editing a seed file alone does not migrate an existing database.
