/**
 * Gitea notification fetcher unit tests with an injected fetch.
 *
 * We don't hit a real Gitea here — that's what tests/f5_router does.
 * What we want to pin down at this layer:
 *   - URL construction (since=, all=, limit=, Host header)
 *   - Authorization: token <PAT> header (REST endpoint requires PAT;
 *     cookies are rejected by Gitea's reqToken middleware — verified
 *     2026-04-27 against 1.22.6).
 *   - cursor advancement (max updated_at, never goes backwards)
 *   - error path (non-2xx surfaces as a typed Error)
 */
import { describe, expect, it, vi } from "vitest";
import {
  advanceCursor,
  fetchNotificationsPage,
  type FetchLike,
  type GiteaNotificationRaw,
} from "../../mini-router/src/listeners/gitea/fetcher.ts";

function fakeFetch(opts: {
  body: GiteaNotificationRaw[];
  status?: number;
  capture?: { url?: string; headers?: Record<string, string> };
}): FetchLike {
  return async (url, init) => {
    if (opts.capture) {
      opts.capture.url = url;
      opts.capture.headers = init?.headers;
    }
    return {
      ok: (opts.status ?? 200) < 400,
      status: opts.status ?? 200,
      async text() {
        return JSON.stringify(opts.body);
      },
      async json() {
        return opts.body;
      },
    };
  };
}

describe("fetchNotificationsPage", () => {
  it("constructs the expected URL with cursor + PAT auth header", async () => {
    const cap: { url?: string; headers?: Record<string, string> } = {};
    const fetch = fakeFetch({ body: [], capture: cap });
    await fetchNotificationsPage({
      baseUrl: "http://gitea:3000/",
      token: "PAT-abc123",
      since: "2026-04-27T08:00:00Z",
      all: true,
      limit: 25,
      fetch,
    });
    expect(cap.url).toBe(
      "http://gitea:3000/api/v1/notifications" +
        "?since=2026-04-27T08%3A00%3A00Z&all=true&limit=25",
    );
    expect(cap.headers).toMatchObject({
      Authorization: "token PAT-abc123",
      Accept: "application/json",
    });
  });

  it("omits since when null and includes Host when given", async () => {
    const cap: { url?: string; headers?: Record<string, string> } = {};
    await fetchNotificationsPage({
      baseUrl: "http://gitea:3000",
      token: "PAT",
      since: null,
      hostHeader: "gitea.localhost",
      fetch: fakeFetch({ body: [], capture: cap }),
    });
    expect(cap.url).not.toContain("since=");
    expect(cap.headers).toMatchObject({ Host: "gitea.localhost" });
  });

  it("returns the parsed list and computes max(updated_at)", async () => {
    const body: GiteaNotificationRaw[] = [
      {
        id: 3,
        updated_at: "2026-04-27T08:01:00Z",
        subject: { title: "c", type: "Issue" },
      },
      {
        id: 1,
        updated_at: "2026-04-27T08:03:00Z",
        subject: { title: "a", type: "Pull" },
      },
      {
        id: 2,
        updated_at: "2026-04-27T08:02:00Z",
        subject: { title: "b", type: "Issue" },
      },
    ];
    const page = await fetchNotificationsPage({
      baseUrl: "http://gitea",
      token: "PAT",
      since: null,
      fetch: fakeFetch({ body }),
    });
    expect(page.items).toHaveLength(3);
    expect(page.maxUpdatedAt).toBe("2026-04-27T08:03:00Z");
  });

  it("returns null max(updated_at) on empty page", async () => {
    const page = await fetchNotificationsPage({
      baseUrl: "http://gitea",
      token: "PAT",
      since: null,
      fetch: fakeFetch({ body: [] }),
    });
    expect(page.items).toEqual([]);
    expect(page.maxUpdatedAt).toBeNull();
  });

  it("throws on non-2xx with a useful error", async () => {
    const fetch = vi.fn(async () => ({
      ok: false,
      status: 500,
      async text() {
        return "oops";
      },
      async json() {
        return {};
      },
    })) as unknown as FetchLike;
    await expect(
      fetchNotificationsPage({
        baseUrl: "http://gitea",
        token: "PAT",
        since: null,
        fetch,
      }),
    ).rejects.toThrow(/500.*oops/);
  });
});

describe("advanceCursor", () => {
  it("keeps prev on empty page", () => {
    expect(advanceCursor("X", { items: [], maxUpdatedAt: null })).toBe("X");
  });

  it("adopts maxUpdatedAt on first run", () => {
    expect(
      advanceCursor(null, {
        items: [],
        maxUpdatedAt: "2026-04-27T08:00:00Z",
      }),
    ).toBe("2026-04-27T08:00:00Z");
  });

  it("never goes backwards (defensive against clock skew)", () => {
    expect(
      advanceCursor("2026-05-01T00:00:00Z", {
        items: [],
        maxUpdatedAt: "2026-04-27T00:00:00Z",
      }),
    ).toBe("2026-05-01T00:00:00Z");
  });

  it("advances when newer", () => {
    expect(
      advanceCursor("2026-04-27T07:00:00Z", {
        items: [],
        maxUpdatedAt: "2026-04-27T09:00:00Z",
      }),
    ).toBe("2026-04-27T09:00:00Z");
  });
});
