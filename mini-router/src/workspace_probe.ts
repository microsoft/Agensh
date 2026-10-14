/**
 * workspace_probe — "has this agent actually changed source?" for the
 * PATCH_READY / SOURCE_DIFF checkpoints (implementer_runner.py:413-476).
 *
 * Upstream gates both nudges on `git diff --name-only` in the agent's worktree,
 * filtered by `_source_like_path` (implementer_runner.py:39-94). The point is
 * to distinguish an agent that has produced a candidate fix from one that has
 * only been reading — a distinction you cannot make from the conversation,
 * because agents narrate edits they never made.
 *
 * Availability differs by topology, and this degrades rather than lying:
 *
 *   shared /work           /work is a host bind mount shared by every agent,
 *                          so the router can see it. Probe works.
 *   per-agent /work        each agent's /work is container-local; the router
 *                          has no path to it. `available` is false and both
 *                          nudges stay silent — better than firing on a guess.
 *
 * Non-git workspaces are supported too: DeLM's shared /work is a plain
 * directory, not a checkout, so we fall back to mtime scanning.
 */
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { readdir, stat } from "node:fs/promises";
import { join } from "node:path";

const execFileP = promisify(execFile);

/** Directories never worth reporting as source change. */
const SKIP_DIRS = new Set([
  ".git", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache",
  "build", "dist", "target", ".cache", "tmp", ".tox", ".venv", "venv",
  "CMakeFiles", ".deps", ".libs",
]);

/** Suffixes that are build output or binary, not authored source. */
const SKIP_SUFFIXES = [
  ".o", ".a", ".so", ".dylib", ".dll", ".exe", ".pyc", ".pyo", ".class",
  ".jar", ".lo", ".la", ".gz", ".tar", ".zip", ".log", ".d",
];

/**
 * Upstream's `_source_like_path`: authored source only.
 *
 * Test files are excluded deliberately — on ProgramBench the grader discards
 * test edits, so an agent that has only touched tests has NOT produced a
 * candidate fix, and nudging it to finish would be actively wrong.
 */
export function isSourceLike(path: string): boolean {
  const p = (path ?? "").trim();
  if (!p) return false;
  const parts = p.split("/");
  for (const seg of parts.slice(0, -1)) {
    if (SKIP_DIRS.has(seg)) return false;
    if (seg === "test" || seg === "tests") return false;
  }
  const base = parts[parts.length - 1] ?? "";
  if (!base || base.startsWith(".")) return false;
  if (base.startsWith("test_") || /_test\.[A-Za-z0-9]+$/.test(base)) return false;
  for (const s of SKIP_SUFFIXES) if (base.endsWith(s)) return false;
  // The built artifact itself is never a source change.
  if (base === "executable") return false;
  return true;
}

export interface WorkspaceState {
  /** False when the router cannot see the workspace at all. */
  available: boolean;
  /** Source-like paths changed, capped for prompt sanity. */
  changed: string[];
}

export class WorkspaceProbe {
  /** mtime high-water mark for the non-git fallback. */
  private since: number;

  constructor(
    private readonly path: string | undefined,
    now: () => number = Date.now,
  ) {
    this.since = now();
  }

  get configured(): boolean {
    return Boolean(this.path);
  }

  /** Source-like files changed in the workspace, or available:false. */
  async probe(): Promise<WorkspaceState> {
    if (!this.path) return { available: false, changed: [] };
    const viaGit = await this.gitChanged();
    if (viaGit !== null) {
      return { available: true, changed: viaGit.filter(isSourceLike).slice(0, 25) };
    }
    const viaMtime = await this.mtimeChanged();
    if (viaMtime === null) return { available: false, changed: [] };
    return { available: true, changed: viaMtime.filter(isSourceLike).slice(0, 25) };
  }

  /** null when this is not a git worktree (or git is unavailable). */
  private async gitChanged(): Promise<string[] | null> {
    try {
      const { stdout } = await execFileP(
        "git",
        ["-C", this.path!, "status", "--porcelain", "--untracked-files=all"],
        { timeout: 10_000, maxBuffer: 4 * 1024 * 1024 },
      );
      return stdout
        .split("\n")
        .map((l) => l.slice(3).trim())
        .filter(Boolean);
    } catch {
      return null;
    }
  }

  /**
   * Files modified since the last probe. Advances the high-water mark, so each
   * call reports only new work — matching `git diff`'s "since you last looked"
   * semantics rather than re-reporting the whole tree forever.
   */
  private async mtimeChanged(): Promise<string[] | null> {
    // Establish visibility FIRST. Without this an unreadable path walks to an
    // empty result and reports available:true — making "the router cannot see
    // this workspace" look identical to "nothing changed", which would silently
    // suppress the nudges for the wrong reason.
    try {
      const st = await stat(this.path!);
      if (!st.isDirectory()) return null;
    } catch {
      return null;
    }
    const out: string[] = [];
    const cutoff = this.since;
    let newest = cutoff;
    const walk = async (dir: string, rel: string, depth: number): Promise<void> => {
      if (depth > 8) return;
      let entries;
      try {
        entries = await readdir(dir, { withFileTypes: true });
      } catch {
        return;
      }
      for (const e of entries) {
        if (SKIP_DIRS.has(e.name)) continue;
        const abs = join(dir, e.name);
        const r = rel ? `${rel}/${e.name}` : e.name;
        if (e.isDirectory()) {
          await walk(abs, r, depth + 1);
        } else if (e.isFile()) {
          try {
            const st = await stat(abs);
            if (st.mtimeMs > cutoff) {
              out.push(r);
              if (st.mtimeMs > newest) newest = st.mtimeMs;
            }
          } catch {
            /* raced with a write; skip */
          }
        }
      }
    };
    try {
      await walk(this.path!, "", 0);
    } catch {
      return null;
    }
    this.since = newest;
    return out;
  }
}

/**
 * PATCH_READY (implementer_runner.py:413-449): the agent has a valid
 * PATCH_SUMMARY *and* real source changes on disk. Tell it to close out rather
 * than keep exploring — an agent that never finishes scores zero however good
 * its patch was.
 *
 * Suppressed when the last step showed a failure: finishing on a known-broken
 * state is worse than continuing.
 */
export function patchReadyNudge(changed: string[], lastStepFailed: boolean): string {
  if (changed.length === 0 || lastStepFailed) return "";
  return [
    "PATCH_READY_CHECKPOINT:",
    `You have published a PATCH_SUMMARY and there are real source changes on disk (${changed
      .slice(0, 6)
      .join(", ")}${changed.length > 6 ? `, +${changed.length - 6} more` : ""}).`,
    "Unless your last step revealed a problem, stop exploring and close out:",
    "verify the build one more time, call `board_finalize`, and say DONE.",
    "Work that is never handed off scores the same as work never done.",
  ].join("\n");
}

/**
 * SOURCE_DIFF (implementer_runner.py:451-476): source changed but nothing was
 * published. Rate-limited to every 3rd step upstream, because firing it every
 * step trains the agent to ignore it.
 */
export function sourceDiffNudge(
  changed: string[],
  step: number,
  everyN = 3,
): string {
  if (changed.length === 0) return "";
  if (step % everyN !== 0) return "";
  return [
    "SOURCE_DIFF_CHECKPOINT:",
    `You have changed source (${changed.slice(0, 6).join(", ")}) but published nothing about it.`,
    "Run the smallest check that would confirm or refute the change, then either",
    "publish a PATCH_SUMMARY with that result as evidence, or a FAIL saying what",
    "broke. Peers cannot build on changes they cannot see.",
  ].join("\n");
}
