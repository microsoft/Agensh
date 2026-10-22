/**
 * Use SSE wakeups to fetch Gitea notifications into the durable worker queue.
 * Save the source cursor only after ingesting the fetched notifications.
 */
import {
  advanceCursor,
  fetchNotificationsPage,
  NOTIFICATION_PAGE_SIZE,
  type GiteaNotificationRaw,
} from "./fetcher.ts";
import { giteaNotificationToUEM } from "./notification.ts";
import { GiteaSSE } from "./sse.ts";
import type { EventStore } from "../../state.ts";
import type { UEM } from "../../uem.ts";
import type { GiteaFormAuth } from "../../gitea_form_auth.ts";

export interface GiteaListenerOptions {
  agent: string;
  state: EventStore;
  baseUrl: string;
  token: string;
  auth: GiteaFormAuth;
  hostHeader?: string;
  onIngest?: (insertedCount: number) => void;
}

const MAX_PAGES = 20;

export class GiteaListener {
  private wakers: Array<() => void> = [];
  private wakePending = false;
  sse: GiteaSSE | null = null;

  constructor(private opts: GiteaListenerOptions) {}

  async pollOnce(): Promise<void> {
    const { agent, state } = this.opts;
    const since = await state.getCursor(agent, "gitea");
    // Keep one lower bound across pages; advancing it mid-fetch could skip results.
    const items: GiteaNotificationRaw[] = [];
    let maxUpdatedAt: string | null = null;
    for (let n = 1; n <= MAX_PAGES; n++) {
      const page = await fetchNotificationsPage({
        baseUrl: this.opts.baseUrl,
        token: this.opts.token,
        since,
        ...(this.opts.hostHeader ? { hostHeader: this.opts.hostHeader } : {}),
        page: n,
      });
      items.push(...page.items);
      if (page.maxUpdatedAt && (!maxUpdatedAt || page.maxUpdatedAt > maxUpdatedAt)) {
        maxUpdatedAt = page.maxUpdatedAt;
      }
      if (page.items.length < NOTIFICATION_PAGE_SIZE) break;
    }
    const observed = Date.now();
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
  }

  async runPolling(opts: {
    signal: AbortSignal;
    onError?: (e: unknown) => void;
  }): Promise<void> {
    const sse = new GiteaSSE({
      baseUrl: this.opts.baseUrl,
      auth: this.opts.auth,
      ...(this.opts.hostHeader ? { hostHeader: this.opts.hostHeader } : {}),
      onTrigger: () => this.trigger(),
      ...(opts.onError ? { onError: opts.onError } : {}),
    });
    this.sse = sse;
    const sseTask = sse.run(opts.signal).catch((e) => {
      opts.onError?.(e);
    });
    try {
      try {
        await this.pollOnce();
      } catch (e) {
        opts.onError?.(e);
      }
      while (!opts.signal.aborted) {
        await this.waitForWake(opts.signal);
        if (opts.signal.aborted) break;
        try {
          await this.pollOnce();
        } catch (e) {
          opts.onError?.(e);
        }
      }
    } finally {
      await sseTask;
    }
  }

  trigger(): void {
    const ws = this.wakers;
    this.wakers = [];
    // Remember notifications that arrive while a fetch is already in progress.
    if (ws.length === 0) this.wakePending = true;
    for (const w of ws) w();
  }

  private waitForWake(signal: AbortSignal): Promise<void> {
    if (this.wakePending) {
      this.wakePending = false;
      return Promise.resolve();
    }
    return new Promise<void>((resolve) => {
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        signal.removeEventListener("abort", finish);
        resolve();
      };
      this.wakers.push(finish);
      signal.addEventListener("abort", finish, { once: true });
    });
  }
}
