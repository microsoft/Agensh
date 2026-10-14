/**
 * Mattermost WebSocket event → UEM mapper.
 *
 * Source-agnostic dispatch contract: dispatcher only sees UEM. New
 * sources just add a mapper file.
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

/**
 * True when this event is the agent's OWN post coming back to it.
 *
 * Without this check about half of every DM delivered mid-turn is the
 * receiving agent's own outgoing message. It renders, delivers and reconciles
 * exactly like a real notice, so nothing fails and the waste is invisible.
 *
 * The merge listener filters the same way (merges/listener.ts: `merged_by ===
 * agent`).
 *
 * Fails OPEN: an unidentifiable sender is delivered. Echoing a message back is
 * cheap; dropping a real peer DM is not.
 */
export function isSelfAuthored(ev: MattermostWsEvent, agent: string): boolean {
  if (!agent) return false;
  const post = parsePostMaybe(ev.data?.post);
  const raw = ev.data?.sender_name || post?.user_id;
  if (!raw) return false;
  const norm = (s: string) => s.replace(/^@/, "").trim().toLowerCase();
  return norm(raw) === norm(agent);
}

/**
 * A mattermost SYSTEM post -- join/leave/add/remove membership churn.
 *
 * Bootstrap creates one account per agent, and each join posts
 * "<agent> joined the team." to the channel. The router turned every one of
 * those into a UEM and fanned it out to every agent, which is N^2 wakeups
 * during startup:
 *
 *      16 agents ->    256   (survivable; this went unnoticed for months)
 *     128 agents -> 16,384   <- 48 agents took their first turn inside an
 *                               11-SECOND window despite a 30s DM stagger;
 *                               load 82, 47k threads, sudo wedged ~15 min.
 *
 * These carry nothing a coder agent can act on. Discriminated by post.type,
 * which mattermost sets to system_* for exactly these and leaves "" (or absent)
 * for real user posts. NOT by message text: an agent writing "I joined the two
 * parser tables" must still be delivered.
 */
export function isSystemPost(ev: MattermostWsEvent): boolean {
  const raw = ev.data?.post;
  if (typeof raw !== "string") return false;
  try {
    const t = (JSON.parse(raw) as MattermostPost)?.type;
    return typeof t === "string" && t.startsWith("system_");
  } catch {
    return false;   // malformed payload is handled elsewhere; never claim it is system
  }
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
  // A deletion leaves edit_at alone, so under the post key it would collide
  // with the original post and be dropped as a duplicate.
  const event_id = ev.event === "post_deleted"
    ? `mattermost:post_deleted:${post_id}`
    : `mattermost:post:${post_id}:${edit_at}`;
  return {
    event_id,
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
  // event_id key includes verb so add+remove of same emoji aren't deduped, and
  // the reaction's create_at so re-adding it after a removal is not either.
  return {
    event_id: `mattermost:${kind}:${post_id}:${r?.user_id ?? "?"}:${r?.emoji_name ?? "?"}:${r?.create_at ?? `seq-${ev.seq}`}`,
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
    : oneLine(a.text ?? "(no text)", isDM ? undefined : CHANNEL_SUMMARY_MAX);
  return `${a.sender} in ${where}: ${body}`;
}

// Channel posts stay capped: they are broadcast rather than targeted, they
// outnumber DMs ~6:1, and their median is ~130 chars, so the cap barely binds.
//
// DMs are deliberately NOT capped. At max=200 most of them arrive clipped, and
// the clip lands on the ask -- "...are your current Tag/Optio..." is a question
// cut before its own question mark. The failure is silent at both ends: the
// sender gets no signal, and the receiver gets a fragment that still reads like
// actionable prose. The recovery tools exist but agents rarely follow a
// truncated DM with them; they reply to a message they have read half of.
//
// Contrast the board, which is right: an over-cap entry is REJECTED with an
// explicit error (SharedLessons.note in shared_lessons.py) so the author
// knows and can use `detail` + `board_unfold`. A clipped DM is silently amputated. DMs exist to
// interrupt a peer and settle a collision; clipping them to ~170 usable chars
// while an untargeted PATCH_SUMMARY beside them gets 300 inverts the priority.
const CHANNEL_SUMMARY_MAX = 200;

/**
 * Collapse to ONE line, optionally clipping.
 *
 * The single-line part is not optional for either kind: mcp-notice-shim joins
 * notices with "\n" (src/index.js:138), so an embedded newline would split one
 * message into what look like several independent notices.
 *
 * `max === undefined` means no clip.
 */
function oneLine(s: string, max?: number): string {
  const t = s.replace(/\s+/g, " ").trim();
  if (max === undefined || t.length <= max) return t;
  return t.slice(0, max - 1) + "…";
}
