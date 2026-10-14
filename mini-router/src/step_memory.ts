/**
 * step_memory — per-agent working memory for the step-loop mode (variant 2).
 *
 * Port of DeLM's base/agent/memory.py Memory class. When the router drives the
 * agent step-by-step against a fresh session each time, nothing else remembers
 * what happened: the ACP session is discarded, so the prompt must carry the
 * history itself. That is exactly what upstream does — `{memory}` is a field of
 * the implementer prompt template.
 *
 * Compression policy is upstream's: once `maxMemory` records accumulate, fold
 * everything older than the last `keepRecent` into a rolling summary and drop
 * the raw rows.
 *
 * One deliberate divergence: upstream summarizes with an LLM
 * (`_summarize_records` calls `self.summarizer_llm`). We summarize
 * deterministically. The router has no LLM client, adding one would put a
 * second model call on every step, and for this content — a list of tool names
 * and statuses — a structural summary loses little. If fidelity turns out to
 * matter, this is the seam to swap.
 */

export interface StepRecord {
  /** 1-based step index this record came from. */
  step: number;
  /** Compact description of what the agent did (tool names + statuses). */
  action: string;
  /** Compact observation the step produced. */
  observation: string;
}

export interface StepMemoryOptions {
  /** Compress once this many records have accumulated. Upstream default 8. */
  maxMemory?: number;
  /** Raw records kept verbatim after compression. Upstream default 3. */
  keepRecent?: number;
  /** Per-field clamp applied when rendering. */
  maxFieldChars?: number;
}

/** Upstream truncate_middle: keep head and tail, elide the middle. */
export function truncateMiddle(text: string, maxChars: number): string {
  const s = String(text ?? "");
  if (maxChars <= 0 || s.length <= maxChars) return s;
  const head = Math.floor((maxChars * 3) / 5);
  const tail = maxChars - head;
  const elided = s.length - head - tail;
  return `${s.slice(0, head)}\n... <${elided} chars elided> ...\n${s.slice(-tail)}`;
}

export class StepMemory {
  private records: StepRecord[] = [];
  private summary = "";
  private readonly maxMemory: number;
  private readonly keepRecent: number;
  private readonly maxFieldChars: number;

  constructor(opts: StepMemoryOptions = {}) {
    this.maxMemory = opts.maxMemory ?? 8;
    this.keepRecent = opts.keepRecent ?? 3;
    this.maxFieldChars = opts.maxFieldChars ?? 1200;
  }

  add(rec: StepRecord): void {
    this.records.push(rec);
    this.compress();
  }

  /** Rendered form spliced into the step prompt as `{memory}`. */
  asText(): string {
    if (!this.summary && this.records.length === 0) return "None";
    const parts: string[] = [];
    if (this.summary) {
      parts.push("[Summary of earlier steps]", this.summary, "");
    }
    if (this.records.length > 0) {
      parts.push("[Recent steps (oldest first)]");
      for (const r of this.records) {
        parts.push(
          `${r.step}. did: ${truncateMiddle(r.action, this.maxFieldChars)}` +
            `\n   saw: ${truncateMiddle(r.observation, this.maxFieldChars)}`,
        );
      }
    }
    return parts.join("\n");
  }

  get size(): number {
    return this.records.length;
  }

  private compress(): void {
    if (this.records.length < this.maxMemory) return;
    const head = this.keepRecent > 0 ? this.records.slice(0, -this.keepRecent) : this.records.slice();
    const tail = this.keepRecent > 0 ? this.records.slice(-this.keepRecent) : [];
    if (head.length > 0) {
      const folded = this.summarize(head);
      this.summary = this.summary ? `${this.summary}\n\n${folded}` : folded;
    }
    this.records = tail;
  }

  /**
   * Deterministic fold: report the step range and the actions taken, so the
   * agent retains a sense of what ground it has already covered without
   * carrying every observation.
   */
  private summarize(recs: StepRecord[]): string {
    if (recs.length === 0) return "";
    const first = recs[0]!.step;
    const last = recs[recs.length - 1]!.step;
    const lines = recs.map((r) => `  step ${r.step}: ${truncateMiddle(r.action, 200)}`);
    return `Steps ${first}-${last} (${recs.length} steps, details elided):\n${lines.join("\n")}`;
  }
}
