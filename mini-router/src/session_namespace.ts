/**
 * ACP session IDs are runtime-specific. A single logical agent may switch
 * between Claude, Copilot, and Hermes, so sharing one KV key would overwrite
 * another runtime's resumable session and make rollback unsafe.
 */
export type AcpSessionNamespace = "claude" | "copilot" | "hermes";

export interface SessionKvStore {
  getKv(agent: string, key: string): Promise<string | null>;
  setKv(agent: string, key: string, value: string): Promise<void>;
}

export interface AcpSessionStore {
  get(): Promise<string | null>;
  set(sessionId: string): Promise<void>;
}

const LEGACY_SESSION_KEY = "acp_session_id";

export function parseAcpSessionNamespace(
  value: string | undefined,
): AcpSessionNamespace {
  if (value === "claude" || value === "copilot" || value === "hermes") {
    return value;
  }
  throw new Error(
    `ACP_SESSION_NAMESPACE must be one of claude|copilot|hermes; got ${JSON.stringify(value ?? "")}`,
  );
}

export function sessionKvKey(namespace: AcpSessionNamespace): string {
  return `${LEGACY_SESSION_KEY}:${namespace}`;
}

/**
 * Create the ACPSocketChannel persistence adapter.
 *
 * Migration rule: the pre-namespace key belonged to the default Claude
 * runtime, so only Claude copies it. The legacy value is retained.
 */
export function createAcpSessionStore(
  kv: SessionKvStore,
  agent: string,
  namespace: AcpSessionNamespace,
): AcpSessionStore {
  const key = sessionKvKey(namespace);
  return {
    async get(): Promise<string | null> {
      const current = await kv.getKv(agent, key);
      if (current) return current;
      if (namespace !== "claude") return null;

      const legacy = await kv.getKv(agent, LEGACY_SESSION_KEY);
      if (!legacy) return null;
      await kv.setKv(agent, key, legacy);
      return legacy;
    },
    async set(sessionId: string): Promise<void> {
      await kv.setKv(agent, key, sessionId);
    },
  };
}
