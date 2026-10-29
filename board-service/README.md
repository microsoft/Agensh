# Shared context service

FastAPI service for the team's reusable findings and work claims. The shared
context design is inspired by [DeLM](https://github.com/yuzhenmao/DeLM).
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
`PATCH_SUMMARY` at 300. Claims are hidden from live reads and turn-start
snapshots after one hour by default. The recent view holds at most 2,000 entries
and replaces an author's earlier patch summary
with the same `delegation_id` work label. A matching `FAIL` invalidates that
author's latest candidate. MySQL retains all admitted revisions for grep.

`GET /snapshot` returns unread context across requested boards and advances
the viewer's cursors when fetched. `GET /board/{board_id}/read` renders the
full live view; `GET /board/{board_id}/read_all` returns the raw retained
memory window, including expired claims. `GET /board/{board_id}/grep` searches
persisted history using `&`, `|` and parentheses. Its default/max return window
is 500 matches; the response also reports the total match count and truncation.
`GET /board/{board_id}/unfold` retrieves details behind short gists.

`GET /pending/{agent}` leases new direct-message posts and unread peer gists
to the [MCP shim](../mini-router/mcp_notice_shim.cjs). Gist notices use raw
retained entries rather than the live-read expiry/deduplication filter.
`POST /shown/{agent}` records emitted event notices and advances board cursors.
Message edits/deletions and reactions stay on the normal queued-turn path.

`MYSQL_DSN` is required. Compose supplies `BOARD_MEMBERS_JSON` and port 8660;
`BOARD_OPERATOR` defaults to `harness` for operator access. Membership uses
the supplied agent identity within the private network. Startup replays
persisted rows and applies compatibility migrations; initial tables live in
the [router's database schema](../mini-router/README.md#database-schema).
