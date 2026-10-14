/**
 * mcp.js — the MCP client half of the sim agent.
 *
 * A real stdio MCP client. It spawns servers from the RENDERED /work/.mcp.json
 * rather than a hardcoded list, which is what makes three things real instead of
 * assumed:
 *
 *   1. calls traverse mcp-notice-shim exactly as a live agent's do, so mid-turn
 *      DM / board-entry delivery is exercised rather than bypassed
 *   2. prune_mcp_servers applies — a profile with no BOARD_SERVICE_URL drops the
 *      board server and the sim has to cope, same as a real agent
 *   3. template drift breaks the sim, which is the early warning we want
 *
 * Tool NAMES are discovered via tools/list, never assumed: gitea-mcp and the
 * mattermost server are upstream binaries behind the CLAUDE.md veto line and
 * their surface is not ours to pin.
 *
 * Every failure is soft. An unreachable server yields `available:false` and its
 * calls report as failed tool calls — which is what a real agent does when its
 * MCP server is down, and keeps the ACP layer testable with no stack at all.
 */
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";

// Empty is absent: compose renders unset optional vars as "" and Number("") is 0,
// which would make every MCP request time out instantly.
const rawTimeout = String(process.env.SIM_MCP_TIMEOUT_MS ?? "").trim();
const REQUEST_TIMEOUT_MS = Number(rawTimeout) > 0 ? Number(rawTimeout) : 20_000;
const PROTOCOL_VERSION = "2024-11-05";

function log(...a) { process.stderr.write(`[sim-agent/mcp] ${a.join(" ")}\n`); }

class McpServer {
  constructor(name, spec) {
    this.name = name;
    this.spec = spec;
    this.proc = null;
    this.available = false;
    this.tools = [];
    this.buf = "";
    this.nextId = 1;
    this.pending = new Map();
  }

  async start() {
    const { command, args = [], env = {} } = this.spec;
    if (!command) { log(`${this.name}: no command in config`); return false; }
    try {
      this.proc = spawn(command, args, {
        stdio: ["pipe", "pipe", "pipe"],
        env: { ...process.env, ...env },
      });
    } catch (e) {
      log(`${this.name}: spawn failed: ${e?.message ?? e}`);
      return false;
    }
    this.proc.on("error", (e) => log(`${this.name}: process error ${e?.message ?? e}`));
    // A write to a server that has gone away fails asynchronously, as an 'error'
    // event on stdin (EPIPE); with no listener it would crash the whole agent.
    this.proc.stdin.on("error", (e) => {
      this.available = false;
      log(`${this.name}: stdin error ${e?.message ?? e}`);
    });
    this.proc.on("exit", (code) => {
      this.available = false;
      for (const { reject } of this.pending.values()) reject(new Error(`${this.name} exited rc=${code}`));
      this.pending.clear();
    });
    // Upstream servers log freely on stderr; keep it out of our protocol path.
    this.proc.stderr.on("data", () => {});
    // Decoded as one stream, so a multibyte character split across chunks survives.
    this.proc.stdout.setEncoding("utf8");
    this.proc.stdout.on("data", (c) => this.#onData(c));

    try {
      await this.request("initialize", {
        protocolVersion: PROTOCOL_VERSION,
        capabilities: {},
        clientInfo: { name: "omcgitea-sim-agent", version: "0.1.0" },
      });
      this.notify("notifications/initialized");
      const listed = await this.request("tools/list", {});
      this.tools = Array.isArray(listed?.tools) ? listed.tools : [];
      this.available = true;
      log(`${this.name}: ready, ${this.tools.length} tools`);
      return true;
    } catch (e) {
      log(`${this.name}: handshake failed: ${e?.message ?? e}`);
      this.available = false;
      return false;
    }
  }

  #onData(chunk) {
    this.buf += chunk;
    const lines = this.buf.split("\n");
    this.buf = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.trim()) continue;
      let msg;
      try { msg = JSON.parse(line); } catch { continue; }
      if (msg.id === undefined) continue; // server notification; nothing subscribes
      const p = this.pending.get(msg.id);
      if (!p) continue;
      this.pending.delete(msg.id);
      if (msg.error) p.reject(new Error(msg.error.message ?? "mcp error"));
      else p.resolve(msg.result);
    }
  }

  notify(method, params) {
    try { this.proc?.stdin.write(JSON.stringify({ jsonrpc: "2.0", method, params }) + "\n"); }
    catch { /* server gone; the next request reports it */ }
  }

  request(method, params) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`${this.name}.${method} timed out after ${REQUEST_TIMEOUT_MS}ms`));
      }, REQUEST_TIMEOUT_MS);
      this.pending.set(id, {
        resolve: (v) => { clearTimeout(timer); resolve(v); },
        reject: (e) => { clearTimeout(timer); reject(e); },
      });
      try {
        this.proc.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
      } catch (e) {
        this.pending.delete(id);
        clearTimeout(timer);
        reject(e);
      }
    });
  }

  /** First tool whose name matches any of `candidates` (exact, then substring). */
  findTool(candidates) {
    const names = this.tools.map((t) => t.name);
    for (const c of candidates) if (names.includes(c)) return c;
    for (const c of candidates) {
      const hit = names.find((n) => n.includes(c));
      if (hit) return hit;
    }
    return null;
  }

  stop() { try { this.proc?.kill("SIGTERM"); } catch { /* */ } }
}

export class McpClient {
  constructor(configPath) {
    const fromEnv = String(process.env.SIM_MCP_CONFIG ?? "").trim();
    this.configPath = configPath ?? (fromEnv || "/work/.mcp.json");
    this.servers = new Map();
  }

  async start() {
    let cfg;
    try {
      cfg = JSON.parse(readFileSync(this.configPath, "utf8"));
    } catch (e) {
      // No rendered config (unit test, or a profile that pruned everything).
      // Not fatal: calls become failed tool calls, which is a real agent's
      // behaviour when its MCP servers are down.
      log(`no mcp config at ${this.configPath} (${e?.code ?? e?.message}); running with no tools`);
      return this;
    }
    const specs = cfg.mcpServers ?? {};
    // Serially, not in parallel: 128 agents each spawning 4 servers at once
    // hits the slice TasksMax and strands agents.
    for (const [name, spec] of Object.entries(specs)) {
      if (name === "playwright") continue; // a browser is not part of any sim surface
      const s = new McpServer(name, spec);
      await s.start();
      this.servers.set(name, s);
    }
    return this;
  }

  server(name) { return this.servers.get(name) ?? null; }
  isAvailable(name) { return Boolean(this.servers.get(name)?.available); }

  /**
   * Call `candidates[0]` (or the first that exists) on `serverName`.
   * Never throws — returns {ok, text} so the policy can report a failed tool
   * call and keep the turn going.
   */
  async call(serverName, candidates, args) {
    const s = this.servers.get(serverName);
    if (!s || !s.available) return { ok: false, text: `${serverName} unavailable` };
    const tool = s.findTool(candidates);
    if (!tool) return { ok: false, text: `${serverName}: no tool matching ${candidates.join("|")}` };
    try {
      const res = await s.request("tools/call", { name: tool, arguments: args });
      const text = (res?.content ?? [])
        .map((c) => (typeof c?.text === "string" ? c.text : ""))
        .join("\n")
        .trim();
      return { ok: !res?.isError, text, tool };
    } catch (e) {
      return { ok: false, text: `${tool}: ${e?.message ?? e}`, tool };
    }
  }

  stop() { for (const s of this.servers.values()) s.stop(); }
}
