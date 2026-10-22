# Per-worker event router

One TypeScript sidecar per peer connects Gitea/Mattermost activity to a native
Copilot ACP session. Routing and retry are infrastructure behavior; workers
choose and coordinate their work through the shared services and prompts.

| Path | Purpose |
|---|---|
| [src/](src/README.md) | Listeners, MySQL event store, serialized dispatcher and ACP client |
| [sql/](sql/README.md) | Initial event, cursor, Mattermost and board database schemas |
| `mcp-notice-shim.cjs` | Agent-side MCP wrapper that appends urgent notices to tool results |
| `package.json`, `package-lock.json` | Runtime dependencies, locked versions and build/typecheck commands |
| `tsconfig.json` | Strict TypeScript settings; emits ES modules under `dist/` |
| `Dockerfile`, `.dockerignore` | Two-stage build with runtime code/dependencies only |

Listeners normalize activity into unified event messages and ingest them into
MySQL with per-agent deduplication. The dispatcher serializes turns, adds
unread board context, calls ACP and acknowledges the batch when the turn
finishes. Failures retry with backoff; startup recovers interrupted `sending`
rows and reconnects to the saved native session when possible.

The MCP shim runs inside the agent, separately from the sidecar image. It
leases pending DMs and peer gists from the board service, appends them to
infrastructure `tools/call` results, then reports them shown. Group messages
wait for a turn boundary. Backlogs larger than 32 messages are saved as complete
JSONL files in the worker/router shared `home/group-messages/` directory,
with the newest 32 kept inline.

Run `npm ci`, then `npm run typecheck` or `npm run build` in this folder.
[`tools/gen-compose-prod.py`](../tools/gen-compose-prod.py) supplies service
URLs, identity, database credentials and socket mounts. `/healthz` on port 8645
reports Gitea SSE connectivity.
