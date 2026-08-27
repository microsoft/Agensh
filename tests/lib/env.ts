import { readFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
export const REPO_ROOT = resolve(dirname(__filename), "..", "..");

/**
 * Tests are pinned to the **test** profile (DESIGN §5.A). dev is the
 * developer's long-running cluster and prod is operated separately —
 * the test suite must never touch either, since vitest's globalTeardown
 * runs `make down` and would wipe a live environment.
 *
 * Override via OMC_TEST_PROFILE=<name> only if you really know what
 * you're doing (e.g. running the suite against a freshly-bootstrapped
 * staging cluster).
 */
export const PROFILE = process.env.OMC_TEST_PROFILE || "test";
export const ENV_FILE_NAME = `.env.${PROFILE}`;
export const PROJECT_NAME = `omcgitea-${PROFILE}`;
export const DATA_DIR = resolve(REPO_ROOT, ".claude-team-data", PROFILE);
export const TOKENS_DIR = resolve(DATA_DIR, "tokens");

export interface RolesMap {
  lead: string[];
  reviewer: string[];
  coder: string[];
}

export interface OmcEnv {
  GITEA_ADMIN_USER: string;
  GITEA_ADMIN_PASSWORD: string;
  /** R5: org owning all repos. Default 'omcgitea'. */
  GITEA_ORG: string;
  AGENTS: string[];
  REPOS: string[];
  EDGE_HTTP_PORT: string;
  EDGE_DOMAIN: string;
  /**
   * Team role assignment (R4 / TEAMCONFIG). Format in .env.<profile>:
   *   ROLES=lead=agent1;reviewer=agent2;coder=agent3,agent4,agent5,...
   * Buckets separated by ';', agents within a bucket by ','.
   * Default if absent: first agent = lead, second = reviewer, rest = coder.
   */
  ROLES: RolesMap;
  raw: Record<string, string>;
}

/**
 * Parse the project .env.<profile> (KEY=VALUE lines) into a typed view.
 * Throws if the file is missing — tests cannot run without it.
 */
export function loadEnv(): OmcEnv {
  const path = resolve(REPO_ROOT, ENV_FILE_NAME);
  if (!existsSync(path)) {
    throw new Error(
      `${ENV_FILE_NAME} not found at ${path}. ` +
        `Run \`cp .env.example ${ENV_FILE_NAME}\` and set GITEA_ADMIN_PASSWORD.`,
    );
  }
  const raw: Record<string, string> = {};
  for (const line of readFileSync(path, "utf8").split("\n")) {
    const t = line.trim();
    if (!t || t.startsWith("#") || !t.includes("=")) continue;
    const idx = t.indexOf("=");
    const k = t.slice(0, idx).trim();
    let v = t.slice(idx + 1).trim();
    if (
      (v.startsWith('"') && v.endsWith('"')) ||
      (v.startsWith("'") && v.endsWith("'"))
    ) {
      v = v.slice(1, -1);
    }
    raw[k] = v;
  }
  const must = (k: string): string => {
    const v = raw[k];
    if (!v) throw new Error(`${ENV_FILE_NAME}: ${k} is required`);
    return v;
  };
  const splitCsv = (s: string | undefined): string[] =>
    (s ?? "").split(",").map((x) => x.trim()).filter(Boolean);

  const agents = splitCsv(raw.AGENTS).length > 0
    ? splitCsv(raw.AGENTS)
    : ["agent1", "agent2"];

  // Parse ROLES="lead=agent1;reviewer=agent2;coder=agent3,agent4"
  const roles: RolesMap = { lead: [], reviewer: [], coder: [] };
  if (raw.ROLES) {
    for (const bucket of raw.ROLES.split(";")) {
      const [k, v] = bucket.split("=");
      const key = (k ?? "").trim();
      if (key === "lead" || key === "reviewer" || key === "coder") {
        roles[key] = splitCsv(v);
      }
    }
  }
  // Default fallback: first=lead, second=reviewer, rest=coder.
  if (roles.lead.length + roles.reviewer.length + roles.coder.length === 0) {
    roles.lead = agents.slice(0, 1);
    roles.reviewer = agents.slice(1, 2);
    roles.coder = agents.slice(2);
  }

  return {
    GITEA_ADMIN_USER: raw.GITEA_ADMIN_USER ?? "chairman",
    GITEA_ADMIN_PASSWORD: must("GITEA_ADMIN_PASSWORD"),
    GITEA_ORG: raw.GITEA_ORG ?? "omcgitea",
    AGENTS: agents,
    REPOS: splitCsv(raw.REPOS).length > 0
      ? splitCsv(raw.REPOS)
      : ["test-sandbox"],
    EDGE_HTTP_PORT: raw.EDGE_HTTP_PORT ?? "28081",
    EDGE_DOMAIN: raw.EDGE_DOMAIN ?? "localhost",
    ROLES: roles,
    raw,
  };
}
