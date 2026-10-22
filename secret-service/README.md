# Internal token service

Small standard-library HTTP service that serves bootstrap-issued worker tokens
to mini-routers on the private Compose network.

| File | Purpose |
|---|---|
| `main.py` | Threaded HTTP server, internal-auth check and validated token-file lookup |
| `Dockerfile` | Python image; mounts are supplied by generated Compose |

`GET /healthz` returns `ok`. `GET /tokens/<agent>` requires `X-Internal-Auth`
matching `SECRET_SERVICE_INTERNAL_AUTH` and reads `agent-<agent>.token` from
`SECRET_SERVICE_TOKENS_DIR` (default `/data/tokens`). Names are limited to
1–64 letters, digits, dots, underscores or hyphens, and resolved paths must
stay inside that directory. Error responses close the HTTP connection.

The service listens on `SECRET_SERVICE_PORT` (default 8650), requires the auth
secret at startup, and receives the [bootstrap](../docker/bootstrap/README.md)
token directory as a read-only mount. Routers request their Gitea token and,
when chat is enabled, the corresponding `<agent>-mm` token.
