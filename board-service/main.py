"""
board-service — DeLM shared-context board + task queue as an HTTP service.

Ports SharedLessons + verify_notes verbatim from ~/DeLM/src/{shared_lessons,verifier}.py
and wraps them with:
  1. FastAPI endpoints (POST /board/{board_id}/note, GET /board/{board_id}/read,
     POST /queue/{queue_id}/{enqueue,claim,complete}).
  2. MySQL WAL so gists + queue tasks survive container restarts.
  3. Per-board membership check driven by BOARD_MEMBERS_JSON env
     (agent identity → set of boards they can read/write).

Design principles kept from DeLM:
  - Verifier is deterministic (no LLM). Schema, per-type char cap, evidence-
    quality regex on PATCH_SUMMARY, batch dedupe.
  - Shared context is append-only in memory (SharedLessons._entries);
    windowing, dedupe, and priority selection happen at read time.
  - Coordination is state-based: agents write compact typed gists, later
    agents read the accumulated view.

MySQL tables (03-board-schema.sql): board_gists, board_queue_tasks,
board_members. On boot we rehydrate SharedLessons for each board_id
we find in board_gists (idempotent).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import time
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiomysql
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from shared_lessons import SharedLessons, VALID_TYPES
from verifier import verify_notes
import unfold as unfold_mod
import gquery

# ------------- config ----------------------------------------------------
MYSQL_DSN = os.environ["MYSQL_DSN"]  # e.g. mysql://omcgitea:pw@mysql:3306/omcgitea
LISTEN_PORT = int(os.environ.get("BOARD_LISTEN_PORT", "8660"))
# BOARD_MEMBERS_JSON: '{"pbench-top":["pbench-worker1","pbench-worker2",...]}'
# Missing/empty → no auth (dev-friendly). In production it should be set.
_MEMBERS_ENV = os.environ.get("BOARD_MEMBERS_JSON", "").strip()
BOARD_MEMBERS: Dict[str, set] = {}
if _MEMBERS_ENV:
    try:
        BOARD_MEMBERS = {k: set(v) for k, v in json.loads(_MEMBERS_ENV).items()}
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"invalid BOARD_MEMBERS_JSON: {e}")

# Feature flags handed to every SharedLessons instance. Upstream constructs the
# board per-task from config.py:58-86; several of these default OFF there and
# gate real behavior, so they have to be reachable rather than hardcoded:
#   patch_summary_latest_wins_enabled — a refined PATCH_SUMMARY REPLACES the
#     thread's earlier one in place, so peers stop reading a stale candidate.
#   patch_summary_lifecycle_enabled  — enables mark_patch_summary_final() and
#     the [status=final,verified,local_failures=N] render suffix agents are
#     told to trust.
_DEFAULT_FEATURE_FLAGS = {
    "patch_summary_enabled": True,
    "claims_enabled": True,
    "tried_admission_filter": True,
    "patch_summary_latest_wins_enabled": True,
    "patch_summary_lifecycle_enabled": True,
}
_FLAGS_ENV = os.environ.get("BOARD_FEATURE_FLAGS_JSON", "").strip()
FEATURE_FLAGS: Dict[str, bool] = dict(_DEFAULT_FEATURE_FLAGS)
if _FLAGS_ENV:
    try:
        FEATURE_FLAGS.update({k: bool(v) for k, v in json.loads(_FLAGS_ENV).items()})
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"invalid BOARD_FEATURE_FLAGS_JSON: {e}")

# Upstream's shared_lessons_render_mode (config.py:79, modes dispatched at
# planner_agent.py:169-207 and swebench_implementer_agent.py:322-377).
VALID_RENDER_MODES = (
    "full",
    "peer_digest",
    "patch_digest",
    "patch_fail_digest",
    "patch_evidence_digest",
    "patch_digest_local_only",
    "patch_clean_local_only",
    "patch_clean_delayed_local",
    "patch_selective_unfold",
)
DEFAULT_RENDER_MODE = os.environ.get("BOARD_RENDER_MODE", "full").strip() or "full"
if DEFAULT_RENDER_MODE not in VALID_RENDER_MODES:
    raise SystemExit(
        f"invalid BOARD_RENDER_MODE {DEFAULT_RENDER_MODE!r}; "
        f"must be one of {VALID_RENDER_MODES}"
    )
# swebench_implementer_agent.py:21 — patch_clean_delayed_local shows nothing
# until this many steps have elapsed.
PATCH_CLEAN_DELAY_STEPS = int(os.environ.get("BOARD_PATCH_CLEAN_DELAY_STEPS", "8"))
# Operator identity used by the harness for the diagnostic endpoints. Not an
# agent; exempt from board membership.
BOARD_OPERATOR = os.environ.get("BOARD_OPERATOR", "harness")

# --- board_grep bounds ------------------------------------------------------
# grep searches board_gists, which is append-only and unbounded, so a broad
# term over a finished run can match five figures of rows. Returning them all
# would dump the whole board into the caller's prompt and force exactly the
# compaction the delta render exists to avoid (a 32-worker board reaches
# ~12.7k gists). So: page the newest N, always report the true total.
_GREP_DEFAULT_LIMIT = int(os.environ.get("BOARD_GREP_DEFAULT_LIMIT", "500"))
_GREP_MAX_LIMIT = int(os.environ.get("BOARD_GREP_MAX_LIMIT", "500"))
# Each term is one more OR'd LIKE branch, i.e. another full scan of the match
# set. Bounded so a pathological call cannot wedge the service for every agent.
_GREP_MAX_TERMS = int(os.environ.get("BOARD_GREP_MAX_TERMS", "50"))

# CLAIM TTL. Upstream's default is 300s (shared_lessons.py:24) and CLAIM is
# advisory throughout: never consulted before a write, capped at 2 per
# delegation, and off entirely in DeLM's shipped preset. We keep that
# semantics — a claim says "I am on this now", not "I own this path" — so the
# upstream TTL is the right default. Overridable for experiments.
# 1h: a claim should outlive the work item it describes. See the rationale on
# DEFAULT_CLAIM_TTL_SECONDS in shared_lessons.py.
CLAIM_TTL_SECONDS = float(os.environ.get("BOARD_CLAIM_TTL_SECONDS", "3600"))

# How long one /pending caller owns this agent's durable delivery mutex while
# its shim renders the result and posts /shown (normally well under 2s: the
# shim's ack times out at 1.5s). If the shim dies, another process can acquire
# the MySQL lease after this long.
PENDING_LEASE_SECONDS = 30.0


def _parse_dsn(dsn: str) -> Dict[str, Any]:
    """`mysql://user:pw@host:port/db` → aiomysql kwargs."""
    # Strip scheme.
    body = dsn.split("://", 1)[1] if "://" in dsn else dsn
    auth, _, tail = body.partition("@")
    user, _, password = auth.partition(":")
    host_port, _, db = tail.partition("/")
    host, _, port = host_port.partition(":")
    return {
        "user": user,
        "password": password or "",
        "host": host or "127.0.0.1",
        "port": int(port) if port else 3306,
        "db": db,
        "autocommit": True,
    }


# ------------- global state ----------------------------------------------
class State:
    """Per-process board + queue registry.

    boards: board_id -> SharedLessons. Constructed lazily on first touch;
    hydrated from board_gists on boot.

    Queue state lives in MySQL only (claim is an atomic UPDATE); no per-process
    cache to keep the "at most once per worker per task" property honest across
    restarts.
    """

    def __init__(self) -> None:
        self.pool: Optional[aiomysql.Pool] = None
        self.boards: Dict[str, SharedLessons] = {}
        self._boards_lock = asyncio.Lock()
        # The L/R layer of the paper's G->S->raw model: board_id -> gist_id ->
        # raw detail. Deliberately NOT inside SharedLessons — the shared context
        # C holds only gists, and keeping the detail out of it is what makes the
        # compression real rather than cosmetic.
        self.details: Dict[str, Dict[int, str]] = {}
        # board_id -> lock held from note() until the entry has its label.
        self.write_locks: Dict[str, asyncio.Lock] = {}

    def write_lock(self, board_id: str) -> asyncio.Lock:
        return self.write_locks.setdefault(board_id, asyncio.Lock())

    def board(self, board_id: str) -> SharedLessons:
        # Lazy: first read/write on a new board creates it in-memory.
        b = self.boards.get(board_id)
        if b is None:
            b = SharedLessons(
                task_id=board_id,
                feature_flags=dict(FEATURE_FLAGS),
            )
            self.boards[board_id] = b
        return b

    async def snapshot_many(
        self, board_ids: List[str]
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], float]:
        """Copy the entry list of every requested board inside ONE critical section.

        A multi-board render (a director board plus a team board) is
        otherwise assembled from N independent reads, so a peer writing between
        read 1 and read 2 yields a view that never existed at any single instant.
        DeLM never hits this because a thread reads exactly one SharedLessons
        under its own lock; once we tier the boards, we have to recover that
        property explicitly.

        Locks are taken in sorted board_id order — one global order shared by
        every caller, which is what keeps concurrent snapshots deadlock-free.
        Rendering happens after the locks drop, since `_select_entries` is pure
        with respect to the snapshot it is handed.
        """
        ordered = sorted(set(board_ids))
        boards = [self.board(bid) for bid in ordered]
        snaps: Dict[str, List[Dict[str, Any]]] = {}
        async with AsyncExitStack() as stack:
            for b in boards:
                await stack.enter_async_context(b._lock)
            at = time.time()
            for bid, b in zip(ordered, boards):
                snaps[bid] = list(b._entries)
        return snaps, at

    async def hydrate(self) -> None:
        """Rehydrate SharedLessons instances from MySQL WAL on boot."""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT id, board_id, thread_id, type, content, task_id, "
                    "ts_epoch, expires_at, delegation_id, task_instruction, detail "
                    "FROM board_gists ORDER BY id"
                )
                rows = await cur.fetchall()
        # Earliest ts per board, computed BEFORE the trim below: it is the run's
        # true start, whereas the oldest SURVIVING entry is just wherever the
        # 2,000-entry window happens to begin.
        earliest: Dict[str, float] = {}
        for r in rows:
            b = self.board(r["board_id"])
            gid = int(r["id"])
            _bts = float(r["ts_epoch"])
            _bid = r["board_id"]
            if _bts < earliest.get(_bid, float("inf")):
                earliest[_bid] = _bts
            detail = r.get("detail")
            if detail:
                self.details.setdefault(r["board_id"], {})[gid] = detail
            entry = {
                "ts": float(r["ts_epoch"]),
                "thread_id": r["thread_id"],
                "type": r["type"],
                "content": r["content"],
                "delegation_id": r.get("delegation_id"),
                "_expires_at": (float(r["expires_at"]) if r["expires_at"] is not None else None),
                "_label": f"G{gid}",
                "_has_detail": bool(detail),
            }
            if r.get("task_instruction"):
                entry["task"] = r["task_instruction"]
            # Re-admit through the same step note() uses, skipping note()'s
            # verifier (every row already passed it on its first admit). It
            # replays what the live board did row by row: the PATCH_SUMMARY
            # latest-wins replacement, the lifecycle marks a FAIL leaves
            # (invalidated, local_failures, no longer verified), and the
            # MAX_BOARD_ENTRIES trim in write order. A trim applied once at the
            # end instead would replace a revision into a slot the live board
            # had already dropped, then cut it.
            b._admit(entry, replay=True)

        # Restore each board's clock origin.
        #
        # _start_time is set to time.time() in SharedLessons.__init__ and every
        # rendered line is "+{ts - _start_time}m". hydrate() repopulates entries
        # but not the origin, which stays at PROCESS BOOT, so without this a
        # mid-run restart renders every pre-restart gist with a NEGATIVE offset
        # ("[tworker2/PATCH_SUMMARY +-66.2m]"), and the lifecycle dump's
        # first_rel_s / last_rel_s go wrong the same way.
        for bid, ts0 in earliest.items():
            b = self.boards.get(bid)
            if b is not None:
                b._start_time = min(b._start_time, ts0)


STATE = State()


# ------------- FastAPI schemas -------------------------------------------
class NoteIn(BaseModel):
    thread_id: str = Field(..., description="Agent identity, e.g. 'pbench-worker3'")
    type: str = Field(..., description="One of FACT/TRIED/OBSERVED/FAIL/CLAIM/PATCH_SUMMARY")
    content: str
    # task_id and delegation_id land in VARCHAR(128) columns. A longer value is
    # refused here; past this point the note is admitted in memory before the
    # INSERT that would reject it.
    task_id: Optional[str] = Field(None, max_length=128)
    # Upstream keys several behaviors on (thread_id, delegation_id) rather than
    # thread alone: the CLAIM cap of 2, the one-PATCH_SUMMARY-per-delegation
    # rule and its latest-wins replacement, and "a FAIL invalidates THIS
    # delegation's own patch summary". Passing None collapses every unit of
    # work an agent ever does into a single bucket, which silently disarms all
    # four. Our analogue is the queue task the agent is working under.
    delegation_id: Optional[str] = Field(None, max_length=128)
    # Rendered as the "Task:" line by the patch_selective_unfold mode
    # (shared_lessons.py:1065-1076). Upstream only populates it in that mode.
    task_instruction: Optional[str] = None
    ttl_seconds: Optional[float] = None
    # The raw source unit R[l] behind this gist. Stored outside the shared
    # context and reachable only via /unfold, so peers pay gist-sized tokens by
    # default and full price only for the slice they ask for.
    detail: Optional[str] = None


class NoteOut(BaseModel):
    status: str  # "admitted" | "rejected"
    reason: Optional[str] = None
    gist_id: Optional[int] = None
    label: Optional[str] = None


class EnqueueIn(BaseModel):
    task_id: str
    description: str
    deps: List[str] = Field(default_factory=list)
    enqueued_by: str


class ClaimIn(BaseModel):
    claimed_by: str


class CompleteIn(BaseModel):
    task_id: str
    claimed_by: str
    state: str = "completed"  # or "failed"
    result_gist_id: Optional[int] = None


# ------------- helpers ----------------------------------------------------
def _authorize(agent: str, board_id: str) -> None:
    """Raise 403 if agent is not a member of board_id (when membership is configured)."""
    if not BOARD_MEMBERS:
        return
    if agent == BOARD_OPERATOR:
        # The harness, not an agent. It never reads gists into a prompt — it
        # only triggers the end-of-run lifecycle dump and reads stats — so
        # gating it on board membership would just mean losing the measurement.
        return
    members = BOARD_MEMBERS.get(board_id)
    if members is None:
        raise HTTPException(status_code=404, detail=f"unknown board {board_id}")
    if agent not in members:
        raise HTTPException(
            status_code=403,
            detail=f"agent {agent!r} is not a member of board {board_id!r}",
        )


async def _persist_gist(board_id: str, entry: Dict[str, Any],
                        task_id: Optional[str] = None,
                        detail: Optional[str] = None) -> int:
    """Append the just-admitted gist to the MySQL WAL. Returns its id.

    Ordering follows the paper's A.4 admission rule — the detail layer is
    durable before the gist that points at it, so a peer can never read a label
    whose backing content is missing.
    """
    async with STATE.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO board_gists "
                "(board_id, thread_id, type, content, task_id, ts_epoch, expires_at, "
                " delegation_id, task_instruction, detail) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    board_id,
                    entry["thread_id"],
                    entry["type"],
                    entry["content"],
                    task_id,
                    entry["ts"],
                    entry.get("_expires_at"),
                    entry.get("delegation_id"),
                    entry.get("task"),
                    detail,
                ),
            )
            return int(cur.lastrowid)


# Columns added after the first deployment. MySQL 8.4 has no
# "ADD COLUMN IF NOT EXISTS", and the init script under
# /docker-entrypoint-initdb.d only runs on a virgin volume, so a live profile
# would otherwise keep the old table forever. Attempt, ignore "duplicate
# column".
_MIGRATIONS = (
    "ALTER TABLE board_gists ADD COLUMN delegation_id VARCHAR(128) NULL",
    "ALTER TABLE board_gists ADD COLUMN task_instruction TEXT NULL",
    "ALTER TABLE board_gists ADD COLUMN detail LONGTEXT NULL",
    # The merge poller's record. The poller writes here and GET /merges?since=
    # reads it back. Merge notices are not delivered to
    # agents, so this table is the analytic record of what landed, nothing more.
    """CREATE TABLE IF NOT EXISTS merges (
         id BIGINT AUTO_INCREMENT PRIMARY KEY,
         repo VARCHAR(255) NOT NULL,
         number INT NOT NULL,
         title VARCHAR(512) NOT NULL DEFAULT '',
         merged_by VARCHAR(128) NOT NULL DEFAULT '',
         merged_at DATETIME NOT NULL,
         seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
         UNIQUE KEY uq_merge (repo, number, merged_at),
         KEY ix_id (id)
       ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    # What mcp-notice-shim has already rendered into a tool result, so the
    # router can retire those rows in its next tick instead of re-delivering
    # them at the turn boundary.
    #
    # Deliberately OURS and not a column on `events`: the router must stay the
    # only writer to that table. Its dispatcher guards a claim on
    # `if (claimed === 0) return` without filtering the batch, so a partial CAS
    # loss from an outside writer double-delivers silently; rows parked in
    # 'sending' are mass-reverted by recoverSendingToPending on boot; rows in
    # 'retrying' are reclaimed only by the router's own retry sweeper.
    """CREATE TABLE IF NOT EXISTS shown (
         event_id BIGINT NOT NULL,
         agent VARCHAR(128) NOT NULL,
         shown_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
         PRIMARY KEY (event_id, agent),
         KEY ix_agent (agent)
       ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    # One durable delivery mutex per agent. Every agent has several independent
    # MCP shims, and a process-local lock would also vanish across a service
    # restart; claiming before any queue read keeps them from rendering the same
    # unacknowledged batch. The token makes a late ack unable to release a newer
    # owner's lease after expiry.
    """CREATE TABLE IF NOT EXISTS pending_leases (
         agent VARCHAR(128) NOT NULL,
         lease_token CHAR(32) NOT NULL,
         lease_until DOUBLE NOT NULL,
         PRIMARY KEY (agent),
         KEY ix_lease_until (lease_until)
       ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    # How far through the board each agent has already been told.
    #
    # "Newly arrived" for mid-turn delivery means "created after the board
    # snapshot that was rendered into this agent's current prompt" -- the agent
    # already holds everything at or below this id under `==== SHARED CONTEXT
    # ====`, so re-injecting it would spend context on a duplicate.
    #
    # Pushed forward from BOTH ends and never backwards:
    #   /snapshot  -> the highest gist id rendered into the prompt (turn start)
    #   /shown     -> past the gists just injected (mid-turn), so the next MCP
    #                 call in the same turn does not repeat them.
    """CREATE TABLE IF NOT EXISTS board_cursor (
         agent VARCHAR(128) NOT NULL,
         board_id VARCHAR(64) NOT NULL,
         gist_id BIGINT NOT NULL,
         updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
         PRIMARY KEY (agent, board_id)
       ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
)


def _gist_id(entry: Dict[str, Any]) -> int:
    """Monotonic board_gists.id carried on an in-memory entry as `_label`="G123".

    Never use list position instead: PATCH_SUMMARY latest-wins replaces in
    place (shared_lessons: `self._entries[existing_idx] = entry`), so a refined
    summary has a HIGHER id at an OLDER position, and a positional cursor would
    skip it forever.
    """
    lab = entry.get("_label")
    if isinstance(lab, str) and lab.startswith("G") and lab[1:].isdigit():
        return int(lab[1:])
    return 0


def _agent_boards(agent: str) -> List[str]:
    """Boards this agent may read. Empty membership config = all known boards."""
    if not BOARD_MEMBERS:
        return list(STATE.boards.keys())
    return [bid for bid, members in BOARD_MEMBERS.items() if agent in members]


async def _get_board_cursor(agent: str, board_id: str) -> int:
    async with STATE.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT gist_id FROM board_cursor WHERE agent=%s AND board_id=%s",
                (agent, board_id),
            )
            row = await cur.fetchone()
    return int(row[0]) if row else 0


async def _advance_board_cursor(agent: str, board_id: str, gist_id: int) -> None:
    """Monotonic: GREATEST() so an out-of-order caller can never rewind it."""
    if gist_id <= 0:
        return
    async with STATE.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO board_cursor (agent, board_id, gist_id) VALUES (%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE gist_id = GREATEST(gist_id, VALUES(gist_id))",
                (agent, board_id, int(gist_id)),
            )
        await conn.commit()


async def _claim_pending_lease(agent: str) -> Optional[str]:
    """Atomically acquire this agent's cross-process /pending mutex."""
    token = secrets.token_hex(16)
    now = time.time()
    until = now + PENDING_LEASE_SECONDS
    acquired = False
    async with STATE.pool.acquire() as conn:
        async with conn.cursor() as cur:
            # Exactly one contender can update an expired row. If the row does
            # not exist, exactly one INSERT IGNORE creates it; a concurrent
            # winner makes every other insert report rowcount=0.
            await cur.execute(
                "UPDATE pending_leases SET lease_token=%s, lease_until=%s "
                "WHERE agent=%s AND lease_until <= %s",
                (token, until, agent, now),
            )
            acquired = cur.rowcount == 1
            if not acquired:
                await cur.execute(
                    "INSERT IGNORE INTO pending_leases "
                    "(agent, lease_token, lease_until) VALUES (%s,%s,%s)",
                    (agent, token, until),
                )
                acquired = cur.rowcount == 1
        await conn.commit()
    return token if acquired else None


async def _release_pending_lease(agent: str, token: str) -> None:
    """Release only the lease represented by token; stale acks are harmless."""
    async with STATE.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM pending_leases WHERE agent=%s AND lease_token=%s",
                (agent, token),
            )
        await conn.commit()


async def _migrate() -> None:
    async with STATE.pool.acquire() as conn:
        async with conn.cursor() as cur:
            for stmt in _MIGRATIONS:
                try:
                    await cur.execute(stmt)
                except Exception:  # noqa: BLE001 — duplicate column is expected
                    pass


# ---------------------------------------------------------------------------
# Merge notices
#
# Gitea notifies IssueWatchers u RepoWatchers u Participants - author, and the
# merger is excluded from their own event, so a merge reaches the PR author and
# its commenters and nobody else. Every other worker keeps building against a
# main that has already moved -- 664 re-pushes across 70 PRs on the ffmpeg
# 16-worker run, each re-entering a 772s median CI queue.
#
# The poller lives here, not in the per-agent router, so the stack polls Gitea
# once instead of once per agent.
# ---------------------------------------------------------------------------

MERGE_WATCH_REPO = os.environ.get("MERGE_WATCH_REPO", "").strip()
MERGE_POLL_MS = int(os.environ.get("MERGE_POLL_MS", "20000") or 20000)
_GITEA_HOST = os.environ.get("GITEA_HOST", "").strip().rstrip("/")


def _gitea_token() -> str:
    """Token from env, or from a file for the secret-service path."""
    t = os.environ.get("GITEA_TOKEN", "").strip()
    if t:
        return t
    f = os.environ.get("GITEA_TOKEN_FILE", "").strip()
    if f:
        try:
            return Path(f).read_text().strip()
        except OSError:
            return ""
    return ""


def _fetch_merged_pulls() -> List[Dict[str, Any]]:
    """Blocking; callers must run it off the loop. stdlib only -- board-service
    has no HTTP client dependency and this is not worth adding one for."""
    import urllib.request

    url = (
        f"{_GITEA_HOST}/api/v1/repos/{MERGE_WATCH_REPO}/pulls"
        "?state=closed&sort=recentupdate&limit=50"
    )
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {_gitea_token()}",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 - in-stack host
        return json.loads(r.read().decode())


async def _record_merges(rows: List[Dict[str, Any]]) -> int:
    """INSERT IGNORE on the unique key, so re-polling the same page is free."""
    if not rows:
        return 0
    n = 0
    async with STATE.pool.acquire() as conn:
        async with conn.cursor() as cur:
            for pr in rows:
                merged_at = pr.get("merged_at")
                if not merged_at:
                    continue  # closed but not merged
                await cur.execute(
                    "INSERT IGNORE INTO merges (repo, number, title, merged_by, merged_at) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (
                        MERGE_WATCH_REPO,
                        int(pr.get("number") or 0),
                        str(pr.get("title") or "")[:512],
                        str(((pr.get("merged_by") or {}) or {}).get("login") or "")[:128],
                        merged_at.replace("T", " ").replace("Z", "")[:19],
                    ),
                )
                n += cur.rowcount
        await conn.commit()
    return n


async def _merge_poll_loop() -> None:
    """Board endpoints must keep working without a token, so this degrades
    rather than raising.

    The readiness check is INSIDE the loop, not a one-shot guard. board-service
    depends only on mysql, so it starts before bootstrap has written
    admin.token: a startup-time check sees no token, and an early return would
    disable the merge poller for the entire run while every endpoint still
    looked healthy ("token=unset" logged at boot, with the file readable
    moments later).
    """
    announced = False
    started = False
    while True:
        ready = bool(MERGE_WATCH_REPO and _GITEA_HOST and _gitea_token())
        if not ready:
            if not announced:
                print(
                    "[board] merge poller waiting "
                    f"(repo={MERGE_WATCH_REPO or 'unset'} "
                    f"host={'set' if _GITEA_HOST else 'unset'} "
                    f"token={'set' if _gitea_token() else 'unset'})",
                    flush=True,
                )
                announced = True
            await asyncio.sleep(MERGE_POLL_MS / 1000)
            continue
        if not started:
            # Say so exactly once. A poller that is silent when healthy is
            # indistinguishable from one that never started -- which is the
            # failure this loop already exists to survive.
            print(
                f"[board] merge poller watching {MERGE_WATCH_REPO} "
                f"every {MERGE_POLL_MS}ms",
                flush=True,
            )
            started = True
        announced = False
        try:
            rows = await asyncio.to_thread(_fetch_merged_pulls)
            added = await _record_merges(rows)
            if added:
                print(f"[board] recorded {added} new merge(s)", flush=True)
        except Exception as e:  # noqa: BLE001 - a poll failure must not kill the service
            print(f"[board] merge poll failed: {e}", flush=True)
        await asyncio.sleep(MERGE_POLL_MS / 1000)


async def _render_mode(
    b: SharedLessons,
    *,
    mode: str,
    role: str,
    viewer: str,
    window_tokens: int,
    step: int,
) -> str:
    """Dispatch upstream's shared_lessons_render_mode matrix.

    Ported from the two call sites that implement it — planner_agent.py:169-207
    and swebench_implementer_agent.py:322-377. The matrix is role-dependent:
    the same mode string shows a planner and an implementer different things,
    and three of the modes blind the planner entirely (the "local_only" family,
    which exists to test whether the planner benefits from the board at all).

    We map role: a lead/director/planner is a "planner"; everyone else is an
    "implementer".
    """
    is_planner = role == "planner"

    if mode == "full":
        # Implementers demote their OWN notes so peer content wins the budget;
        # the planner sees the board unfiltered.
        if is_planner:
            return await b.render(window_tokens=window_tokens)
        return await b.render(
            window_tokens=window_tokens,
            viewer_thread_id=viewer,
            self_policy="demote_current",
        )

    if mode == "peer_digest":
        return await b.render_peer_digest(
            window_tokens=window_tokens, viewer_thread_id=viewer
        )

    if mode == "patch_digest":
        return await b.render_peer_digest(
            window_tokens=window_tokens,
            viewer_thread_id=viewer,
            allowed_types=("PATCH_SUMMARY",),
        )

    if mode == "patch_fail_digest":
        if is_planner:
            return await b.render_peer_digest(
                window_tokens=window_tokens,
                viewer_thread_id=viewer,
                allowed_types=("PATCH_SUMMARY",),
            )
        # Only peer FAILs grounded in a real patch attempt — an ungrounded FAIL
        # is usually just someone's broken command.
        #
        # NOTE: board_finalize was removed, so nothing sets `_finalized` any
        # more and this filter now matches nothing — patch_fail_digest would
        # render no FAILs at all. It is unreachable in our config
        # (BOARD_RENDER_MODE is unset -> "full"), so this is dormant rather
        # than broken; anyone enabling this mode must first decide what
        # "grounded" means without the finalize signal.
        return await b.render_peer_digest(
            window_tokens=window_tokens,
            viewer_thread_id=viewer,
            allowed_types=("PATCH_SUMMARY", "FAIL"),
            fail_requires_finalized_patch=True,
        )

    if mode == "patch_evidence_digest":
        if is_planner:
            return await b.render_peer_digest(
                window_tokens=window_tokens,
                viewer_thread_id=viewer,
                allowed_types=("PATCH_SUMMARY",),
            )
        return await b.render_peer_digest(
            window_tokens=window_tokens,
            viewer_thread_id=viewer,
            allowed_types=("PATCH_SUMMARY", "OBSERVED", "FACT"),
        )

    if mode in ("patch_digest_local_only", "patch_clean_local_only",
                "patch_clean_delayed_local"):
        if is_planner:
            return ""  # planner deliberately blinded in this family
        if mode == "patch_clean_delayed_local" and step < PATCH_CLEAN_DELAY_STEPS:
            return ""
        return await b.render_peer_digest(
            window_tokens=window_tokens,
            viewer_thread_id=viewer,
            allowed_types=("PATCH_SUMMARY",),
            patch_requires_no_fail=(mode != "patch_digest_local_only"),
        )

    if mode == "patch_selective_unfold":
        return await b.render_patch_selective_unfold()

    raise HTTPException(status_code=400, detail=f"unknown render_mode {mode!r}")


# ------------- app --------------------------------------------------------
app = FastAPI(title="omcgitea-board", version="0.1.0")


@app.on_event("startup")
async def _startup() -> None:
    kwargs = _parse_dsn(MYSQL_DSN)
    # MySQL accepts pings while it is still finishing first-boot initialization,
    # so "healthy" upstream does not guarantee a usable connection. Without a
    # retry the board dies at startup and every agent runs with no shared
    # context — a silent degradation, since dispatch is designed to continue
    # when the board is absent.
    delays = [1, 2, 3, 5, 8, 13, 21]
    last: Exception | None = None
    for i, d in enumerate([0, *delays]):
        if d:
            await asyncio.sleep(d)
        try:
            # Pool sized for the team. ONE board-service serves every agent, and
            # every MCP tool call hits /pending -- at 128 agents that is roughly
            # 650 req/min against this pool. maxsize=8 suffices at 4-16 workers
            # and is a hard queue at 128. mysql allows 1000 connections
            # (gen-compose-prod.py), so the pool is not the scarce side.
            _pool_max = int(os.environ.get("BOARD_MYSQL_POOL_MAX", "32"))
            STATE.pool = await aiomysql.create_pool(
                minsize=1, maxsize=_pool_max, **kwargs)
            break
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"[board] mysql connect attempt {i + 1} failed: {e}", flush=True)
    if STATE.pool is None:
        raise SystemExit(f"board: cannot reach mysql after retries: {last}")
    await _migrate()
    await STATE.hydrate()
    # Fire-and-forget: a poll failure must never take the board down.
    asyncio.create_task(_merge_poll_loop())


@app.on_event("shutdown")
async def _shutdown() -> None:
    if STATE.pool is not None:
        STATE.pool.close()
        await STATE.pool.wait_closed()


@app.get("/merges")
async def get_merges(since: int = 0, limit: int = 200) -> Dict[str, Any]:
    """Merges observed since `since`. READ-ONLY — advances no cursor.

    The router polls this and inserts UEM `events` rows itself, keeping it the
    only writer to that table. Self-merge suppression is NOT done here: the
    router knows its own agent and filters on `merged_by`, which keeps this
    endpoint agent-agnostic and therefore cacheable across the stack.

    It must stay read-only: a take-once read that advances a cursor as a side
    effect loses the merge outright whenever the reader drains and then fails
    to deliver (a failed prompt, a crashed MCP server).
    """
    async with STATE.pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT id, repo, number, title, merged_by, merged_at "
                "FROM merges WHERE id > %s ORDER BY id ASC LIMIT %s",
                (int(since), max(1, min(1000, int(limit)))),
            )
            rows = list(await cur.fetchall())
    return {
        "merges": [
            {
                "id": int(r["id"]),
                "repo": r["repo"],
                "number": int(r["number"]),
                "title": r["title"],
                "merged_by": r["merged_by"],
                "text": f"[system] PR #{int(r['number'])} merged to main",
            }
            for r in rows
        ],
    }


@app.get("/pending/{agent}")
async def get_pending(agent: str, limit: int = 50) -> Dict[str, Any]:
    """Priority notices this agent has not yet been shown. NOT take-once.

    Called by mcp-notice-shim on every MCP tool call, so it must be cheap and
    it must be safe to call repeatedly: retirement happens in the router's tick
    once /shown records what actually reached a tool result. Reading here can
    never lose a notice.

    A durable, per-agent mutex is acquired before any queue read. An agent runs
    one shim per MCP server, and parallel tool calls (or overlapping service
    processes during a rollout) would otherwise read and render the same batch.
    /shown releases the exact lease token after durable retirement; if the shim
    dies first, the lease expires and the batch becomes visible again.

    Reads `events` but never writes it -- the router owns that table.
    """
    lease_token = await _claim_pending_lease(agent)
    if lease_token is None:
        return {"agent": agent, "notices": []}

    async with STATE.pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT e.id, e.payload FROM events e "
                " LEFT JOIN shown s ON s.event_id = e.id AND s.agent = e.agent "
                " WHERE e.agent = %s AND e.state = 'pending' "
                "   AND JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.kind')) = 'dm' "
                "   AND s.event_id IS NULL "
                " ORDER BY e.id ASC LIMIT %s",
                (agent, max(1, min(200, int(limit)))),
            )
            rows = list(await cur.fetchall())

    cursors: Dict[str, int] = {}
    for bid in _agent_boards(agent):
        try:
            cursors[bid] = await _get_board_cursor(agent, bid)
        except Exception:  # noqa: BLE001 -- never fail a tool call over a board read
            continue

    now_ts = time.time()
    notices: List[Dict[str, Any]] = []
    for r in rows:
        payload = r["payload"]
        if isinstance(payload, (str, bytes)):
            try:
                payload = json.loads(payload)
            except Exception:
                continue
        text = (payload or {}).get("summary")
        if not text:
            continue
        notices.append({"id": f"e{int(r['id'])}", "text": str(text)})

    # Board entries written since the snapshot already in this agent's prompt.
    #
    # Rendered with the SAME function the shared-context block uses, and
    # appended with no wrapper: the agent sees the entries themselves, exactly
    # as they appear under `==== SHARED CONTEXT ====`, not a "[system] board
    # updated" placeholder it would have to act on.
    #
    # Own entries are skipped -- self-echo was 49% of all DM volume before the
    # mattermost path grew the same filter.
    for bid, cursor in cursors.items():
        try:
            snap = list(STATE.board(bid)._entries)
        except Exception:  # noqa: BLE001 -- never fail a tool call over a board read
            continue
        fresh = [e for e in snap
                 if _gist_id(e) > cursor and e.get("thread_id") != agent]
        fresh.sort(key=_gist_id)
        b = STATE.board(bid)
        rendered: List[Dict[str, Any]] = []
        for e in fresh:
            try:
                line = b.format_entry_line(e, now_ts)
            except Exception:  # noqa: BLE001
                # /shown advances one monotonic cursor per board. Never render a
                # higher gist across a lower formatting gap or its ack would make
                # the lower gist permanently unreachable.
                break
            notices.append({"id": f"g{_gist_id(e)}", "text": line})
            rendered.append(e)

        # Advertise labels for the entries we just delivered.
        #
        # format_entry_line emits no id -- it is a verbatim port and both this
        # path and the turn-start block call it so the two render identically.
        # So the label has to ride in a separate block, exactly as `full` mode
        # does after format_for_prompt.
        #
        # Without this, mid-turn would be the ONLY delivery path with no handle
        # to unfold by -- and mid-turn is the dominant path, so most board
        # content would arrive unopenable.
        #
        # The id is deliberately NOT `g<id>`: this is derived from entries that
        # each carry their own ack, so post_shown's `g`/`e` parsers skip it and
        # nothing tries to retire a gist that does not exist.
        try:
            idx = unfold_mod.render_index(rendered)
        except Exception:  # noqa: BLE001 -- never fail a tool call over the index
            idx = ""
        if idx:
            notices.append({"id": f"bx-{bid}", "text": idx})

    if not notices:
        await _release_pending_lease(agent, lease_token)
        return {"agent": agent, "notices": []}
    return {"agent": agent, "notices": notices, "lease_token": lease_token}


@app.post("/shown/{agent}")
async def post_shown(agent: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Record which notices the shim rendered into a tool result.

    Fire-and-forget from the shim's side: a lost ack costs one duplicate
    notice, whereas blocking the tool call would cost the agent a step.
    INSERT IGNORE so a retried report is idempotent.
    """
    raw = (body or {}).get("ids", [])
    lease_token = (body or {}).get("lease_token")
    if not isinstance(lease_token, str) or re.fullmatch(r"[0-9a-f]{32}", lease_token) is None:
        lease_token = None
    # The id is namespaced so one report can carry both sources:
    #   "e123" -> an events row, retired via the `shown` table (router's tick)
    #   "g456" -> a board gist, retired by advancing this agent's board cursor
    # Bare digits are accepted as event ids for compatibility with older shims.
    event_ids: List[int] = []
    gist_ids: List[int] = []
    for i in raw:
        s = str(i)
        if s.startswith("g") and s[1:].isdigit():
            gist_ids.append(int(s[1:]))
        elif s.startswith("e") and s[1:].isdigit():
            event_ids.append(int(s[1:]))
        elif s.lstrip("-").isdigit():
            event_ids.append(int(s))
    if not event_ids and not gist_ids:
        return {"recorded": 0}
    if event_ids:
        async with STATE.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(
                    "INSERT IGNORE INTO shown (event_id, agent) VALUES (%s, %s)",
                    [(i, agent) for i in event_ids],
                )
            await conn.commit()
    if gist_ids:
        # Gist ids are global, but cursors are per board. Resolve each ack to its
        # actual board rather than pushing every board to the global maximum;
        # otherwise a temporarily unreadable board can lose lower-numbered gists.
        placeholders = ",".join(["%s"] * len(gist_ids))
        async with STATE.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    f"SELECT id, board_id FROM board_gists WHERE id IN ({placeholders})",
                    tuple(gist_ids),
                )
                gist_rows = list(await cur.fetchall())
        allowed = set(_agent_boards(agent))
        tops: Dict[str, int] = {}
        for row in gist_rows:
            bid = str(row["board_id"])
            if bid in allowed:
                tops[bid] = max(tops.get(bid, 0), int(row["id"]))
        for bid, top in tops.items():
            await _advance_board_cursor(agent, bid, top)
    if lease_token is not None:
        # The mutex was acquired before /pending read anything, so after all
        # retirement writes above commit there is no stale losing reader to race
        # this release. Token matching protects a newer post-expiry owner.
        await _release_pending_lease(agent, lease_token)
    return {"recorded": len(event_ids) + len(gist_ids)}


@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    return {"ok": True, "boards": list(STATE.boards.keys())}


# ---- board endpoints -----------------------------------------------------
@app.post("/board/{board_id}/note", response_model=NoteOut)
async def post_note(board_id: str, note: NoteIn) -> NoteOut:
    _authorize(note.thread_id, board_id)
    # Run DeLM's deterministic verifier on this single-note batch.
    clean, status = verify_notes([{"type": note.type, "content": note.content}])
    if not clean:
        return NoteOut(status="rejected", reason=status)
    b = STATE.board(board_id)
    # One write per board at a time, from admission until the label is set.
    # note() puts the entry on the board before the INSERT assigns its id, and
    # the delta reads skip unlabeled entries while advancing each viewer's
    # cursor to the highest labeled id. Two overlapping writes could finish
    # out of order, move a cursor past the lower id, and that gist would never
    # reach a peer's delta.
    async with STATE.write_lock(board_id):
        # We map DeLM's numeric thread_id → agent identity string. Ports of shared_lessons.py
        # keep thread_id as int in some paths; here we set it as-is (str) and rely on the
        # dedupe key being (type, normalized-content), which doesn't care.
        entry = await b.note(
            thread_id=note.thread_id,
            type=clean[0]["type"],
            content=clean[0]["content"],
            delegation_id=note.delegation_id,
            # CLAIM carries the configured TTL unless the caller pins one.
            ttl_seconds=(
                note.ttl_seconds
                if note.ttl_seconds is not None
                else (CLAIM_TTL_SECONDS if clean[0]["type"] == "CLAIM" else None)
            ),
            task_instruction=note.task_instruction,
        )
        if entry is None:
            # e.g. TRIED admission filter dropped it
            return NoteOut(status="rejected", reason="admission-filter")
        gid = await _persist_gist(board_id, entry, task_id=note.task_id, detail=note.detail)
        # Label the live entry so the render index can advertise it. `entry` is the
        # same dict SharedLessons holds in _entries, so this mutation is visible to
        # every later read without touching the ported storage code.
        entry["_label"] = f"G{gid}"
        entry["_has_detail"] = bool(note.detail)
        if note.detail:
            STATE.details.setdefault(board_id, {})[gid] = note.detail
    return NoteOut(status="admitted", gist_id=gid, label=f"G{gid}")


@app.get("/board/{board_id}/read")
async def get_read(
    board_id: str,
    viewer: str = Query(..., description="Agent identity of the reader"),
    # 0 = unlimited (ship the whole board). The lower bound must allow 0, or
    # the router's request for the full board would 422. See
    # shared_lessons._select_entries.
    window_tokens: int = Query(1000, ge=0, le=8000),
    render_mode: Optional[str] = Query(
        None, description=f"One of {VALID_RENDER_MODES}; defaults to BOARD_RENDER_MODE"
    ),
    role: str = Query("implementer", description="'planner' or 'implementer'"),
    self_policy: str = Query(
        "include",
        description="include | demote_current | demote_thread | exclude_current "
                    "(applies to render_mode=full only)",
    ),
    step: int = Query(0, ge=0, description="Caller's step index; patch_clean_delayed_local gates on it"),
) -> Dict[str, Any]:
    _authorize(viewer, board_id)
    b = STATE.board(board_id)
    mode = render_mode or DEFAULT_RENDER_MODE
    if mode not in VALID_RENDER_MODES:
        raise HTTPException(status_code=400, detail=f"unknown render_mode {mode!r}")

    # The default path keeps returning stats (callers depend on them); the
    # non-`full` modes upstream return a bare string.
    if mode == "full" and role != "planner":
        entries, stats = await b.read_with_stats(
            window_tokens=window_tokens,
            viewer_thread_id=viewer,
            self_policy=self_policy,
        )
        rendered = b.format_for_prompt(entries)
        stats = dict(stats)
        stats["rendered_chars_actual"] = len(rendered)
        idx = unfold_mod.render_index(entries)
        if idx:
            rendered = rendered + "\n\n" + idx
        return {"board_id": board_id, "rendered": rendered,
                "render_mode": mode, "stats": stats}

    rendered = await _render_mode(
        b, mode=mode, role=role, viewer=viewer,
        window_tokens=window_tokens, step=step,
    )
    return {"board_id": board_id, "rendered": rendered, "render_mode": mode, "stats": {}}


@app.get("/board/{board_id}/stats")
async def get_board_stats(
    board_id: str,
    viewer: str = Query(...),
    window_tokens: Optional[int] = Query(None, ge=100, le=8000),
) -> Dict[str, Any]:
    """Storage + render-selection stats (shared_lessons.py:842-921).

    This is how we answer "did the board actually get used" with something
    better than counting HTTP calls: it reports duplicates suppressed, entries
    dropped for budget, expired claims, and per-type live counts.
    """
    _authorize(viewer, board_id)
    b = STATE.board(board_id)
    return await b.get_stats(window_tokens=window_tokens)


@app.post("/board/{board_id}/lifecycle")
async def post_lifecycle(board_id: str, viewer: str = Query(...)) -> Dict[str, Any]:
    """Dump the per-entry lesson-lifecycle JSONL (shared_lessons.py:1370).

    Each row carries written_count (raw
    appends collapsed by dedupe) and render_count (times the entry was actually
    selected into someone's window) — the only direct evidence of whether a
    gist ever reached another agent, which is the question these runs exist to
    answer.
    """
    _authorize(viewer, board_id)
    out_dir = Path(os.environ.get("BOARD_LIFECYCLE_DIR", "/data/lifecycle"))
    path = out_dir / f"{board_id}.jsonl"
    root = os.path.realpath(out_dir)
    destination = os.path.realpath(path)
    if destination == root or not destination.startswith(os.path.join(root, "")):
        raise HTTPException(status_code=400, detail="lifecycle path outside export directory")
    out_dir.mkdir(parents=True, exist_ok=True)
    await STATE.board(board_id).write_lifecycle_summary(Path(destination))
    return {"board_id": board_id, "path": str(path)}


@app.get("/board/{board_id}/read_all")
async def get_read_all(board_id: str, viewer: str = Query(...)) -> Dict[str, Any]:
    """Diagnostic: return every raw entry. Not for agent consumption."""
    _authorize(viewer, board_id)
    b = STATE.board(board_id)
    entries = await b.read_all()
    return {"board_id": board_id, "count": len(entries), "entries": entries}


@app.get("/board/{board_id}/grep")
async def get_grep(
    board_id: str,
    viewer: str = Query(..., description="Agent identity of the reader"),
    words: str = Query(
        "",
        description="Optional boolean expression: '|' OR, '&' AND, '()' grouping. "
                    "e.g. (parser|lexer)&crash. Omit to filter by type alone; "
                    "at least one of words/types is required.",
    ),
    limit: int = Query(_GREP_DEFAULT_LIMIT, ge=1, le=_GREP_MAX_LIMIT),
    types: str = Query("", description="Optional type filter, '|' separated (e.g. FAIL|FACT)"),
) -> Dict[str, Any]:
    """Search the FULL run history for gists whose content matches any term.

    Every other read path (board_read, the turn-start delta, the peer digest)
    serves SharedLessons._entries, which is trimmed to MAX_BOARD_ENTRIES at the
    append site. board_gists is append-only and never trimmed, so this queries
    the table directly -- that is the entire point of the endpoint, and the
    reason it must not be "optimised" into a scan of _entries.

    A 32-worker run writes ~12.7k gists, so board_read covers only about a
    sixth of the run and an agent asking "has anyone tried this?" would be
    answered from a sixth of the evidence.

    content only -- not detail. The gist is what its author wrote to be read by
    peers; detail is unbounded backing text whose incidental vocabulary would
    swamp the results. Grep for the gist, then board_unfold its label.
    """
    _authorize(viewer, board_id)

    # Boolean expression, parsed by gquery (see that module for the grammar and
    # for why it is a parser rather than a flat ',' / '&' split: brackets would
    # not be special, so `(parser|lexer)` would be searched as a LITERAL string
    # and return a confident wrong answer).
    node = None
    if (words or "").strip():
        try:
            node = gquery.parse(words)
        except gquery.QueryError as e:
            raise HTTPException(status_code=400, detail=f"bad `words` expression: {e}")
        n_terms = gquery.count_terms(node)
        if n_terms > _GREP_MAX_TERMS:
            raise HTTPException(
                status_code=400,
                detail=f"`words` has {n_terms} terms; the limit is {_GREP_MAX_TERMS}",
            )

    try:
        type_filter = gquery.parse_type_list(types, VALID_TYPES)
    except gquery.QueryError as e:
        raise HTTPException(status_code=400, detail=f"bad `types` filter: {e}")

    # Either alone is a legitimate query ("every FAIL on this board"); both
    # empty would return the entire history, which is a footgun not a search.
    if node is None and not type_filter:
        raise HTTPException(
            status_code=400,
            detail="provide words and/or types; both empty would return the whole board",
        )

    # LIKE metacharacters in a caller's term must match literally. Without this
    # a single "%" matches every row and silently returns the whole board --
    # the opposite of a search. ESCAPE '\' is stated explicitly because MySQL's
    # default depends on NO_BACKSLASH_ESCAPES.
    def _lit(term: str) -> str:
        out = term.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
        return f"%{out}%"

    where = ["board_id=%s"]
    params: List[Any] = [board_id]
    if node is not None:
        frag, ps = gquery.compile_sql(node, _lit)
        where.append(frag)
        params.extend(ps)
    if type_filter:
        where.append("type IN (" + ",".join(["%s"] * len(type_filter)) + ")")
        params.extend(type_filter)
    where_sql = " AND ".join(where)

    async with STATE.pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # True total, independent of `limit`: a caller that only sees the
            # capped page still learns how much it did not see, so truncation
            # is never silent.
            await cur.execute(f"SELECT COUNT(*) AS n FROM board_gists WHERE {where_sql}", params)
            row = await cur.fetchone()
            total = int((row or {}).get("n", 0))
            await cur.execute(
                "SELECT id, board_id, thread_id, type, content, delegation_id, ts_epoch, "
                "(detail IS NOT NULL AND detail <> '') AS has_detail "
                f"FROM board_gists WHERE {where_sql} ORDER BY id DESC LIMIT %s",
                params + [int(limit)],
            )
            rows = await cur.fetchall() or []

    # Selection is newest-first (ORDER BY id DESC LIMIT n) so a truncated query
    # keeps the MOST RECENT matches. Presentation is the reverse: board_gists.id
    # is monotonic, so ascending id is chronological, and a reader following a
    # sequence of events wants them in the order they happened. Every other
    # board path already delivers ascending (pending sorts by gist id), so this
    # makes grep consistent with them.
    rows = list(reversed(rows))

    entries = [
        {
            "id": int(r["id"]),
            "label": f"G{int(r['id'])}",
            "thread_id": r["thread_id"],
            "type": r["type"],
            "content": r["content"],
            "delegation_id": r.get("delegation_id"),
            "ts_epoch": float(r["ts_epoch"]) if r.get("ts_epoch") is not None else None,
        }
        for r in rows
    ]

    # Render with the SAME formatter every other board path uses, so a gist
    # looks identical whether it arrives in the turn-start block, mid-turn, from
    # board_read, or from a grep hit. Two copies of the format would drift the
    # first time either was touched, and the drift is invisible: both keep
    # emitting plausible lines and nothing fails.
    #
    # format_for_prompt groups by type ([Patch summaries] / [Active claims] /
    # [Shared lessons]); `rows` is already ascending by id, so each group stays
    # in chronological order.
    b = STATE.board(board_id)
    render_entries = [
        {
            "ts": float(r["ts_epoch"]) if r.get("ts_epoch") is not None else 0.0,
            "thread_id": r["thread_id"],
            "type": r["type"],
            "content": r["content"],
            "delegation_id": r.get("delegation_id"),
            "_expires_at": None,   # grep is history: never age a hit out of the result
            "_label": f"G{int(r['id'])}",
            "_has_detail": bool(r.get("has_detail")),
        }
        for r in rows
    ]
    try:
        rendered = b.format_for_prompt(render_entries)
        # format_entry_line emits no id by design, so labels ride in the same
        # trailing index board_read and the mid-turn path use. Without it a grep
        # hit could not be board_unfold-ed -- the agent would see the gist and
        # have no handle for the detail behind it.
        idx = unfold_mod.render_index(render_entries)
        if idx:
            rendered = rendered + "\n\n" + idx
    except Exception:  # noqa: BLE001 -- never fail a search over formatting
        rendered = ""
    out: Dict[str, Any] = {
        "board_id": board_id,
        "words": words,
        "total": total,
        "returned": len(entries),
        "truncated": total > len(entries),
        "rendered": rendered,
        "entries": entries,
    }
    return out


@app.get("/snapshot")
async def get_snapshot(
    viewer: str = Query(..., description="Agent identity of the reader"),
    boards: str = Query(..., description="Comma-separated board ids"),
    # 0 = unlimited (ship the whole board). The lower bound must allow 0, or
    # the router's request for the full board would 422. See
    # shared_lessons._select_entries.
    window_tokens: int = Query(1000, ge=0, le=8000),
    render_mode: Optional[str] = Query(None),
    role: str = Query("implementer"),
    self_policy: str = Query("include"),
    step: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Render several boards from a single consistent read point.

    This is what the mini-router calls to build a prompt prefix for an agent
    that sits on more than one board. Authorization is checked for EVERY board
    up front: a viewer who cannot read one of them gets a 403 rather than a
    quietly-truncated view, so board tiering stays a real boundary.

    Every render mode goes through a `*_from(snap)` seam, so the tiered case
    gets the same consistency guarantee as the flat one.
    """
    board_ids = [b.strip() for b in (boards or "").split(",") if b.strip()]
    if not board_ids:
        raise HTTPException(status_code=400, detail="boards must be non-empty")
    mode = render_mode or DEFAULT_RENDER_MODE
    if mode not in VALID_RENDER_MODES:
        raise HTTPException(status_code=400, detail=f"unknown render_mode {mode!r}")
    for bid in board_ids:
        _authorize(viewer, bid)

    snaps, at = await STATE.snapshot_many(board_ids)
    is_planner = role == "planner"
    out: Dict[str, Any] = {}
    for bid in board_ids:
        b = STATE.board(bid)
        snap = snaps[bid]
        stats: Dict[str, Any] = {}
        # Must be reset per board: it is only assigned in the "full" branch, so
        # without this it would leak the previous board's entries into this
        # board's watermark.
        rendered_entries: Optional[List[Dict[str, Any]]] = None

        if mode == "full":
            # The turn-start block is a DELTA, not the whole board.
            #
            # An agent already holds every earlier entry in previous turns of its
            # context; re-rendering the full board each turn would spend context
            # on a duplicate and force a cap on FACT/OBSERVED entries.
            #
            # PATCH_SUMMARY gets no exemption. It is latest-wins state rather
            # than an event, but re-sending it in FULL every turn would be most
            # of the block's cost: at 16 workers it grows to tens of thousands
            # of tokens per turn, and cumulative board text passes twice the
            # 272k window, forcing the compaction that destroys the very
            # earlier turns this delta design depends on.
            #
            # Safe because latest-wins writes a REVISED summary with a new, higher
            # board_gists.id, which clears any cursor that had seen the original,
            # so revisions still propagate. What an agent loses is the implicit
            # complete fix-set; board_read returns it on demand (a few thousand
            # tokens) and the prompt already points there.
            #
            # RECOVERY: after a session compaction the earlier turns are gone and
            # this delta cannot bring them back. board_read returns the full
            # board on demand and the prompt tells agents to call it; that is the
            # only path back to older FACT/FAIL/CLAIM.
            if not is_planner:
                _cur = await _get_board_cursor(viewer, bid)
                snap = [e for e in snap if _gist_id(e) > _cur]
            entries, stats = b._select_entries(
                snap,
                window_tokens=window_tokens,
                viewer_thread_id=None if is_planner else viewer,
                self_policy="include" if is_planner else self_policy,
            )
            rendered = b.format_for_prompt(entries)
            stats = dict(stats)
            stats["rendered_chars_actual"] = len(rendered)
            idx = unfold_mod.render_index(entries)
            if idx:
                rendered = rendered + "\n\n" + idx
            rendered_entries = entries
        elif mode == "patch_selective_unfold":
            rendered = b.render_patch_selective_unfold_from(snap)
        elif mode in ("patch_digest_local_only", "patch_clean_local_only",
                      "patch_clean_delayed_local"):
            if is_planner or (mode == "patch_clean_delayed_local"
                              and step < PATCH_CLEAN_DELAY_STEPS):
                rendered = ""
            else:
                rendered = b.render_peer_digest_from(
                    snap, window_tokens=window_tokens, viewer_thread_id=viewer,
                    allowed_types=("PATCH_SUMMARY",),
                    patch_requires_no_fail=(mode != "patch_digest_local_only"),
                )
        else:
            allowed, fail_grounded = _digest_filters(mode, is_planner)
            rendered = b.render_peer_digest_from(
                snap, window_tokens=window_tokens, viewer_thread_id=viewer,
                allowed_types=allowed,
                fail_requires_finalized_patch=fail_grounded,
            )
        out[bid] = {"rendered": rendered, "stats": stats}

        # Anchor this agent's mid-turn watermark to what actually reached
        # its prompt. Everything at or below is now in the context window, so
        # /pending must not inject it again -- "newly arrived" means created
        # AFTER this snapshot.
        #
        # Basis is the RENDERED entries in full mode: an entry dropped by the
        # token budget never reached the agent, so it must stay deliverable.
        # Digest modes have no per-entry render list, so the snapshot is the
        # honest basis there -- the agent saw a summary of it, and treating it
        # as unseen would flood the next tool call with the whole board.
        try:
            basis = rendered_entries if rendered_entries is not None else snap
            await _advance_board_cursor(
                viewer, bid, max((_gist_id(e) for e in basis), default=0)
            )
        except Exception:  # noqa: BLE001 -- never fail a prompt render over a cursor
            pass
    return {"viewer": viewer, "snapshot_at": at, "render_mode": mode, "boards": out}


def _digest_filters(mode: str, is_planner: bool):
    """allowed_types + fail_requires_finalized_patch for the digest modes."""
    if mode == "peer_digest":
        return None, False
    if mode == "patch_digest" or is_planner:
        return ("PATCH_SUMMARY",), False
    if mode == "patch_fail_digest":
        return ("PATCH_SUMMARY", "FAIL"), True
    if mode == "patch_evidence_digest":
        return ("PATCH_SUMMARY", "OBSERVED", "FACT"), False
    return None, False


@app.get("/board/{board_id}/unfold")
async def get_unfold(
    board_id: str,
    viewer: str = Query(...),
    labels: str = Query(..., description="Comma-separated, e.g. 'G12,G7.2'"),
    depth: str = Query(
        "raw",
        description="'raw' (S->raw, the default) or 'summary' (G->S, diagnostics only)",
    ),
) -> Dict[str, Any]:
    """Expand gists into their backing detail — the paper's selective unfolding.

    Read-only by construction. Nothing here writes to the board, which is the
    paper's guarantee that unfolded content stays "local to the requesting call"
    (A.2) and that peers keep observing only the gist layer.

    depth defaults to 'raw': every unfold an agent makes is a raw unfold. The
    'summary' hop (G->S) is retained for diagnostics but is not reachable
    from the agent surface -- mcp-board pins depth=raw, and render_index
    advertises only base labels, so nothing enumerates the G12.1/G12.2
    sub-chunks a summary would list, and agents in practice only ever ask for
    raw.
    """
    _authorize(viewer, board_id)
    if depth not in ("summary", "raw"):
        raise HTTPException(status_code=400, detail="depth must be 'summary' or 'raw'")
    req = [l for l in (labels or "").split(",") if l.strip()]
    if not req:
        raise HTTPException(status_code=400, detail="labels must be non-empty")
    out = unfold_mod.unfold(req, STATE.details.get(board_id, {}), depth=depth)
    return {"board_id": board_id, **out}


# ---- queue endpoints -----------------------------------------------------
@app.post("/queue/{queue_id}/enqueue")
async def post_enqueue(queue_id: str, item: EnqueueIn) -> Dict[str, Any]:
    now = time.time()
    async with STATE.pool.acquire() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute(
                    "INSERT INTO board_queue_tasks "
                    "(queue_id, task_id, description, deps, state, enqueued_at) "
                    "VALUES (%s,%s,%s,%s,'pending',%s)",
                    (queue_id, item.task_id, item.description,
                     ",".join(item.deps), now),
                )
            except aiomysql.IntegrityError:
                raise HTTPException(
                    status_code=409, detail=f"task {item.task_id} already enqueued"
                )
    return {"queue_id": queue_id, "task_id": item.task_id, "state": "pending"}


@app.post("/queue/{queue_id}/claim")
async def post_claim(queue_id: str, req: ClaimIn) -> Optional[Dict[str, Any]]:
    """Atomically claim the oldest ready (deps-satisfied) pending task."""
    now = time.time()
    async with STATE.pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # 1) Find all pending tasks and completed task_ids, then pick
            #    the oldest pending whose deps are all satisfied.
            #    Doing this in SQL cleanly is awkward with a CSV deps col;
            #    we do the deps join in Python (queues are small — 10s of tasks).
            await cur.execute(
                "SELECT task_id FROM board_queue_tasks "
                "WHERE queue_id=%s AND state='completed'", (queue_id,)
            )
            done = {r["task_id"] for r in await cur.fetchall()}
            await cur.execute(
                "SELECT id, task_id, description, deps FROM board_queue_tasks "
                "WHERE queue_id=%s AND state='pending' "
                "ORDER BY enqueued_at ASC", (queue_id,)
            )
            pendings = await cur.fetchall()
            picked = None
            for p in pendings:
                deps = [d for d in (p["deps"] or "").split(",") if d]
                if all(d in done for d in deps):
                    picked = p
                    break
            if picked is None:
                return None
            # 2) Atomic claim: UPDATE ... WHERE state='pending'.
            # If another worker beat us to it, affected_rows=0 → retry.
            await cur.execute(
                "UPDATE board_queue_tasks "
                "SET state='claimed', claimed_by=%s, claimed_at=%s "
                "WHERE id=%s AND state='pending'",
                (req.claimed_by, now, picked["id"]),
            )
            if cur.rowcount == 0:
                # Someone raced us. Recurse — but we simplify: just return null,
                # let the client retry on its next poll.
                return None
    return {
        "queue_id": queue_id,
        "task_id": picked["task_id"],
        "description": picked["description"],
        "deps": [d for d in (picked["deps"] or "").split(",") if d],
        "claimed_by": req.claimed_by,
        "claimed_at": now,
    }


@app.post("/queue/{queue_id}/complete")
async def post_complete(queue_id: str, req: CompleteIn) -> Dict[str, Any]:
    now = time.time()
    if req.state not in ("completed", "failed"):
        raise HTTPException(status_code=400, detail="state must be completed or failed")
    async with STATE.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE board_queue_tasks "
                "SET state=%s, completed_at=%s, result_gist_id=%s "
                "WHERE queue_id=%s AND task_id=%s AND claimed_by=%s "
                "AND state='claimed'",
                (req.state, now, req.result_gist_id, queue_id,
                 req.task_id, req.claimed_by),
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=409,
                    detail=f"task {req.task_id!r} not in claimed state by {req.claimed_by!r}",
                )
    return {"queue_id": queue_id, "task_id": req.task_id, "state": req.state}


@app.get("/queue/{queue_id}/status")
async def get_queue_status(queue_id: str) -> Dict[str, Any]:
    async with STATE.pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT task_id, description, deps, state, claimed_by, "
                "claimed_at, completed_at, result_gist_id "
                "FROM board_queue_tasks WHERE queue_id=%s ORDER BY enqueued_at",
                (queue_id,),
            )
            tasks = await cur.fetchall()
    counts = {"pending": 0, "claimed": 0, "completed": 0, "failed": 0}
    for t in tasks:
        counts[t["state"]] = counts.get(t["state"], 0) + 1
    return {"queue_id": queue_id, "counts": counts, "tasks": tasks}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=LISTEN_PORT, log_level="info")
