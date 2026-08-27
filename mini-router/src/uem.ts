/**
 * UEM (Unified Event Message) — environment → agent push protocol.
 *
 * Wire-level contract documented in v2docs/UEM.md (canonical source).
 * Single-agent variant for R7 sidecar mini-router.
 */
export interface UEM {
  /** Globally unique dedup key. */
  event_id: string;
  /** Source environment identifier. */
  source: string;
  /** Logical destination agent name. (Always == this sidecar's AGENT_NAME.) */
  target_agent: string;
  /** Event subtype within the source. */
  kind: string;
  /** Self-contained one-line locator. */
  summary: string;
  /** Wall-clock observation time at the source (epoch ms). */
  observed_at: number;
  /** Source-specific structured payload (opaque to UEM protocol). */
  raw: unknown;
  /** Index signature for compat with EventStore.UEMLike. */
  [k: string]: unknown;
}
