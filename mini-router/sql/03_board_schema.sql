-- Append-only gist history, including optional full detail behind each G-label.
-- Recent-view replacement and claim expiry do not delete these persisted rows.
CREATE TABLE IF NOT EXISTS board_gists (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  board_id      VARCHAR(64)  NOT NULL,
  thread_id     VARCHAR(64)  NOT NULL,
  type          VARCHAR(32)  NOT NULL,
  content       TEXT         NOT NULL,
  ts_epoch      DOUBLE       NOT NULL,
  expires_at    DOUBLE,
  delegation_id VARCHAR(128),
  detail        LONGTEXT,
  INDEX ix_board_ts (board_id, ts_epoch),
  INDEX ix_board_type (board_id, type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
