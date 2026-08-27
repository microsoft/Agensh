/**
 * Cluster-level fixture builders. Vitest doesn't have pytest-style
 * dependency-injected fixtures, so we expose factory functions that
 * tests call inside `beforeAll` to pin a session-scoped resource.
 */
import { GiteaClient } from "./gitea.ts";
import { loadEnv, type OmcEnv } from "./env.ts";
import { readAdminToken, readAgentToken } from "./tokens.ts";

export interface TestContext {
  env: OmcEnv;
  baseUrl: string;
  hostHeader: string;
  /** Anonymous client. */
  gitea: GiteaClient;
  /** Authenticated as chairman/admin. */
  giteaAdmin: GiteaClient;
  /** Per-agent authenticated clients. */
  giteaAgents: Map<string, GiteaClient>;
  adminToken: string;
  agentTokens: Map<string, string>;
}

export function makeContext(): TestContext {
  const env = loadEnv();
  // Use the virtual hostname in the URL itself — undici strips Host
  // headers, so we route via DNS (gitea.localhost → 127.0.0.1) instead.
  const baseUrl = `http://gitea.${env.EDGE_DOMAIN}:${env.EDGE_HTTP_PORT}`;
  const hostHeader = `gitea.${env.EDGE_DOMAIN}`;
  const gitea = new GiteaClient(baseUrl, hostHeader);
  const adminToken = readAdminToken();
  const giteaAdmin = gitea.withToken(adminToken);

  const agentTokens = new Map<string, string>();
  const giteaAgents = new Map<string, GiteaClient>();
  for (const a of env.AGENTS) {
    const t = readAgentToken(a);
    agentTokens.set(a, t);
    giteaAgents.set(a, gitea.withToken(t));
  }

  return {
    env,
    baseUrl,
    hostHeader,
    gitea,
    giteaAdmin,
    giteaAgents,
    adminToken,
    agentTokens,
  };
}
