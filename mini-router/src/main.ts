/**
 * mini-router main — single-agent sidecar entrypoint (R7).
 *
 * Boot sequence (DESIGN_R7_SIDECAR §8):
 *   1. read env: AGENT_NAME, GITEA_HOST, MYSQL_DSN, SECRET_SERVICE_URL,
 *      SECRET_SERVICE_INTERNAL_AUTH, ACP_SOCKET_PATH, GITEA_PASSWORD_FILE
 *   2. fetch own token from secret-service
 *   3. connect MySQL (ensureSchema), recoverSendingToPending
 *   4. construct ACPSocketChannel(ACP_SOCKET_PATH)
 *   5. construct GiteaListener with PAT + form-cookie auth
 *   6. construct Dispatcher (onLog defaults to console.error — R7 fix)
 *   7. start SSE listener, dispatcher loop, retry sweeper, HTTP server
 *   8. install uncaughtException/unhandledRejection → log + exit(1)
 */
import { EventStore } from "./state.ts";
import { Dispatcher } from "./dispatcher.ts";
import { ACPSocketChannel } from "./acp_socket_channel.ts";
import { GiteaListener } from "./listeners/gitea/listener.ts";
import { GiteaFormAuth } from "./gitea_form_auth.ts";
import { MattermostListener } from "./listeners/mattermost/listener.ts";
import {
  createAcpSessionStore,
  parseAcpSessionNamespace,
  type AcpSessionNamespace,
} from "./session_namespace.ts";
import { BoardClient, parseBoardIds } from "./board_client.ts";
import { StepLoop } from "./step_loop.ts";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { readFileSync } from "node:fs";

interface Env {
  agent: string;
  giteaHost: string;
  hostHeader?: string;
  mysqlDsn: string;
  secretServiceUrl: string;
  secretAuth: string;
  acpSocketPath: string;
  sessionNamespace: AcpSessionNamespace;
  giteaPasswordFile?: string;
  metricsPort: number;
  retrySweepMs: number;
  // R8 mattermost:
  mattermostHost?: string;
  mattermostHostHeader?: string;
  // DeLM shared context (optional; absent → all board behavior disabled):
  boardServiceUrl?: string;
  boardIds: string[];
  boardWindowTokens?: number;
}

function readEnv(): Env {
  const agent = required("AGENT_NAME");
  return {
    agent,
    giteaHost: required("GITEA_HOST"),
    hostHeader: process.env.GITEA_HOST_HEADER,
    mysqlDsn: required("MYSQL_DSN"),
    secretServiceUrl: required("SECRET_SERVICE_URL"),
    secretAuth: required("SECRET_SERVICE_INTERNAL_AUTH"),
    acpSocketPath: process.env.ACP_SOCKET_PATH ?? "/var/run/acp/agent.sock",
    sessionNamespace: parseAcpSessionNamespace(process.env.ACP_SESSION_NAMESPACE),
    giteaPasswordFile:
      process.env.GITEA_PASSWORD_FILE ?? `/run/omcgitea/tokens/agent-${agent}.password`,
    metricsPort: Number(process.env.METRICS_PORT ?? "8645"),
    retrySweepMs: Number(process.env.RETRY_SWEEP_MS ?? "30000"),
    // mattermost is optional — if MATTERMOST_HOST is unset, listener won't start.
    ...(process.env.MATTERMOST_HOST ? { mattermostHost: process.env.MATTERMOST_HOST } : {}),
    ...(process.env.MATTERMOST_HOST_HEADER ? { mattermostHostHeader: process.env.MATTERMOST_HOST_HEADER } : {}),
    // DeLM shared context — optional. BOARD_SERVICE_URL unset (dev/prod and
    // the sweep_5 profiles) → BoardClient.enabled is false and dispatch is
    // byte-for-byte the pre-board behavior.
    ...(process.env.BOARD_SERVICE_URL ? { boardServiceUrl: process.env.BOARD_SERVICE_URL } : {}),
    boardIds: parseBoardIds(process.env.BOARD_IDS),
    ...(process.env.BOARD_WINDOW_TOKENS
      ? { boardWindowTokens: Number(process.env.BOARD_WINDOW_TOKENS) }
      : {}),
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

interface Metrics {
  events_pending: number;
  events_failed: number;
  events_sent: number;
  events_retrying: number;
  sse_connected: 0 | 1;
  sse_last_frame_age_seconds: number;
  retry_attempts_total: number;
  acp_reconnects_total: number;
  start_time_seconds: number;
}

async function main(): Promise<void> {
  const env = readEnv();
  const log = (lvl: string, msg: string, extra?: unknown) => {
    const t = new Date().toISOString();
    // eslint-disable-next-line no-console
    console.error(`[mini-router ${env.agent}] ${t} ${lvl} ${msg}`, extra ?? "");
  };
  log("info", `boot agent=${env.agent}`);

  // Step 1: fetch token via secret-service
  const token = await fetchToken(env.secretServiceUrl, env.agent, env.secretAuth);
  log("info", `token fetched len=${token.length}`);

  // Step 2: MySQL
  const store = new EventStore({ pool: { uri: env.mysqlDsn } });
  await store.ensureSchema();
  const recovered = await store.recoverSendingToPending(env.agent);
  if (recovered > 0) log("warn", `recovered ${recovered} stuck 'sending' rows → pending`);

  // Step 3: ACP socket channel.
  // sessionStore: persists ACP sessionId in MySQL agent_kv so that on
  // hermes-agent restart / router restart we call loadSession with the
  // last id (which keeps prompt cache hot + the agent's conversation
  // history attached). Without this, every reconnect starts a fresh
  // session and the agent loses every prior turn — see R10 fix
  // 2026-05-11.
  // R-stuck: ACP silence timeout. If the agent emits no ACP message
  // (no stopReason, no message_chunk, no usage_update) for this many
  // milliseconds while a prompt is in flight, force-close the connection
  // so prompt() rejects and the dispatcher can retry. The next prompt is
  // prepended with a notice telling the agent its last turn timed out.
  //
  // Default 0 (disabled) keeps current behaviour for all unset agents.
  // Set MINI_ROUTER_STUCK_MS=1200000 (20min) in compose env for agents
  // that should auto-recover. See v2notes/reviewer-4.5h-hang.md.
  const stuckMs = Number(process.env.MINI_ROUTER_STUCK_MS ?? "0") || undefined;
  // Read here (not at the dispatcher) because the channel needs to know
  // whether to open a fresh ACP session per prompt.
  const boardMode = (process.env.BOARD_MODE ?? "batch").toLowerCase();
  const channel = new ACPSocketChannel({
    socketPath: env.acpSocketPath,
    cwd: "/work",
    onLog: (lvl, msg, err) => log(`acp.${lvl}`, msg, err),
    sessionStore: createAcpSessionStore(
      store,
      env.agent,
      env.sessionNamespace,
    ),
    stuckMs,
    freshSessionPerPrompt: boardMode === "steploop",
  });

  // Step 4: dispatcher (onLog DEFAULTS to console.error per R7 fix)
  let retryAttemptsTotal = 0;
  // DeLM shared context: forced read (board spliced into every prompt) +
  // forced write (nudge when a turn publishes nothing). Disabled unless
  // BOARD_SERVICE_URL and BOARD_IDS are both set.
  const board = new BoardClient({
    ...(env.boardServiceUrl ? { baseUrl: env.boardServiceUrl } : {}),
    agent: env.agent,
    boardIds: env.boardIds,
    ...(process.env.BOARD_QUEUE_ID ? { queueId: process.env.BOARD_QUEUE_ID } : {}),
    ...(env.boardWindowTokens ? { windowTokens: env.boardWindowTokens } : {}),
    ...(process.env.BOARD_RENDER_MODE ? { renderMode: process.env.BOARD_RENDER_MODE } : {}),
    // The render-mode matrix is role-dependent. Anything that leads — the
    // director, a team lead, a DeLM planner — reads as a planner; everyone
    // else is an implementer. Overridable with BOARD_ROLE.
    role:
      process.env.BOARD_ROLE ??
      (/(^|-)(director|lead|planner)(-|$)/.test(env.agent) ? "planner" : "implementer"),
    log: (lvl, msg, err) => log(lvl, `[board] ${msg}`, err),
  });
  if (board.enabled) {
    log(
      "info",
      `shared context ON: url=${env.boardServiceUrl} boards=${env.boardIds.join(",")}` +
        ` mode=${process.env.BOARD_RENDER_MODE ?? "(service default)"}`,
    );
  }

  const dispatcher = new Dispatcher({
    agent: env.agent,
    state: store,
    channel,
    board,
    // Off by default; set PBENCH_REINJECT_AFTER_COMPACTION=1 to re-enable.
    reinjectAfterCompaction: process.env.PBENCH_REINJECT_AFTER_COMPACTION === "1",
    onLog: (e) => log(e.level, e.msg, e.err),
  });

  // Step 5: GiteaListener (PAT for REST + form-cookie for SSE)
  const password = readPassword(env.giteaPasswordFile!);
  const auth = new GiteaFormAuth({
    baseUrl: env.giteaHost,
    username: env.agent,
    password,
    ...(env.hostHeader ? { hostHeader: env.hostHeader } : {}),
  });
  const ctrl = new AbortController();
  const listener = new GiteaListener({
    agent: env.agent,
    state: store as unknown as never, // structural compat (state has same async signatures)
    baseUrl: env.giteaHost,
    token,
    auth,
    ...(env.hostHeader ? { hostHeader: env.hostHeader } : {}),
    onIngest: (n) => {
      log("info", `ingested ${n} events; waking dispatcher`);
      dispatcher.wake();
    },
  });

  // Step 6: kick off all loops
  const tasks: Promise<void>[] = [];
  // BOARD_MODE selects how the agent is driven:
  //   batch    (default) — copilot owns its session; the board rides along with
  //                        each dispatched UEM batch. Keeps prompt caching.
  //   steploop           — the router owns the loop DeLM-style: one freshly
  //                        built prompt per step against a fresh session, with
  //                        the board spliced in every time. Costs caching.
  // Anything else falls back to batch, so a typo cannot silently disable the
  // agent.
  if (boardMode === "steploop") {
    const task = process.env.STEP_LOOP_TASK
      ?? "Work on the task described in /work (see AGENTS.md and the seeded README).";
    const maxSteps = Number(process.env.STEP_LOOP_MAX_STEPS ?? "50");
    const hours = Number(process.env.STEP_LOOP_HOURS ?? "0");
    const deadlineMs = hours > 0 ? Date.now() + hours * 3600_000 : undefined;
    log("info", `BOARD_MODE=steploop maxSteps=${maxSteps}${hours ? ` hours=${hours}` : ""}`);
    const loop = new StepLoop({
      agent: env.agent,
      channel,
      board,
      task,
      ...(process.env.BOARD_QUEUE_ID ? { queueId: process.env.BOARD_QUEUE_ID } : {}),
      maxSteps,
      ...(deadlineMs ? { deadlineMs } : {}),
      noProgressLimit: Number(process.env.STEP_LOOP_NO_PROGRESS_LIMIT ?? "8"),
      strategyPrior: (process.env.STEP_LOOP_STRATEGY_PRIOR ?? "1") !== "0",
      // Only set where the router can actually see the agent's workspace (the
      // DeLM profiles share /work as a host bind mount). Unset elsewhere, and
      // the checkpoints stay silent rather than guessing.
      ...(process.env.STEP_LOOP_WORKSPACE
        ? { workspacePath: process.env.STEP_LOOP_WORKSPACE }
        : {}),
      log: (lvl, msg, err) => log(lvl, `[steploop] ${msg}`, err),
    });
    tasks.push(
      loop.run(ctrl.signal)
        .then((r) => log("info", `[steploop] finished after ${r.steps} step(s): ${r.reason}`))
        .catch((e) => log("error", "steploop exited", e)),
    );
  } else {
    tasks.push(dispatcher.runForever().catch((e) => log("error", "dispatcher exited", e)));
  }
  tasks.push(
    listener.runPolling({ signal: ctrl.signal, onError: (e) => log("error", "listener err", e) })
      .catch((e) => log("error", "listener exited", e)),
  );
  tasks.push(retrySweeperLoop(env.agent, store, dispatcher, env.retrySweepMs, ctrl.signal, log,
    () => retryAttemptsTotal++).catch((e) => log("error", "retry sweeper exited", e)));

  // Step 6b (R8): mattermost listener (optional — only if MATTERMOST_HOST set)
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

  // Step 7: HTTP server (/healthz /metrics)
  const server = createServer(async (req, res) => {
    try {
      if (req.url === "/healthz") {
        const sse = listener.sse;
        const ok = !!sse?.connected;
        res.statusCode = ok ? 200 : 503;
        res.end(JSON.stringify({ agent: env.agent, sse_connected: ok }));
        return;
      }
      if (req.url === "/metrics") {
        const m = await collectMetrics(env, store, listener, retryAttemptsTotal);
        res.statusCode = 200;
        res.setHeader("content-type", "text/plain; version=0.0.4");
        res.end(renderMetrics(env.agent, m));
        return;
      }
      res.statusCode = 404;
      res.end("not found");
    } catch (e) {
      res.statusCode = 500;
      res.end(String((e as Error).message));
    }
  });
  await new Promise<void>((resolve) => server.listen(env.metricsPort, "0.0.0.0", () => resolve()));
  log("info", `http listening on :${env.metricsPort}`);

  // Step 8: process-level safety net
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
  onAttempt: () => void,
): Promise<void> {
  while (!signal.aborted) {
    try {
      const claimed = await store.claimRetryReady(agent);
      if (claimed.length > 0) {
        log("info", `retry sweep: ${claimed.length} events`);
        onAttempt();
        await dispatcher.dispatchSpecific(claimed);
      }
    } catch (e) {
      log("error", "retry sweep failed", e);
    }
    await sleepWithSignal(intervalMs, signal);
  }
}

function sleepWithSignal(ms: number, signal: AbortSignal): Promise<void> {
  // R10.1 fix: previously installed `addEventListener("abort", …, {once:true})`
  // and never removed it on the timeout path. retrySweeperLoop calls this
  // every 30s, so over ~12h a long-running router accumulated 1500+ abort
  // listeners and node printed MaxListenersExceededWarning. Track + remove.
  return new Promise((resolve) => {
    const onAbort = () => {
      clearTimeout(t);
      signal.removeEventListener("abort", onAbort);
      resolve();
    };
    const t = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

async function collectMetrics(
  env: Env,
  store: EventStore,
  listener: GiteaListener,
  retryAttempts: number,
): Promise<Metrics> {
  // counts via state-aggregation queries
  const pool = (store as unknown as { pool: { query: (sql: string, p: unknown[]) => Promise<[Array<{ state: string; n: number }>, unknown]> } }).pool;
  let counts: Record<string, number> = {};
  try {
    const [rows] = await pool.query(
      `SELECT state, COUNT(*) AS n FROM events WHERE agent = ? GROUP BY state`,
      [env.agent],
    );
    for (const r of rows) counts[r.state] = Number(r.n);
  } catch { /* */ }
  const sse = listener.sse;
  const lastFrameAt = sse?.lastFrameAt ?? 0;
  const ageSec = lastFrameAt > 0 ? (Date.now() - lastFrameAt) / 1000 : -1;
  return {
    events_pending: counts.pending ?? 0,
    events_failed: counts.failed ?? 0,
    events_sent: counts.sent ?? 0,
    events_retrying: counts.retrying ?? 0,
    sse_connected: sse?.connected ? 1 : 0,
    sse_last_frame_age_seconds: ageSec,
    retry_attempts_total: retryAttempts,
    acp_reconnects_total: 0,
    start_time_seconds: 0,
  };
}

function renderMetrics(agent: string, m: Metrics): string {
  const l = `agent="${agent}"`;
  return [
    `# HELP mini_router_events_pending Pending events for this agent`,
    `# TYPE mini_router_events_pending gauge`,
    `mini_router_events_pending{${l}} ${m.events_pending}`,
    `# HELP mini_router_events_failed Failed events for this agent`,
    `# TYPE mini_router_events_failed gauge`,
    `mini_router_events_failed{${l}} ${m.events_failed}`,
    `# HELP mini_router_events_sent Sent events`,
    `# TYPE mini_router_events_sent gauge`,
    `mini_router_events_sent{${l}} ${m.events_sent}`,
    `# HELP mini_router_events_retrying Retrying events`,
    `# TYPE mini_router_events_retrying gauge`,
    `mini_router_events_retrying{${l}} ${m.events_retrying}`,
    `# HELP mini_router_sse_connected 1 if SSE has an open connection`,
    `# TYPE mini_router_sse_connected gauge`,
    `mini_router_sse_connected{${l}} ${m.sse_connected}`,
    `# HELP mini_router_sse_last_frame_age_seconds Seconds since last SSE frame`,
    `# TYPE mini_router_sse_last_frame_age_seconds gauge`,
    `mini_router_sse_last_frame_age_seconds{${l}} ${m.sse_last_frame_age_seconds}`,
    `# HELP mini_router_retry_attempts_total Cumulative retry sweep attempts`,
    `# TYPE mini_router_retry_attempts_total counter`,
    `mini_router_retry_attempts_total{${l}} ${m.retry_attempts_total}`,
    ``,
  ].join("\n");
}

main().catch((e) => {
  // eslint-disable-next-line no-console
  console.error("[mini-router] fatal", e);
  process.exit(1);
});
