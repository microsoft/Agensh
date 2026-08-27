#!/usr/bin/env bash
# test_reboot_guard.sh — a reboot must never leave ProgramBench stacks running headless.
#
# WHY
# Sweep 6.11 was cut by a maintenance reboot at 16:25 UTC on 2026-08-12, ~9h in. Docker's
# `restart: unless-stopped` (tools/gen-compose-prod.py) brought all four stacks back; the chain
# drivers were nohup'd processes and did not come back. So 20 agents ran for a further 10 hours
# with nothing able to stop them, advance a lane, or export a submission — against a 6h budget.
# The same shape cost 4.5 days in 6.10 (v2docs/INCIDENT_6.10_MEMORY.md §4).
#
# The asymmetry is the whole point: the SUPERVISOR cannot survive a reboot, but the WORK can.
# So the guard runs at boot and tears the work down. A stack whose driver is gone is an orphan
# by definition — there is no case where resurrecting one unattended is correct.
#
# Usage: bash tests/pbench/test_reboot_guard.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UNIT="$ROOT/docker/pbench-reboot-guard.service"
GUARD="$ROOT/scripts/pbench_reboot_guard.sh"
rc=0
ok()   { echo "PASS $*"; }
fail() { echo "FAIL $*"; rc=1; }

# --- 1. the unit exists and runs at boot --------------------------------------
[ -f "$UNIT" ] && ok "a reboot-guard unit is shipped" || fail "no unit — nothing runs at boot"
grep -qE '^WantedBy=multi-user.target' "$UNIT" 2>/dev/null \
    && ok "the unit is wanted by multi-user.target, so it runs on every boot" \
    || fail "the unit is not wired to a boot target"
# Docker restarts the stacks; the guard must run after docker is up or it finds nothing.
grep -qE '^After=.*docker' "$UNIT" 2>/dev/null \
    && ok "it runs after docker, so the resurrected containers are visible to it" \
    || fail "no After=docker — the guard could run before the containers come back"
grep -qE '^Type=oneshot' "$UNIT" 2>/dev/null \
    && ok "oneshot: it does its work and exits" \
    || fail "not a oneshot service"

# --- 2. CONTAINER SAFETY ------------------------------------------------------
# This is the assertion that matters most. CLAUDE.md: never stop a container this project did
# not create. This host runs 11 kind clusters belonging to another project, and a boot-time
# script that gets this wrong destroys someone else's work with no human watching.
[ -f "$GUARD" ] && ok "the guard script exists" || fail "no guard script"
if [ -f "$GUARD" ]; then
    grep -qE 'omcgitea' "$GUARD" \
        && ok "the guard scopes itself to omcgitea projects" \
        || fail "the guard does not scope by this project's prefix"
    # A bare `docker stop $(docker ps -q)` or any unfiltered prune is fatal here.
    body=$(sed 's/#.*//' "$GUARD")
    printf '%s' "$body" | grep -qE 'docker (system )?prune|docker stop \$\(docker ps -q\)|docker rm -f \$\(docker ps -aq\)' \
        && fail "the guard contains an unfiltered global docker operation" \
        || ok "no unfiltered global docker operation"
    printf '%s' "$body" | grep -qE '\-\-all\b|\-a\b.*prune' \
        && fail "the guard uses a global -a/--all form" \
        || ok "no global -a/--all form"
    # It must tear down by COMPOSE PROJECT, so bind-mounted data survives for a later export.
    printf '%s' "$body" | grep -qE 'com\.docker\.compose\.project' \
        && ok "it enumerates stacks by compose project label" \
        || fail "it does not enumerate by compose project label"
fi

# --- 3. it must NOT destroy the data ------------------------------------------
# `make clean` wipes DATA_ROOT. At boot that would destroy the Gitea repos holding work the
# agents already did — exactly what let ctags and pandoc be recovered after their export
# failed. The guard stops containers; it never deletes state.
if [ -f "$GUARD" ]; then
    sed 's/#.*//' "$GUARD" | grep -qE 'make clean|rm -rf .*(DATA_ROOT|claude-team-data)' \
        && fail "the guard deletes data — the repos are the only copy of the agents' work" \
        || ok "the guard stops containers without deleting any data"
fi

# --- 4. it must leave a trace -------------------------------------------------
# 6.10 ran 4.5 days unnoticed. Whatever the guard does at boot has to be discoverable
# afterwards, or the next incident is just as silent.
if [ -f "$GUARD" ]; then
    sed 's/#.*//' "$GUARD" | grep -qE 'logger|>>.*\.log|tee' \
        && ok "the guard records what it tore down" \
        || fail "the guard leaves no record — a silent teardown is its own mystery"
fi

# --- 5. BEHAVIOURAL: it must select ours and ignore everything else -----------
# Greps cannot prove the selection is safe. Stand up one container labelled like ours and one
# labelled like a foreign project, and require the guard's own selection to return only ours.
if ! sudo docker info >/dev/null 2>&1; then
    echo "SKIP behavioural check (no docker)"
elif [ ! -f "$GUARD" ]; then
    echo "SKIP behavioural check (no guard script)"
else
    MINE=omcgitea-guardtest-$$
    THEIRS=cluster-guardtest-$$
    sudo docker run -d --name "$MINE-gitea-1" --label com.docker.compose.project="$MINE" \
        alpine:3 sleep 60 >/dev/null 2>&1
    sudo docker run -d --name "$THEIRS-node-1" --label com.docker.compose.project="$THEIRS" \
        alpine:3 sleep 60 >/dev/null 2>&1
    SEL=$(PBENCH_GUARD_DRY_RUN=1 bash "$GUARD" 2>/dev/null)
    printf '%s' "$SEL" | grep -q "$MINE" \
        && ok "the guard finds our orphaned stack" \
        || fail "the guard did not find our stack (dry run returned: $(printf '%s' "$SEL" | tr '\n' ' '))"
    printf '%s' "$SEL" | grep -q "$THEIRS" \
        && fail "the guard selected a FOREIGN project — it would destroy another user's work" \
        || ok "the guard ignores the foreign project"
    for p in "$MINE" "$THEIRS"; do
        sudo docker rm -f $(sudo docker ps -aq --filter "label=com.docker.compose.project=$p") \
            >/dev/null 2>&1 || true
    done
fi

exit $rc
