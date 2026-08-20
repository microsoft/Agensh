import { execFileSync } from "node:child_process";
import {
  mkdirSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { resolve } from "node:path";
import { REPO_ROOT, TOKENS_DIR } from "./env.ts";
import { COMPOSE_CONTEXT, composePs } from "./cluster.ts";

const ARTIFACTS_DIR = resolve(REPO_ROOT, "tests", "_artifacts");
const SERVICES = [
  "gitea",
  "nginx-edge",
  "bootstrap",
  "gitea-admin-init",
  "hermes-agent-1",
  "hermes-agent-2",
];

/** Retention: keep newest N artifact subdirs; older ones are pruned. */
const KEEP_LATEST = Number(process.env.OMC_TEST_ARTIFACTS_KEEP ?? "10");

function pruneOldArtifacts(): void {
  let entries: string[];
  try {
    entries = readdirSync(ARTIFACTS_DIR);
  } catch {
    return; // directory not created yet
  }
  const dirs = entries
    .map((name) => {
      const p = resolve(ARTIFACTS_DIR, name);
      try {
        const s = statSync(p);
        if (!s.isDirectory()) return null;
        return { path: p, mtime: s.mtimeMs };
      } catch {
        return null;
      }
    })
    .filter((x): x is { path: string; mtime: number } => x !== null)
    .sort((a, b) => b.mtime - a.mtime); // newest first
  for (const old of dirs.slice(KEEP_LATEST)) {
    try {
      rmSync(old.path, { recursive: true, force: true });
    } catch {
      // best-effort
    }
  }
}

/**
 * On failure, dump container logs + a `compose ps` snapshot + a tokens
 * directory listing (names only, never contents) under
 * tests/_artifacts/<timestamp>_<label>/.
 */
export async function dumpArtifacts(label: string): Promise<string> {
  const ts = new Date()
    .toISOString()
    .replace(/[:.]/g, "-")
    .replace("T", "_")
    .replace("Z", "");
  const out = resolve(ARTIFACTS_DIR, `${ts}_${label}`);
  mkdirSync(out, { recursive: true });
  pruneOldArtifacts();

  // compose ps snapshot
  writeFileSync(resolve(out, "compose-ps.txt"), composePs());

  // Per-service logs
  for (const svc of SERVICES) {
    const path = resolve(out, `${svc}.log`);
    try {
      const log = execFileSync(
        "sudo",
        [
          "docker",
          "compose",
          "-f",
          COMPOSE_CONTEXT.COMPOSE_FILE,
          "--project-name",
          COMPOSE_CONTEXT.PROJECT_NAME,
          "--env-file",
          COMPOSE_CONTEXT.ENV_FILE,
          "--profile",
          "dev",
          "logs",
          "--no-color",
          "--tail",
          "500",
          svc,
        ],
        { encoding: "utf8", timeout: 30_000 },
      );
      writeFileSync(path, log);
    } catch (e) {
      writeFileSync(path, `(failed to fetch logs: ${String(e)})\n`);
    }
  }

  // Tokens dir listing (names only, never contents)
  try {
    const ls = execFileSync(
      "sudo",
      ["ls", "-la", TOKENS_DIR],
      { encoding: "utf8", timeout: 5_000 },
    );
    writeFileSync(resolve(out, "tokens-listing.txt"), ls);
  } catch (e) {
    writeFileSync(
      resolve(out, "tokens-listing.txt"),
      `(failed to list tokens: ${String(e)})\n`,
    );
  }

  console.log(`[artifacts] dumped to ${out}`);
  return out;
}
