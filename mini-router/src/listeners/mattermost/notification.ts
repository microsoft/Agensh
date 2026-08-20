/**
 * Mattermost WebSocket event → UEM mapper.
 *
 * Source-agnostic dispatch contract: dispatcher only sees UEM. New
 * sources just add a mapper file. See DESIGN §6.C "多环境支持".
 *
 * Reference: Mattermost API docs (2026-05) `/api/v4/websocket`.
 *   Each WS event has shape:
 *     { event: <name>, data: {...}, broadcast: {user_id, channel_id, team_id, omit_users}, seq }
 *
 *   For `posted` / `post_edited` / `post_deleted`:
 *     data.post is a JSON STRING (not an object) — must JSON.parse.
 *     data.channel_type ∈ {"O" public, "P" private, "D" direct, "G" group}
 *     data.sender_name like "@username"
 *     data.channel_display_name human-friendly
 *
 * The mattermost server pre-filters per-user via the WebSocket
 * subscription model: a single PAT-authenticated socket only receives
 * events the user has permission to see (channels they belong to, DMs,
 * mentions). We do NO additional filtering here — the listener trusts
 * mattermost's broadcast filter, parallel to how the gitea listener
 * trusts /api/v1/notifications to be per-user filtered.
 */
import type { UEM } from "../../uem.ts";

export interface MattermostWsBroadcast {
  user_id?: string;
  channel_id?: string;
  team_id?: string;
  omit_users?: Record<string, boolean> | null;
}

/** Subset of post fields we use; raw shape kept opaque in payload.raw. */
export interface MattermostPost {
  id: string;
  create_at: number;
  edit_at: number;
  user_id: string;
  channel_id: string;
  message: string;
  type?: string;
}

export interface MattermostWsEvent {
  event: string;
  data: Record<string, unknown> & {
    /** JSON-encoded MattermostPost. Mattermost wire format quirk. */
    post?: string;
    /** JSON-encoded MattermostReaction (reaction_added/removed). */
    reaction?: string;
    channel_display_name?: string;
    channel_name?: string;
    channel_type?: string;
    sender_name?: string;
    mentions?: string;
    team_id?: string;
  };
  broadcast: MattermostWsBroadcast;
  seq: number;
}

/** Subset of reaction fields. Wire format: data.reaction is a JSON string. */
export interface MattermostReaction {
  user_id: string;
  post_id: string;
  emoji_name: string;
  create_at: number;
  channel_id?: string;
}

/** Map mattermost ws event → UEM. */
export function mattermostEventToUEM(
  ev: MattermostWsEvent,
  target_agent: string,
  observed_at: number,
): UEM {
  if (ev.event === "reaction_added" || ev.event === "reaction_removed") {
    return reactionToUEM(ev, target_agent, observed_at);
  }
  const kind = mapKind(ev);
  const post = parsePostMaybe(ev.data?.post);
  const channelLabel =
    ev.data?.channel_display_name ||
    ev.data?.channel_name ||
    post?.channel_id ||
    ev.broadcast?.channel_id ||
    "?";
  const sender = ev.data?.sender_name || post?.user_id || "?";
  const summary = renderSummary({
    kind,
    sender,
    channel_type: ev.data?.channel_type,
    channelLabel,
    text: post?.message,
    malformed: ev.data?.post !== undefined && post === null,
  });
  const post_id = post?.id ?? `seq-${ev.seq}`;
  const edit_at = post?.edit_at ?? 0;
  return {
    event_id: `mattermost:post:${post_id}:${edit_at}`,
    source: "mattermost",
    target_agent,
    kind,
    summary,
    observed_at,
    raw: ev,
  };
}

function mapKind(ev: MattermostWsEvent): string {
  if (ev.event === "post_edited") return "post_edited";
  if (ev.event === "post_deleted") return "post_deleted";
  // For "posted", refine by channel_type.
  if (ev.event === "posted") {
    switch (ev.data?.channel_type) {
      case "D": return "dm";
      case "G": return "group";
      case "O":
      case "P":
      default:  return "post";
    }
  }
  // Other events (typing, status_change, ...) — mapped but caller may filter
  return ev.event;
}

function parsePostMaybe(raw: unknown): MattermostPost | null {
  if (typeof raw !== "string") return null;
  try {
    const o = JSON.parse(raw) as MattermostPost;
    if (typeof o.id !== "string") return null;
    return o;
  } catch {
    return null;
  }
}

function parseReactionMaybe(raw: unknown): MattermostReaction | null {
  if (typeof raw !== "string") return null;
  try {
    const o = JSON.parse(raw) as MattermostReaction;
    if (typeof o.post_id !== "string" || typeof o.user_id !== "string") return null;
    return o;
  } catch {
    return null;
  }
}

function reactionToUEM(
  ev: MattermostWsEvent,
  target_agent: string,
  observed_at: number,
): UEM {
  const r = parseReactionMaybe(ev.data?.reaction);
  const kind = ev.event === "reaction_added" ? "reaction_added" : "reaction_removed";
  const verb = ev.event === "reaction_added" ? "reacted" : "unreacted";
  const emoji = r?.emoji_name ? `:${r.emoji_name}:` : "(unknown)";
  const post_id = r?.post_id ?? `seq-${ev.seq}`;
  const summary = r
    ? `${r.user_id} ${verb} ${emoji} on post ${post_id}`
    : `${verb} ${emoji} (malformed reaction payload)`;
  // event_id key includes verb so add+remove of same emoji aren't deduped.
  return {
    event_id: `mattermost:${kind}:${post_id}:${r?.user_id ?? "?"}:${r?.emoji_name ?? "?"}`,
    source: "mattermost",
    target_agent,
    kind,
    summary,
    observed_at,
    raw: ev,
  };
}

interface SummaryArgs {
  kind: string;
  sender: string;
  channel_type?: string;
  channelLabel: string;
  text?: string;
  malformed?: boolean;
}

function renderSummary(a: SummaryArgs): string {
  const isDM = a.channel_type === "D" || a.kind === "dm";
  const where = isDM ? "DM" : `#${a.channelLabel}`;
  const body = a.malformed
    ? "(malformed post payload)"
    : oneLine(a.text ?? "(no text)");
  return `${a.sender} in ${where}: ${body}`;
}

function oneLine(s: string, max = 200): string {
  const t = s.replace(/\s+/g, " ").trim();
  return t.length > max ? t.slice(0, max - 1) + "…" : t;
}
