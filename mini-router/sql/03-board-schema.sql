-- Shared context-board schema. Loaded on first MySQL boot via
-- /docker-entrypoint-initdb.d. The service upgrades older tables on startup.

-- board_gists: append-only log of admitted gists. Each row is one gist
-- surviving the deterministic verifier at admission time. board_id partitions
-- the shared notes (`pbench-top` for the released peer-coder experiment).
CREATE TABLE IF NOT EXISTS board_gists (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  board_id      VARCHAR(64)  NOT NULL,
  thread_id     VARCHAR(64)  NOT NULL,   -- agent identity, e.g. "pbench-worker3"
  type          VARCHAR(32)  NOT NULL,   -- FACT / OBSERVED / FAIL / CLAIM / PATCH_SUMMARY; legacy TRIED rows remain readable
  content       TEXT         NOT NULL,
  ts_epoch      DOUBLE       NOT NULL,   -- unix timestamp (float seconds)
  expires_at    DOUBLE,                  -- CLAIM only: TTL for auto-eviction from renders
  delegation_id VARCHAR(128),            -- work label for patch replacement and FAIL invalidation
  detail        LONGTEXT,                -- full text behind an abstract gist (selective unfolding)
  INDEX ix_board_ts (board_id, ts_epoch),
  INDEX ix_board_type (board_id, type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
