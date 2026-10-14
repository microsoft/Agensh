/**
 * GiteaListener — wake-driven cursor pull, one listener per agent.
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
  type GiteaNotificationRaw,
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

/** Upper bound on pages per poll, so a runaway backlog cannot pin the loop. */
const MAX_PAGES = 20;

export class GiteaListener {
  private wakers: Array<() => void> = [];
  /** A trigger() that arrived while no poll was waiting; the next wait returns at once. */
  private wakePending = false;
  sse: GiteaSSE | null = null;

  constructor(private opts: GiteaListenerOptions) {}

  /** Run one pull cycle: read cursor → fetch → ingest → advance cursor. */
  async pollOnce(): Promise<{ inserted: number; cursor: string | null }> {
    const { agent, state } = this.opts;
    const since = await state.getCursor(agent, "gitea");
    // Gitea returns the newest first, and the cursor jumps to the newest seen,
    // so anything past the first page would never be fetched again. Page until
    // a short page; overlap between pages is collapsed by ingest's dedup.
    const limit = this.opts.limit ?? 50;
    const items: GiteaNotificationRaw[] = [];
    let maxUpdatedAt: string | null = null;
    for (let n = 1; n <= MAX_PAGES; n++) {
      const page = await fetchNotificationsPage({
        baseUrl: this.opts.baseUrl,
        token: this.opts.token,
        since,
        ...(this.opts.fetch ? { fetch: this.opts.fetch } : {}),
        ...(this.opts.hostHeader ? { hostHeader: this.opts.hostHeader } : {}),
        limit,
        page: n,
      });
      items.push(...page.items);
      if (page.maxUpdatedAt && (!maxUpdatedAt || page.maxUpdatedAt > maxUpdatedAt)) {
        maxUpdatedAt = page.maxUpdatedAt;
      }
      if (page.items.length < limit) break;
    }
    const observed = (this.opts.now ?? Date.now)();
    const uems: UEM[] = items.map((n) =>
      giteaNotificationToUEM(n, agent, observed),
    );
    const next = advanceCursor(since, { items, maxUpdatedAt });
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
    // SSE is the only wake, so one that lands mid-poll (after the fetch, before
    // the next wait) must not be dropped: its notification would sit unread
    // until some later, unrelated trigger.
    if (ws.length === 0) this.wakePending = true;
    for (const w of ws) w();
  }

  private waitForWake(signal?: AbortSignal): Promise<void> {
    if (this.wakePending) {
      this.wakePending = false;
      return Promise.resolve();
    }
    // Always remove the abort listener on resolve. A `{once:true}` listener
    // only auto-removes on abort, so a wake() that resolves without removing
    // it leaks one listener per tick of the polling loop, and a long-running
    // listener hits MaxListenersExceededWarning.
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
