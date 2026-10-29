-- Durable worker event queue. Listener event IDs are deduplicated per agent.
-- Keep this seed schema aligned with EventStore.ensureSchema() in src/state.ts.
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
  last_error TEXT NULL,
  batch_id CHAR(36) NULL,
  next_retry_at BIGINT NULL,
  UNIQUE KEY uk_dedup_agent (dedup_key, agent),
  KEY ix_agent_state_id (agent, state, id),
  KEY ix_state_retry (state, next_retry_at),
  KEY ix_batch_state (batch_id, state)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Source ingestion watermarks advance after the corresponding events are stored.
CREATE TABLE IF NOT EXISTS cursors (
  agent VARCHAR(128) NOT NULL,
  source VARCHAR(64) NOT NULL,
  `cursor` VARCHAR(255) NOT NULL,
  PRIMARY KEY (agent, source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
