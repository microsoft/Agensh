/**
 * Dispatcher — single-agent serial worker draining events table → ACPChannel.
 *
 * R7 fixes from incident analysis:
 *   - onLog DEFAULTS to console.error (the 09:18 incident root cause was
 *     main.ts forgetting to wire onLog → silent failures for 6h).
 *   - On ACP failure, calls state.markFailed which auto-sets next_retry_at;
 *     the retry sweeper picks it up later.
 *   - state.markBatchSending also bumps attempts; markFailed bumps again.
 *     We intentionally accept the 2-step bump as a "claimed once" indicator;
 *     terminal at attempts >= MAX_ATTEMPTS (5) so worst case = 4 retries.
 *
 * Loop: tick() pulls pending batch → markBatchSending CAS → channel.prompt
 *       → markBatchSent on success / markFailed on error.
 */
import type { EventRow, EventStore } from "./state.ts";
import type { BoardClient } from "./board_client.ts";
import { randomUUID } from "node:crypto";

export interface ACPChannel {
  prompt(uem: unknown[]): Promise<{ stopReason: string }>;
  /** True at most once per compaction; reading clears it. Absent on channels that
   *  cannot observe compaction, where this degrades to no re-injection. */
  takeCompacted?(): boolean;
  /** Optional: send raw text (used for the forced-write follow-up prompt). */
  promptText?(text: string): Promise<{ stopReason: string }>;
  /** Optional: prefix spliced onto the next prompt's text (forced read). */
  setPromptPrefix?(prefix: string | null): void;
}

export interface DispatcherLogEntry {
  level: "warn" | "error";
  msg: string;
  batch?: string;
  err?: unknown;
}

export interface DispatcherOptions {
  agent: string;
  state: EventStore;
  channel: ACPChannel;
  /** Idle interval when nothing pending. Default 30s. */
  idleMs?: number;
  /** Cap on batch size. Default 32. */
  batchLimit?: number;
  signal?: AbortSignal;
  now?: () => number;
  sleep?: (ms: number, signal?: AbortSignal) => Promise<void>;
  batchId?: () => string;
  /** Logger hook. **Defaults to console.error.** Critical: never undefined. */
  onLog?: (entry: DispatcherLogEntry) => void;
  /**
   * DeLM shared-context forcing. When present and enabled, every dispatched
   * batch gets the rendered board spliced in front of it (forced read), and a
   * turn that publishes no gist gets one follow-up nudge (forced write).
   * Absent/disabled → dispatch behaves exactly as before.
   */
  board?: BoardClient;
  /**
   * Re-inject the board and any pending UEMs after the agent compacts its context.
   * **Default false — disabled.**
   *
   * The mechanism works (see the RE-INJECT block below) but lands AFTER the turn, because ACP
   * `session/prompt` is request-response and cannot be interleaved. Interrupting the turn
   * instead would abort whatever tool call is in flight — plausibly a build or a suite run —
   * and would arrive while the agent is still reorienting from the summary. Off until that
   * trade is settled; the detection and injection code stay so re-enabling is one flag.
   */
  reinjectAfterCompaction?: boolean;
}

/** Render re-injected UEM payloads as text for promptText(). The channel renders batches
 *  internally for prompt(), but promptText takes a string, so the post-compaction block
 *  formats them here in the same [event] shape the agent already knows. */
function renderPayloads(payloads: unknown[]): string {
  return payloads
    .map((p) => {
      const u = p as { event_id?: string; source?: string; kind?: string; summary?: string };
      if (!u || typeof u !== "object" || u.summary === undefined) return JSON.stringify(p);
      return [`[event]`, `event_id=${u.event_id}`, `source=${u.source}`, `kind=${u.kind}`,
              `summary: ${u.summary}`].join("\n");
    })
    .join("\n\n");
}

const DEFAULT_LOG = (entry: DispatcherLogEntry): void => {
  const tag = entry.batch ? `[${entry.batch.slice(0, 8)}]` : "";
  // eslint-disable-next-line no-console
  console.error(`[dispatcher] ${entry.level} ${tag} ${entry.msg}`, entry.err ?? "");
};

export class Dispatcher {
  private wakers: Array<() => void> = [];
  private readonly log: (entry: DispatcherLogEntry) => void;
  /**
   * Serialises every dispatch through one promise chain.
   *
   * Two independent loops reach this class: main.ts:270 runs runForever(), and
   * main.ts:276 runs retrySweeperLoop() which calls dispatchSpecific(). Nothing
   * coordinated them, so both could be inside channel.prompt() on the SAME
   * sessionId at once. Routine trigger: the stuck watchdog force-closes a
   * 20-minute-silent turn (MINI_ROUTER_STUCK_MS), those rows get
   * next_retry_at = now + backoff, runForever immediately picks up the next
   * pending batch, and <=RETRY_SWEEP_MS (30s) later the sweeper fires the
   * retries into the same socket.
   *
   * Three pieces of single-slot channel state corrupt when that happens:
   *   promptPrefix  consumed by whichever prompt lands first, so one turn gets
   *                 the other's rendered board and the other gets none
   *   lastUpdateAt  shared, so turn B's RX keeps turn A's silence watchdog
   *                 asleep -- stuck detection dies exactly when it is needed
   *   close()       in sendText's catch tears down the socket for BOTH, so one
   *                 failure fails the other's whole batch
   *
   * A mutex around channel.prompt() alone is not enough: dispatchBatch does
   * markBatchSending -> prompt -> markBatchSent, and locking only the middle
   * leaves the DB transitions racing. Serialise the whole batch instead.
   * Retries queue behind the live turn, which is the intended semantics.
   */
  private inFlight: Promise<unknown> = Promise.resolve();

  constructor(private opts: DispatcherOptions) {
    // R7 09:18 incident regression: never let onLog be undefined.
    this.log = opts.onLog ?? DEFAULT_LOG;
  }

  async tick(): Promise<{ dispatched: number }> {
    const limit = this.opts.batchLimit ?? 32;
    const batch = await this.opts.state.nextPendingBatch(this.opts.agent, limit);
    if (batch.length === 0) return { dispatched: 0 };
    this.log({ level: "warn", msg: `tick: dispatching batch of ${batch.length}` });
    await this.serialize(() => this.dispatchBatch(batch));
    return { dispatched: batch.length };
  }

  /** Dispatch a specific batch (used by retry sweeper). The batch
   *  rows are typically in 'retrying' state from claimRetryReady; we
   *  re-mark them sending under a fresh batch_id so markBatchSent's
   *  CAS works. (markBatchSending accepts pending|retrying.) */
  async dispatchSpecific(batch: EventRow[]): Promise<void> {
    if (batch.length === 0) return;
    await this.serialize(() => this.dispatchBatch(batch));
  }

  /** Run fn after any dispatch already in flight, whether it settles or throws. */
  private serialize<T>(fn: () => Promise<T>): Promise<T> {
    const run = this.inFlight.then(fn, fn);
    this.inFlight = run.then(
      () => undefined,
      () => undefined,
    );
    return run;
  }

  wake(): void {
    const ws = this.wakers;
    this.wakers = [];
    for (const w of ws) w();
  }

  async runForever(): Promise<void> {
    const idleMs = this.opts.idleMs ?? 30_000;
    const sleep = this.opts.sleep ?? defaultSleep;
    while (!this.opts.signal?.aborted) {
      let dispatched = 0;
      try {
        ({ dispatched } = await this.tick());
      } catch (e) {
        this.log({ level: "error", msg: "tick failed", err: e });
      }
      if (dispatched > 0) continue;
      await this.waitForWakeOrTimeout(sleep, idleMs);
    }
  }

  private waitForWakeOrTimeout(
    sleep: (ms: number, signal?: AbortSignal) => Promise<void>,
    ms: number,
  ): Promise<void> {
    // R10.1: previously the `finish` closure was pushed into this.wakers
    // but never spliced back out on the timeout path. wake() drains the
    // array (so it doesn't leak when wake fires first), but if the sleep
    // timeout fires first the closure stays in this.wakers forever and
    // gets called by every subsequent wake(). Over hours this caused
    // resolve()-on-already-resolved-promise spam + memory growth.
    return new Promise<void>((resolve) => {
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        const idx = this.wakers.indexOf(finish);
        if (idx >= 0) this.wakers.splice(idx, 1);
        resolve();
      };
      this.wakers.push(finish);
      void sleep(ms, this.opts.signal).then(finish).catch(finish);
    });
  }

  private async dispatchBatch(batch: EventRow[]): Promise<void> {
    const now = this.opts.now ?? Date.now;
    const batchId = (this.opts.batchId ?? randomUUID)();
    const ids = batch.map((r) => r.id);
    const claimed = await this.opts.state.markBatchSending(ids, batchId);
    if (claimed === 0) return; // already claimed by another tick
    const board = this.opts.board;
    const boardOn = Boolean(board?.enabled);
    try {
      // ---- FORCED READ (DeLM §3.1) --------------------------------------
      // The board (and the task queue) travel with every dispatched UEM
      // batch, so an agent sees accumulated peer progress without calling a
      // read tool. Note the cadence difference from upstream: DeLM owns its
      // agent loop and re-renders per LLM step, whereas copilot-CLI owns
      // ours and we can only inject per inbound batch. Board failure
      // degrades to no prefix.
      let gistsBefore: number | null = null;
      if (boardOn) {
        try {
          const prefix = await board!.renderBatchPrefix();
          this.opts.channel.setPromptPrefix?.(prefix || null);
        } catch (e) {
          this.log({ level: "warn", msg: "board render failed; dispatching without shared context", err: e });
          this.opts.channel.setPromptPrefix?.(null);
        }
        gistsBefore = await board!.countOwnGists();
      }

      await this.opts.channel.prompt(batch.map((r) => r.payload));
      await this.opts.state.markBatchSent(batchId, now());

      // ---- RE-INJECT AFTER COMPACTION -------------------------------------
      // A compaction folds the transcript into a summary MID-turn, so the board prefix and
      // the batch that opened the turn survive only as paraphrase. Put both back now, while
      // the batch mutex still holds: prompting from the session-update callback would race
      // the turn that is still finishing, which this file documents as corrupting both. The
      // next tick re-renders the board anyway, but only if another event arrives -- with an
      // idle queue the agent would keep working blind.
      // takeCompacted() is called even when disabled: the flag is read-and-clear, so leaving
      // it set would fire a stale re-injection the moment this is switched on.
      const didCompact = this.opts.channel.takeCompacted?.() ?? false;
      if (didCompact && this.opts.reinjectAfterCompaction && this.opts.channel.promptText) {
        const parts: string[] = [];
        if (boardOn) {
          try {
            const fresh = await board!.renderForPrompt();
            if (fresh) parts.push(fresh);
          } catch (e) {
            this.log({ level: "warn", msg: "post-compaction board render failed", batch: batchId, err: e });
          }
        }
        // "if there is a waiting message": claim what is pending so it arrives now rather
        // than a tick later. An empty queue contributes nothing -- a bare nudge would spend
        // a turn on no content.
        let reCount = 0;
        try {
          const waiting = await this.opts.state.nextPendingBatch(this.opts.agent, this.opts.batchLimit ?? 32);
          if (waiting.length > 0) {
            const reBatch = `${batchId}-postcompact`;
            if ((await this.opts.state.markBatchSending(waiting.map((r) => r.id), reBatch)) > 0) {
              reCount = waiting.length;
              parts.push(renderPayloads(waiting.map((r) => r.payload)));
              await this.opts.state.markBatchSent(reBatch, now());
            }
          }
        } catch (e) {
          this.log({ level: "warn", msg: "post-compaction pending fetch failed", batch: batchId, err: e });
        }
        if (parts.length > 0) {
          this.log({ level: "warn", msg: `re-injecting after compaction (board=${boardOn}, uems=${reCount})`, batch: batchId });
          try {
            this.opts.channel.setPromptPrefix?.(null);
            await this.opts.channel.promptText(parts.join("\n\n"));
          } catch (e) {
            this.log({ level: "warn", msg: "post-compaction re-injection failed", batch: batchId, err: e });
          }
        }
      }

      // ---- FORCED WRITE (DeLM §3.2) -------------------------------------
      // Upstream replays any turn whose response omits the NOTE section. We
      // can't reject a completed copilot turn, so we detect "published
      // nothing" and send exactly one follow-up demanding a gist. Skipped
      // when we couldn't read the count (null) so a board outage never
      // produces spurious nudges.
      if (boardOn && gistsBefore !== null && this.opts.channel.promptText) {
        const gistsAfter = await board!.countOwnGists();
        if (gistsAfter !== null && gistsAfter <= gistsBefore) {
          this.log({
            level: "warn",
            msg: `agent published no gist this turn (${gistsBefore} -> ${gistsAfter}); sending forced-write nudge`,
            batch: batchId,
          });
          try {
            this.opts.channel.setPromptPrefix?.(null);
            await this.opts.channel.promptText(board!.buildForcedWriteNudge());
          } catch (e) {
            this.log({ level: "warn", msg: "forced-write nudge failed", batch: batchId, err: e });
          }
        }
      }
    } catch (err) {
      const msg = errMsg(err);
      for (const r of batch) {
        try {
          await this.opts.state.markFailed(r.id, msg, now());
        } catch (e2) {
          this.log({
            level: "error",
            msg: `markFailed failed for id=${r.id}`,
            err: e2,
          });
        }
      }
      this.log({
        level: "error",
        msg: `acp prompt failed (${batch.length} events): ${msg}`,
        batch: batchId,
        err,
      });
    }
  }
}

function errMsg(e: unknown): string {
  if (e instanceof Error) return e.message;
  try {
    return JSON.stringify(e);
  } catch {
    return String(e);
  }
}

function defaultSleep(ms: number, signal?: AbortSignal): Promise<void> {
  // R10.1 fix: previously addEventListener without { once: true } and no
  // explicit removal on the timeout path → leaked one listener per dispatch
  // backoff. Dispatcher loop calls this on every batch, so a long-running
  // router accumulated thousands of abort listeners (MaxListenersExceededWarning).
  return new Promise((resolve) => {
    if (!signal) {
      setTimeout(resolve, ms);
      return;
    }
    const onAbort = () => {
      clearTimeout(t);
      signal.removeEventListener("abort", onAbort);
      resolve();
    };
    const t = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal.addEventListener("abort", onAbort, { once: true });
  });
}
