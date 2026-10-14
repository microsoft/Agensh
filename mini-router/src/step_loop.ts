/**
 * step_loop — variant 2: the router owns the agent loop, DeLM-style.
 *
 * Upstream (src/runners/implementer_runner.py:180) is a plain
 * `for t in range(max_steps)` that calls `agent.step()`; each step rebuilds the
 * whole prompt (swebench_implementer_agent.py:401) and issues one stateless LLM
 * call. That is why "the board is always in context" holds trivially there:
 * there is no conversation to drift from, so every step is re-grounded.
 *
 * Our default mode cannot do that — copilot-CLI owns its session and runs many
 * internal turns off a single prompt, so the router only gets to inject at
 * wake-up. This module takes the loop back:
 *
 *   for each step:
 *     prompt = header + task + BOARD + QUEUE + memory + last observation
 *     result = channel.promptStep(prompt)     // fresh ACP session
 *     memory.add(what it did, what it saw)
 *
 * Costs, accepted deliberately: prompt-cache reuse is gone (session reuse
 * hits the cache ~97% of the time), and each step pays to re-send the accumulated
 * memory. The trade is exact control over what is in context every step.
 *
 * Termination: the agent signals completion by publishing a PATCH_SUMMARY and
 * saying DONE, or the step budget / wall clock runs out.
 */
import type { BoardClient } from "./board_client.ts";
import { StepMemory } from "./step_memory.ts";
import { renderObservation, type TurnSummary } from "./turn_observer.ts";
import {
  NoProgressDetector,
  actionSignature,
  peerPatchCheckpoint,
  renderStrategySection,
} from "./step_policies.ts";
import {
  WorkspaceProbe,
  patchReadyNudge,
  sourceDiffNudge,
} from "./workspace_probe.ts";

export interface StepChannel {
  promptStep(text: string): Promise<{ stopReason: string; summary: TurnSummary }>;
}

export interface StepLoopOptions {
  agent: string;
  channel: StepChannel;
  board?: BoardClient;
  /**
   * The standing task text, resent every step. Upstream's analogue is
   * `task_instruction`, which is NOT a static per-role string: it is the
   * argument the planner passes to `delegate_task`, i.e. the assignment
   * written in natural language at dispatch time
   * (src/tools/delegate.py:198). We approximate that by preferring the
   * description of whatever queue task this agent currently holds, falling
   * back to this text when it holds none.
   */
  task: string;
  /** Queue polled for a live assignment to use as the task text. */
  queueId?: string;
  /** Upstream default is 50. */
  maxSteps?: number;
  /** Stop starting new steps once this deadline passes (epoch ms). */
  deadlineMs?: number;
  now?: () => number;
  log?: (level: "info" | "warn" | "error", msg: string, err?: unknown) => void;
  memory?: StepMemory;
  /**
   * Stop after this many consecutive identical action signatures. Upstream's
   * NO_PROGRESS_LIMIT is 8; 0 disables the check.
   */
  noProgressLimit?: number;
  /** Prepend a per-agent strategy prior so siblings start from different angles. */
  strategyPrior?: boolean;
  /**
   * Path to the agent's workspace, when the router can see it. Enables the
   * PATCH_READY / SOURCE_DIFF checkpoints; both stay silent when unset or
   * unreadable rather than guessing from tool calls.
   */
  workspacePath?: string;
}

const DONE_RE = /\bDONE\b/;

export class StepLoop {
  private readonly memory: StepMemory;
  private readonly log: (level: "info" | "warn" | "error", msg: string, err?: unknown) => void;
  private readonly noProgress: NoProgressDetector | null;
  private readonly workspace: WorkspaceProbe;
  /** Rendered board text from this step, reused to build the peer checkpoint. */
  private lastBoardText = "";
  /** Whether this agent has a live PATCH_SUMMARY (gates PATCH_READY). */
  private publishedPatch = false;

  constructor(private readonly opts: StepLoopOptions) {
    this.memory = opts.memory ?? new StepMemory();
    this.log = opts.log ?? (() => {});
    const limit = opts.noProgressLimit ?? 8;
    this.noProgress = limit > 0 ? new NoProgressDetector(limit) : null;
    this.workspace = new WorkspaceProbe(opts.workspacePath);
  }

  /** Run until DONE, step budget, or deadline. Returns steps executed. */
  async run(signal?: AbortSignal): Promise<{ steps: number; reason: string }> {
    const maxSteps = this.opts.maxSteps ?? 50;
    const now = this.opts.now ?? Date.now;
    let lastObservation = "(this is your first step — nothing has happened yet)";

    for (let step = 1; step <= maxSteps; step++) {
      if (signal?.aborted) return { steps: step - 1, reason: "aborted" };
      if (this.opts.deadlineMs && now() >= this.opts.deadlineMs) {
        return { steps: step - 1, reason: "deadline" };
      }

      const assignment = await this.currentAssignment();
      // Tell the board which step we are on: the patch_clean_delayed_local
      // mode withholds peer content until step 8, so a step counter that never
      // advances would keep the agent blinded for the whole run.
      this.opts.board?.setStep(step);
      const prompt = await this.buildPrompt(step, maxSteps, lastObservation, assignment);
      let result: { stopReason: string; summary: TurnSummary };
      try {
        result = await this.opts.channel.promptStep(prompt);
      } catch (err) {
        // A failed step is recoverable: record it and let the next step see it,
        // rather than aborting the whole agent.
        this.log("warn", `step ${step} failed`, err);
        this.memory.add({ step, action: "(step failed)", observation: String(err) });
        lastObservation = `==== LAST STEP ====\nyour previous step errored: ${String(err)}\n==== END LAST STEP ====`;
        continue;
      }

      const s = result.summary;
      const action =
        s.tools.length > 0
          ? s.tools.map((t) => `${t.name}[${t.status}]`).join(", ")
          : s.message
            ? "(message only)"
            : "(no action)";
      lastObservation = renderObservation(s, result.stopReason);

      // A peer with a credible candidate fix is worth interrupting for, and the
      // observation is where the agent is actually looking. Upstream injects
      // here rather than into the static prompt for exactly that reason.
      const checkpoint = peerPatchCheckpoint(this.lastBoardText, this.opts.agent);
      if (checkpoint) lastObservation = `${lastObservation}\n\n${checkpoint}`;

      // What actually changed on disk this step. Distinguishes an agent that
      // produced a candidate fix from one that only narrated editing —
      // something the conversation alone cannot tell you.
      if (this.workspace.configured) {
        try {
          const ws = await this.workspace.probe();
          if (ws.available && ws.changed.length > 0) {
            const failed = /\b(FAIL|error|Traceback|Segmentation fault)\b/i.test(
              lastObservation,
            );
            if (!this.publishedPatch && this.opts.board?.enabled) {
              this.publishedPatch = await this.opts.board.hasOwnPatchSummary();
            }
            // A live PATCH_SUMMARY from this agent means it has a candidate to
            // hand off; otherwise the change is still unpublished.
            const nudge = this.publishedPatch
              ? patchReadyNudge(ws.changed, failed)
              : sourceDiffNudge(ws.changed, step);
            if (nudge) lastObservation = `${lastObservation}\n\n${nudge}`;
          }
        } catch (err) {
          this.log("warn", "workspace probe failed", err);
        }
      }

      this.memory.add({ step, action, observation: lastObservation });

      this.log(
        "info",
        `step ${step}/${maxSteps}: ${s.toolCallCount} tool call(s), stop=${result.stopReason}`,
      );

      if (DONE_RE.test(s.message)) {
        return { steps: step, reason: "done" };
      }

      // Stop an agent that has stopped making progress. Without this a stuck
      // agent re-runs one command until its entire budget is gone.
      if (this.noProgress?.observe(actionSignature(s.tools))) {
        this.log(
          "warn",
          `no progress: ${this.noProgress.consecutive} consecutive identical actions; stopping`,
        );
        return { steps: step, reason: "no_progress" };
      }
    }
    return { steps: maxSteps, reason: "max_steps" };
  }

  /**
   * The task text for this step: the claimed queue task's description when the
   * agent holds one, else the standing task. Mirrors upstream, where a worker
   * is told what to do by the planner rather than by a role template.
   */
  private async currentAssignment(): Promise<string | null> {
    const board = this.opts.board;
    const qid = this.opts.queueId;
    if (!board?.enabled || !qid) return null;
    try {
      const t = await board.claimedTaskFor(qid, this.opts.agent);
      return t ? `${t.task_id}: ${t.description}` : null;
    } catch {
      return null;
    }
  }

  /**
   * Rebuild the entire prompt for one step. Mirrors upstream's
   * build_implementer_prompt: task, shared context, memory, current
   * observation — assembled fresh every time.
   */
  private async buildPrompt(
    step: number,
    maxSteps: number,
    observation: string,
    assignment: string | null,
  ): Promise<string> {
    const board = this.opts.board;
    const boardBlock = board?.enabled ? await board.renderBatchPrefix() : "";
    this.lastBoardText = boardBlock;
    const remaining = maxSteps - step;

    return [
      `You are ${this.opts.agent}, working autonomously.`,
      "",
      this.opts.strategyPrior === false ? "" : renderStrategySection(this.opts.agent),
      `==== PROGRESS ====`,
      `Step ${step}/${maxSteps} — ${remaining} step(s) remain.`,
      remaining <= 5
        ? "You are nearly out of steps. Finish and publish what you have rather than starting new work."
        : "",
      "",
      `==== YOUR TASK ====`,
      assignment
        ? `You claimed this from the queue:\n${assignment}`
        : this.opts.task,
      "",
      boardBlock,
      `==== WHAT YOU HAVE DONE SO FAR ====`,
      this.memory.asText(),
      "",
      observation,
      "",
      `==== THIS STEP ====`,
      "Take ONE concrete action toward the task, then stop and let the next step continue.",
      "Publish anything reusable to the shared context with `board_write` before you finish this step.",
      "When the task is fully complete and verified, say DONE in your reply.",
    ]
      .filter((x) => x !== "")
      .join("\n");
  }
}
