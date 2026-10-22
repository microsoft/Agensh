# Initial MySQL schemas

Mounted read-only at `/docker-entrypoint-initdb.d` in the fleet's MySQL image.
Numbered files run in order when an empty MySQL data directory is initialized.

| File | Purpose |
|---|---|
| `01-events-schema.sql` | Durable event rows, delivery/retry indexes and per-agent source cursors in `omcgitea` |
| `02-mattermost-db.sql` | Separate `mattermost` database and grants for the shared application user |
| `03-board-schema.sql` | Append-only board gists, work labels, claim expiry and optional full detail |

[`EventStore.ensureSchema()`](../src/state.ts) also ensures event/cursor tables,
creates `agent_kv` for session IDs, and upgrades the batch/state index under a
database lock. The [board service](../../board-service/README.md) applies
compatibility columns and creates its shown-event ledger, pending-notice leases
and board cursors at startup. Editing a seed file alone does not migrate an
existing database.
