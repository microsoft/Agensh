/**
 * Per-agent Gitea form-session authentication.
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
 */
interface GiteaCredentials {
  headers: Record<string, string>;
  expiresAt: number;
}

export interface GiteaFormAuthOptions {
  baseUrl: string;
  username: string;
  password: string;
  /** Optional Host header (we go through nginx-edge in some setups). */
  hostHeader?: string;
}

/**
 * Thrown while the login circuit breaker is open; the SSE reconnect loop backs off.
 */
class AuthLockedError extends Error {
  constructor(
    remainingMs: number,
    lastError: string,
  ) {
    super(
      `auth locked for ${Math.ceil(remainingMs / 1000)}s (last error: ${lastError})`,
    );
    this.name = "AuthLockedError";
  }
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

export class GiteaFormAuth {
  private cached: GiteaCredentials | null = null;
  private inflight: Promise<GiteaCredentials> | null = null;
  // Circuit breaker state. consecutiveFailures resets to 0 on any
  // successful login. lockedUntil is the timestamp until which we
  // refuse to even try (and immediately throw AuthLockedError).
  private _consecutiveFailures = 0;
  private lockedUntil = 0;
  private lastError = "";

  constructor(private readonly opts: GiteaFormAuthOptions) {}

  /** True iff the breaker is currently open. */
  get locked(): boolean {
    return this.lockedUntil > Date.now();
  }

  async ensureCredentials(): Promise<GiteaCredentials> {
    if (this.cached && this.cached.expiresAt > Date.now()) return this.cached;
    // Breaker open? short-circuit without touching Gitea.
    if (this.locked) {
      throw new AuthLockedError(
        this.lockedUntil - Date.now(),
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
        this._consecutiveFailures++;
        this.lastError = e instanceof Error ? e.message : String(e);
        if (this._consecutiveFailures >= DEFAULT_MAX_FAILURES) {
          this.lockedUntil = Date.now() + DEFAULT_LOCK_MS;
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

  private async login(): Promise<GiteaCredentials> {
    const base = this.opts.baseUrl.replace(/\/$/, "");
    const baseHeaders: Record<string, string> = {};
    if (this.opts.hostHeader) baseHeaders.Host = this.opts.hostHeader;

    // Step 1: GET /user/login → cookies (i_like_gitea + _csrf).
    const r1 = await fetch(`${base}/user/login`, {
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
    const sess1 = c1[SESSION_COOKIE];
    const csrf = c1[CSRF_COOKIE];
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
    const r2 = await fetch(`${base}/user/login`, {
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
    const sess2 = c2[SESSION_COOKIE];
    if (!sess2) {
      throw new Error("gitea login POST missing i_like_gitea cookie");
    }

    const creds: GiteaCredentials = {
      headers: { Cookie: `${SESSION_COOKIE}=${sess2}` },
      expiresAt: Date.now() + DEFAULT_TTL_MS,
    };
    this.cached = creds;
    return creds;
  }
}

/** Parse the native Node 20+ fetch response's separate Set-Cookie lines. */
function parseSetCookies(headers: Headers): Record<string, string> {
  const values: Record<string, string> = {};
  for (const line of headers.getSetCookie()) {
    const [pair] = line.split(";");
    if (!pair) continue;
    const eq = pair.indexOf("=");
    if (eq <= 0) continue;
    const name = pair.slice(0, eq).trim();
    const value = pair.slice(eq + 1).trim();
    values[name] = value;
  }
  return values;
}
