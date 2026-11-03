/**
 * Normalize posts, edits, deletions and reactions into worker event messages.
 * Keep DM bodies untruncated; cap channel message bodies before adding prefixes.
 * Summaries normalize whitespace; the raw payload retains the original text.
 */
import type { UEM } from "../../uem.ts";

export interface MattermostWsBroadcast {
  user_id?: string;
  channel_id?: string;
  team_id?: string;
  omit_users?: Record<string, boolean> | null;
}

export interface MattermostPost {
  id: string;
  create_at: number;
  edit_at: number;
  user_id: string;
  channel_id: string;
  message: string;
  type?: string;
  /** Set on replies: the post that started the thread. */
  root_id?: string;
}

export interface MattermostWsEvent {
  event: string;
  data: Record<string, unknown> & {
    post?: string;
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

export interface MattermostReaction {
  user_id: string;
  post_id: string;
  emoji_name: string;
  create_at: number;
  channel_id?: string;
}

export function isSelfAuthored(ev: MattermostWsEvent, agent: string): boolean {
  if (!agent) return false;
  const post = parsePostMaybe(ev.data?.post);
  const raw = ev.data?.sender_name || post?.user_id;
  if (!raw) return false;
  const norm = (s: string) => s.replace(/^@/, "").trim().toLowerCase();
  return norm(raw) === norm(agent);
}

export function isSystemPost(ev: MattermostWsEvent): boolean {
  const raw = ev.data?.post;
  if (typeof raw !== "string") return false;
  try {
    const t = (JSON.parse(raw) as MattermostPost)?.type;
    return typeof t === "string" && t.startsWith("system_");
  } catch {
    return false;
  }
}

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

/**
 * Mark the product owner's DMs and posts that @mention the worker as urgent, so
 * the board service delivers them mid-turn like DMs.
 */
export function markUrgentFromHuman(
  uem: UEM,
  ev: MattermostWsEvent,
  human: string | undefined,
): UEM {
  if (!human || ev.event !== "posted") return uem;
  const norm = (s: string) => s.replace(/^@/, "").trim().toLowerCase();
  const sender = ev.data?.sender_name ?? "";
  if (norm(sender) !== norm(human)) return uem;
  const text = parsePostMaybe(ev.data?.post)?.message ?? "";
  if (uem.kind !== "dm" && !mentions(text, uem.target_agent)) return uem;
  return { ...uem, urgent: true, summary: `URGENT from the product owner: ${uem.summary}` };
}

export function mentions(text: string, agent: string): boolean {
  const escaped = agent.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(^|[^\\w@-])@${escaped}(?![\\w-])`, "i").test(text);
}

/**
 * Inline context (EVENT_CONTEXT=inline): a reply says which thread it belongs to
 * and how that thread started; a channel post cut to the summary limit names its
 * post id, so the worker can read the rest.
 */
export function withThreadContext(
  uem: UEM,
  ev: MattermostWsEvent,
  root: { author: string; message: string } | null,
): UEM {
  if (ev.event !== "posted") return uem;
  const post = parsePostMaybe(ev.data?.post);
  if (!post) return uem;
  const parts: string[] = [uem.summary];
  if (post.root_id) {
    const start = root ? `${root.author}: "${oneLine(root.message, 120)}"` : "an earlier post";
    parts.push(`(reply in the thread of post ${post.root_id}, started by ${start})`);
  }
  const isDM = ev.data?.channel_type === "D";
  if (!isDM && post.message.replace(/\s+/g, " ").trim().length > CHANNEL_SUMMARY_MAX) {
    parts.push(`(post ${post.id}; read the rest of it in Mattermost)`);
  }
  return parts.length > 1 ? { ...uem, summary: parts.join(" ") } : uem;
}

// DM classification also determines eligibility for mid-turn notice delivery.
function mapKind(ev: MattermostWsEvent): string {
  if (ev.event === "post_edited") return "post_edited";
  if (ev.event === "post_deleted") return "post_deleted";
  if (ev.event === "posted") {
    switch (ev.data?.channel_type) {
      case "D": return "dm";
      case "G": return "group";
      case "O":
      case "P":
      default:  return "post";
    }
  }
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

const CHANNEL_SUMMARY_MAX = 200;

function oneLine(s: string, max?: number): string {
  const t = s.replace(/\s+/g, " ").trim();
  if (max === undefined || t.length <= max) return t;
  return t.slice(0, max - 1) + "…";
}
