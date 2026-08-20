#!/usr/bin/env bash
# test_mm_ids.sh — agents must be TOLD their Mattermost team and task channel.
#
# WHY
# The mattermost MCP is configured with URL + token only. Upstream
# mcp-server-mattermost 0.5.1 exposes no MATTERMOST_TEAM_ID setting, so every
# team-scoped tool — post_message, search_messages, list_my_channels — needs a
# team_id / channel_id the agent supplies itself.
#
# Workers routinely fail that discovery and invent plausibly-shaped 26-char
# ids. Measured on sweep 6.3 pandoc: worker3 called get_channel_messages with
# channel `o5w8h47pdfbzjc4d8w7dhnhren`, which never existed — the run only had
# town-square, off-topic and pbench-task. Mattermost answers 403 "You do not
# have the appropriate permissions" for a team you are not in, and 404 for a
# channel that is not there. The agent reads that as a lockout:
#
#   worker3: "list_teams is denied. So I'll coordinate via gitea."
#
# 47 of 80 workers across the 20-task sweep hit this; in 5 tasks all four did.
# Provisioning was never the problem — every agent is a member of the team and
# of all three channels, with a session valid for six months. They simply were
# never told the ids.
#
# The cost is not the lost chat. The lead uses mattermost silence as its
# liveness signal, concludes the worker is stuck, and takes over the work.
# Pandoc's worker3 was declared stuck 19 minutes before it opened a complete,
# CI-green HTML+LaTeX+Plain writer — which the lead then closed unmerged.
#
# The runner creates the channel and therefore already holds both ids, and it
# owns task_brief(), the canonical text posted to the gitea issue AND the MM
# channel AND the reminders. Putting the ids there reaches every agent without
# depending on container start order.
#
# Usage: bash tests/pbench/test_mm_ids.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
rc=0
ok()   { echo "PASS $*"; }
fail() { echo "FAIL $*"; rc=1; }

RUNNERS=(
    "$ROOT/scripts/pbench_run_1team.sh"
)

for r in "${RUNNERS[@]}"; do
    [ -f "$r" ] || { echo "FATAL: $r missing"; exit 1; }
    n=$(basename "$r")

    # 1. The brief must carry the ids the MCP cannot infer.
    brief=$(sed -n '/^task_brief()/,/^}/p' "$r")
    if [ -z "$brief" ]; then
        fail "$n: no task_brief() found"
        continue
    fi
    case "$brief" in
        *TASK_CHANNEL_ID*) ok "$n: brief carries the task channel id" ;;
        *) fail "$n: brief never states the channel id — agents must guess it" ;;
    esac
    case "$brief" in
        *MM_TEAM_ID*|*team_id*) ok "$n: brief carries the team id" ;;
        *) fail "$n: brief never states the team id — team-scoped tools 403" ;;
    esac
done

# 2. Team/channel membership adds must not be silently discarded. They are
#    currently `... >/dev/null 2>&1 || true`, so a failed add is invisible and
#    presents later as an unexplained 403.
r="$ROOT/scripts/pbench_run_1team.sh"
if grep -q 'mm_join_ok\|verify_mm_membership' "$r"; then
    ok "membership adds are checked"
else
    fail "membership adds are fire-and-forget (>/dev/null 2>&1 || true)"
fi

exit $rc
