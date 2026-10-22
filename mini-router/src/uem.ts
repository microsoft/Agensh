/** Unified event message shared by listeners, persistence and prompt rendering. */
export interface UEM {
  event_id: string;
  source: string;
  target_agent: string;
  kind: string;
  summary: string;
  observed_at: number;
  raw: unknown;
  [k: string]: unknown;
}
