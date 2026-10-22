# Serve shared context over HTTP, persisting every admitted gist in MySQL.
# Turn-start snapshots and MCP notices share delivery cursors; the recent board
# is an in-memory view, while grep searches the complete persisted history.

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
from verifier import verify_note
import unfold as unfold_mod
import gquery

MYSQL_DSN = os.environ["MYSQL_DSN"]
LISTEN_PORT = int(os.environ.get("BOARD_LISTEN_PORT", "8660"))
_MEMBERS_ENV = os.environ.get("BOARD_MEMBERS_JSON", "").strip()
BOARD_MEMBERS: Dict[str, set] = {}
if _MEMBERS_ENV:
    try:
        BOARD_MEMBERS = {k: set(v) for k, v in json.loads(_MEMBERS_ENV).items()}
    except Exception as e:
        raise SystemExit(f"invalid BOARD_MEMBERS_JSON: {e}")

BOARD_OPERATOR = os.environ.get("BOARD_OPERATOR", "harness")

_GREP_DEFAULT_LIMIT = int(os.environ.get("BOARD_GREP_DEFAULT_LIMIT", "500"))
_GREP_MAX_LIMIT = int(os.environ.get("BOARD_GREP_MAX_LIMIT", "500"))
_GREP_MAX_TERMS = int(os.environ.get("BOARD_GREP_MAX_TERMS", "50"))

CLAIM_TTL_SECONDS = float(os.environ.get("BOARD_CLAIM_TTL_SECONDS", "3600"))

PENDING_LEASE_SECONDS = 30.0


def _parse_dsn(dsn: str) -> Dict[str, Any]:
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


class State:
    # Recent render state and long details are rebuilt from the database at startup.
    def __init__(self) -> None:
        self.pool: Optional[aiomysql.Pool] = None
        self.boards: Dict[str, SharedLessons] = {}
        self.details: Dict[str, Dict[int, str]] = {}
        self.write_locks: Dict[str, asyncio.Lock] = {}

    def write_lock(self, board_id: str) -> asyncio.Lock:
        return self.write_locks.setdefault(board_id, asyncio.Lock())

    def board(self, board_id: str) -> SharedLessons:
        b = self.boards.get(board_id)
        if b is None:
            b = SharedLessons(
                task_id=board_id,
            )
            self.boards[board_id] = b
        return b

    async def snapshot_many(
        self, board_ids: List[str]
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], float]:
        ordered = sorted(set(board_ids))
        # Acquire board locks in a fixed order to avoid multi-board deadlocks.
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
        # Replay admission rules so patch replacement and failure status survive restarts.
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT id, board_id, thread_id, type, content, "
                    "ts_epoch, expires_at, delegation_id, detail "
                    "FROM board_gists ORDER BY id"
                )
                rows = await cur.fetchall()
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
            b._admit(entry)

        for bid, ts0 in earliest.items():
            b = self.boards.get(bid)
            if b is not None:
                b._start_time = min(b._start_time, ts0)


STATE = State()


class NoteIn(BaseModel):
    thread_id: str = Field(..., description="Agent identity, e.g. 'pbench-worker3'")
    type: str = Field(..., description="One of FACT/OBSERVED/FAIL/CLAIM/PATCH_SUMMARY")
    content: str
    delegation_id: Optional[str] = Field(None, max_length=128)
    ttl_seconds: Optional[float] = None
    detail: Optional[str] = None


class NoteOut(BaseModel):
    status: str
    reason: Optional[str] = None
    gist_id: Optional[int] = None
    label: Optional[str] = None


def _authorize(agent: str, board_id: str) -> None:
    # Board membership uses the caller's identity within the private service network.
    if not BOARD_MEMBERS:
        return
    if agent == BOARD_OPERATOR:
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
    # Persist a new row even when the recent view replaces an older patch summary.
    async with STATE.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO board_gists "
                "(board_id, thread_id, type, content, ts_epoch, expires_at, "
                " delegation_id, detail) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    board_id,
                    entry["thread_id"],
                    entry["type"],
                    entry["content"],
                    entry["ts"],
                    entry.get("_expires_at"),
                    entry.get("delegation_id"),
                    detail,
                ),
            )
            return int(cur.lastrowid)


_MIGRATIONS = (
    "ALTER TABLE board_gists ADD COLUMN delegation_id VARCHAR(128) NULL",
    "ALTER TABLE board_gists ADD COLUMN detail LONGTEXT NULL",
    """CREATE TABLE IF NOT EXISTS shown (
         event_id BIGINT NOT NULL,
         agent VARCHAR(128) NOT NULL,
         shown_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
         PRIMARY KEY (event_id, agent),
         KEY ix_agent (agent)
       ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS pending_leases (
         agent VARCHAR(128) NOT NULL,
         lease_token CHAR(32) NOT NULL,
         lease_until DOUBLE NOT NULL,
         PRIMARY KEY (agent),
         KEY ix_lease_until (lease_until)
       ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
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
    lab = entry.get("_label")
    if isinstance(lab, str) and lab.startswith("G") and lab[1:].isdigit():
        return int(lab[1:])
    return 0


def _agent_boards(agent: str) -> List[str]:
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
    if gist_id <= 0:
        return
    # Concurrent snapshot and shim acknowledgements must never move a cursor back.
    async with STATE.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO board_cursor (agent, board_id, gist_id) VALUES (%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE gist_id = GREATEST(gist_id, VALUES(gist_id))",
                (agent, board_id, int(gist_id)),
            )
        await conn.commit()


async def _claim_pending_lease(agent: str) -> Optional[str]:
    # One short lease prevents simultaneous MCP wrappers from draining the same notices.
    token = secrets.token_hex(16)
    now = time.time()
    until = now + PENDING_LEASE_SECONDS
    acquired = False
    async with STATE.pool.acquire() as conn:
        async with conn.cursor() as cur:
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
    # An expired holder cannot release a newer wrapper's lease.
    async with STATE.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM pending_leases WHERE agent=%s AND lease_token=%s",
                (agent, token),
            )
        await conn.commit()


async def _migrate() -> None:
    # Compatibility DDL is best-effort; fresh tables are seeded by mini-router/sql/.
    async with STATE.pool.acquire() as conn:
        async with conn.cursor() as cur:
            for stmt in _MIGRATIONS:
                try:
                    await cur.execute(stmt)
                except Exception:
                    pass


app = FastAPI(title="omcgitea-board", version="0.1.0")


@app.on_event("startup")
async def _startup() -> None:
    kwargs = _parse_dsn(MYSQL_DSN)
    delays = [1, 2, 3, 5, 8, 13, 21]
    last: Exception | None = None
    for i, d in enumerate([0, *delays]):
        if d:
            await asyncio.sleep(d)
        try:
            _pool_max = int(os.environ.get("BOARD_MYSQL_POOL_MAX", "32"))
            STATE.pool = await aiomysql.create_pool(
                minsize=1, maxsize=_pool_max, **kwargs)
            break
        except Exception as e:
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


@app.get("/pending/{agent}")
async def get_pending(agent: str, limit: int = 50) -> Dict[str, Any]:
    # Only DMs and peer gists interrupt a turn; channel messages stay in the queue.
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
        except Exception:
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

    for bid, cursor in cursors.items():
        try:
            snap = list(STATE.board(bid)._entries)
        except Exception:
            continue
        fresh = [e for e in snap
                 if _gist_id(e) > cursor and e.get("thread_id") != agent]
        fresh.sort(key=_gist_id)
        b = STATE.board(bid)
        rendered: List[Dict[str, Any]] = []
        for e in fresh:
            try:
                line = b.format_entry_line(e, now_ts)
            except Exception:
                break
            notices.append({"id": f"g{_gist_id(e)}", "text": line})
            rendered.append(e)

        try:
            idx = unfold_mod.render_index(rendered)
        except Exception:
            idx = ""
        if idx:
            notices.append({"id": f"bx-{bid}", "text": idx})

    if not notices:
        await _release_pending_lease(agent, lease_token)
        return {"agent": agent, "notices": []}
    return {"agent": agent, "notices": notices, "lease_token": lease_token}


@app.post("/shown/{agent}")
async def post_shown(agent: str, body: Dict[str, Any]) -> Dict[str, Any]:
    # e-prefixed IDs acknowledge queue events; g-prefixed IDs advance board cursors.
    raw = (body or {}).get("ids", [])
    lease_token = (body or {}).get("lease_token")
    if not isinstance(lease_token, str) or re.fullmatch(r"[0-9a-f]{32}", lease_token) is None:
        lease_token = None
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
        await _release_pending_lease(agent, lease_token)
    return {"recorded": len(event_ids) + len(gist_ids)}


@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    return {"ok": True, "boards": list(STATE.boards.keys())}


@app.post("/board/{board_id}/note", response_model=NoteOut)
async def post_note(board_id: str, note: NoteIn) -> NoteOut:
    _authorize(note.thread_id, board_id)
    clean, status = verify_note({"type": note.type, "content": note.content})
    if clean is None:
        return NoteOut(status="rejected", reason=status)
    b = STATE.board(board_id)
    async with STATE.write_lock(board_id):
        # Keep admission, persisted ID assignment and detail caching ordered per board.
        entry = await b.note(
            thread_id=note.thread_id,
            type=clean["type"],
            content=clean["content"],
            delegation_id=note.delegation_id,
            ttl_seconds=(
                note.ttl_seconds
                if note.ttl_seconds is not None
                else (CLAIM_TTL_SECONDS if clean["type"] == "CLAIM" else None)
            ),
        )
        if entry is None:
            return NoteOut(status="rejected", reason="admission-filter")
        gid = await _persist_gist(board_id, entry, detail=note.detail)
        entry["_label"] = f"G{gid}"
        entry["_has_detail"] = bool(note.detail)
        if note.detail:
            STATE.details.setdefault(board_id, {})[gid] = note.detail
    return NoteOut(status="admitted", gist_id=gid, label=f"G{gid}")


@app.get("/board/{board_id}/read")
async def get_read(
    board_id: str,
    viewer: str = Query(..., description="Agent identity of the reader"),
) -> Dict[str, Any]:
    _authorize(viewer, board_id)
    board = STATE.board(board_id)
    entries = await board.read()
    rendered = board.format_for_prompt(entries)
    index = unfold_mod.render_index(entries)
    if index:
        rendered += "\n\n" + index
    return {"board_id": board_id, "rendered": rendered}


@app.post("/board/{board_id}/lifecycle")
async def post_lifecycle(board_id: str, viewer: str = Query(...)) -> Dict[str, Any]:
    _authorize(viewer, board_id)
    out_dir = Path(os.environ.get("BOARD_LIFECYCLE_DIR", "/data/lifecycle"))
    path = out_dir / f"{board_id}.jsonl"
    root = os.path.realpath(out_dir)
    # Resolve symlinks before creating anything so exports stay under the configured root.
    destination = os.path.realpath(path)
    if destination == root or not destination.startswith(os.path.join(root, "")):
        raise HTTPException(status_code=400, detail="lifecycle path outside export directory")
    out_dir.mkdir(parents=True, exist_ok=True)
    await STATE.board(board_id).write_lifecycle_summary(Path(destination))
    return {"board_id": board_id, "path": str(path)}


@app.get("/board/{board_id}/read_all")
async def get_read_all(board_id: str, viewer: str = Query(...)) -> Dict[str, Any]:
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
    _authorize(viewer, board_id)

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

    if node is None and not type_filter:
        raise HTTPException(
            status_code=400,
            detail="provide words and/or types; both empty would return the whole board",
        )

    def _lit(term: str) -> str:
        # Search terms are literal substrings, including SQL LIKE wildcard characters.
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

    # Fetch the newest matches, then render that window in chronological order.
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

    b = STATE.board(board_id)
    render_entries = [
        {
            "ts": float(r["ts_epoch"]) if r.get("ts_epoch") is not None else 0.0,
            "thread_id": r["thread_id"],
            "type": r["type"],
            "content": r["content"],
            "delegation_id": r.get("delegation_id"),
            "_expires_at": None,
            "_label": f"G{int(r['id'])}",
            "_has_detail": bool(r.get("has_detail")),
        }
        for r in rows
    ]
    try:
        rendered = b.format_for_prompt(render_entries)
        idx = unfold_mod.render_index(render_entries)
        if idx:
            rendered = rendered + "\n\n" + idx
    except Exception:
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
) -> Dict[str, Any]:
    board_ids = [b.strip() for b in (boards or "").split(",") if b.strip()]
    if not board_ids:
        raise HTTPException(status_code=400, detail="boards must be non-empty")
    for bid in board_ids:
        _authorize(viewer, bid)

    snaps, at = await STATE.snapshot_many(board_ids)
    # Turn starts consume unread gists; explicit board_read returns the live view.
    out: Dict[str, Any] = {}
    for bid in board_ids:
        b = STATE.board(bid)
        snap = snaps[bid]
        _cur = await _get_board_cursor(viewer, bid)
        snap = [e for e in snap if _gist_id(e) > _cur]
        entries = b._select_entries(snap)
        rendered = b.format_for_prompt(entries)
        idx = unfold_mod.render_index(entries)
        if idx:
            rendered = rendered + "\n\n" + idx
        out[bid] = {"rendered": rendered}

        try:
            await _advance_board_cursor(
                viewer, bid, max((_gist_id(e) for e in entries), default=0)
            )
        except Exception:
            pass
    return {"viewer": viewer, "snapshot_at": at, "boards": out}


@app.get("/board/{board_id}/unfold")
async def get_unfold(
    board_id: str,
    viewer: str = Query(...),
    labels: str = Query(..., description="Comma-separated gist labels, e.g. G12,G7"),
) -> Dict[str, Any]:
    _authorize(viewer, board_id)
    requested = [label for label in labels.split(",") if label.strip()]
    if not requested:
        raise HTTPException(status_code=400, detail="labels must be non-empty")
    return {"board_id": board_id, **unfold_mod.unfold(requested, STATE.details.get(board_id, {}))}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=LISTEN_PORT, log_level="info")
