/**
 * Real MySQL EventStore tests (R7 sidecar / F8).
 *
 * These tests must NOT mock MySQL — they spin up a dedicated mysql:8.4
 * container (name `omcgitea-test-mysql`) and run real DDL/DML against it.
 * Container name is project-prefixed per CLAUDE.md container safety rule.
 *
 * Each test uses a unique agent namespace (`test-${uuid}-...`) so the file
 * is isolation-safe even if rerun in parallel against a shared DB.
 */
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import {
  EventStore,
  RETRY_BACKOFF_MS,
  newBatchId,
  type UEMLike,
} from "../../mini-router/src/state.ts";

const CONTAINER = "omcgitea-test-mysql";
const ROOT_PW = "test-root-pw";
const DB = "omcgitea_test";
const PORT = 23306; // host-side; avoids clashing with prod 3306

function sh(cmd: string, args: string[]): { code: number; out: string; err: string } {
  const r = spawnSync(cmd, args, { encoding: "utf8" });
  return { code: r.status ?? -1, out: r.stdout ?? "", err: r.stderr ?? "" };
}

function dockerExists(name: string): boolean {
  // Safety: only ever asks about our own container name.
  const r = sh("sudo", ["-n", "docker", "ps", "-a", "--filter", `name=^${name}$`, "--format", "{{.Names}}"]);
  return r.out.trim() === name;
}

function dockerRunning(name: string): boolean {
  const r = sh("sudo", ["-n", "docker", "ps", "--filter", `name=^${name}$`, "--format", "{{.Names}}"]);
  return r.out.trim() === name;
}

async function waitForReady(): Promise<void> {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    const r = sh("sudo", [
      "-n", "docker", "exec", CONTAINER,
      "mysqladmin", "ping", "-uroot", `-p${ROOT_PW}`,
    ]);
    if (r.out.includes("mysqld is alive")) return;
    await new Promise((res) => setTimeout(res, 1000));
  }
  throw new Error("mysql container did not become ready in 60s");
}

let store: EventStore;

beforeAll(async () => {
  if (!dockerExists(CONTAINER)) {
    const r = sh("sudo", [
      "-n", "docker", "run", "-d",
      "--name", CONTAINER,
      "-e", `MYSQL_ROOT_PASSWORD=${ROOT_PW}`,
      "-e", `MYSQL_DATABASE=${DB}`,
      "-p", `${PORT}:3306`,
      "mysql:8.4",
    ]);
    if (r.code !== 0) throw new Error(`docker run failed: ${r.err}`);
  } else if (!dockerRunning(CONTAINER)) {
    sh("sudo", ["-n", "docker", "start", CONTAINER]);
  }
  await waitForReady();
  // Give mysqld a beat after ping passes — first connection sometimes
  // races initialization on cold boot.
  await new Promise((r) => setTimeout(r, 1500));
  store = new EventStore({
    pool: {
      host: "127.0.0.1",
      port: PORT,
      user: "root",
      password: ROOT_PW,
      database: DB,
    },
  });
  // Retry ensureSchema briefly: container may still be finishing init.
  let lastErr: unknown;
  for (let i = 0; i < 20; i++) {
    try {
      await store.ensureSchema();
      lastErr = undefined;
      break;
    } catch (e) {
      lastErr = e;
      await new Promise((r) => setTimeout(r, 500));
    }
  }
  if (lastErr) throw lastErr;
}, 90_000);

afterAll(async () => {
  if (store) await store.close();
  // Leave the container around for fast reruns; CI can prune by name.
  // Safety: only ever touch the container we created.
});

function uem(agent: string, suffix = "evt"): UEMLike {
  return {
    event_id: `${agent}-${suffix}-${randomUUID()}`,
    source: "gitea",
    target_agent: agent,
    kind: "issue.opened",
    summary: "test",
    observed_at: new Date().toISOString(),
    raw: {},
  };
}

function ns(): string {
  // unique-per-test agent namespace (max 128 chars of `agent` column)
  return `t-${randomUUID().slice(0, 8)}`;
}

describe("EventStore.ingest", () => {
  it("inserts a pending row and returns id", async () => {
    const a = ns();
    const id = await store.ingest(uem(a));
    expect(id).not.toBeNull();
    const row = await store._getById(id!);
    expect(row?.state).toBe("pending");
    expect(row?.agent).toBe(a);
    expect(row?.attempts).toBe(0);
  });

  it("is idempotent on (dedup_key, agent): second insert returns null", async () => {
    const a = ns();
    const u = uem(a);
    const id1 = await store.ingest(u);
    expect(id1).not.toBeNull();
    const id2 = await store.ingest(u);
    expect(id2).toBeNull();
  });

  it("same dedup_key under DIFFERENT agent inserts a new row", async () => {
    const a = ns();
    const b = ns();
    const u = uem(a);
    const id1 = await store.ingest(u);
    const u2 = { ...u, target_agent: b };
    const id2 = await store.ingest(u2);
    expect(id1).not.toBeNull();
    expect(id2).not.toBeNull();
    expect(id1).not.toBe(id2);
  });
});

describe("EventStore.nextPendingBatch", () => {
  it("returns oldest pending events for the requested agent only", async () => {
    const a = ns();
    const b = ns();
    const idA1 = await store.ingest(uem(a, "1"));
    const idA2 = await store.ingest(uem(a, "2"));
    const idB1 = await store.ingest(uem(b, "1"));
    const got = await store.nextPendingBatch(a, 32);
    const ids = got.map((r) => r.id);
    expect(ids).toContain(idA1);
    expect(ids).toContain(idA2);
    expect(ids).not.toContain(idB1);
    // FIFO order
    const aOnly = got.filter((r) => r.agent === a);
    for (let i = 1; i < aOnly.length; i++) {
      expect(aOnly[i]!.id).toBeGreaterThan(aOnly[i - 1]!.id);
    }
  });

  it("respects limit", async () => {
    const a = ns();
    for (let i = 0; i < 5; i++) await store.ingest(uem(a, `${i}`));
    const got = await store.nextPendingBatch(a, 2);
    expect(got.length).toBe(2);
  });
});

describe("EventStore.markBatchSending", () => {
  it("transitions pending → sending, sets batch_id, bumps attempts", async () => {
    const a = ns();
    const id1 = (await store.ingest(uem(a, "1")))!;
    const id2 = (await store.ingest(uem(a, "2")))!;
    const bid = newBatchId();
    const n = await store.markBatchSending([id1, id2], bid);
    expect(n).toBe(2);
    const r1 = await store._getById(id1);
    expect(r1?.state).toBe("sending");
    expect(r1?.batch_id).toBe(bid);
    expect(r1?.attempts).toBe(1);
  });

  it("ignores rows that are not pending (CAS-safe)", async () => {
    const a = ns();
    const id = (await store.ingest(uem(a)))!;
    await store.markBatchSending([id], newBatchId());
    // second call must not bump attempts again
    const n2 = await store.markBatchSending([id], newBatchId());
    expect(n2).toBe(0);
    const r = await store._getById(id);
    expect(r?.attempts).toBe(1);
  });
});

describe("EventStore.markBatchSent", () => {
  it("transitions sending → sent, stamps sent_at", async () => {
    const a = ns();
    const id = (await store.ingest(uem(a)))!;
    const bid = newBatchId();
    await store.markBatchSending([id], bid);
    const before = Date.now();
    const n = await store.markBatchSent(bid);
    expect(n).toBe(1);
    const r = await store._getById(id);
    expect(r?.state).toBe("sent");
    expect(r?.sent_at).not.toBeNull();
    expect(r!.sent_at!).toBeGreaterThanOrEqual(before - 5);
  });
});

describe("EventStore.markFailed (retry backoff)", () => {
  it("schedules next_retry_at = now + backoff[attempts-1]", async () => {
    const a = ns();
    const id = (await store.ingest(uem(a)))!;
    // simulate a dispatch attempt
    await store.markBatchSending([id], newBatchId());
    const now = 1_700_000_000_000;
    const res = await store.markFailed(id, "boom", now);
    expect(res?.attempts).toBe(2); // 1 from sending, +1 from failure
    expect(res?.next_retry_at).toBe(now + RETRY_BACKOFF_MS[1]); // attempts-1 = 1 → 5s
    const r = await store._getById(id);
    expect(r?.state).toBe("failed");
    expect(r?.last_error).toBe("boom");
  });

  it("attempts reaching MAX → next_retry_at NULL (terminal)", async () => {
    const a = ns();
    const id = (await store.ingest(uem(a)))!;
    // burn through attempts: each failure increments attempts by 1.
    // start with attempts=0; we need attempts to become 5 → next null.
    for (let i = 0; i < 5; i++) {
      await store.markFailed(id, `fail-${i}`, 1_700_000_000_000);
    }
    const r = await store._getById(id);
    expect(r?.attempts).toBe(5);
    expect(r?.next_retry_at).toBeNull();
  });
});

describe("EventStore.claimRetryReady", () => {
  it("returns failed/retrying rows whose next_retry_at <= now, marks them retrying", async () => {
    const a = ns();
    const id = (await store.ingest(uem(a)))!;
    await store.markBatchSending([id], newBatchId());
    const now = 1_700_000_000_000;
    await store.markFailed(id, "x", now);
    // Before retry window: nothing
    const empty = await store.claimRetryReady(a, now + 500);
    expect(empty).toHaveLength(0);
    // After retry window: claim it
    const claimed = await store.claimRetryReady(a, now + RETRY_BACKOFF_MS[1]! + 1);
    expect(claimed.map((r) => r.id)).toContain(id);
    const r = await store._getById(id);
    expect(r?.state).toBe("retrying");
  });

  it("never returns rows belonging to other agents", async () => {
    const a = ns();
    const b = ns();
    const idA = (await store.ingest(uem(a)))!;
    const idB = (await store.ingest(uem(b)))!;
    await store.markBatchSending([idA], newBatchId());
    await store.markBatchSending([idB], newBatchId());
    const now = 1_700_000_000_000;
    await store.markFailed(idA, "ea", now);
    await store.markFailed(idB, "eb", now);
    const claimed = await store.claimRetryReady(a, now + 600_000);
    const ids = claimed.map((r) => r.id);
    expect(ids).toContain(idA);
    expect(ids).not.toContain(idB);
  });

  it("does NOT return terminal (attempts >= MAX_ATTEMPTS) rows", async () => {
    const a = ns();
    const id = (await store.ingest(uem(a)))!;
    for (let i = 0; i < 5; i++) await store.markFailed(id, "x", 1);
    const claimed = await store.claimRetryReady(a, Date.now());
    expect(claimed.find((r) => r.id === id)).toBeUndefined();
  });

  it("two parallel claimRetryReady on same agent do not double-claim same row", async () => {
    const a = ns();
    // Seed many failed rows so we exercise the FOR UPDATE path repeatedly.
    const ids: number[] = [];
    for (let i = 0; i < 8; i++) {
      const id = (await store.ingest(uem(a, `r${i}`)))!;
      await store.markBatchSending([id], newBatchId());
      await store.markFailed(id, "x", 1);
      ids.push(id);
    }
    const now = Date.now() + 10 * 60_000;
    const [c1, c2] = await Promise.all([
      store.claimRetryReady(a, now, 16),
      store.claimRetryReady(a, now, 16),
    ]);
    const set1 = new Set(c1.map((r) => r.id));
    const set2 = new Set(c2.map((r) => r.id));
    for (const x of set1) expect(set2.has(x)).toBe(false);
    // Every seeded row landed in exactly one of the two claims.
    const union = new Set([...set1, ...set2]);
    for (const id of ids) expect(union.has(id)).toBe(true);
  });
});

describe("EventStore cursors", () => {
  it("get returns null when unset", async () => {
    const a = ns();
    expect(await store.getCursor(a, "gitea")).toBeNull();
  });

  it("set then get round-trips; upsert overwrites", async () => {
    const a = ns();
    await store.setCursor(a, "gitea", "2026-05-01T00:00:00Z");
    expect(await store.getCursor(a, "gitea")).toBe("2026-05-01T00:00:00Z");
    await store.setCursor(a, "gitea", "2026-05-02T00:00:00Z");
    expect(await store.getCursor(a, "gitea")).toBe("2026-05-02T00:00:00Z");
  });
});

describe("EventStore agent_kv (R10 session persistence)", () => {
  it("get returns null when unset", async () => {
    const a = ns();
    expect(await store.getKv(a, "acp_session_id")).toBeNull();
  });

  it("set then get round-trips; upsert overwrites", async () => {
    const a = ns();
    await store.setKv(a, "acp_session_id", "session-aaa-111");
    expect(await store.getKv(a, "acp_session_id")).toBe("session-aaa-111");
    await store.setKv(a, "acp_session_id", "session-bbb-222");
    expect(await store.getKv(a, "acp_session_id")).toBe("session-bbb-222");
  });

  it("isolates by (agent, key) — different agents do not collide", async () => {
    const a = ns();
    const b = ns();
    await store.setKv(a, "acp_session_id", "ses-A");
    await store.setKv(b, "acp_session_id", "ses-B");
    expect(await store.getKv(a, "acp_session_id")).toBe("ses-A");
    expect(await store.getKv(b, "acp_session_id")).toBe("ses-B");
  });

  it("delete removes only the requested key", async () => {
    const a = ns();
    await store.setKv(a, "acp_session_id", "x");
    await store.setKv(a, "other", "y");
    await store.deleteKv(a, "acp_session_id");
    expect(await store.getKv(a, "acp_session_id")).toBeNull();
    expect(await store.getKv(a, "other")).toBe("y");
  });
});

describe("EventStore.recoverSendingToPending", () => {
  it("scrubs only the requested agent's sending rows", async () => {
    const a = ns();
    const b = ns();
    const idA = (await store.ingest(uem(a)))!;
    const idB = (await store.ingest(uem(b)))!;
    await store.markBatchSending([idA], newBatchId());
    await store.markBatchSending([idB], newBatchId());
    const n = await store.recoverSendingToPending(a);
    expect(n).toBe(1);
    expect((await store._getById(idA))?.state).toBe("pending");
    expect((await store._getById(idB))?.state).toBe("sending");
  });
});
