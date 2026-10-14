/**
 * Gitea form-login UpstreamAuth implementation.
 *
 * Gitea's `/user/events` SSE endpoint rejects PAT (`Authorization: token
 * <pat>`) with `event: close, data: unauthorized` (Gitea 1.22.6). The
 * only auth scheme it accepts is the standard Gitea web session cookie `i_like_gitea`.
 *
 * Login flow (verified by curl from inside the router container):
 *   1. GET /user/login
 *      → Set-Cookie: i_like_gitea=<sess>; HttpOnly
 *      → Set-Cookie: _csrf=<csrf>; Max-Age=86400; HttpOnly
 *      The HTML form's hidden _csrf field equals the cookie _csrf value
 *      (same-origin double-submit pattern), so we don't parse HTML — we
 *      just echo the cookie value into the form body.
 *   2. POST /user/login (Cookie: i_like_gitea=...; _csrf=...)
 *      Body: user_name=<u>&password=<p>&_csrf=<csrf>
 *      Success: 303 See Other, Location: /, new Set-Cookie i_like_gitea
 *      Failure (bad creds): 200 OK with HTML error page (no redirect)
 *   3. Authenticated requests carry only the new i_like_gitea cookie.
 *
 * Session lifetime: Gitea's [session] LIFE_TIME defaults to 86400 (1d)
 * but we treat it as 6h to be safe — re-login is cheap (2 round trips)
 * and we'd rather refresh too eagerly than serve stale cookies.
 *
 * IAM future: when Gitea is fronted by OIDC, /user/login is usually
 * disabled or 302's to the IdP. We'll add OidcAuth as a sibling impl;
 * the SSE driver and fetcher stay untouched.
 */
import type { FetchLike } from "./listeners/gitea/fetcher.ts";
import type { UpstreamAuth, UpstreamCredentials } from "./upstream_auth.ts";

export interface GiteaFormAuthOptions {
  baseUrl: string;
  username: string;
  password: string;
  fetch?: FormFetchLike;
  /** Optional Host header (we go through nginx-edge in some setups). */
  hostHeader?: string;
  /** Cached cookie validity in ms. Default 6h. */
  sessionTtlMs?: number;
  now?: () => number;
  /** Lock the auth out after this many consecutive login failures.
   *  Default 5. Prevents reconnect storms when creds are wrong / IAM is
   *  down. */
  maxConsecutiveFailures?: number;
  /** Duration of the lockout window once the breaker trips. Default 60s. */
  lockMs?: number;
}

/**
 * Thrown by ensureCredentials() while the breaker is open. SSE driver
 * (and any other consumer) should treat this as "back off; do not
 * reconnect immediately" rather than a normal connect failure.
 */
export class AuthLockedError extends Error {
  constructor(
    public readonly remainingMs: number,
    public readonly lastError: string,
  ) {
    super(
      `auth locked for ${Math.ceil(remainingMs / 1000)}s (last error: ${lastError})`,
    );
    this.name = "AuthLockedError";
  }
}

/**
 * Form-login needs response headers (multiple Set-Cookie lines) and a
 * 303 status without auto-following — neither is exposed by the
 * pull-fetcher's FetchLike. We define a richer fetch shim here.
 */
export interface FormFetchLike {
  (
    input: string,
    init?: {
      method?: string;
      headers?: Record<string, string>;
      body?: string;
      redirect?: "manual" | "follow";
      signal?: AbortSignal;
    },
  ): Promise<{
    ok: boolean;
    status: number;
    headers: { get(name: string): string | null };
    text(): Promise<string>;
  }>;
}

const SESSION_COOKIE = "i_like_gitea";
const CSRF_COOKIE = "_csrf";
// 6h was the run length when this was written, which made the cookie outlive
// any single run by construction. Re-login on 401 still covers a longer run,
// but the point of the value is not to get there.
const DEFAULT_TTL_MS = 6 * 60 * 60 * 1000;
const DEFAULT_MAX_FAILURES = 5;
// While the breaker is tripped ensureCredentials() throws and the agent's
// Gitea wake channel is hard down.
const DEFAULT_LOCK_MS = 60 * 1000;

interface ParsedCookies {
  /** name → value */
  values: Record<string, string>;
}

export class GiteaFormAuth implements UpstreamAuth {
  private cached: UpstreamCredentials | null = null;
  private inflight: Promise<UpstreamCredentials> | null = null;
  private readonly fetch: FormFetchLike;
  private readonly now: () => number;
  // Circuit breaker state. consecutiveFailures resets to 0 on any
  // successful login. lockedUntil is the timestamp until which we
  // refuse to even try (and immediately throw AuthLockedError).
  private _consecutiveFailures = 0;
  private _totalFailures = 0;
  private lockedUntil = 0;
  private lastError = "";
  private readonly maxFailures: number;
  private readonly lockMs: number;

  constructor(private readonly opts: GiteaFormAuthOptions) {
    this.fetch =
      opts.fetch ?? (globalThis.fetch as unknown as FormFetchLike);
    this.now = opts.now ?? Date.now;
    this.maxFailures = opts.maxConsecutiveFailures ?? DEFAULT_MAX_FAILURES;
    this.lockMs = opts.lockMs ?? DEFAULT_LOCK_MS;
  }

  /** Number of consecutive login failures since the last success. */
  get consecutiveFailures(): number {
    return this._consecutiveFailures;
  }

  /** Cumulative login failures across the lifetime of this auth. */
  get totalLoginFailures(): number {
    return this._totalFailures;
  }

  /** True iff the breaker is currently open. */
  get locked(): boolean {
    return this.lockedUntil > this.now();
  }

  async ensureCredentials(): Promise<UpstreamCredentials> {
    if (this.cached && this.cached.expiresAt > this.now()) return this.cached;
    // Breaker open? short-circuit without touching Gitea.
    if (this.locked) {
      throw new AuthLockedError(
        this.lockedUntil - this.now(),
        this.lastError,
      );
    }
    if (this.inflight) return this.inflight;
    this.inflight = this.login()
      .then((c) => {
        this._consecutiveFailures = 0;
        this.lockedUntil = 0;
        return c;
      })
      .catch((e) => {
        this._totalFailures++;
        this._consecutiveFailures++;
        this.lastError = e instanceof Error ? e.message : String(e);
        if (this._consecutiveFailures >= this.maxFailures) {
          this.lockedUntil = this.now() + this.lockMs;
        }
        throw e;
      })
      .finally(() => {
        this.inflight = null;
      });
    return this.inflight;
  }

  invalidate(): void {
    this.cached = null;
  }

  /** Public so that adapters which translate UpstreamAuth → an external
   *  fetcher can present credentials as a single Cookie header. */
  static cookieHeader(creds: UpstreamCredentials): string | undefined {
    return creds.headers.Cookie;
  }

  private async login(): Promise<UpstreamCredentials> {
    const base = this.opts.baseUrl.replace(/\/$/, "");
    const baseHeaders: Record<string, string> = {};
    if (this.opts.hostHeader) baseHeaders.Host = this.opts.hostHeader;

    // Step 1: GET /user/login → cookies (i_like_gitea + _csrf).
    const r1 = await this.fetch(`${base}/user/login`, {
      method: "GET",
      headers: { ...baseHeaders, Accept: "text/html" },
    });
    if (!r1.ok) {
      const body = await r1.text().catch(() => "");
      throw new Error(
        `gitea login GET failed: ${r1.status} ${body.slice(0, 200)}`,
      );
    }
    const c1 = parseSetCookies(r1.headers);
    const sess1 = c1.values[SESSION_COOKIE];
    const csrf = c1.values[CSRF_COOKIE];
    if (!sess1 || !csrf) {
      throw new Error(
        `gitea login GET missing cookies (i_like_gitea=${!!sess1} _csrf=${!!csrf})`,
      );
    }

    // Step 2: POST /user/login (form body + carry both cookies).
    const form = new URLSearchParams();
    form.set("user_name", this.opts.username);
    form.set("password", this.opts.password);
    form.set("_csrf", csrf);
    const r2 = await this.fetch(`${base}/user/login`, {
      method: "POST",
      redirect: "manual",
      headers: {
        ...baseHeaders,
        "Content-Type": "application/x-www-form-urlencoded",
        Cookie: `${SESSION_COOKIE}=${sess1}; ${CSRF_COOKIE}=${csrf}`,
      },
      body: form.toString(),
    });
    // Successful Gitea login is 303 See Other → /. A 200 OK means we got
    // the login page back with an error message.
    if (r2.status !== 303) {
      const body = await r2.text().catch(() => "");
      throw new Error(
        `gitea login POST expected 303, got ${r2.status} ${body.slice(0, 200)}`,
      );
    }
    const c2 = parseSetCookies(r2.headers);
    const sess2 = c2.values[SESSION_COOKIE];
    if (!sess2) {
      throw new Error("gitea login POST missing i_like_gitea cookie");
    }

    const ttl = this.opts.sessionTtlMs ?? DEFAULT_TTL_MS;
    const creds: UpstreamCredentials = {
      headers: { Cookie: `${SESSION_COOKIE}=${sess2}` },
      expiresAt: this.now() + ttl,
    };
    this.cached = creds;
    return creds;
  }
}

/**
 * Parse Set-Cookie headers from a response. Standard fetch
 * `headers.get('set-cookie')` only returns one value (joined or first),
 * but we need every cookie. WHATWG fetch exposes `headers.getSetCookie()`
 * (Node 18.14+); we feature-detect and fall back to a comma-split for
 * test stubs.
 *
 * Comma-splitting Set-Cookie is technically lossy because Expires=
 * contains a comma (`Wdy, DD Mon YYYY ...`), but Gitea's cookies don't
 * use Expires (they use Max-Age + HttpOnly + SameSite), so this is
 * safe for our specific upstream.
 */
function parseSetCookies(headers: {
  get(name: string): string | null;
  getSetCookie?(): string[];
}): ParsedCookies {
  const lines: string[] = [];
  if (typeof headers.getSetCookie === "function") {
    lines.push(...headers.getSetCookie());
  } else {
    const raw = headers.get("set-cookie");
    if (raw) lines.push(...raw.split(/, (?=[^ ;=]+=)/));
  }
  const values: Record<string, string> = {};
  for (const line of lines) {
    const [pair] = line.split(";");
    if (!pair) continue;
    const eq = pair.indexOf("=");
    if (eq <= 0) continue;
    const name = pair.slice(0, eq).trim();
    const value = pair.slice(eq + 1).trim();
    values[name] = value;
  }
  return { values };
}
