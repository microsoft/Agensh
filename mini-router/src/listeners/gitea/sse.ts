/**
 * Gitea SSE driver — push-only wakeup channel.
 *
 * Why push-only:
 *   PAT does not authorize /user/events (Gitea 1.22 rejects with
 *   `event: close, data: unauthorized`). Cookie auth is the only way.
 *   We use an injected UpstreamAuth so the same SSE driver works under
 *   form-cookie today and OIDC tomorrow without code change.
 *
 *   There is no polling fallback: at N=300 agents a 5s polling floor
 *   adds 60 QPS of empty-response noise to Gitea. SSE is
 *   the sole wake channel, with a heartbeat watchdog to detect silent
 *   half-close and reconnect.
 *
 * Architecture rules:
 *   - This module emits TRIGGERS, not data. We never trust the SSE
 *     payload — it has no Last-Event-ID replay semantics. Every trigger
 *     just causes the listener to call `pollOnce()` immediately to read
 *     the per-user-filtered /api/v1/notifications endpoint.
 *   - On disconnect we reconnect with exponential backoff + jitter.
 *   - On `event: close, data: unauthorized` we invalidate the cached
 *     credentials and reconnect (forces fresh login on next attempt).
 *   - Watchdog: if no frame arrives within heartbeatTimeoutMs the
 *     connection is presumed dead (NAT silent-close, mid-box reaped
 *     idle TCP, …) and we cancel the reader to force a reconnect.
 *     Gitea natively emits `notification-count` ~every 30s as a
 *     keep-alive, so a 45s default timeout has 50% margin.
 *
 * Lifecycle:
 *   run(signal) — connects, parses SSE frames, calls onTrigger on
 *                 `notification-count`. Returns when the signal aborts.
 */
import type { FetchLike } from "./fetcher.ts";
import type { UpstreamAuth } from "../../upstream_auth.ts";

export interface GiteaSSEOptions {
  baseUrl: string;
  /** Per-user auth provider (cookie today, OIDC tomorrow). */
  auth: UpstreamAuth;
  /** Called when a notification-count event arrives. */
  onTrigger: () => void;
  /** Optional Host header (we go through nginx-edge in some setups). */
  hostHeader?: string;
  /** Inject a fetch (tests). */
  fetch?: FetchLike;
  /** Inject a sleep (tests). Default: real setTimeout. */
  sleep?: (ms: number) => Promise<void>;
  /** First retry delay; doubles up to maxBackoffMs. Default 500ms. */
  initialBackoffMs?: number;
  /** Cap on backoff. Default 30s. */
  maxBackoffMs?: number;
  /** Watchdog: kill the connection if no frame within this many ms.
   *  Default 45_000. Set to 0 to disable (tests). */
  heartbeatTimeoutMs?: number;
  /** Optional log callback for visibility (errors only). */
  onError?: (e: unknown) => void;
  /** Status callbacks for observability (metrics). */
  onConnected?: () => void;
  onDisconnected?: () => void;
}

/** Subset of fetch().body — undici returns ReadableStream<Uint8Array>. */
type SSEResponse = {
  ok: boolean;
  status: number;
  body?: ReadableStream<Uint8Array> | null;
  text(): Promise<string>;
};

const TRIGGER_EVENT = "notification-count";
const CLOSE_EVENT = "close";
const UNAUTHORIZED_DATA = "unauthorized";

export class GiteaSSE {
  /** Number of (re)connects performed. Exposed for metrics. */
  reconnects = 0;
  /** Whether the driver currently believes it has an open connection. */
  connected = false;
  /** Epoch-ms of last frame received (0 if none yet). */
  lastFrameAt = 0;

  constructor(private readonly opts: GiteaSSEOptions) {}

  async run(signal: AbortSignal): Promise<void> {
    const sleep = this.opts.sleep ?? defaultSleep;
    // A reconnect gap is time the agent gets no issue/PR wakeups. Twin of the
    // Mattermost ws.ts backoff; the two halves of this recovery path must agree.
    const initial = this.opts.initialBackoffMs ?? 500;
    const cap = this.opts.maxBackoffMs ?? 30_000;
    let backoff = initial;

    while (!signal.aborted) {
      try {
        await this.connectOnce(signal);
        // A clean disconnect: reset backoff to initial.
        backoff = initial;
      } catch (e) {
        this.opts.onError?.(e);
      }
      if (signal.aborted) break;
      const jitter = backoff * (0.75 + Math.random() * 0.5);
      await sleep(Math.min(jitter, cap));
      backoff = Math.min(backoff * 2, cap);
    }
  }

  private async connectOnce(signal: AbortSignal): Promise<void> {
    const f = this.opts.fetch ?? (globalThis.fetch as unknown as FetchLike);
    const url = `${this.opts.baseUrl.replace(/\/$/, "")}/user/events`;

    const creds = await this.opts.auth.ensureCredentials();
    const headers: Record<string, string> = {
      ...creds.headers,
      Accept: "text/event-stream",
      "Cache-Control": "no-cache",
    };
    if (this.opts.hostHeader) headers.Host = this.opts.hostHeader;

    this.reconnects++;
    const res = (await f(url, { headers, signal })) as unknown as SSEResponse;
    if (!res.ok || !res.body) {
      const body = await res.text().catch(() => "");
      // 401/403 → cached cookie is stale, force re-login next time.
      if (res.status === 401 || res.status === 403) {
        this.opts.auth.invalidate();
      }
      throw new Error(
        `gitea SSE connect failed: ${res.status} ${body.slice(0, 200)}`,
      );
    }

    this.connected = true;
    this.opts.onConnected?.();
    this.lastFrameAt = Date.now();

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";

    // Heartbeat watchdog: cancels the reader if no frame is observed
    // within heartbeatTimeoutMs. Gitea sends notification-count ~30s,
    // default timeout 45s gives 50% margin. Half-closed TCP (NAT timeout,
    // load-balancer reaping idle conns) shows up as "reader.read() never
    // returns" — without this watchdog the loop would hang forever.
    // A half-closed stream left undetected is time the agent receives no
    // Gitea wakeups at all.
    const hbTimeout = this.opts.heartbeatTimeoutMs ?? 45_000;
    let watchdog: ReturnType<typeof setInterval> | null = null;
    if (hbTimeout > 0) {
      watchdog = setInterval(() => {
        if (Date.now() - this.lastFrameAt > hbTimeout) {
          this.opts.onError?.(
            new Error(
              `gitea SSE heartbeat timeout (${hbTimeout}ms without frame)`,
            ),
          );
          // cancel() resolves the in-flight reader.read() with done=true.
          reader.cancel().catch(() => {
            /* best-effort */
          });
        }
      }, Math.max(1000, Math.floor(hbTimeout / 4)));
    }

    let unauthorized = false;
    try {
      while (!signal.aborted) {
        const { value, done } = await reader.read();
        if (done) return;
        this.lastFrameAt = Date.now();
        buf += decoder.decode(value, { stream: true });
        let idx: number;
        while ((idx = findFrameEnd(buf)) !== -1) {
          const frame = buf.slice(0, idx);
          buf = buf.slice(idx + frameDelimLen(buf, idx));
          const fr = parseFrame(frame);
          if (fr.event === CLOSE_EVENT && fr.data === UNAUTHORIZED_DATA) {
            // Gitea explicitly told us our session is no good. Invalidate
            // and abort this connection — outer loop will reconnect with
            // fresh credentials.
            unauthorized = true;
            this.opts.auth.invalidate();
            return;
          }
          if (fr.event === TRIGGER_EVENT) {
            try {
              this.opts.onTrigger();
            } catch (e) {
              this.opts.onError?.(e);
            }
          }
        }
      }
    } finally {
      if (watchdog) clearInterval(watchdog);
      try {
        reader.releaseLock();
      } catch {
        /* best-effort */
      }
      this.connected = false;
      this.opts.onDisconnected?.();
      if (unauthorized) {
        // Treat unauthorized close as an error path so backoff applies
        // and we don't tight-loop the auth flow.
        throw new Error("gitea SSE unauthorized — session invalidated");
      }
    }
  }
}

interface ParsedFrame {
  event: string;
  data: string;
}

function parseFrame(frame: string): ParsedFrame {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of frame.split(/\r?\n/)) {
    if (!line || line.startsWith(":")) continue;
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  return { event, data: dataLines.join("\n") };
}

/** Find the index of the first frame terminator ("\n\n" or "\r\n\r\n"). */
function findFrameEnd(buf: string): number {
  const a = buf.indexOf("\n\n");
  const b = buf.indexOf("\r\n\r\n");
  if (a === -1) return b;
  if (b === -1) return a;
  return Math.min(a, b);
}

function frameDelimLen(buf: string, idx: number): number {
  return buf.startsWith("\r\n\r\n", idx) ? 4 : 2;
}

function defaultSleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
