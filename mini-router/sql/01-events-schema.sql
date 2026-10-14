-- mini-router schema (R7 sidecar). Loaded by docker-entrypoint-initdb.d
-- on first MySQL boot, and by EventStore.ensureSchema() at every connect.
CREATE TABLE IF NOT EXISTS events (
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
  KEY ix_state_retry (state, next_retry_at),
  KEY ix_batch_state (batch_id, state)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cursors (
  agent VARCHAR(128) NOT NULL,
  source VARCHAR(64) NOT NULL,
  `cursor` VARCHAR(255) NOT NULL,
  PRIMARY KEY (agent, source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
