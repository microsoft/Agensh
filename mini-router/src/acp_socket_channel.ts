/**
 * ACPSocketChannel — connects to a unix socket served by acp-bridge.py in the
 * agent container, from the mini-router sidecar.
 *
 * Each socket connection spawns an unmodified Copilot ACP process. We keep
 * one long-lived connection per channel for
 * cache reuse (session_id stable across prompts).
 *
 * Reconnect: prompt() detects dead connection → reconnects with backoff
 * [1s, 2s, 5s, 10s, 30s, 60s] (capped). Dispatcher only sees prompt()
 * resolve/reject — connection drama is hidden.
 */
import * as acp from "@agentclientprotocol/sdk";
import { createConnection, type Socket } from "node:net";
import type { UEM } from "./uem.ts";
import { errorMessage, sleep } from "./runtime.ts";

// Exhausting this ladder throws `acp connect exhausted`, which markFailed()s
// every row in the batch at once -- burning one of MAX_ATTEMPTS=5 for up to 32
// events.
const RECONNECT_BACKOFF_MS: readonly number[] = [1_000, 2_000, 5_000, 10_000, 30_000, 60_000];

export interface ACPSocketChannelOptions {
  socketPath: string;
  cwd: string;
  /** Optional: restore a sessionId across reconnects (cache continuity). */
  sessionStore: {
    get(): Promise<string | null>;
    set(sessionId: string): Promise<void>;
  };
  stuckMs?: number;
  /** Logger hook for connection drama (optional). */
  onLog?: (level: "info" | "warn" | "error", msg: string, err?: unknown) => void;
}

export class ACPSocketChannel {
  private socket: Socket | null = null;
  private connection: acp.ClientSideConnection | null = null;
  private sessionId: string | null = null;
  private lastUpdateAt = 0;
  private connecting: Promise<void> | null = null;
  /** Set when the previous prompt was force-closed by stuck-timeout.
   *  Prepended to the next prompt text so the agent learns the prior
   *  turn was killed for going silent (it should background long tools). */
  private pendingNotice: string | null = null;
  /**
   * DeLM forced read: rendered shared-context block spliced ahead of the next
   * prompt's text. Set by Dispatcher before each dispatch; consumed once.
   * null → prompt text is unchanged from the pre-board behavior.
   */
  private promptPrefix: string | null = null;
  private readonly log: (lvl: "info" | "warn" | "error", msg: string, err?: unknown) => void;

  constructor(private readonly opts: ACPSocketChannelOptions) {
    this.log = opts.onLog ?? ((lvl, m, e) => {
      // eslint-disable-next-line no-console
      console.error(`[acp-socket] ${lvl} ${m}`, e ?? "");
    });
  }

  async prompt(uem: unknown[]): Promise<{ stopReason: string }> {
    if (!this.connection || !this.sessionId) {
      await this.connectWithBackoff();
    }
    const events = uem as UEM[];
    let text = defaultRenderBatch(events);

    // If a previous turn was force-closed due to ACP silence,
    // prepend a system notice so the agent learns to use background
    // execution (& / nohup) for long-running tools next time.
    if (this.pendingNotice) {
      text = this.pendingNotice + "\n\n---\n\n" + text;
      this.pendingNotice = null;
    }

    // DeLM forced read: splice the rendered shared context ahead of the event
    // text so peer progress is always in context, without the agent having to
    // call a read tool. Consumed once per prompt.
    if (this.promptPrefix) {
      text = this.promptPrefix + "\n---\n\n" + text;
      this.promptPrefix = null;
    }

    return this.sendText(text);
  }

  /** Set (or clear with null) the shared-context prefix for the next prompt. */
  setPromptPrefix(prefix: string | null): void {
    this.promptPrefix = prefix;
  }

  /**
   * Send a raw text turn with no UEM rendering. Used for the DeLM
   * forced-write follow-up nudge.
   */
  async promptText(text: string): Promise<{ stopReason: string }> {
    if (!this.connection || !this.sessionId) {
      await this.connectWithBackoff();
    }
    return this.sendText(text);
  }

  /** Shared prompt-send path: watchdog + error handling. */
  private async sendText(text: string): Promise<{ stopReason: string }> {
    try {
      this.lastUpdateAt = Date.now();
      // Race conn.prompt against a silence-watchdog. The watchdog
      // checks `lastUpdateAt` (updated on every ACP RX in connectOnce); if
      // no RX for stuckMs, force-close the connection so prompt rejects.
      const stuckMs = this.opts.stuckMs;
      const promptP = this.connection!.prompt({
        sessionId: this.sessionId!,
        prompt: [{ type: "text", text }],
      });
      let res: { stopReason: string };
      if (stuckMs && stuckMs > 0) {
        const watchdog = this.watchSilence(stuckMs);
        try {
          res = (await Promise.race([promptP, watchdog.promise])) as { stopReason: string };
        } finally {
          watchdog.cancel();
        }
      } else {
        res = await promptP;
      }
      return { stopReason: res.stopReason };
    } catch (err) {
      // Connection died mid-prompt. Tear down so next call reconnects.
      this.log("warn", `prompt failed; closing connection`, err);
      await this.close();
      throw err;
    }
  }

  /** Returns a promise that rejects when no ACP RX has been observed for
   *  stuckMs. Polls every min(stuckMs/4, 5000)ms. cancel() stops the timer. */
  private watchSilence(stuckMs: number): {
    promise: Promise<never>;
    cancel: () => void;
  } {
    const tick = Math.max(50, Math.min(Math.floor(stuckMs / 4), 5000));
    let timer: NodeJS.Timeout | null = null;
    const promise = new Promise<never>((_, reject) => {
      const check = () => {
        const now = Date.now();
        const silentFor = now - this.lastUpdateAt;
        if (silentFor >= stuckMs) {
          this.log(
            "warn",
            `acp silence ${silentFor}ms >= stuckMs ${stuckMs}; force-closing connection`,
          );
          this.pendingNotice =
            `[system] previous turn timed out (no ACP message for ${Math.floor(silentFor / 1000)}s). ` +
            `Connection was reset. For long-running tools (tests, large bash scripts), ` +
            `run them in the background with & or nohup so you stay responsive to events.`;
          // Closing socket will cause conn.prompt() to reject; the catch
          // in prompt() also calls close() — idempotent.
          this.close().catch(() => undefined);
          reject(new Error(`acp prompt stuck: no RX for ${silentFor}ms`));
          return;
        }
        timer = setTimeout(check, tick);
      };
      timer = setTimeout(check, tick);
    });
    return {
      promise,
      cancel: () => {
        if (timer) {
          clearTimeout(timer);
          timer = null;
        }
      },
    };
  }

  async close(): Promise<void> {
    if (this.socket) {
      try { this.socket.destroy(); } catch { /* */ }
    }
    this.socket = null;
    this.connection = null;
    this.sessionId = null;
  }

  private async connectWithBackoff(): Promise<void> {
    if (this.connecting) return this.connecting;
    this.connecting = (async () => {
      let lastErr: unknown = null;
      for (let i = 0; i < RECONNECT_BACKOFF_MS.length; i++) {
        try {
          await this.connectOnce();
          return;
        } catch (e) {
          lastErr = e;
          const wait = RECONNECT_BACKOFF_MS[i]!;
          this.log("warn", `connect attempt ${i + 1} failed; sleeping ${wait}ms`, e);
          await sleep(wait);
        }
      }
      throw new Error(`acp connect exhausted: ${errorMessage(lastErr)}`);
    })();
    try {
      await this.connecting;
    } finally {
      this.connecting = null;
    }
  }

  private async connectOnce(): Promise<void> {
    this.log("info", `connectOnce: dialing ${this.opts.socketPath}`);
    const sock = await new Promise<Socket>((resolve, reject) => {
      const s = createConnection({ path: this.opts.socketPath });
      const onErr = (e: Error) => { s.removeListener("connect", onOk); reject(e); };
      const onOk = () => { s.removeListener("error", onErr); resolve(s); };
      s.once("error", onErr);
      s.once("connect", onOk);
    });
    this.socket = sock;
    this.log("info", `connectOnce: socket established`);

    // Detect socket close → reject any pending requests via SDK abort
    sock.on("close", () => {
      this.log("warn", `socket closed (peer EOF)`);
      // A failed attempt's socket can close after a later attempt connected;
      // it must not tear down the live connection.
      if (this.socket !== sock) return;
      // Force the connection to abort so prompt() rejects instead of hanging
      this.socket = null;
      this.connection = null;
      this.sessionId = null;
    });
    sock.on("error", (e) => {
      this.log("warn", `socket error`, e);
    });

    // Bridge node Socket (Duplex) to web streams expected by ACP SDK ndJsonStream.
    // CRITICAL: We hand-build the readable + writable instead of using Duplex.toWeb,
    // because the latter has subtle backpressure / pause-mode interactions with
    // bidirectional sockets that stop newSession-response bytes from flowing
    // (reproducible when mini-router connects to a socat-bridged python
    // acp_adapter).
    const readable = new ReadableStream<Uint8Array>({
      start: (controller) => {
        sock.on("data", (chunk: Buffer) => {
          this.log("info", `RX ${chunk.length}B: ${chunk.toString("utf8").slice(0, 200)}`);
          controller.enqueue(new Uint8Array(chunk.buffer, chunk.byteOffset, chunk.byteLength));
        });
        sock.on("end", () => {
          try { controller.close(); } catch { /* */ }
        });
        sock.on("error", (e) => {
          try { controller.error(e); } catch { /* */ }
        });
      },
      cancel() {
        sock.destroy();
      },
    });
    const writable = new WritableStream<Uint8Array>({
      write(chunk) {
        return new Promise<void>((resolve, reject) => {
          if (sock.writableEnded) { reject(new Error("socket already ended")); return; }
          // sock.write returns false → backpressure → wait for 'drain'
          const ok = sock.write(chunk, (err) => {
            if (err) reject(err);
            else if (ok) resolve();
          });
          if (!ok) sock.once("drain", () => resolve());
        });
      },
      close() {
        return new Promise<void>((resolve) => {
          sock.end(() => resolve());
        });
      },
      abort() {
        sock.destroy();
      },
    });
    const stream = acp.ndJsonStream(writable, readable);

    const conn = new acp.ClientSideConnection(
      () => clientImpl(() => {
        this.lastUpdateAt = Date.now();
      }),
      stream,
    );
    this.connection = conn;
    this.log("info", `connectOnce: ACP connection wired, sending initialize`);

    // A failed handshake must close its socket, or every reconnect attempt
    // leaks one, along with whatever the bridge accepted it into.
    try {
      // TIME-BOUNDED. An unanswered initialize would hang connectOnce forever, so
      // the reconnect loop would never get another turn.
      //
      // When acp-bridge.py's Popen hits the slice TasksMax, its serve thread dies
      // and leaves the socket ACCEPTED with no child behind it. The router logs
      // "socket established" and "sending initialize", then waits on a dead peer
      // while still ingesting events and waking a dispatcher that has nothing to
      // deliver to, and the agent is lost. A connect that succeeds at the socket
      // layer says nothing about whether an agent is actually behind it.
      const initMs = Number(process.env.ACP_INIT_TIMEOUT_MS ?? 60_000);
      await withTimeout(
        conn.initialize({
          protocolVersion: acp.PROTOCOL_VERSION,
          clientCapabilities: {
            fs: { readTextFile: false, writeTextFile: false },
          },
        }),
        initMs,
        `initialize did not answer within ${initMs}ms (socket up, no agent behind it)`,
      );
      this.log("info", `connectOnce: initialize OK, opening session`);

      const restoreId = await this.opts.sessionStore.get();
      let sessionId: string | null = null;
      if (restoreId) {
        try {
          await conn.loadSession({
            cwd: this.opts.cwd,
            sessionId: restoreId,
            mcpServers: [],
          });
          sessionId = restoreId;
        } catch {
          sessionId = null;
        }
      }
      if (!sessionId) {
        const ns = await conn.newSession({
          cwd: this.opts.cwd,
          mcpServers: [],
        });
        const newId = ns.sessionId;
        if (!newId) throw new Error("acp newSession returned no sessionId");
        sessionId = newId;
        await this.opts.sessionStore.set(newId);
      }
      const finalId = sessionId!;
      this.sessionId = finalId;
      this.log("info", `connected, sessionId=${finalId.slice(0, 8)}`);
    } catch (e) {
      sock.destroy();
      throw e;
    }
  }
}

function clientImpl(onSessionUpdate: () => void): acp.Client {
  return {
    async requestPermission(params: acp.RequestPermissionRequest) {
      return {
        outcome: {
          outcome: "selected" as const,
          optionId:
            params.options.find((o: acp.PermissionOption) => o.kind === "allow_once")?.optionId ??
            params.options[0]?.optionId ??
            "",
        },
      };
    },
    async sessionUpdate(_params: unknown) {
      onSessionUpdate();
    },
  };
}

import { defaultRenderBatch } from "./uem_render.ts";

/** Reject if `p` has not settled within `ms`, so a dead peer cannot stall a caller forever. */
function withTimeout<T>(p: Promise<T>, ms: number, msg: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(msg)), ms);
    p.then(
      (v) => { clearTimeout(timer); resolve(v); },
      (e) => { clearTimeout(timer); reject(e); },
    );
  });
}
