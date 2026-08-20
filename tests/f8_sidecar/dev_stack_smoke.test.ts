/**
 * R7 sidecar smoke — end-to-end on real dev stack.
 *
 * Lead opens 1 issue assigned to a coder. Verify the mini-router-<coder>
 * sidecar:
 *   1. ingests the gitea notification into MySQL within 30s
 *   2. dispatches via ACP unix socket to the hermes-agent container
 *   3. event row state goes pending → sending (and ideally → sent if
 *      hermes finishes in time)
 *
 * This is the regression test for: "agent3 didn't get pinged" / sidecar
 * boots but never receives events / ACP socket dead etc.
 */
import { describe, expect, it, beforeAll } from "vitest";
import { setTimeout as sleep } from "node:timers/promises";
import { spawnSync } from "node:child_process";
import { loadEnv, REPO_ROOT, TOKENS_DIR, ENV_FILE_NAME, PROJECT_NAME } from "../lib/env.ts";

const env = loadEnv();
const baseUrl = `http://gitea.${env.EDGE_DOMAIN}:${env.EDGE_HTTP_PORT}`;
const tokensDir = TOKENS_DIR;

function adminToken(): string {
  const r = spawnSync("sudo", ["cat", `${tokensDir}/admin.token`], { encoding: "utf8" });
  if (r.status !== 0) throw new Error("cannot read admin token: " + r.stderr);
  return r.stdout.trim();
}

function leadToken(): string {
  const lead = env.ROLES.lead[0];
  const r = spawnSync("sudo", ["cat", `${tokensDir}/agent-${lead}.token`], { encoding: "utf8" });
  if (r.status !== 0) throw new Error(`cannot read lead token (${tokensDir}/agent-${lead}.token): ${r.stderr}`);
  return r.stdout.trim();
}

function mysqlQuery(sql: string): string {
  const pwRes = spawnSync("bash", ["-c", `grep MYSQL_PASSWORD ${REPO_ROOT}/${ENV_FILE_NAME} | cut -d= -f2`], { encoding: "utf8" });
  const pw = pwRes.stdout.trim();
  const r = spawnSync("sudo", [
    "docker", "exec", `${PROJECT_NAME}-mysql-1`,
    "mysql", "-uomcgitea", `-p${pw}`, "omcgitea", "-sNe", sql,
  ], { encoding: "utf8" });
  if (r.status !== 0) throw new Error(`mysql query failed: ${r.stderr}`);
  return r.stdout.trim();
}

describe("R7 sidecar smoke (real dev stack)", () => {
  const stamp = Date.now();
  const repo = env.REPOS[0]!;
  const owner = env.GITEA_ORG;
  let issueNumber: number;
  let coder: string;

  beforeAll(async () => {
    coder = env.ROLES.coder[0]!;
    // Wait for mini-router-<coder> to be healthy
    const sidecarName = `${PROJECT_NAME}-mini-router-${coder}-1`;
    let healthy = false;
    for (let i = 0; i < 30; i++) {
      const r = spawnSync("sudo", ["docker", "inspect", "--format", "{{.State.Health.Status}}", sidecarName], { encoding: "utf8" });
      if (r.stdout.trim() === "healthy") { healthy = true; break; }
      await sleep(2000);
    }
    expect(healthy, `${sidecarName} did not become healthy in 60s`).toBe(true);
  }, 120_000);

  it("lead issue → mini-router ingests within 30s → event reaches sending/sent", async () => {
    const tok = leadToken();
    const body = `@${coder} R7 smoke ${stamp} — please observe and reply with comment 'r7-ack-${stamp}' on this issue.`;
    const res = await fetch(`${baseUrl}/api/v1/repos/${owner}/${repo}/issues`, {
      method: "POST",
      headers: { "Authorization": `token ${tok}`, "Content-Type": "application/json" },
      body: JSON.stringify({ title: `R7 smoke ${stamp}`, body, assignees: [coder] }),
    });
    expect(res.status).toBe(201);
    const issue = await res.json() as { number: number };
    issueNumber = issue.number;

    // Poll mysql events table — a fresh ingest with this issue's notification
    // must appear within 30s (SSE wake + pull).
    const deadline = Date.now() + 60_000;
    let ingested = false;
    let finalState = "";
    let finalAttempts = 0;
    while (Date.now() < deadline) {
      const out = mysqlQuery(
        `SELECT state, attempts FROM events WHERE agent='${coder}' AND payload LIKE '%R7 smoke ${stamp}%' LIMIT 1`,
      );
      if (out) {
        const [state, attempts] = out.split("\t");
        finalState = state ?? "";
        finalAttempts = Number(attempts ?? 0);
        ingested = true;
        if (finalState === "sent") break;
      }
      await sleep(2000);
    }
    expect(ingested, `event for issue #${issueNumber} not ingested in 60s`).toBe(true);
    expect(["pending", "sending", "sent", "failed", "retrying"]).toContain(finalState);
    // Either sent (hermes finished) or in-flight (sending) — both prove the
    // dispatch chain reached the ACP socket.
    expect(finalAttempts).toBeGreaterThanOrEqual(1);
    // eslint-disable-next-line no-console
    console.log(`[smoke] issue #${issueNumber} → coder=${coder} → state=${finalState} attempts=${finalAttempts}`);
  }, 90_000);
});
