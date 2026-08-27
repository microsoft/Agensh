/**
 * ACPSocketChannel stress tests (R7).
 *
 * 真 unix socket 上的并发 / 重连 / 大消息 / 高频压测。
 * 这是 sidecar 通信机制必须扛住的场景：
 *   1. 单 channel 顺序大量 prompt (1000 次) — 验证不漏
 *   2. 重连风暴 — server 反复 close, channel 必须每次重连成功
 *   3. 大 prompt body (1MB) — 验证 ndjson framing 不被切断
 *   4. 多 channel 对同一 server 并发 — 验证 socat fork-equivalent 隔离
 */
import { afterEach, describe, expect, it } from "vitest";
import { createServer, type Server, type Socket } from "node:net";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ACPSocketChannel } from "../../mini-router/src/acp_socket_channel.ts";
import type { UEM } from "../../mini-router/src/uem.ts";

interface JsonRpcMsg { jsonrpc: "2.0"; id?: number | string; method?: string; params?: unknown; result?: unknown; error?: unknown; }

class StressServer {
  server: Server;
  socketPath: string;
  totalPrompts = 0;
  totalConnections = 0;
  closeAfterPromptsPerConn = 0;

  constructor() {
    const dir = mkdtempSync(join(tmpdir(), "acp-stress-"));
    this.socketPath = join(dir, "agent.sock");
    this.server = createServer((sock) => this.handle(sock));
  }
  async start() { return new Promise<void>((res) => this.server.listen(this.socketPath, () => res())); }
  async stop() { return new Promise<void>((res) => this.server.close(() => res())); }

  private handle(sock: Socket): void {
    this.totalConnections++;
    let buf = "";
    let promptsThisConn = 0;
    const send = (m: JsonRpcMsg) => sock.write(JSON.stringify(m) + "\n");
    sock.on("data", (chunk) => {
      buf += chunk.toString("utf8");
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.trim()) continue;
        let msg: JsonRpcMsg;
        try { msg = JSON.parse(line); } catch { continue; }
        if (msg.method === "initialize") {
          send({
            jsonrpc: "2.0", id: msg.id,
            result: {
              protocolVersion: 1,
              agentCapabilities: { loadSession: true, promptCapabilities: { audio: false, embeddedContext: false, image: false, meta: false }, mcpCapabilities: { http: false, sse: false } },
              authMethods: [],
            },
          });
        } else if (msg.method === "session/new") {
          send({ jsonrpc: "2.0", id: msg.id, result: { sessionId: `sess-${this.totalConnections}`, modes: null } });
        } else if (msg.method === "session/load") {
          send({ jsonrpc: "2.0", id: msg.id, result: { modes: null } });
        } else if (msg.method === "session/prompt") {
          this.totalPrompts++;
          promptsThisConn++;
          send({ jsonrpc: "2.0", id: msg.id, result: { stopReason: "end_turn" } });
          if (this.closeAfterPromptsPerConn && promptsThisConn >= this.closeAfterPromptsPerConn) {
            setImmediate(() => sock.end());
          }
        }
      }
    });
    sock.on("error", () => {});
  }
}

function uem(idx: number, body = "x"): UEM {
  return {
    event_id: `stress:${idx}`, source: "test", target_agent: "a",
    kind: "test", summary: body.slice(0, 100), observed_at: idx, raw: { body },
  };
}

let server: StressServer;
const channels: ACPSocketChannel[] = [];

afterEach(async () => {
  for (const c of channels.splice(0)) await c.close();
  await server?.stop();
  try { rmSync(server?.socketPath ?? "", { force: true }); } catch { /* */ }
});

describe("ACPSocketChannel stress (R7)", () => {
  it("sequential 1000 prompts on one channel — no drops, no hangs", async () => {
    server = new StressServer();
    await server.start();
    const ch = new ACPSocketChannel({ socketPath: server.socketPath, cwd: "/work", onLog: () => {} });
    channels.push(ch);
    const t0 = Date.now();
    for (let i = 0; i < 1000; i++) {
      const r = await ch.prompt(uem(i));
      expect(r.stopReason).toBe("end_turn");
    }
    const elapsed = Date.now() - t0;
    expect(server.totalPrompts).toBe(1000);
    expect(server.totalConnections).toBe(1); // single long-lived
    // eslint-disable-next-line no-console
    console.log(`[acp-stress seq] 1000 prompts in ${elapsed}ms (${Math.floor(1000 / (elapsed / 1000))}/s)`);
    expect(elapsed).toBeLessThan(15_000);
  }, 30_000);

  it("reconnect storm: server closes every 5 prompts, channel survives 100 prompts", async () => {
    server = new StressServer();
    server.closeAfterPromptsPerConn = 5;
    await server.start();
    const ch = new ACPSocketChannel({ socketPath: server.socketPath, cwd: "/work", onLog: () => {} });
    channels.push(ch);
    let succeeded = 0;
    let failed = 0;
    for (let i = 0; i < 100; i++) {
      try {
        const r = await ch.prompt(uem(i));
        expect(r.stopReason).toBe("end_turn");
        succeeded++;
      } catch {
        failed++;
        // small delay to let close handler propagate before next attempt
        await new Promise((r) => setTimeout(r, 50));
      }
    }
    // Most prompts should succeed; some may fail at the exact close moment.
    // Connections should equal ceil(100/5) ± a few for failed/retried prompts.
    expect(succeeded).toBeGreaterThan(80);
    expect(server.totalConnections).toBeGreaterThanOrEqual(15);
    // eslint-disable-next-line no-console
    console.log(`[acp-stress reconnect] 100 prompts: ${succeeded} ok, ${failed} fail, ${server.totalConnections} reconnects`);
  }, 30_000);

  it("large body: 1MB prompt body round-trips without truncation", async () => {
    server = new StressServer();
    await server.start();
    const ch = new ACPSocketChannel({ socketPath: server.socketPath, cwd: "/work", onLog: () => {} });
    channels.push(ch);
    const big = "A".repeat(1024 * 1024); // 1 MB body
    const r = await ch.prompt(uem(1, big));
    expect(r.stopReason).toBe("end_turn");
    expect(server.totalPrompts).toBe(1);
  }, 30_000);

  it("multiple independent channels concurrent on same server (sidecar fork model)", async () => {
    server = new StressServer();
    await server.start();
    const N = 10;
    for (let i = 0; i < N; i++) {
      channels.push(new ACPSocketChannel({ socketPath: server.socketPath, cwd: "/work", onLog: () => {} }));
    }
    // Each channel does 50 prompts in parallel
    const t0 = Date.now();
    await Promise.all(channels.map(async (c, i) => {
      for (let j = 0; j < 50; j++) {
        const r = await c.prompt(uem(i * 100 + j));
        expect(r.stopReason).toBe("end_turn");
      }
    }));
    const elapsed = Date.now() - t0;
    expect(server.totalPrompts).toBe(N * 50);
    expect(server.totalConnections).toBe(N); // one per channel
    // eslint-disable-next-line no-console
    console.log(`[acp-stress parallel] ${N}×50 prompts in ${elapsed}ms`);
  }, 30_000);
});
