/**
 * Dispatcher tests (R7 sidecar / F8).
 *
 * Real MySQL EventStore + a fake ACPChannel in-process to test the
 * dispatcher's tick / dispatchSpecific / onLog defaults / failure path.
 *
 * Critical regression: the 09:18 incident root cause was main.ts not
 * wiring onLog → silent failures. Tests assert that:
 *   - onLog defaults to a real logger (NOT undefined)
 *   - On ACP throw, BOTH state.markFailed gets called AND log fires
 *   - markFailed correctly bumps attempts and sets next_retry_at
 */
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { Dispatcher } from "../../mini-router/src/dispatcher.ts";
import {
  EventStore,
  RETRY_BACKOFF_MS,
  type UEMLike,
} from "../../mini-router/src/state.ts";

const CONTAINER = "omcgitea-test-mysql";
const ROOT_PW = "test-root-pw";
const DB = "omcgitea_test";
const PORT = 23306;

function sh(cmd: string, args: string[]): { code: number; out: string; err: string } {
  const r = spawnSync(cmd, args, { encoding: "utf8" });
  return { code: r.status ?? -1, out: r.stdout ?? "", err: r.stderr ?? "" };
}

async function waitForReady(): Promise<void> {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    const r = sh("sudo", ["-n", "docker", "exec", CONTAINER, "mysqladmin", "ping", "-uroot", `-p${ROOT_PW}`]);
    if (r.out.includes("mysqld is alive")) return;
    await new Promise((res) => setTimeout(res, 1000));
  }
  throw new Error("mysql container not ready in 60s");
}

let store: EventStore;

beforeAll(async () => {
  // Reuse the shared test mysql container; mysql_events.test.ts owns
  // its lifecycle. Just wait for it to be ready and connect.
  await waitForReady();
  store = new EventStore({
    pool: {
      uri: `mysql://root:${ROOT_PW}@127.0.0.1:${PORT}/${DB}`,
    },
  });
  await store.ensureSchema();
}, 90_000);

afterAll(async () => {
  await (store as unknown as { pool: { end(): Promise<void> } }).pool.end();
});

const NS = `disp-${randomUUID().slice(0, 8)}`;
function uem(idx: number, agent: string): UEMLike {
  return {
    event_id: `${NS}:${idx}`,
    source: "test",
    target_agent: agent,
    kind: "test",
    summary: `evt ${idx}`,
    observed_at: Date.now(),
    raw: null,
  };
}

describe("Dispatcher (R7)", () => {
  it("happy path: prompt resolves → markBatchSent", async () => {
    const agent = `${NS}-happy`;
    await store.ingest(uem(1, agent));
    await store.ingest(uem(2, agent));
    const calls: unknown[][] = [];
    const channel = {
      async prompt(uems: unknown[]) { calls.push(uems); return { stopReason: "end_turn" }; },
    };
    const d = new Dispatcher({ agent, state: store, channel });
    const { dispatched } = await d.tick();
    expect(dispatched).toBe(2);
    expect(calls).toHaveLength(1);
    expect(calls[0]).toHaveLength(2);
    // Verify state via DB
    const remaining = await store.nextPendingBatch(agent, 100);
    expect(remaining).toHaveLength(0);
  });

  it("REGRESSION 09:18: onLog DEFAULTS to console.error, NEVER undefined", () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      const d = new Dispatcher({
        agent: "x", state: store,
        channel: { prompt: async () => { throw new Error("boom"); } },
      });
      // Construct without onLog. Internal `log` must be a real fn.
      // Reach into private to assert; works because TS doesn't enforce at runtime.
      const log = (d as unknown as { log: (e: unknown) => void }).log;
      expect(typeof log).toBe("function");
      log({ level: "error", msg: "test fire" });
      expect(errSpy).toHaveBeenCalled();
    } finally {
      errSpy.mockRestore();
    }
  });

  it("ACP throw → markFailed bumps attempts AND onLog fires (NOT silent)", async () => {
    const agent = `${NS}-fail`;
    await store.ingest(uem(10, agent));
    const logged: Array<{ level: string; msg: string }> = [];
    const channel = {
      async prompt(_u: unknown[]) { throw new Error("acp-died"); },
    };
    const d = new Dispatcher({
      agent, state: store, channel,
      onLog: (e) => logged.push({ level: e.level, msg: e.msg }),
    });
    await d.tick();
    // assert: log fired
    expect(logged.find((l) => l.level === "error" && l.msg.includes("acp prompt failed"))).toBeTruthy();
    // assert: row in 'failed' state with attempts=2 (sending bumped, then markFailed bumped)
    const pool = (store as unknown as { pool: { query: (sql: string, p: unknown[]) => Promise<unknown> } }).pool;
    const rows = (await pool.query(`SELECT state, attempts, last_error, next_retry_at FROM events WHERE agent=?`, [agent])) as [Array<{ state: string; attempts: number; last_error: string; next_retry_at: number | null }>, unknown];
    const row = rows[0][0]!;
    expect(row.state).toBe("failed");
    expect(row.attempts).toBe(2);
    expect(row.last_error).toContain("acp-died");
    expect(row.next_retry_at).toBeGreaterThan(0);
  });

  it("retry sweeper path: claimRetryReady → dispatchSpecific → markBatchSent", async () => {
    const agent = `${NS}-retry`;
    await store.ingest(uem(20, agent));
    // First attempt fails to seed a 'failed' row with next_retry_at in past.
    let firstCall = true;
    const channel = {
      async prompt(_u: unknown[]) {
        if (firstCall) { firstCall = false; throw new Error("first fail"); }
        return { stopReason: "end_turn" };
      },
    };
    const d = new Dispatcher({ agent, state: store, channel });
    await d.tick(); // marks failed, attempts=2, next_retry_at=now+5s
    // Force next_retry_at to past so claimRetryReady picks it up
    const pool = (store as unknown as { pool: { query: (sql: string, p: unknown[]) => Promise<unknown> } }).pool;
    await pool.query(`UPDATE events SET next_retry_at = ? WHERE agent = ?`, [Date.now() - 1000, agent]);
    const claimed = await store.claimRetryReady(agent);
    expect(claimed).toHaveLength(1);
    await d.dispatchSpecific(claimed);
    const rows = (await pool.query(`SELECT state FROM events WHERE agent=?`, [agent])) as [Array<{ state: string }>, unknown];
    expect(rows[0][0]!.state).toBe("sent");
  });

  it("nextPendingBatch is agent-scoped (no cross-agent leakage)", async () => {
    const a = `${NS}-iso-a`, b = `${NS}-iso-b`;
    await store.ingest(uem(30, a));
    await store.ingest(uem(31, b));
    const batchA = await store.nextPendingBatch(a, 10);
    const batchB = await store.nextPendingBatch(b, 10);
    expect(batchA.every((r) => r.agent === a)).toBe(true);
    expect(batchB.every((r) => r.agent === b)).toBe(true);
  });
});
