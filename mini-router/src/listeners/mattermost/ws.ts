/**
 * Mattermost WebSocket driver — push channel for the mattermost listener.
 *
 * Lifecycle:
 *   run(signal) — connects, performs authentication_challenge, dispatches
 *                 each event to onEvent. Reconnects with exponential
 *                 backoff. Returns when signal aborts.
 *
 * Design parity with `listeners/gitea/sse.ts`:
 *   - Backoff w/ jitter
 *   - Heartbeat watchdog (mattermost emits regular events, configurable
 *     timeout — set to 0 to disable for tests)
 *   - onError callback for observability
 *   - connected / reconnects metrics gauges
 *   - graceful shutdown on AbortSignal
 *
 * Mattermost-specific quirks:
 *   - WS URL is HTTP(S) → WS(S) scheme switch
 *   - Auth via in-band JSON `authentication_challenge`, not header
 *   - First useful frame is `hello` (sent after server accepts auth)
 *   - All frames are JSON-encoded objects with {event, data, broadcast, seq}
 */
import WebSocket from "ws";
import type { MattermostWsEvent } from "./notification.ts";

export interface MattermostWSOptions {
  /** HTTP base URL of mattermost server, e.g. "http://mattermost:8065". */
  baseUrl: string;
  /** Personal access token. */
  token: string;
  /** Called for every WebSocket frame received (after auth ack). */
  onEvent: (ev: MattermostWsEvent) => void;
  /** Optional Host header override (we go through nginx-edge in some setups). */
  hostHeader?: string;
  /** Initial backoff between connect attempts (ms). Default 500. */
  initialBackoffMs?: number;
  /** Cap on backoff. Default 30s. */
  maxBackoffMs?: number;
  /** Watchdog timeout (ms). Default 0 (DISABLED).
   *
   * Mattermost server doesn't proactively send keepalive frames; events
   * arrive only when something happens in subscribed channels. A naive
   * "no frame in N seconds" watchdog will kill an idle but healthy
   * connection (a 60s watchdog loops forever on a quiet channel).
   *
   * Set to 0 to disable application-level watchdog and rely on WebSocket
   * protocol Ping/Pong + TCP keepalive. The ws library defaults to
   * automatic pong reply; if the server's pong is silent we still detect
   * via socket 'close' event, which triggers our reconnect loop.
   *
   * Set explicitly > 0 only if your operator wants extra-aggressive
   * dead-conn detection AND you've enabled application-level pings via
   * the WebSocket Ping frame (not implemented here yet). */
  heartbeatTimeoutMs?: number;
  /**
   * Interval between client-originated WebSocket PING frames (ms).
   * Default 30_000. Set to 0 to disable.
   *
   * This is not belt-and-braces, it is the connection's survival. Mattermost
   * closes a websocket whose peer has sent nothing before its read deadline
   * ("websocket.NextReader: closing websocket ... i/o timeout"), and the `ws`
   * library only AUTO-REPLIES to pings — it never originates them. So without
   * a client ping a connection carrying no events is silent by definition and
   * gets reaped. At 256 agents most sockets are lost that way, and because
   * mattermost never replays, many agents then receive zero events for the
   * entire run.
   *
   * A ping is a frame the server reads, so it resets that deadline. 30s is well
   * inside mattermost's default and costs 2 frames/minute/agent.
   */
  pingIntervalMs?: number;
  /** Fired after each successful (re)connect, once auth has been sent.
   *  The listener uses it to drain whatever arrived while the socket was down. */
  onConnect?: () => void;
  /** Inject sleep for tests. */
  sleep?: (ms: number) => Promise<void>;
  /** Errors callback (optional). */
  onError?: (e: unknown) => void;
}

export class MattermostWS {
  /** Number of (re)connect attempts performed. */
  reconnects = 0;
  /** True iff we currently believe a socket is open. */
  connected = false;
  /** Epoch-ms of last frame received (0 if none yet). */
  lastFrameAt = 0;

  constructor(private opts: MattermostWSOptions) {}

  async run(signal: AbortSignal): Promise<void> {
    const sleep = this.opts.sleep ?? defaultSleep;
    // A reconnect gap is time the agent spends not receiving DMs.
    const initial = this.opts.initialBackoffMs ?? 500;
    const cap = this.opts.maxBackoffMs ?? 30_000;
    let backoff = initial;
    while (!signal.aborted) {
      try {
        await this.connectOnce(signal);
        backoff = initial; // clean disconnect → reset
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
    const wsUrl = httpToWs(this.opts.baseUrl) + "/api/v4/websocket";
    this.reconnects++;
    const headers: Record<string, string> = {};
    if (this.opts.hostHeader) headers.Host = this.opts.hostHeader;
    const sock = new WebSocket(wsUrl, { headers });

    let onAbort = () => {
      try { sock.terminate(); } catch { /* noop */ }
    };
    signal.addEventListener("abort", onAbort, { once: true });

    let watchdog: NodeJS.Timeout | null = null;
    let pinger: NodeJS.Timeout | null = null;

    const closed = new Promise<void>((resolve, reject) => {
      sock.once("error", (err: Error) => reject(err));
      sock.once("close", () => resolve());
      sock.on("open", () => {
        // Send authentication_challenge.
        sock.send(JSON.stringify({
          seq: 1,
          action: "authentication_challenge",
          data: { token: this.opts.token },
        }));
        this.connected = true;
        this.lastFrameAt = Date.now();
        // Keep the connection non-silent. See pingIntervalMs.
        const pingMs = this.opts.pingIntervalMs ?? 30_000;
        if (pingMs > 0) {
          pinger = setInterval(() => {
            try { sock.ping(); } catch { /* socket already going down */ }
          }, pingMs);
        }
        // Drain anything posted while we were disconnected. Mattermost's
        // websocket does not replay, so without this a reconnect recovers the
        // channel but not the message that was missed on it.
        try { this.opts.onConnect?.(); } catch (err) { this.opts.onError?.(err); }
        // Install heartbeat watchdog (default OFF — mattermost server
        // doesn't send proactive keepalives, see option doc above).
        const ttl = this.opts.heartbeatTimeoutMs ?? 0;
        if (ttl > 0) {
          watchdog = setInterval(() => {
            if (Date.now() - this.lastFrameAt > ttl) {
              this.opts.onError?.(new Error(`mattermost ws heartbeat timeout (${ttl}ms)`));
              try { sock.terminate(); } catch { /* noop */ }
            }
          }, Math.max(500, Math.floor(ttl / 4)));
        }
      });
      sock.on("message", (data) => {
        this.lastFrameAt = Date.now();
        let parsed: unknown;
        try {
          parsed = JSON.parse(data.toString());
        } catch (err) {
          this.opts.onError?.(err);
          return;
        }
        // Auth ack frames have `status` not `event` — skip them silently.
        if (typeof parsed === "object" && parsed && "event" in parsed) {
          try {
            this.opts.onEvent(parsed as MattermostWsEvent);
          } catch (err) {
            this.opts.onError?.(err);
          }
        }
      });
    });

    try {
      await closed;
    } finally {
      if (watchdog) clearInterval(watchdog);
      if (pinger) clearInterval(pinger);
      signal.removeEventListener("abort", onAbort);
      this.connected = false;
    }
  }
}

function httpToWs(url: string): string {
  if (url.startsWith("http://")) return "ws://" + url.slice("http://".length);
  if (url.startsWith("https://")) return "wss://" + url.slice("https://".length);
  return url;
}

function defaultSleep(ms: number): Promise<void> {
  return new Promise((res) => setTimeout(res, ms));
}

export type { MattermostWsEvent };
