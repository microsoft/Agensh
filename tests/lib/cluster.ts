import { execFileSync, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";
import {
  REPO_ROOT,
  TOKENS_DIR,
  ENV_FILE_NAME,
  PROJECT_NAME,
  type OmcEnv,
} from "./env.ts";
import { dumpArtifacts } from "./artifacts.ts";

const COMPOSE_FILE = resolve(REPO_ROOT, "docker", "docker-compose.yml");
const ENV_FILE = resolve(REPO_ROOT, ENV_FILE_NAME);
const BOOTSTRAP_FLAG = resolve(TOKENS_DIR, ".bootstrap-done");

/**
 * Check if a path exists, falling back to `sudo test -e` for paths under
 * the 0700-root tokens directory. The bootstrap container creates that
 * dir owned by root, so a non-root tester cannot stat children directly.
 */
function pathExists(p: string): boolean {
  if (existsSync(p)) return true;
  const r = spawnSync("sudo", ["test", "-e", p], { stdio: "ignore" });
  return r.status === 0;
}

/** Run `make <target>` from the repo root; throws on non-zero exit.
 *
 * IMPORTANT: forwards `PROFILE=<env.ts PROFILE>` so the test suite
 * never accidentally targets the developer's `dev` profile. The Makefile
 * defaults to PROFILE=dev when unset; passing it explicitly here keeps
 * vitest's globalTeardown (`make down`) safely confined to the test
 * cluster. See tests/lib/env.ts for the rationale.
 */
export function makeRun(target: string, timeoutMs = 600_000): void {
  // Lazy require to avoid circular env.ts ↔ cluster.ts at module init.
  // (env.ts already imported at top, but PROFILE is resolved at runtime
  // via process.env, so we read it again here in case OMC_TEST_PROFILE
  // changed mid-run — rare but cheap.)
  const profile = process.env.OMC_TEST_PROFILE || "test";
  const r = spawnSync("make", [target, `PROFILE=${profile}`], {
    cwd: REPO_ROOT,
    encoding: "utf8",
    timeout: timeoutMs,
    stdio: ["ignore", "pipe", "pipe"],
  });
  if (r.status !== 0) {
    const tail = (s: string | null) =>
      (s ?? "").split("\n").slice(-40).join("\n");
    throw new Error(
      `make ${target} failed (exit=${r.status})\n` +
        `stdout:\n${tail(r.stdout)}\n` +
        `stderr:\n${tail(r.stderr)}`,
    );
  }
}

const DEBUG = process.env.OMC_TEST_DEBUG === "1";

/** Probe nginx-edge → Gitea version endpoint. */
export async function isClusterUp(env: OmcEnv): Promise<boolean> {
  // Note: undici (Node 20 fetch) silently strips user-supplied Host headers,
  // so we cannot set Host manually on a 127.0.0.1 URL. Instead use the
  // virtual hostname directly — gitea.localhost resolves to loopback on
  // every distro we support.
  const url = `http://gitea.${env.EDGE_DOMAIN}:${env.EDGE_HTTP_PORT}/api/v1/version`;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 3_000);
  try {
    const res = await fetch(url, { signal: ctrl.signal });
    if (res.status !== 200) {
      if (DEBUG) console.warn(`[isClusterUp] ${url} status=${res.status}`);
      return false;
    }
    const text = await res.text();
    const ok = text.includes("version");
    if (DEBUG) console.warn(`[isClusterUp] ${url} body=${text.slice(0, 80)} ok=${ok}`);
    return ok;
  } catch (e) {
    if (DEBUG) console.warn(`[isClusterUp] ${url} fetch threw: ${String(e)}`);
    return false;
  } finally {
    clearTimeout(timer);
  }
}

export async function waitFor(
  predicate: () => boolean | Promise<boolean>,
  opts: { timeoutMs: number; intervalMs?: number; desc: string },
): Promise<void> {
  const { timeoutMs, intervalMs = 2_000, desc } = opts;
  const deadline = Date.now() + timeoutMs;
  let lastErr: unknown = null;
  while (Date.now() < deadline) {
    try {
      if (await predicate()) return;
    } catch (e) {
      lastErr = e;
    }
    await sleep(intervalMs);
  }
  throw new Error(
    `timed out after ${timeoutMs}ms waiting for ${desc}` +
      (lastErr ? `: ${String(lastErr)}` : ""),
  );
}

/**
 * Bring the cluster up via `make up` and wait until both:
 *  1. nginx-edge proxies a 200 from Gitea
 *  2. bootstrap has finished (.bootstrap-done flag exists)
 *
 * Honours OMC_TEST_NO_UP=1 (skip startup, assume already running).
 * On failure dumps artifacts under tests/_artifacts/.
 */
export async function bringUp(env: OmcEnv): Promise<void> {
  const skipUp = process.env.OMC_TEST_NO_UP === "1";
  if (!skipUp) {
    try {
      makeRun("up");
    } catch (e) {
      await dumpArtifacts("make-up-failed").catch(() => undefined);
      throw e;
    }
  }
  try {
    await waitFor(() => isClusterUp(env), {
      timeoutMs: 180_000,
      desc: "nginx-edge → gitea version 200",
    });
  } catch (e) {
    await dumpArtifacts("cluster-not-up").catch(() => undefined);
    throw e;
  }
  try {
    await waitFor(() => pathExists(BOOTSTRAP_FLAG), {
      timeoutMs: 120_000,
      desc: "bootstrap to finish (.bootstrap-done)",
    });
  } catch (e) {
    await dumpArtifacts("bootstrap-not-done").catch(() => undefined);
    throw e;
  }
}

/**
 * Re-run the bootstrap one-shot container. Internally uses
 * `make bootstrap-rerun` which removes `.bootstrap-done` (the early-exit
 * mark) and runs `docker compose up bootstrap`, so the script walks
 * the full reconciliation path against the current Gitea state.
 *
 * Safe to call against a healthy running cluster: bootstrap is idempotent
 * — token files are reused (still pass `GET /user`), users/repos are
 * checked-then-skipped, and any legacy hermes-agent webhooks are DELETED
 * (M2-E.1: router supersedes the webhook path).
 */
export function rerunBootstrap(timeoutMs = 120_000): void {
  makeRun("bootstrap-rerun", timeoutMs);
}

export function bringDown(): void {
  // Best-effort: don't fail teardown if compose down hiccups.
  try {
    makeRun("down", 120_000);
  } catch (e) {
    console.warn(`[cluster] make down failed: ${String(e)}`);
  }
}

/** Quick `docker compose ps` snapshot — used in artifact dumps. */
export function composePs(): string {
  try {
    return execFileSync(
      "sudo",
      [
        "docker",
        "compose",
        "-f",
        COMPOSE_FILE,
        "--project-name",
        PROJECT_NAME,
        "--env-file",
        ENV_FILE,
        "--profile",
        "dev",
        "ps",
      ],
      { encoding: "utf8", timeout: 15_000 },
    );
  } catch (e) {
    return `(compose ps failed: ${String(e)})`;
  }
}

export const COMPOSE_CONTEXT = { COMPOSE_FILE, ENV_FILE, PROJECT_NAME };
