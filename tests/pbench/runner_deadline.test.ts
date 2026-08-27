/**
 * pbench/runner_deadline.test.ts — the run brief must not state the budget.
 *
 * WHY
 * The brief used to end with "Wall-clock budget: ${HOURS}h." Telling a team it
 * has six hours makes six hours the plan: sweep_6.2 teams front-loaded
 * exploration and back-loaded integration, and the failures cluster at the end
 * of the run — gdal filed its last issue at +95m and spent the remaining 4h25m
 * with one agent coding; pandoc's writer PRs opened at +109/+130/+137/+179m and
 * none merged; ditaa never once ran compile.sh in a clean tree.
 *
 * A number the agents can pace against is worth less than a signal at the two
 * moments the correct action actually changes: stop starting new work (T-45m),
 * and land what exists (T-5m). Those already exist as *instructions* in
 * director_lead/workflow.md ("Stage 3: convergence (last 45 minutes)") but the
 * agents had no way to know when they were in that stage — there is no clock in
 * the container and no external trigger. So the runner sends them.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { REPO_ROOT } from "../lib/env.ts";

const RUNNER = resolve(REPO_ROOT, "scripts/pbench_run_1team.sh");
const text = () => readFileSync(RUNNER, "utf8");

/** The heredoc body of task_brief(), which is what agents actually receive. */
function brief(body: string): string {
  const m = body.match(/task_brief\(\)\s*\{[\s\S]*?^\s*cat <<EOF$([\s\S]*?)^EOF$/m);
  if (!m) throw new Error("task_brief heredoc not found");
  return m[1]!;
}

describe("run brief and deadline reminders", () => {
  it("does not tell the team how long it has", () => {
    const b = brief(text());
    expect(b).not.toMatch(/wall-?clock budget/i);
    expect(b).not.toMatch(/\$\{HOURS\}/);
    expect(b).not.toMatch(/\b\d+\s*h(ours?)?\b/i);
  });

  it("still tells them the deliverable and that nobody is coming", () => {
    // Removing the budget must not remove the rest of the brief.
    const b = brief(text());
    expect(b).toContain("compile.sh");
    expect(b).toContain("./executable");
    expect(b).toMatch(/NO internet access/i);
    expect(b).toMatch(/FULLY autonomous/i);
  });

  it("schedules reminders at T-45m and T-5m", () => {
    const body = text();
    expect(body).toMatch(/deadline_reminder_loop\(\)/);
    // Offsets expressed in seconds from the end of the run.
    expect(body).toMatch(/45\s*\*\s*60/);
    expect(body).toMatch(/5\s*\*\s*60/);
  });

  it("runs the reminder loop alongside the wait, and reaps it", () => {
    const body = text();
    expect(body).toMatch(/deadline_reminder_loop\s+"\$secs"\s*&/);
    // A leaked background loop would outlive the run and post into the next one.
    expect(body).toMatch(/kill\s+"\$reminder_pid"/);
  });

  it("the two reminders say different things", () => {
    // T-45m = stop starting new work. T-5m = land what exists. If both said
    // "hurry up" the second would add nothing.
    const body = text();
    const loop = body.match(/deadline_reminder_loop\(\)\s*\{[\s\S]*?\n\}/)?.[0] ?? "";
    expect(loop).toMatch(/45 minutes|45m/i);
    expect(loop).toMatch(/5 minutes|5m/i);
    expect(loop).toMatch(/merge|land|compile\.sh/i);
  });
});
