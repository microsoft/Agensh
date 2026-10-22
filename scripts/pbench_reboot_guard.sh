#!/usr/bin/env bash
# Stop orphaned omcgitea Compose projects after host boot, preserving profile data.
# PBENCH_GUARD_DRY_RUN=1 lists affected projects without stopping containers.
set -u
ROOT="${PBENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
LOG="${PBENCH_GUARD_LOG:-$ROOT/out/reboot-guard.log}"
DRY="${PBENCH_GUARD_DRY_RUN:-0}"

DOCKER="docker"
command -v sudo >/dev/null 2>&1 && DOCKER="sudo docker"

projects=$($DOCKER ps --format '{{.Label "com.docker.compose.project"}}' 2>/dev/null \
           | grep -E '^omcgitea-' | sort -u)

if [ "$DRY" = "1" ]; then
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
    profile="${proj#omcgitea-}"
    n=$($DOCKER ps -q --filter "label=com.docker.compose.project=$proj" 2>/dev/null | grep -c . || true)
    say "stopping $proj ($n containers, profile=$profile) — data preserved"
    if ! (cd "$ROOT" && timeout 300 make down PROFILE="$profile" >>"$LOG" 2>&1); then
        # Label-scoped fallback handles projects whose generated Compose files are gone.
        say "WARN: make down failed for $proj; stopping its containers by label"
        ids=$($DOCKER ps -q --filter "label=com.docker.compose.project=$proj" 2>/dev/null)
        [ -n "$ids" ] && $DOCKER stop -t 10 $ids >>"$LOG" 2>&1 || true
    fi
done

say "done; the sweep driver did not survive the reboot, so these were orphans"
say "to resume: re-run the sweep driver — pbench_chain.sh salvages an interrupted task"
