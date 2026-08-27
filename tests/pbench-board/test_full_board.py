#!/usr/bin/env python3
"""test_full_board.py — a dispatch must carry the WHOLE board, not a window.

WHY
Measured on sweep 6.3: 91 overlap incidents across 20 tasks, 169,566 wasted
lines. In 82 of them the second agent never saw a CLAIM on work a peer was
already doing.

The board is only re-rendered when the mini-router dispatches a UEM
(board_client.ts:9), and these agents run hundreds of autonomous turns per
dispatch. Chroma, one 6-hour run: the lead got 1 board view in 441 turns;
worker2's last view of the entire run was at +13.9m; worker4 had a 282-minute
blackout. Sixteen peer CLAIM lines were rendered team-wide, all run, all agents.

On top of that rarity the render was *windowed*: 1500 tokens and at most
_MAX_RENDERED_CLAIMS=6 claims, chosen by priority. So two different dispatches
could show two different subsets, and an absent CLAIM was ambiguous between
"nobody claimed this" and "it was dropped by the window / aged out of TTL".
That ambiguity is fatal to the rule the lead is given — "a fresh CLAIM means
they are mid-implementation, not stuck" — because absence carries no
information.

A whole run's board is small: chroma wrote 126 entries in 6 hours, about 4,095
tokens at the 100-char content cap. Shipping all of it makes absence mean
absence.

This does NOT fix render frequency, which is the larger defect. It makes what
we do render complete and monotone.

Usage: python3 tests/pbench-board/test_full_board.py
"""
import asyncio
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "board-service"))

import shared_lessons as sl  # noqa: E402

rc = 0


def ok(msg):
    print(f"PASS {msg}")


def fail(msg):
    global rc
    print(f"FAIL {msg}")
    rc = 1


def build_board(n_claims=12, n_facts=40):
    """A board busier than the 6-claim cap and wider than a 1500-token window.

    Entries are appended in the same shape main.py uses (main.py:210), with
    CLAIMs given a far-future expiry so this test measures the RENDER window
    and not TTL expiry.
    """
    b = sl.SharedLessons("demo-task")
    now = 1_800_000_000.0
    for i in range(n_facts):
        b._entries.append({
            "ts": now + i, "thread_id": f"worker{i % 4 + 1}", "type": "FACT",
            "content": f"fact number {i} about module {i} " + "x" * 40,
            "delegation_id": None, "_expires_at": None,
            "task": "demo", "_label": f"G{i}", "_has_detail": False,
        })
    for i in range(n_claims):
        b._entries.append({
            "ts": now + 1000 + i, "thread_id": f"worker{i % 4 + 1}", "type": "CLAIM",
            "content": f"implementing module {i} on branch worker/module-{i}",
            "delegation_id": None, "_expires_at": now + 10**9,
            "task": "demo", "_label": f"C{i}", "_has_detail": False,
        })
    return b


def rendered(board, **kw):
    return asyncio.run(board.render(**kw))


# --- 1. unlimited mode must exist and must show every CLAIM -----------------
board = build_board()
try:
    full = rendered(board, window_tokens=0)
except SystemExit:
    raise
except Exception as e:  # noqa: BLE001
    full = ""
    fail(f"window_tokens=0 (unlimited) raised {type(e).__name__}: {e}")

claims_shown = full.count("/CLAIM")
if claims_shown >= 12:
    ok(f"unlimited render shows every CLAIM ({claims_shown}/12)")
else:
    fail(f"unlimited render dropped CLAIMs: {claims_shown}/12 shown")

# --- 2. it must not silently truncate the durable entries either ------------
facts_shown = full.count("/FACT")
if facts_shown >= 40:
    ok(f"unlimited render shows every FACT ({facts_shown}/40)")
else:
    fail(f"unlimited render dropped FACTs: {facts_shown}/40 shown")

# --- 3. an explicit budget must still be honoured (no regression) -----------
windowed = rendered(board, window_tokens=1500)
if len(windowed) < len(full):
    ok("an explicit window_tokens budget still narrows the render")
else:
    fail("window_tokens=1500 no longer narrows anything — budget path broke")

# --- 4. absence must mean absence: same board, same render twice ------------
again = rendered(board, window_tokens=0)
if again == full:
    ok("unlimited render is deterministic (absence means absence)")
else:
    fail("unlimited render is not stable across calls")

# --- 5. the HTTP layer must ACCEPT 0 ---------------------------------------
# This is the trap: the endpoints validated `ge=100`, so the moment the router
# started asking for the whole board every read would 422 and the board would
# go completely dark — strictly worse than the window it replaced.
main_py = (ROOT / "board-service" / "main.py").read_text()
bad = main_py.count("Query(1000, ge=100")
if bad == 0:
    ok("board-service accepts window_tokens=0 (no ge=100 lower bound left)")
else:
    fail(f"{bad} endpoint(s) still reject window_tokens=0 with ge=100 -> board would 422")

# --- 6. the router must actually ASK for the whole board -------------------
client_ts = (ROOT / "mini-router" / "src" / "board_client.ts").read_text()
if "opts.windowTokens ?? 0" in client_ts:
    ok("mini-router defaults to the whole board")
else:
    fail("mini-router still defaults to a windowed render")

sys.exit(rc)
