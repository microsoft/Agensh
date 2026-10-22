# Service routes

Virtual hosts included by [`nginx.conf`](../nginx.conf).

| File | Route and implementation |
|---|---|
| `gitea.conf` | Port 80 → `gitea:3000`; unbuffered HTTP/1.1 supports streaming events and Git traffic |
| `mattermost.conf` | Port 81 → `mattermost:8065`; forwards WebSocket upgrade headers and permits long-lived connections |

Both are default servers, so host-port routing works without a particular
hostname. Their Compose port mappings come from the generated profile; workers
access the internal upstream addresses directly.
