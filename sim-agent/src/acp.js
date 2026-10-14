/**
 * acp.js — the ACP server half of the sim agent.
 *
 * Speaks newline-delimited JSON-RPC on stdio. acp-bridge.py turns that into the
 * per-agent unix socket the mini-router connects to, so this file implements
 * exactly the surface `mini-router/src/acp_socket_channel.ts` drives and nothing
 * more:
 *
 *   initialize     -> capabilities (loadSession MUST be true; without it the
 *                     router opens a new session on every reconnect and the
 *                     prompt-cache continuity path is never exercised)
 *   session/new    -> {sessionId, modes:null}
 *   session/load   -> {modes:null}
 *   session/prompt -> {stopReason:"end_turn"}
 *
 * STDOUT IS THE PROTOCOL. Every diagnostic goes to stderr; a stray console.log
 * here would be parsed as a JSON-RPC frame by the router. (The router tolerates
 * non-JSON noise lines, but relying on that is asking for a debugging session
 * nobody wants.)
 */

const DEFAULT_PROTOCOL_VERSION = 1;

export function log(...args) {
  process.stderr.write(`[sim-agent] ${args.join(" ")}\n`);
}

/**
 * @param {object} opts
 * @param {(text: string, emit: Emitter) => Promise<{stopReason: string}>} opts.onPrompt
 * @param {NodeJS.ReadableStream} [opts.input]
 * @param {NodeJS.WritableStream} [opts.output]
 */
export function startAcpServer({ onPrompt, input = process.stdin, output = process.stdout }) {
  let sessionId = null;
  let buf = "";

  const send = (msg) => output.write(JSON.stringify(msg) + "\n");
  const reply = (id, result) => send({ jsonrpc: "2.0", id, result });
  const replyError = (id, message) =>
    send({ jsonrpc: "2.0", id, error: { code: -32000, message } });

  /**
   * Emitter for session/update notifications. The router feeds these to
   * TurnObserver (turn_observer.ts:73), which builds the TurnSummary that
   * step_loop turns into the next step's observation AND into its no-progress
   * signature. A turn that ran tools but emitted nothing reads as a stalled
   * agent and gets nudged, so reporting is not optional.
   */
  const makeEmitter = () => {
    let seq = 0;
    const update = (update) => send({ jsonrpc: "2.0", method: "session/update", params: { sessionId, update } });
    return {
      message(text) {
        update({ sessionUpdate: "agent_message_chunk", content: { type: "text", text } });
      },
      /** @returns {string} toolCallId — pass it to toolResult() */
      toolCall(title, kind = "other") {
        const toolCallId = `sim-${++seq}`;
        update({ sessionUpdate: "tool_call", toolCallId, title, kind, status: "pending" });
        return toolCallId;
      },
      toolResult(toolCallId, status, text) {
        update({
          sessionUpdate: "tool_call_update",
          toolCallId,
          status,
          ...(text ? { content: [{ type: "content", content: { type: "text", text } }] } : {}),
        });
      },
    };
  };

  async function handle(msg) {
    const { id, method, params } = msg;
    switch (method) {
      case "initialize":
        reply(id, {
          protocolVersion: Number(params?.protocolVersion) || DEFAULT_PROTOCOL_VERSION,
          agentCapabilities: {
            loadSession: true,
            promptCapabilities: { audio: false, embeddedContext: false, image: false, meta: false },
            mcpCapabilities: { http: false, sse: false },
          },
          authMethods: [],
        });
        return;

      case "session/new":
        // Stable per-process id. The router persists it via sessionStore and
        // hands it back on reconnect through session/load.
        sessionId = `sim-${process.pid}-${Date.now().toString(36)}`;
        reply(id, { sessionId, modes: null });
        return;

      case "session/load":
        // Always accept: the sim's durable state lives in a state file keyed by
        // agent name, not in the ACP session, so any id the router remembers is
        // resumable by construction.
        sessionId = params?.sessionId ?? sessionId;
        reply(id, { modes: null });
        return;

      case "session/prompt": {
        const text = (params?.prompt ?? [])
          .filter((b) => b && b.type === "text" && typeof b.text === "string")
          .map((b) => b.text)
          .join("\n");
        const emit = makeEmitter();
        try {
          const res = await onPrompt(text, emit);
          reply(id, { stopReason: res?.stopReason ?? "end_turn" });
        } catch (e) {
          // A policy crash must not wedge the turn: the router would sit on this
          // request until its stuck-watchdog fired, which looks like a hung agent
          // rather than a broken sim.
          log(`prompt failed: ${e?.stack ?? e}`);
          emit.message(`sim policy error: ${e?.message ?? e}`);
          reply(id, { stopReason: "end_turn" });
        }
        return;
      }

      case "session/cancel":
        // Notification in ACP (no id). Nothing to cancel — turns are short.
        if (id !== undefined) reply(id, null);
        return;

      default:
        if (id !== undefined) replyError(id, `sim-agent: unsupported method ${method}`);
    }
  }

  // Decoded as one stream, so a multibyte character split across chunks survives.
  input.setEncoding("utf8");
  input.on("data", (chunk) => {
    buf += chunk;
    const lines = buf.split("\n");
    buf = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.trim()) continue;
      let msg;
      try {
        msg = JSON.parse(line);
      } catch {
        continue; // the router emits none, but be as tolerant as it is
      }
      if (!msg.method) continue; // a response to something we sent; we send no requests
      handle(msg).catch((e) => log(`handler crashed: ${e?.stack ?? e}`));
    }
  });

  input.on("end", () => {
    log("stdin closed, exiting");
    process.exit(0);
  });

  return { get sessionId() { return sessionId; } };
}
