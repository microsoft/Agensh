/**
 * turn_observer — reconstructs what an ACP turn produced.
 *
 * Needed by the step-loop mode (variant 2). DeLM's runner can build each
 * step's observation trivially because it executes the tool itself: the ACI
 * returns the command output straight to the loop
 * (implementer_runner.py feeds `obs` into the next `agent.step`). We do not
 * execute anything — copilot-CLI does — so the only way to know what a turn
 * did is to watch the `session/update` notifications stream past and rebuild
 * an observation from them.
 *
 * ACP emits these update kinds during a turn (copilot-CLI 1.0.70):
 *   agent_thought_chunk   — reasoning text, deliberately DROPPED (noise, and
 *                           replaying a model's own reasoning back at it in
 *                           the next step tends to entrench mistakes)
 *   agent_message_chunk   — assistant text addressed to the user
 *   tool_call             — a tool invocation starting (name + args)
 *   tool_call_update      — its result / status
 *
 * We keep the last N tool calls and the assistant text, then render a compact
 * observation. Everything is best-effort: an unrecognized payload shape is
 * ignored rather than throwing, because a malformed update must never break
 * the turn.
 */

export interface ToolRecord {
  name: string;
  status: string;
  /** Truncated result/output text, when the update carried one. */
  output?: string;
}

export interface TurnSummary {
  /** Assistant text emitted this turn (thought chunks excluded). */
  message: string;
  /** Tool calls observed, in order. */
  tools: ToolRecord[];
  /** Raw count before truncation, so the observation can say "N more". */
  toolCallCount: number;
}

const MAX_TOOLS_RENDERED = 8;
const MAX_TOOL_OUTPUT_CHARS = 600;
const MAX_MESSAGE_CHARS = 2000;

function truncate(s: string, n: number): string {
  const t = s.trim();
  if (t.length <= n) return t;
  return t.slice(0, n) + `… (+${t.length - n} chars)`;
}

/** Pull a plausible text payload out of the several shapes ACP uses. */
function textOf(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) return content.map(textOf).filter(Boolean).join("");
  if (content && typeof content === "object") {
    const o = content as Record<string, unknown>;
    if (typeof o["text"] === "string") return o["text"];
    if (o["content"] !== undefined) return textOf(o["content"]);
  }
  return "";
}

/**
 * Accumulates session/update notifications for one turn. Construct one per
 * turn, feed it every update, then call summary().
 */
export class TurnObserver {
  private message = "";
  private readonly tools: ToolRecord[] = [];
  private byId = new Map<string, ToolRecord>();

  observe(params: unknown): void {
    try {
      const p = params as { update?: Record<string, unknown> } | undefined;
      const u = p?.update;
      if (!u || typeof u !== "object") return;
      const kind = String(u["sessionUpdate"] ?? "");

      if (kind === "agent_message_chunk") {
        this.message += textOf(u["content"]);
        return;
      }
      // Thought chunks are intentionally dropped — see file header.
      if (kind === "agent_thought_chunk") return;

      if (kind === "tool_call") {
        const id = String(u["toolCallId"] ?? `t${this.tools.length}`);
        const rec: ToolRecord = {
          name: String(u["title"] ?? u["kind"] ?? "tool"),
          status: String(u["status"] ?? "pending"),
        };
        this.byId.set(id, rec);
        this.tools.push(rec);
        return;
      }

      if (kind === "tool_call_update") {
        const id = String(u["toolCallId"] ?? "");
        const rec = this.byId.get(id);
        if (!rec) return;
        if (u["status"] !== undefined) rec.status = String(u["status"]);
        const out = textOf(u["content"]);
        if (out) rec.output = truncate(out, MAX_TOOL_OUTPUT_CHARS);
        return;
      }
    } catch {
      // A malformed update must never break the turn.
    }
  }

  summary(): TurnSummary {
    return {
      message: truncate(this.message, MAX_MESSAGE_CHARS),
      tools: this.tools.slice(-MAX_TOOLS_RENDERED),
      toolCallCount: this.tools.length,
    };
  }
}

/**
 * Render a turn into the observation shown at the top of the next step —
 * the analogue of DeLM's `obs` dict, which carries the previous command's
 * output plus a state line.
 */
export function renderObservation(s: TurnSummary, stopReason: string): string {
  const parts: string[] = ["==== LAST STEP ===="];
  if (s.message) parts.push(`You said:\n${s.message}`);
  if (s.tools.length > 0) {
    const hidden = s.toolCallCount - s.tools.length;
    parts.push(
      `Tools you ran${hidden > 0 ? ` (last ${s.tools.length} of ${s.toolCallCount})` : ""}:`,
    );
    for (const t of s.tools) {
      parts.push(`  - ${t.name} [${t.status}]${t.output ? `\n      ${t.output.replace(/\n/g, "\n      ")}` : ""}`);
    }
  }
  if (s.tools.length === 0 && !s.message) {
    parts.push("(your last step produced no tool calls and no output)");
  }
  parts.push(`stop_reason=${stopReason}`);
  parts.push("==== END LAST STEP ====");
  return parts.join("\n");
}
