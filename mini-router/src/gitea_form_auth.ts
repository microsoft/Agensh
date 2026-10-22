/**
 * Obtain and cache browser-session cookies for Gitea's /user/events SSE feed.
 * The notifications REST API uses a separate token; it cannot authenticate SSE.
 */
interface GiteaCredentials {
  headers: Record<string, string>;
  expiresAt: number;
}

export interface GiteaFormAuthOptions {
  baseUrl: string;
  username: string;
  password: string;
  hostHeader?: string;
}

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
const DEFAULT_TTL_MS = 6 * 60 * 60 * 1000;
const DEFAULT_MAX_FAILURES = 5;
const DEFAULT_LOCK_MS = 60 * 1000;

export class GiteaFormAuth {
  private cached: GiteaCredentials | null = null;
  private inflight: Promise<GiteaCredentials> | null = null;
  private _consecutiveFailures = 0;
  private lockedUntil = 0;
  private lastError = "";

  constructor(private readonly opts: GiteaFormAuthOptions) {}

  get locked(): boolean {
    return this.lockedUntil > Date.now();
  }

  async ensureCredentials(): Promise<GiteaCredentials> {
    if (this.cached && this.cached.expiresAt > Date.now()) return this.cached;
    if (this.locked) {
      throw new AuthLockedError(
        this.lockedUntil - Date.now(),
        this.lastError,
      );
    }
    if (this.inflight) return this.inflight;
    // Coalesce reconnect attempts and back off after repeated login failures.
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

    const form = new URLSearchParams();
    // Submit the CSRF cookie with the form and retain the post-login session cookie.
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
