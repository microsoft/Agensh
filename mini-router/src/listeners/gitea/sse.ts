/**
 * Maintain Gitea's cookie-authenticated SSE connection with heartbeat recovery.
 * notification-count frames wake REST ingestion; they are not event payloads.
 */
import type { GiteaFormAuth } from "../../gitea_form_auth.ts";
import { sleep } from "../../runtime.ts";

export interface GiteaSSEOptions {
  baseUrl: string;
  auth: GiteaFormAuth;
  onTrigger: () => void;
  hostHeader?: string;
  onError?: (e: unknown) => void;
}

const TRIGGER_EVENT = "notification-count";
const CLOSE_EVENT = "close";
const UNAUTHORIZED_DATA = "unauthorized";

export class GiteaSSE {
  connected = false;
  lastFrameAt = 0;

  constructor(private readonly opts: GiteaSSEOptions) {}

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
    const url = `${this.opts.baseUrl.replace(/\/$/, "")}/user/events`;

    const creds = await this.opts.auth.ensureCredentials();
    const headers: Record<string, string> = {
      ...creds.headers,
      Accept: "text/event-stream",
      "Cache-Control": "no-cache",
    };
    if (this.opts.hostHeader) headers.Host = this.opts.hostHeader;

    const res = await fetch(url, { headers, signal });
    if (!res.ok || !res.body) {
      const body = await res.text().catch(() => "");
      if (res.status === 401 || res.status === 403) {
        this.opts.auth.invalidate();
      }
      throw new Error(
        `gitea SSE connect failed: ${res.status} ${body.slice(0, 200)}`,
      );
    }

    this.connected = true;
    this.lastFrameAt = Date.now();

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";

    const hbTimeout = 45_000;
    // A silent stream is canceled so the outer loop can authenticate and reconnect.
    const watchdog = setInterval(() => {
        if (Date.now() - this.lastFrameAt > hbTimeout) {
          this.opts.onError?.(
            new Error(
              `gitea SSE heartbeat timeout (${hbTimeout}ms without frame)`,
            ),
          );
          reader.cancel().catch(() => {
          });
        }
    }, Math.max(1000, Math.floor(hbTimeout / 4)));

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
      clearInterval(watchdog);
      try {
        reader.releaseLock();
      } catch {
      }
      this.connected = false;
      if (unauthorized) {
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

function findFrameEnd(buf: string): number {
  // Accept both newline conventions without splitting a partially received frame.
  const a = buf.indexOf("\n\n");
  const b = buf.indexOf("\r\n\r\n");
  if (a === -1) return b;
  if (b === -1) return a;
  return Math.min(a, b);
}

function frameDelimLen(buf: string, idx: number): number {
  return buf.startsWith("\r\n\r\n", idx) ? 4 : 2;
}
