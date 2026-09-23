#!/usr/bin/env bash
# End-to-end smoke test for board-service against a real MySQL container.
# Spins up a throwaway mysql + board-service (both from images built by this
# repo), runs a battery of curl requests, verifies the responses match
# expectations for the DeLM verifier + windowing logic.
#
# Requires: sudo docker, curl, jq. Runs as root inside its own throwaway
# docker network to avoid colliding with any live pbench profile.
set -u
PROJECT="omcgitea-board-smoke-$(openssl rand -hex 8)"
NET="$PROJECT-net"
BOARD_IMAGE="$PROJECT:test"
CREATED_MYSQL=0
CREATED_BOARD=0
CREATED_NETWORK=0
MYSQL_PW="smoke_$(openssl rand -hex 8)"
BOARD_PORT=$((RANDOM % 20000 + 30000))
MYSQL_PORT=$((RANDOM % 20000 + 30000))
LOG=/tmp/$PROJECT.log
: > "$LOG"

cleanup() {
    [ "$CREATED_BOARD" = 0 ] || sudo docker rm -f "$PROJECT-board" >/dev/null 2>&1 || true
    [ "$CREATED_MYSQL" = 0 ] || sudo docker rm -fv "$PROJECT-mysql" >/dev/null 2>&1 || true
    [ "$CREATED_NETWORK" = 0 ] || sudo docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
say()  { echo "[test $(date -u +%H:%M:%S)] $*" | tee -a "$LOG"; }

# --- 1. Build this checkout under a tag owned by this test run ---------------
say "building $BOARD_IMAGE"
sudo docker build -t "$BOARD_IMAGE" \
    "$(cd "$(dirname "$0")/../../board-service" && pwd)" \
    >>"$LOG" 2>&1 || fail "build board-service"

# --- 2. Ephemeral network + mysql -----------------------------------------
sudo docker network create "$NET" >/dev/null || fail "docker network create"
CREATED_NETWORK=1
say "starting mysql on host port $MYSQL_PORT"
sudo docker run -d --name "$PROJECT-mysql" --network "$NET" \
    -e MYSQL_ROOT_PASSWORD="$MYSQL_PW" \
    -e MYSQL_DATABASE=omcgitea \
    -e MYSQL_USER=omcgitea \
    -e MYSQL_PASSWORD="$MYSQL_PW" \
    -v "$(cd "$(dirname "$0")/../../mini-router/sql" && pwd):/docker-entrypoint-initdb.d:ro" \
    -p "127.0.0.1:$MYSQL_PORT:3306" \
    mysql:8.4 >/dev/null || fail "docker run mysql"
CREATED_MYSQL=1

# Wait for mysql
for i in $(seq 1 40); do
    if sudo docker exec "$PROJECT-mysql" mysqladmin -uroot -p"$MYSQL_PW" ping >/dev/null 2>&1; then
        say "mysql ready in ${i}s"
        break
    fi
    sleep 3
done
sudo docker exec "$PROJECT-mysql" mysqladmin -uroot -p"$MYSQL_PW" ping >/dev/null 2>&1 \
    || fail "mysql never came up"

# --- 3. Start board-service -----------------------------------------------
say "starting board-service on host port $BOARD_PORT"
sudo docker run -d --name "$PROJECT-board" --network "$NET" \
    -e MYSQL_DSN="mysql://omcgitea:$MYSQL_PW@$PROJECT-mysql:3306/omcgitea" \
    -e BOARD_LISTEN_PORT=8660 \
    -e BOARD_MEMBERS_JSON='{"pbench-top":["planner","team1-lead","team2-lead"],"pbench-team1":["team1-lead","team1-worker1"]}' \
    -p "127.0.0.1:$BOARD_PORT:8660" \
    "$BOARD_IMAGE" >/dev/null || fail "docker run board-service"
CREATED_BOARD=1

# Wait for healthz
for i in $(seq 1 20); do
    if curl -fsS "http://localhost:$BOARD_PORT/healthz" >/dev/null 2>&1; then
        say "board-service healthy in ${i}s"
        break
    fi
    sleep 2
done
curl -fsS "http://localhost:$BOARD_PORT/healthz" >/dev/null 2>&1 \
    || { sudo docker logs "$PROJECT-board" 2>&1 | tail -30; fail "board-service never came up"; }

BASE="http://localhost:$BOARD_PORT"

# --- 4. Test cases ---------------------------------------------------------

# 4.1 Membership: planner can write to pbench-top, team1-worker1 cannot.
say "4.1 membership check"
r=$(curl -sS -X POST "$BASE/board/pbench-top/note" -H 'Content-Type: application/json' \
    -d '{"thread_id":"planner","type":"FACT","content":"initial recon: samtools uses hts_open"}')
echo "$r" | jq -e '.status=="admitted"' >/dev/null || fail "4.1a planner FACT admit: $r"

r=$(curl -sS -X POST "$BASE/board/pbench-top/note" -H 'Content-Type: application/json' \
    -d '{"thread_id":"team1-worker1","type":"FACT","content":"trying to write to top"}')
echo "$r" | jq -e '.detail | contains("not a member")' >/dev/null \
    || fail "4.1b non-member write should 403: $r"

# 4.2 Deterministic verifier rejects a PATCH_SUMMARY with invalid evidence.
say "4.2 verifier rejects invalid PATCH_SUMMARY evidence"
r=$(curl -sS -X POST "$BASE/board/pbench-top/note" -H 'Content-Type: application/json' \
    -d '{"thread_id":"planner","type":"PATCH_SUMMARY","content":"files=x.c | idea=stub | evidence=tbd"}')
echo "$r" | jq -e '.status=="rejected"' >/dev/null || fail "4.2 should reject tbd evidence: $r"

# 4.3 Read back what we wrote (viewer=planner is a member of pbench-top).
say "4.3 read renders admitted gists"
r=$(curl -sS "$BASE/board/pbench-top/read?viewer=planner&window_tokens=2000")
echo "$r" | jq -e '.rendered | contains("hts_open")' >/dev/null || fail "4.3 read: $r"

# 4.4 Duplicate FACT is silently deduped (only one row in _entries — actually
#     shared_lessons stores both but renders one with (x2)). Verify count.
say "4.4 duplicate FACT dedupes in render"
curl -sS -X POST "$BASE/board/pbench-top/note" -H 'Content-Type: application/json' \
    -d '{"thread_id":"planner","type":"FACT","content":"initial recon: samtools uses hts_open"}' >/dev/null
r=$(curl -sS "$BASE/board/pbench-top/read?viewer=planner&window_tokens=2000")
# Should have "(x2)" marker on the deduped FACT
echo "$r" | jq -r '.rendered' | grep -q '(x2)' || fail "4.4 expected (x2) dedupe marker: $r"

# 4.5 Queue: enqueue → claim → complete flow.
say "4.5 queue enqueue/claim/complete"
curl -fsS -X POST "$BASE/queue/pbench-top/enqueue" -H 'Content-Type: application/json' \
    -d '{"task_id":"sub-1","description":"Implement hts_open shim","deps":[],"enqueued_by":"planner"}' \
    >/dev/null || fail "4.5a enqueue"

r=$(curl -sS -X POST "$BASE/queue/pbench-top/claim" -H 'Content-Type: application/json' \
    -d '{"claimed_by":"team1-lead"}')
echo "$r" | jq -e '.task_id=="sub-1"' >/dev/null || fail "4.5b claim: $r"

# Second claim while first is unfinished should return null.
r=$(curl -sS -X POST "$BASE/queue/pbench-top/claim" -H 'Content-Type: application/json' \
    -d '{"claimed_by":"team2-lead"}')
[ "$r" = "null" ] || fail "4.5c second claim should be null, got: $r"

curl -fsS -X POST "$BASE/queue/pbench-top/complete" -H 'Content-Type: application/json' \
    -d '{"task_id":"sub-1","claimed_by":"team1-lead","state":"completed"}' \
    >/dev/null || fail "4.5d complete"

# 4.6 Deps: task sub-2 depends on sub-3 which doesn't exist yet → not claimable.
say "4.6 unmet deps block claim"
curl -fsS -X POST "$BASE/queue/pbench-top/enqueue" -H 'Content-Type: application/json' \
    -d '{"task_id":"sub-2","description":"Build compile.sh","deps":["sub-3"],"enqueued_by":"planner"}' \
    >/dev/null || fail "4.6a enqueue"
r=$(curl -sS -X POST "$BASE/queue/pbench-top/claim" -H 'Content-Type: application/json' \
    -d '{"claimed_by":"team1-lead"}')
[ "$r" = "null" ] || fail "4.6b sub-2 should be blocked by missing sub-3: $r"

# 4.7 Persistence: restart board-service, verify hydrate() replays gists.
say "4.7 hydrate on restart"
sudo docker restart "$PROJECT-board" >/dev/null
for i in $(seq 1 20); do
    curl -fsS "$BASE/healthz" >/dev/null 2>&1 && break
    sleep 2
done
r=$(curl -sS "$BASE/board/pbench-top/read?viewer=planner&window_tokens=2000")
echo "$r" | jq -e '.rendered | contains("hts_open")' >/dev/null \
    || fail "4.7 gist did not survive restart: $r"

# 4.8 Multi-board snapshot: one call renders every board the viewer belongs to,
#     copied under a single critical section so the view cannot tear across a
#     concurrent write. team1-lead is a member of both pbench-top and
#     pbench-team1, so a snapshot must carry both.
say "4.8 multi-board snapshot"
curl -fsS -X POST "$BASE/board/pbench-team1/note" -H 'Content-Type: application/json' \
    -d '{"thread_id":"team1-lead","type":"FACT","content":"team1 board marker: bgzf_read is the hot path"}' \
    >/dev/null || fail "4.8a seed team1 board"

r=$(curl -sS "$BASE/snapshot?viewer=team1-lead&boards=pbench-top,pbench-team1&window_tokens=2000")
echo "$r" | jq -e '.boards["pbench-top"].rendered | contains("hts_open")' >/dev/null \
    || fail "4.8b snapshot missing pbench-top content: $r"
echo "$r" | jq -e '.boards["pbench-team1"].rendered | contains("bgzf_read")' >/dev/null \
    || fail "4.8c snapshot missing pbench-team1 content: $r"
# Every board in one snapshot must share a single logical read point.
echo "$r" | jq -e '.snapshot_at | type=="number"' >/dev/null \
    || fail "4.8d snapshot must report its read point: $r"

# A board the viewer cannot read must be refused, not silently omitted —
# otherwise 2b's tiered isolation would degrade into "best effort".
r=$(curl -sS -o /dev/null -w '%{http_code}' \
    "$BASE/snapshot?viewer=team1-worker1&boards=pbench-top,pbench-team1&window_tokens=2000")
[ "$r" = "403" ] || fail "4.8e snapshot must 403 on a non-member board, got HTTP $r"

# 4.9 Selective unfolding: board holds the gist, detail expands on demand.
say "4.9 selective unfolding (G -> S -> raw)"
DETAIL='SEGFAULT trace begins here. '"$(head -c 4000 /dev/zero | tr '\0' 'x')"' TAIL_MARKER_ZZZ'
r=$(jq -cn --arg d "$DETAIL" \
    '{thread_id:"planner",type:"OBSERVED",content:"bgzf_read segfaults on truncated input; full trace stored",detail:$d}' \
    | curl -sS -X POST "$BASE/board/pbench-top/note" -H 'Content-Type: application/json' -d @-)
echo "$r" | jq -e '.status=="admitted"' >/dev/null || fail "4.9a admit with detail: $r"
LBL=$(echo "$r" | jq -r '.label')
[ -n "$LBL" ] && [ "$LBL" != "null" ] || fail "4.9b no label returned: $r"

# The gist must be advertised as unfoldable, or the agent has no handle to use.
r=$(curl -sS "$BASE/board/pbench-top/read?viewer=planner&window_tokens=2000")
echo "$r" | jq -r '.rendered' | grep -q "Unfoldable" || fail "4.9c render lacks unfold index: $r"
echo "$r" | jq -r '.rendered' | grep -q "$LBL" || fail "4.9d render lacks label $LBL"
# The raw detail must NOT be in the default render — that is the compression.
echo "$r" | jq -r '.rendered' | grep -q 'TAIL_MARKER_ZZZ' && fail "4.9e detail leaked into gist render"

# Hop 1: G -> S lists addressable sub-chunks without paying for raw.
r=$(curl -sS "$BASE/board/pbench-top/unfold?viewer=planner&labels=$LBL&depth=summary")
echo "$r" | jq -e --arg l "$LBL" '.resolved == [$l]' >/dev/null || fail "4.9f summary unfold: $r"
echo "$r" | jq -r '.rendered' | grep -q "$LBL\.1" || fail "4.9g summary lacks sub-chunk labels: $r"

# Hop 2: S -> raw returns the real text, with n+/-1 neighbors.
r=$(curl -sS "$BASE/board/pbench-top/unfold?viewer=planner&labels=$LBL.2&depth=raw")
echo "$r" | jq -r '.rendered' | grep -q 'requested' || fail "4.9h raw unfold marker: $r"
echo "$r" | jq -r '.rendered' | grep -q "$LBL\.1" || fail "4.9i raw unfold must include neighbor n-1: $r"

# Unfolding must not write back to the board (paper A.2).
n_before=$(curl -sS "$BASE/board/pbench-top/read_all?viewer=planner" | jq '.count')
curl -sS "$BASE/board/pbench-top/unfold?viewer=planner&labels=$LBL&depth=raw" >/dev/null
n_after=$(curl -sS "$BASE/board/pbench-top/read_all?viewer=planner" | jq '.count')
[ "$n_before" = "$n_after" ] || fail "4.9j unfold mutated the board ($n_before -> $n_after)"

# A hallucinated label degrades to "unknown", never a 5xx.
r=$(curl -sS "$BASE/board/pbench-top/unfold?viewer=planner&labels=G999999&depth=raw")
echo "$r" | jq -e '.unknown | length == 1' >/dev/null || fail "4.9k unknown label handling: $r"

# 4.10 Render modes: the matrix upstream dispatches per role.
say "4.10 render modes"
for m in full peer_digest patch_digest patch_fail_digest patch_evidence_digest \
         patch_digest_local_only patch_clean_local_only patch_clean_delayed_local \
         patch_selective_unfold; do
    r=$(curl -sS "$BASE/board/pbench-top/read?viewer=planner&window_tokens=2000&render_mode=$m&role=implementer")
    echo "$r" | jq -e --arg m "$m" '.render_mode==$m' >/dev/null || fail "4.10 mode $m failed: $r"
done
r=$(curl -sS -o /dev/null -w '%{http_code}' "$BASE/board/pbench-top/read?viewer=planner&render_mode=bogus")
[ "$r" = "400" ] || fail "4.10b unknown render_mode should 400, got $r"
# The local_only family deliberately blinds the planner.
r=$(curl -sS "$BASE/board/pbench-top/read?viewer=planner&render_mode=patch_digest_local_only&role=planner")
echo "$r" | jq -e '.rendered==""' >/dev/null || fail "4.10c planner must be blinded in local_only: $r"

# 4.11 Lifecycle + stats: the evidence that a gist actually reached a peer.
say "4.11 lifecycle + stats"
r=$(curl -sS "$BASE/board/pbench-top/stats?viewer=planner&window_tokens=2000")
echo "$r" | jq -e '.stored_entries > 0' >/dev/null || fail "4.11a stats: $r"
r=$(curl -sS -X POST "$BASE/board/pbench-top/lifecycle?viewer=planner")
echo "$r" | jq -e '.path' >/dev/null || fail "4.11b lifecycle dump: $r"
dump_path=$(echo "$r" | jq -r '.path')
sudo docker exec "$PROJECT-board" python -c \
    'import json,pathlib,sys; rows=[json.loads(s) for s in pathlib.Path(sys.argv[1]).read_text().splitlines()]; assert any(r["kind"]=="entry" for r in rows); assert rows[-1]["kind"]=="summary" and rows[-1]["stored_total"]>0' \
    "$dump_path" || fail "4.11b lifecycle file contents"

# The harness is not a board member but must still be able to trigger the dump,
# or the run loses its only record of which gists were ever read.
r=$(curl -sS -X POST "$BASE/board/pbench-top/lifecycle?viewer=harness")
echo "$r" | jq -e '.path' >/dev/null || fail "4.11c operator lifecycle dump: $r"
# That exemption must NOT become a general way past membership.
r=$(curl -sS -X POST "$BASE/board/pbench-top/note" -H 'Content-Type: application/json' \
    -d '{"thread_id":"team1-worker1","type":"FACT","content":"still not a member"}')
echo "$r" | jq -e '.detail | contains("not a member")' >/dev/null \
    || fail "4.11d membership still enforced for agents: $r"

# A lifecycle filename must not redirect the HTTP export outside its root.
sudo docker exec "$PROJECT-board" python -c \
    'from pathlib import Path; p=Path("/tmp/lifecycle-sentinel.jsonl"); p.write_text("outside sentinel"); Path("/data/lifecycle/escape.jsonl").symlink_to(p)' \
    || fail "4.11e prepare lifecycle symlink"
status=$(curl -sS -o /dev/null -w '%{http_code}' -X POST "$BASE/board/escape/lifecycle?viewer=harness")
[ "$status" = "400" ] || fail "4.11e symlink escape should return 400, got $status"
sudo docker exec "$PROJECT-board" python -c \
    'from pathlib import Path; assert Path("/tmp/lifecycle-sentinel.jsonl").read_text()=="outside sentinel"' \
    || fail "4.11e outside lifecycle file was changed"

# 4.12 delegation_id must accept our string ids (queue task_ids), not just ints.
#      The upstream port hard-casts ids to int; agent names and task_ids are
#      strings, and a 500 here silently disables the CLAIM cap, patch
#      latest-wins, and FAIL-invalidates-own-patch, all of which key on it.
say "4.12 string delegation_id + detail round-trip"
r=$(curl -sS -X POST "$BASE/board/pbench-top/note" -H 'Content-Type: application/json' \
    -d '{"thread_id":"planner","type":"FACT","content":"deleg id is a queue task id","delegation_id":"sub-faidx","detail":"long detail here"}')
echo "$r" | jq -e '.status=="admitted"' >/dev/null || fail "4.12a string delegation_id rejected: $r"
LBL2=$(echo "$r" | jq -r '.label')
r=$(curl -sS "$BASE/board/pbench-top/unfold?viewer=planner&labels=$LBL2&depth=raw")
echo "$r" | jq -e --arg l "$LBL2" '.resolved==[$l]' >/dev/null || fail "4.12b detail not stored: $r"
# PATCH_SUMMARY keyed on the same string delegation_id must also admit.
r=$(curl -sS -X POST "$BASE/board/pbench-top/note" -H 'Content-Type: application/json' \
    -d '{"thread_id":"planner","type":"PATCH_SUMMARY","content":"files=src/faidx.c | idea=index | evidence=ran ./executable -i x, matched reference","delegation_id":"sub-faidx"}')
echo "$r" | jq -e '.status=="admitted"' >/dev/null || fail "4.12c PATCH_SUMMARY with string delegation_id: $r"
r=$(curl -sS -X POST "$BASE/board/pbench-top/finalize" -H 'Content-Type: application/json' \
    -d '{"thread_id":"planner","delegation_id":"sub-faidx"}')
echo "$r" | jq -e '.finalized==true' >/dev/null || fail "4.12d finalize by string delegation_id: $r"

# 4.13 CLAIM must be repeatable: it is the only liveness signal a lead has.
#      Upstream caps CLAIMs at 2 per (thread, delegation) and SUPPRESSES the
#      rest. The TTL is now 3600s (was 300s, which gave a worker ~10 visible
#      minutes out of a 6h task, after which it was indistinguishable from a
#      dead one). Repeatability still matters: a re-posted CLAIM is what
#      separates "heads-down" from "gone". Measured
#      on sweep_6.2/typst: worker3 was the busiest agent on the team (63-81
#      tool calls per 15min) while the lead recorded "worker3 MIA 60min" and
#      reassigned its issue three times, spawning two competing
#      implementations and five discarded PRs.
say "4.13 CLAIM is repeatable (liveness heartbeat)"
for i in 1 2 3 4 5; do
    r=$(curl -sS -X POST "$BASE/board/pbench-top/note" -H 'Content-Type: application/json' \
        -d "{\"thread_id\":\"planner\",\"type\":\"CLAIM\",\"content\":\"implementing eval lexer, step $i\",\"delegation_id\":\"sub-eval\"}")
    echo "$r" | jq -e '.status=="admitted"' >/dev/null \
        || fail "4.13 CLAIM #$i suppressed (cap still enforced): $r"
done
# All five must be retrievable; a lead polling for liveness reads the latest.
r=$(curl -sS "$BASE/board/pbench-top/read_all?viewer=planner")
n=$(echo "$r" | jq '[.entries[] | select(.type=="CLAIM" and .thread_id=="planner")] | length')
[ "$n" -ge 5 ] || fail "4.13 expected >=5 stored CLAIMs from planner, got $n"

say "ALL TESTS PASSED"
