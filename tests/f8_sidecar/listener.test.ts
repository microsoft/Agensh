/**
 * GiteaListener tests for mini-router (R7) — composition of fetcher + EventStore.
 *
 * Ported from router/test/listener.test.ts. Uses real MySQL (shared
 * test container) with per-test agent namespace for isolation.
 */
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { EventStore } from "../../mini-router/src/state.ts";
import { GiteaListener } from "../../mini-router/src/listeners/gitea/listener.ts";
import type {
  FetchLike,
  GiteaNotificationRaw,
} from "../../mini-router/src/listeners/gitea/fetcher.ts";
import type { UpstreamAuth } from "../../mini-router/src/upstream_auth.ts";

const CONTAINER = "omcgitea-test-mysql";
const ROOT_PW = "test-root-pw";
const DB = "omcgitea_test";
const PORT = 23306;

function sh(cmd: string, args: string[]): { code: number; out: string } {
  const r = spawnSync(cmd, args, { encoding: "utf8" });
  return { code: r.status ?? -1, out: r.stdout ?? "" };
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
beforeAll(async () => {
  await waitForReady();
  store = new EventStore({ pool: { uri: `mysql://root:${ROOT_PW}@127.0.0.1:${PORT}/${DB}` } });
  await store.ensureSchema();
}, 90_000);
afterAll(async () => {
  await (store as unknown as { pool: { end(): Promise<void> } }).pool.end();
});

function stubAuth(): UpstreamAuth {
  return {
    async ensureCredentials() {
      return { headers: { Cookie: "i_like_gitea=stub" }, expiresAt: Date.now() + 3_600_000 };
    },
    invalidate() {},
  };
}

function fakeFetch(pages: GiteaNotificationRaw[][]): {
  fetch: FetchLike;
  calls: { url: string; since: string | null }[];
} {
  let i = 0;
  const calls: { url: string; since: string | null }[] = [];
  const fetch: FetchLike = async (url) => {
    const u = new URL(url);
    calls.push({ url, since: u.searchParams.get("since") });
    const body = pages[Math.min(i++, pages.length - 1)] ?? [];
    return {
      ok: true,
      status: 200,
      async text() { return JSON.stringify(body); },
      async json() { return body; },
    };
  };
  return { fetch, calls };
}

function notif(id: number, ts: string, title = `t${id}`): GiteaNotificationRaw {
  return {
    id, updated_at: ts,
    subject: { title, type: "Issue" },
    repository: { full_name: "team/sandbox" },
  };
}

describe("GiteaListener.pollOnce()", () => {
  it("on first run sends since=null, ingests rows, advances cursor", async () => {
    const agent = `lst-${randomUUID().slice(0, 8)}-first`;
    const { fetch, calls } = fakeFetch([
      [notif(1, "2026-04-27T08:00:00Z"), notif(2, "2026-04-27T08:01:00Z")],
    ]);
    const listener = new GiteaListener({
      agent, state: store, baseUrl: "http://gitea", auth: stubAuth(), token: "PAT", fetch,
    });
    const r = await listener.pollOnce();
    expect(r.inserted).toBe(2);
    expect(r.cursor).toBe("2026-04-27T08:01:00Z");
    expect(await store.getCursor(agent, "gitea")).toBe("2026-04-27T08:01:00Z");
    expect(calls[0]!.since).toBeNull();
  });

  it("on second run sends since=<cursor> and dedupes overlap", async () => {
    const agent = `lst-${randomUUID().slice(0, 8)}-overlap`;
    const { fetch, calls } = fakeFetch([
      [notif(1, "2026-04-27T08:00:00Z")],
      [notif(1, "2026-04-27T08:00:00Z"), notif(2, "2026-04-27T08:05:00Z")],
    ]);
    const listener = new GiteaListener({
      agent, state: store, baseUrl: "http://gitea", auth: stubAuth(), token: "PAT", fetch,
    });
    const r1 = await listener.pollOnce();
    const r2 = await listener.pollOnce();
    expect(r1.inserted).toBe(1);
    expect(r2.inserted).toBe(1);
    expect(calls[1]!.since).toBe("2026-04-27T08:00:00Z");
  });

  it("fires onIngest only when newly inserted rows exist", async () => {
    const agent = `lst-${randomUUID().slice(0, 8)}-onIngest`;
    const { fetch } = fakeFetch([
      [notif(1, "2026-04-27T08:00:00Z")],
      [notif(1, "2026-04-27T08:00:00Z")],
      [],
    ]);
    let calls = 0;
    let lastCount = 0;
    const listener = new GiteaListener({
      agent, state: store, baseUrl: "http://gitea", auth: stubAuth(), token: "PAT", fetch,
      onIngest: (n) => { calls++; lastCount = n; },
    });
    await listener.pollOnce();
    await listener.pollOnce();
    await listener.pollOnce();
    expect(calls).toBe(1);
    expect(lastCount).toBe(1);
  });

  it("on fetch error the cursor does not move", async () => {
    const agent = `lst-${randomUUID().slice(0, 8)}-err`;
    const fetch: FetchLike = async () => ({
      ok: false, status: 500,
      async text() { return "oops"; },
      async json() { return {}; },
    });
    const listener = new GiteaListener({
      agent, state: store, baseUrl: "http://gitea", auth: stubAuth(), token: "PAT", fetch,
    });
    await store.setCursor(agent, "gitea", "2026-04-27T07:00:00Z");
    await expect(listener.pollOnce()).rejects.toThrow();
    expect(await store.getCursor(agent, "gitea")).toBe("2026-04-27T07:00:00Z");
  });

  it("does an initial pollOnce and only re-polls on trigger() (no periodic fallback)", async () => {
    const agent = `lst-${randomUUID().slice(0, 8)}-trigger`;
    let pollCalls = 0;
    const fetch: FetchLike = async () => {
      pollCalls++;
      return {
        ok: true, status: 200,
        async text() { return "[]"; },
        async json() { return []; },
      };
    };
    const listener = new GiteaListener({
      agent, state: store, baseUrl: "http://gitea", auth: stubAuth(), token: "PAT", fetch,
      sse: null,
    });
    const ctrl = new AbortController();
    const done = listener.runPolling({ signal: ctrl.signal });
    for (let i = 0; i < 10; i++) await new Promise((r) => setTimeout(r, 5));
    expect(pollCalls).toBe(1);
    await new Promise((r) => setTimeout(r, 50));
    expect(pollCalls).toBe(1);
    listener.trigger();
    for (let i = 0; i < 10; i++) await new Promise((r) => setTimeout(r, 5));
    expect(pollCalls).toBe(2);
    ctrl.abort();
    await done;
  });
});
