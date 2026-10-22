# Agent runtime

Builds and supervises one peer's native Copilot harness. The router supplies
events over ACP; the [worker prompt](../prompts/README.md) supplies the cooperation
loop described in [the report](../agensh.pdf).

| Path | Purpose |
|---|---|
| `Dockerfile.base` | Caches the upstream Gitea MCP binary in an artifact image |
| `Dockerfile` | Extends a task's v6 cleanroom with private Node, pinned Copilot and MCP tools |
| `entrypoint.sh` | Installs credentials, renders instructions/config, checks SQLite locking and starts the bridge |
| `acp-bridge.py` | Serves `/var/run/acp/agent.sock`, starts the non-root ACP child and handles cancellation |
| `archive.py` | Saves HOME/workspace state and validates shutdown archives before cleanup |
| [config/](config/README.md) | MCP server template and tool exclusions |

The root supervisor launches Copilot as UID/GID 10000. Persistent HOME lives
under `/opt/data/home`; the workspace is `/work`. The reference executable is
mounted separately so the child can run it without reading its bytes. Node is
installed under `/opt/agentrt` to preserve the task's existing toolchain.

The bridge serializes connections and lets active prompts cancel before
stopping child processes. Shutdown writes a private
`shutdown/<boot-id>/state.tar.gz` containing HOME and the complete workspace,
including Git and ignored files. A manifest becomes complete only after the
archive is sealed and its size/checksum recorded. The launcher checks these
manifests before automatic cleanup.

Build `Dockerfile` from the repository root, or use
[`scripts/pbench_build_pertask_images.sh`](../scripts/pbench_build_pertask_images.sh).
The [generated Compose stack](../tools/README.md) also mounts prompts, config,
the bridge, archive helper and MCP adapters from the checkout.
