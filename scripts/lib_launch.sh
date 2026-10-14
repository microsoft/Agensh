# Shared by scripts/launch_single_node.sh (compose) and scripts/launch_multi_node.sh
# (AKS). Sourced, never executed.
#
# Callers set before sourcing: ROOT, MODE, TASKS (space-separated task ids) and
# HOURS. A launch runs its TASKS in order, each on its own profile
# pbench-<MODE>-<short task>. Everything that differs between the two paths
# (compose vs k8s, image preparation) stays in the launchers.
#
# Run identity: RUN_ID (default: the UTC start time) names this launch, so its
# trajectories and logs never collide with another launch of the same profile.

: "${ROOT:?}" "${MODE:?}" "${TASKS:?}" "${HOURS:?}"
PB_REPO="${PROGRAMBENCH_REPO:-$HOME/programbench}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
[[ "$RUN_ID" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "FATAL: RUN_ID='$RUN_ID' must match [A-Za-z0-9._-]+" >&2; exit 1; }
SUFFIX="$MODE.$RUN_ID"
TRAJ_ROOT="${TRAJ_ROOT:-$HOME/pbench-trajectories}"
DRIVER_LOG="$ROOT/out/$MODE.driver.log"

log() { echo "[$MODE $(date -u +%H:%M:%S)] $*" | tee -a "$DRIVER_LOG"; }
short() { local t="${1#*__}"; echo "${t%%.*}" | tr -cd 'a-z0-9-'; }
task_profile() { echo "pbench-$MODE-$(short "$1")"; }

# The launch shell must not decide what runs. Compose interpolation ranks the
# shell environment above --env-file (make runs compose under sudo -E), so any
# `${KEY:-default}` in gen-compose-prod.py resolves from the shell first, and
# gen-k8s.py takes ANTHROPIC_MODEL, PBENCH_LLM_UPSTREAM and UPSTREAM_AUTH_TOKEN
# from the shell over the profile. A shell that exports ANTHROPIC_MODEL,
# ANTHROPIC_BASE_URL or ANTHROPIC_AUTH_TOKEN for its own use would otherwise
# hand the agents another model, a route past egress-proxy, or a personal
# token. Every key the profile sets is unset from the shell when the values
# differ; the key is logged, never its value. No launcher-owned variable (HOURS,
# WORKERS, TASKS, RUN_ID; on multi-node also AZ_SUBSCRIPTION, PBENCH_ACR,
# PBENCH_REGISTRY, PBENCH_IMAGE_DIGESTS) appears in a profile.
scrub_shadowed_env() {  # $1 = profile env file
    local f="$1" k v cur n=0
    [ -r "$f" ] || return 0
    while IFS='=' read -r k v; do
        case "$k" in ''|'#'*) continue ;; esac
        [[ "$k" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
        v="${v%\"}"; v="${v#\"}"; v="${v%\'}"; v="${v#\'}"   # .env quoting
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

# The upstream auth header exactly as egress-proxy (scripts/strip_metadata_proxy.py)
# sends it for the profile's UPSTREAM_AUTH_STYLE, so a probe authenticates the
# way the run will. Printed for `curl -H @-`: the token never reaches an argv.
upstream_auth_header() {  # $1 UPSTREAM_AUTH_STYLE  $2 token
    local style="${1,,}"
    case "${style//[[:space:]]/}" in
        api-key) printf 'api-key: %s\n' "$2" ;;
        *)       printf 'Authorization: Bearer %s\n' "$2" ;;
    esac
}

# Refuse to start while a chain or runner for one of this launch's profiles is
# alive: two stacks on one profile share ports, data and a namespace. Matched on
# PROFILE in the process environment, exactly.
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

# image_file_matches IMG PATH HOST_FILE: the file baked at PATH in IMG is
# byte-identical to HOST_FILE. False on a missing image, file, or host file.
image_file_matches() {
    [ -s "$3" ] || return 1
    sudo docker run --rm --pull never --network none --entrypoint cat "$1" "$2" 2>/dev/null | cmp -s - "$3"
}

# Task dirs under an OUT_ROOT that pbench_chain.sh would salvage into the next
# launch. Must filter exactly as the chain's salvage_interrupted does.
unfinished_runs() { ls "$1" 2>/dev/null | grep '__' | grep -vE '\.archived$|\.aborted$|\.interrupted$'; }

# Names of extra variables exported into the RUN / EVAL phase of every task, on
# top of the common set below. The launcher sets these before run_chain. A value
# that belongs to one profile only is set per task by an optional
# launch_profile_env <profile>, which run_chain calls before reading them.
LAUNCH_RUN_VARS=()
LAUNCH_EVAL_VARS=()

# The tasks run back to back. RUN is in the foreground; eval is detached so the
# next task starts at once instead of waiting 5-30 min for scoring. Eval touches
# no containers and each task has its own OUT_ROOT, so it cannot collide with
# the next run.
EVAL_PIDS=()
run_chain() {
    local task p common v run_extra eval_extra rc
    for task in $TASKS; do
        p="$(task_profile "$task")"
        common=(
            PROFILE="$p"
            SUFFIX="$SUFFIX"
            TASKS_ENV="$task"
            TRAJ_ROOT="$TRAJ_ROOT"
            OUT_ROOT="$ROOT/out/$p"
            RUN_SCRIPT="./scripts/pbench_run.sh"
            PROGRAMBENCH_REPO="$PB_REPO"
            HOURS="$HOURS"
        )
        if declare -F launch_profile_env >/dev/null; then launch_profile_env "$p"; fi
        run_extra=(); for v in "${LAUNCH_RUN_VARS[@]}"; do run_extra+=("$v=${!v}"); done
        eval_extra=(); for v in "${LAUNCH_EVAL_VARS[@]}"; do eval_extra+=("$v=${!v}"); done
        log "starting $task (${HOURS}h) profile=$p"
        env "${common[@]}" PHASE=run "${run_extra[@]}" PATH="$HOME/.local/bin:$PATH" \
            "$ROOT/scripts/pbench_chain.sh" > "$ROOT/out/chain-$p.driver.log" 2>&1
        rc=$?
        log "finished RUN $task (rc=$rc) — eval detached"
        env "${common[@]}" PHASE=eval "${eval_extra[@]}" PATH="$HOME/.local/bin:$PATH" \
            nohup "$ROOT/scripts/pbench_chain.sh" >> "$ROOT/out/chain-$p.driver.log" 2>&1 &
        EVAL_PIDS+=($!)
        log "  eval $task pid=$! (runs alongside the next task)"
    done
    # Do not exit while a detached eval is still scoring the last task.
    [ ${#EVAL_PIDS[@]} -gt 0 ] && { log "waiting on ${#EVAL_PIDS[@]} detached eval(s)"; wait "${EVAL_PIDS[@]}" 2>/dev/null; }
    log "ALL DONE"
}
