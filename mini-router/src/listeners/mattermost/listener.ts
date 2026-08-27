/**
 * MattermostListener — wraps MattermostWS + ingests UEM into the events
 * store. Parallel to listeners/gitea/listener.ts.
 *
 * Lifecycle:
 *   run({signal}) — start ws driver; for each event call mapper + ingest;
 *                   onIngest fires per row inserted (so the dispatcher
 *                   can wake immediately).
 *
 * No filtering: per the V8 design decision, mattermost server already
 * pre-filters events to per-user via the ws subscription. We trust it.
 * (Noise-control optional; can layer kind whitelist later.)
 */
import type { EventStore } from "../../state.ts";
import { MattermostWS } from "./ws.ts";
import { mattermostEventToUEM, type MattermostWsEvent } from "./notification.ts";

export interface MattermostListenerOptions {
  agent: string;
  state: EventStore;
  baseUrl: string;
  /** Personal access token. */
  token: string;
  hostHeader?: string;
  /** Wake hook for the dispatcher. */
  onIngest?: (insertedCount: number) => void;
  /** Inject `now()` for tests (default: Date.now). */
  now?: () => number;
  /** Inject ws for tests (rare — usually use a real fake server). */
  ws?: MattermostWS;
  /** Heartbeat tuning passed through to MattermostWS. */
  heartbeatTimeoutMs?: number;
  /** Backoff tuning. */
  initialBackoffMs?: number;
  maxBackoffMs?: number;
  /** Errors callback. */
  onError?: (e: unknown) => void;
}

export class MattermostListener {
  ws: MattermostWS;

  constructor(private opts: MattermostListenerOptions) {
    this.ws = opts.ws ?? new MattermostWS({
      baseUrl: opts.baseUrl,
      token: opts.token,
      ...(opts.hostHeader ? { hostHeader: opts.hostHeader } : {}),
      ...(opts.heartbeatTimeoutMs !== undefined ? { heartbeatTimeoutMs: opts.heartbeatTimeoutMs } : {}),
      ...(opts.initialBackoffMs !== undefined ? { initialBackoffMs: opts.initialBackoffMs } : {}),
      ...(opts.maxBackoffMs !== undefined ? { maxBackoffMs: opts.maxBackoffMs } : {}),
      onEvent: (ev) => this.handleEvent(ev),
      ...(opts.onError ? { onError: opts.onError } : {}),
    });
  }

  async run(opts: { signal: AbortSignal }): Promise<void> {
    await this.ws.run(opts.signal);
  }

  private async handleEvent(ev: MattermostWsEvent): Promise<void> {
    // Skip non-content events (hello, status_change, typing, …).
    // We could whitelist later; for now accept post*, ignore others.
    if (!isInterestingEvent(ev.event)) return;
    const observed = (this.opts.now ?? Date.now)();
    const uem = mattermostEventToUEM(ev, this.opts.agent, observed);
    try {
      const id = await this.opts.state.ingest(uem, observed);
      if (id !== null) this.opts.onIngest?.(1);
    } catch (e) {
      this.opts.onError?.(e);
    }
  }
}

function isInterestingEvent(name: string): boolean {
  // Posts: agent 必须感知。
  // Reactions: emoji 点赞/反对是有语义的反馈，必须感知（详见 v2notes
  // R8 决策 2026-05-11）。reaction 风暴风险用 dispatcher 的批合并兜底，
  // 不在监听器层做白名单过滤。
  return (
    name === "posted" ||
    name === "post_edited" ||
    name === "post_deleted" ||
    name === "reaction_added" ||
    name === "reaction_removed"
  );
}
