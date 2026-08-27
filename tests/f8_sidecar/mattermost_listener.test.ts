/**
 * F8 mattermost listener integration test.
 *
 * Real EventStore (mysql) + fake mattermost WebSocket server.
 * Verifies the full path:
 *   ws frame → MattermostListener → ingest into events table → onIngest fires.
 */
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { spawnSync } from "node:child_process";
import { createServer, type Server } from "node:http";
import { WebSocketServer, type WebSocket as WSConn } from "ws";
import { randomUUID } from "node:crypto";
import { EventStore } from "../../mini-router/src/state.ts";
import { MattermostListener } from "../../mini-router/src/listeners/mattermost/listener.ts";

const CONTAINER = "omcgitea-test-mysql";
const ROOT_PW = "test-root-pw";
const DB = "omcgitea_test";
const PORT = 23306;

function sh(cmd: string, args: string[]) {
  const r = spawnSync(cmd, args, { encoding: "utf8" });
  return { out: r.stdout ?? "" };
}
async function waitForReady(): Promise<void> {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    const r = sh("sudo", ["-n", "docker", "exec", CONTAINER, "mysqladmin", "ping", "-uroot", `-p${ROOT_PW}`]);
    if (r.out.includes("mysqld is alive")) return;
    await new Promise((res) => setTimeout(res, 1000));
  }
  throw new Error("mysql not ready");
}

let store: EventStore;
let httpServer: Server;
let wss: WebSocketServer;
let port: number;
let conns: WSConn[] = [];

beforeAll(async () => {
  await waitForReady();
  store = new EventStore({ pool: { uri: `mysql://root:${ROOT_PW}@127.0.0.1:${PORT}/${DB}` } });
  await store.ensureSchema();
}, 90_000);
afterAll(async () => {
  await (store as unknown as { pool: { end(): Promise<void> } }).pool.end();
});

beforeEach(async () => {
  conns = [];
  httpServer = createServer();
  wss = new WebSocketServer({ server: httpServer, path: "/api/v4/websocket" });
  wss.on("connection", async (c) => {
    conns.push(c);
    const auth = await new Promise((res) => c.once("message", (b) => res(JSON.parse(b.toString()))));
    void auth;
    c.send(JSON.stringify({ status: "OK", seq_reply: 1 }));
    c.send(JSON.stringify({ event: "hello", data: {}, broadcast: {}, seq: 0 }));
  });
  await new Promise<void>((res) => httpServer.listen(0, "127.0.0.1", () => res()));
  const addr = httpServer.address();
  port = typeof addr === "object" && addr ? addr.port : 0;
});
afterEach(async () => {
  wss.close();
  await new Promise<void>((res) => httpServer.close(() => res()));
});

describe("MattermostListener", () => {
  it("ingests `posted` ws events into mysql under correct agent", async () => {
    const agent = `mml-${randomUUID().slice(0, 8)}`;
    const ingestedCounts: number[] = [];
    const listener = new MattermostListener({
      agent,
      state: store,
      baseUrl: `http://127.0.0.1:${port}`,
      token: "tok-test",
      onIngest: (n) => ingestedCounts.push(n),
    });
    const ctrl = new AbortController();
    const task = listener.run({ signal: ctrl.signal });
    // Wait for connect + auth + hello
    await new Promise((r) => setTimeout(r, 300));
    expect(conns.length).toBeGreaterThan(0);

    // Push 3 `posted` events
    for (let i = 0; i < 3; i++) {
      conns[0]!.send(JSON.stringify({
        event: "posted",
        data: {
          channel_type: "O",
          channel_display_name: "general",
          channel_name: "general",
          sender_name: "@coder1",
          post: JSON.stringify({ id: `p-${i}`, create_at: i, edit_at: 0, user_id: "u1", channel_id: "ch1", message: `msg ${i}` }),
        },
        broadcast: { channel_id: "ch1", team_id: "t1" },
        seq: i + 1,
      }));
    }
    // Give time for them to arrive + be ingested
    await new Promise((r) => setTimeout(r, 300));
    ctrl.abort();
    await task;

    const pool = (store as unknown as { pool: { query: (sql: string, p: unknown[]) => Promise<unknown> } }).pool;
    const rows = (await pool.query(
      `SELECT dedup_key FROM events WHERE agent=? ORDER BY id`,
      [agent],
    )) as [Array<{ dedup_key: string }>, unknown];
    expect(rows[0].length).toBe(3);
    expect(rows[0].map((r) => r.dedup_key).sort()).toEqual([
      "mattermost:post:p-0:0",
      "mattermost:post:p-1:0",
      "mattermost:post:p-2:0",
    ]);
    expect(ingestedCounts.reduce((a, b) => a + b, 0)).toBe(3);
  }, 30_000);

  it("dedups same post (idempotency on dedup_key)", async () => {
    const agent = `mml-${randomUUID().slice(0, 8)}`;
    const listener = new MattermostListener({
      agent, state: store,
      baseUrl: `http://127.0.0.1:${port}`,
      token: "tok-test",
    });
    const ctrl = new AbortController();
    const task = listener.run({ signal: ctrl.signal });
    await new Promise((r) => setTimeout(r, 300));

    const ev = JSON.stringify({
      event: "posted",
      data: {
        channel_type: "O",
        channel_display_name: "general",
        sender_name: "@coder1",
        post: JSON.stringify({ id: "p-x", create_at: 1, edit_at: 0, user_id: "u1", channel_id: "ch1", message: "hi" }),
      },
      broadcast: { channel_id: "ch1", team_id: "t1" },
      seq: 1,
    });
    conns[0]!.send(ev);
    conns[0]!.send(ev);
    await new Promise((r) => setTimeout(r, 300));
    ctrl.abort();
    await task;

    const pool = (store as unknown as { pool: { query: (sql: string, p: unknown[]) => Promise<unknown> } }).pool;
    const rows = (await pool.query(`SELECT id FROM events WHERE agent=?`, [agent])) as [Array<unknown>, unknown];
    expect(rows[0].length).toBe(1);
  }, 30_000);
});
