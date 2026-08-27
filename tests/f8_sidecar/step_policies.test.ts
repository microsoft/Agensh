/**
 * f8_sidecar/step_policies.test.ts — the DeLM agent-loop behaviors that are
 * independent of the environment.
 *
 * These are the pieces that make a shared board change what an agent DOES,
 * rather than merely appear in its prompt: stop repeating yourself, react when
 * a peer already solved it, start from a different angle than your siblings,
 * and remember structurally rather than in prose.
 */
import { describe, it, expect } from "vitest";
import {
  NoProgressDetector,
  NO_PROGRESS_LIMIT,
  actionSignature,
  parsePeerPatches,
  peerPatchCheckpoint,
  strategyPrior,
  STRATEGY_PRIORS,
  compactMemory,
  renderCompactedMemory,
} from "../../mini-router/src/step_policies.ts";

describe("NoProgressDetector", () => {
  it("fires only after the limit of identical signatures", () => {
    const d = new NoProgressDetector();
    let fired = false;
    for (let i = 1; i < NO_PROGRESS_LIMIT; i++) {
      fired = d.observe("bash[completed]");
      expect(fired).toBe(false);
    }
    expect(d.observe("bash[completed]")).toBe(true);
  });

  it("resets when the agent does something different", () => {
    const d = new NoProgressDetector(3);
    d.observe("a");
    d.observe("a");
    expect(d.observe("b")).toBe(false); // progress → counter resets
    expect(d.consecutive).toBe(1);
    d.observe("b");
    expect(d.observe("b")).toBe(true);
  });

  it("ignores reasoning changes — only the action counts", () => {
    // The whole point: rewording an explanation while re-running the same
    // command is not progress.
    const d = new NoProgressDetector(3);
    const sig = actionSignature([{ name: "bash", status: "completed" }]);
    d.observe(sig);
    d.observe(sig);
    expect(d.observe(sig)).toBe(true);
  });

  it("treats a no-tool turn as a real signature", () => {
    const d = new NoProgressDetector(2);
    const sig = actionSignature([]);
    expect(sig).toBe("(no tools)");
    d.observe(sig);
    expect(d.observe(sig)).toBe(true);
  });
});

describe("peer patch checkpoint", () => {
  // Exactly the shape format_for_prompt emits (shared_lessons.py:1031):
  // "[t{thread_id}/PATCH_SUMMARY +{m}m] {content}{status suffix}" — no space
  // after the `t`.
  const board = [
    "[Patch summaries]",
    "[tw2/PATCH_SUMMARY +3.0m] files=src/a.c | idea=guard null | evidence=ran t1, PASSED [status=verified]",
    "[tw3/PATCH_SUMMARY +4.0m] files=src/b.c | idea=fix len | evidence=ran t2, PASSED [status=final,verified]",
    "[tw4/PATCH_SUMMARY +5.0m] files=src/c.c | idea=hunch | evidence=ran t3, PASSED [status=local_failures=2]",
    "[tw1/PATCH_SUMMARY +6.0m] files=src/d.c | idea=mine | evidence=ran t4, PASSED [status=verified]",
  ].join("\n");

  it("ranks final+verified above verified above the rest", () => {
    const ps = parsePeerPatches(board, "w1");
    expect(ps[0]!.thread).toBe("w3"); // final+verified wins
    expect(ps[0]!.rank).toBe(0);
    expect(ps[1]!.thread).toBe("w2");
  });

  it("excludes the viewer's own patches", () => {
    const ps = parsePeerPatches(board, "w1");
    expect(ps.some((p) => p.thread === "w1")).toBe(false);
  });

  it("drops invalidated patches — upstream re-renders those as FAIL", () => {
    const b =
      "[tw9/PATCH_SUMMARY +1.0m] files=x | idea=y | evidence=z [status=invalidated]";
    expect(parsePeerPatches(b, "w1")).toHaveLength(0);
  });

  it("produces a checkpoint naming the peer and the three legal responses", () => {
    const c = peerPatchCheckpoint(board, "w1");
    expect(c).toContain("PEER_PATCH_CHECKPOINT");
    expect(c).toContain("w3");
    expect(c).toContain("finalized AND verified");
    expect(c).toContain("verify it yourself");
    expect(c).toContain("publish a FAIL");
  });

  it("stays silent when there is nothing credible to interrupt for", () => {
    expect(peerPatchCheckpoint("", "w1")).toBe("");
    expect(peerPatchCheckpoint("[Shared lessons]\n[tw2/FACT +1m] hi", "w1")).toBe("");
    // Unranked AND repeatedly failing → not worth breaking the agent's flow.
    const weak =
      "[tw5/PATCH_SUMMARY +1m] files=x | idea=y | evidence=z [status=local_failures=3]";
    expect(peerPatchCheckpoint(weak, "w1")).toBe("");
  });

  it("surfaces the failure count when the best candidate has one", () => {
    const b =
      "[tw6/PATCH_SUMMARY +1m] files=x | idea=y | evidence=z [status=verified,local_failures=1]";
    expect(peerPatchCheckpoint(b, "w1")).toContain("1 recorded local failure");
  });
});

describe("strategy priors", () => {
  it("gives sibling workers different starting angles", () => {
    const names = ["team1-worker1", "team1-worker2", "team1-worker3", "team1-worker4"];
    const got = new Set(names.map(strategyPrior));
    // The anti-convergence property: four siblings must not all start the same way.
    expect(got.size).toBe(STRATEGY_PRIORS.length);
  });

  it("is stable for a given agent across calls", () => {
    expect(strategyPrior("team2-worker3")).toBe(strategyPrior("team2-worker3"));
  });

  it("still assigns a prior to an unnumbered name", () => {
    expect(STRATEGY_PRIORS).toContain(strategyPrior("planner"));
    expect(STRATEGY_PRIORS).toContain(strategyPrior(""));
  });
});

describe("deterministic memory compaction", () => {
  const recs = [
    { action: "bash[completed]", observation: "gcc src/bgzf.c -o x\nsrc/bgzf.c:44: error: implicit decl" },
    { action: "edit[completed]", observation: "wrote src/bgzf.c" },
    { action: "bash[completed]", observation: "tests/test_view.py FAILED with ValueError" },
    { action: "bash[completed]", observation: "tests/test_view.py PASSED (ValueError no longer raised)" },
    { action: "bash[completed]", observation: "SegfaultError in src/faidx.c" },
  ];

  it("extracts files, tests, exceptions and commands", () => {
    const c = compactMemory(recs);
    expect(c.editedFiles).toContain("src/bgzf.c");
    expect(c.failingTests.some((t) => t.includes("test_view"))).toBe(true);
    expect(c.exceptionClasses).toContain("ValueError");
    expect(c.commands).toContain("bash");
  });

  it("tracks which failures are still unresolved", () => {
    const c = compactMemory(recs);
    // ValueError was seen failing, then later passing → resolved.
    expect(c.unresolved).not.toContain("ValueError");
    // SegfaultError never appeared alongside a pass → still open.
    expect(c.unresolved).toContain("SegfaultError");
  });

  it("cannot invent content that was never observed", () => {
    // The reason for preferring this over an LLM summarizer.
    const c = compactMemory([{ action: "bash[completed]", observation: "hello" }]);
    expect(c.editedFiles).toHaveLength(0);
    expect(c.exceptionClasses).toHaveLength(0);
  });

  it("renders only the sections that have content", () => {
    expect(renderCompactedMemory(compactMemory([]))).toBe("");
    const out = renderCompactedMemory(compactMemory(recs));
    expect(out).toContain("Files touched");
    expect(out).toContain("STILL UNRESOLVED");
  });

  it("survives empty and malformed input", () => {
    expect(() => compactMemory([])).not.toThrow();
    expect(() =>
      compactMemory([{ action: "", observation: "" }]),
    ).not.toThrow();
  });
});
