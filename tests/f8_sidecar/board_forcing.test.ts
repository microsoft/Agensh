/**
 * f8_sidecar/board_forcing.test.ts — DeLM forced read/write in the dispatcher.
 *
 * Verifies the two structural properties ported from DeLM
 * (see mini-router/src/board_client.ts header):
 *
 *   FORCED READ  — the rendered shared context is pushed onto the channel as a
 *                  prompt prefix before every dispatch, so the agent sees peer
 *                  progress without calling a read tool.
 *   FORCED WRITE — a turn that publishes no gist triggers exactly one
 *                  follow-up prompt inviting one. It tolerates silence: a
 *                  placeholder gist is worse than no gist.
 *
 * Uses a fake fetch + fake channel; no MySQL, no containers.
 */
import { describe, it, expect } from "vitest";
import { BoardClient } from "../../mini-router/src/board_client.ts";

type FetchArgs = { url: string; init?: RequestInit };

/** Fake fetch that serves /read and /read_all from a scripted gist list. */
function makeFetch(opts: {
  rendered?: string;
  entriesByCall?: Array<Array<{ thread_id: string }>>;
  failRead?: boolean;
}) {
  const calls: FetchArgs[] = [];
  let readAllCall = 0;
  const impl = (async (url: string | URL, init?: RequestInit) => {
    const u = String(url);
    calls.push({ url: u, init });
    if (u.includes("/read_all")) {
      const entries = opts.entriesByCall?.[readAllCall] ?? [];
      readAllCall += 1;
      return new Response(JSON.stringify({ count: entries.length, entries }), { status: 200 });
    }
    if (u.includes("/read")) {
      if (opts.failRead) return new Response("boom", { status: 500 });
      return new Response(JSON.stringify({ rendered: opts.rendered ?? "" }), { status: 200 });
    }
    return new Response("{}", { status: 200 });
  }) as unknown as typeof fetch;
  return { impl, calls };
}

describe("BoardClient — forced read", () => {
  it("is disabled without a baseUrl, so dispatch is unchanged", async () => {
    const c = new BoardClient({ agent: "a1", boardIds: ["pbench-top"] });
    expect(c.enabled).toBe(false);
    expect(await c.renderForPrompt()).toBe("");
    expect(await c.countOwnGists()).toBeNull();
  });

  it("is disabled with a baseUrl but no boards", () => {
    const c = new BoardClient({ baseUrl: "http://b:8660", agent: "a1", boardIds: [] });
    expect(c.enabled).toBe(false);
  });

  it("renders admitted gists into a prompt block with peer-use guidance", async () => {
    const { impl } = makeFetch({ rendered: "[t/FACT +0.1m] reference exits 2 on bad flag" });
    const c = new BoardClient({
      baseUrl: "http://b:8660",
      agent: "planner",
      boardIds: ["pbench-top"],
      fetchImpl: impl,
    });
    const block = await c.renderForPrompt();
    expect(block).toContain("==== SHARED CONTEXT ====");
    expect(block).toContain("reference exits 2 on bad flag");
    // The guidance is what makes the block actionable rather than decorative.
    expect(block).toContain("do not repeat a path recorded as FAIL");
    expect(block).toContain("==== END SHARED CONTEXT ====");
  });

  it("labels each board when the agent belongs to several (hierarchical 2b)", async () => {
    const { impl } = makeFetch({ rendered: "[t/FACT +0m] x" });
    const c = new BoardClient({
      baseUrl: "http://b:8660",
      agent: "team1-lead",
      boardIds: ["pbench-top", "pbench-team1"],
      fetchImpl: impl,
    });
    const block = await c.renderForPrompt();
    expect(block).toContain("SHARED CONTEXT: pbench-top");
    expect(block).toContain("SHARED CONTEXT: pbench-team1");
  });

  it("still emits the block for an empty board (variant 1: board rides every batch)", async () => {
    // Deliberate change from the first cut, which skipped the prefix when the
    // board was empty. In the round-2 run every agent's single wake-up landed
    // before any peer had written, so the protocol never appeared in context
    // at all. An empty board is information: you are first.
    const { impl } = makeFetch({ rendered: "(no shared lessons yet)" });
    const c = new BoardClient({
      baseUrl: "http://b:8660",
      agent: "a1",
      boardIds: ["pbench-top"],
      fetchImpl: impl,
    });
    const block = await c.renderForPrompt();
    expect(block).toContain("==== SHARED CONTEXT ====");
    expect(block).toContain("you are the first to write here");
    expect(block).toContain("publish concrete findings");
  });

  it("still emits the block when the board service errors (never blocks dispatch)", async () => {
    const { impl } = makeFetch({ failRead: true });
    const c = new BoardClient({
      baseUrl: "http://b:8660",
      agent: "a1",
      boardIds: ["pbench-top"],
      fetchImpl: impl,
    });
    // Degrades to the empty-board form rather than throwing or blocking.
    const block = await c.renderForPrompt();
    expect(block).toContain("==== SHARED CONTEXT ====");
  });

  it("renders the task queue so a woken agent sees unclaimed work", async () => {
    // round-2: the planner enqueued 4 subtasks and no worker ever claimed one,
    // because nothing told them the queue was non-empty.
    const impl = (async (url: string | URL) => {
      const u = String(url);
      if (u.includes("/queue/")) {
        return new Response(JSON.stringify({
          counts: { pending: 2, claimed: 1, completed: 0 },
          tasks: [
            { task_id: "sub-core", state: "pending", description: "Produce src/main.c" },
            { task_id: "sub-sam", state: "pending", description: "Produce src/view.c" },
            { task_id: "sub-fa", state: "claimed", description: "faidx", claimed_by: "w3" },
            { task_id: "sub-old", state: "completed", description: "done already" },
          ],
        }), { status: 200 });
      }
      return new Response(JSON.stringify({ rendered: "" }), { status: 200 });
    }) as unknown as typeof fetch;
    const c = new BoardClient({
      baseUrl: "http://b:8660",
      agent: "w1",
      boardIds: ["pbench-top"],
      queueId: "pbench-top",
      fetchImpl: impl,
    });
    const q = await c.renderQueueForPrompt("pbench-top");
    expect(q).toContain("pending=2");
    expect(q).toContain("sub-core");
    expect(q).toContain("claimed by w3");
    expect(q).toContain("2 task(s) are unclaimed");
    expect(q).not.toContain("done already");   // completed rows are noise
  });

  it("batch prefix carries board and queue together", async () => {
    const impl = (async (url: string | URL) => {
      const u = String(url);
      if (u.includes("/queue/")) {
        return new Response(JSON.stringify({
          counts: { pending: 1, claimed: 0, completed: 0 },
          tasks: [{ task_id: "t1", state: "pending", description: "do a thing" }],
        }), { status: 200 });
      }
      return new Response(JSON.stringify({ rendered: "[t/FACT +0m] peer note" }), { status: 200 });
    }) as unknown as typeof fetch;
    const c = new BoardClient({
      baseUrl: "http://b:8660",
      agent: "w1",
      boardIds: ["pbench-top"],
      queueId: "pbench-top",
      fetchImpl: impl,
    });
    const p = await c.renderBatchPrefix();
    expect(p).toContain("peer note");
    expect(p).toContain("TASK QUEUE");
  });

  it("batch prefix is empty when the board is disabled (non-board profiles)", async () => {
    const c = new BoardClient({ agent: "a1", boardIds: ["pbench-top"] });
    expect(await c.renderBatchPrefix()).toBe("");
  });
});

describe("BoardClient — forced write", () => {
  it("counts only this agent's own gists", async () => {
    const { impl } = makeFetch({
      entriesByCall: [[
        { thread_id: "planner" },
        { thread_id: "worker1" },
        { thread_id: "planner" },
      ]],
    });
    const c = new BoardClient({
      baseUrl: "http://b:8660",
      agent: "planner",
      boardIds: ["pbench-top"],
      fetchImpl: impl,
    });
    expect(await c.countOwnGists()).toBe(2);
  });

  it("returns null on total board failure so no spurious nudge fires", async () => {
    const impl = (async () => {
      throw new Error("network down");
    }) as unknown as typeof fetch;
    const c = new BoardClient({
      baseUrl: "http://b:8660",
      agent: "a1",
      boardIds: ["pbench-top"],
      fetchImpl: impl,
    });
    expect(await c.countOwnGists()).toBeNull();
  });

  it("nudge names the board and the legal types, and asks for a CLAIM refresh", () => {
    const c = new BoardClient({
      baseUrl: "http://b:8660",
      agent: "a1",
      boardIds: ["pbench-team2"],
    });
    const n = c.buildForcedWriteNudge();
    expect(n).toContain("board `pbench-team2`");
    for (const t of ["FACT", "OBSERVED", "FAIL", "CLAIM", "PATCH_SUMMARY"]) {
      expect(n).toContain(t);
    }
    // The nudge used to demand a gist and offer `FACT (none)` as the escape.
    // On sweep_6.1 that produced 976 placeholder writes out of 4464 (21.8%),
    // almost all from idle reviewers correctly reporting they had nothing —
    // so the placeholder is still refused.
    expect(n).not.toContain("(none)");
    expect(n).toContain("Do NOT publish a placeholder");
    // But blessing silence outright was worse: on sweep_6.2/typst, worker3 went
    // quiet on the board for 108 minutes while writing a 3089-line interpreter,
    // and its lead recorded "worker3 MIA 60min" and reassigned the issue three
    // times, spawning two competing implementations and five discarded PRs.
    // A turn with no discovery is not a turn with no state — refresh the CLAIM.
    expect(n).not.toContain("silence is a valid turn");
    expect(n).toMatch(/refresh your `?CLAIM`?/i);
  });
});

describe("BoardClient consistent multi-board read", () => {
  /** Records every URL fetched and answers /snapshot with both boards. */
  function snapshotFetch(boards: Record<string, string>) {
    const urls: string[] = [];
    const impl = (async (url: string | URL) => {
      const u = String(url);
      urls.push(u);
      if (u.includes("/snapshot")) {
        return new Response(
          JSON.stringify({
            snapshot_at: 1,
            boards: Object.fromEntries(
              Object.entries(boards).map(([k, v]) => [k, { rendered: v }]),
            ),
          }),
          { status: 200 },
        );
      }
      return new Response(JSON.stringify({ rendered: "PER-BOARD-FALLBACK" }), { status: 200 });
    }) as unknown as typeof fetch;
    return { urls, impl };
  }

  it("reads N boards with ONE snapshot call, not N reads", async () => {
    const { urls, impl } = snapshotFetch({
      "pbench-top": "top: director says freeze the ABI",
      "pbench-team1": "team1: bgzf_read is the hot path",
    });
    const c = new BoardClient({
      baseUrl: "http://b:8660",
      agent: "team1-lead",
      boardIds: ["pbench-top", "pbench-team1"],
      fetchImpl: impl,
    });
    const out = await c.renderForPrompt();
    // Both boards present, from a single logical read point.
    expect(out).toContain("freeze the ABI");
    expect(out).toContain("bgzf_read is the hot path");
    expect(urls.filter((u) => u.includes("/snapshot"))).toHaveLength(1);
    expect(urls.filter((u) => u.includes("/read?"))).toHaveLength(0);
  });

  it("falls back to per-board reads when /snapshot is unavailable", async () => {
    // A router built against a newer board-service must still work against an
    // older one that has no /snapshot.
    const urls: string[] = [];
    const impl = (async (url: string | URL) => {
      const u = String(url);
      urls.push(u);
      if (u.includes("/snapshot")) return new Response("nope", { status: 404 });
      return new Response(JSON.stringify({ rendered: "legacy read path" }), { status: 200 });
    }) as unknown as typeof fetch;
    const c = new BoardClient({
      baseUrl: "http://b:8660",
      agent: "w1",
      boardIds: ["pbench-top", "pbench-team1"],
      fetchImpl: impl,
    });
    const out = await c.renderForPrompt();
    expect(out).toContain("legacy read path");
    expect(urls.filter((u) => u.includes("/read?"))).toHaveLength(2);
  });

  it("carries render_mode, role and step to the service", async () => {
    const { urls, impl } = snapshotFetch({ "pbench-top": "x" });
    const c = new BoardClient({
      baseUrl: "http://b:8660",
      agent: "lead",
      boardIds: ["pbench-top"],
      renderMode: "patch_clean_delayed_local",
      role: "planner",
      fetchImpl: impl,
    });
    c.setStep(9);
    await c.renderForPrompt();
    const u = urls[0]!;
    expect(u).toContain("render_mode=patch_clean_delayed_local");
    expect(u).toContain("role=planner");
    expect(u).toContain("step=9");
  });

  it("omits render_mode when unset so the service default wins", async () => {
    const { urls, impl } = snapshotFetch({ "pbench-top": "x" });
    const c = new BoardClient({
      baseUrl: "http://b:8660",
      agent: "w1",
      boardIds: ["pbench-top"],
      fetchImpl: impl,
    });
    await c.renderForPrompt();
    expect(urls[0]!).not.toContain("render_mode=");
  });
});
