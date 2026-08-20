/**
 * F8 sidecar / ACP unix-socket bridge.
 *
 * R7 design (DESIGN_R7_SIDECAR §4.3 / §9): each hermes-agent container
 * runs an in-foreground `socat UNIX-LISTEN:/var/run/acp/agent.sock,fork
 * EXEC:"python -m acp_adapter.entry"`. Per-connection fork → fresh
 * acp_adapter subprocess wired to the socket as stdio.
 *
 * What we test (real container, real socket, no mocks):
 *  1. socket file exists at the host bind-mount path
 *  2. one connection → JSON-RPC `initialize` → matching response.id
 *  3. disconnect + reconnect → second `initialize` succeeds (proves fork)
 *  4. two concurrent connections → independent responses
 *
 * Permissions: socket is mode 0660 owned by uid:gid 10000:10000 (the hermes
 * user). The host test runner (azureuser) is not in that group, so we go
 * through `sudo python3 -c '...AF_UNIX...'` line-bridge instead of node
 * net.createConnection — same wire bytes, real socket, just elevated perms
 * to read/write it.
 */
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";
import { describe, expect, it } from "vitest";
import { DATA_DIR } from "../lib/env.ts";

// agent1/agent2 only exist under PROFILE=dev (compose `profiles: ["dev"]`).
// Test profile starts agent3..agent10 instead. Pick agent3 as the canonical
// probe target.
const AGENT = "agent3";
const HOST_SOCK = resolve(DATA_DIR, "acp", AGENT, "agent.sock");

interface AcpClient {
  proc: ChildProcessWithoutNullStreams;
  send(msg: object): void;
  recv(timeoutMs: number): Promise<any>;
  close(): void;
}

function connect(): AcpClient {
  // sudo because the socket is mode 0660 owned by uid 10000.
  // Tiny python bridge: copies stdin → AF_UNIX socket and socket → stdout
  // unbuffered. Equivalent to `socat - UNIX-CONNECT:sock`, but socat is
  // not installed on this dev host.
  const PY = `
import os, sys, socket, threading, errno
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect(${JSON.stringify(HOST_SOCK)})
def up():
    try:
        while True:
            b = os.read(0, 65536)
            if not b: break
            s.sendall(b)
    except Exception:
        pass
    try: s.shutdown(socket.SHUT_WR)
    except Exception: pass
def dn():
    try:
        while True:
            b = s.recv(65536)
            if not b: break
            os.write(1, b)
    except Exception:
        pass
t = threading.Thread(target=up, daemon=True)
t.start()
dn()
`;
  const proc = spawn("sudo", ["python3", "-u", "-c", PY], {
    stdio: ["pipe", "pipe", "pipe"],
  });
  let buf = "";
  const queue: any[] = [];
  const waiters: ((v: any) => void)[] = [];
  proc.stdout.on("data", (chunk: Buffer) => {
    buf += chunk.toString("utf8");
    let idx;
    while ((idx = buf.indexOf("\n")) !== -1) {
      const line = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 1);
      if (!line) continue;
      let parsed: any;
      try {
        parsed = JSON.parse(line);
      } catch {
        // skip non-JSON-RPC noise (warnings shouldn't appear since
        // acp_adapter routes logging to stderr, but be defensive)
        continue;
      }
      if (waiters.length) waiters.shift()!(parsed);
      else queue.push(parsed);
    }
  });
  proc.stderr.on("data", (c: Buffer) => {
    if (process.env.OMC_TEST_DEBUG === "1")
      process.stderr.write(`[socat-stderr] ${c.toString("utf8")}`);
  });
  return {
    proc,
    send(msg: object) {
      proc.stdin.write(JSON.stringify(msg) + "\n");
    },
    recv(timeoutMs: number): Promise<any> {
      return new Promise((res, rej) => {
        if (queue.length) return res(queue.shift());
        const t = setTimeout(() => {
          const i = waiters.indexOf(w);
          if (i >= 0) waiters.splice(i, 1);
          rej(new Error(`recv timeout after ${timeoutMs}ms`));
        }, timeoutMs);
        const w = (v: any) => {
          clearTimeout(t);
          res(v);
        };
        waiters.push(w);
      });
    },
    close() {
      try {
        proc.stdin.end();
      } catch {
        /* noop */
      }
      try {
        proc.kill("SIGTERM");
      } catch {
        /* noop */
      }
    },
  };
}

async function initializeOnce(c: AcpClient, id: number): Promise<any> {
  c.send({
    jsonrpc: "2.0",
    id,
    method: "initialize",
    params: {
      protocolVersion: 1,
      clientCapabilities: {},
      clientInfo: { name: "omcgitea-bridge-test", version: "0.0.1" },
    },
  });
  // initialize on a cold acp_adapter.entry can take a few seconds (env load,
  // hermes constants). Generous timeout.
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    const msg = await c.recv(60_000);
    // Skip server-initiated notifications without an id (none expected
    // pre-initialize, but defensive).
    if (msg.id === id) return msg;
  }
  throw new Error("no response to initialize");
}

describe("F8 acp bridge (R7 sidecar)", () => {
  it("host-side socket exists for agent1 at /var/run/acp bind-mount", () => {
    expect(existsSync(HOST_SOCK)).toBe(true);
  });

  it("single connection: initialize round-trip succeeds", async () => {
    const c = connect();
    try {
      const resp = await initializeOnce(c, 1);
      expect(resp.id).toBe(1);
      expect(resp.error).toBeUndefined();
      expect(resp.result).toBeDefined();
      expect(typeof resp.result.protocolVersion).toBe("number");
    } finally {
      c.close();
    }
  });

  it("reconnect: each new connection gets a fresh acp_adapter subprocess", async () => {
    for (let i = 0; i < 3; i++) {
      const c = connect();
      try {
        const resp = await initializeOnce(c, 100 + i);
        expect(resp.id).toBe(100 + i);
        expect(resp.result?.protocolVersion).toBeDefined();
      } finally {
        c.close();
      }
      await sleep(200);
    }
  });

  it("concurrent: 2 connections get independent subprocesses", async () => {
    const a = connect();
    const b = connect();
    try {
      const [ra, rb] = await Promise.all([
        initializeOnce(a, 7001),
        initializeOnce(b, 7002),
      ]);
      expect(ra.id).toBe(7001);
      expect(rb.id).toBe(7002);
      expect(ra.result?.protocolVersion).toBeDefined();
      expect(rb.result?.protocolVersion).toBeDefined();
    } finally {
      a.close();
      b.close();
    }
  });

  it("FULL HANDSHAKE: initialize → newSession → response received (the dev-stack regression)", async () => {
    // Real-world bug repro: mini-router connects, sends initialize OK,
    // sends session/new, but never receives the newSession response.
    // The fact that bridge tests above pass while dev hangs means our
    // bridge tests are too shallow. This test goes one step further.
    const c = connect();
    try {
      const initResp = await initializeOnce(c, 9001);
      expect(initResp.id).toBe(9001);
      // Send session/new immediately after initialize
      c.send({
        jsonrpc: "2.0",
        id: 9002,
        method: "session/new",
        params: { cwd: "/work", mcpServers: [] },
      });
      // Wait for the matching response (id=9002).
      // Hermes also emits a session/update notification right after
      // newSession; we must keep reading past notifications until we
      // see the response.
      const deadline = Date.now() + 60_000;
      let nsResp: any = null;
      while (Date.now() < deadline) {
        const msg = await c.recv(60_000);
        if (msg.id === 9002) { nsResp = msg; break; }
        // Otherwise it's a notification (no id) — keep going.
      }
      expect(nsResp, "newSession response (id=9002) must arrive within 60s").toBeTruthy();
      expect(nsResp.error).toBeUndefined();
      expect(nsResp.result?.sessionId).toBeTruthy();
      expect(typeof nsResp.result.sessionId).toBe("string");
    } finally {
      c.close();
    }
  }, 120_000);
});
