/**
 * f8_sidecar/workspace_probe.test.ts — the "has this agent actually changed
 * source?" signal behind the PATCH_READY / SOURCE_DIFF checkpoints.
 *
 * These run against real directories rather than mocks: the whole value of the
 * probe is that it reports what is on disk instead of what the agent claimed,
 * so mocking the filesystem would test nothing worth testing.
 */
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  WorkspaceProbe,
  isSourceLike,
  patchReadyNudge,
  sourceDiffNudge,
} from "../../mini-router/src/workspace_probe.ts";

describe("isSourceLike", () => {
  it("accepts authored source", () => {
    for (const p of ["src/bgzf.c", "include/hts.h", "compile.sh", "Makefile", "a/b/c.py"]) {
      expect(isSourceLike(p), p).toBe(true);
    }
  });

  it("rejects tests — the grader discards test edits, so they are not a fix", () => {
    for (const p of ["tests/test_view.py", "test/foo.c", "src/test_helper.py", "src/foo_test.go"]) {
      expect(isSourceLike(p), p).toBe(false);
    }
  });

  it("rejects build output, caches and the built artifact itself", () => {
    for (const p of [
      "src/bgzf.o", "libhts.a", "build/x.c", "node_modules/y/index.js",
      "__pycache__/m.pyc", ".git/config", "executable", "out.log",
    ]) {
      expect(isSourceLike(p), p).toBe(false);
    }
  });

  it("rejects empty and dotfile paths", () => {
    expect(isSourceLike("")).toBe(false);
    expect(isSourceLike("   ")).toBe(false);
    expect(isSourceLike(".gitignore")).toBe(false);
  });
});

describe("WorkspaceProbe", () => {
  let dir: string;
  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), "wsprobe-"));
  });
  afterEach(async () => {
    await rm(dir, { recursive: true, force: true });
  });

  it("reports unavailable when no workspace is configured", async () => {
    const p = new WorkspaceProbe(undefined);
    expect(p.configured).toBe(false);
    expect(await p.probe()).toEqual({ available: false, changed: [] });
  });

  it("reports unavailable for a path the router cannot see", async () => {
    // This is the our-method case: the agent's /work is container-local.
    const p = new WorkspaceProbe(join(dir, "does-not-exist"));
    const r = await p.probe();
    expect(r.available).toBe(false);
  });

  it("detects new source files in a plain (non-git) shared workspace", async () => {
    // DeLM's /work is a directory, not a checkout.
    const p = new WorkspaceProbe(dir, () => Date.now() - 10_000);
    await mkdir(join(dir, "src"), { recursive: true });
    await writeFile(join(dir, "src", "faidx.c"), "int main(){}");
    const r = await p.probe();
    expect(r.available).toBe(true);
    expect(r.changed).toContain("src/faidx.c");
  });

  it("filters out build output and tests from what it reports", async () => {
    const p = new WorkspaceProbe(dir, () => Date.now() - 10_000);
    await mkdir(join(dir, "src"), { recursive: true });
    await mkdir(join(dir, "tests"), { recursive: true });
    await writeFile(join(dir, "src", "a.c"), "x");
    await writeFile(join(dir, "src", "a.o"), "x");
    await writeFile(join(dir, "tests", "test_a.py"), "x");
    await writeFile(join(dir, "executable"), "x");
    const r = await p.probe();
    expect(r.changed).toContain("src/a.c");
    expect(r.changed).not.toContain("src/a.o");
    expect(r.changed).not.toContain("tests/test_a.py");
    expect(r.changed).not.toContain("executable");
  });

  it("reports only NEW work on a second probe", async () => {
    const p = new WorkspaceProbe(dir, () => Date.now() - 10_000);
    await writeFile(join(dir, "one.c"), "x");
    expect((await p.probe()).changed).toContain("one.c");
    // Nothing new written → nothing new reported.
    const second = await p.probe();
    expect(second.changed).not.toContain("one.c");
  });
});

describe("checkpoint nudges", () => {
  it("PATCH_READY tells the agent to close out", () => {
    const n = patchReadyNudge(["src/a.c"], false);
    expect(n).toContain("PATCH_READY_CHECKPOINT");
    expect(n).toContain("board_finalize");
    expect(n).toContain("DONE");
  });

  it("PATCH_READY stays silent after a failing step", () => {
    // Finishing on a known-broken state is worse than continuing.
    expect(patchReadyNudge(["src/a.c"], true)).toBe("");
  });

  it("PATCH_READY stays silent with no source change", () => {
    expect(patchReadyNudge([], false)).toBe("");
  });

  it("SOURCE_DIFF is rate-limited so it does not become noise", () => {
    const changed = ["src/a.c"];
    expect(sourceDiffNudge(changed, 1)).toBe("");
    expect(sourceDiffNudge(changed, 2)).toBe("");
    expect(sourceDiffNudge(changed, 3)).toContain("SOURCE_DIFF_CHECKPOINT");
    expect(sourceDiffNudge(changed, 6)).toContain("SOURCE_DIFF_CHECKPOINT");
  });

  it("SOURCE_DIFF stays silent with no source change", () => {
    expect(sourceDiffNudge([], 3)).toBe("");
  });
});
