/**
 * mini-router state — MySQL-backed events store (R7 sidecar).
 *
 * Replaces the SQLite RouterState in router/src/state.ts. Self-contained:
 * has no imports from router/. See v2docs/DESIGN_R7_SIDECAR.md §5/§6/§8.
 *
 * Mini-router runs one process per agent. A single shared MySQL holds
 * `events` rows for ALL agents; row-level isolation via `agent` column
 * means a sidecar only ever WHEREs `agent = $self`.
 */
import { createPool, type Pool, type PoolOptions, type RowDataPacket, type ResultSetHeader } from "mysql2/promise";
import { randomUUID } from "node:crypto";

export type EventState =
  | "pending"
  | "sending"
  | "sent"
  | "failed"
  | "retrying";

/**
 * UEM-shaped payload (kept structural to avoid pulling in router/src
 * types). Mini-router doesn't validate the shape — Gitea listener does.
 */
export interface UEMLike {
  event_id: string;
  source: string;
  target_agent: string;
  [k: string]: unknown;
}

export interface EventRow {
  id: number;
  dedup_key: string;
  source: string;
  agent: string;
  payload: UEMLike;
  state: EventState;
  attempts: number;
  created_at: number;
  sent_at: number | null;
  acked_at: number | null;
  last_error: string | null;
  batch_id: string | null;
  next_retry_at: number | null;
}

/** Backoff schedule per DESIGN_R7_SIDECAR §6: indexed by attempts-1 (1-based). */
export const RETRY_BACKOFF_MS: readonly number[] = [
  1_000,
  5_000,
  30_000,
  120_000,
  600_000,
];
export const MAX_ATTEMPTS = 5;

export interface EventStoreOptions {
  /** mysql2 pool config (uri or fields). */
  pool: PoolOptions | { uri: string };
  /** Optional: skip ensureSchema() — for prod where DBA owns DDL. */
  skipSchema?: boolean;
}

export class EventStore {
  private pool: Pool;
  private schemaReady = false;

  constructor(opts: EventStoreOptions) {
    this.pool = createPool(
      "uri" in opts.pool
        ? { uri: opts.pool.uri, connectionLimit: 4 }
        : { ...opts.pool, connectionLimit: opts.pool.connectionLimit ?? 4 },
    );
  }

  async ensureSchema(): Promise<void> {
    if (this.schemaReady) return;
    const ddl = [
      `CREATE TABLE IF NOT EXISTS events (
         id BIGINT PRIMARY KEY AUTO_INCREMENT,
         dedup_key VARCHAR(255) NOT NULL,
         source VARCHAR(64) NOT NULL,
         agent VARCHAR(128) NOT NULL,
         payload JSON NOT NULL,
         state ENUM('pending','sending','sent','failed','retrying') NOT NULL DEFAULT 'pending',
         attempts INT NOT NULL DEFAULT 0,
         created_at BIGINT NOT NULL,
         sent_at BIGINT NULL,
         acked_at BIGINT NULL,
         last_error TEXT NULL,
         batch_id CHAR(36) NULL,
         next_retry_at BIGINT NULL,
         UNIQUE KEY uk_dedup_agent (dedup_key, agent),
         KEY ix_agent_state_id (agent, state, id),
         KEY ix_state_retry (state, next_retry_at)
       ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`,
      `CREATE TABLE IF NOT EXISTS cursors (
         agent VARCHAR(128) NOT NULL,
         source VARCHAR(64) NOT NULL,
         \`cursor\` VARCHAR(255) NOT NULL,
         PRIMARY KEY (agent, source)
       ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`,
      // R10 (session persistence) — small generic per-agent K/V store.
      // ACP session IDs use `acp_session_id:<runtime>` so switching between
      // Claude/Copilot/Hermes cannot overwrite another runtime's resumable
      // session. Generic on purpose so future small bits of cross-restart
      // state don't need new DDL.
      `CREATE TABLE IF NOT EXISTS agent_kv (
         agent VARCHAR(128) NOT NULL,
         k VARCHAR(128) NOT NULL,
         v TEXT NOT NULL,
         updated_at BIGINT NOT NULL,
         PRIMARY KEY (agent, k)
       ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`,
    ];
    for (const stmt of ddl) {
      await this.pool.query(stmt);
    }
    this.schemaReady = true;
  }

  /**
   * Insert UEM as `pending`. Returns inserted row id, or null if a row
   * with (dedup_key, agent) already exists. (idempotency hinge).
   */
  async ingest(uem: UEMLike, now: number = Date.now()): Promise<number | null> {
    const [r] = await this.pool.query<ResultSetHeader>(
      `INSERT INTO events
         (dedup_key, source, agent, payload, state, attempts, created_at)
       VALUES (?, ?, ?, CAST(? AS JSON), 'pending', 0, ?)
       ON DUPLICATE KEY UPDATE id = id`,
      [uem.event_id, uem.source, uem.target_agent, JSON.stringify(uem), now],
    );
    // mysql2: ON DUPLICATE KEY with id=id → affectedRows=1 but insertId=0
    // for the dup case (no actual insert). For real insert, insertId>0.
    if (r.affectedRows === 1 && r.insertId > 0) return Number(r.insertId);
    return null;
  }

  /** Oldest pending events for an agent in FIFO order. Never crosses agents. */
  async nextPendingBatch(agent: string, limit: number): Promise<EventRow[]> {
    const cap = Math.max(1, Math.min(1000, Math.floor(limit)));
    const [rows] = await this.pool.query<RowDataPacket[]>(
      `SELECT * FROM events
         WHERE agent = ? AND state = 'pending'
         ORDER BY id ASC
         LIMIT ${cap}`,
      [agent],
    );
    return rows.map(toEventRow);
  }

  /**
   * pending → sending; tag batch_id; bump attempts. Returns # rows actually
   * transitioned (CAS-protected so concurrent dispatchers don't double-claim).
   */
  async markBatchSending(ids: number[], batchId: string): Promise<number> {
    if (ids.length === 0) return 0;
    const placeholders = ids.map(() => "?").join(",");
    const [r] = await this.pool.query<ResultSetHeader>(
      `UPDATE events
         SET state='sending',
             attempts = attempts + 1,
             last_error = NULL,
             batch_id = ?
       WHERE id IN (${placeholders}) AND state IN ('pending','retrying')`,
      [batchId, ...ids],
    );
    return r.affectedRows;
  }

  /** sending → sent; stamp sent_at. */
  async markBatchSent(batchId: string, now: number = Date.now()): Promise<number> {
    const [r] = await this.pool.query<ResultSetHeader>(
      `UPDATE events
         SET state='sent', sent_at = ?
       WHERE batch_id = ? AND state = 'sending'`,
      [now, batchId],
    );
    return r.affectedRows;
  }

  /**
   * Mark a single row as failed. Computes next_retry_at via §6 backoff.
   * `attempts` is read fresh inside the UPDATE; if attempts+1 >= MAX_ATTEMPTS
   * the row becomes terminal (next_retry_at = NULL) and won't be reclaimed.
   *
   * Returns the post-update {attempts, next_retry_at} for caller's metric/log.
   */
  async markFailed(
    id: number,
    err: string,
    now: number = Date.now(),
  ): Promise<{ attempts: number; next_retry_at: number | null } | null> {
    // Read attempts then update — safer/clearer than encoding the backoff
    // table inside SQL CASE. There is no other writer to a single row's
    // attempts in normal operation; if there is, the worst case is a
    // slightly stale next_retry_at, which sweeper will still pick up.
    const [rows] = await this.pool.query<RowDataPacket[]>(
      `SELECT attempts FROM events WHERE id = ?`,
      [id],
    );
    if (rows.length === 0) return null;
    // markBatchSending already did `attempts = attempts + 1` for this delivery.
    // Adding another here burned two attempts per try: with MAX_ATTEMPTS=5 an
    // event died after THREE deliveries, not five, and the ladder only ever used
    // rungs [1] and [3] (5s, 120s) -- 1s, 30s and 600s were unreachable.
    const newAttempts = Number(rows[0]!.attempts);
    const next =
      newAttempts >= MAX_ATTEMPTS
        ? null
        : now + RETRY_BACKOFF_MS[newAttempts - 1]!;
    // Guard on state='sending'. markBatchSent runs INSIDE the dispatcher's try
    // block, so a MySQL blip on that UPDATE -- after the batch was already
    // delivered to the agent -- flipped up to 32 'sent' rows back to 'failed',
    // and the sweeper redelivered every one of them.
    await this.pool.query(
      `UPDATE events
         SET state='failed',
             attempts = ?,
             last_error = ?,
             next_retry_at = ?
       WHERE id = ? AND state = 'sending'`,
      [newAttempts, err, next, id],
    );
    return { attempts: newAttempts, next_retry_at: next };
  }

  /**
   * Atomically claim retry-ready rows for one agent. Transitions
   * (failed|retrying) AND attempts < MAX_ATTEMPTS AND next_retry_at <= now
   * → 'retrying'. The UPDATE-then-SELECT (within a tx with FOR UPDATE)
   * pattern prevents double-claim under concurrent sweepers.
   *
   * Concurrency proof: SELECT … FOR UPDATE locks candidate rows; a
   * concurrent sweeper either waits or sees state='retrying' (locked-out
   * by the WHERE clause).
   */
  async claimRetryReady(
    agent: string,
    now: number = Date.now(),
    limit: number = 16,
  ): Promise<EventRow[]> {
    const cap = Math.max(1, Math.min(1000, Math.floor(limit)));
    const conn = await this.pool.getConnection();
    try {
      await conn.beginTransaction();
      const [picks] = await conn.query<RowDataPacket[]>(
        `SELECT id FROM events
           WHERE agent = ?
             AND state = 'failed'
             AND attempts < ?
             AND next_retry_at IS NOT NULL
             AND next_retry_at <= ?
           ORDER BY next_retry_at ASC, id ASC
           LIMIT ${cap}
           FOR UPDATE`,
        [agent, MAX_ATTEMPTS, now],
      );
      if (picks.length === 0) {
        await conn.commit();
        return [];
      }
      const ids = picks.map((r) => Number(r.id));
      const placeholders = ids.map(() => "?").join(",");
      await conn.query(
        `UPDATE events SET state='retrying'
           WHERE id IN (${placeholders})`,
        ids,
      );
      const [rows] = await conn.query<RowDataPacket[]>(
        `SELECT * FROM events WHERE id IN (${placeholders}) ORDER BY id ASC`,
        ids,
      );
      await conn.commit();
      return rows.map(toEventRow);
    } catch (e) {
      await conn.rollback();
      throw e;
    } finally {
      conn.release();
    }
  }

  /** Boot-time scrub: revive `sending` (left over from a kill -9). */
  async recoverSendingToPending(agent: string): Promise<number> {
    const [r] = await this.pool.query<ResultSetHeader>(
      `UPDATE events
         SET state='pending',
             last_error = COALESCE(last_error, 'recovered from sending on boot')
       WHERE agent = ? AND state = 'sending'`,
      [agent],
    );
    return r.affectedRows;
  }

  async getCursor(agent: string, source: string): Promise<string | null> {
    const [rows] = await this.pool.query<RowDataPacket[]>(
      "SELECT `cursor` FROM cursors WHERE agent = ? AND source = ?",
      [agent, source],
    );
    if (rows.length === 0) return null;
    return String(rows[0]!.cursor);
  }

  async setCursor(agent: string, source: string, cursor: string): Promise<void> {
    await this.pool.query(
      "INSERT INTO cursors (agent, source, `cursor`) VALUES (?, ?, ?) " +
        "ON DUPLICATE KEY UPDATE `cursor` = VALUES(`cursor`)",
      [agent, source, cursor],
    );
  }

  /**
   * Generic per-agent K/V (R10). ACP session IDs are stored under
   * `acp_session_id:<runtime>` so router/runtime restarts can call
   * loadSession without cross-kind collisions. See session_namespace.ts,
   * main.ts wiring, and acp_socket_channel.ts loadSession branch.
   */
  async getKv(agent: string, key: string): Promise<string | null> {
    const [rows] = await this.pool.query<RowDataPacket[]>(
      "SELECT v FROM agent_kv WHERE agent = ? AND k = ?",
      [agent, key],
    );
    if (rows.length === 0) return null;
    return String(rows[0]!.v);
  }

  async setKv(agent: string, key: string, value: string, now: number = Date.now()): Promise<void> {
    await this.pool.query(
      "INSERT INTO agent_kv (agent, k, v, updated_at) VALUES (?, ?, ?, ?) " +
        "ON DUPLICATE KEY UPDATE v = VALUES(v), updated_at = VALUES(updated_at)",
      [agent, key, value, now],
    );
  }

  async deleteKv(agent: string, key: string): Promise<void> {
    await this.pool.query("DELETE FROM agent_kv WHERE agent = ? AND k = ?", [agent, key]);
  }

  /** Test helper: fetch one row by id (cross-agent). */
  async _getById(id: number): Promise<EventRow | null> {
    const [rows] = await this.pool.query<RowDataPacket[]>(
      `SELECT * FROM events WHERE id = ?`,
      [id],
    );
    return rows.length === 0 ? null : toEventRow(rows[0]!);
  }

  async close(): Promise<void> {
    await this.pool.end();
  }
}

export function newBatchId(): string {
  return randomUUID();
}

function toEventRow(r: RowDataPacket): EventRow {
  // mysql2 returns JSON columns as already-parsed objects.
  const payload =
    typeof r.payload === "string"
      ? (JSON.parse(r.payload) as UEMLike)
      : (r.payload as UEMLike);
  return {
    id: Number(r.id),
    dedup_key: String(r.dedup_key),
    source: String(r.source),
    agent: String(r.agent),
    payload,
    state: String(r.state) as EventState,
    attempts: Number(r.attempts),
    created_at: Number(r.created_at),
    sent_at: r.sent_at == null ? null : Number(r.sent_at),
    acked_at: r.acked_at == null ? null : Number(r.acked_at),
    last_error: r.last_error == null ? null : String(r.last_error),
    batch_id: r.batch_id == null ? null : String(r.batch_id),
    next_retry_at: r.next_retry_at == null ? null : Number(r.next_retry_at),
  };
}
