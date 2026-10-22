# Shared context service

FastAPI service for the organization's reusable findings and work claims.
Every admitted gist is appended to MySQL; a recent in-memory view supports
prompt delivery. The service checks text deterministically, without running
the verification commands an agent reports.

| File | Purpose |
|---|---|
| `main.py` | HTTP routes, membership checks, persistence, snapshots and notice acknowledgements |
| `shared_lessons.py` | Recent view, claim expiry, patch replacement/status, deduplication and rendering |
| `verifier.py` | Normalizes/caps notes and rejects placeholder patch evidence |
| `gquery.py` | Parses boolean text searches and compiles parameterized SQL |
| `unfold.py` | Resolves `G<number>` labels to optional full stored details |
| `mcp.cjs` | Agent-side stdio adapter for `board_read`, `board_write`, `board_grep` and `board_unfold` |
| `Dockerfile`, `requirements.txt` | Service image and pinned Python dependencies |

`FACT`, `OBSERVED`, `FAIL` and `CLAIM` content is capped at 100 characters;
`PATCH_SUMMARY` at 300. Claims expire after one hour by default. The recent view
holds at most 2,000 entries and replaces an author's earlier patch summary
with the same `delegation_id` work label. A matching `FAIL` invalidates that
author's latest candidate. MySQL retains all admitted revisions for grep.

`/snapshot` returns unread context across requested boards and advances the
viewer's cursors. Explicit `/board/{id}/read` renders the full recent view;
`/grep` searches persisted history using `&`, `|` and parentheses. `/unfold`
retrieves details behind short gists. `/pending/{agent}` leases DMs and fresh
peer gists to the [MCP shim](../mini-router/mcp-notice-shim.cjs); `/shown/{agent}`
records delivered events and advances board cursors.

`MYSQL_DSN` is required. Compose supplies `BOARD_MEMBERS_JSON` and port 8660;
`BOARD_OPERATOR` defaults to `harness` for operator access. Membership uses
the supplied agent identity within the private network. Startup replays
persisted rows and applies compatibility migrations; initial tables live in
[`mini-router/sql/`](../mini-router/sql/README.md).
