/** Fetch shared context for turn starts and detect whether the worker published. */
export interface BoardClientOpts {
  baseUrl?: string;
  agent: string;
  boardIds: string[];
  log?: (level: "info" | "warn" | "error", msg: string, err?: unknown) => void;
}

export class BoardClient {
  private readonly baseUrl?: string;
  private readonly agent: string;
  private readonly boardIds: string[];
  private readonly log: (level: "info" | "warn" | "error", msg: string, err?: unknown) => void;

  constructor(opts: BoardClientOpts) {
    this.baseUrl = opts.baseUrl?.replace(/\/+$/, "") || undefined;
    this.agent = opts.agent;
    this.boardIds = opts.boardIds.filter(Boolean);
    this.log = opts.log ?? (() => {});
  }

  get enabled(): boolean {
    return Boolean(this.baseUrl) && this.boardIds.length > 0;
  }

  async renderForPrompt(): Promise<string> {
    if (!this.enabled) return "";
    const { boards: perBoard, unreachable } = await this.readBoards();
    const blocks: string[] = [];
    let anyContent = false;
    let anyDown = false;
    for (const boardId of this.boardIds) {
      const down = unreachable.has(boardId);
      const rendered = (perBoard.get(boardId) ?? "").trim();
      const empty = !rendered || rendered === "(no shared lessons yet)";
      if (down) anyDown = true;
      else if (!empty) anyContent = true;
      const header =
        this.boardIds.length > 1 ? `==== SHARED CONTEXT: ${boardId} ====` : "==== SHARED CONTEXT ====";
      const body = down
        ? "(the shared board could not be reached this turn — its contents are UNKNOWN, not empty)"
        : empty
          ? "(nothing published yet — you are the first to write here)"
          : rendered;
      blocks.push(`${header}\n${body}`);
    }
    const guidance = anyDown
      ? "\n\nThe shared board could not be reached this turn, so the view above is " +
        "INCOMPLETE — treat it as unknown, not empty. Do NOT assume you are first: " +
        "peers may already have recorded facts, dead ends and fixes you cannot see " +
        "here. Publish what you find as usual; it will land once the board recovers."
      : anyContent
        ? "\n\nThe entries above are verified notes published by your peers. " +
          "Read them BEFORE acting: do not re-derive a FACT someone already " +
          "established, do not repeat a path recorded as FAIL, and check " +
          "PATCH_SUMMARY entries before proposing your own fix."
        : "\n\nNothing has been published yet. Whatever you discover this turn is " +
          "what your peers will see, so publish concrete findings rather than plans.";
    return blocks.join("\n\n") + guidance + "\n==== END SHARED CONTEXT ====\n";
  }

  private async readBoards(): Promise<{ boards: Map<string, string>; unreachable: Set<string> }> {
    // Snapshot returns unread gists across boards; full reads are a fallback.
    const out = new Map<string, string>();
    const missing = () => new Set(this.boardIds.filter((b) => !out.has(b)));
    const qs =
      `?viewer=${encodeURIComponent(this.agent)}` +
      `&boards=${encodeURIComponent(this.boardIds.join(","))}`;
    try {
      const res = await fetch(`${this.baseUrl}/snapshot${qs}`, { method: "GET" });
      if (res.ok) {
        const body = (await res.json()) as {
          boards?: Record<string, { rendered?: string }>;
        };
        for (const [bid, v] of Object.entries(body.boards ?? {})) {
          out.set(bid, v?.rendered ?? "");
        }
        if (out.size > 0) return { boards: out, unreachable: missing() };
      } else {
        this.log("warn", `board snapshot -> ${res.status}; falling back to per-board reads`);
      }
    } catch (err) {
      this.log("warn", `board snapshot failed; falling back to per-board reads`, err);
    }

    for (const boardId of this.boardIds) {
      try {
        const url =
          `${this.baseUrl}/board/${encodeURIComponent(boardId)}/read` +
          `?viewer=${encodeURIComponent(this.agent)}`;
        const res = await fetch(url, { method: "GET" });
        if (res.ok) {
          const body = (await res.json()) as { rendered?: string };
          out.set(boardId, body.rendered ?? "");
        } else {
          this.log("warn", `board read ${boardId} -> ${res.status}`);
        }
      } catch (err) {
        this.log("warn", `board read ${boardId} failed`, err);
      }
    }
    return { boards: out, unreachable: missing() };
  }

  async latestOwnGistId(): Promise<number | null> {
    // Distinguish a successful empty read (0) from unavailable board data (null).
    if (!this.enabled) return null;
    let latest = 0;
    let sawAny = false;
    for (const boardId of this.boardIds) {
      try {
        const url =
          `${this.baseUrl}/board/${encodeURIComponent(boardId)}/read_all` +
          `?viewer=${encodeURIComponent(this.agent)}`;
        const res = await fetch(url, { method: "GET" });
        if (!res.ok) continue;
        const body = (await res.json()) as { entries?: Array<{ thread_id?: string; _label?: string }> };
        for (const e of body.entries ?? []) {
          if (e.thread_id !== this.agent) continue;
          const m = /^G(\d+)$/.exec(e._label ?? "");
          if (m) latest = Math.max(latest, Number(m[1]));
        }
        sawAny = true;
      } catch (err) {
        this.log("warn", `board read_all ${boardId} failed`, err);
      }
    }
    return sawAny ? latest : null;
  }

  buildForcedWriteNudge(): string {
    const primary = this.boardIds[0] ?? "";
    return (
      "==== SHARED CONTEXT: ANYTHING TO PUBLISH? ====\n" +
      "This turn produced no board entry. If you established something your " +
      "peers can build on, publish it now; if you are still mid-task, refresh " +
      "your `CLAIM` so peers and your lead can see the work is live.\n\n" +
      `\`board_write\` on board \`${primary}\`:\n` +
      "  FACT <objective discovery, <=100 chars>\n" +
      "  OBSERVED <what you ran and what it printed, <=100 chars>\n" +
      "  FAIL <hypothesis you falsified, so peers skip it, <=100 chars>\n" +
      "  CLAIM <what you are working on right now, <=100 chars>\n" +
      "  PATCH_SUMMARY files=<paths> | idea=<one line> | evidence=<what verified it>\n\n" +
      "Do NOT publish a placeholder. Publish only evidence — let peers draw " +
      "their own conclusions.\n" +
      "==== END ====\n"
    );
  }

}

export function parseBoardIds(raw: string | undefined): string[] {
  return (raw ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}
