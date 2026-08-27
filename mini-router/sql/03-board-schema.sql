-- Shared board + task-queue schema for the DeLM-borrowing baselines and
-- our-method variants. Loaded on first MySQL boot via
-- /docker-entrypoint-initdb.d and re-applied by board-service.ensureSchema()
-- at every connect so a `make clean` cycle still initializes cleanly.

-- board_gists: append-only log of admitted gists. Each row is one gist
-- surviving the deterministic verifier at admission time. board_id partitions
-- the space (`pbench-top`, `pbench-team1`, …) so a single service instance can
-- serve multiple boards in the hierarchical topology.
CREATE TABLE IF NOT EXISTS board_gists (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  board_id      VARCHAR(64)  NOT NULL,
  thread_id     VARCHAR(64)  NOT NULL,   -- agent identity, e.g. "planner", "team1-worker3"
  type          VARCHAR(32)  NOT NULL,   -- FACT / TRIED / OBSERVED / FAIL / CLAIM / PATCH_SUMMARY
  content       TEXT         NOT NULL,
  task_id       VARCHAR(128),            -- optional link to a queue task
  ts_epoch      DOUBLE       NOT NULL,   -- unix timestamp (float seconds)
  expires_at    DOUBLE,                  -- CLAIM only: TTL for auto-eviction from renders
  delegation_id VARCHAR(128),            -- unit of work; CLAIM cap, patch latest-wins and FAIL-invalidation all key on (thread_id, delegation_id)
  task_instruction TEXT,                 -- rendered as the "Task:" line by patch_selective_unfold
  detail        LONGTEXT,                -- full text behind an abstract gist (selective unfolding)
  INDEX ix_board_ts (board_id, ts_epoch),
  INDEX ix_board_type (board_id, type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- board_queue_tasks: per-queue subtask table. A task becomes claimable when
-- ALL its dependencies (comma-separated task_ids in `deps`) are `completed`.
-- Claiming is an atomic UPDATE gated on state=pending; workers get the row
-- back and no other worker can claim the same task.
CREATE TABLE IF NOT EXISTS board_queue_tasks (
  id               BIGINT PRIMARY KEY AUTO_INCREMENT,
  queue_id         VARCHAR(64)  NOT NULL,
  task_id          VARCHAR(128) NOT NULL,   -- planner-assigned, e.g. "sub-1"
  description      TEXT         NOT NULL,
  deps             TEXT,                    -- CSV of task_ids this depends on
  state            VARCHAR(16)  NOT NULL DEFAULT 'pending', -- pending / claimed / completed / failed
  claimed_by       VARCHAR(64),
  claimed_at       DOUBLE,
  completed_at     DOUBLE,
  result_gist_id   BIGINT,                  -- optional FK to board_gists.id
  enqueued_at      DOUBLE       NOT NULL,
  UNIQUE KEY uk_queue_task (queue_id, task_id),
  INDEX ix_queue_state (queue_id, state)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- board_members: which agents can read/write which boards. Enforced at
-- request time in the service (server-side authorization). Populated
-- once at compose-up by the entrypoint that reads BOARD_MEMBERS_JSON.
CREATE TABLE IF NOT EXISTS board_members (
  board_id     VARCHAR(64) NOT NULL,
  member       VARCHAR(64) NOT NULL,
  PRIMARY KEY (board_id, member)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Board_gists cross-database grant so board-service (running as user
-- 'omcgitea') can also write to a hypothetical isolation DB later.
-- (Deferred: for M1 we keep everything in the same `omcgitea` database.)
