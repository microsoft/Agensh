# Shared launch helpers; source after ROOT, MODE, TASKS and HOURS are set.
# Profile names isolate live state; the run ID names the archived trajectory.
: "${ROOT:?}" "${MODE:?}" "${TASKS:?}" "${HOURS:?}"
PB_REPO="${PROGRAMBENCH_REPO:-$HOME/programbench}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
[[ "$RUN_ID" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "FATAL: RUN_ID='$RUN_ID' must match [A-Za-z0-9._-]+" >&2; exit 1; }
PROFILE_SUFFIX="${PROFILE_SUFFIX:-}"
[[ -z "$PROFILE_SUFFIX" || "$PROFILE_SUFFIX" =~ ^[a-z0-9][a-z0-9-]*$ ]] \
    || { echo "FATAL: PROFILE_SUFFIX must begin with a lowercase letter or digit and contain only lowercase letters, digits and hyphens" >&2; exit 2; }
SUFFIX="$MODE.$RUN_ID"
TRAJ_ROOT="${TRAJ_ROOT:-$HOME/pbench-trajectories}"
DRIVER_LOG="$ROOT/out/$MODE.driver.log"

log() { echo "[$MODE $(date -u +%H:%M:%S)] $*" | tee -a "$DRIVER_LOG"; }
short() { local t="${1#*__}"; echo "${t%%.*}" | tr -cd 'a-z0-9-'; }
task_profile() { echo "pbench-$MODE-$(short "$1")${PROFILE_SUFFIX:+-$PROFILE_SUFFIX}"; }

scrub_shadowed_env() {
    # Compose prefers exported shell values over --env-file, so remove conflicts.
    local f="$1" k v cur n=0
    [ -r "$f" ] || return 0
    while IFS='=' read -r k v; do
        case "$k" in ''|'#'*) continue ;; esac
        [[ "$k" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
        v="${v%\"}"; v="${v#\"}"; v="${v%\'}"; v="${v#\'}"
        [ -n "${!k+x}" ] || continue
        cur="${!k}"
        [ "$cur" = "$v" ] && continue
        log "shadow: unset $k — the launch shell would outrank the profile"
        unset "$k"
        n=$((n + 1))
    done < "$f"
    [ "$n" -gt 0 ] && log "shadow: scrubbed $n key(s) from $(basename "$f"); the profile is now authoritative"
    return 0
}

upstream_auth_header() {
    local style="${1,,}"
    case "${style//[[:space:]]/}" in
        api-key) printf 'api-key: %s\n' "$2" ;;
        *)       printf 'Authorization: Bearer %s\n' "$2" ;;
    esac
}

refuse_double_launch() {
    local rc=0 task p pid pr
    for task in $TASKS; do
        p="$(task_profile "$task")"
        for pid in $(pgrep -f 'pbench_chain\.sh|pbench_run\.sh' 2>/dev/null); do
            pr="$(sudo cat "/proc/$pid/environ" 2>/dev/null | tr '\0' '\n' | awk '/^PROFILE=/{print substr($0, 9); exit}')"
            [ "$pr" = "$p" ] || continue
            log "FATAL: $p is already running (pid $pid) — refusing to double-launch"
            rc=1
        done
    done
    return $rc
}

image_file_matches() {
    # Compare the baked file itself; image timestamps do not prove its contents.
    [ -s "$3" ] || return 1
    sudo docker run --rm --pull never --network none --entrypoint cat "$1" "$2" 2>/dev/null | cmp -s - "$3"
}

unfinished_runs() { ls "$1" 2>/dev/null | grep '__' | grep -vE '\.archived$|\.aborted$|\.interrupted$'; }

EVAL_PIDS=()
run_chain() {
    local task p common rc
    for task in $TASKS; do
        p="$(task_profile "$task")"
        common=(
            PROFILE="$p"
            SUFFIX="$SUFFIX"
            TASKS_ENV="$task"
            TRAJ_ROOT="$TRAJ_ROOT"
            OUT_ROOT="$ROOT/out/$p"
            PROGRAMBENCH_REPO="$PB_REPO"
            HOURS="$HOURS"
        )
        log "starting $task (${HOURS}h) profile=$p"
        env "${common[@]}" PHASE=run PATH="$HOME/.local/bin:$PATH" \
            "$ROOT/scripts/pbench_chain.sh" > "$ROOT/out/chain-$p.driver.log" 2>&1
        rc=$?
        log "finished RUN $task (rc=$rc) — eval detached"
        # Evaluation consumes the exported submission while the next task runs.
        env "${common[@]}" PHASE=eval PATH="$HOME/.local/bin:$PATH" \
            nohup "$ROOT/scripts/pbench_chain.sh" >> "$ROOT/out/chain-$p.driver.log" 2>&1 &
        EVAL_PIDS+=($!)
        log "  eval $task pid=$! (runs alongside the next task)"
    done
    [ ${#EVAL_PIDS[@]} -gt 0 ] && { log "waiting on ${#EVAL_PIDS[@]} detached eval(s)"; wait "${EVAL_PIDS[@]}" 2>/dev/null; }
    log "ALL DONE"
}
