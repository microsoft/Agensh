/**
 * pbench/dispatcher_serial.test.ts — only one dispatch may be in flight.
 *
 * WHY
 * Two independent loops drive the Dispatcher. main.ts:270 starts
 * runForever(), which ticks pending batches; main.ts:276 starts
 * retrySweeperLoop(), which at main.ts:369 calls dispatchSpecific() on rows
 * claimRetryReady() hands it. Both funnel into dispatchBatch() ->
 * channel.prompt() -> acp_socket_channel.ts conn.prompt({sessionId}) — and
 * nothing coordinated them. A grep of dispatcher.ts for mutex/lock/inflight/
 * busy/semaphore returned nothing; the "serial worker" in the file header was
 * only ever true of runForever on its own.
 *
 * The trigger is routine, not exotic:
 *   1. an agent goes silent past MINI_ROUTER_STUCK_MS (default 20 min) mid-turn
 *   2. watchSilence force-closes the connection and prompt() rejects
 *   3. dispatchBatch's catch marks those rows failed with a near-term retry
 *   4. runForever continues at once and picks up the NEXT pending batch
 *   5. within RETRY_SWEEP_MS (default 30s) the sweeper fires the retries into
 *      the same socket, while the batch from (4) is still streaming
 *
 * Three pieces of single-slot channel state corrupt when that happens:
 *   promptPrefix   (acp_socket_channel.ts:94-96) consumed once per prompt, so
 *                  one turn gets the other's rendered board and the other none
 *   lastUpdateAt   (:146) shared, so turn B's RX keeps turn A's silence
 *                  watchdog asleep — stuck detection dies exactly when two
 *                  turns overlap, which is the case it exists for
 *   close()        (:170) in sendText's catch tears the socket down for BOTH,
 *                  so one failure fails the other's whole batch
 *
 * A mutex around channel.prompt() alone would not fix it: dispatchBatch runs
 * markBatchSending -> prompt -> markBatchSent, and locking only the middle step
 * leaves the DB transitions racing. So the whole batch is serialised.
 *
 * These tests drive the real Dispatcher with fakes for state and channel and
 * assert on observed concurrency, not on the presence of a keyword.
 */
import { describe, expect, it } from "vitest";
import { Dispatcher } from "../../mini-router/src/dispatcher.js";

type Row = { id: number; payload: string };

/** Channel that records max observed concurrency and prompt ordering. */
function makeChannel() {
  let inFlight = 0;
  const seen = { max: 0, order: [] as string[] };
  return {
    seen,
    async prompt(payloads: string[]): Promise<{ stopReason: string }> {
      inFlight += 1;
      seen.max = Math.max(seen.max, inFlight);
      seen.order.push(`start:${payloads.join(",")}`);
      // Yield across several microtask+macrotask boundaries so a genuinely
      // concurrent caller has every chance to interleave.
      for (let i = 0; i < 5; i++) await new Promise((r) => setTimeout(r, 1));
      seen.order.push(`end:${payloads.join(",")}`);
      inFlight -= 1;
      return { stopReason: "end_turn" };
    },
  };
}

function makeState(pending: Row[][]) {
  const queue = [...pending];
  return {
    async nextPendingBatch(): Promise<Row[]> {
      return queue.shift() ?? [];
    },
    async markBatchSending(): Promise<number> {
      return 1;
    },
    async markBatchSent(): Promise<number> {
      return 1;
    },
    async markFailed(): Promise<null> {
      return null;
    },
  };
}

function makeDispatcher(channel: ReturnType<typeof makeChannel>, pending: Row[][]) {
  return new Dispatcher({
    agent: "test-agent",
    state: makeState(pending) as never,
    channel: channel as never,
    onLog: () => undefined,
  } as never);
}

describe("dispatcher serialisation", () => {
  it("never runs two dispatches at once when tick and the retry sweeper race", async () => {
    const channel = makeChannel();
    const d = makeDispatcher(channel, [[{ id: 1, payload: "tick-batch" }]]);

    // Exactly the production race: runForever's tick and the sweeper's
    // dispatchSpecific issued without awaiting the first.
    await Promise.all([
      d.tick(),
      d.dispatchSpecific([{ id: 2, payload: "retry-batch" }] as never),
    ]);

    expect(channel.seen.max).toBe(1);
  });

  it("completes each prompt before starting the next (no interleaving)", async () => {
    const channel = makeChannel();
    const d = makeDispatcher(channel, [[{ id: 1, payload: "A" }]]);

    await Promise.all([
      d.tick(),
      d.dispatchSpecific([{ id: 2, payload: "B" }] as never),
    ]);

    // Every start must be immediately followed by its own end.
    for (let i = 0; i < channel.seen.order.length; i += 2) {
      const start = channel.seen.order[i]!;
      const end = channel.seen.order[i + 1]!;
      expect(end).toBe(start.replace("start:", "end:"));
    }
  });

  it("a failing dispatch does not wedge the chain for the next one", async () => {
    // If the in-flight promise were stored without catching rejection, one
    // throw would poison every later dispatch (and surface as an unhandled
    // rejection). Prove the queue keeps draining.
    let calls = 0;
    const channel = {
      seen: { max: 0, order: [] as string[] },
      async prompt(): Promise<{ stopReason: string }> {
        calls += 1;
        if (calls === 1) throw new Error("boom: connection died mid-prompt");
        return { stopReason: "end_turn" };
      },
    };
    const d = makeDispatcher(channel as never, [[{ id: 1, payload: "A" }]]);

    const results = await Promise.allSettled([
      d.tick(),
      d.dispatchSpecific([{ id: 2, payload: "B" }] as never),
    ]);

    expect(calls).toBe(2); // the second dispatch still ran
    expect(results.some((r) => r.status === "fulfilled")).toBe(true);
  });
});
