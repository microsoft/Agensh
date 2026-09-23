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

# ------------- config ----------------------------------------------------
MYSQL_DSN = os.environ["MYSQL_DSN"]  # e.g. mysql://omcgitea:pw@mysql:3306/omcgitea
LISTEN_PORT = int(os.environ.get("BOARD_LISTEN_PORT", "8660"))
# BOARD_MEMBERS_JSON: '{"pbench-top":["planner","team1-lead",...],
#                      "pbench-team1":["team1-lead","team1-worker1",...]}'
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

# CLAIM TTL. Upstream's default is 300s (shared_lessons.py:24) and CLAIM is
# advisory throughout: never consulted before a write, capped at 2 per
# delegation, and off entirely in DeLM's shipped preset. We keep that
# semantics — a claim says "I am on this now", not "I own this path" — so the
# upstream TTL is the right default. Overridable for experiments.
# 1h: a claim should outlive the work item it describes. See the rationale on
# DEFAULT_CLAIM_TTL_SECONDS in shared_lessons.py.
CLAIM_TTL_SECONDS = float(os.environ.get("BOARD_CLAIM_TTL_SECONDS", "3600"))


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

        A multi-board render (director + team board, in the 2b topology) is
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
        for r in rows:
            b = self.board(r["board_id"])
            gid = int(r["id"])
            detail = r.get("detail")
            if detail:
                self.details.setdefault(r["board_id"], {})[gid] = detail
            # Directly append into _entries (bypassing note()'s verifier)
            # since these gists ALREADY passed the verifier on their first admit.
            b._entries.append({
                "ts": float(r["ts_epoch"]),
                "thread_id": r["thread_id"],
                "type": r["type"],
                "content": r["content"],
                "delegation_id": r.get("delegation_id"),
                "_expires_at": (float(r["expires_at"]) if r["expires_at"] is not None else None),
                "task": r.get("task_instruction") or r["task_id"],
                "_label": f"G{gid}",
                "_has_detail": bool(detail),
            })


STATE = State()


# ------------- FastAPI schemas -------------------------------------------
class NoteIn(BaseModel):
    thread_id: str = Field(..., description="Agent identity, e.g. 'planner' or 'team1-worker3'")
    type: str = Field(..., description="One of FACT/TRIED/OBSERVED/FAIL/CLAIM/PATCH_SUMMARY")
    content: str
    task_id: Optional[str] = None
    # Upstream keys several behaviors on (thread_id, delegation_id) rather than
    # thread alone: the CLAIM cap of 2, the one-PATCH_SUMMARY-per-delegation
    # rule and its latest-wins replacement, and "a FAIL invalidates THIS
    # delegation's own patch summary". Passing None collapses every unit of
    # work an agent ever does into a single bucket, which silently disarms all
    # four. Our analogue is the queue task the agent is working under.
    delegation_id: Optional[str] = None
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
                    entry.get("task"),
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
)


async def _migrate() -> None:
    async with STATE.pool.acquire() as conn:
        async with conn.cursor() as cur:
            for stmt in _MIGRATIONS:
                try:
                    await cur.execute(stmt)
                except Exception:  # noqa: BLE001 — duplicate column is expected
                    pass


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
            STATE.pool = await aiomysql.create_pool(minsize=1, maxsize=8, **kwargs)
            break
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"[board] mysql connect attempt {i + 1} failed: {e}", flush=True)
    if STATE.pool is None:
        raise SystemExit(f"board: cannot reach mysql after retries: {last}")
    await _migrate()
    await STATE.hydrate()


@app.on_event("shutdown")
async def _shutdown() -> None:
    if STATE.pool is not None:
        STATE.pool.close()
        await STATE.pool.wait_closed()


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
    gid = await _persist_gist(board_id, entry, detail=note.detail)
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
    # 0 = unlimited (ship the whole board). The lower bound used to be 100,
    # which would have 422'd the router once it started asking for the full
    # board. See shared_lessons._select_entries and
    # tests/pbench-board/test_full_board.py.
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


class FinalizeIn(BaseModel):
    thread_id: str
    delegation_id: Optional[str] = None
    content: Optional[str] = None


@app.post("/board/{board_id}/finalize")
async def post_finalize(board_id: str, req: FinalizeIn) -> Dict[str, Any]:
    """Mark this delegation's latest PATCH_SUMMARY as an explicit handoff.

    Upstream calls this when an implementer says `finish done`
    (implementer_runner.py:371-411). It is oracle-free — it records only that
    the agent chose to hand off, not that the grader agreed — and it is what
    puts `status=final` in peers' rendered view, which the prompt tells them to
    weight above unfinalized candidates. Without it the whole trust-signal
    layer renders as if nothing were ever completed.
    """
    _authorize(req.thread_id, board_id)
    b = STATE.board(board_id)
    ok = await b.mark_patch_summary_final(
        thread_id=req.thread_id,
        delegation_id=req.delegation_id,
        content=req.content,
    )
    return {"board_id": board_id, "finalized": bool(ok)}


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

    Ported but never called until now. Each row carries written_count (raw
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


@app.get("/snapshot")
async def get_snapshot(
    viewer: str = Query(..., description="Agent identity of the reader"),
    boards: str = Query(..., description="Comma-separated board ids"),
    # 0 = unlimited (ship the whole board). The lower bound used to be 100,
    # which would have 422'd the router once it started asking for the full
    # board. See shared_lessons._select_entries and
    # tests/pbench-board/test_full_board.py.
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
    quietly-truncated view, so the 2b tiering stays a real boundary.

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

        if mode == "full":
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
    depth: str = Query("summary", description="'summary' (G->S) or 'raw' (S->raw)"),
) -> Dict[str, Any]:
    """Expand gists into their backing detail — the paper's selective unfolding.

    Read-only by construction. Nothing here writes to the board, which is the
    paper's guarantee that unfolded content stays "local to the requesting call"
    (A.2) and that peers keep observing only the gist layer.
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
