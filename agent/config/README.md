# Worker configuration

Runtime inputs consumed by [`entrypoint.sh`](../entrypoint.sh).

| File | Implementation |
|---|---|
| `mcp.json.tmpl` | Defines stdio Gitea, Mattermost and board MCP servers with environment placeholders |
| `copilot-deny-tools.json` | Lists MCP tool selectors denied and excluded from the advertised tool set |

The entrypoint renders the template to `/work/.mcp.json` with `envsubst`,
converts timeout values to numbers, and removes the board server when
`BOARD_SERVICE_URL` is unset. Each server runs through
[`mcp-notice-shim.cjs`](../../mini-router/mcp-notice-shim.cjs) so tool results
can carry DMs and new board gists. `${AGENT_NODE}` selects the private Node runtime.

Deny-list entries use `server(tool)` syntax. The entrypoint supplies both
Copilot permission-denial flags and the corresponding model-visible exclusions.
Native `task` and `list_agents` exclusions are configured in the entrypoint.
These files are strict JSON/template data; implementation notes belong here.
