/**
 * Gitea notification → UEM mapper.
 *
 * Why a separate file: the dispatch layer must remain source-agnostic.
 * A new source (slack/email/cron) gets its own mapper file; UEM is the
 * common ground.
 *
 * Reference shape from Gitea API `/api/v1/notifications` (per Gitea
 * 1.22 swagger):
 *   {
 *     "id": 42,
 *     "subject": { "title", "type"="Issue|Pull|Commit", "url",
 *                   "html_url", "state", "latest_comment_url" },
 *     "repository": { "full_name", ... },
 *     "unread": bool,
 *     "pinned": bool,
 *     "updated_at": "2026-04-27T08:00:00Z",
 *     "url": "..."
 *   }
 *
 * Gitea does not expose *why* the notification fired (mention vs
 * assigned vs review-requested). We map subject.type →
 * `kind` and rely on the agent to read `summary` + fetch details. Finer
 * categorization can be layered in later by hitting subject.url.
 */
import type { UEM } from "../../uem.ts";

/** The minimal shape we depend on; extra fields are kept in raw. */
export interface GiteaNotification {
  id: number;
  unread?: boolean;
  pinned?: boolean;
  updated_at: string;
  url?: string;
  subject?: {
    title?: string;
    type?: string;          // "Issue" | "Pull" | "Commit" | etc
    url?: string;           // API url
    html_url?: string;      // human url
    state?: string;
    latest_comment_url?: string;
  };
  repository?: {
    full_name?: string;
  };
}

/**
 * Map a Gitea notification + the agent it's destined to into a UEM.
 *
 * `target_agent` comes from the listener (one SSE per agent), not from
 * the notification itself — Gitea already filtered to per-user-relevant.
 */
export function giteaNotificationToUEM(
  notif: GiteaNotification,
  target_agent: string,
  observed_at: number,
): UEM {
  const subj = notif.subject ?? {};
  const repo = notif.repository?.full_name ?? "?";
  const title = subj.title ?? "(no title)";
  const kind = (subj.type ?? "Unknown").toLowerCase();
  // Self-contained locator: repo + kind + (issue/PR number when derivable
  // from subject.url) + title. The agent reconstructs the lookup via the
  // gitea MCP from these fields alone — no internal URL is leaked.
  const num = extractNumber(subj.url ?? subj.html_url);
  const ref = num !== null ? ` #${num}` : "";
  const summary = `${repo} ${kind}${ref}: ${title}`;
  return {
    // event_id MUST include updated_at: Gitea's notification.id is
    // per-thread (one row per (user, issue)), and a follow-up comment
    // only bumps updated_at on the same row. If we used the bare id
    // as dedup_key, every activity after the first would be silently
    // dropped (B7 — "first event delivered, subsequent comments lost").
    // Concatenating updated_at gives us a fresh dedup_key per bump
    // while still being idempotent under same-cursor re-pulls.
    event_id: `gitea:notif:${notif.id}:${notif.updated_at}`,
    source: "gitea",
    target_agent,
    kind,
    summary,
    observed_at,
    raw: notif,
  };
}

/** Pull the trailing /<n> off a Gitea subject URL ("…/issues/42"). */
function extractNumber(url: string | undefined): number | null {
  if (!url) return null;
  const m = url.match(/\/(\d+)(?:\?|$|#)/);
  return m ? Number(m[1]) : null;
}
