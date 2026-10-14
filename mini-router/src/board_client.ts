/**
 * board_client — mini-router → board-service HTTP client.
 *
 * Implements the two structural properties DeLM relies on (paper §3.1-3.2,
 * upstream src/agents/swebench_implementer_agent.py:322 + src/prompts/
 * swebench_local.py:92):
 *
 *   1. FORCED READ — the shared context is not a tool the agent may choose to
 *      call. It is re-rendered and spliced into the prompt on every dispatch,
 *      so accumulated peer progress is always in the agent's context window.
 *      Upstream does this by assigning `self.shared_lessons_block` at the top
 *      of every step; we do it by prepending to the UEM prompt text.
 *
 *   2. FORCED WRITE — upstream makes the NOTE section a required part of the
 *      response format and replays any turn that omits it. We cannot reject a
 *      copilot-CLI turn mid-flight, so we approximate: count the board's gists
 *      for this agent before and after the turn; if the agent wrote nothing,
 *      offer a follow-up prompt inviting one, exactly once per turn.
 *
 *      The follow-up asks for a `CLAIM` refresh rather than accepting
 *      silence: a turn with no discovery is still a turn with state. Two
 *      failure modes bound it. Offering a `FACT (none)` escape turns a large
 *      share of writes into that placeholder, mostly from idle reviewers with
 *      no PRs to review. Accepting silence lets a busy worker publish nothing
 *      for long stretches, and peers whose only liveness signal is a branch, a
 *      PR or a board write read it as missing and reassign its work, spawning
 *      competing implementations. So the placeholder stays refused: a claim
 *      says what you are doing, which is information; `(none)` says nothing.
 *
 * Failure policy: every method degrades to a no-op on any error. A board
 * outage must never block agent dispatch — the run continues with the board
 * simply absent from the prompt.
 */

export interface BoardClientOpts {
  /** e.g. http://board-service:8660 — unset disables all board behavior. */
  baseUrl?: string;
  /** This sidecar's agent identity; used as thread_id / viewer. */
  agent: string;
  /** CSV of board ids this agent may access. First entry is the primary. */
  boardIds: string[];
  /** Queue id rendered alongside the board (BOARD_QUEUE_ID). Optional. */
  queueId?: string;
  /**
   * Token budget for the rendered block spliced into each prompt.
   * 0 (the default) means UNLIMITED — ship the whole board.
   */
  windowTokens?: number;
  /**
   * Upstream's shared_lessons_render_mode (config.py:79). Selects WHAT the
   * agent sees, not just how much: `full` is the raw board, the `*_digest`
   * family strips low-signal narration and keeps only peer content, and the
   * `*_local_only` family blinds planners entirely. Defaults to the
   * board-service's own default when unset.
   */
  renderMode?: string;
  /**
   * "planner" or "implementer". The mode matrix is role-dependent — the same
   * mode string shows a lead and a worker different things — so the router has
   * to tell the service which side of it this agent is on.
   */
  role?: string;
  /** Injected for tests. */
  fetchImpl?: typeof fetch;
  log?: (level: "info" | "warn" | "error", msg: string, err?: unknown) => void;
}

export class BoardClient {
  private readonly baseUrl?: string;
  private readonly agent: string;
  private readonly boardIds: string[];
  private readonly queueId: string;
  private readonly windowTokens: number;
  private readonly renderMode?: string;
  private readonly role: string;
  private readonly fetchImpl: typeof fetch;
  private readonly log: (level: "info" | "warn" | "error", msg: string, err?: unknown) => void;
  /** Step index reported to the service; patch_clean_delayed_local gates on it. */
  private step = 0;

  constructor(opts: BoardClientOpts) {
    this.baseUrl = opts.baseUrl?.replace(/\/+$/, "") || undefined;
    this.agent = opts.agent;
    this.boardIds = opts.boardIds.filter(Boolean);
    this.queueId = opts.queueId ?? "";
    // 0 = unlimited: ship the WHOLE board on every dispatch. A windowed render
    // makes an absent CLAIM ambiguous between "nobody claimed this work" and
    // "it was dropped by the budget", so agents overlap on work a peer already
    // claimed. A whole 6-hour board is ~126 entries / ~4k tokens.
    // Override with BOARD_WINDOW_TOKENS if a board ever gets large enough to
    // matter.
    this.windowTokens = opts.windowTokens ?? 0;
    this.renderMode = opts.renderMode || undefined;
    this.role = opts.role || "implementer";
    this.fetchImpl = opts.fetchImpl ?? fetch;
    this.log = opts.log ?? (() => {});
  }

  /** Advance the step counter used by the delayed render modes. */
  setStep(step: number): void {
    this.step = Math.max(0, step);
  }

  /** True when a board is configured; callers skip all board work otherwise. */
  get enabled(): boolean {
    return Boolean(this.baseUrl) && this.boardIds.length > 0;
  }

  /**
   * FORCED READ. Render every board this agent belongs to, concatenated.
   *
   * Attached UNCONDITIONALLY to each dispatched UEM batch, including when the
   * board is still empty. An empty board is itself information — it tells the
   * agent it is first and that peers will read whatever it publishes — and
   * emitting the header every time keeps the protocol visible in context
   * rather than appearing only once peers happen to have written something.
   *
   * Returns "" only when the board is disabled, so non-board profiles
   * dispatch exactly as before.
   */
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
    // An unreachable board must never be reported as an empty one. Saying
    // "you are the first to write here" on a failed fetch is not a degraded
    // message, it is a false one: agents resuming to that sentence while the
    // peers' gists sit in the database restart the team's work from nothing.
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

  /**
   * Read every board in ONE request via /snapshot, which copies them all under
   * a single critical section.
   *
   * With N separate reads, a peer writing between read 1 and read 2 gives the
   * agent a view that never existed at any instant — a lead could see a team
   * board claiming a task is done above a top board that has not heard of it.
   * Falls back to per-board reads if /snapshot is unavailable, so a router
   * built against a newer board-service still works against an older one.
   */
  private async readBoards(): Promise<{ boards: Map<string, string>; unreachable: Set<string> }> {
    const out = new Map<string, string>();
    const missing = () => new Set(this.boardIds.filter((b) => !out.has(b)));
    const qs =
      `?viewer=${encodeURIComponent(this.agent)}` +
      `&boards=${encodeURIComponent(this.boardIds.join(","))}` +
      `&window_tokens=${this.windowTokens}` +
      `&role=${encodeURIComponent(this.role)}` +
      `&step=${this.step}` +
      (this.renderMode ? `&render_mode=${encodeURIComponent(this.renderMode)}` : "");
    try {
      const res = await this.fetchImpl(`${this.baseUrl}/snapshot${qs}`, { method: "GET" });
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
          `?viewer=${encodeURIComponent(this.agent)}` +
          `&window_tokens=${this.windowTokens}` +
          `&role=${encodeURIComponent(this.role)}` +
          `&step=${this.step}` +
          (this.renderMode ? `&render_mode=${encodeURIComponent(this.renderMode)}` : "");
        const res = await this.fetchImpl(url, { method: "GET" });
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
    // Whatever we never managed to read is UNREACHABLE, not empty. The caller
    // must not present it to the agent as "nobody has written here yet".
    return { boards: out, unreachable: missing() };
  }

  /**
   * Render the current task queue for a board's queue id. Included alongside
   * the board so a woken agent can see that work is waiting without having to
   * poll `queue_claim` first — in the round-2 run the planner enqueued four
   * subtasks and no worker ever claimed one, because nothing told them the
   * queue was non-empty.
   */
  async renderQueueForPrompt(queueId: string): Promise<string> {
    if (!this.enabled || !queueId) return "";
    try {
      const url = `${this.baseUrl}/queue/${encodeURIComponent(queueId)}/status`;
      const res = await this.fetchImpl(url, { method: "GET" });
      if (!res.ok) return "";
      const body = (await res.json()) as {
        counts?: Record<string, number>;
        tasks?: Array<{ task_id?: string; state?: string; description?: string; claimed_by?: string }>;
      };
      const tasks = body.tasks ?? [];
      if (tasks.length === 0) return "";
      const counts = body.counts ?? {};
      const lines = tasks
        .filter((t) => t.state === "pending" || t.state === "claimed")
        .slice(0, 12)
        .map((t) => {
          const who = t.state === "claimed" ? ` (claimed by ${t.claimed_by})` : "";
          return `  [${t.state}] ${t.task_id}${who}: ${String(t.description ?? "").slice(0, 120)}`;
        });
      if (lines.length === 0) return "";
      const pending = counts["pending"] ?? 0;
      return (
        `==== TASK QUEUE (${queueId}) ====\n` +
        `pending=${counts["pending"] ?? 0} claimed=${counts["claimed"] ?? 0} completed=${counts["completed"] ?? 0}\n` +
        lines.join("\n") +
        (pending > 0
          ? `\n\n${pending} task(s) are unclaimed. Call \`queue_claim\` to take one before starting your own work.`
          : "") +
        "\n==== END TASK QUEUE ====\n"
      );
    } catch (err) {
      this.log("warn", `queue status ${queueId} failed`, err);
      return "";
    }
  }

  /**
   * Highest board_gists id this agent has authored across its boards. Used to
   * detect whether a turn produced a write (the forced-write check). Returns
   * null on error so the caller can distinguish "no writes" from "couldn't
   * tell".
   *
   * An id, not a count: read_all serves the trimmed window, so once the board
   * is full a new gist can push out one of the agent's own older ones, and a
   * refined PATCH_SUMMARY replaces its predecessor in place. Either way the
   * count stays flat although the agent wrote; its newest id still rises.
   */
  async latestOwnGistId(): Promise<number | null> {
    if (!this.enabled) return null;
    let latest = 0;
    let sawAny = false;
    for (const boardId of this.boardIds) {
      try {
        const url =
          `${this.baseUrl}/board/${encodeURIComponent(boardId)}/read_all` +
          `?viewer=${encodeURIComponent(this.agent)}`;
        const res = await this.fetchImpl(url, { method: "GET" });
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

  /**
   * The nudge sent when a turn produced no board write. Mirrors upstream's
   * replay message (swebench_implementer_agent.py:138) but phrased for a
   * tool-calling agent rather than a strict three-section text format.
   */
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

  /**
   * The complete block attached to every dispatched UEM batch: shared context
   * plus (when configured) the task queue. This is variant 1 — the board
   * travels with the batch rather than being something the agent fetches.
   */
  async renderBatchPrefix(): Promise<string> {
    if (!this.enabled) return "";
    const [board, queue] = await Promise.all([
      this.renderForPrompt(),
      this.renderQueueForPrompt(this.queueId),
    ]);
    return [board, queue].filter(Boolean).join("\n");
  }

  /**
   * Whether this agent has a live PATCH_SUMMARY on any of its boards.
   *
   * Gates the PATCH_READY vs SOURCE_DIFF choice: source changes plus a
   * published candidate means "close it out", source changes with nothing
   * published means "verify and publish". Read from storage rather than from
   * the rendered view, because several render modes demote or hide the
   * viewer's own notes and would report false.
   */
  async hasOwnPatchSummary(): Promise<boolean> {
    if (!this.enabled) return false;
    for (const boardId of this.boardIds) {
      try {
        const res = await this.fetchImpl(
          `${this.baseUrl}/board/${encodeURIComponent(boardId)}/read_all` +
            `?viewer=${encodeURIComponent(this.agent)}`,
          { method: "GET" },
        );
        if (!res.ok) continue;
        const body = (await res.json()) as {
          entries?: Array<{ thread_id?: string; type?: string }>;
        };
        if (
          (body.entries ?? []).some(
            (e) => e.thread_id === this.agent && e.type === "PATCH_SUMMARY",
          )
        ) {
          return true;
        }
      } catch (err) {
        this.log("warn", `hasOwnPatchSummary ${boardId} failed`, err);
      }
    }
    return false;
  }

  /**
   * The task this agent currently holds on `queueId`, if any. Used by the step
   * loop to source its task text from the live assignment rather than a static
   * role string — upstream's task_instruction is written by the planner at
   * delegate time, not baked into a template.
   */
  async claimedTaskFor(
    queueId: string,
    agent: string,
  ): Promise<{ task_id: string; description: string } | null> {
    if (!this.enabled || !queueId) return null;
    try {
      const res = await this.fetchImpl(
        `${this.baseUrl}/queue/${encodeURIComponent(queueId)}/status`,
        { method: "GET" },
      );
      if (!res.ok) return null;
      const body = (await res.json()) as {
        tasks?: Array<{ task_id?: string; state?: string; description?: string; claimed_by?: string }>;
      };
      const t = (body.tasks ?? []).find(
        (x) => x.state === "claimed" && x.claimed_by === agent,
      );
      return t ? { task_id: String(t.task_id ?? ""), description: String(t.description ?? "") } : null;
    } catch (err) {
      this.log("warn", `claimedTaskFor ${queueId} failed`, err);
      return null;
    }
  }
}

/** Parse the BOARD_IDS env (CSV) into a list. */
export function parseBoardIds(raw: string | undefined): string[] {
  return (raw ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}
