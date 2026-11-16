#!/bin/bash
# Source-only frozen native functions, NOT ProgramBench main.
# Retain the original up-slot/run-slot recipes, but NEVER implicitly add
# ProgramBench's private-reference overlay/default ENV_FILE. The cold owner
# supplies a frozen command containing only our generated base/safe overlay.
make() {
    local target="$1" arg profile_seen=0
    shift
    case "$target" in up-slot|run-slot) ;; *) return 64 ;; esac
    for arg in "$@"; do
        case "$arg" in
          PROFILE=*) [ "$arg" = "PROFILE=${COUNT14_NATIVE_PROFILE:?}" ] || return 64;profile_seen=1 ;;
          UP_FLAGS=*|SERVICES=*|SERVICE=*|NAME=*) ;;
          *) return 64 ;;
        esac
    done
    [ "$profile_seen" = 1 ] || return 64
    command "${COUNT14_NATIVE_MAKE:?}" "$target" "$@" \
        "ENV_FILE=${COUNT14_NATIVE_ENV_FILE:?}" \
        "COMPOSE_BASE=${COUNT14_NATIVE_COMPOSE_BASE:?}" \
        "COMPOSE=${COUNT14_NATIVE_COMPOSE_COMMAND:?}"
}
# Never let sudo drop DOCKER_HOST and silently hit the system root disk.
# This is local to these frozen native functions, not a host/sudo configuration.
sudo() {
    [ "$1" != -n ] || shift
    if [ "$1" = docker ]; then
        shift
        case "${COUNT14_NATIVE_DOCKER_SOCKET:?}" in
          unix:///mnt/ptb-scratch2/*|unix:///mnt/ptb-scratch/*) ;;
          *) return 64 ;;
        esac
        "${COUNT14_NATIVE_DOCKER:?}" --host "$COUNT14_NATIVE_DOCKER_SOCKET" "$@"
    else
        [ "$EUID" = 0 ] || return 64
        command "$@"
    fi
}
# Fixed host control child. All calls MUST use command substitution,
# so exec preserves the exact registered parent/child relation for SO_PEERCRED.
count14_spawn_ctl() {
    exec "${COUNT14_NATIVE_PYTHON:?}" -I -B "${COUNT14_NATIVE_SPAWN_CLIENT:?}" "$@"
}
count14_finish_same_launch() {
    local control mode active nonce attempt
    for attempt in $(seq 1 8); do
        control=$(count14_spawn_ctl FINISH "$1" "$2" "$3" 1) || return 2
        read -r mode active nonce <<< "$control"
        [ "$mode" != DONE ] || return 0
        [ "$mode" = RETAINED ] || return 2
        sleep "${PBENCH_SPAWN_POLL_S:-15}"
    done
    return 2  # retain SAME admitted effect; never repeat launch/wake/revive
}
retire_old_agent() {
    # Actual same-owner state machine. Original spawn BEGIN's exact nonce is
    # argument3; every CID is full length and checked against registration.
    count14_native_retire_stopped_exact "$@"
}
count14_native_retire_stopped_exact() {
    local wi="${1##*-worker}" ordinal="${2#spawn-}" nonce="$3" control mode active reply attempt
    shift 3
    [ "$#" = 2 ] || return 2
    # Repeated metadata BEGIN/POLL resumes the SAME job/Popen, never repeats a
    # model or native launch, and cannot authorize a different CID/nonce.
    for attempt in $(seq 1 8); do
        control=$(count14_spawn_ctl RETIRE_BEGIN "$wi" "$ordinal" "$nonce" "$@") || {
            sleep "${PBENCH_SPAWN_POLL_S:-15}"; continue;
        }
        read -r mode active reply <<< "$control"
        [ "$mode" != DONE ] || return 0
        [ "$mode" = RETAINED ] || return 2
        sleep "${PBENCH_SPAWN_POLL_S:-15}"
    done
    return 2  # retain SAME job and all original control children, no force
}
count14_run_original_spawn() {
    local required
    for required in log mm_dm_channel mm_post count14_native_retire_stopped_exact; do
        declare -F "$required" >/dev/null || return 64
    done
    spawn_loop "$@"
}

start_agent_containers() {  # $1 slot index, $2 worker name, $3 extra compose flags
    local wi="$1" wname="$2" flags="${3:-}" out try=1
    # up-slot reuses the rendered compose file, so parallel slot launches are safe.
    until out="$(cd "$ROOT" && make up-slot PROFILE="$PROFILE" UP_FLAGS="$flags" \
            SERVICES="agent-worker${wi} mini-router-worker${wi}" 2>&1)"; do
        log "WARN: container start failed for $wname (try $try); retrying in ${PBENCH_START_RETRY_S:-30}s"
        printf '%s\n' "$out" | tail -n 5 | while IFS= read -r l; do log "    $l"; done
        try=$((try + 1))
        sleep "${PBENCH_START_RETRY_S:-30}"
    done
    log "started containers for $wname"
}

launch_worker() {  # $1 slot index, $2 kickoff text: start the slot and wake it by task DM
    local wi="$1" kickoff="$2" wname="${ORG_NAME}-worker$1" dmch
    start_agent_containers "$wi" "$wname"
    sleep "${PBENCH_BRINGUP_SETTLE_S:-20}"
    dmch="$(mm_dm_channel "$wname" 2>/dev/null)" || dmch=""
    if [ -z "$dmch" ]; then
        dmch="$(mm_dm_channel "$wname" 2>/dev/null)" || dmch=""
    fi
    if [ -z "$dmch" ]; then
        log "WARN: no DM channel for $wname"
        return 0
    fi
    # The tag lets the router hold the first prompt until this task arrives.
    mm_post "$dmch" "$kickoff" '{"agensh_task":true}' >/dev/null 2>&1 \
        && log "woke $wname" \
        || log "WARN: DM wake failed for $wname"
}

retired_slot() {  # $1 slot count, $2 first slot to try -> a retired slot that is free to reuse
    local n="$1" first="$2" k i identities="$PROFILE_DATA_DIR/identities"
    # Round-robin from $2 so every slot is reused, not only the lowest-numbered ones.
    for k in $(seq 0 $((n - 1))); do
        i=$(( (first - 1 + k) % n + 1 ))
        sudo -n test -f "$identities/${ORG_NAME}-worker$i/pending.json" && continue
        sudo -n cat "$identities/${ORG_NAME}-worker$i/current.json" 2>/dev/null \
            | jq -e '.retired == true' >/dev/null 2>&1 && { echo "$i"; return 0; }
    done
    return 1
}

slot_containers() {  # $1 slot index -> IDs of its router then its agent container
    local service
    for service in "mini-router-worker$1" "agent-worker$1"; do
        sudo docker ps -aq --no-trunc --filter "label=com.docker.compose.project=omcgitea-$PROFILE" \
            --filter "label=com.docker.compose.service=$service"
    done
}

secret_call() {  # $1 slot index, $2 action (revive|wake), $3 JSON body -> response
    local secret
    secret=$(sudo docker ps -q --filter "label=com.docker.compose.project=omcgitea-$PROFILE" \
             --filter "label=com.docker.compose.service=secret-service" | head -1)
    [ -n "$secret" ] || { echo "secret-service is not running"; return 1; }
    sudo docker exec "$secret" python3 -c '
import os, sys, urllib.request
request = urllib.request.Request("http://127.0.0.1:8650/identities/" + sys.argv[1] + "/" + sys.argv[2],
    sys.argv[3].encode(),
    {"X-Internal-Auth": os.environ["SECRET_SERVICE_INTERNAL_AUTH"], "Content-Type": "application/json"})
print(urllib.request.urlopen(request, timeout=300).read().decode())' "${ORG_NAME}-worker$1" "$2" "$3" 2>&1
}

account_live() {  # $1 account -> success while a slot's current, non-retired identity is that account
    sudo -n sh -c 'cat "$1"/*/current.json' _ "$PROFILE_DATA_DIR/identities" 2>/dev/null \
        | jq -se --arg a "$1" 'any(.[]; .username == $a and (.retired != true))' >/dev/null
}

reuse_slot() {  # $1 slot index, $2 spawn request id: a new agent, new account, fresh containers
    local wi="$1" request="$2" wname="${ORG_NAME}-worker$1" out ids name
    REUSED_ACCOUNT=""
    local retire_nonce="${3:-}"
    ids=$(slot_containers "$wi")
    retire_old_agent "$wname" "$request" "$retire_nonce" $ids || return 2
    if [ -d "$PROFILE_DATA_DIR/agents/$wname" ]; then
        sudo -n mv "$PROFILE_DATA_DIR/agents/$wname" "$PROFILE_DATA_DIR/agents/$wname.retiring-$request" || return 2
    fi
    if [ -d "$PROFILE_DATA_DIR/acp/$wname" ]; then
        sudo -n mv "$PROFILE_DATA_DIR/acp/$wname" "$PROFILE_DATA_DIR/acp/$wname.retiring-$request" || return 2
    fi
    # Provision the account without its task DM; the DM follows once the fresh
    # router is up, so the router receives it live rather than from history.
    if ! out=$(secret_call "$wi" revive "{\"request_id\": \"$request\", \"wake\": false}"); then
        log "WARN: reusing worker$wi for $request failed: $(printf '%s' "$out" | tail -n 1)"
        return 1
    fi
    REUSED_ACCOUNT=$(printf '%s' "$out" | jq -r '.username // empty' 2>/dev/null)
    sudo -n install -d -o 10000 -g 10000 "$PROFILE_DATA_DIR/agents/$wname/home" \
        "$PROFILE_DATA_DIR/agents/$wname/home/group-messages"
    for name in "agent-worker$wi" "mini-router-worker$wi"; do
        until out=$(cd "$ROOT" && make run-slot PROFILE="$PROFILE" SERVICE="$name" \
                NAME="omcgitea-$PROFILE-$name-$request" 2>&1); do
            log "WARN: starting $name for $request failed; retrying in ${PBENCH_START_RETRY_S:-30}s"
            printf '%s\n' "$out" | tail -n 3 | while IFS= read -r l; do log "    $l"; done
            sleep "${PBENCH_START_RETRY_S:-30}"
        done
        # Compose one-off containers have no restart policy; the router relies on one.
        sudo docker update --restart unless-stopped "omcgitea-$PROFILE-$name-$request" >/dev/null
    done
    sleep "${PBENCH_BRINGUP_SETTLE_S:-20}"
    if ! out=$(secret_call "$wi" wake "{\"request_id\": \"$request\"}"); then
        log "WARN: task DM for worker$wi ($request) failed: $(printf '%s' "$out" | tail -n 1)"
        return 1
    fi
    log "reused retired slot worker$wi for $request with fresh containers: @$REUSED_ACCOUNT"
}

spawn_loop() {  # $1 budget seconds, $2 worker slots, $3 kickoff text
    # The claim checker records one spawn request per accepted CLAIM. Each starts
    # one new agent: in the next unused slot, or, once all slots are in use, in a
    # retired worker's slot with a fresh account and containers. Retired agents
    # are never restarted.
    # At most one newcomer at a time is looking for its first CLAIM: the next
    # launch waits until the previous newcomer has claimed (or left), so the team
    # grows only as fast as newcomers find distinct work. When every slot holds a
    # working agent, requests wait and resume as soon as a slot frees up. Like
    # replacement sessions, launches stop at T-15.
    local secs="$1" n_slots="$2" kickoff="$3" launched=1 next=1 slot request requested
    local container password stop_at waiting="" stopping=0 rotate=1 claimed
    local newcomer="${ORG_NAME}-worker1" newcomer_since timeout="${PBENCH_NEWCOMER_TIMEOUT_S:-900}"
    trap 'stopping=1' TERM
    newcomer_since=-1
    container=$(sudo docker ps --filter "name=omcgitea-$PROFILE-mysql" \
                --format '{{.Names}}' 2>/dev/null | head -1 || true)
    password=$(grep -E '^MYSQL_ROOT_PASSWORD=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)
    if [ -z "$container" ] || [ -z "$password" ]; then
        log "WARN: spawn loop cannot read spawn requests (container='${container:-none}'); the team stays at 1 worker"
        return 0
    fi
    sql() {
        sudo docker exec "$container" mysql -N -B -uroot -p"$password" -D omcgitea -e "$1" \
            2>/dev/null | tr -d '[:space:]' || true
    }
    local control mode active_now nonce
    while [ "$stopping" = 0 ]; do
        control=$(count14_spawn_ctl READ) || { sleep "${PBENCH_SPAWN_POLL_S:-15}"; continue; }
        read -r mode active_now nonce <<< "$control"
        [ "$mode" != FINAL ] || break
        [ "$mode" = RUNNING ] || { sleep "${PBENCH_SPAWN_POLL_S:-15}"; continue; }
        [ "$newcomer_since" -ge 0 ] || newcomer_since="$active_now"
        if [ -n "$newcomer" ]; then
            # The gate opens once the newcomer posts its first CLAIM, leaves, or times out.
            claimed=$(sql "SELECT COUNT(*) FROM board_gists WHERE type='CLAIM' AND account='$newcomer'")
            if [[ "$claimed" =~ ^[1-9] ]]; then
                newcomer=""
            elif [ $(( active_now - newcomer_since )) -ge "$timeout" ]; then
                log "newcomer @$newcomer made no CLAIM in ${timeout}s; opening the launch gate"
                newcomer=""
            elif ! account_live "$newcomer"; then
                newcomer=""
            else
                sleep "${PBENCH_SPAWN_POLL_S:-15}"
                continue
            fi
        fi
        # The table appears when the checker's router first boots; until then nothing is requested.
        requested=$(sql "SELECT COUNT(*) FROM spawn_requests")
        [[ "$requested" =~ ^[0-9]+$ ]] || requested=0
        if [ "$next" -le "$requested" ]; then
            request="spawn-$next"
            if [ "$launched" -lt "$n_slots" ]; then
                control=$(count14_spawn_ctl BEGIN "$((launched + 1))" "$next" 0) || return 2
                read -r mode active_now nonce <<< "$control"
                [ "$mode" != HOLD ] || { sleep "${PBENCH_SPAWN_POLL_S:-15}"; continue; }
                [ "$mode" = ALLOW ] || return 2
                launched=$((launched + 1))
                log "$request: launching worker$launched"
                launch_worker "$launched" "$kickoff" || return 2
                count14_finish_same_launch "$launched" "$next" "$nonce" || return 2
                newcomer="${ORG_NAME}-worker$launched"; newcomer_since="$active_now"
                next=$((next + 1))
            elif slot=$(retired_slot "$n_slots" "$rotate"); then
                log "$request: reusing retired slot worker$slot"
                control=$(count14_spawn_ctl BEGIN "$slot" "$next" 1) || return 2
                read -r mode active_now nonce <<< "$control"
                [ "$mode" != HOLD ] || { sleep "${PBENCH_SPAWN_POLL_S:-15}"; continue; }
                [ "$mode" = ALLOW ] || return 2
                if reuse_slot "$slot" "$request" "$nonce"; then
                    count14_finish_same_launch "$slot" "$next" "$nonce" || return 2
                    newcomer="$REUSED_ACCOUNT"; newcomer_since="$active_now"
                    rotate=$(( slot % n_slots + 1 ))
                    next=$((next + 1))
                fi
            else
                # Every slot holds a working agent: block until a retirement frees one.
                [ "$waiting" = "$request" ] || log "$request waits: all $n_slots slots are busy"
                waiting="$request"
            fi
        fi
        [ -n "$newcomer" ] || sleep "${PBENCH_SPAWN_POLL_S:-15}"
    done
    # Previous agents may still be sealing their archives.
    wait
    log "spawn loop stopped: $launched of $n_slots slots used, $((next - 1)) of $requested spawn requests served"
}

