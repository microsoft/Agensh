/**
 * GiteaListener — wake-driven cursor pull, single-agent variant for R7.
 *
 * No periodic polling fallback; SSE is the sole wake. One catch-up
 * pollOnce on boot drains backlog. Listener writes ingested events into
 * MySQL via State.ingestBatch (idempotent on dedup_key). Dispatcher is
 * woken via onIngest callback.
 */
import {
  advanceCursor,
  fetchNotificationsPage,
  type FetchLike,
} from "./fetcher.ts";
import { giteaNotificationToUEM } from "./notification.ts";
import { GiteaSSE } from "./sse.ts";
import type { EventStore } from "../../state.ts";
import type { UEM } from "../../uem.ts";
import type { UpstreamAuth } from "../../upstream_auth.ts";

export interface GiteaListenerOptions {
  agent: string;
  state: EventStore;
  baseUrl: string;
  /** PAT — REST notifications. */
  token: string;
  /** Cookie/OIDC auth — SSE only. */
  auth: UpstreamAuth;
  fetch?: FetchLike;
  now?: () => number;
  hostHeader?: string;
  onIngest?: (insertedCount: number) => void;
  limit?: number;
  /** SSE driver; tests can disable by passing null. */
  sse?: GiteaSSE | null;
}

export class GiteaListener {
  private wakers: Array<() => void> = [];
  sse: GiteaSSE | null = null;

  constructor(private opts: GiteaListenerOptions) {}

  /** Run one pull cycle: read cursor → fetch → ingest → advance cursor. */
  async pollOnce(): Promise<{ inserted: number; cursor: string | null }> {
    const { agent, state } = this.opts;
    const since = await state.getCursor(agent, "gitea");
    const page = await fetchNotificationsPage({
      baseUrl: this.opts.baseUrl,
      token: this.opts.token,
      since,
      ...(this.opts.fetch ? { fetch: this.opts.fetch } : {}),
      ...(this.opts.hostHeader ? { hostHeader: this.opts.hostHeader } : {}),
      ...(this.opts.limit !== undefined ? { limit: this.opts.limit } : {}),
    });
    const observed = (this.opts.now ?? Date.now)();
    const uems: UEM[] = page.items.map((n) =>
      giteaNotificationToUEM(n, agent, observed),
    );
    const next = advanceCursor(since, page);
    let inserted = 0;
    for (const u of uems) {
      const id = await state.ingest(u, observed);
      if (id !== null) inserted++;
    }
    if (next) await state.setCursor(agent, "gitea", next);
    if (inserted > 0) this.opts.onIngest?.(inserted);
    return { inserted, cursor: next };
  }

  async runPolling(opts: {
    signal?: AbortSignal;
    onError?: (e: unknown) => void;
  } = {}): Promise<void> {
    let sseTask: Promise<void> | null = null;
    if (this.opts.sse !== null) {
      const sse = this.opts.sse ??
        new GiteaSSE({
          baseUrl: this.opts.baseUrl,
          auth: this.opts.auth,
          ...(this.opts.hostHeader
            ? { hostHeader: this.opts.hostHeader }
            : {}),
          ...(this.opts.fetch ? { fetch: this.opts.fetch } : {}),
          onTrigger: () => this.trigger(),
          ...(opts.onError ? { onError: opts.onError } : {}),
        });
      this.sse = sse;
      if (sse && opts.signal) {
        sseTask = sse.run(opts.signal).catch((e) => {
          opts.onError?.(e);
        });
      }
    }
    try {
      try {
        await this.pollOnce();
      } catch (e) {
        opts.onError?.(e);
      }
      while (!opts.signal?.aborted) {
        await this.waitForWake(opts.signal);
        if (opts.signal?.aborted) break;
        try {
          await this.pollOnce();
        } catch (e) {
          opts.onError?.(e);
        }
      }
    } finally {
      if (sseTask) await sseTask;
    }
  }

  trigger(): void {
    const ws = this.wakers;
    this.wakers = [];
    for (const w of ws) w();
  }

  private waitForWake(signal?: AbortSignal): Promise<void> {
    // R10.1 fix: previously installed a `{once:true}` abort listener that
    // only auto-removed on abort. The wake() path resolved without removing
    // it, so each tick of the polling loop leaked one listener. Long-running
    // listener saw MaxListenersExceededWarning. Always remove on resolve.
    return new Promise<void>((resolve) => {
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        if (signal) signal.removeEventListener("abort", finish);
        resolve();
      };
      this.wakers.push(finish);
      signal?.addEventListener("abort", finish, { once: true });
    });
  }
}
