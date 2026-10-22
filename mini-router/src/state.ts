/**
 * Store per-worker events, source cursors and ACP session IDs in shared MySQL.
 * Events move pending -> sending -> sent, with bounded retries after failures.
 */
import { createPool, type Pool, type RowDataPacket, type ResultSetHeader } from "mysql2/promise";
import { GROUP_CHAT_SQL } from "./group_messages.ts";

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

    // All routers may start together; serialize the index upgrade with a DB lock.
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

  async ingest(uem: UEMLike, now: number = Date.now()): Promise<number | null> {
    // The unique event/agent key absorbs repeated live events and catch-up results.
    const [r] = await this.pool.query<ResultSetHeader>(
      `INSERT INTO events
         (dedup_key, source, agent, payload, state, attempts, created_at)
       VALUES (?, ?, ?, CAST(? AS JSON), 'pending', 0, ?)
       ON DUPLICATE KEY UPDATE id = id`,
      [uem.event_id, uem.source, uem.target_agent, JSON.stringify(uem), now],
    );
    if (r.affectedRows === 1 && r.insertId > 0) return Number(r.insertId);
    return null;
  }

  async nextPendingBatch(agent: string, limit: number): Promise<EventRow[]> {
    // Drain all group messages so the file backlog includes every queued message.
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

  async markBatchSent(batchId: string, now: number = Date.now()): Promise<void> {
    await this.pool.query(
      MARK_BATCH_SENT_SQL,
      [now, batchId],
    );
  }

  async claimShown(agent: string, ids: number[], now: number = Date.now()): Promise<Set<number>> {
    // The board service writes this ledger after the shim emits a notice.
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

  async markFailed(
    id: number,
    err: string,
    now: number = Date.now(),
  ): Promise<void> {
    const [rows] = await this.pool.query<RowDataPacket[]>(
      `SELECT attempts FROM events WHERE id = ?`,
      [id],
    );
    if (rows.length === 0) return;
    // Attempts are incremented when claimed for sending, before the ACP call.
    const newAttempts = Number(rows[0]!.attempts);
    const next =
      newAttempts >= MAX_ATTEMPTS
        ? null
        : now + RETRY_BACKOFF_MS[newAttempts - 1]!;
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

  async claimRetryReady(
    agent: string,
    now: number = Date.now(),
    limit: number = 16,
  ): Promise<EventRow[]> {
    const cap = Math.max(1, Math.min(1000, Math.floor(limit)));
    const conn = await this.pool.getConnection();
    try {
      // Lock the chosen rows until their retry claim and payload read are complete.
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
  const payload =
    typeof r.payload === "string"
      ? (JSON.parse(r.payload) as UEMLike)
      : (r.payload as UEMLike);
  return {
    id: Number(r.id),
    payload,
  };
}
