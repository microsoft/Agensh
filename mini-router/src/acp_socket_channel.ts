/**
 * Deliver prompts to Copilot over the agent container's Unix socket using ACP.
 * Persist session IDs in MySQL so reconnects can restore conversational state.
 */
import * as acp from "@agentclientprotocol/sdk";
import { createConnection, type Socket } from "node:net";
import type { UEM } from "./uem.ts";
import { errorMessage, sleep } from "./runtime.ts";

const RECONNECT_BACKOFF_MS: readonly number[] = [1_000, 2_000, 5_000, 10_000, 30_000, 60_000];

export interface ACPSocketChannelOptions {
  socketPath: string;
  cwd: string;
  sessionStore: {
    get(): Promise<string | null>;
    set(sessionId: string): Promise<void>;
  };
  stuckMs?: number;
  onLog?: (level: "info" | "warn" | "error", msg: string, err?: unknown) => void;
}

export class ACPSocketChannel {
  private socket: Socket | null = null;
  private connection: acp.ClientSideConnection | null = null;
  private sessionId: string | null = null;
  private lastUpdateAt = 0;
  private connecting: Promise<void> | null = null;
  private pendingNotice: string | null = null;
  private promptPrefix: string | null = null;
  private readonly log: (lvl: "info" | "warn" | "error", msg: string, err?: unknown) => void;

  constructor(private readonly opts: ACPSocketChannelOptions) {
    this.log = opts.onLog ?? ((lvl, m, e) => {
      console.error(`[acp-socket] ${lvl} ${m}`, e ?? "");
    });
  }

  async prompt(uem: unknown[]): Promise<{ stopReason: string }> {
    if (!this.connection || !this.sessionId) {
      await this.connectWithBackoff();
    }
    const events = uem as UEM[];
    let text = defaultRenderBatch(events);

    if (this.pendingNotice) {
      text = this.pendingNotice + "\n\n---\n\n" + text;
      this.pendingNotice = null;
    }

    if (this.promptPrefix) {
      // Shared context belongs to this prompt and must not leak into the next turn.
      text = this.promptPrefix + "\n---\n\n" + text;
      this.promptPrefix = null;
    }

    return this.sendText(text);
  }

  setPromptPrefix(prefix: string | null): void {
    this.promptPrefix = prefix;
  }

  async promptText(text: string): Promise<{ stopReason: string }> {
    if (!this.connection || !this.sessionId) {
      await this.connectWithBackoff();
    }
    return this.sendText(text);
  }

  private async sendText(text: string): Promise<{ stopReason: string }> {
    try {
      this.lastUpdateAt = Date.now();
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
      this.log("warn", `prompt failed; closing connection`, err);
      await this.close();
      throw err;
    }
  }

  private watchSilence(stuckMs: number): {
    promise: Promise<never>;
    cancel: () => void;
  } {
    // The optional watchdog measures time since a session update, not turn length.
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
      try { this.socket.destroy(); } catch {   }
    }
    this.socket = null;
    this.connection = null;
    this.sessionId = null;
  }

  private async connectWithBackoff(): Promise<void> {
    // Share concurrent callers' handshake instead of opening competing sessions.
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

    sock.on("close", () => {
      this.log("warn", `socket closed (peer EOF)`);
      if (this.socket !== sock) return;
      this.socket = null;
      this.connection = null;
      this.sessionId = null;
    });
    sock.on("error", (e) => {
      this.log("warn", `socket error`, e);
    });

    const readable = new ReadableStream<Uint8Array>({
      start: (controller) => {
        sock.on("data", (chunk: Buffer) => {
          this.log("info", `RX ${chunk.length}B: ${chunk.toString("utf8").slice(0, 200)}`);
          controller.enqueue(new Uint8Array(chunk.buffer, chunk.byteOffset, chunk.byteLength));
        });
        sock.on("end", () => {
          try { controller.close(); } catch {   }
        });
        sock.on("error", (e) => {
          try { controller.error(e); } catch {   }
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

    try {
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
      // A missing or unloadable native session starts fresh and replaces the ID.
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
  // Workers run autonomously; prefer ACP's one-time permission grant when offered.
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

function withTimeout<T>(p: Promise<T>, ms: number, msg: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(msg)), ms);
    p.then(
      (v) => { clearTimeout(timer); resolve(v); },
      (e) => { clearTimeout(timer); reject(e); },
    );
  });
}
