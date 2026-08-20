/**
 * Gitea SSE driver tests.
 *
 * Contract under test:
 *   - opens GET /user/events with `Authorization: token <PAT>` + Accept SSE
 *   - parses SSE frames; on `event: notification-count` fires onTrigger
 *   - on stream end / error, reconnects with exponential backoff (jittered)
 *   - stops cleanly on AbortSignal
 *
 * SSE is the LATENCY optimization (sub-second wakeup); the cursor poll
 * remains the source of truth. So we test:
 *   - the trigger fires when the SSE event arrives
 *   - reconnect happens on disconnect
 *   - we do NOT trust the SSE payload itself (no Last-Event-ID replay)
 */
import { describe, it, expect } from "vitest";
import { GiteaSSE } from "../../mini-router/src/listeners/gitea/sse.ts";
import type { FetchLike } from "../../mini-router/src/listeners/gitea/fetcher.ts";
import type {
  UpstreamAuth,
  UpstreamCredentials,
} from "../../mini-router/src/upstream_auth.ts";

/** Stub auth that returns a fixed cookie header set. */
function stubAuth(cookie = "i_like_gitea=test-sess"): UpstreamAuth & {
  invalidations: number;
  ensures: number;
} {
  let invalidations = 0;
  let ensures = 0;
  const a = {
    async ensureCredentials(): Promise<UpstreamCredentials> {
      ensures++;
      return { headers: { Cookie: cookie }, expiresAt: Date.now() + 3600_000 };
    },
    invalidate() {
      invalidations++;
    },
    get invalidations() {
      return invalidations;
    },
    get ensures() {
      return ensures;
    },
  };
  return a;
}

/**
 * Build a fake fetch that returns a controllable SSE response.
 * Each call to the returned fetch yields a fresh response whose body
 * we control via the returned `push` function.
 */
function makeSSEFetch(): {
  fetch: FetchLike;
  /** Push raw text into the current connection's body. */
  push: (chunk: string) => void;
  /** Close the current connection (simulates server-side disconnect). */
  closeCurrent: () => void;
  /** How many connections have been opened. */
  connections: () => number;
  /** Headers seen on the most recent connection. */
  lastHeaders: () => Record<string, string> | null;
  /** Wait until at least n connections have been opened. */
  waitConns: (n: number, timeoutMs?: number) => Promise<void>;
} {
  let conns = 0;
  let lastHeaders: Record<string, string> | null = null;
  let currentController: ReadableStreamDefaultController<Uint8Array> | null =
    null;
  const enc = new TextEncoder();

  const fetch: FetchLike = async (_url, init) => {
    conns++;
    lastHeaders = (init?.headers as Record<string, string>) ?? {};
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        currentController = controller;
      },
      cancel() {
        currentController = null;
      },
    });
    // The real fetch response object would have body as ReadableStream.
    // Our SSE driver uses fetch().body — so we expose it the same way.
    return {
      ok: true,
      status: 200,
      body: stream,
      async text() {
        return "";
      },
      async json() {
        return null;
      },
    } as unknown as Awaited<ReturnType<FetchLike>>;
  };

  return {
    fetch,
    push: (chunk) => {
      if (currentController) currentController.enqueue(enc.encode(chunk));
    },
    closeCurrent: () => {
      if (currentController) {
        try {
          currentController.close();
        } catch {
          /* already closed */
        }
        currentController = null;
      }
    },
    connections: () => conns,
    lastHeaders: () => lastHeaders,
    waitConns: async (n, timeoutMs = 1000) => {
      const deadline = Date.now() + timeoutMs;
      while (conns < n && Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 5));
      }
      if (conns < n) {
        throw new Error(`expected ${n} connections, got ${conns}`);
      }
    },
  };
}

describe("GiteaSSE", () => {
  it("opens GET /user/events with the right headers", async () => {
    const f = makeSSEFetch();
    const sse = new GiteaSSE({
      baseUrl: "http://gitea",
      auth: stubAuth(),
      onTrigger: () => {},
      fetch: f.fetch,
    });
    const ctrl = new AbortController();
    const done = sse.run(ctrl.signal);
    await f.waitConns(1);
    const h = f.lastHeaders()!;
    expect(h.Cookie).toBe("i_like_gitea=test-sess");
    expect(h.Authorization).toBeUndefined();
    expect((h.Accept ?? "").toLowerCase()).toContain("text/event-stream");
    ctrl.abort();
    f.closeCurrent();
    await done;
  });

  it("fires onTrigger when a notification-count event arrives", async () => {
    const f = makeSSEFetch();
    let triggers = 0;
    const sse = new GiteaSSE({
      baseUrl: "http://gitea",
      auth: stubAuth(),
      onTrigger: () => {
        triggers++;
      },
      fetch: f.fetch,
    });
    const ctrl = new AbortController();
    const done = sse.run(ctrl.signal);
    await f.waitConns(1);

    // SSE frame format: blank line terminates a frame.
    f.push("event: notification-count\ndata: 3\n\n");
    // Yield to let the parser tick.
    for (let i = 0; i < 10; i++) await new Promise((r) => setTimeout(r, 5));
    expect(triggers).toBe(1);

    // A frame split across two pushes still parses.
    f.push("event: notification-count\n");
    f.push("data: 5\n\n");
    for (let i = 0; i < 10; i++) await new Promise((r) => setTimeout(r, 5));
    expect(triggers).toBe(2);

    ctrl.abort();
    f.closeCurrent();
    await done;
  });

  it("ignores unrelated event types", async () => {
    const f = makeSSEFetch();
    let triggers = 0;
    const sse = new GiteaSSE({
      baseUrl: "http://gitea",
      auth: stubAuth(),
      onTrigger: () => {
        triggers++;
      },
      fetch: f.fetch,
    });
    const ctrl = new AbortController();
    const done = sse.run(ctrl.signal);
    await f.waitConns(1);

    f.push("event: stopwatches\ndata: []\n\n");
    f.push(": ping\n\n"); // SSE comment
    f.push("event: logout\ndata: 1\n\n");
    for (let i = 0; i < 10; i++) await new Promise((r) => setTimeout(r, 5));
    expect(triggers).toBe(0);

    ctrl.abort();
    f.closeCurrent();
    await done;
  });

  it("reconnects when the stream closes (with backoff stub)", async () => {
    const f = makeSSEFetch();
    const sleeps: number[] = [];
    const sse = new GiteaSSE({
      baseUrl: "http://gitea",
      auth: stubAuth(),
      onTrigger: () => {},
      fetch: f.fetch,
      // Stub out the backoff so the test runs instantly.
      sleep: async (ms) => {
        sleeps.push(ms);
      },
    });
    const ctrl = new AbortController();
    const done = sse.run(ctrl.signal);
    await f.waitConns(1);

    // Server-side disconnect → driver should reconnect.
    f.closeCurrent();
    await f.waitConns(2);

    // And again.
    f.closeCurrent();
    await f.waitConns(3);

    expect(sleeps.length).toBeGreaterThanOrEqual(2);
    // First backoff non-zero (we don't pin exact value — only that it's
    // bounded and growing-ish).
    expect(sleeps[0]).toBeGreaterThan(0);
    expect(sleeps[0]).toBeLessThan(60_000);

    ctrl.abort();
    f.closeCurrent();
    await done;
  });

  it("stops cleanly on abort and does not reconnect", async () => {
    const f = makeSSEFetch();
    const sse = new GiteaSSE({
      baseUrl: "http://gitea",
      auth: stubAuth(),
      onTrigger: () => {},
      fetch: f.fetch,
      sleep: async () => {},
    });
    const ctrl = new AbortController();
    const done = sse.run(ctrl.signal);
    await f.waitConns(1);

    ctrl.abort();
    f.closeCurrent();
    await done;
    const before = f.connections();
    // Wait a bit to confirm no further reconnect happens.
    await new Promise((r) => setTimeout(r, 50));
    expect(f.connections()).toBe(before);
  });

  // ----- additional coverage (M2-E.1 hardening) -------------------------

  it("treats HTTP non-2xx as a transient error and reconnects", async () => {
    // Gitea returns 401 if the token is rotated, 503 during restarts.
    // The driver must NOT crash the parent process — just reconnect.
    let conns = 0;
    let firstErr: unknown = null;
    let liveCtl: ReadableStreamDefaultController<Uint8Array> | null = null;
    const fetch: FetchLike = async () => {
      conns++;
      if (conns === 1) {
        return {
          ok: false,
          status: 503,
          body: null,
          async text() {
            return "service unavailable";
          },
          async json() {
            return null;
          },
        } as unknown as Awaited<ReturnType<FetchLike>>;
      }
      const stream = new ReadableStream<Uint8Array>({
        start(c) {
          liveCtl = c as ReadableStreamDefaultController<Uint8Array>;
        },
      });
      return {
        ok: true,
        status: 200,
        body: stream,
        async text() {
          return "";
        },
        async json() {
          return null;
        },
      } as unknown as Awaited<ReturnType<FetchLike>>;
    };
    const sleeps: number[] = [];
    const sse = new GiteaSSE({
      baseUrl: "http://gitea",
      auth: stubAuth(),
      onTrigger: () => {},
      fetch,
      sleep: async (ms) => {
        sleeps.push(ms);
      },
      onError: (e) => {
        firstErr ??= e;
      },
    });
    const ctrl = new AbortController();
    const done = sse.run(ctrl.signal);
    const deadline = Date.now() + 1000;
    while (conns < 2 && Date.now() < deadline)
      await new Promise((r) => setTimeout(r, 5));
    expect(conns).toBeGreaterThanOrEqual(2);
    expect(String((firstErr as Error)?.message ?? "")).toMatch(
      /503|service unavailable/i,
    );
    ctrl.abort();
    const c = liveCtl as ReadableStreamDefaultController<Uint8Array> | null;
    if (c) {
      try {
        c.close();
      } catch {
        /* */
      }
    }
    await done;
  });

  it("parses CRLF-terminated frames (Windows / proxied servers)", async () => {
    // Some HTTP intermediaries normalize \n to \r\n. The parser must
    // accept both — the SSE spec mandates either is valid.
    const f = makeSSEFetch();
    let triggers = 0;
    const sse = new GiteaSSE({
      baseUrl: "http://gitea",
      auth: stubAuth(),
      onTrigger: () => {
        triggers++;
      },
      fetch: f.fetch,
    });
    const ctrl = new AbortController();
    const done = sse.run(ctrl.signal);
    await f.waitConns(1);

    f.push("event: notification-count\r\ndata: 1\r\n\r\n");
    for (let i = 0; i < 10; i++) await new Promise((r) => setTimeout(r, 5));
    expect(triggers).toBe(1);

    ctrl.abort();
    f.closeCurrent();
    await done;
  });

  it("ignores SSE comments and keep-alive heartbeats", async () => {
    // Gitea (and many SSE servers) send `:keep-alive` comment lines to
    // keep the TCP connection from being reaped by middleboxes. They
    // are NOT events and must not influence trigger count or framing.
    const f = makeSSEFetch();
    let triggers = 0;
    const sse = new GiteaSSE({
      baseUrl: "http://gitea",
      auth: stubAuth(),
      onTrigger: () => {
        triggers++;
      },
      fetch: f.fetch,
    });
    const ctrl = new AbortController();
    const done = sse.run(ctrl.signal);
    await f.waitConns(1);

    f.push(":keep-alive\n\n");
    f.push(": some-comment\n\n");
    f.push("event: notification-count\ndata: 7\n\n");
    for (let i = 0; i < 10; i++) await new Promise((r) => setTimeout(r, 5));
    expect(triggers).toBe(1);

    ctrl.abort();
    f.closeCurrent();
    await done;
  });

  it("does not double-trigger when a frame has multiple data lines", async () => {
    // Per SSE spec, multi-line `data:` is concatenated on the consumer
    // side. We deliberately ignore data, but the framing must still
    // resolve to ONE event per frame, not one per `data:` line.
    const f = makeSSEFetch();
    let triggers = 0;
    const sse = new GiteaSSE({
      baseUrl: "http://gitea",
      auth: stubAuth(),
      onTrigger: () => {
        triggers++;
      },
      fetch: f.fetch,
    });
    const ctrl = new AbortController();
    const done = sse.run(ctrl.signal);
    await f.waitConns(1);

    f.push(
      "event: notification-count\ndata: line one\ndata: line two\ndata: line three\n\n",
    );
    for (let i = 0; i < 10; i++) await new Promise((r) => setTimeout(r, 5));
    expect(triggers).toBe(1);

    ctrl.abort();
    f.closeCurrent();
    await done;
  });

  it("backoff is bounded by maxBackoffMs", async () => {
    // With many consecutive failures the backoff doubles, but must
    // never exceed maxBackoffMs (set tight here so the cap is observable
    // within a few reconnect cycles).
    const f = makeSSEFetch();
    const sleeps: number[] = [];
    const sse = new GiteaSSE({
      baseUrl: "http://gitea",
      auth: stubAuth(),
      onTrigger: () => {},
      fetch: f.fetch,
      initialBackoffMs: 100,
      maxBackoffMs: 250,
      sleep: async (ms) => {
        sleeps.push(ms);
      },
    });
    const ctrl = new AbortController();
    const done = sse.run(ctrl.signal);

    // Force several reconnects.
    for (let i = 0; i < 6; i++) {
      await f.waitConns(i + 1);
      f.closeCurrent();
    }
    ctrl.abort();
    f.closeCurrent();
    await done;

    // Every recorded sleep must respect the cap (allowing for ±25% jitter
    // applied BEFORE the cap; the implementation does Math.min(jitter, cap)
    // so the value handed to sleep is ≤ cap).
    for (const s of sleeps) expect(s).toBeLessThanOrEqual(250);
    // And we should observe at least one near-cap value (growth happened).
    expect(Math.max(...sleeps)).toBeGreaterThanOrEqual(100);
  });

  it("clean disconnect resets the backoff to initial", async () => {
    // After a connection that opened cleanly (any trigger received before
    // disconnect), the backoff must reset — otherwise a flapping server
    // would push us to the cap and stay there.
    const f = makeSSEFetch();
    const sleeps: number[] = [];
    const sse = new GiteaSSE({
      baseUrl: "http://gitea",
      auth: stubAuth(),
      onTrigger: () => {},
      fetch: f.fetch,
      initialBackoffMs: 50,
      maxBackoffMs: 5_000,
      sleep: async (ms) => {
        sleeps.push(ms);
      },
    });
    const ctrl = new AbortController();
    const done = sse.run(ctrl.signal);

    await f.waitConns(1);
    f.closeCurrent(); // sleep #1 ≈ 50ms (initial)
    await f.waitConns(2);
    f.closeCurrent(); // sleep #2 ≈ 100ms (doubled)
    await f.waitConns(3);
    f.closeCurrent(); // sleep #3 ≈ 200ms (doubled again)
    await f.waitConns(4);

    ctrl.abort();
    f.closeCurrent();
    await done;

    // Reset semantics: every clean disconnect goes back to ~initial, so
    // every sleep observed here is a jittered ~50ms (initial), never
    // growing past initial × 1.25. If reset were broken we'd see 100/200
    // immediately on iterations 2/3.
    const initial = 50;
    for (const s of sleeps) {
      expect(s).toBeGreaterThanOrEqual(initial * 0.74);
      expect(s).toBeLessThanOrEqual(initial * 1.26);
    }
  });

  it("forwards onError when the fetch itself throws", async () => {
    // Network layer throw (DNS failure, TLS error, etc) — must be
    // captured via onError, not surfaced as an unhandled rejection.
    const errs: unknown[] = [];
    let attempt = 0;
    const fetch: FetchLike = async () => {
      attempt++;
      // Yield to the event loop so the test's setTimeout-based wait can
      // observe `errs.length` growing — otherwise the synchronous throw
      // path keeps the microtask queue saturated and starves macrotasks.
      await new Promise((r) => setTimeout(r, 1));
      throw new Error(`ECONNREFUSED #${attempt}`);
    };
    const sse = new GiteaSSE({
      baseUrl: "http://gitea",
      auth: stubAuth(),
      onTrigger: () => {},
      fetch,
      sleep: async () => {},
      onError: (e) => errs.push(e),
    });
    const ctrl = new AbortController();
    const done = sse.run(ctrl.signal);
    const deadline = Date.now() + 1000;
    while (errs.length < 2 && Date.now() < deadline)
      await new Promise((r) => setTimeout(r, 5));
    ctrl.abort();
    await done;

    expect(errs.length).toBeGreaterThanOrEqual(2);
    expect(String((errs[0] as Error).message)).toContain("ECONNREFUSED");
  });

  it("does not trigger when only an `event:` line arrives without frame end", async () => {
    // Half-frame in the buffer must NOT fire. If the connection drops
    // mid-frame, we drop the partial silently; the next connection's
    // pollOnce wake fires from the listener loop anyway.
    const f = makeSSEFetch();
    let triggers = 0;
    const sse = new GiteaSSE({
      baseUrl: "http://gitea",
      auth: stubAuth(),
      onTrigger: () => {
        triggers++;
      },
      fetch: f.fetch,
    });
    const ctrl = new AbortController();
    const done = sse.run(ctrl.signal);
    await f.waitConns(1);

    // Push a frame WITHOUT the terminating blank line.
    f.push("event: notification-count\ndata: 99\n");
    for (let i = 0; i < 10; i++) await new Promise((r) => setTimeout(r, 5));
    expect(triggers).toBe(0);

    // Now complete the frame.
    f.push("\n");
    for (let i = 0; i < 10; i++) await new Promise((r) => setTimeout(r, 5));
    expect(triggers).toBe(1);

    ctrl.abort();
    f.closeCurrent();
    await done;
  });

  it("includes Host header when configured", async () => {
    // We go through nginx-edge which routes by Host header — the SSE
    // driver must honour the override the same way the cursor fetcher does.
    const f = makeSSEFetch();
    const sse = new GiteaSSE({
      baseUrl: "http://nginx-edge",
      auth: stubAuth(),
      onTrigger: () => {},
      fetch: f.fetch,
      hostHeader: "gitea.localhost",
    });
    const ctrl = new AbortController();
    const done = sse.run(ctrl.signal);
    await f.waitConns(1);

    expect(f.lastHeaders()!.Host).toBe("gitea.localhost");

    ctrl.abort();
    f.closeCurrent();
    await done;
  });

  it("survives a synchronous throw inside onTrigger", async () => {
    // A buggy listener throwing in onTrigger must NOT poison the SSE
    // loop — subsequent triggers must still fire.
    const f = makeSSEFetch();
    let triggers = 0;
    const errs: unknown[] = [];
    const sse = new GiteaSSE({
      baseUrl: "http://gitea",
      auth: stubAuth(),
      onTrigger: () => {
        triggers++;
        if (triggers === 1) throw new Error("downstream boom");
      },
      fetch: f.fetch,
      onError: (e) => errs.push(e),
    });
    const ctrl = new AbortController();
    const done = sse.run(ctrl.signal);
    await f.waitConns(1);

    f.push("event: notification-count\ndata: a\n\n");
    f.push("event: notification-count\ndata: b\n\n");
    for (let i = 0; i < 10; i++) await new Promise((r) => setTimeout(r, 5));
    expect(triggers).toBe(2);
    expect(errs.length).toBe(1);

    ctrl.abort();
    f.closeCurrent();
    await done;
  });

  // ----- M2-E.2: cookie auth + heartbeat watchdog ----------------------

  it("invalidates auth and reconnects on `event: close, data: unauthorized`", async () => {
    // Gitea closes the SSE stream with `event: close\ndata: unauthorized`
    // when the cookie has expired or never authenticated. The driver
    // must call auth.invalidate() so the next ensureCredentials() does
    // a fresh login, and reconnect.
    const auth = stubAuth("i_like_gitea=stale");
    const f = makeSSEFetch();
    const sse = new GiteaSSE({
      baseUrl: "http://gitea",
      auth,
      onTrigger: () => {},
      fetch: f.fetch,
      sleep: async () => {},
    });
    const ctrl = new AbortController();
    const done = sse.run(ctrl.signal);
    await f.waitConns(1);

    f.push("event: close\ndata: unauthorized\n\n");

    // After receiving the close frame the driver should reconnect.
    await f.waitConns(2);
    expect(auth.invalidations).toBeGreaterThanOrEqual(1);

    ctrl.abort();
    f.closeCurrent();
    await done;
  });

  it("invalidates auth on HTTP 401 from /user/events", async () => {
    // 401 on the SSE handshake also indicates a stale cookie.
    let conns = 0;
    let liveCtl: ReadableStreamDefaultController<Uint8Array> | null = null;
    const fetch: FetchLike = async () => {
      conns++;
      if (conns === 1) {
        return {
          ok: false,
          status: 401,
          body: null,
          async text() {
            return "unauthorized";
          },
          async json() {
            return null;
          },
        } as unknown as Awaited<ReturnType<FetchLike>>;
      }
      const stream = new ReadableStream<Uint8Array>({
        start(c) {
          liveCtl = c as ReadableStreamDefaultController<Uint8Array>;
        },
      });
      return {
        ok: true,
        status: 200,
        body: stream,
        async text() {
          return "";
        },
        async json() {
          return null;
        },
      } as unknown as Awaited<ReturnType<FetchLike>>;
    };
    const auth = stubAuth();
    const sse = new GiteaSSE({
      baseUrl: "http://gitea",
      auth,
      onTrigger: () => {},
      fetch,
      sleep: async () => {},
    });
    const ctrl = new AbortController();
    const done = sse.run(ctrl.signal);
    const deadline = Date.now() + 1000;
    while (conns < 2 && Date.now() < deadline)
      await new Promise((r) => setTimeout(r, 5));
    expect(auth.invalidations).toBeGreaterThanOrEqual(1);
    ctrl.abort();
    const c = liveCtl as ReadableStreamDefaultController<Uint8Array> | null;
    if (c) {
      try {
        c.close();
      } catch {
        /* */
      }
    }
    await done;
  });

  it("watchdog cancels a silent connection and reconnects", async () => {
    // Half-closed TCP (NAT timeout, LB reaping idle conns) shows up as
    // "reader.read() never returns". Without the watchdog the driver
    // would hang forever. With heartbeatTimeoutMs=300 we expect:
    //   1. open #1
    //   2. push nothing, wait 300ms+
    //   3. watchdog fires reader.cancel() → loop exits → reconnect
    //   4. open #2
    const f = makeSSEFetch();
    const errs: unknown[] = [];
    const sse = new GiteaSSE({
      baseUrl: "http://gitea",
      auth: stubAuth(),
      onTrigger: () => {},
      fetch: f.fetch,
      sleep: async () => {},
      onError: (e) => errs.push(e),
      heartbeatTimeoutMs: 300,
    });
    const ctrl = new AbortController();
    const done = sse.run(ctrl.signal);

    await f.waitConns(1);
    // Do NOT push anything → watchdog must fire after ~300ms.
    await f.waitConns(2, 3000);
    expect(
      errs.some((e) =>
        String((e as Error)?.message ?? "").includes("heartbeat timeout"),
      ),
    ).toBe(true);

    ctrl.abort();
    f.closeCurrent();
    await done;
  });

  it("watchdog stays quiet while frames arrive within timeout", async () => {
    // Gitea sends notification-count ~30s as a keep-alive. With
    // hbTimeout=300 and a frame every 100ms, the watchdog must NOT fire.
    const f = makeSSEFetch();
    const errs: unknown[] = [];
    const sse = new GiteaSSE({
      baseUrl: "http://gitea",
      auth: stubAuth(),
      onTrigger: () => {},
      fetch: f.fetch,
      sleep: async () => {},
      onError: (e) => errs.push(e),
      heartbeatTimeoutMs: 300,
    });
    const ctrl = new AbortController();
    const done = sse.run(ctrl.signal);
    await f.waitConns(1);

    for (let i = 0; i < 10; i++) {
      f.push(":keep-alive\n\n");
      await new Promise((r) => setTimeout(r, 80));
    }
    expect(f.connections()).toBe(1);
    expect(errs).toHaveLength(0);

    ctrl.abort();
    f.closeCurrent();
    await done;
  });
});
