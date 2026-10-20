/**
 * mini-router state — MySQL-backed events store.
 *
 * Mini-router runs one process per agent. A single shared MySQL holds
 * `events` rows for ALL agents; row-level isolation via `agent` column
 * means a sidecar only ever WHEREs `agent = $self`.
 */
import { createPool, type Pool, type RowDataPacket, type ResultSetHeader } from "mysql2/promise";
import { GROUP_CHAT_SQL } from "./group_messages.ts";

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
  payload: UEMLike;
}

/** Backoff schedule, indexed by attempts-1 (1-based).
 * This ladder re-delivers a batch after a turn fails or is killed. MAX_ATTEMPTS
 * deliveries use MAX_ATTEMPTS-1 rungs, so the whole span is ~2.6 min (the
 * sweeper's 30 s poll rounds the first two rungs up). */
export const RETRY_BACKOFF_MS: readonly number[] = [
  1_000,
  5_000,
  30_000,
  120_000,
];
export const MAX_ATTEMPTS = 5;

export const MARK_BATCH_SENT_SQL = `UPDATE events FORCE INDEX (ix_batch_state)
  SET state='sent', sent_at = ?
  WHERE batch_id = ? AND state = 'sending'`;

export class EventStore {
  private pool: Pool;

  constructor(uri: string) {
    this.pool = createPool({ uri, connectionLimit: 4 });
  }

  async ensureSchema(): Promise<void> {
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
         last_error TEXT NULL,
         batch_id CHAR(36) NULL,
         next_retry_at BIGINT NULL,
         UNIQUE KEY uk_dedup_agent (dedup_key, agent),
         KEY ix_agent_state_id (agent, state, id),
         KEY ix_state_retry (state, next_retry_at),
         KEY ix_batch_state (batch_id, state)
       ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`,
      `CREATE TABLE IF NOT EXISTS cursors (
         agent VARCHAR(128) NOT NULL,
         source VARCHAR(64) NOT NULL,
         \`cursor\` VARCHAR(255) NOT NULL,
         PRIMARY KEY (agent, source)
       ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`,
      // Persist the Copilot ACP session under acp_session_id:copilot so a
      // router restart can restore the conversation.
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

    // CREATE TABLE IF NOT EXISTS does not upgrade an existing database. Most
    // sidecars will see the index and return immediately; on an old schema the
    // advisory lock serializes the one ALTER across all concurrently starting
    // sidecars.
    const batchIndexSql = `SELECT COLUMN_NAME AS column_name
      FROM information_schema.STATISTICS
      WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'events'
        AND INDEX_NAME = 'ix_batch_state'
      ORDER BY SEQ_IN_INDEX`;
    const expectedBatchIndex = "batch_id,state";
    const columns = (rows: RowDataPacket[]) =>
      rows.map((row) => String(row.column_name)).join(",");
    const [existingRows] = await this.pool.query<RowDataPacket[]>(batchIndexSql);
    const existingColumns = columns(existingRows);
    if (existingColumns && existingColumns !== expectedBatchIndex) {
      throw new Error(`events.ix_batch_state has unexpected columns: ${existingColumns}`);
    }
    if (!existingColumns) {
      const conn = await this.pool.getConnection();
      let locked = false;
      try {
        const [lockRows] = await conn.query<RowDataPacket[]>(
          "SELECT GET_LOCK('omcgitea.events.ix_batch_state', 120) AS acquired",
        );
        locked = Number(lockRows[0]?.acquired) === 1;
        if (!locked) throw new Error("timed out waiting to upgrade events.ix_batch_state");

        const [recheckRows] = await conn.query<RowDataPacket[]>(batchIndexSql);
        const recheckColumns = columns(recheckRows);
        if (recheckColumns && recheckColumns !== expectedBatchIndex) {
          throw new Error(`events.ix_batch_state has unexpected columns: ${recheckColumns}`);
        }
        if (!recheckColumns) {
          await conn.query("ALTER TABLE events ADD KEY ix_batch_state (batch_id, state)");
        }
      } finally {
        if (locked) {
          await conn.query("SELECT RELEASE_LOCK('omcgitea.events.ix_batch_state')").catch(() => undefined);
        }
        conn.release();
      }
    }
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

  /** FIFO for other events, plus the complete file-backed group-chat backlog. */
  async nextPendingBatch(agent: string, limit: number): Promise<EventRow[]> {
    const cap = Math.max(1, Math.min(1000, Math.floor(limit)));
    const [[rows], [messages]] = await Promise.all([
      this.pool.query<RowDataPacket[]>(
        `SELECT id, payload FROM events WHERE agent = ? AND state = 'pending' AND NOT ${GROUP_CHAT_SQL}
           ORDER BY id ASC LIMIT ${cap}`, [agent]),
      this.pool.query<RowDataPacket[]>(
        `SELECT id, payload FROM events WHERE agent = ? AND state = 'pending' AND ${GROUP_CHAT_SQL}
           ORDER BY id ASC`, [agent]),
    ]);
    return [...rows, ...messages].map(toEventRow).sort((a, b) => a.id - b.id);
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
  async markBatchSent(batchId: string, now: number = Date.now()): Promise<void> {
    await this.pool.query(
      MARK_BATCH_SENT_SQL,
      [now, batchId],
    );
  }

  /**
   * Retire rows mcp-notice-shim already rendered into a tool result.
   *
   * The shim appends pending DM notices to an MCP tool result mid-turn
   * and reports what it showed into board-service's `shown` table. Those rows
   * are already in the agent's context, so re-delivering them at the turn
   * boundary would duplicate them. This is the only place that reconciles the
   * two paths, and it lives here rather than in board-service because the
   * ROUTER must stay the only writer to `events` (dispatchBatch guards a claim
   * on `claimed === 0` without filtering the batch, so a partial CAS loss from
   * an outside writer double-delivers silently).
   *
   * `AND state='pending'` is the CAS: a row already claimed into 'sending' by
   * dispatchBatch belongs to that batch and is left alone.
   *
   * Fails OPEN. `shown` is created by board-service, so on a stack where that
   * has not run yet the query throws; returning an empty set means "nothing was
   * pre-shown", i.e. deliver normally. Losing a de-dup costs one duplicate
   * notice; throwing here would stall the whole batch.
   */
  async claimShown(agent: string, ids: number[], now: number = Date.now()): Promise<Set<number>> {
    const out = new Set<number>();
    if (ids.length === 0) return out;
    const placeholders = ids.map(() => "?").join(",");
    try {
      const [rows] = await this.pool.query<RowDataPacket[]>(
        `SELECT event_id FROM shown WHERE agent = ? AND event_id IN (${placeholders})`,
        [agent, ...ids],
      );
      const candidates = rows.map((r) => Number(r.event_id));
      if (candidates.length === 0) return out;
      const ph2 = candidates.map(() => "?").join(",");
      await this.pool.query<ResultSetHeader>(
        `UPDATE events
           SET state='sent', sent_at = ?
         WHERE id IN (${ph2}) AND state = 'pending'`,
        [now, ...candidates],
      );
      for (const id of candidates) out.add(id);
    } catch {
      return new Set<number>();
    }
    return out;
  }

  /**
   * Mark a single row as failed. Computes next_retry_at from RETRY_BACKOFF_MS.
   * `attempts` is read fresh inside the UPDATE; if attempts+1 >= MAX_ATTEMPTS
   * the row becomes terminal (next_retry_at = NULL) and won't be reclaimed.
   *
   */
  async markFailed(
    id: number,
    err: string,
    now: number = Date.now(),
  ): Promise<void> {
    // Read attempts then update — safer/clearer than encoding the backoff
    // table inside SQL CASE. There is no other writer to a single row's
    // attempts in normal operation; if there is, the worst case is a
    // slightly stale next_retry_at, which sweeper will still pick up.
    const [rows] = await this.pool.query<RowDataPacket[]>(
      `SELECT attempts FROM events WHERE id = ?`,
      [id],
    );
    if (rows.length === 0) return;
    // markBatchSending already did `attempts = attempts + 1` for this delivery.
    // Adding another here would burn two attempts per try: with MAX_ATTEMPTS=5
    // an event would die after three deliveries, not five.
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
  }

  /**
   * Atomically claim retry-ready rows for one agent. Transitions
   * (failed|retrying) AND attempts < MAX_ATTEMPTS AND next_retry_at <= now
   * → 'retrying'.
   *
   * 'retrying' is picked up again because a claimed row stays there if the
   * router dies, or markBatchSending throws, before the dispatch; nothing else
   * ever moves it on. Re-claiming cannot double-deliver: the router's one
   * sweeper awaits each dispatch before it claims again, and markBatchSending's
   * CAS lets only one batch take a row to 'sending'.
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
      const where = `agent = ? AND state IN ('failed','retrying')
             AND attempts < ? AND next_retry_at IS NOT NULL AND next_retry_at <= ?`;
      const params = [agent, MAX_ATTEMPTS, now];
      const [others] = await conn.query<RowDataPacket[]>(
        `SELECT id FROM events
           WHERE ${where} AND NOT ${GROUP_CHAT_SQL}
           ORDER BY next_retry_at ASC, id ASC
           LIMIT ${cap}
           FOR UPDATE`,
        params,
      );
      const [messages] = await conn.query<RowDataPacket[]>(
        `SELECT id FROM events WHERE ${where} AND ${GROUP_CHAT_SQL} ORDER BY id ASC FOR UPDATE`, params,
      );
      const picks = [...others, ...messages];
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
        `SELECT id, payload FROM events WHERE id IN (${placeholders}) ORDER BY id ASC`,
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
   * Generic per-agent K/V. ACP session IDs are stored under
   * `acp_session_id:copilot` so router restarts can restore the same ACP session.
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

}


function toEventRow(r: RowDataPacket): EventRow {
  // mysql2 returns JSON columns as already-parsed objects.
  const payload =
    typeof r.payload === "string"
      ? (JSON.parse(r.payload) as UEMLike)
      : (r.payload as UEMLike);
  return {
    id: Number(r.id),
    payload,
  };
}
