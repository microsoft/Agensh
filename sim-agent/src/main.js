#!/usr/bin/env node
/**
 * sim-agent — AGENT_KIND=sim entry point.
 *
 * Stands where claude-agent-acp stands: a stdio ACP agent spawned by
 * acp-bridge.py, one process per socket connection. It speaks the real ACP
 * protocol to the mini-router and calls the real MCP servers against real
 * Gitea / Mattermost / board. The only thing missing is the model.
 */
import { startAcpServer, log } from "./acp.js";
import { McpClient } from "./mcp.js";
import { SimPolicy } from "./policy.js";

const mcp = new McpClient();
const policy = new SimPolicy({ mcp, log });

// MCP servers come up in the background: the router's `initialize` is
// time-bounded (ACP_INIT_TIMEOUT_MS, 60s) and spawning four stdio servers can
// outlast that on a loaded host. Answering ACP immediately and letting the first
// turn wait on `ready` keeps a slow MCP start from looking like a dead agent.
const ready = mcp.start().catch((e) => {
  log(`mcp start failed (continuing with no tools): ${e?.stack ?? e}`);
  return mcp;
});

startAcpServer({
  onPrompt: async (text, emit) => {
    await ready;
    return policy.handlePrompt(text, emit);
  },
});

log(`started agent=${process.env.AGENT_NAME ?? "?"} turns=${process.env.PBENCH_SIM_TURNS ?? 4}`);

for (const sig of ["SIGTERM", "SIGINT"]) {
  process.on(sig, () => {
    mcp.stop();
    process.exit(0);
  });
}
