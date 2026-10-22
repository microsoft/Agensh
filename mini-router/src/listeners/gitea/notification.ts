/** Convert a Gitea notification revision into a stable event ID and short summary. */
import type { UEM } from "../../uem.ts";
import type { GiteaNotificationRaw } from "./fetcher.ts";

export function giteaNotificationToUEM(
  notif: GiteaNotificationRaw,
  target_agent: string,
  observed_at: number,
): UEM {
  const subj = notif.subject ?? {};
  const repo = notif.repository?.full_name ?? "?";
  const title = subj.title ?? "(no title)";
  const kind = (subj.type ?? "Unknown").toLowerCase();
  const num = extractNumber(subj.url ?? subj.html_url);
  const ref = num !== null ? ` #${num}` : "";
  const summary = `${repo} ${kind}${ref}: ${title}`;
  return {
    // Include the revision timestamp so later updates to one thread remain distinct.
    event_id: `gitea:notif:${notif.id}:${notif.updated_at}`,
    source: "gitea",
    target_agent,
    kind,
    summary,
    observed_at,
    raw: notif,
  };
}

function extractNumber(url: string | undefined): number | null {
  if (!url) return null;
  const m = url.match(/\/(\d+)(?:\?|$|#)/);
  return m ? Number(m[1]) : null;
}
