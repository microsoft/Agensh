/**
 * F8 — secret-service (DESIGN_R7_SIDECAR §4.2 / §7).
 *
 * Real test. Brings up ONLY the `secret-service` compose service against
 * a temp tokens dir, then exercises the HTTP contract over the published
 * loopback port. No mocks of HTTP server / fs. Tears down on `afterAll`.
 *
 * Why standalone (not via globalSetup): we want fast red→green iteration
 * on the sidecar refactor without waiting for the whole Gitea stack.
 */
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync, readFileSync, chmodSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { setTimeout as sleep } from "node:timers/promises";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPO_ROOT = resolve(__dirname, "..", "..");
const COMPOSE_FILE = resolve(REPO_ROOT, "docker", "docker-compose.yml");
const SECRET_DIR = resolve(REPO_ROOT, "secret-service");
const PROJECT = "omcgitea-f8secret";
const AUTH = "test-auth-secret-do-not-use-in-prod-9b2c1f";
// Free-ish high port for host publish; collision unlikely in dev.
const HOST_PORT = 18650;

let tokensDir: string;
let containerId: string | null = null;

function sh(cmd: string, args: string[], opts: { input?: string } = {}): string {
  // Always pass -n to sudo so it never waits on TTY for a password
  // (the dev box is configured with NOPASSWD; if that ever changes the
  // test should fail loudly rather than hang vitest's hook timeout).
  const finalArgs = cmd === "sudo" ? ["-n", ...args] : args;
  const r = spawnSync(cmd, finalArgs, {
    encoding: "utf8",
    input: opts.input,
    stdio: ["pipe", "pipe", "pipe"],
  });
  if (r.status !== 0) {
    throw new Error(
      `${cmd} ${args.join(" ")} → exit ${r.status}\nstdout:${r.stdout}\nstderr:${r.stderr}`,
    );
  }
  return r.stdout;
}

async function http(
  method: "GET" | "POST",
  path: string,
  opts: { auth?: string; body?: string } = {},
): Promise<{ status: number; body: string }> {
  const headers: Record<string, string> = {};
  if (opts.auth !== undefined) headers["X-Internal-Auth"] = opts.auth;
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 3_000);
  try {
    const res = await fetch(`http://127.0.0.1:${HOST_PORT}${path}`, {
      method,
      headers,
      body: opts.body,
      signal: ctrl.signal,
    });
    return { status: res.status, body: await res.text() };
  } finally {
    clearTimeout(t);
  }
}

async function waitHealthy(timeoutMs = 30_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastErr = "";
  let i = 0;
  while (Date.now() < deadline) {
    try {
      const r = await http("GET", "/healthz");
      if (r.status === 200) return;
      lastErr = `status=${r.status}`;
    } catch (e) {
      lastErr = String(e);
    }
    if (++i % 5 === 0) console.log(`[f8] healthz attempt ${i}: ${lastErr}`);
    await sleep(500);
  }
  throw new Error(`secret-service not healthy in ${timeoutMs}ms: ${lastErr}`);
}

beforeAll(async () => {
  console.log("[f8] build image…");
  // Build the image (cheap if cached).
  sh("sudo", [
    "docker",
    "build",
    "-t",
    "omcgitea-secret-service:local",
    SECRET_DIR,
  ]);
  console.log("[f8] build done");

  // Temp tokens dir — readable by the container (mode 0755, since the
  // image runs as root and we want host-side test code to read too).
  tokensDir = mkdtempSync(resolve(tmpdir(), "omc-secret-test-"));
  chmodSync(tokensDir, 0o755);
  writeFileSync(resolve(tokensDir, "agent-agent1.token"), "real-token-from-disk-abc123\n");
  chmodSync(resolve(tokensDir, "agent-agent1.token"), 0o644);

  // Cleanup any prior leftover container from a previous test run.
  spawnSync("sudo", ["-n", "docker", "rm", "-f", `${PROJECT}-secret`], { stdio: "ignore" });
  console.log("[f8] launching container…");

  // Run the container directly (faster than full compose; we're testing
  // the image, not compose wiring — compose wiring is covered indirectly
  // by f4_e2e once full stack runs).
  const out = sh("sudo", [
    "docker", "run", "-d",
    "--name", `${PROJECT}-secret`,
    "-e", `SECRET_SERVICE_INTERNAL_AUTH=${AUTH}`,
    "-e", "SECRET_SERVICE_TOKENS_DIR=/data/tokens",
    "-v", `${tokensDir}:/data/tokens`,  // rw (POST tests need write)
    "-p", `127.0.0.1:${HOST_PORT}:8650`,
    "omcgitea-secret-service:local",
  ]);
  containerId = out.trim();
  console.log("[f8] container", containerId.slice(0, 12), "waiting healthy…");
  await waitHealthy();
  console.log("[f8] healthy");
}, 120_000);

afterAll(() => {
  if (containerId) {
    spawnSync("sudo", ["-n", "docker", "rm", "-f", `${PROJECT}-secret`], { stdio: "ignore" });
  }
  if (tokensDir) {
    // Files inside may be root-owned (container writes 0600 root) — use sudo.
    spawnSync("sudo", ["-n", "rm", "-rf", tokensDir], { stdio: "ignore" });
  }
});

describe("secret-service", () => {
  it("GET /healthz returns 200 ok", async () => {
    const r = await http("GET", "/healthz");
    expect(r.status).toBe(200);
    expect(r.body.trim()).toBe("ok");
  });

  it("GET /tokens/<agent> requires auth header → 401 without", async () => {
    const r = await http("GET", "/tokens/agent1");
    expect(r.status).toBe(401);
  });

  it("GET /tokens/<agent> rejects wrong auth → 401", async () => {
    const r = await http("GET", "/tokens/agent1", { auth: "wrong" });
    expect(r.status).toBe(401);
  });

  it("GET /tokens/agent1 with correct auth returns the on-disk token", async () => {
    const r = await http("GET", "/tokens/agent1", { auth: AUTH });
    expect(r.status).toBe(200);
    const onDisk = readFileSync(resolve(tokensDir, "agent-agent1.token"), "utf8");
    expect(r.body).toBe(onDisk);
  });

  it("GET /tokens/<nonexistent> returns 404", async () => {
    const r = await http("GET", "/tokens/doesnotexist", { auth: AUTH });
    expect(r.status).toBe(404);
  });

  it("POST /tokens/<agent> writes token, GET round-trips", async () => {
    const tok = "round-trip-token-xyz-789\n";
    const post = await http("POST", "/tokens/agent2", { auth: AUTH, body: tok });
    expect(post.status).toBe(204);
    const get = await http("GET", "/tokens/agent2", { auth: AUTH });
    expect(get.status).toBe(200);
    expect(get.body).toBe(tok);
    // Verify the file landed on disk under the expected name (read via
    // sudo since the secret-service container writes mode 0600 root-owned).
    const onDisk = execFileSync(
      "sudo",
      ["-n", "cat", resolve(tokensDir, "agent-agent2.token")],
      { encoding: "utf8" },
    );
    expect(onDisk).toBe(tok);
  });

  it("POST /tokens/<agent> requires auth → 401 without", async () => {
    const r = await http("POST", "/tokens/agent3", { body: "x" });
    expect(r.status).toBe(401);
  });

  it("handles concurrent GETs", async () => {
    const results = await Promise.all(
      Array.from({ length: 16 }, () => http("GET", "/tokens/agent1", { auth: AUTH })),
    );
    for (const r of results) {
      expect(r.status).toBe(200);
      expect(r.body).toContain("real-token-from-disk-abc123");
    }
  });
});
