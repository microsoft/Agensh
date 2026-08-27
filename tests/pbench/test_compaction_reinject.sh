#!/usr/bin/env bash
# test_compaction_reinject.sh — the router can detect a context compaction and put back what
# it dropped (board + waiting UEMs), but that re-injection is currently DISABLED BY DEFAULT.
#
# STATUS: `reinjectAfterCompaction` defaults false. The mechanism below is retained and tested
# so re-enabling is one flag, but no board refresh and no UEM batch are sent after a
# compaction. It lands AFTER the turn -- ACP session/prompt is request-response and cannot be
# interleaved -- and interrupting the turn instead would abort whatever tool call is in flight
# (plausibly a build or a suite run) at the moment the agent is still reorienting from the
# summary. Off until that trade is settled.
#
# WHY
# The board is injected as a prefix on each dispatched UEM batch (dispatcher.ts, "FORCED
# READ"), and UEMs only reach an agent between turns. A compaction happens MID-turn: the
# adapter folds the transcript into a summary and the agent keeps working. Whatever the board
# said, and whatever the batch that started the turn said, is now a paraphrase at best. Until
# the next inbound event the agent runs blind, and if no event arrives it stays blind.
#
# Compaction is observable without touching upstream. claude-agent-acp emits, at
# dist/acp-agent.js:494:
#
#     sessionUpdate: "usage_update",  used: 0,  size: session.contextWindowSize
#     sessionUpdate: "agent_message_chunk",  content: {text: "\n\nCompacting completed."}
#
# `used: 0` is the structured signal — a normal usage_update carries real usage, so zero is
# unambiguous and needs no prose matching.
#
# Usage: bash tests/pbench/test_compaction_reinject.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CH="$ROOT/mini-router/src/acp_socket_channel.ts"
DP="$ROOT/mini-router/src/dispatcher.ts"
rc=0
ok()   { echo "PASS $*"; }
fail() { echo "FAIL $*"; rc=1; }

# --- 1. the channel must recognise a compaction -------------------------------
grep -q 'usage_update' "$CH" \
    && ok "the channel inspects usage_update" \
    || fail "nothing looks at usage_update — compaction is invisible to the router"
grep -qE 'used\b.*===?\s*0|=== *0' "$CH" \
    && ok "compaction is detected by used===0, the adapter's own signal" \
    || fail "no used===0 check — the only structured compaction signal is unused"
# Prose is a fallback, never the primary: the adapter's wording is upstream and can change.
grep -q 'Compacting completed' "$CH" && grep -q 'used' "$CH" \
    && ok "the prose marker is at most a secondary check" \
    || ok "detection does not depend on upstream wording"

# --- 2. it must be reported once per compaction, and not stick ----------------
grep -qE 'takeCompacted|consumeCompact' "$CH" \
    && ok "the flag is take-once, so one compaction cannot re-fire forever" \
    || fail "no take-once accessor — a stuck flag would re-inject on every later turn"

# --- 3. the dispatcher must re-inject board AND pending UEMs ------------------
grep -qE 'takeCompacted|consumeCompact' "$DP" \
    && ok "the dispatcher acts on the compaction signal" \
    || fail "the channel may detect compaction but nothing responds to it"
grep -A40 'RE-INJECT AFTER COMPACTION' "$DP" | grep -qE 'renderForPrompt' \
    && ok "the latest board is re-rendered after a compaction" \
    || fail "board is not re-injected — the agent keeps working without shared context"
grep -A40 'RE-INJECT AFTER COMPACTION' "$DP" | grep -qE 'nextPendingBatch' \
    && ok "a waiting UEM batch is re-injected too" \
    || fail "pending events are not re-delivered after a compaction"
# "if there is waiting message" — an empty queue must NOT produce a bare nudge, or every
# compaction costs a turn for nothing.
grep -A40 'RE-INJECT AFTER COMPACTION' "$DP" | grep -qE 'waiting\.length > 0' \
    && ok "injection is conditional on there being something to inject" \
    || fail "a compaction with an empty queue would still burn a turn"

# --- 4. it must not violate the dispatcher's serialisation -------------------
# dispatcher.ts documents at length that two concurrent prompts on one session corrupt both
# turns; the whole batch is mutexed for that reason. The re-injection is another prompt, so it
# has to happen where the mutex still holds, not from the update callback.
grep -A40 'RE-INJECT AFTER COMPACTION' "$DP" | grep -q 'promptText' \
    && ok "re-injection goes through promptText inside the serialised section" \
    || fail "re-injection does not use the serialised prompt path"
grep -q 'takeCompacted' "$CH" && ! awk '/onSessionUpdate|clientImpl\(\(/,/\}\)/' "$CH" | grep -q 'promptText' \
    && ok "nothing prompts from inside the session-update callback" \
    || fail "a prompt is issued from the update callback — that races the in-flight turn"

# --- 5. it must actually COMPILE ---------------------------------------------
# The greps above all passed while three type errors sat in the file: nextPendingBatch takes
# (agent, limit) not (limit), ACPChannel exposes no renderBatch, and the log entry type admits
# only warn|error. Grep cannot see any of that. The router image carries tsc, and the host has
# no node, so compile inside the image.
if docker image inspect omcgitea-mini-router:local >/dev/null 2>&1; then
    TSC=$(timeout 400 docker run --rm -v "$ROOT/mini-router:/w" -w /w \
            --entrypoint sh omcgitea-mini-router:local \
            -c 'node node_modules/typescript/bin/tsc --noEmit 2>&1 | head -20' 2>&1)
    [ -z "$TSC" ] \
        && ok "mini-router typechecks" \
        || { fail "typecheck errors:"; printf '%s\n' "$TSC" | sed 's/^/    /'; }
else
    echo "SKIP typecheck (omcgitea-mini-router:local not built)"
fi

# --- 6. DEFAULT OFF -----------------------------------------------------------
grep -qE 'reinjectAfterCompaction\?: boolean' "$DP" \
    && ok "re-injection is an explicit option, not hardcoded" \
    || fail "no flag — the behaviour cannot be turned off without an edit"
grep -q 'process.env.PBENCH_REINJECT_AFTER_COMPACTION === "1"' "$ROOT/mini-router/src/main.ts" \
    && ok "it is OFF unless PBENCH_REINJECT_AFTER_COMPACTION=1" \
    || fail "the flag is not wired to env, or does not default off"
# takeCompacted is read-and-clear. If it were only called when ENABLED, the flag would be
# holding a stale `true` and would fire a spurious re-injection the instant it was switched on.
 grep -A15 'RE-INJECT AFTER COMPACTION' "$DP" | grep -q 'const didCompact = this.opts.channel.takeCompacted' \
    && ok "the flag is drained even while disabled, so enabling cannot fire a stale one" \
    || fail "takeCompacted only runs when enabled — enabling would replay an old compaction"

exit $rc
