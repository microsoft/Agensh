#!/usr/bin/env bash
# test_export_resilience.sh — a failed submission export must never look like a score.
#
# WHY
# Sweep 6.11 lost 2 of its 4 completed tasks to this. ctags and pandoc both hit their 6h
# deadline within 5 minutes of each other, both exports got HTTP 504 from Gitea at exactly
# nginx's `proxy_read_timeout 300s` (docker/nginx-edge/conf.d/gitea.conf:22), and both wrote a
# 4.0K tarball containing ZERO files. Eval then recorded 2579 and 5467 `not_run` -> 0.00%,
# which is indistinguishable from a team that built nothing. The repos were fine: cloned
# offline from the archived bare repo afterwards they yielded 99 and 148 entries with
# compile.sh present and a merged PR at HEAD.
#
# Three separate defects, each of which alone would have prevented the loss:
#
#   1. ORDER. teardown() ran export_submission() BEFORE `make down`, so at export time all 5
#      agents were still live on Gitea over MCP and act_runner could still be running CI jobs.
#      Four stacks hit their deadline inside 19 minutes and tore down into the same host. The
#      two earliest lost the race; the two that won still took 7.5 and 13.5 minutes.
#   2. NO RETRY. A single `git clone`. One transient 504 was terminal.
#   3. SILENT ZERO. The failure path wrote an "empty-but-valid" tarball and carried on, so the
#      loss surfaced as a plausible score rather than as an error.
#
# Usage: bash tests/pbench/test_export_resilience.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN="$ROOT/scripts/pbench_run_1team.sh"
rc=0
ok()   { echo "PASS $*"; }
fail() { echo "FAIL $*"; rc=1; }

[ -f "$RUN" ] || { echo "FAIL missing $RUN"; exit 1; }

# --- 1. quiesce before export -------------------------------------------------
grep -q 'quiesce_agents' "$RUN" \
    && ok "teardown has a quiesce step" \
    || fail "nothing quiesces the stack — the export races 5 live agents, as in 6.11"

# The order is the whole point: quiesce must come BEFORE the export, and the export before
# `make down` (which destroys the Gitea we are cloning from).
awk '/^teardown\(\)/,/^}/' "$RUN" > /tmp/_td.$$ 2>/dev/null
q=$(grep -n 'quiesce_agents' /tmp/_td.$$ | head -1 | cut -d: -f1)
x=$(grep -n 'export_submission' /tmp/_td.$$ | head -1 | cut -d: -f1)
d=$(grep -n 'make down' /tmp/_td.$$ | head -1 | cut -d: -f1)
if [ -n "$q" ] && [ -n "$x" ] && [ -n "$d" ] && [ "$q" -lt "$x" ] && [ "$x" -lt "$d" ]; then
    ok "teardown order is quiesce -> export -> down"
else
    fail "teardown order wrong (quiesce=$q export=$x down=$d); need quiesce < export < down"
fi
rm -f /tmp/_td.$$

# Gitea must SURVIVE the quiesce — it is the thing we are about to clone from. A quiesce that
# stops the whole stack would turn a 504 into a connection refused, not a fix.
# Check the container SELECTION, not any mention: the function legitimately names gitea in its
# prose and in a log line explaining what it spares. Only `--filter name=` / an explicit stop
# target decides what actually gets killed.
qbody()  { awk '/^quiesce_agents\(\)/,/^}/' "$RUN" | sed 's/#.*//'; }
qsel()   { qbody | grep -oE -- '--filter[= ]"?[a-z.]+=[^"]*"?|docker (stop|kill|rm)[^|]*'; }
qsel | grep -qE 'hermes-agent|mini-router|act-runner' \
    && ok "quiesce selects agents/routers/runner, the Gitea clients" \
    || fail "quiesce does not select the agent containers"
qsel | grep -qE 'gitea|mysql|nginx|mattermost|board' \
    && fail "quiesce selects an infrastructure container — the export needs gitea alive" \
    || ok "quiesce selects no infrastructure container, so gitea survives"

# --- 2. CONTAINER SAFETY ------------------------------------------------------
# CLAUDE.md forbids acting on any container this project did not create. A quiesce that
# matches on name alone would hit another project's containers on a shared host; this host
# runs 11 kind clusters belonging to someone else.
qbody | grep -qE 'com\.docker\.compose\.project|COMPOSE_PROJECT|omcgitea-\$' \
    && ok "quiesce is scoped to this compose project" \
    || fail "quiesce is not project-scoped — it could stop another project's containers"

# --- 3. retry the clone -------------------------------------------------------
awk '/^export_submission\(\)/,/^}/' "$RUN" | grep -qE 'for .*attempt|while .*attempt|retry' \
    && ok "the export retries rather than giving up on one 504" \
    || fail "still a single-shot clone — one transient 504 loses the task"
awk '/^export_submission\(\)/,/^}/' "$RUN" | grep -qE 'sleep' \
    && ok "retries back off instead of hammering a struggling gitea" \
    || fail "retries have no backoff"

# --- 4. a failed export must NOT read as a score ------------------------------
# This is the assertion that matters. 6.11's loss was invisible because the failure produced a
# well-formed artifact. Whatever the fallback writes, something adjacent must mark it as an
# export failure so a human or a scorer can tell 0.00% from "we never got the code".
awk '/^export_submission\(\)/,/^}/' "$RUN" | grep -qE 'EXPORT_FAILED|export_failed' \
    && ok "a failed export leaves an explicit marker" \
    || fail "a failed export still produces only an empty tarball — a silent 0.00%"
awk '/^export_submission\(\)/,/^}/' "$RUN" | grep -qE 'ERROR|FATAL' \
    && ok "the failure is logged at error level, not as a WARN in passing" \
    || fail "the failure is only a WARN — it scrolled past unnoticed in 6.11"

# --- 5. the scorer must honour the marker ------------------------------------
# A marker nothing reads is decoration. Whatever aggregates scores has to exclude, or at least
# flag, a task whose submission never made it out of Gitea.
SC="$ROOT/scripts/pbench_score.py"
if [ -f "$SC" ]; then
    grep -qE 'EXPORT_FAILED|export_failed' "$SC" \
        && ok "the scorer distinguishes an export failure from a zero" \
        || fail "the scorer would count a failed export as 0.00%, exactly as in 6.11"
else
    echo "SKIP scorer check (scripts/pbench_score.py absent)"
fi

# --- 6. BEHAVIOURAL: the filter must really select agents and spare gitea -----
# Everything above is a grep. The fix hinges on a docker semantic that greps cannot check:
# `docker ps` OR-s repeated --filter name= values and AND-s them with --filter label=. If it
# AND-ed them instead, the quiesce would select nothing and silently do nothing — the exact
# 6.11 failure, reintroduced with all the tests still green. Build a throwaway stack and look.
if ! docker info >/dev/null 2>&1 && ! sudo docker info >/dev/null 2>&1; then
    echo "SKIP behavioural filter check (no docker)"
else
    P=omcgitea-quiescetest-$$
    for n in hermes-agent-team1-lead mini-router-team1-lead act-runner gitea mysql; do
        sudo docker run -d --name "$P-$n-1" --label com.docker.compose.project=$P \
            alpine:3 sleep 60 >/dev/null 2>&1
    done
    SEL=$(sudo docker ps --filter "label=com.docker.compose.project=$P" \
            --filter "name=hermes-agent" --filter "name=mini-router" --filter "name=act-runner" \
            --format '{{.Names}}' 2>/dev/null)
    n_sel=$(printf '%s' "$SEL" | grep -c . || true)
    [ "$n_sel" = "3" ] \
        && ok "the filter selects exactly the 3 agent/router/runner containers" \
        || fail "filter selected $n_sel containers, expected 3 — docker's filter semantics differ"
    # Match the SERVICE suffix, not a bare substring: every container name here starts with
    # "omcgitea-", which contains "gitea", so a naive grep flags a correct selection.
    printf '%s\n' "$SEL" | grep -qE -- '-(gitea|mysql)-[0-9]+$' \
        && fail "the filter would stop gitea/mysql — the export clones from gitea" \
        || ok "gitea and mysql are not selected, so the export still has something to clone"
    # Cleanup touches ONLY the containers this test just created, by its own unique label.
    sudo docker rm -f $(sudo docker ps -aq --filter "label=com.docker.compose.project=$P") \
        >/dev/null 2>&1 || true
fi

exit $rc
