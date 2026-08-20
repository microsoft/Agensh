#!/usr/bin/env bash
# pbench_1team_sweep.sh — sweep 6.11 re-run: all 20 tasks, 4 chains of 5.
#
# WHAT HAPPENED
# The 2026-08-12 07:23 UTC launch ran 4 chains of 5. A maintenance reboot at 16:25 UTC killed
# every driver (nohup'd) while docker's `restart: unless-stopped` brought the stacks back, so
# 20 agents ran a further 10 hours headless. Four tasks completed cleanly before that (ctags,
# pandoc, gromacs, ffmpeg); four were mid-flight (typst, php-src, quickjs, cppcheck); twelve
# never started.
#
# WHY 4 CHAINS OF 5
# Four concurrent stacks (20 agents) is the footprint whose memory behaviour is measured: peak
# 31.8 GB of the slice's 402 GB. Five tasks per chain is ~30h, which spans this host's
# roughly-daily maintenance window (~12:35-13:36 UTC) and its reboot (~16:25 UTC), so the tail
# of each chain will likely be cut. That is now bounded and recoverable rather than the 10-hour
# headless burn it was on 2026-08-12: the reboot guard stops stacks cleanly at boot, DATA_ROOT
# survives, and a cut task's submission still exports offline from its Gitea repo (which is
# exactly how ctags was recovered from a reported 0.00% to 39.05%).
# Re-run this driver after a reboot to resume; pbench_chain.sh salvages an interrupted task.
#
# NOTE ON THE STAGGER
# On 2026-08-12 every container in all four stacks froze at 12:53:43 UTC and did not run again
# until 13:36:21 -- 43 minutes. dockerd's stdio copier failed for exactly that window (4,460
# `copy stream failed`, none before or after), so agents blocked in write() on a full stdout
# pipe: alive, unkilled, silent. Because the stacks were staggered, each one's 6h clock expired
# at a different point relative to the freeze and the damage LOOKED per-task: ctags -31m,
# pandoc -36m, gromacs -41m, ffmpeg -0m. It was one event, unevenly charged.
# A stagger of 0 would make such an event hit all four equally and keep cross-task comparison
# clean; 600s is the operator's choice. If a run comes out uneven again, check
# scripts/pbench_traj_metrics.sh for max_gap_min / shortfall_min before concluding anything
# about agent behaviour.
#
# WHAT IS DIFFERENT SINCE THE FIRST 6.11 LAUNCH
#   1. docker/pbench-reboot-guard.service (installed + enabled). On every boot it tears down
#      any surviving omcgitea stack, so a reboot now costs a clean stop instead of 10 hours of
#      headless burn. It stops containers only -- DATA_ROOT survives, so a submission can still
#      be exported from the Gitea repo afterwards.
#   2. teardown() now quiesces the agents BEFORE exporting, retries the clone 3x with backoff,
#      and writes an EXPORT_FAILED marker instead of a silent empty tarball. In this sweep
#      ctags and pandoc both exported EMPTY after Gitea 504s and scored 0.00%; recovered
#      offline, ctags is 39.05%. See tests/pbench/test_export_resilience.sh.
#   3. scripts/pbench_score.py excludes EXPORT_FAILED tasks from the macro instead of
#      averaging their fake zero in.
#
set -u
# Repo root = where THIS script lives, not a fixed checkout. This tree is a
# standalone snapshot; a pinned $HOME/agensteam would read compose files,
# .env.<profile> and templates from a different tree than the one invoked.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || { echo "FATAL: cannot cd $ROOT" >&2; exit 1; }

ROUND="${ROUND:-6.11}"
SLUG="${SLUG:-s611}"
HOURS="${HOURS:-6}"
STAGGER="${STAGGER:-600}"          # 10 min between chain starts (operator's choice)
TRAJ_ROOT="${TRAJ_ROOT:-$HOME/agensteam_traj_eng_sweep_6.11_1_team}"
PB_REPO="${PROGRAMBENCH_REPO:-$HOME/programbench}"
DRIVER_LOG="$ROOT/out/1team-sweep${ROUND}b.driver.log"

# Four chains, FIVE tasks each -- the full 20-task sweep, re-run from scratch.
# The first run's four completed tasks (ctags, pandoc, gromacs, ffmpeg) were all confounded by
# the 2026-08-12 freeze, which cost them 31-43 min of a 360 min budget, so they are re-run here
# rather than carried over. Their trajectories are preserved in
# ~/agensteam_traj_eng_sweep_6.11_1_team.run1-frozen.
# Chain openers are the four with the most sweep history, so the first 6h window stays
# comparable to 6.9/6.10.
CHAINS=(
  "b:universal-ctags__ctags.243595e  c:typst__typst.88356d0        i:osgeo__gdal.0847f12        m:tstack__lnav.ee34494        q:stathissideris__ditaa.f2286c4"
  "f:jgm__pandoc.5caad90             d:php__php-src.c891263        j:duckdb__duckdb.bdb65ec     n:ast-grep__ast-grep.dde0fe0  r:tinycc__tinycc.9b8765d"
  "e:gromacs__gromacs.665ea4c        g:bellard__quickjs.d7ae12a    k:nukesor__pueue.8b9d6fe     o:alecthomas__chroma.8d04def  s:zk-org__zk.10d93d5"
  "a:ffmpeg__ffmpeg.360a402          h:danmar__cppcheck.0a5b103    l:samtools__samtools.aa823b5 p:johnkerl__miller.8d85b46    t:osgeo__proj.75d455c"
)

mkdir -p "$TRAJ_ROOT" "$ROOT/out"
log() { echo "[sweep${ROUND}b $(date -u +%H:%M:%S)] $*" | tee -a "$DRIVER_LOG"; }
short() { t="${1#*__}"; echo "${t%%.*}" | tr -cd 'a-z0-9-'; }

ALL=()
for c in "${CHAINS[@]}"; do for e in $c; do ALL+=("$e"); done; done

# --- Preflight --------------------------------------------------------------
log "preflight over ${#ALL[@]} tasks in ${#CHAINS[@]} chains"
fail=0
for e in "${ALL[@]}"; do
    L="${e%%:*}"; task="${e#*:}"
    p="org-pbench-method-2a-${SLUG}$L"
    [ -f "$ROOT/.env.$p" ] || { log "FATAL: .env.$p missing"; fail=1; continue; }

    img="omcgitea-agent-$(short "$task"):pertask-claude"
    sudo docker image inspect "$img" >/dev/null 2>&1 || { log "FATAL: image missing: $img"; fail=1; }
    got="$(awk -F= '$1=="AGENT_IMAGE"{print $2; exit}' "$ROOT/.env.$p")"
    [ "$got" = "$img" ] || { log "FATAL: .env.$p AGENT_IMAGE=$got expected $img"; fail=1; }

    sudo docker run --rm --entrypoint sh "$img" -c 'test -f /opt/claude-agent-acp/dist/index.js' 2>/dev/null \
        || { log "FATAL: $img has no claude-agent-acp"; fail=1; }
    k="$(awk -F= '$1=="AGENT_KIND"{print $2; exit}' "$ROOT/.env.$p")"
    [ "$k" = "claude" ] || { log "FATAL: .env.$p AGENT_KIND=$k expected claude"; fail=1; }
    m="$(awk -F= '$1=="ANTHROPIC_MODEL"{print $2; exit}' "$ROOT/.env.$p")"
    [ "$m" = "claude-opus-5" ] || { log "FATAL: .env.$p ANTHROPIC_MODEL=$m expected claude-opus-5"; fail=1; }
    o="$(awk -F= '$1=="UPSTREAM_PATH_OVERRIDE"{print $2; exit}' "$ROOT/.env.$p")"
    [ -z "$o" ] || { log "FATAL: .env.$p UPSTREAM_PATH_OVERRIDE='$o' must be empty"; fail=1; }

    ci="programbench/${task/__/_1776_}:task_cleanroom_v6"
    sudo docker image inspect "$ci" >/dev/null 2>&1 || { log "FATAL: cleanroom missing: $ci"; fail=1; }

    # A non-empty leftover data dir makes pbench_run_1team.sh die; a leftover out dir makes the
    # chain "salvage" a dead run into this sweep. An EMPTY dir is what `make clean` leaves and
    # is harmless, so only refuse if it actually holds something.
    dd="$ROOT/.claude-team-data-${SLUG}$L"
    if [ -d "$dd" ] && [ -n "$(sudo ls -A "$dd" 2>/dev/null)" ]; then
        log "FATAL: stale non-empty $dd — archive it first"; fail=1
    fi
    [ -d "$ROOT/out/pbench-sweep${ROUND}-${SLUG}$L" ] \
        && { log "FATAL: stale out/pbench-sweep${ROUND}-${SLUG}$L — archive it first"; fail=1; }
    if compgen -G "$TRAJ_ROOT/*.2a-${SLUG}$L-sweep${ROUND}" >/dev/null 2>&1; then
        log "FATAL: $TRAJ_ROOT already holds 2a-${SLUG}$L-sweep${ROUND}"; fail=1
    fi
done
for img in omcgitea-board:local omcgitea-mini-router:local; do
    sudo docker image inspect "$img" >/dev/null 2>&1 || { log "FATAL: image missing: $img"; fail=1; }
done
dupes="$(for e in "${ALL[@]}"; do
    awk -F= '$1=="EDGE_HTTP_PORT"||$1=="EDGE_MM_PORT"{print $2}' "$ROOT/.env.org-pbench-method-2a-${SLUG}${e%%:*}" 2>/dev/null
done | sort | uniq -d)"
[ -z "$dupes" ] || { log "FATAL: duplicate ports: $dupes"; fail=1; }
subdupes="$(for e in "${ALL[@]}"; do
    awk -F= '$1 ~ /^PBENCH_SUBNET_/{print $2}' "$ROOT/.env.org-pbench-method-2a-${SLUG}${e%%:*}" 2>/dev/null
done | sort | uniq -d)"
[ -z "$subdupes" ] || { log "FATAL: duplicate subnets: $subdupes"; fail=1; }

sm="$(systemctl show pbench.slice -p MemoryMax --value 2>/dev/null)"
case "$sm" in
    ''|infinity) log "FATAL: pbench.slice has no MemoryMax"; fail=1 ;;
    *) log "pbench.slice MemoryMax=$sm ($(( sm / 1073741824 )) GiB)" ;;
esac

# The reboot guard is the reason a 12h chain is a reasonable bet on this host.
if [ "$(systemctl is-enabled pbench-reboot-guard.service 2>/dev/null)" = "enabled" ]; then
    log "reboot guard enabled — a maintenance reboot will stop stacks cleanly"
else
    log "FATAL: pbench-reboot-guard.service not enabled (see docker/pbench-reboot-guard.service)"; fail=1
fi

U="$(awk -F= '$1=="PBENCH_LLM_UPSTREAM"{print $2; exit}' "$ROOT/.env.org-pbench-method-2a-${SLUG}c")"
K="$(awk -F= '$1=="UPSTREAM_AUTH_TOKEN"{print $2; exit}' "$ROOT/.env.org-pbench-method-2a-${SLUG}c")"
M="$(awk -F= '$1=="ANTHROPIC_MODEL"{print $2; exit}' "$ROOT/.env.org-pbench-method-2a-${SLUG}c")"
code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 60 \
    -H "x-api-key: $K" -H 'anthropic-version: 2023-06-01' -H 'content-type: application/json' \
    -X POST "$U/v1/messages" \
    -d "{\"model\":\"$M\",\"max_tokens\":8,\"messages\":[{\"role\":\"user\",\"content\":\"ok\"}]}" 2>/dev/null)
[ "$code" = "200" ] && log "upstream OK ($M -> HTTP 200)" \
                    || { log "FATAL: upstream $M -> HTTP $code"; fail=1; }

[ "$fail" = "0" ] || { log "preflight FAILED — nothing launched"; exit 1; }
log "preflight OK: ${#ALL[@]} profiles, claude path, slice armed, reboot guard on, upstream live"
[ "${PREFLIGHT_ONLY:-0}" = "1" ] && { log "PREFLIGHT_ONLY=1 — stopping before launch"; exit 0; }

# --- Launch -----------------------------------------------------------------
run_chain() {
    local chain="$1"; shift
    for e in "$@"; do
        local L="${e%%:*}" task="${e#*:}"
        local profile="org-pbench-method-2a-${SLUG}$L"
        log "chain$chain: starting $L $task (${HOURS}h) profile=$profile"
        env \
            PROFILE="$profile" \
            INSTANCE="${SLUG}$L" \
            SUFFIX="2a-${SLUG}$L-sweep${ROUND}" \
            TASKS_ENV="$task" \
            TRAJ_ROOT="$TRAJ_ROOT" \
            OUT_ROOT="$ROOT/out/pbench-sweep${ROUND}-${SLUG}$L" \
            RUN_SCRIPT="./scripts/pbench_run_1team.sh" \
            PROGRAMBENCH_REPO="$PB_REPO" \
            HOURS="$HOURS" \
            PATH="$HOME/.local/bin:$PATH" \
            ./scripts/pbench_chain.sh > "$ROOT/out/chain-sweep${ROUND}-${SLUG}$L.driver.log" 2>&1
        log "chain$chain: finished $L $task (rc=$?)"
    done
    log "chain$chain: ALL DONE"
}

PIDS=()
i=0
for c in "${CHAINS[@]}"; do
    i=$((i+1))
    log "launching chain$i: $(for e in $c; do printf '%s ' "$(short "${e#*:}")"; done)"
    run_chain "$i" $c &
    PIDS+=($!)
    log "  chain$i pid=${PIDS[-1]}"
    [ "$i" -lt "${#CHAINS[@]}" ] && { log "  sleeping ${STAGGER}s"; sleep "$STAGGER"; }
done

log "=== ${#CHAINS[@]} chains running, 5 tasks each; ~$(( 5 * HOURS ))h + $(( (${#CHAINS[@]}-1) * STAGGER / 60 ))m stagger ==="
wait "${PIDS[@]}"
log "=== sweep ${ROUND}b complete ==="
