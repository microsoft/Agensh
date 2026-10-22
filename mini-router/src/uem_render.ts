/** Render queued event summaries with times relative to the shared run start. */
import type { UEM } from "./uem.ts";

const PROCESS_START_MS = Date.now();

function anchorMs(): number {
  // Without a shared harness timestamp, measure from this router's process startup.
  const raw = Number(process.env.PBENCH_RUN_START_MS || "");
  return Number.isFinite(raw) && raw > 0 ? raw : PROCESS_START_MS;
}

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
