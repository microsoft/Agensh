/**
 * Gitea notification fetcher — the REST half of L1 (pull).
 *
 * Why pull is the source of truth, not SSE: Gitea SSE
 * (`GET /user/events`) emits a `notification-count` heartbeat but does
 * not replay events on reconnect (no Last-Event-ID semantics). SSE only
 * compresses our latency; correctness rests on the cursor-driven pull.
 *
 * This module returns a parsed page. The cursor lives in EventStore.
 *
 * Auth (Gitea quirk, 1.22.6):
 *   `/api/v1/notifications` is gated by Gitea's `reqToken` middleware
 *   which **rejects session cookies** with `401 token is required`.
 *   Conversely `/user/events` (SSE) is mounted under the web tree and
 *   **rejects PATs** with `event: close, data: unauthorized`. The two
 *   halves of the same workflow live behind two non-overlapping auth
 *   schemes — that is upstream's history, not our design.
 *
 *   So router must carry both:
 *     - PAT here (REST pull)
 *     - cookie session in the SSE driver
 *   Form-session authentication covers SSE; this module uses the PAT directly.
 *
 * Cursor semantics: we use `since=<RFC3339 timestamp>` and remember the
 * max(updated_at) of the last seen page. Gitea returns notifications
 * with `updated_at >= since`, sorted descending. If we ever see a page
 * larger than the page size, we walk pages.
 */

export const NOTIFICATION_PAGE_SIZE = 50;

export interface NotificationsPage {
  items: GiteaNotificationRaw[];
  /** Max(updated_at) across the page, or null on empty page. */
  maxUpdatedAt: string | null;
}

export interface GiteaNotificationRaw {
  id: number;
  unread?: boolean;
  pinned?: boolean;
  updated_at: string;
  url?: string;
  subject?: {
    title?: string;
    type?: string;
    url?: string;
    html_url?: string;
    state?: string;
    latest_comment_url?: string;
  };
  repository?: {
    full_name?: string;
  };
}

export interface FetchOptions {
  baseUrl: string;
  /** Gitea PAT. REST API only accepts PAT/Basic/OAuth2; cookie sessions
   *  are rejected by `reqToken`. The cookie path lives in the SSE driver. */
  token: string;
  /** ISO timestamp; pass null on first run to get all unread. */
  since: string | null;
  /** 1-based page number; omitted = the first page. */
  page?: number;
  /** Optional Host header override (we go through nginx-edge). */
  hostHeader?: string;
}

/**
 * Fetch one page of notifications. The caller decides whether to call
 * again (GiteaListener.pollOnce pages on a full page).
 *
 * Notes on Gitea API:
 *   - `since`: only notifications updated_at >= since
 *   - response is a JSON array (not paginated wrapper); pagination via
 *     `page` + `limit` query params + `Link` header
 */
export async function fetchNotificationsPage(
  opts: FetchOptions,
): Promise<NotificationsPage> {
  const params = new URLSearchParams();
  if (opts.since) params.set("since", opts.since);
  params.set("limit", String(NOTIFICATION_PAGE_SIZE));
  if (opts.page !== undefined && opts.page > 1) params.set("page", String(opts.page));

  const url = `${opts.baseUrl.replace(/\/$/, "")}/api/v1/notifications?${params.toString()}`;
  const headers: Record<string, string> = {
    Accept: "application/json",
    Authorization: `token ${opts.token}`,
  };
  if (opts.hostHeader) headers.Host = opts.hostHeader;

  const res = await fetch(url, { headers });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(
      `gitea notifications fetch failed: ${res.status} ${body.slice(0, 200)}`,
    );
  }
  const items = (await res.json()) as GiteaNotificationRaw[];
  let maxUpdatedAt: string | null = null;
  for (const it of items) {
    if (!maxUpdatedAt || it.updated_at > maxUpdatedAt) {
      maxUpdatedAt = it.updated_at;
    }
  }
  return { items, maxUpdatedAt };
}

/**
 * Compute the next cursor given the previous one and a freshly fetched
 * page. Rules:
 *   - if the page was empty, keep the old cursor
 *   - else advance to max(updated_at)
 *
 * We bias to **never go backwards** even if the server returns a
 * lower max(updated_at) than what we previously saw (defensive against
 * clock skew and re-indexing weirdness).
 */
export function advanceCursor(
  prev: string | null,
  page: NotificationsPage,
): string | null {
  if (!page.maxUpdatedAt) return prev;
  if (!prev) return page.maxUpdatedAt;
  return page.maxUpdatedAt > prev ? page.maxUpdatedAt : prev;
}
