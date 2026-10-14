/**
 * step_policies — DeLM agent-loop behaviors that are independent of the
 * environment, ported for the step loop (variant 2).
 *
 * These are the parts of upstream's runner that change what an agent DOES,
 * as opposed to plumbing. Each is pure so it can be unit-tested without a
 * container:
 *
 *   NoProgressDetector      implementer_runner.py:15, 236-254
 *   peerPatchCheckpoint()   swebench_implementer_agent.py:22-69, 379-388
 *   strategyPrior()         prompts/swebench_global.py:20-49
 *   compactMemory()         memory_compactor.py:201-249
 *
 * NOT ported here, and deliberately: the PATCH_READY / SOURCE_DIFF checkpoint
 * nudges (implementer_runner.py:413-476). Both gate on `git diff --name-only`
 * in the agent's worktree, and the mini-router container has no mount of it —
 * the routers run beside the agents, not inside their workspace. Faking the
 * signal from observed tool calls would fire on any edit rather than on
 * durable repo state, which is a different and much noisier trigger. Wiring
 * those needs a read-only workspace mount in the compose overlays first.
 */

/** Upstream: NO_PROGRESS_LIMIT (implementer_runner.py:15). */
export const NO_PROGRESS_LIMIT = 8;

/**
 * Ends a run that has stopped making progress.
 *
 * Upstream compares an "action signature" across consecutive steps and stops
 * after 8 identical ones. The signature deliberately EXCLUDES reasoning and
 * notes: an agent that reworded its explanation while issuing the same command
 * has not made progress, and without this a stuck agent burns its entire
 * budget re-running one command.
 */
export class NoProgressDetector {
  private last: string | null = null;
  private repeats = 0;

  constructor(private readonly limit: number = NO_PROGRESS_LIMIT) {}

  /** Record a step's action signature. Returns true when the run should stop. */
  observe(signature: string): boolean {
    const sig = (signature ?? "").trim();
    if (sig && sig === this.last) {
      this.repeats += 1;
    } else {
      this.last = sig;
      this.repeats = 1;
    }
    return this.repeats >= this.limit;
  }

  get consecutive(): number {
    return this.repeats;
  }
}

/**
 * The action signature for a turn: which tools ran, in order, with status.
 * Assistant prose is excluded for the reason above.
 */
export function actionSignature(
  tools: Array<{ name?: string; status?: string }>,
): string {
  if (!tools || tools.length === 0) return "(no tools)";
  return tools.map((t) => `${t.name ?? "?"}[${t.status ?? "?"}]`).join(",");
}

// ---------------------------------------------------------------------------
// Peer-patch checkpoint
// ---------------------------------------------------------------------------

export interface PeerPatch {
  thread: string;
  content: string;
  final: boolean;
  verified: boolean;
  localFailures: number;
  rank: number;
}

const PATCH_LINE_RE = /^\[t([^/\]]+)\/PATCH_SUMMARY[^\]]*\]\s*(.+)$/;
const STATUS_RE = /\[status=([^\]]*)\]/;
const LOCAL_FAILS_RE = /local_failures=(\d+)/;

/**
 * Parse peer PATCH_SUMMARY lines out of a rendered board block and rank them.
 *
 * Upstream's ranking is final+verified > verified > final > everything else,
 * which is what makes the shared context actionable rather than merely
 * present: an agent about to start broad exploration is pointed at the single
 * most-trustworthy candidate fix a peer already has.
 */
export function parsePeerPatches(boardText: string, self: string): PeerPatch[] {
  const out: PeerPatch[] = [];
  for (const raw of (boardText ?? "").split("\n")) {
    const m = PATCH_LINE_RE.exec(raw.trim());
    if (!m) continue;
    const thread = m[1]!.trim();
    if (thread === self) continue; // peers only
    const body = m[2]!;
    const status = STATUS_RE.exec(body)?.[1] ?? "";
    const final = /\bfinal\b/.test(status);
    const verified = /\bverified\b/.test(status);
    const invalidated = /\binvalidated\b/.test(status);
    if (invalidated) continue; // upstream re-renders these as FAIL, not candidates
    const localFailures = Number(LOCAL_FAILS_RE.exec(status)?.[1] ?? "0");
    const rank = final && verified ? 0 : verified ? 1 : final ? 2 : 3;
    out.push({ thread, content: body, final, verified, localFailures, rank });
  }
  out.sort((a, b) => a.rank - b.rank || a.localFailures - b.localFailures);
  return out;
}

/**
 * The checkpoint injected into the OBSERVATION (not the static prompt) when a
 * peer already has a credible candidate fix.
 *
 * Upstream puts this in the observation on purpose: the static prompt is the
 * same every step and gets skimmed, while the observation is what the agent is
 * actually reacting to. Returns "" when there is nothing worth interrupting
 * for.
 */
export function peerPatchCheckpoint(boardText: string, self: string): string {
  const patches = parsePeerPatches(boardText, self);
  if (patches.length === 0) return "";
  const best = patches[0]!;
  // An unranked, repeatedly-failing candidate is not worth a checkpoint.
  if (best.rank === 3 && best.localFailures > 0) return "";
  const trust =
    best.rank === 0
      ? "finalized AND verified"
      : best.rank === 1
        ? "verified"
        : best.rank === 2
          ? "finalized"
          : "unverified";
  return [
    "PEER_PATCH_CHECKPOINT:",
    `A peer (${best.thread}) has a ${trust} candidate fix:`,
    `  ${best.content}`,
    best.localFailures > 0
      ? `It has ${best.localFailures} recorded local failure(s) — treat with care.`
      : "",
    "Before starting broad exploration of your own, do ONE of:",
    "  (a) verify it yourself and build on it,",
    "  (b) refine it and publish the refinement as your own PATCH_SUMMARY, or",
    "  (c) reject it — and publish a FAIL saying what disproved it, so the next",
    "      peer does not repeat this cycle.",
    "Duplicating work a peer has already verified is the main way parallel",
    "agents waste budget.",
  ]
    .filter(Boolean)
    .join("\n");
}

// ---------------------------------------------------------------------------
// Strategy priors
// ---------------------------------------------------------------------------

/**
 * Upstream hardcodes one prior per thread index (swebench_global.py:20-49).
 * They exist to stop parallel agents from converging on the same first move —
 * with identical prompts and a shared board, agents otherwise pile onto
 * whatever the first one found.
 */
export const STRATEGY_PRIORS: readonly string[] = [
  "Start from a minimal reproduction. Build the smallest input that exercises " +
    "the behavior, confirm it, and work outward from there.",
  "Start from the code. Read the implementation paths involved and reason about " +
    "what they do before running anything.",
  "Start from the specification. Establish what the correct behavior IS — from " +
    "docs, the reference binary's output, or the interface — before changing code.",
  "Start from the tests. Find what exercises this area, run it, and let the " +
    "failures direct you.",
];

/**
 * Assign a prior deterministically from the agent name, so a given agent keeps
 * the same angle across restarts. Upstream indexes by thread id; our agents are
 * named (`pbench-worker3`), so we derive the index from the name.
 */
export function strategyPrior(agent: string): string {
  const name = agent ?? "";
  // Prefer a trailing number when the name has one — it keeps sibling workers
  // spread across distinct priors instead of relying on hash luck.
  const trailing = /(\d+)\s*$/.exec(name);
  let idx: number;
  if (trailing) {
    idx = Number(trailing[1]) % STRATEGY_PRIORS.length;
  } else {
    let h = 0;
    for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
    idx = h % STRATEGY_PRIORS.length;
  }
  return STRATEGY_PRIORS[idx]!;
}

export function renderStrategySection(agent: string): string {
  return `==== STRATEGY ====\n${strategyPrior(agent)}\n`;
}

// ---------------------------------------------------------------------------
// Deterministic memory compaction
// ---------------------------------------------------------------------------

export interface CompactedMemory {
  editedFiles: string[];
  failingTests: string[];
  exceptionClasses: string[];
  commands: string[];
  unresolved: string[];
}

const FILE_RE = /\b[\w./-]+\.(?:c|h|cc|cpp|hpp|py|rs|go|js|ts|sh|mk|am|in)\b/g;
const TEST_RE = /\b(?:test_[\w.]+|[\w.]+_test|tests?\/[\w./-]+)\b/g;
const EXC_RE = /\b([A-Z][A-Za-z0-9]*(?:Error|Exception|Fault|Abort))\b/g;
const FAILED_RE = /\b(FAILED|FAIL|error:|Segmentation fault|assertion failed)\b/i;
const PASSED_RE = /\b(PASSED|PASS|ok|success)\b/i;

/**
 * Fold step history into a fixed-shape structured block instead of prose.
 *
 * Upstream offers this as `memory_compaction_mode="deterministic"`
 * (memory_compactor.py:201-249) so compaction costs no LLM call and, more
 * importantly, cannot hallucinate: a summarizer that invents a file path the
 * agent never touched sends it somewhere real.
 *
 * `unresolved` implements upstream's small resolution state machine: an
 * exception class first seen alongside a failure stays unresolved until it
 * later appears alongside a pass.
 */
export function compactMemory(
  records: Array<{ action: string; observation: string }>,
): CompactedMemory {
  const editedFiles = new Set<string>();
  const failingTests = new Set<string>();
  const exceptionClasses = new Set<string>();
  const commands = new Set<string>();
  const failedExc = new Set<string>();
  const passedExc = new Set<string>();

  for (const r of records ?? []) {
    const action = r.action ?? "";
    const obs = r.observation ?? "";
    const both = `${action}\n${obs}`;

    for (const m of both.matchAll(FILE_RE)) editedFiles.add(m[0]);
    for (const m of both.matchAll(TEST_RE)) failingTests.add(m[0]);

    const isFail = FAILED_RE.test(obs);
    const isPass = PASSED_RE.test(obs);
    for (const m of both.matchAll(EXC_RE)) {
      exceptionClasses.add(m[1]!);
      // Upstream keys this on an explicit FAILED marker. We treat the exception
      // class itself as the failure evidence, because real tool output names
      // the exception far more often than it prints the literal word "FAILED"
      // ("SegfaultError in src/faidx.c"), and the stricter rule leaves the
      // unresolved set empty on exactly the runs it exists to summarize.
      // Seeing the class alongside a pass still resolves it.
      if (isPass) passedExc.add(m[1]!);
      else if (isFail || !isPass) failedExc.add(m[1]!);
    }
    for (const tool of action.split(",")) {
      const t = tool.trim();
      if (t) commands.add(t.replace(/\[[^\]]*\]$/, ""));
    }
  }

  const cap = (s: Set<string>, n: number) => Array.from(s).slice(0, n);
  return {
    editedFiles: cap(editedFiles, 20),
    failingTests: cap(failingTests, 12),
    exceptionClasses: cap(exceptionClasses, 12),
    commands: cap(commands, 15),
    unresolved: Array.from(failedExc).filter((e) => !passedExc.has(e)).slice(0, 12),
  };
}

export function renderCompactedMemory(c: CompactedMemory): string {
  const section = (title: string, items: string[]) =>
    items.length ? `${title}: ${items.join(", ")}` : "";
  const lines = [
    section("Files touched", c.editedFiles),
    section("Tests seen", c.failingTests),
    section("Exception classes", c.exceptionClasses),
    section("Commands tried", c.commands),
    section("STILL UNRESOLVED", c.unresolved),
  ].filter(Boolean);
  return lines.length ? lines.join("\n") : "";
}
