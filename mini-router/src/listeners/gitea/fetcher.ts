/**
 * Gitea notification fetcher — the REST half of L1 (pull).
 *
 * Why pull is the source of truth, not SSE: Gitea SSE
 * (`GET /user/events`) emits a `notification-count` heartbeat but does
 * not replay events on reconnect (no Last-Event-ID semantics). SSE only
 * compresses our latency; correctness rests on the cursor-driven pull.
 *
 * This module is deliberately I/O-only and stateless: it takes a
 * `fetch`-like injectable and returns a parsed page. The cursor lives
 * in `RouterState`.
 *
 * Auth (Gitea quirk — verified 2026-04-27 against 1.22.6):
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
 *   The `UpstreamAuth` abstraction therefore covers SSE only; this
 *   module deliberately stays on the simpler `token: string` field.
 *
 * Cursor semantics: we use `since=<RFC3339 timestamp>` and remember the
 * max(updated_at) of the last seen page. Gitea returns notifications
 * with `updated_at >= since`, sorted descending. If we ever see a page
 * larger than the page size, we walk pages.
 */

export interface FetchLike {
  (
    input: string,
    init?: { headers?: Record<string, string>; signal?: AbortSignal },
  ): Promise<{
    ok: boolean;
    status: number;
    text(): Promise<string>;
    json(): Promise<unknown>;
  }>;
}

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
  /** Include read notifications? Default false (unread only). */
  all?: boolean;
  /** Page size (Gitea max ~50). */
  limit?: number;
  fetch?: FetchLike;
  /** Optional Host header override (we go through nginx-edge). */
  hostHeader?: string;
}

/**
 * Fetch one page of notifications. The caller decides whether to call
 * again (e.g. on a saw-full-page heuristic).
 *
 * Notes on Gitea API:
 *   - `since`: only notifications updated_at >= since
 *   - `all=true`: include already-read; default unread-only
 *   - response is a JSON array (not paginated wrapper); pagination via
 *     `page` + `limit` query params + `Link` header
 */
export async function fetchNotificationsPage(
  opts: FetchOptions,
): Promise<NotificationsPage> {
  const f = opts.fetch ?? (globalThis.fetch as FetchLike);
  const params = new URLSearchParams();
  if (opts.since) params.set("since", opts.since);
  if (opts.all) params.set("all", "true");
  params.set("limit", String(opts.limit ?? 50));

  const url = `${opts.baseUrl.replace(/\/$/, "")}/api/v1/notifications?${params.toString()}`;
  const headers: Record<string, string> = {
    Accept: "application/json",
    Authorization: `token ${opts.token}`,
  };
  if (opts.hostHeader) headers.Host = opts.hostHeader;

  const res = await f(url, { headers });
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
