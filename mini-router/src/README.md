# Router implementation

The runtime connects service listeners to a durable queue and one ACP session.

| File/folder | Responsibility |
|---|---|
| `main.ts` | Environment parsing, token acquisition, loop startup, retry sweep and health endpoint |
| [listeners/](listeners/README.md) | Gitea SSE/REST and Mattermost WebSocket/REST ingestion |
| `state.ts` | MySQL schemas, deduplication, batch states, retry claims, source cursors and session IDs |
| `dispatcher.ts` | Serialized turns, shown-event reconciliation, board prefix and publication nudge |
| `acp_socket_channel.ts` | ACP handshake, native session restore, prompt delivery and optional silence watchdog |
| `board_client.ts` | Multi-board snapshots, read fallback and latest-own-gist lookup |
| `group_messages.ts` | Group-message classification, durable JSONL backlogs and exact-handle mention counts |
| `gitea_form_auth.ts` | Browser-form login and cached cookies for the SSE connection |
| `uem.ts`, `uem_render.ts` | Unified event shape and prompt summaries with run-relative timestamps |
| `runtime.ts` | Error formatting and abort-aware delays |

Delivery follows `pending → sending → sent`. A failed attempt enters `failed`,
then `retrying` when due; failed rows stop being eligible after five recorded
attempts. A restart returns `sending` rows to `pending`. Normal dispatch and
retries share one serialization chain, and the dispatcher retires DMs delivered through
the MCP shim's `shown` ledger. Recovery can redeliver interrupted activity.

The ACP session ID is stored in `agent_kv`, while Copilot's native session data
lives in the worker HOME. `PBENCH_RUN_START_MS` aligns event timestamps across
workers; without it, rendering uses router process startup.
