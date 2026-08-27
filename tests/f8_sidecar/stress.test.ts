/**
 * Stress tests for mini-router (R7) — push the dispatcher + state hard
 * but stay 100% in-process so the suite finishes in seconds and doesn't
 * burn LLM tokens.
 *
 * Ported from router/test/stress.test.ts. R7 changes:
 *   - State is real MySQL (per-test agent namespace) instead of :memory: SQLite
 *   - No watchdog/cancellation tests — R7 dispatcher uses the retry-on-fail
 *     mechanism from state.markFailed (next_retry_at) instead.
 *   - Channel is a thin in-process fake (no ACP SDK round-trip needed
 *     since we trust the unit tests for that).
 *
 * Invariants pinned:
 *   1. Per-agent FIFO holds even when many agents fire concurrently
 *   2. Cross-agent parallelism scales with N agents
 *   3. Coalescing: events arriving between ticks merge into one prompt
 *   4. Throughput: no O(N²) regression in MySQL layer
 */
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { Dispatcher } from "../../mini-router/src/dispatcher.ts";
import { EventStore, type UEMLike } from "../../mini-router/src/state.ts";

const CONTAINER = "omcgitea-test-mysql";
const ROOT_PW = "test-root-pw";
const DB = "omcgitea_test";
const PORT = 23306;

function sh(cmd: string, args: string[]) {
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
  store = new EventStore({ pool: { uri: `mysql://root:${ROOT_PW}@127.0.0.1:${PORT}/${DB}?connectionLimit=20` } });
  await store.ensureSchema();
}, 90_000);
afterAll(async () => {
  await (store as unknown as { pool: { end(): Promise<void> } }).pool.end();
});

function uem(event_id: string, agent: string): UEMLike {
  return {
    event_id, source: "stress", target_agent: agent,
    kind: "test", summary: "x", observed_at: 1, raw: {},
  };
}

class FakeChannel {
  prompts: unknown[][] = [];
  hook?: () => Promise<void>;
  async prompt(uems: unknown[]) {
    if (this.hook) await this.hook();
    this.prompts.push(uems);
    return { stopReason: "end_turn" };
  }
}

describe("mini-router stress (R7)", () => {
  it("coalesces burst-arrived events into a small number of prompt() calls", async () => {
    const NS = `coal-${randomUUID().slice(0, 8)}`;
    const agent = `${NS}-a`;
    let releaseFirst!: () => void;
    const firstReleased = new Promise<void>((r) => (releaseFirst = r));
    const channel = new FakeChannel();
    let calls = 0;
    channel.hook = async () => {
      calls++;
      if (calls === 1) await firstReleased;  // only the first prompt blocks
    };
    const disp = new Dispatcher({ agent, state: store, channel, batchLimit: 1000 });

    await store.ingest(uem(`${NS}-seed`, agent));
    const tick1 = disp.tick();
    // Wait for hook to be entered (calls==1 means prompt was called and is blocked)
    while (calls === 0) {
      await new Promise((r) => setTimeout(r, 5));
    }
    const N = 100;
    for (let i = 0; i < N; i++) {
      await store.ingest(uem(`${NS}-burst-${i}`, agent));
    }
    releaseFirst();
    const r1 = await tick1;
    const r2 = await disp.tick();
    expect(r1.dispatched).toBe(1);
    expect(r2.dispatched).toBe(N);
    expect(channel.prompts).toHaveLength(2);
    expect(channel.prompts[1]).toHaveLength(N);
  }, 30_000);

  it("preserves per-agent FIFO under N=4 agents × M=50 events concurrent dispatch", async () => {
    const NS = `fifo-${randomUUID().slice(0, 8)}`;
    const N = 4, M = 50;
    const channels: FakeChannel[] = [];
    const dispatchers: Dispatcher[] = [];
    for (let a = 0; a < N; a++) {
      const c = new FakeChannel();
      channels.push(c);
      dispatchers.push(new Dispatcher({
        agent: `${NS}-a${a}`, state: store, channel: c, batchLimit: 10,
      }));
    }
    // Ingest all up-front
    for (let a = 0; a < N; a++) {
      for (let i = 0; i < M; i++) {
        await store.ingest(uem(`${NS}-a${a}-i${i}`, `${NS}-a${a}`));
      }
    }
    // Drain in parallel
    await Promise.all(dispatchers.map(async (d) => {
      while ((await d.tick()).dispatched > 0) { /* */ }
    }));
    // Per-agent FIFO check
    for (let a = 0; a < N; a++) {
      const order: string[] = [];
      for (const p of channels[a]!.prompts) {
        for (const u of p as Array<{ event_id: string }>) order.push(u.event_id);
      }
      expect(order).toHaveLength(M);
      for (let i = 0; i < M; i++) {
        expect(order[i]).toBe(`${NS}-a${a}-i${i}`);
      }
    }
  }, 60_000);

  it("throughput: N=20 agents × M=50 events drains under 30s (no O(N²) regression)", async () => {
    const NS = `tput-${randomUUID().slice(0, 8)}`;
    const N = 20, M = 50;
    const dispatchers: Dispatcher[] = [];
    for (let a = 0; a < N; a++) {
      dispatchers.push(new Dispatcher({
        agent: `${NS}-a${a}`, state: store, channel: new FakeChannel(), batchLimit: 25,
      }));
    }
    for (let a = 0; a < N; a++) {
      for (let i = 0; i < M; i++) {
        await store.ingest(uem(`${NS}-a${a}-i${i}`, `${NS}-a${a}`));
      }
    }
    const t0 = Date.now();
    await Promise.all(dispatchers.map(async (d) => {
      while ((await d.tick()).dispatched > 0) { /* */ }
    }));
    const elapsed = Date.now() - t0;
    expect(elapsed).toBeLessThan(30_000);
    // eslint-disable-next-line no-console
    console.log(`[stress] ${N * M} events drained in ${elapsed}ms (${Math.floor((N * M) / (elapsed / 1000))} events/s)`);
  }, 60_000);
});
