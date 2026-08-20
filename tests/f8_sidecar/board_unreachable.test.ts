/**
 * f8_sidecar/board_unreachable.test.ts — an unreachable board must not be
 * rendered as an EMPTY board.
 *
 * WHY
 * readBoards() catches every fetch failure and falls back; when both /snapshot
 * and the per-board /read fail, it returns an empty map. renderForPrompt()
 * cannot tell that apart from a board nobody has written to yet, so it emits:
 *
 *     (nothing published yet — you are the first to write here)
 *     Nothing has been published yet. Whatever you discover this turn is
 *     what your peers will see, so publish concrete findings rather than plans.
 *
 * That is not a degraded message — it is an affirmative, confident claim that
 * the agent is first. Observed live: when sweep 6.8's s68f agents resumed after
 * the host recovered, all five were told the board was empty while 180 KB of
 * peers' gists sat in board_gists.ibd on disk. The team's accumulated context
 * was silently discarded and four workers restarted from nothing.
 *
 * The crash triggered it, but nothing about it is crash-specific: a board-service
 * restart, a slow start, or one dropped request produces the same lie.
 *
 * An unreachable board must say so, so the agent knows its view is incomplete
 * rather than believing it is authoritative.
 */
import { describe, it, expect } from "vitest";
import { BoardClient } from "../../mini-router/src/board_client.ts";

function client(fetchImpl: any) {
  return new BoardClient({
    baseUrl: "http://board:8080",
    agent: "worker1",
    boardIds: ["team1"],
    fetchImpl,
    log: () => {},
  } as any);
}

const unreachable = async () => {
  throw new Error("ECONNREFUSED");
};
const http500 = async () => new Response("boom", { status: 500 });
const emptyOk = async (url: string | URL) =>
  String(url).includes("/snapshot")
    ? new Response(JSON.stringify({ boards: { team1: { rendered: "" } } }), { status: 200 })
    : new Response(JSON.stringify({ rendered: "" }), { status: 200 });
const contentOk = async (url: string | URL) =>
  String(url).includes("/snapshot")
    ? new Response(JSON.stringify({ boards: { team1: { rendered: "FACT: parser is LL(1)" } } }), { status: 200 })
    : new Response(JSON.stringify({ rendered: "FACT: parser is LL(1)" }), { status: 200 });

describe("board unreachable vs board empty", () => {
  it("does NOT claim the agent is first when the board cannot be reached", async () => {
    const out = await client(unreachable).renderForPrompt();
    expect(out).not.toContain("you are the first to write here");
    expect(out).not.toContain("Nothing has been published yet");
  });

  it("says the board was unreachable, so the agent knows its view is incomplete", async () => {
    const out = await client(unreachable).renderForPrompt();
    expect(out.toLowerCase()).toMatch(/could not|unreachable|unavailable/);
  });

  it("treats a 500 the same as a connection refusal", async () => {
    const out = await client(http500).renderForPrompt();
    expect(out).not.toContain("you are the first to write here");
    expect(out.toLowerCase()).toMatch(/could not|unreachable|unavailable/);
  });

  it("still reports a genuinely empty board as empty", async () => {
    const out = await client(emptyOk).renderForPrompt();
    expect(out).toContain("you are the first to write here");
    expect(out.toLowerCase()).not.toMatch(/could not|unreachable|unavailable/);
  });

  it("renders real content unchanged", async () => {
    const out = await client(contentOk).renderForPrompt();
    expect(out).toContain("FACT: parser is LL(1)");
    expect(out).not.toContain("you are the first to write here");
    expect(out.toLowerCase()).not.toMatch(/could not|unreachable|unavailable/);
  });

  it("keeps the SHARED CONTEXT envelope even when unreachable", async () => {
    // The dispatcher and the agent prompt both key off this envelope; dropping
    // it on failure would change the shape of the turn, not just its content.
    const out = await client(unreachable).renderForPrompt();
    expect(out).toContain("SHARED CONTEXT");
    expect(out).toContain("END SHARED CONTEXT");
  });
});
