/**
 * GiteaFormAuth unit tests.
 *
 * What we pin down:
 *   - Two-step login: GET /user/login captures cookies, POST submits
 *     form with the cookie-derived _csrf, expects 303.
 *   - The form body contains user_name, password, _csrf (and only those).
 *   - On 200 (login error page) we throw a typed error, not silently
 *     return stale creds.
 *   - ensureCredentials caches and only re-fetches after invalidate() or
 *     after expiresAt has passed.
 *   - Concurrent ensureCredentials() callers share one in-flight login.
 *   - cookieHeader() returns the merged Cookie string.
 */
import { describe, expect, it } from "vitest";
import {
  AuthLockedError,
  GiteaFormAuth,
  type FormFetchLike,
} from "../../mini-router/src/gitea_form_auth.ts";

interface Call {
  url: string;
  method: string;
  headers: Record<string, string> | undefined;
  body: string | undefined;
}

function makeFetch(
  responses: Array<{
    status: number;
    setCookie?: string[];
    body?: string;
  }>,
  calls: Call[] = [],
): { fetch: FormFetchLike; calls: Call[] } {
  let i = 0;
  const fetch: FormFetchLike = async (url, init) => {
    calls.push({
      url,
      method: init?.method ?? "GET",
      headers: init?.headers,
      body: init?.body,
    });
    const r = responses[i++];
    if (!r) throw new Error(`unexpected ${calls.length}th call to ${url}`);
    const sc = r.setCookie ?? [];
    return {
      ok: r.status >= 200 && r.status < 300,
      status: r.status,
      headers: {
        get(name: string) {
          if (name.toLowerCase() === "set-cookie") {
            return sc.length ? sc.join(", ") : null;
          }
          return null;
        },
        getSetCookie() {
          return sc;
        },
      },
      async text() {
        return r.body ?? "";
      },
    };
  };
  return { fetch, calls };
}

const GET_LOGIN_RESP = {
  status: 200,
  setCookie: [
    "i_like_gitea=sess1abc; Path=/; HttpOnly; SameSite=Lax",
    "_csrf=CSRFTOKEN1; Path=/; Max-Age=86400; HttpOnly; SameSite=Lax",
  ],
  body: "<html>login form</html>",
};
const POST_303 = {
  status: 303,
  setCookie: [
    "i_like_gitea=sess2logged; Path=/; HttpOnly; SameSite=Lax",
    "lang=en-US; Path=/; HttpOnly; SameSite=Lax",
    "_csrf=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax",
  ],
};

describe("GiteaFormAuth", () => {
  it("performs the two-step login and returns the post-login cookie", async () => {
    const calls: Call[] = [];
    const { fetch } = makeFetch([GET_LOGIN_RESP, POST_303], calls);
    const auth = new GiteaFormAuth({
      baseUrl: "http://gitea:3000/",
      username: "load1",
      password: "pw-of-load1",
      fetch,
      now: () => 1_000_000,
    });
    const creds = await auth.ensureCredentials();
    expect(creds.headers.Cookie).toBe("i_like_gitea=sess2logged");
    // Default TTL is 6h.
    expect(creds.expiresAt).toBe(1_000_000 + 6 * 60 * 60 * 1000);

    // Two calls fired.
    expect(calls).toHaveLength(2);
    const [g, p] = calls;
    expect(g!.url).toBe("http://gitea:3000/user/login");
    expect(g!.method).toBe("GET");
    expect(p!.url).toBe("http://gitea:3000/user/login");
    expect(p!.method).toBe("POST");
    expect(p!.headers!["Content-Type"]).toBe(
      "application/x-www-form-urlencoded",
    );
    // Both cookies forwarded into the POST.
    expect(p!.headers!.Cookie).toContain("i_like_gitea=sess1abc");
    expect(p!.headers!.Cookie).toContain("_csrf=CSRFTOKEN1");
    // Form body contains user_name, password, _csrf.
    const form = new URLSearchParams(p!.body ?? "");
    expect(form.get("user_name")).toBe("load1");
    expect(form.get("password")).toBe("pw-of-load1");
    expect(form.get("_csrf")).toBe("CSRFTOKEN1");
  });

  it("throws when the GET response is missing cookies", async () => {
    const { fetch } = makeFetch([{ status: 200, setCookie: [] }]);
    const auth = new GiteaFormAuth({
      baseUrl: "http://gitea:3000",
      username: "u",
      password: "p",
      fetch,
    });
    await expect(auth.ensureCredentials()).rejects.toThrow(/missing cookies/);
  });

  it("throws when POST returns 200 (login form re-render = bad creds)", async () => {
    const { fetch } = makeFetch([
      GET_LOGIN_RESP,
      {
        status: 200,
        setCookie: [],
        body: "<html>username or password is incorrect</html>",
      },
    ]);
    const auth = new GiteaFormAuth({
      baseUrl: "http://gitea:3000",
      username: "u",
      password: "wrong",
      fetch,
    });
    await expect(auth.ensureCredentials()).rejects.toThrow(/expected 303/);
  });

  it("throws when POST 303 response has no i_like_gitea cookie", async () => {
    const { fetch } = makeFetch([
      GET_LOGIN_RESP,
      { status: 303, setCookie: ["lang=en-US; Path=/"] },
    ]);
    const auth = new GiteaFormAuth({
      baseUrl: "http://gitea:3000",
      username: "u",
      password: "p",
      fetch,
    });
    await expect(auth.ensureCredentials()).rejects.toThrow(
      /missing i_like_gitea/,
    );
  });

  it("caches credentials until expiresAt elapses", async () => {
    let now = 1_000_000;
    const calls: Call[] = [];
    const { fetch } = makeFetch(
      [GET_LOGIN_RESP, POST_303, GET_LOGIN_RESP, POST_303],
      calls,
    );
    const auth = new GiteaFormAuth({
      baseUrl: "http://gitea:3000",
      username: "u",
      password: "p",
      fetch,
      sessionTtlMs: 1000,
      now: () => now,
    });
    const a = await auth.ensureCredentials();
    const b = await auth.ensureCredentials();
    expect(a).toBe(b);
    expect(calls).toHaveLength(2); // cached

    // Advance past TTL.
    now = 1_000_000 + 2000;
    const c = await auth.ensureCredentials();
    expect(c).not.toBe(a);
    expect(calls).toHaveLength(4);
  });

  it("invalidate() forces a fresh login on next ensureCredentials", async () => {
    const calls: Call[] = [];
    const { fetch } = makeFetch(
      [GET_LOGIN_RESP, POST_303, GET_LOGIN_RESP, POST_303],
      calls,
    );
    const auth = new GiteaFormAuth({
      baseUrl: "http://gitea:3000",
      username: "u",
      password: "p",
      fetch,
    });
    await auth.ensureCredentials();
    auth.invalidate();
    await auth.ensureCredentials();
    expect(calls).toHaveLength(4);
  });

  it("coalesces concurrent ensureCredentials() into one in-flight login", async () => {
    let resolveGet: ((v: unknown) => void) | null = null;
    const calls: Call[] = [];
    const fetch: FormFetchLike = async (url, init) => {
      calls.push({
        url,
        method: init?.method ?? "GET",
        headers: init?.headers,
        body: init?.body,
      });
      // Hold the GET open until the second caller has joined.
      if (calls.length === 1) {
        await new Promise((r) => {
          resolveGet = r;
        });
        return {
          ok: true,
          status: 200,
          headers: {
            get: () => null,
            getSetCookie: () => GET_LOGIN_RESP.setCookie!,
          },
          async text() {
            return "";
          },
        };
      }
      // Subsequent (POST).
      return {
        ok: false,
        status: 303,
        headers: {
          get: () => null,
          getSetCookie: () => POST_303.setCookie!,
        },
        async text() {
          return "";
        },
      };
    };
    const auth = new GiteaFormAuth({
      baseUrl: "http://gitea:3000",
      username: "u",
      password: "p",
      fetch,
    });
    const p1 = auth.ensureCredentials();
    const p2 = auth.ensureCredentials();
    // Wait a microtask, then unblock the GET.
    await new Promise((r) => setTimeout(r, 1));
    resolveGet!(undefined);
    const [a, b] = await Promise.all([p1, p2]);
    expect(a).toBe(b);
    // Only one (GET, POST) pair executed.
    expect(calls).toHaveLength(2);
  });

  it("after maxConsecutiveFailures, locks for lockMs and throws AuthLockedError without hitting Gitea", async () => {
    let now = 1_000_000;
    const calls: Call[] = [];
    // 3 bad responses, then we never call again during the lock window.
    const badGet = { status: 500, body: "gitea down" };
    const { fetch } = makeFetch([badGet, badGet, badGet], calls);
    const auth = new GiteaFormAuth({
      baseUrl: "http://gitea:3000",
      username: "u",
      password: "p",
      fetch,
      maxConsecutiveFailures: 3,
      lockMs: 60_000,
      now: () => now,
    });
    // Three failures push us into locked state.
    await expect(auth.ensureCredentials()).rejects.toThrow();
    await expect(auth.ensureCredentials()).rejects.toThrow();
    await expect(auth.ensureCredentials()).rejects.toThrow();
    expect(calls).toHaveLength(3);
    expect(auth.locked).toBe(true);

    // While locked, no network call, throws AuthLockedError.
    await expect(auth.ensureCredentials()).rejects.toBeInstanceOf(
      AuthLockedError,
    );
    expect(calls).toHaveLength(3);

    // Lock window passes → tries again (fails again here, but fetch is
    // exhausted so we just confirm a network call happened).
    now += 60_001;
    await expect(auth.ensureCredentials()).rejects.toThrow();
    expect(calls.length).toBeGreaterThan(3);
  });

  it("a successful login resets the consecutive-failure counter", async () => {
    const calls: Call[] = [];
    const { fetch } = makeFetch(
      [
        { status: 500, body: "transient" }, // fail 1
        { status: 500, body: "transient" }, // fail 2
        GET_LOGIN_RESP, // success starts here
        POST_303,
      ],
      calls,
    );
    const auth = new GiteaFormAuth({
      baseUrl: "http://gitea:3000",
      username: "u",
      password: "p",
      fetch,
      maxConsecutiveFailures: 3, // 2 fails should NOT lock
      lockMs: 60_000,
    });
    await expect(auth.ensureCredentials()).rejects.toThrow();
    await expect(auth.ensureCredentials()).rejects.toThrow();
    expect(auth.locked).toBe(false);
    // Now a success — should clear the counter so next failure starts fresh.
    const creds = await auth.ensureCredentials();
    expect(creds.headers.Cookie).toContain("i_like_gitea=");
    expect(auth.consecutiveFailures).toBe(0);
  });

  it("exposes failure metrics for /metrics rendering", async () => {
    const { fetch } = makeFetch([{ status: 500, body: "boom" }]);
    const auth = new GiteaFormAuth({
      baseUrl: "http://gitea:3000",
      username: "u",
      password: "p",
      fetch,
      maxConsecutiveFailures: 5,
    });
    expect(auth.totalLoginFailures).toBe(0);
    await expect(auth.ensureCredentials()).rejects.toThrow();
    expect(auth.totalLoginFailures).toBe(1);
    expect(auth.consecutiveFailures).toBe(1);
  });
});
