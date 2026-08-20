/**
 * F8 mattermost WebSocket driver tests.
 *
 * Real WebSocket against an in-process fake mattermost server. Verifies:
 *  - connect to /api/v4/websocket
 *  - authentication_challenge with bearer token
 *  - hello event signals success
 *  - posted events flow into onEvent callback
 *  - non-200 response triggers backoff reconnect
 *  - heartbeat watchdog kills silent connection
 *  - signal abort tears down cleanly
 */
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { createServer, type Server } from "node:http";
import { WebSocketServer, type WebSocket as WSConn } from "ws";
import { MattermostWS, type MattermostWsEvent } from "../../mini-router/src/listeners/mattermost/ws.ts";

let httpServer: Server;
let wss: WebSocketServer;
let port: number;
const onConn: Array<(c: WSConn) => void> = [];

beforeEach(async () => {
  httpServer = createServer();
  wss = new WebSocketServer({ server: httpServer, path: "/api/v4/websocket" });
  wss.on("connection", (c) => {
    for (const fn of onConn) fn(c);
  });
  await new Promise<void>((res) => httpServer.listen(0, "127.0.0.1", () => res()));
  const addr = httpServer.address();
  port = typeof addr === "object" && addr ? addr.port : 0;
});

afterEach(async () => {
  onConn.length = 0;
  wss.close();
  await new Promise<void>((res) => httpServer.close(() => res()));
});

function baseUrl(): string {
  return `http://127.0.0.1:${port}`;
}

async function expectMessage(c: WSConn): Promise<unknown> {
  return new Promise((res) => c.once("message", (b) => res(JSON.parse(b.toString()))));
}

describe("MattermostWS", () => {
  it("authenticates via authentication_challenge then receives hello", async () => {
    let authPayload: unknown = null;
    onConn.push(async (c) => {
      authPayload = await expectMessage(c);
      // ack
      c.send(JSON.stringify({ status: "OK", seq_reply: (authPayload as { seq?: number }).seq ?? 1 }));
      // hello
      c.send(JSON.stringify({ event: "hello", data: { server_version: "10.0" }, broadcast: {}, seq: 0 }));
    });

    const events: MattermostWsEvent[] = [];
    const ws = new MattermostWS({
      baseUrl: baseUrl(),
      token: "tok-abc",
      onEvent: (ev) => events.push(ev),
      heartbeatTimeoutMs: 0,
    });
    const ctrl = new AbortController();
    const task = ws.run(ctrl.signal);
    // give it ~200ms to connect + auth + recv hello
    await new Promise((r) => setTimeout(r, 300));
    ctrl.abort();
    await task;

    expect(authPayload).toMatchObject({
      action: "authentication_challenge",
      data: { token: "tok-abc" },
    });
    expect(events.find((e) => e.event === "hello")).toBeTruthy();
    expect(ws.connected).toBe(false); // after abort
  });

  it("delivers `posted` events to onEvent callback", async () => {
    onConn.push(async (c) => {
      await expectMessage(c);
      c.send(JSON.stringify({ status: "OK", seq_reply: 1 }));
      c.send(JSON.stringify({ event: "hello", data: {}, broadcast: {}, seq: 0 }));
      c.send(JSON.stringify({
        event: "posted",
        data: {
          channel_type: "O",
          channel_display_name: "general",
          channel_name: "general",
          sender_name: "@coder1",
          post: JSON.stringify({ id: "p1", create_at: 1, edit_at: 0, user_id: "u1", channel_id: "ch1", message: "hi" }),
        },
        broadcast: { channel_id: "ch1", team_id: "t1" },
        seq: 1,
      }));
    });

    const events: MattermostWsEvent[] = [];
    const ws = new MattermostWS({
      baseUrl: baseUrl(),
      token: "tok",
      onEvent: (e) => events.push(e),
      heartbeatTimeoutMs: 0,
    });
    const ctrl = new AbortController();
    const task = ws.run(ctrl.signal);
    await new Promise((r) => setTimeout(r, 300));
    ctrl.abort();
    await task;

    const posted = events.find((e) => e.event === "posted");
    expect(posted).toBeTruthy();
    expect((posted!.data as { channel_display_name: string }).channel_display_name).toBe("general");
  });

  it("reconnects on disconnect with backoff", async () => {
    let connCount = 0;
    onConn.push(async (c) => {
      connCount++;
      await expectMessage(c);
      c.send(JSON.stringify({ status: "OK", seq_reply: 1 }));
      // close immediately to force reconnect
      c.close();
    });

    const ws = new MattermostWS({
      baseUrl: baseUrl(),
      token: "tok",
      onEvent: () => {},
      heartbeatTimeoutMs: 0,
      initialBackoffMs: 50,
      maxBackoffMs: 100,
    });
    const ctrl = new AbortController();
    const task = ws.run(ctrl.signal);
    // Give time for >= 2 connect attempts
    await new Promise((r) => setTimeout(r, 600));
    ctrl.abort();
    await task;

    expect(connCount).toBeGreaterThanOrEqual(2);
    expect(ws.reconnects).toBeGreaterThanOrEqual(2);
  }, 10_000);

  it("heartbeat watchdog kills silent connection", async () => {
    onConn.push(async (c) => {
      await expectMessage(c);
      c.send(JSON.stringify({ status: "OK", seq_reply: 1 }));
      // never send any further frames — watchdog should fire
    });

    let lastErr: unknown = null;
    const ws = new MattermostWS({
      baseUrl: baseUrl(),
      token: "tok",
      onEvent: () => {},
      heartbeatTimeoutMs: 200,
      initialBackoffMs: 50,
      maxBackoffMs: 50,
      onError: (e) => { lastErr = e; },
    });
    const ctrl = new AbortController();
    const task = ws.run(ctrl.signal);
    await new Promise((r) => setTimeout(r, 700));
    ctrl.abort();
    await task;

    expect(String(lastErr)).toMatch(/heartbeat/i);
    expect(ws.reconnects).toBeGreaterThanOrEqual(2);
  }, 10_000);

  it("signal abort tears down cleanly without throwing", async () => {
    onConn.push(async (c) => {
      await expectMessage(c);
      c.send(JSON.stringify({ status: "OK", seq_reply: 1 }));
      c.send(JSON.stringify({ event: "hello", data: {}, broadcast: {}, seq: 0 }));
    });

    const ws = new MattermostWS({
      baseUrl: baseUrl(),
      token: "tok",
      onEvent: () => {},
      heartbeatTimeoutMs: 0,
    });
    const ctrl = new AbortController();
    const task = ws.run(ctrl.signal);
    await new Promise((r) => setTimeout(r, 200));
    ctrl.abort();
    await expect(task).resolves.toBeUndefined();
  });
});
