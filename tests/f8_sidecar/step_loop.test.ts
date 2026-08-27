/**
 * f8_sidecar/step_loop.test.ts — variant 2 (router owns the agent loop).
 *
 * Covers the three pieces that make a DeLM-style step loop possible on top of
 * copilot-CLI:
 *   TurnObserver — rebuild what a turn did from session/update notifications,
 *                  since (unlike DeLM) we do not execute the tools ourselves
 *   StepMemory   — carry history in the prompt, since each step runs against a
 *                  fresh session with no conversation to remember it
 *   StepLoop     — the loop itself: fresh prompt per step, board every time
 */
import { describe, it, expect } from "vitest";
import { TurnObserver, renderObservation } from "../../mini-router/src/turn_observer.ts";
import { StepMemory, truncateMiddle } from "../../mini-router/src/step_memory.ts";
import { StepLoop } from "../../mini-router/src/step_loop.ts";
import { BoardClient } from "../../mini-router/src/board_client.ts";

const upd = (u: Record<string, unknown>) => ({ update: u });

describe("TurnObserver", () => {
  it("captures assistant text and drops reasoning chunks", () => {
    const o = new TurnObserver();
    o.observe(upd({ sessionUpdate: "agent_thought_chunk", content: { type: "text", text: "hmm maybe" } }));
    o.observe(upd({ sessionUpdate: "agent_message_chunk", content: { type: "text", text: "Running " } }));
    o.observe(upd({ sessionUpdate: "agent_message_chunk", content: { type: "text", text: "the tests." } }));
    const s = o.summary();
    expect(s.message).toBe("Running the tests.");
    // Replaying a model's own reasoning back at it entrenches mistakes.
    expect(s.message).not.toContain("hmm maybe");
  });

  it("pairs tool calls with their results", () => {
    const o = new TurnObserver();
    o.observe(upd({ sessionUpdate: "tool_call", toolCallId: "c1", title: "bash", status: "pending" }));
    o.observe(upd({
      sessionUpdate: "tool_call_update", toolCallId: "c1", status: "completed",
      content: { type: "text", text: "3 files changed" },
    }));
    const s = o.summary();
    expect(s.tools).toHaveLength(1);
    expect(s.tools[0]!.name).toBe("bash");
    expect(s.tools[0]!.status).toBe("completed");
    expect(s.tools[0]!.output).toContain("3 files changed");
  });

  it("keeps a recent window but reports the true total", () => {
    const o = new TurnObserver();
    for (let i = 0; i < 20; i++) {
      o.observe(upd({ sessionUpdate: "tool_call", toolCallId: `c${i}`, title: `tool${i}`, status: "completed" }));
    }
    const s = o.summary();
    expect(s.toolCallCount).toBe(20);
    expect(s.tools.length).toBeLessThanOrEqual(8);
    expect(s.tools[s.tools.length - 1]!.name).toBe("tool19");   // newest retained
  });

  it("ignores malformed updates rather than throwing", () => {
    const o = new TurnObserver();
    expect(() => {
      o.observe(undefined);
      o.observe({});
      o.observe(upd({ sessionUpdate: "tool_call_update", toolCallId: "nope" }));  // no matching call
      o.observe("garbage" as unknown);
    }).not.toThrow();
    expect(o.summary().tools).toHaveLength(0);
  });

  it("renders an observation a next step can act on", () => {
    const o = new TurnObserver();
    o.observe(upd({ sessionUpdate: "agent_message_chunk", content: { type: "text", text: "built ok" } }));
    o.observe(upd({ sessionUpdate: "tool_call", toolCallId: "c1", title: "make", status: "completed" }));
    const text = renderObservation(o.summary(), "end_turn");
    expect(text).toContain("==== LAST STEP ====");
    expect(text).toContain("built ok");
    expect(text).toContain("make [completed]");
    expect(text).toContain("stop_reason=end_turn");
  });

  it("says so explicitly when a step did nothing", () => {
    const text = renderObservation(new TurnObserver().summary(), "end_turn");
    expect(text).toContain("no tool calls and no output");
  });
});

describe("StepMemory", () => {
  it("reports None when empty", () => {
    expect(new StepMemory().asText()).toBe("None");
  });

  it("keeps records verbatim below the compression threshold", () => {
    const m = new StepMemory({ maxMemory: 8, keepRecent: 3 });
    for (let i = 1; i <= 5; i++) m.add({ step: i, action: `act${i}`, observation: `obs${i}` });
    const t = m.asText();
    expect(m.size).toBe(5);
    expect(t).toContain("act1");
    expect(t).toContain("act5");
    expect(t).not.toContain("[Summary of earlier steps]");
  });

  it("folds older records into a summary and keeps keepRecent raw (upstream policy)", () => {
    const m = new StepMemory({ maxMemory: 8, keepRecent: 3 });
    for (let i = 1; i <= 8; i++) m.add({ step: i, action: `act${i}`, observation: `obs${i}` });
    const t = m.asText();
    expect(m.size).toBe(3);                      // only keepRecent survive raw
    expect(t).toContain("[Summary of earlier steps]");
    expect(t).toContain("Steps 1-5");            // the folded range
    expect(t).toContain("act8");                 // newest still raw
    expect(t).not.toContain("obs1");             // old observation dropped
  });

  it("accumulates successive summaries rather than replacing them", () => {
    const m = new StepMemory({ maxMemory: 4, keepRecent: 1 });
    for (let i = 1; i <= 12; i++) m.add({ step: i, action: `act${i}`, observation: `obs${i}` });
    const t = m.asText();
    expect(t).toContain("Steps 1-3");
    expect(t.match(/Steps \d+-\d+/g)!.length).toBeGreaterThan(1);
  });

  it("truncateMiddle keeps both ends", () => {
    const s = "A".repeat(100) + "MIDDLE" + "Z".repeat(100);
    const out = truncateMiddle(s, 60);
    expect(out.startsWith("A")).toBe(true);
    expect(out.endsWith("Z")).toBe(true);
    expect(out).toContain("chars elided");
    expect(out).not.toContain("MIDDLE");
  });
});

describe("StepLoop", () => {
  /** Channel that records prompts and replies with a scripted turn. */
  function fakeChannel(script: Array<{ message?: string; tools?: string[] }>) {
    const prompts: string[] = [];
    let i = 0;
    return {
      prompts,
      channel: {
        async promptStep(text: string) {
          prompts.push(text);
          const s = script[Math.min(i++, script.length - 1)] ?? {};
          return {
            stopReason: "end_turn",
            summary: {
              message: s.message ?? "",
              tools: (s.tools ?? []).map((n) => ({ name: n, status: "completed" })),
              toolCallCount: (s.tools ?? []).length,
            },
          };
        },
      },
    };
  }

  it("runs until the agent says DONE", async () => {
    const { channel, prompts } = fakeChannel([
      { tools: ["bash"] },
      { tools: ["bash"] },
      { message: "all verified. DONE" },
    ]);
    const loop = new StepLoop({ agent: "w1", channel, task: "build it", maxSteps: 20 });
    const r = await loop.run();
    expect(r.reason).toBe("done");
    expect(r.steps).toBe(3);
    expect(prompts).toHaveLength(3);
  });

  it("stops at the step budget", async () => {
    const { channel } = fakeChannel([{ tools: ["bash"] }]);
    const loop = new StepLoop({ agent: "w1", channel, task: "t", maxSteps: 4 });
    const r = await loop.run();
    expect(r.reason).toBe("max_steps");
    expect(r.steps).toBe(4);
  });

  it("stops at the deadline without starting another step", async () => {
    const { channel, prompts } = fakeChannel([{ tools: ["bash"] }]);
    let t = 1000;
    const loop = new StepLoop({
      agent: "w1", channel, task: "t", maxSteps: 50,
      now: () => (t += 500),          // each check advances the clock
      deadlineMs: 2000,
    });
    const r = await loop.run();
    expect(r.reason).toBe("deadline");
    expect(prompts.length).toBeLessThan(50);
  });

  it("rebuilds the prompt each step, carrying memory and the last observation", async () => {
    const { channel, prompts } = fakeChannel([
      { tools: ["grep"], message: "searched" },
      { message: "DONE" },
    ]);
    const loop = new StepLoop({ agent: "w1", channel, task: "find the bug", maxSteps: 10 });
    await loop.run();
    // Step 1: no history yet.
    expect(prompts[0]).toContain("find the bug");
    expect(prompts[0]).toContain("Step 1/10");
    expect(prompts[0]).toContain("first step");
    // Step 2: the previous step is now visible as memory + observation.
    expect(prompts[1]).toContain("Step 2/10");
    expect(prompts[1]).toContain("WHAT YOU HAVE DONE SO FAR");
    expect(prompts[1]).toContain("grep");
    expect(prompts[1]).toContain("searched");
  });

  it("splices the board into every step's prompt", async () => {
    const impl = (async (url: string | URL) => {
      if (String(url).includes("/queue/")) return new Response("{}", { status: 200 });
      return new Response(JSON.stringify({ rendered: "[t/FACT +0m] peer found X" }), { status: 200 });
    }) as unknown as typeof fetch;
    const board = new BoardClient({
      baseUrl: "http://b:8660", agent: "w1", boardIds: ["pbench-top"], fetchImpl: impl,
    });
    const { channel, prompts } = fakeChannel([{ tools: ["a"] }, { tools: ["b"] }, { message: "DONE" }]);
    const loop = new StepLoop({ agent: "w1", channel, board, task: "t", maxSteps: 10 });
    await loop.run();
    // This is the property the whole variant exists for.
    expect(prompts).toHaveLength(3);
    for (const p of prompts) expect(p).toContain("peer found X");
  });

  it("survives a failing step and lets the next one see the error", async () => {
    let calls = 0;
    const channel = {
      async promptStep(_t: string) {
        calls++;
        if (calls === 1) throw new Error("acp exploded");
        return {
          stopReason: "end_turn",
          summary: { message: "DONE", tools: [], toolCallCount: 0 },
        };
      },
    };
    const loop = new StepLoop({ agent: "w1", channel, task: "t", maxSteps: 5 });
    const r = await loop.run();
    expect(r.reason).toBe("done");
    expect(calls).toBe(2);          // did not abort on the failure
  });

  it("warns when the step budget is nearly gone", async () => {
    const { channel, prompts } = fakeChannel([{ tools: ["x"] }]);
    const loop = new StepLoop({ agent: "w1", channel, task: "t", maxSteps: 3 });
    await loop.run();
    expect(prompts[prompts.length - 1]).toContain("nearly out of steps");
  });

  it("uses the claimed queue task as the task text (upstream: planner-authored)", async () => {
    // Upstream never gives a worker a static role task: task_instruction is
    // what the planner passed to delegate_task. The queue assignment is our
    // analogue, so it must win over the standing task text.
    const impl = (async (url: string | URL) => {
      const u = String(url);
      if (u.includes("/queue/")) {
        return new Response(JSON.stringify({
          counts: { pending: 0, claimed: 1, completed: 0 },
          tasks: [{ task_id: "sub-faidx", state: "claimed", claimed_by: "w1",
                    description: "Produce src/faidx.c" }],
        }), { status: 200 });
      }
      return new Response(JSON.stringify({ rendered: "" }), { status: 200 });
    }) as unknown as typeof fetch;
    const board = new BoardClient({
      baseUrl: "http://b:8660", agent: "w1", boardIds: ["pbench-top"],
      queueId: "pbench-top", fetchImpl: impl,
    });
    const { channel, prompts } = fakeChannel([{ message: "DONE" }]);
    const loop = new StepLoop({
      agent: "w1", channel, board, queueId: "pbench-top",
      task: "generic fallback text", maxSteps: 5,
    });
    await loop.run();
    expect(prompts[0]).toContain("You claimed this from the queue");
    expect(prompts[0]).toContain("sub-faidx: Produce src/faidx.c");
    expect(prompts[0]).not.toContain("generic fallback text");
  });

  it("falls back to the standing task when holding no assignment", async () => {
    const impl = (async (url: string | URL) => {
      if (String(url).includes("/queue/")) {
        return new Response(JSON.stringify({ counts: {}, tasks: [] }), { status: 200 });
      }
      return new Response(JSON.stringify({ rendered: "" }), { status: 200 });
    }) as unknown as typeof fetch;
    const board = new BoardClient({
      baseUrl: "http://b:8660", agent: "w1", boardIds: ["pbench-top"],
      queueId: "pbench-top", fetchImpl: impl,
    });
    const { channel, prompts } = fakeChannel([{ message: "DONE" }]);
    const loop = new StepLoop({
      agent: "w1", channel, board, queueId: "pbench-top",
      task: "rebuild samtools from the reference binary", maxSteps: 5,
    });
    await loop.run();
    expect(prompts[0]).toContain("rebuild samtools from the reference binary");
  });

  it("honors an abort signal", async () => {
    const { channel } = fakeChannel([{ tools: ["x"] }]);
    const ac = new AbortController();
    ac.abort();
    const loop = new StepLoop({ agent: "w1", channel, task: "t", maxSteps: 10 });
    const r = await loop.run(ac.signal);
    expect(r.reason).toBe("aborted");
    expect(r.steps).toBe(0);
  });

  it("stops an agent that keeps repeating the same action", async () => {
    // Without this a stuck agent re-runs one command until the budget is gone.
    const { channel, prompts } = fakeChannel([{ tools: ["bash"] }]);
    const loop = new StepLoop({
      agent: "w1", channel, task: "t", maxSteps: 100, noProgressLimit: 4,
    });
    const r = await loop.run();
    expect(r.reason).toBe("no_progress");
    expect(r.steps).toBe(4);
    expect(prompts.length).toBe(4);        // did not burn all 100
  });

  it("does not stop an agent that keeps varying its actions", async () => {
    const { channel } = fakeChannel([
      { tools: ["a"] }, { tools: ["b"] }, { tools: ["c"] }, { message: "DONE" },
    ]);
    const loop = new StepLoop({
      agent: "w1", channel, task: "t", maxSteps: 20, noProgressLimit: 3,
    });
    expect((await loop.run()).reason).toBe("done");
  });

  it("gives each agent a strategy prior, and different ones to siblings", async () => {
    const runFor = async (agent: string) => {
      const { channel, prompts } = fakeChannel([{ message: "DONE" }]);
      await new StepLoop({ agent, channel, task: "t", maxSteps: 3 }).run();
      return prompts[0]!;
    };
    const p1 = await runFor("team1-worker1");
    const p2 = await runFor("team1-worker2");
    expect(p1).toContain("==== STRATEGY ====");
    expect(p2).toContain("==== STRATEGY ====");
    // The anti-convergence property, end to end.
    expect(p1).not.toBe(p2);
  });

  it("interrupts with a peer checkpoint when a peer has a verified fix", async () => {
    const peer =
      "[tw2/PATCH_SUMMARY +1.0m] files=src/a.c | idea=guard | evidence=ran t1, PASSED [status=final,verified]";
    const impl = (async (url: string | URL) => {
      if (String(url).includes("/queue/")) return new Response("{}", { status: 200 });
      return new Response(
        JSON.stringify({ boards: { "pbench-top": { rendered: peer } } }),
        { status: 200 },
      );
    }) as unknown as typeof fetch;
    const board = new BoardClient({
      baseUrl: "http://b:8660", agent: "w1", boardIds: ["pbench-top"], fetchImpl: impl,
    });
    const { channel, prompts } = fakeChannel([{ tools: ["grep"] }, { message: "DONE" }]);
    const loop = new StepLoop({ agent: "w1", channel, board, task: "t", maxSteps: 5 });
    await loop.run();
    // The checkpoint rides in the NEXT step's prompt via memory/observation.
    expect(prompts[1]).toContain("PEER_PATCH_CHECKPOINT");
    expect(prompts[1]).toContain("w2");
  });
});
