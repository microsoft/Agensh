# Mattermost messages

Chat activity is ingested live and recovered through REST after reconnects.

| File | Purpose |
|---|---|
| `ws.ts` | Opens `/api/v4/websocket`, authenticates, pings and reconnects with jitter |
| `listener.ts` | Filters events, ingests messages/reactions and performs staggered REST catch-up |
| `notification.ts` | Normalizes posts, edits, deletions and reactions; builds IDs and summaries |

Direct posts have kind `dm`; their complete text is retained in the summary
for mid-turn delivery. Channel/group summaries are capped at 200 characters,
with full post text kept in the raw event. Self-authored and system posts are
filtered where identity is available. REST catch-up resolves the current user
and team channels, then fetches posts after its process-local timestamp;
a fresh router starts with a ten-minute lookback.

The [dispatcher](../../dispatcher.ts) handles turn delivery. The
[MCP shim](../../../mcp-notice-shim.cjs) handles urgent DMs, while
[`group_messages.ts`](../../group_messages.ts) stores large channel backlogs.
