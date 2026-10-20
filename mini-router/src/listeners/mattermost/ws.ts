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
 *   - Client-originated WebSocket pings every 30 seconds
 *   - onError callback for observability
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
import { sleep } from "../../runtime.ts";

export interface MattermostWSOptions {
  /** HTTP base URL of mattermost server, e.g. "http://mattermost:8065". */
  baseUrl: string;
  /** Personal access token. */
  token: string;
  /** Called for every WebSocket frame received (after auth ack). */
  onEvent: (ev: MattermostWsEvent) => void;
  /** Optional Host header override (we go through nginx-edge in some setups). */
  hostHeader?: string;
  /** Fired after each successful (re)connect, once auth has been sent.
   *  The listener uses it to drain whatever arrived while the socket was down. */
  onConnect?: () => void;
  /** Errors callback (optional). */
  onError?: (e: unknown) => void;
}

export class MattermostWS {
  constructor(private opts: MattermostWSOptions) {}

  async run(signal: AbortSignal): Promise<void> {
    // A reconnect gap is time the agent spends not receiving DMs.
    const initial = 500;
    const cap = 30_000;
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
    const headers: Record<string, string> = {};
    if (this.opts.hostHeader) headers.Host = this.opts.hostHeader;
    const sock = new WebSocket(wsUrl, { headers });

    let onAbort = () => {
      try { sock.terminate(); } catch { /* noop */ }
    };
    signal.addEventListener("abort", onAbort, { once: true });

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
        // Client-originated pings keep Mattermost's read deadline alive.
        pinger = setInterval(() => {
          try { sock.ping(); } catch { /* socket already going down */ }
        }, 30_000);
        // Drain anything posted while we were disconnected. Mattermost's
        // websocket does not replay, so without this a reconnect recovers the
        // channel but not the message that was missed on it.
        try { this.opts.onConnect?.(); } catch (err) { this.opts.onError?.(err); }
      });
      sock.on("message", (data) => {
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
      if (pinger) clearInterval(pinger);
      signal.removeEventListener("abort", onAbort);
    }
  }
}

function httpToWs(url: string): string {
  if (url.startsWith("http://")) return "ws://" + url.slice("http://".length);
  if (url.startsWith("https://")) return "wss://" + url.slice("https://".length);
  return url;
}
