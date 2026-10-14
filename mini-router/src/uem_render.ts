/**
 * uem_render.ts — how a UEM is spoken to an agent.
 *
 * Split out of acp_socket_channel.ts so it can be tested without pulling in
 * @agentclientprotocol/sdk: these are pure functions over a UEM, and the only
 * reason they were unreachable from a unit test was a transitive SDK import.
 *
 * THE RUN CLOCK
 * Every time signal an agent receives is harness-generated and expressed as
 * relative run time in minutes. The board renders "+{rel}m" and the runner's
 * T-45m / T-5m notices fire 45 and 5 minutes before the deadline.
 *
 * An absolute timestamp such as
 *     observed_at=2026-08-30T17:40:44.000Z
 * spliced into every prompt would be an absolute wall clock and a fourth
 * agent-visible time signal, disagreeing in form with the board's "+180.0m"
 * in the same context.
 *
 * Events therefore render as minutes since run start.
 */
import type { UEM } from "./uem.ts";

/** Fallback anchor: when no run start is published, this process starting is
 *  the closest thing to "when the run began" that a sidecar can know. */
const PROCESS_START_MS = Date.now();

/** Read at call time, not module load: the entrypoint may export these after
 *  this module is first imported, and tests set them per-case. */
function anchorMs(): number {
  const raw = Number(process.env.PBENCH_RUN_START_MS || "");
  return Number.isFinite(raw) && raw > 0 ? raw : PROCESS_START_MS;
}

/**
 * Epoch ms -> "+N.Nm" minutes since run start.
 *
 * Clamped at zero: an event can predate the anchor (a sidecar restart, or an
 * event queued before the router came up), and "-3.0m" in a prompt is both
 * meaningless to the agent and a tell that the clock is real.
 */
export function runAge(observedAtMs: number): string {
  const real = Math.max(0, observedAtMs - anchorMs());
  return `+${(real / 60_000).toFixed(1)}m`;
}

export function defaultRenderUEM(uem: UEM): string {
  return [
    `[event]`,
    `event_id=${uem.event_id}`,
    `source=${uem.source}`,
    `kind=${uem.kind}`,
    `observed_at=${runAge(uem.observed_at)}`,
    `summary: ${uem.summary}`,
  ].join("\n");
}

export function defaultRenderBatch(uems: UEM[]): string {
  if (uems.length === 1) return defaultRenderUEM(uems[0]!);
  const blocks = uems.map((u, i) =>
    [
      `--- event ${i + 1}/${uems.length} ---`,
      `event_id=${u.event_id}`,
      `source=${u.source}`,
      `kind=${u.kind}`,
      `observed_at=${runAge(u.observed_at)}`,
      `summary: ${u.summary}`,
    ].join("\n"),
  );
  return [`[event-batch] ${uems.length} events`, ``, blocks.join("\n\n")].join("\n");
}
