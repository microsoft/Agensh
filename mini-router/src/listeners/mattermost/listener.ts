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
import { isSelfAuthored, isSystemPost, mattermostEventToUEM, type MattermostWsEvent } from "./notification.ts";

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
  /** This agent's mattermost user id, so catch-up can drop its own posts.
   *  Optional: the websocket path filters on sender_name, which REST lacks. */
  selfUserId?: string;
  /** Ping cadence passed through to MattermostWS. */
  pingIntervalMs?: number;
  /** How far back catch-up looks on the first poll (ms). Default 10 min. */
  catchupLookbackMs?: number;
  /**
   * Max random delay before a catch-up poll (ms). Default 30_000.
   *
   * Every agent reconnects at roughly the same moment (a mattermost restart, a
   * ramp, a network blip), so an un-jittered catch-up is a thundering herd
   * against mattermost's REST API: at 256 agents the routers fail with
   * UND_ERR_CONNECT_TIMEOUT and agents are left with zero events. Spreading the
   * polls over a window is what makes the recovery path survivable at scale.
   */
  catchupJitterMs?: number;
  /** Per-request timeout for catch-up HTTP calls (ms). Default 15_000. */
  catchupRequestTimeoutMs?: number;
  /** Inject fetch for tests. */
  fetchImpl?: typeof fetch;
}

export class MattermostListener {
  ws: MattermostWS;
  /** Newest post timestamp already ingested; the `since` cursor for catch-up. */
  private cursor = 0;
  /** This agent's mattermost user id; undefined = not yet resolved, null = unknown. */
  private selfId: string | null | undefined = undefined;
  /** Cached (team,channel) list. Membership is fixed for a run, and re-walking
   *  teams+channels on every reconnect turned one poll into ~8 requests. */
  private channelCache: { id: string; name: string; display_name: string; type: string }[] | null = null;
  /** Serialises catch-up so a reconnect storm cannot stack N polls per agent. */
  private polling = false;

  constructor(private opts: MattermostListenerOptions) {
    this.ws = opts.ws ?? new MattermostWS({
      baseUrl: opts.baseUrl,
      token: opts.token,
      ...(opts.hostHeader ? { hostHeader: opts.hostHeader } : {}),
      ...(opts.heartbeatTimeoutMs !== undefined ? { heartbeatTimeoutMs: opts.heartbeatTimeoutMs } : {}),
      ...(opts.initialBackoffMs !== undefined ? { initialBackoffMs: opts.initialBackoffMs } : {}),
      ...(opts.maxBackoffMs !== undefined ? { maxBackoffMs: opts.maxBackoffMs } : {}),
      ...(opts.pingIntervalMs !== undefined ? { pingIntervalMs: opts.pingIntervalMs } : {}),
      onEvent: (ev) => this.handleEvent(ev),
      // Every (re)connect drains the gap. Mattermost's websocket does not
      // replay, so this is the only thing that makes a dropped socket
      // recoverable rather than a permanently missed wake.
      onConnect: () => { void this.scheduleCatchup(); },
      ...(opts.onError ? { onError: opts.onError } : {}),
    });
  }

  async run(opts: { signal: AbortSignal }): Promise<void> {
    await this.ws.run(opts.signal);
  }

  /**
   * Drain posts that arrived while the websocket was down.
   *
   * The gitea listener does the same (its pollOnce() catch-up). Without it, a
   * routine socket drop becomes a permanently missed wake for every agent whose
   * post landed during the gap.
   *
   * Synthesises the same `posted` event shape the websocket delivers, so both
   * paths produce the SAME event_id (`mattermost:post:<id>:<edit_at>`) and the
   * store's (dedup_key, agent) unique key collapses any overlap. Returns the
   * number of rows actually inserted.
   */
  /** Jittered, non-overlapping catch-up. See catchupJitterMs. */
  private async scheduleCatchup(): Promise<void> {
    if (this.polling) return;
    this.polling = true;
    try {
      const jitter = this.opts.catchupJitterMs ?? 30_000;
      if (jitter > 0) await new Promise((r) => setTimeout(r, Math.random() * jitter));
      await this.pollOnce();
    } catch (e) {
      this.opts.onError?.(e);
    } finally {
      this.polling = false;
    }
  }

  async pollOnce(): Promise<number> {
    const doFetch = this.opts.fetchImpl ?? fetch;
    const base = this.opts.baseUrl.replace(/\/$/, "");
    const headers: Record<string, string> = { Authorization: `Bearer ${this.opts.token}` };
    if (this.opts.hostHeader) headers.Host = this.opts.hostHeader;
    const reqTimeout = this.opts.catchupRequestTimeoutMs ?? 15_000;
    const getJson = async (path: string): Promise<unknown> => {
      // Bounded: an unbounded fetch against a saturated mattermost wedges the
      // poll, and `polling` would then block every later catch-up too.
      const ac = new AbortController();
      const t = setTimeout(() => ac.abort(), reqTimeout);
      try {
        const r = await doFetch(`${base}${path}`, { headers, signal: ac.signal });
        if (!r.ok) throw new Error(`mattermost ${path} -> ${r.status}`);
        return await r.json();
      } finally {
        clearTimeout(t);
      }
    };

    const since = this.cursor > 0
      ? this.cursor
      : (this.opts.now ?? Date.now)() - (this.opts.catchupLookbackMs ?? 10 * 60_000);

    // The websocket path filters an agent's own posts on sender_name; REST only
    // carries user_id, so catch-up needs the id or it would re-inject the
    // agent's own posts as notices. Resolved
    // once, lazily, so callers need not wire it through.
    if (this.selfId === undefined) {
      try {
        this.selfId = this.opts.selfUserId ?? str(await getJson("/api/v4/users/me"), "id") ?? null;
      } catch {
        this.selfId = null; // fail open: better a duplicate than a lost wake
      }
    }

    let inserted = 0;
    if (this.channelCache === null) {
      const acc: { id: string; name: string; display_name: string; type: string }[] = [];
      for (const team of asArray(await getJson("/api/v4/users/me/teams"))) {
        const teamId = str(team, "id");
        if (!teamId) continue;
        for (const ch of asArray(await getJson(`/api/v4/users/me/teams/${teamId}/channels`))) {
          const id = str(ch, "id");
          if (!id) continue;
          acc.push({
            id,
            name: str(ch, "name") ?? "",
            display_name: str(ch, "display_name") ?? "",
            type: str(ch, "type") ?? "",
          });
        }
      }
      this.channelCache = acc;
    }
    {
      for (const ch of this.channelCache) {
        const chId = ch.id;
        const page = await getJson(`/api/v4/channels/${chId}/posts?since=${Math.floor(since)}`);
        const posts = (page as { posts?: Record<string, unknown> } | null)?.posts ?? {};
        for (const post of Object.values(posts)) {
          const p = post as Record<string, unknown>;
          // REST carries user_id where the websocket carries sender_name, so the
          // self-filter has to key on the id here.
          if (this.selfId && p.user_id === this.selfId) continue;
          const createAt = Number(p.create_at ?? 0);
          if (createAt > this.cursor) this.cursor = createAt;
          const ev: MattermostWsEvent = {
            event: "posted",
            data: {
              post: JSON.stringify(p),
              channel_display_name: ch.display_name,
              channel_name: ch.name,
              channel_type: ch.type,
              sender_name: String(p.user_id ?? "?"),
            },
            broadcast: { channel_id: chId },
            seq: 0,
          } as MattermostWsEvent;
          if (await this.ingestEvent(ev)) inserted++;
        }
      }
    }
    return inserted;
  }

  private async handleEvent(ev: MattermostWsEvent): Promise<void> {
    await this.ingestEvent(ev);
  }

  /** Shared by the websocket and catch-up paths. Returns true iff a row landed. */
  private async ingestEvent(ev: MattermostWsEvent): Promise<boolean> {
    // Skip non-content events (hello, status_change, typing, …).
    // We could whitelist later; for now accept post*, ignore others.
    if (!isInterestingEvent(ev.event)) return false;
    // An agent must never be notified of its own post: that spends the notice
    // budget injecting an agent's own words back into its context mid-turn,
    // and without this filter it is about half of every DM delivered.
    if (isSelfAuthored(ev, this.opts.agent)) return false;
    // Membership churn is N^2 during startup and wakes the whole team at once.
    if (isSystemPost(ev)) return false;
    const observed = (this.opts.now ?? Date.now)();
    const uem = mattermostEventToUEM(ev, this.opts.agent, observed);
    try {
      const id = await this.opts.state.ingest(uem, observed);
      if (id !== null) { this.opts.onIngest?.(1); return true; }
    } catch (e) {
      this.opts.onError?.(e);
    }
    return false;
  }
}

function asArray(v: unknown): Record<string, unknown>[] {
  return Array.isArray(v) ? (v as Record<string, unknown>[]) : [];
}

function str(o: unknown, k: string): string | undefined {
  const v = (o as Record<string, unknown> | null)?.[k];
  return typeof v === "string" ? v : undefined;
}

function isInterestingEvent(name: string): boolean {
  // Posts: the agent must see them.
  // Reactions: an emoji up/down vote is feedback with meaning, so the agent
  // must see it too. A reaction storm is absorbed by the dispatcher's batch
  // merge, not by a whitelist here in the listener.
  return (
    name === "posted" ||
    name === "post_edited" ||
    name === "post_deleted" ||
    name === "reaction_added" ||
    name === "reaction_removed"
  );
}
