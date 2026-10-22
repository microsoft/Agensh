/** Maintain a token-authenticated Mattermost WebSocket and reconnect with jitter. */
import WebSocket from "ws";
import type { MattermostWsEvent } from "./notification.ts";
import { sleep } from "../../runtime.ts";

export interface MattermostWSOptions {
  baseUrl: string;
  token: string;
  onEvent: (ev: MattermostWsEvent) => void;
  hostHeader?: string;
  onConnect?: () => void;
  onError?: (e: unknown) => void;
}

export class MattermostWS {
  constructor(private opts: MattermostWSOptions) {}

  async run(signal: AbortSignal): Promise<void> {
    const initial = 500;
    const cap = 30_000;
    let backoff = initial;
    while (!signal.aborted) {
      try {
        await this.connectOnce(signal);
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
    const wsUrl = httpToWs(this.opts.baseUrl) + "/api/v4/websocket";
    const headers: Record<string, string> = {};
    if (this.opts.hostHeader) headers.Host = this.opts.hostHeader;
    const sock = new WebSocket(wsUrl, { headers });

    let onAbort = () => {
      try { sock.terminate(); } catch {   }
    };
    signal.addEventListener("abort", onAbort, { once: true });

    let pinger: NodeJS.Timeout | null = null;

    const closed = new Promise<void>((resolve, reject) => {
      sock.once("error", (err: Error) => reject(err));
      sock.once("close", () => resolve());
      sock.on("open", () => {
        // Mattermost authenticates inside the socket protocol after the upgrade.
        sock.send(JSON.stringify({
          seq: 1,
          action: "authentication_challenge",
          data: { token: this.opts.token },
        }));
        pinger = setInterval(() => {
          try { sock.ping(); } catch {   }
        }, 30_000);
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
