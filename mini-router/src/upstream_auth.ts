/**
 * UpstreamAuth — abstraction over per-user credentials to upstream
 * services (Gitea today; chat/org/IAM tomorrow).
 *
 * Why this exists:
 *   M2-E.1 SSE wake requires Gitea cookie auth (PAT does not work on
 *   /user/events — Gitea rejects with `event: close, data: unauthorized`,
 *   which we observed in N=100 loadtest debugging on 2026-04-27).
 *   Cookie login is a Gitea-specific implementation detail. When an IAM
 *   layer (Keycloak / Authentik / Dex) is introduced, the path changes
 *   to OIDC client-credentials → bearer token, but consumers (SSE
 *   driver, REST client) shouldn't care: they just want "give me the
 *   header set that authorizes me as agent <X>".
 *
 *   By coding to UpstreamAuth, switching auth schemes at IAM time means
 *   adding one more impl (OidcAuth) and rewiring main.ts — no changes
 *   to GiteaSSE / fetcher / listener.
 *
 * Contract:
 *   ensureCredentials(): return a fresh credential set; impl decides
 *     whether to reuse a cached one or re-authenticate. Headers in
 *     `headers` are merged into outgoing requests.
 *   invalidate(): drop any cached credentials so the next ensure*() call
 *     forces re-auth. Called by consumers on 401/auth-close errors.
 */

export interface UpstreamCredentials {
  /** Headers to merge into outgoing requests (e.g. Cookie, Authorization). */
  headers: Record<string, string>;
  /** Epoch-ms when these credentials should no longer be trusted. Soft
   *  hint — consumers don't poll on this; invalidate() on 401 is the
   *  hard signal. */
  expiresAt: number;
}

export interface UpstreamAuth {
  ensureCredentials(): Promise<UpstreamCredentials>;
  invalidate(): void;
}
