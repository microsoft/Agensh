#!/usr/bin/env bash
# pbench_reboot_guard.sh — stop ProgramBench stacks that outlived their driver.
#
# WHY THIS EXISTS
# Agents and mini-routers carry `restart: unless-stopped` (tools/gen-compose-prod.py), but the
# sweep drivers are nohup'd processes. A reboot therefore resurrects the WORK and not its
# SUPERVISOR. Sweep 6.11 was cut by a maintenance reboot on 2026-08-12 and 20 agents kept
# running for a further 10 hours against a 6h budget, with nothing able to stop them, advance a
# lane, or export a submission. Sweep 6.10 burned 4.5 days the same way.
#
# A stack whose driver is gone is an orphan by definition: HOURS, the task sequence and the
# export all live in the driver. There is no case where resurrecting one unattended is correct,
# so the guard tears them down at boot.
#
# WHAT IT DOES NOT DO
# It does not delete anything. `make down` stops containers and leaves DATA_ROOT alone, so the
# Gitea repos survive and a submission can still be exported afterwards -- which is exactly how
# ctags and pandoc were recovered when their export failed in 6.11.
#
# Install:  sudo cp docker/pbench-reboot-guard.service /etc/systemd/system/
#           sudo systemctl daemon-reload && sudo systemctl enable pbench-reboot-guard.service
# Dry run:  PBENCH_GUARD_DRY_RUN=1 bash scripts/pbench_reboot_guard.sh
set -u
# Default to the checkout this script lives in. PBENCH_ROOT still overrides, which
# is what the systemd unit uses when it runs the guard from an absolute install path.
ROOT="${PBENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
LOG="${PBENCH_GUARD_LOG:-$ROOT/out/reboot-guard.log}"
DRY="${PBENCH_GUARD_DRY_RUN:-0}"

DOCKER="docker"
command -v sudo >/dev/null 2>&1 && DOCKER="sudo docker"

# Enumerate RUNNING compose projects, then keep only ours.
#
# The prefix filter is the safety boundary and it is not negotiable: this host also runs 11
# `kind` clusters belonging to another project (containers named cluster-*), and CLAUDE.md
# forbids touching any container this project did not create. We select by the compose PROJECT
# LABEL and require the `omcgitea-` prefix -- never by name substring, never with -a/--all,
# never with prune.
projects=$($DOCKER ps --format '{{.Label "com.docker.compose.project"}}' 2>/dev/null \
           | grep -E '^omcgitea-' | sort -u)

if [ "$DRY" = "1" ]; then
    # Used by tests/pbench/test_reboot_guard.sh to assert the selection without acting.
    printf '%s\n' "$projects"
    exit 0
fi

mkdir -p "$(dirname "$LOG")" 2>/dev/null || true
say() { echo "[reboot-guard $(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }

if [ -z "$projects" ]; then
    say "no omcgitea stacks running; nothing to do"
    exit 0
fi

say "found $(printf '%s\n' "$projects" | grep -c .) orphaned stack(s) after boot:"
printf '%s\n' "$projects" | sed 's/^/    /' | tee -a "$LOG"

for proj in $projects; do
    # `make down` == `docker compose down`: stops and removes containers, keeps the host
    # bind-mounts. PROFILE is the project name minus the omcgitea- prefix.
    profile="${proj#omcgitea-}"
    n=$($DOCKER ps -q --filter "label=com.docker.compose.project=$proj" 2>/dev/null | grep -c . || true)
    say "stopping $proj ($n containers, profile=$profile) — data preserved"
    if ! (cd "$ROOT" && timeout 300 make down PROFILE="$profile" >>"$LOG" 2>&1); then
        # Fall back to stopping the containers directly, still scoped to this project label.
        say "WARN: make down failed for $proj; stopping its containers by label"
        ids=$($DOCKER ps -q --filter "label=com.docker.compose.project=$proj" 2>/dev/null)
        [ -n "$ids" ] && $DOCKER stop -t 10 $ids >>"$LOG" 2>&1 || true
    fi
done

say "done; the sweep driver did not survive the reboot, so these were orphans"
say "to resume: re-run the sweep driver — pbench_chain.sh salvages an interrupted task"
