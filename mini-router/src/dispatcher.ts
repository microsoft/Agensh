/**
 * Serialize queued events into worker turns, adding fresh board context first.
 * Delivery is acknowledged after a completed turn; failed prompts enter retry.
 */
import type { EventRow, EventStore } from "./state.ts";
import type { BoardClient } from "./board_client.ts";
import { randomUUID } from "node:crypto";
import { errorMessage, sleep } from "./runtime.ts";
import { groupMessagePayloads } from "./group_messages.ts";

export interface ACPChannel {
  prompt(uem: unknown[]): Promise<{ stopReason: string }>;
  promptText(text: string): Promise<{ stopReason: string }>;
  setPromptPrefix(prefix: string | null): void;
}

export interface DispatcherLogEntry {
  level: "warn" | "error";
  msg: string;
  batch?: string;
  err?: unknown;
}

export interface DispatcherOptions {
  agent: string;
  groupMessageDirectory: string;
  state: EventStore;
  channel: ACPChannel;
  onLog?: (entry: DispatcherLogEntry) => void;
  board: BoardClient;
}

const DEFAULT_LOG = (entry: DispatcherLogEntry): void => {
  const tag = entry.batch ? `[${entry.batch.slice(0, 8)}]` : "";
  console.error(`[dispatcher] ${entry.level} ${tag} ${entry.msg}`, entry.err ?? "");
};

export class Dispatcher {
  private wakers: Array<() => void> = [];
  private readonly log: (entry: DispatcherLogEntry) => void;
  private inFlight: Promise<unknown> = Promise.resolve();

  constructor(private opts: DispatcherOptions) {
    this.log = opts.onLog ?? DEFAULT_LOG;
  }

  tick(): Promise<{ dispatched: number }> {
    return this.serialize(() => this.tickLocked());
  }

  private async tickLocked(): Promise<{ dispatched: number }> {
    const batch = await this.opts.state.nextPendingBatch(this.opts.agent, 32);
    if (batch.length === 0) return { dispatched: 0 };

    let shown = new Set<number>();
    // Retire DMs already appended to an MCP result by the mid-turn notice shim.
    try {
      shown = await this.opts.state.claimShown(this.opts.agent, batch.map((r) => r.id), Date.now());
    } catch (e) {
      this.log({ level: "warn", msg: "shown-reconciliation failed; delivering batch as-is", err: e });
    }
    const pending = shown.size ? batch.filter((r) => !shown.has(r.id)) : batch;
    if (shown.size) {
      this.log({
        level: "warn",
        msg: `tick: ${shown.size} row(s) already delivered mid-turn by the shim; retired`,
      });
    }
    if (pending.length === 0) return { dispatched: 0 };

    this.log({ level: "warn", msg: `tick: dispatching batch of ${pending.length}` });
    await this.dispatchBatch(pending);
    return { dispatched: pending.length };
  }

  async dispatchSpecific(batch: EventRow[]): Promise<void> {
    if (batch.length === 0) return;
    await this.serialize(() => this.dispatchBatch(batch));
  }

  private serialize<T>(fn: () => Promise<T>): Promise<T> {
    // Normal dispatch and the retry sweeper must never prompt the session at once.
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
    while (true) {
      let dispatched = 0;
      try {
        ({ dispatched } = await this.tick());
      } catch (e) {
        this.log({ level: "error", msg: "tick failed", err: e });
      }
      if (dispatched > 0) continue;
      await this.waitForWakeOrTimeout(30_000);
    }
  }

  private waitForWakeOrTimeout(ms: number): Promise<void> {
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
      void sleep(ms).then(finish).catch(finish);
    });
  }

  private async dispatchBatch(batch: EventRow[]): Promise<void> {
    const batchId = randomUUID();
    const ids = batch.map((r) => r.id);
    const claimed = await this.opts.state.markBatchSending(ids, batchId);
    if (claimed === 0) return;
    const board = this.opts.board;
    const boardOn = board.enabled;
    let delivered = false;
    try {
      let gistsBefore: number | null = null;
      if (boardOn) {
        try {
          const prefix = await board.renderForPrompt();
          this.opts.channel.setPromptPrefix(prefix || null);
        } catch (e) {
          this.log({ level: "warn", msg: "board render failed; dispatching without shared context", err: e });
          this.opts.channel.setPromptPrefix(null);
        }
        gistsBefore = await board.latestOwnGistId();
      }

      const payloads = await groupMessagePayloads(batch, this.opts.groupMessageDirectory, this.opts.agent);
      await this.opts.channel.prompt(payloads);
      delivered = true;
      await this.opts.state.markBatchSent(batchId, Date.now());

      if (boardOn && gistsBefore !== null) {
        // Encourage useful publication without inventing a board entry for the agent.
        const gistsAfter = await board.latestOwnGistId();
        if (gistsAfter !== null && gistsAfter <= gistsBefore) {
          this.log({
            level: "warn",
            msg: `agent published no gist this turn (latest own gist G${gistsBefore} -> G${gistsAfter}); sending forced-write nudge`,
            batch: batchId,
          });
          try {
            this.opts.channel.setPromptPrefix(null);
            await this.opts.channel.promptText(board.buildForcedWriteNudge());
          } catch (e) {
            this.log({ level: "warn", msg: "forced-write nudge failed", batch: batchId, err: e });
          }
        }
      }
    } catch (err) {
      const msg = errorMessage(err);
      if (delivered) {
        // A bookkeeping failure after success must not put the turn back in retry.
        try {
          await this.opts.state.markBatchSent(batchId, Date.now());
        } catch (e2) {
          this.log({ level: "error", msg: `markBatchSent failed after delivery`, batch: batchId, err: e2 });
        }
        this.log({
          level: "error",
          msg: `post-delivery step failed (${batch.length} events): ${msg}`,
          batch: batchId,
          err,
        });
        return;
      }
      for (const r of batch) {
        try {
          await this.opts.state.markFailed(r.id, msg, Date.now());
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
