# Gitea notifications

Repository activity reaches workers through Gitea's notification API.

| File | Purpose |
|---|---|
| `sse.ts` | Maintains `/user/events`, handles heartbeat/auth recovery and signals `notification-count` updates |
| `fetcher.ts` | Reads token-authenticated notification pages and computes a monotonic timestamp cursor |
| `listener.ts` | Fetches on startup/wakeup, ingests pages, persists the cursor and wakes dispatch |
| `notification.ts` | Builds event summaries and IDs from notification ID plus revision timestamp |

SSE uses browser-session cookies from [`gitea_form_auth.ts`](../../gitea_form_auth.ts);
REST uses the worker token. The SSE frame is a wakeup rather than the repository
event itself. A fetch keeps one `since` bound across up to 20 pages of 50 items
and advances the stored cursor after ingestion. A wakeup received during a
fetch is retained for the next pass.
