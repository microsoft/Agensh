/**
 * pbench/agent_image.test.ts — the agent image must be selectable per profile.
 *
 * Every ProgramBench task is graded inside its own `task_cleanroom_v6` image.
 * Until now every agent ran in v48-cleanroom, the UNION of all 20 toolchains,
 * which put the agent's build environment out of step with the grader's: the
 * union carried clap 4.6.4 / serde 1.0.229 while every cleanroom carried
 * 4.6.1 / 1.0.228. Agents built green, wrote a Cargo.lock pinning the newer
 * crate, and eval could not resolve it — pueue, ast-grep and typst each scored
 * 0.00% on a one-patch-version skew.
 *
 * Dockerfile.pertask fixes the images; this fixes the wiring. The compose
 * template hard-coded `omcgitea-hermes-agent:local`, so selecting a per-task
 * image meant retagging a global name — which cannot work when 20 tasks run
 * concurrently against 20 different images on one host.
 *
 * The default must remain the historical tag so every existing profile and
 * every sweep_5/6/6.1 rerun is unaffected.
 */
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { REPO_ROOT } from "../lib/env.ts";

const GENERATOR = resolve(REPO_ROOT, "tools/gen-compose-prod.py");
const PROD = resolve(REPO_ROOT, "docker/docker-compose.prod.yml");

const text = (p: string) => readFileSync(p, "utf8");

/** Render the generator's output with a given env and parse the image line. */
function generatedImage(extraEnv: Record<string, string> = {}): string {
  const result = spawnSync("python3", [GENERATOR], {
    cwd: REPO_ROOT,
    env: { ...process.env, ...extraEnv },
    encoding: "utf8",
    timeout: 30_000,
  });
  if (result.status !== 0) {
    throw new Error(`generator failed\n${result.stderr}`);
  }
  const m = result.stdout.match(/^\s*image:\s*"([^"]+)"/m);
  if (!m) throw new Error("generated compose has no image: line");
  return m[1]!;
}

describe("per-profile agent image selection", () => {
  it("makes the agent image an interpolated variable, not a literal", () => {
    // Both the frozen prod template and the generator that supersedes it.
    for (const f of [PROD, GENERATOR]) {
      expect(text(f)).toContain("${AGENT_IMAGE:-omcgitea-hermes-agent:local}");
    }
  });

  it("defaults to the historical tag so existing profiles are unchanged", () => {
    expect(generatedImage()).toBe("${AGENT_IMAGE:-omcgitea-hermes-agent:local}");
  });

  it("compose interpolates AGENT_IMAGE from the profile env file", () => {
    // The value reaches compose through --env-file, which is also how
    // DATA_ROOT and the edge ports are already threaded per profile.
    const body = text(PROD);
    const anchor = body.match(/x-hermes-agent:[\s\S]{0,200}/)?.[0] ?? "";
    expect(anchor).toContain("AGENT_IMAGE");
    expect(anchor).not.toMatch(/image:\s*"omcgitea-hermes-agent:local"/);
  });
});
