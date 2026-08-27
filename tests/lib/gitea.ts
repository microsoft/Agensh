/**
 * Thin Gitea REST client routed through nginx-edge.
 *
 * Always sends the `Host: gitea.${EDGE_DOMAIN}` header so the request
 * matches the nginx-edge server block. Tests should never bypass nginx
 * to talk to Gitea directly — that path is the one we ship in prod.
 */
export interface GiteaResponse<T = unknown> {
  status: number;
  ok: boolean;
  data: T;
  text: string;
  headers: Headers;
}

export class GiteaClient {
  constructor(
    public readonly baseUrl: string,
    public readonly hostHeader: string,
    private readonly auth?:
      | { kind: "basic"; user: string; password: string }
      | { kind: "token"; token: string },
  ) {}

  static withBasic(
    baseUrl: string,
    hostHeader: string,
    user: string,
    password: string,
  ): GiteaClient {
    return new GiteaClient(baseUrl, hostHeader, {
      kind: "basic",
      user,
      password,
    });
  }

  withToken(token: string): GiteaClient {
    return new GiteaClient(this.baseUrl, this.hostHeader, {
      kind: "token",
      token,
    });
  }

  private buildHeaders(extra?: HeadersInit): Headers {
    const h = new Headers(extra);
    // NOTE: do NOT set Host here. Node 20's undici fetch silently strips
    // user-supplied Host headers. Routing via virtual host is achieved by
    // putting the hostname in baseUrl (e.g. http://gitea.localhost:28080).
    if (!h.has("accept")) h.set("Accept", "application/json");
    if (this.auth) {
      if (this.auth.kind === "basic") {
        const enc = Buffer.from(
          `${this.auth.user}:${this.auth.password}`,
        ).toString("base64");
        h.set("Authorization", `Basic ${enc}`);
      } else {
        h.set("Authorization", `token ${this.auth.token}`);
      }
    }
    return h;
  }

  async request<T = unknown>(
    method: string,
    path: string,
    options: { body?: unknown; timeoutMs?: number; headers?: HeadersInit } = {},
  ): Promise<GiteaResponse<T>> {
    const { body, timeoutMs = 30_000, headers } = options;
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const h = this.buildHeaders(headers);
      let payload: BodyInit | undefined;
      if (body !== undefined) {
        h.set("Content-Type", "application/json");
        payload = JSON.stringify(body);
      }
      const res = await fetch(`${this.baseUrl}${path}`, {
        method,
        headers: h,
        body: payload,
        signal: ctrl.signal,
      });
      const text = await res.text();
      let data: T = undefined as T;
      if (text) {
        try {
          data = JSON.parse(text) as T;
        } catch {
          // Non-JSON body — leave data undefined, callers can use .text.
        }
      }
      return {
        status: res.status,
        ok: res.ok,
        data,
        text,
        headers: res.headers,
      };
    } finally {
      clearTimeout(timer);
    }
  }

  get<T = unknown>(path: string): Promise<GiteaResponse<T>> {
    return this.request<T>("GET", path);
  }

  post<T = unknown>(path: string, body: unknown): Promise<GiteaResponse<T>> {
    return this.request<T>("POST", path, { body });
  }

  patch<T = unknown>(path: string, body: unknown): Promise<GiteaResponse<T>> {
    return this.request<T>("PATCH", path, { body });
  }

  put<T = unknown>(path: string, body?: unknown): Promise<GiteaResponse<T>> {
    return this.request<T>("PUT", path, body === undefined ? {} : { body });
  }

  delete<T = unknown>(path: string): Promise<GiteaResponse<T>> {
    return this.request<T>("DELETE", path);
  }
}

// --- common Gitea types (only the fields the tests touch) ----------------

export interface GiteaUser {
  id: number;
  login: string;
  email: string;
}

export interface GiteaIssue {
  id: number;
  number: number;
  title: string;
  body: string;
  state: "open" | "closed";
  user: GiteaUser;
  comments: number;
  created_at: string;
  updated_at: string;
}

export interface GiteaComment {
  id: number;
  body: string;
  user: GiteaUser;
  created_at: string;
}

export interface GiteaPullRequest {
  id: number;
  number: number;
  state: "open" | "closed";
  merged: boolean;
  title: string;
  body: string;
  head: { sha: string; ref: string; label: string };
  base: { sha: string; ref: string; label: string };
}
