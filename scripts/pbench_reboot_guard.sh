#!/usr/bin/env bash
# pbench_reboot_guard.sh — stop ProgramBench stacks that outlived their driver.
#
# WHY THIS EXISTS
# Agents and mini-routers carry `restart: unless-stopped` (tools/gen-compose-prod.py), but the
# launchers are nohup'd processes. A reboot therefore resurrects the WORK and not its
# SUPERVISOR: the agents keep running past their budget, with nothing able to stop them,
# advance to the next task, or export a submission.
#
# A stack whose launcher is gone is an orphan by definition: HOURS, the task sequence and the
# export all live in the launcher. There is no case where resurrecting one unattended is correct,
# so the guard tears them down at boot.
#
# WHAT IT DOES NOT DO
# It does not delete anything. `make down` stops containers and leaves DATA_ROOT alone, so the
# Gitea repos survive and a submission can still be exported afterwards, including one whose
# export failed during the run.
#
# Install: see docker/pbench-reboot-guard.service and README.md; substitute the
#          checkout's absolute path before installing the service.
# Dry run:  PBENCH_GUARD_DRY_RUN=1 bash scripts/pbench_reboot_guard.sh
set -u
ROOT="${PBENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
LOG="${PBENCH_GUARD_LOG:-$ROOT/out/reboot-guard.log}"
DRY="${PBENCH_GUARD_DRY_RUN:-0}"

DOCKER="docker"
command -v sudo >/dev/null 2>&1 && DOCKER="sudo docker"

# Enumerate RUNNING compose projects, then keep only ours.
#
# The prefix filter is the safety boundary and it is not negotiable: this host also runs
# `kind` clusters belonging to another project (containers named cluster-*), and CLAUDE.md
# forbids touching any container this project did not create. We select by the compose PROJECT
# LABEL and require the `omcgitea-` prefix -- never by name substring, never with -a/--all,
# never with prune.
projects=$($DOCKER ps --format '{{.Label "com.docker.compose.project"}}' 2>/dev/null \
           | grep -E '^omcgitea-' | sort -u)

if [ "$DRY" = "1" ]; then
    # Print the selection without acting.
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
