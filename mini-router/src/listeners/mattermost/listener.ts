/**
 * Ingest live Mattermost activity and recover recent posts after reconnects.
 * Both paths use the same event conversion and durable deduplication key.
 */
import type { EventStore } from "../../state.ts";
import { MattermostWS } from "./ws.ts";
import {
  isSelfAuthored,
  isSystemPost,
  markUrgentFromHuman,
  mattermostEventToUEM,
  withThreadContext,
  type MattermostWsEvent,
} from "./notification.ts";

export interface MattermostListenerOptions {
  agent: string;
  state: EventStore;
  baseUrl: string;
  token: string;
  hostHeader?: string;
  /** The product owner's username; their DMs and mentions are urgent. */
  human?: string;
  /** "inline": replies carry how their thread started (withThreadContext). */
  eventContext?: string;
  onIngest?: (insertedCount: number) => void;
  onError?: (e: unknown) => void;
}

export class MattermostListener {
  ws: MattermostWS;
  private cursor = 0;
  private selfId: string | null | undefined = undefined;
  private channelCache: { id: string; name: string; display_name: string; type: string }[] | null = null;
  private polling = false;

  constructor(private opts: MattermostListenerOptions) {
    this.ws = new MattermostWS({
      baseUrl: opts.baseUrl,
      token: opts.token,
      ...(opts.hostHeader ? { hostHeader: opts.hostHeader } : {}),
      onEvent: (ev) => { void this.ingestEvent(ev); },
      onConnect: () => { void this.scheduleCatchup(); },
      ...(opts.onError ? { onError: opts.onError } : {}),
    });
  }

  async run(opts: { signal: AbortSignal }): Promise<void> {
    await this.ws.run(opts.signal);
  }

  private async scheduleCatchup(): Promise<void> {
    if (this.polling) return;
    this.polling = true;
    try {
      // Stagger REST catch-up when many workers reconnect to the same server.
      await new Promise((r) => setTimeout(r, Math.random() * 30_000));
      await this.pollOnce();
    } catch (e) {
      this.opts.onError?.(e);
    } finally {
      this.polling = false;
    }
  }

  async pollOnce(): Promise<void> {
    const base = this.opts.baseUrl.replace(/\/$/, "");
    const headers: Record<string, string> = { Authorization: `Bearer ${this.opts.token}` };
    if (this.opts.hostHeader) headers.Host = this.opts.hostHeader;
    const getJson = async (path: string): Promise<unknown> => {
      const ac = new AbortController();
      const t = setTimeout(() => ac.abort(), 15_000);
      try {
        const r = await fetch(`${base}${path}`, { headers, signal: ac.signal });
        if (!r.ok) throw new Error(`mattermost ${path} -> ${r.status}`);
        return await r.json();
      } finally {
        clearTimeout(t);
      }
    };

    const since = this.cursor > 0
      ? this.cursor
      : Date.now() - 10 * 60_000;

    // REST posts expose user IDs, so resolve our own ID before filtering echoes.
    if (this.selfId === undefined) {
      try {
        this.selfId = str(await getJson("/api/v4/users/me"), "id") ?? null;
      } catch {
        this.selfId = null;
      }
    }

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
          if (this.selfId && p.user_id === this.selfId) continue;
          const createAt = Number(p.create_at ?? 0);
          // This catch-up cursor is process-local; a fresh router looks back 10 min.
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
          await this.ingestEvent(ev);
        }
      }
    }
  }

  /** The post that started a reply's thread, with its author's username. */
  private async threadRoot(ev: MattermostWsEvent): Promise<{ author: string; message: string } | null> {
    let rootId: string | undefined;
    try {
      rootId = (JSON.parse(String(ev.data?.post ?? "{}")) as { root_id?: string }).root_id;
    } catch {
      return null;
    }
    if (!rootId) return null;
    const base = this.opts.baseUrl.replace(/\/$/, "");
    const headers: Record<string, string> = { Authorization: `Bearer ${this.opts.token}` };
    if (this.opts.hostHeader) headers.Host = this.opts.hostHeader;
    const get = async (path: string) => {
      const r = await fetch(`${base}${path}`, { headers, signal: AbortSignal.timeout(10_000) });
      return r.ok ? ((await r.json()) as Record<string, unknown>) : null;
    };
    try {
      const root = await get(`/api/v4/posts/${rootId}`);
      if (!root) return null;
      const user = typeof root.user_id === "string" ? await get(`/api/v4/users/${root.user_id}`) : null;
      return { author: String(user?.username ?? root.user_id ?? "?"), message: String(root.message ?? "") };
    } catch {
      return null;
    }
  }

  private async ingestEvent(ev: MattermostWsEvent): Promise<void> {
    if (!isInterestingEvent(ev.event)) return;
    if (isSelfAuthored(ev, this.opts.agent)) return;
    if (isSystemPost(ev)) return;
    const observed = Date.now();
    let uem = markUrgentFromHuman(mattermostEventToUEM(ev, this.opts.agent, observed), ev, this.opts.human);
    if (this.opts.eventContext === "inline") {
      uem = withThreadContext(uem, ev, await this.threadRoot(ev));
    }
    try {
      const id = await this.opts.state.ingest(uem, observed);
      if (id !== null) this.opts.onIngest?.(1);
    } catch (e) {
      this.opts.onError?.(e);
    }
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
  return (
    name === "posted" ||
    name === "post_edited" ||
    name === "post_deleted" ||
    name === "reaction_added" ||
    name === "reaction_removed"
  );
}
