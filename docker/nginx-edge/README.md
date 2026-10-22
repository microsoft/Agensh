# Edge proxy

Routes the profile's host-facing HTTP ports to shared repository and chat
services. Internal workers use service names directly.

| Path | Purpose |
|---|---|
| `nginx.conf` | Worker/connection settings, 100 MiB request limit and virtual-host includes |
| [conf.d/](conf.d/README.md) | Gitea and Mattermost upstream routes |

Compose mounts both paths read-only into the upstream Nginx image. Container
port 80 serves Gitea and port 81 serves Mattermost; profile variables determine
their host port mappings. Routes forward the original host/client headers.
Gitea disables buffering for SSE; Mattermost preserves WebSocket upgrades.
