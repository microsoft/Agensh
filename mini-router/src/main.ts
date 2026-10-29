/**
 * Wire one worker's durable event queue, service listeners and ACP dispatcher.
 * The router delivers activity; the agent prompt defines how agents cooperate.
 */
import { EventStore } from "./state.ts";
import { Dispatcher } from "./dispatcher.ts";
import { ACPSocketChannel } from "./acp_socket_channel.ts";
import { GiteaListener } from "./listeners/gitea/listener.ts";
import { GiteaFormAuth } from "./gitea_form_auth.ts";
import { MattermostListener } from "./listeners/mattermost/listener.ts";
import { BoardClient, parseBoardIds } from "./board_client.ts";
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { sleep } from "./runtime.ts";

interface Env {
  agent: string;
  agentKind: "pi" | "copilot" | "codex" | "claude";
  giteaHost: string;
  hostHeader?: string;
  mysqlDsn: string;
  secretServiceUrl: string;
  secretAuth: string;
  acpSocketPath: string;
  giteaPasswordFile: string;
  listenPort: number;
  retrySweepMs: number;
  mattermostHost?: string;
  mattermostHostHeader?: string;
  boardServiceUrl?: string;
  boardIds: string[];
}

function readEnv(): Env {
  const agent = required("AGENT_NAME");
  const agentKind = process.env.AGENT_HARNESS ?? "copilot";
  if (agentKind !== "pi" && agentKind !== "copilot" && agentKind !== "codex" && agentKind !== "claude") {
    throw new Error("AGENT_HARNESS must be pi, copilot, codex or claude");
  }
  return {
    agent,
    agentKind,
    giteaHost: required("GITEA_HOST"),
    hostHeader: process.env.GITEA_HOST_HEADER,
    mysqlDsn: required("MYSQL_DSN"),
    secretServiceUrl: required("SECRET_SERVICE_URL"),
    secretAuth: required("SECRET_SERVICE_INTERNAL_AUTH"),
    acpSocketPath: process.env.ACP_SOCKET_PATH ?? "/var/run/acp/agent.sock",
    giteaPasswordFile:
      process.env.GITEA_PASSWORD_FILE ?? `/run/omcgitea/tokens/agent-${agent}.password`,
    listenPort: Number(process.env.MINI_ROUTER_PORT ?? "8645"),
    retrySweepMs: Number(process.env.RETRY_SWEEP_MS ?? "30000"),
    ...(process.env.MATTERMOST_HOST ? { mattermostHost: process.env.MATTERMOST_HOST } : {}),
    ...(process.env.MATTERMOST_HOST_HEADER ? { mattermostHostHeader: process.env.MATTERMOST_HOST_HEADER } : {}),
    ...(process.env.BOARD_SERVICE_URL ? { boardServiceUrl: process.env.BOARD_SERVICE_URL } : {}),
    boardIds: parseBoardIds(process.env.BOARD_IDS),
  };
}

function required(name: string): string {
  const v = process.env[name];
  if (!v) {
    throw new Error(`missing env ${name}`);
  }
  return v;
}

async function fetchToken(url: string, agent: string, auth: string): Promise<string> {
  const res = await fetch(`${url.replace(/\/$/, "")}/tokens/${agent}`, {
    headers: { "X-Internal-Auth": auth },
  });
  if (!res.ok) {
    throw new Error(`secret-service /tokens/${agent} → ${res.status}`);
  }
  return (await res.text()).trim();
}

function readPassword(file: string): string {
  try {
    return readFileSync(file, "utf8").trim();
  } catch (e) {
    throw new Error(`cannot read agent password at ${file}: ${(e as Error).message}`);
  }
}

async function main(): Promise<void> {
  const env = readEnv();
  const log = (lvl: string, msg: string, extra?: unknown) => {
    const t = new Date().toISOString();
    console.error(`[mini-router ${env.agent}] ${t} ${lvl} ${msg}`, extra ?? "");
  };
  log("info", `boot agent=${env.agent}`);

  const token = await fetchToken(env.secretServiceUrl, env.agent, env.secretAuth);
  log("info", `token fetched len=${token.length}`);

  const store = new EventStore(env.mysqlDsn);
  await store.ensureSchema();
  // A router restart may interrupt a turn before its delivery is acknowledged.
  const recovered = await store.recoverSendingToPending(env.agent);
  if (recovered > 0) log("warn", `recovered ${recovered} stuck 'sending' rows → pending`);

  const stuckMs = Number(process.env.MINI_ROUTER_STUCK_MS ?? "0") || undefined;
  const channel = new ACPSocketChannel({
    socketPath: env.acpSocketPath,
    cwd: "/work",
    onLog: (lvl, msg, err) => log(`acp.${lvl}`, msg, err),
    sessionStore: {
      get: () => store.getKv(env.agent, `acp_session_id:${env.agentKind}`),
      set: (sessionId) => store.setKv(env.agent, `acp_session_id:${env.agentKind}`, sessionId),
    },
    stuckMs,
  });

  const board = new BoardClient({
    ...(env.boardServiceUrl ? { baseUrl: env.boardServiceUrl } : {}),
    agent: env.agent,
    boardIds: env.boardIds,
    log: (lvl, msg, err) => log(lvl, `[board] ${msg}`, err),
  });
  if (board.enabled) {
    log(
      "info",
      `shared context ON: url=${env.boardServiceUrl} boards=${env.boardIds.join(",")}`,
    );
  }

  const dispatcher = new Dispatcher({
    agent: env.agent,
    groupMessageDirectory: "/opt/data/home/group-messages",
    state: store,
    channel,
    board,
    onLog: (e) => log(e.level, e.msg, e.err),
  });

  const password = readPassword(env.giteaPasswordFile);
  const auth = new GiteaFormAuth({
    baseUrl: env.giteaHost,
    username: env.agent,
    password,
    ...(env.hostHeader ? { hostHeader: env.hostHeader } : {}),
  });
  const ctrl = new AbortController();
  const listener = new GiteaListener({
    agent: env.agent,
    state: store,
    baseUrl: env.giteaHost,
    token,
    auth,
    ...(env.hostHeader ? { hostHeader: env.hostHeader } : {}),
    onIngest: (n) => {
      log("info", `ingested ${n} events; waking dispatcher`);
      dispatcher.wake();
    },
  });

  const tasks: Promise<void>[] = [];
  tasks.push(dispatcher.runForever().catch((e) => log("error", "dispatcher exited", e)));
  tasks.push(
    listener.runPolling({ signal: ctrl.signal, onError: (e) => log("error", "listener err", e) })
      .catch((e) => log("error", "listener exited", e)),
  );
  tasks.push(retrySweeperLoop(env.agent, store, dispatcher, env.retrySweepMs, ctrl.signal, log).catch((e) => log("error", "retry sweeper exited", e)));

  let mmListener: MattermostListener | null = null;
  if (env.mattermostHost) {
    try {
      const mmToken = await fetchToken(env.secretServiceUrl, `${env.agent}-mm`, env.secretAuth);
      log("info", `mattermost token fetched len=${mmToken.length}`);
      mmListener = new MattermostListener({
        agent: env.agent,
        state: store,
        baseUrl: env.mattermostHost,
        token: mmToken,
        ...(env.mattermostHostHeader ? { hostHeader: env.mattermostHostHeader } : {}),
        onIngest: (n) => {
          log("info", `mattermost ingested ${n} events; waking dispatcher`);
          dispatcher.wake();
        },
        onError: (e) => log("warn", "mattermost listener err", e),
      });
      tasks.push(
        mmListener.run({ signal: ctrl.signal })
          .catch((e) => log("error", "mattermost listener exited", e)),
      );
    } catch (e) {
      log("warn", `mattermost listener disabled: ${(e as Error).message}`);
    }
  }

  const server = createServer(async (req, res) => {
    try {
      if (req.url === "/healthz") {
        // Health reflects the Gitea SSE connection, not model or turn progress.
        const sse = listener.sse;
        const ok = !!sse?.connected;
        res.statusCode = ok ? 200 : 503;
        res.end(JSON.stringify({ agent: env.agent, sse_connected: ok }));
        return;
      }
      res.statusCode = 404;
      res.end("not found");
    } catch (e) {
      res.statusCode = 500;
      res.end(String((e as Error).message));
    }
  });
  await new Promise<void>((resolve) => server.listen(env.listenPort, "0.0.0.0", () => resolve()));
  log("info", `http listening on :${env.listenPort}`);

  process.on("uncaughtException", (e) => {
    log("error", "uncaughtException", e);
    process.exit(1);
  });
  process.on("unhandledRejection", (e) => {
    log("error", "unhandledRejection", e);
    process.exit(1);
  });
  process.on("SIGTERM", () => {
    log("info", "SIGTERM received; shutting down");
    ctrl.abort();
    server.close();
    setTimeout(() => process.exit(0), 5000).unref();
  });

  await Promise.race(tasks);
  log("error", "a primary loop exited; this is fatal");
  process.exit(1);
}

async function retrySweeperLoop(
  agent: string,
  store: EventStore,
  dispatcher: Dispatcher,
  intervalMs: number,
  signal: AbortSignal,
  log: (lvl: string, msg: string, extra?: unknown) => void,
): Promise<void> {
  while (!signal.aborted) {
    try {
      const claimed = await store.claimRetryReady(agent);
      if (claimed.length > 0) {
        log("info", `retry sweep: ${claimed.length} events`);
        await dispatcher.dispatchSpecific(claimed);
      }
    } catch (e) {
      log("error", "retry sweep failed", e);
    }
    await sleep(intervalMs, signal);
  }
}

main().catch((e) => {
  console.error("[mini-router] fatal", e);
  process.exit(1);
});
