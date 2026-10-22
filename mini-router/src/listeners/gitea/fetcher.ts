/** Fetch token-authenticated notification pages and advance a monotonic cursor. */
export const NOTIFICATION_PAGE_SIZE = 50;

export interface NotificationsPage {
  items: GiteaNotificationRaw[];
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
  token: string;
  since: string | null;
  page?: number;
  hostHeader?: string;
}

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

export function advanceCursor(
  prev: string | null,
  page: NotificationsPage,
): string | null {
  if (!page.maxUpdatedAt) return prev;
  if (!prev) return page.maxUpdatedAt;
  return page.maxUpdatedAt > prev ? page.maxUpdatedAt : prev;
}
