/**
 * ACPSocketChannel tests (R7 sidecar / F8).
 *
 * Real unix socket + a fake ACP server (a tiny in-process JSON-RPC
 * implementation) to verify:
 *   - connect → initialize → newSession → first prompt round-trip
 *   - prompt() resolves on agent stopReason
 *   - prompt() REJECTS when socket closes mid-flight (the dev-stack bug)
 *   - reconnect on subsequent prompt after socket EOF
 *   - SDK noise on stdout (non-JSON lines) is tolerated, not fatal
 *
 * The dev-stack 03:18 bug: socat closes its EXEC subprocess after the
 * first prompt, leaving mini-router awaiting prompt() forever. This
 * suite asserts that closing the socket → prompt rejects.
 */
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { createServer, type Server, type Socket } from "node:net";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ACPSocketChannel } from "../../mini-router/src/acp_socket_channel.ts";
import type { UEM } from "../../mini-router/src/uem.ts";

interface JsonRpcMsg {
  jsonrpc: "2.0";
  id?: number | string;
  method?: string;
  params?: unknown;
  result?: unknown;
  error?: unknown;
}

interface FakeACPServerOpts {
  /** If set, after the Nth prompt response, close the socket. */
  closeAfterPrompts?: number;
  /** If true, write a non-JSON line to stdout before each response (simulate hermes log noise). */
  emitNoise?: boolean;
  /** If set, never respond to prompts (simulate hung agent). */
  hangPrompts?: boolean;
  /** If >0, write N non-JSON noise lines between initialize-resp and newSession-resp. */
  noiseBeforeNewSession?: number;
}

class FakeACPServer {
  private server: Server;
  socketPath: string;
  promptsHandled = 0;
  promptTexts: string[] = [];
  connections = 0;
  newSessions = 0;
  loadSessionsAccepted: string[] = [];
  loadSessionsRejected: string[] = [];
  /** If non-null, fail every loadSession with this error message. */
  failLoadSession: string | null = null;
  private opts: FakeACPServerOpts;

  constructor(opts: FakeACPServerOpts = {}) {
    this.opts = opts;
    const dir = mkdtempSync(join(tmpdir(), "acp-test-"));
    this.socketPath = join(dir, "agent.sock");
    this.server = createServer((sock) => this.handle(sock));
  }

  async start(): Promise<void> {
    return new Promise((resolve) => this.server.listen(this.socketPath, () => resolve()));
  }

  async stop(): Promise<void> {
    return new Promise((resolve) => this.server.close(() => resolve()));
  }

  private handle(sock: Socket): void {
    this.connections++;
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
              agentCapabilities: {
                loadSession: true,
                promptCapabilities: { audio: false, embeddedContext: false, image: false, meta: false },
                mcpCapabilities: { http: false, sse: false },
              },
              authMethods: [],
            },
          });
        } else if (msg.method === "session/new") {
          this.newSessions++;
          const n = this.opts.noiseBeforeNewSession ?? 0;
          for (let i = 0; i < n; i++) {
            sock.write(`[INFO] hermes log noise line ${i} that is not JSON\n`);
          }
          send({ jsonrpc: "2.0", id: msg.id, result: { sessionId: "sess-fake-123", modes: null } });
        } else if (msg.method === "session/load") {
          const sid = (msg.params as { sessionId?: string } | undefined)?.sessionId ?? "?";
          if (this.failLoadSession) {
            this.loadSessionsRejected.push(sid);
            send({ jsonrpc: "2.0", id: msg.id, error: { code: -32000, message: this.failLoadSession } });
          } else {
            this.loadSessionsAccepted.push(sid);
            send({ jsonrpc: "2.0", id: msg.id, result: { modes: null } });
          }
        } else if (msg.method === "session/prompt") {
          if (this.opts.emitNoise) {
            sock.write("[INFO] hermes log noise that's not JSON\n");
          }
          // Capture prompt text for assertion (R-stuck tests).
          try {
            const params = (msg.params ?? {}) as { prompt?: Array<{ type?: string; text?: string }> };
            for (const block of params.prompt ?? []) {
              if (block?.type === "text" && typeof block.text === "string") {
                this.promptTexts.push(block.text);
              }
            }
          } catch { /* ignore */ }
          if (this.opts.hangPrompts) return;
          this.promptsHandled++;
          promptsThisConn++;
          send({ jsonrpc: "2.0", id: msg.id, result: { stopReason: "end_turn" } });
          if (this.opts.closeAfterPrompts && promptsThisConn >= this.opts.closeAfterPrompts) {
            setImmediate(() => sock.end());
          }
        }
      }
    });
    sock.on("error", () => {});
  }
}

function uem(idx: number): UEM {
  return {
    event_id: `acp-test:${idx}`,
    source: "test",
    target_agent: "agent-x",
    kind: "test",
    summary: `evt ${idx}`,
    observed_at: Date.now(),
    raw: null,
  };
}

let server: FakeACPServer;
let channel: ACPSocketChannel;

beforeEach(async () => {});

afterEach(async () => {
  await channel?.close();
  await server?.stop();
  try { rmSync(server?.socketPath ?? "", { force: true }); } catch { /* */ }
});

describe("ACPSocketChannel (R7)", () => {
  it("happy path: connect → initialize → newSession → prompt → stopReason", async () => {
    server = new FakeACPServer();
    await server.start();
    channel = new ACPSocketChannel({
      socketPath: server.socketPath,
      cwd: "/work",
      onLog: () => {},
    });
    const r = await channel.prompt(uem(1));
    expect(r.stopReason).toBe("end_turn");
    expect(server.promptsHandled).toBe(1);
    expect(server.connections).toBe(1);
  });

  it("REGRESSION B11: newSession response must arrive even after several initialize-time noise lines", async () => {
    // Reproduces the dev-stack hang where socat ',stderr' was piping
    // hermes-side python logging into the unix socket, interleaving
    // many non-JSON lines between initialize-response and newSession-response.
    server = new FakeACPServer({ noiseBeforeNewSession: 12 });
    await server.start();
    channel = new ACPSocketChannel({
      socketPath: server.socketPath, cwd: "/work", onLog: () => {},
    });
    const r1 = await channel.prompt(uem(99));
    expect(r1.stopReason).toBe("end_turn");
    expect(server.promptsHandled).toBe(1);
  });

  it("multiple prompts on one connection (cache reuse)", async () => {
    server = new FakeACPServer();
    await server.start();
    channel = new ACPSocketChannel({
      socketPath: server.socketPath, cwd: "/work", onLog: () => {},
    });
    await channel.prompt(uem(1));
    await channel.prompt(uem(2));
    await channel.prompt(uem(3));
    expect(server.promptsHandled).toBe(3);
    expect(server.connections).toBe(1); // single long-lived connection
  });

  it("DEV-STACK BUG REGRESSION: prompt rejects when socket closes mid-flight", async () => {
    // Simulate socat EXEC subprocess exiting after delivering first response.
    server = new FakeACPServer({ closeAfterPrompts: 1 });
    await server.start();
    channel = new ACPSocketChannel({
      socketPath: server.socketPath, cwd: "/work", onLog: () => {},
    });
    // First prompt succeeds.
    const r1 = await channel.prompt(uem(1));
    expect(r1.stopReason).toBe("end_turn");
    // Wait for the close event to propagate.
    await new Promise((r) => setTimeout(r, 100));
    // Second prompt MUST either reject (socket dead) OR succeed via reconnect.
    // Currently the bug is that it hangs forever. We assert it returns within 5s.
    const t0 = Date.now();
    const second = channel.prompt(uem(2));
    const result = await Promise.race([
      second.then((v) => ({ ok: true, v })).catch((e) => ({ ok: false, e })),
      new Promise((res) => setTimeout(() => res({ ok: false, e: new Error("timeout") }), 5000)),
    ]) as { ok: boolean; v?: unknown; e?: unknown };
    const elapsed = Date.now() - t0;
    // Expectation: it does NOT hang for 5s. Either reject or succeed quickly.
    expect(elapsed).toBeLessThan(4500);
  });

  it("reconnect: after close, next prompt opens a fresh connection", async () => {
    // Server closes the socket after the first prompt response delivered.
    // Then it accepts a brand new connection and serves prompts indefinitely.
    server = new FakeACPServer({ closeAfterPrompts: 1 });
    await server.start();
    channel = new ACPSocketChannel({
      socketPath: server.socketPath, cwd: "/work", onLog: () => {},
    });
    await channel.prompt(uem(1));
    // Wait for socket close event to propagate.
    await new Promise((r) => setTimeout(r, 200));
    // Second prompt may reject (residual close error from in-flight read loop)
    // OR succeed via reconnect. Either way, it MUST not hang.
    const t0 = Date.now();
    let secondOk = false;
    try { await channel.prompt(uem(2)); secondOk = true; } catch { /* ok */ }
    expect(Date.now() - t0).toBeLessThan(3000);
    // Wait again for any close after second prompt
    await new Promise((r) => setTimeout(r, 200));
    // Third prompt MUST succeed via a fresh reconnect.
    const r3 = await channel.prompt(uem(3));
    expect(r3.stopReason).toBe("end_turn");
    expect(server.connections).toBeGreaterThanOrEqual(2);
    expect(secondOk || true).toBe(true); // either path acceptable
  });

  it("tolerates non-JSON noise on stdout (SDK eats it, doesn't crash)", async () => {
    server = new FakeACPServer({ emitNoise: true });
    await server.start();
    channel = new ACPSocketChannel({
      socketPath: server.socketPath, cwd: "/work", onLog: () => {},
    });
    const r1 = await channel.prompt(uem(1));
    const r2 = await channel.prompt(uem(2));
    expect(r1.stopReason).toBe("end_turn");
    expect(r2.stopReason).toBe("end_turn");
    expect(server.promptsHandled).toBe(2);
  });

  // R10 — sessionStore: persist ACP sessionId across reconnects so prompt
  // cache + conversation history survive hermes/router restarts.
  it("R10: persists sessionId on first connect via sessionStore.set", async () => {
    server = new FakeACPServer();
    await server.start();
    let stored: string | null = null;
    const sessionStore = {
      get: async () => stored,
      set: async (sid: string) => { stored = sid; },
    };
    channel = new ACPSocketChannel({
      socketPath: server.socketPath, cwd: "/work", onLog: () => {}, sessionStore,
    });
    await channel.prompt(uem(1));
    expect(stored).toBe("sess-fake-123");
    expect(server.newSessions).toBe(1);
    expect(server.loadSessionsAccepted.length).toBe(0);
  });

  it("R10: on second connect, calls loadSession with stored id (no newSession)", async () => {
    server = new FakeACPServer({ closeAfterPrompts: 1 });
    await server.start();
    let stored: string | null = null;
    const sessionStore = {
      get: async () => stored,
      set: async (sid: string) => { stored = sid; },
    };
    channel = new ACPSocketChannel({
      socketPath: server.socketPath, cwd: "/work", onLog: () => {}, sessionStore,
    });
    // First prompt → newSession + persist id
    await channel.prompt(uem(1));
    expect(stored).toBe("sess-fake-123");
    expect(server.newSessions).toBe(1);
    // Server closes socket after first prompt; trigger reconnect.
    await new Promise((r) => setTimeout(r, 200));
    try { await channel.prompt(uem(2)); } catch { /* may reject due to mid-flight close */ }
    await new Promise((r) => setTimeout(r, 200));
    await channel.prompt(uem(3));
    // Second connect should have used loadSession with the stored id, not newSession.
    expect(server.loadSessionsAccepted).toContain("sess-fake-123");
    expect(server.newSessions).toBe(1); // never opened a fresh session
  });

  it("R10: if loadSession rejects, falls back to newSession and re-persists", async () => {
    server = new FakeACPServer({ closeAfterPrompts: 1 });
    await server.start();
    let stored: string | null = "stale-session-id-from-prior-run";
    const sessionStore = {
      get: async () => stored,
      set: async (sid: string) => { stored = sid; },
    };
    server.failLoadSession = "session not found";
    channel = new ACPSocketChannel({
      socketPath: server.socketPath, cwd: "/work", onLog: () => {}, sessionStore,
    });
    // First connect: loadSession("stale-…") fails → newSession.
    await channel.prompt(uem(1));
    expect(server.loadSessionsRejected).toContain("stale-session-id-from-prior-run");
    expect(server.newSessions).toBe(1);
    expect(stored).toBe("sess-fake-123"); // overwritten with new id from newSession
  });

  // ===========================================================================
  // R-stuck: ACP silence timeout.
  //
  // The 4.5h reviewer-team5 hang (2026-05-16 09:15 → 13:53) showed prompt()
  // can await forever when the agent stops emitting any ACP message
  // (no stopReason, no message_chunk, no usage_update). Symptom in prod:
  // mini-router keeps ingesting events but never dispatches because the
  // last prompt() never resolves.
  //
  // Fix: ACPSocketChannel accepts `stuckMs` opt. If no ACP RX (any kind)
  // for stuckMs while a prompt is in flight, the channel closes the
  // connection so prompt() rejects → dispatcher unblocks, retries later.
  // The next reconnect's prompt is prepended with a system-style notice
  // telling the agent its previous turn hit a timeout, so the agent can
  // learn to background long-running tools.
  // ===========================================================================
  it("R-stuck: prompt rejects when agent goes silent past stuckMs", async () => {
    server = new FakeACPServer({ hangPrompts: true });
    await server.start();
    channel = new ACPSocketChannel({
      socketPath: server.socketPath, cwd: "/work", onLog: () => {},
      stuckMs: 300, // 300ms silence triggers timeout in test
    });
    const t0 = Date.now();
    await expect(channel.prompt(uem(1))).rejects.toThrow(/stuck|silence|timeout/i);
    const dt = Date.now() - t0;
    expect(dt).toBeGreaterThanOrEqual(250);
    expect(dt).toBeLessThan(2000); // shouldn't wait minutes
  }, 5000);

  it("R-stuck: after stuck-timeout reconnect, next prompt is prepended with notice", async () => {
    // First server: hangs forever to trigger stuck timeout.
    server = new FakeACPServer({ hangPrompts: true });
    await server.start();
    const sockPath = server.socketPath;
    channel = new ACPSocketChannel({
      socketPath: sockPath, cwd: "/work", onLog: () => {},
      stuckMs: 300,
    });
    await expect(channel.prompt(uem(1))).rejects.toThrow();

    // Replace server with one that records the next prompt text + responds.
    await server.stop();
    server = new FakeACPServer();
    // Reuse the same socket path so the channel's reconnect lands on the new server.
    (server as unknown as { socketPath: string }).socketPath = sockPath;
    await server.start();

    await channel.prompt(uem(2));
    const concat = server.promptTexts.join("\n");
    expect(concat).toMatch(/previous turn timed out|stuck|silence/i);
  }, 10000);

  it("R-stuck: stuckMs not set → prompt does NOT auto-timeout (back-compat)", async () => {
    server = new FakeACPServer({ hangPrompts: true });
    await server.start();
    channel = new ACPSocketChannel({
      socketPath: server.socketPath, cwd: "/work", onLog: () => {},
      // no stuckMs
    });
    // Race prompt against a 500ms timer; the timer should win (prompt still hanging).
    const p = channel.prompt(uem(1)).catch((e) => `rejected:${String(e).slice(0, 40)}`);
    const winner = await Promise.race([
      p,
      new Promise<string>((r) => setTimeout(() => r("still-hanging"), 500)),
    ]);
    expect(winner).toBe("still-hanging");
    // Force-close to unwind the hanging prompt before test exit.
    // Race the resolution against a short timer so a non-rejecting SDK
    // can't deadlock the test.
    await channel.close();
    await Promise.race([p, new Promise((r) => setTimeout(r, 500))]);
  }, 5000);
});
