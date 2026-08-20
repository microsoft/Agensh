#!/usr/bin/env bash
# test_remind_loop.sh — REAL regression test for the remind_loop scoping fix.
#
# Bug: the runner captured the MM task-channel id into a LOCAL `ch` inside a
# $() subshell; the global TASK_CHANNEL_ID stayed empty, so the background
# remind_loop's `[ -n "$TASK_CHANNEL_ID" ]` guard was always false and it posted
# ZERO reminders (verified across the first 5 multi-agent runs: grep -c
# "reminder #" == 0). Fix: push_seed_and_drive now assigns the global.
#
# This test does NOT mock Mattermost — per CLAUDE.md the MM path must be real.
# It runs against a LIVE pbench profile (assumed already up via `make up
# PROFILE=$PROFILE`) and asserts the real Mattermost `pbench-task` channel
# actually received >=1 director progress-check ("Project supervision") post.
#
#   PROFILE=org-pbench-ffmpeg-b2 REMIND_MINS=1 \
#     tests/pbench/test_remind_loop.sh
#
# Intended to be invoked after a short run has had at least one REMIND_MINS
# interval elapse (e.g. the 20-min ffmpeg validation run with REMIND_MINS=5).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROFILE="${PROFILE:?PROFILE=org-pbench-<slug> required (a live, up profile)}"
ENV_FILE="$ROOT/.env.$PROFILE"
[ -f "$ENV_FILE" ] || { echo "FATAL: $ENV_FILE missing"; exit 1; }

# `|| true`: some keys (MATTERMOST_TEAM_NAME) are optional and absent from the
# generated env; under `set -o pipefail` a non-matching grep would otherwise
# abort the whole test before any assertion runs.
get() { grep -E "^$1=" "$ENV_FILE" | cut -d= -f2- || true; }
EDGE_MM_PORT="$(get EDGE_MM_PORT)"
MM_USER="$(get MATTERMOST_ADMIN_USER)"
MM_PASS="$(get MATTERMOST_ADMIN_PASSWORD)"
ORG_NAME="$(get ORG_NAME)"
TEAM="$(get MATTERMOST_TEAM_NAME)"; TEAM="${TEAM:-$ORG_NAME}"
MM_BASE="http://localhost:${EDGE_MM_PORT}"

pass() { echo "  ok: $*"; }
fail() { echo "  FAIL: $*"; exit 1; }

# 1. real MM admin login (scoped session token, like the orchestrator does)
TOKEN=$(curl -sS -i -d "{\"login_id\":\"$MM_USER\",\"password\":\"$MM_PASS\"}" \
    "$MM_BASE/api/v4/users/login" \
    | awk -F': ' '/^[Tt]oken:/ {gsub(/\r/,""); print $2; exit}')
[ -n "$TOKEN" ] || fail "MM admin login failed at $MM_BASE"
pass "MM admin login"

# 2. resolve team + pbench-task channel
team_id=$(curl -sS -H "Authorization: Bearer $TOKEN" \
    "$MM_BASE/api/v4/teams/name/$TEAM" | jq -r '.id // empty')
[ -n "$team_id" ] || fail "team $TEAM not found"
ch=$(curl -sS -H "Authorization: Bearer $TOKEN" \
    "$MM_BASE/api/v4/teams/$team_id/channels/name/pbench-task" | jq -r '.id // empty')
[ -n "$ch" ] || fail "pbench-task channel not found (was the team driven?)"
pass "pbench-task channel: $ch"

# 3. assert at least one reminder ("Project supervision #N") landed in the channel
posts=$(curl -sS -H "Authorization: Bearer $TOKEN" \
    "$MM_BASE/api/v4/channels/$ch/posts?per_page=200")
n=$(printf '%s' "$posts" | jq '[.posts[]? | select(.message | test("Project supervision"))] | length')
echo "  reminder posts in channel: $n"
[ "${n:-0}" -ge 1 ] || fail "0 reminders in MM channel — remind_loop fix NOT working"
pass "remind_loop fired >=1 reminder into the real MM channel (n=$n)"

echo "PASS test_remind_loop ($PROFILE)"
