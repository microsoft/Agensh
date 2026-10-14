/**
 * UEM (Unified Event Message) — environment → agent push protocol.
 *
 * This file is the wire-level contract.
 * Single-agent variant for the mini-router sidecar.
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
