# Service event listeners

Translate organization activity into [`UEM`](../uem.ts) messages and store it
through [`EventStore`](../state.ts) before waking the dispatcher.

| Folder | Ingestion path |
|---|---|
| [gitea/](gitea/README.md) | Cookie-authenticated SSE wakeups trigger token-authenticated notification fetches |
| [mattermost/](mattermost/README.md) | Authenticated WebSocket events plus REST post catch-up after reconnects |

Each converter creates a stable event ID and preserves the raw payload beside
its prompt summary. MySQL deduplicates IDs per agent, allowing live and catch-up
paths to overlap. Gitea persists its notification watermark; Mattermost keeps
its catch-up timestamp in process memory and initially looks back ten minutes.
Both listeners reconnect with backoff and jitter.
