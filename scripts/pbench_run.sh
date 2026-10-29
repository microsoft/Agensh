#!/usr/bin/env bash
# Run one task for a team: seed Gitea, start workers, enforce the budget and export.
# Graceful worker shutdown seals archives that must verify before profile teardown.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TASK="${TASK:?TASK=<instance_id> required (e.g. abishekvashok__cmatrix.5c082c6)}"
HOURS="${HOURS:-2}"
OUT_DIR="${OUT_DIR:-$ROOT/out/pbench}"
PROFILE="${PROFILE:?PROFILE=pbench-single-node-<task> required}"
case "$PROFILE" in
    pbench-single-node-?*) ;;
    *) echo "[pbench] FATAL: this release supports PROFILE=pbench-single-node-<task> only" >&2; exit 1 ;;
esac
ENV_FILE="$ROOT/.env.$PROFILE"

run_budget_seconds() {
    python3 -c "print(int(round(float('$HOURS')*3600)))"
}

run_budget_remaining() {
    local remain=$(( $1 - $2 )) floor
    floor=60
    [ "$remain" -lt "$floor" ] && remain="$floor"
    echo "$remain"
}
export PBENCH_RUN_START_MS="${PBENCH_RUN_START_MS:-$(python3 -c 'import time; print(int(time.time()*1000))')}"
DOCKER_ORG="${PROGRAMBENCH_DOCKER_ORG:-programbench}"
REPO="${PBENCH_REPO:-main}"
PB_REPO="${PROGRAMBENCH_REPO:-$HOME/programbench}"
export PBENCH_DOCKER="${PBENCH_DOCKER:-sudo docker}"

BIN_PATH="$OUT_DIR/$TASK/bin/executable"
export PBENCH_BIN="$BIN_PATH"

log() { echo "[pbench] $*" >&2; }
die() { echo "[pbench] FATAL: $*" >&2; exit 1; }

source "$ROOT/scripts/lib_pbench_images.sh"

PROMPTS_DIR="$ROOT/prompts"

render_prompt() {
    local file="$1" names="" kv
    shift
    [ -s "$file" ] || { echo "render_prompt: $file is missing" >&2; return 1; }
    # Restrict envsubst so shell examples and unrelated placeholders stay literal.
    for kv in "$@"; do names+="\${${kv%%=*}}"; done
    env "$@" envsubst "$names" < "$file"
}

# Scan private native journals with sudo before traversing their directories.
worker_last_activity() {
    sudo -n find "$1" -type f -name '*.jsonl' -printf '%T@\n' 2>/dev/null \
        | awk 'BEGIN { latest = 0 } $1 > latest { latest = $1 }
               END { if (latest > 0) printf "%.0f\n", int(latest) }'
}

worker_idle_phase() {
    local total_seconds="$1" remaining_seconds="$2" delivery_seconds=300
    [ "$total_seconds" -gt 2700 ] && delivery_seconds=2700
    if [ "$remaining_seconds" -le "$delivery_seconds" ]; then
        printf '%s\n' delivery
    else
        printf '%s\n' development
    fi
}
command -v envsubst >/dev/null 2>&1 || die "envsubst not found (apt install gettext-base); it renders the prompts under prompts/"

ORCH="$(grep -E '^PBENCH_ORCHESTRATOR=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d ' \r' || true)"
ORCH="${PBENCH_ORCHESTRATOR:-${ORCH:-compose}}"
[ "$ORCH" = "compose" ] || die "PBENCH_ORCHESTRATOR='$ORCH'; this release supports single-node Compose only"

WATCHDOG_PID=""
REMINDER_PID=""

stop_background_loops() {
    local pid
    for pid in "$WATCHDOG_PID" "$REMINDER_PID"; do
        [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
    done
    WATCHDOG_PID=""
    REMINDER_PID=""
}

[ -f "$ENV_FILE" ] || die "$ENV_FILE missing (task #1 should have created it)"

img_base="$DOCKER_ORG/$(printf '%s' "$TASK" | sed 's/__/_1776_/')"
CLEANROOM_TAG="$(pbench_cleanroom_tag "$ENV_FILE")" || die "reference image configuration mismatch"
CLEANROOM_IMG="$img_base:$CLEANROOM_TAG"

if [ -e "$OUT_DIR/$TASK" ]; then
    die "$OUT_DIR/$TASK already exists — leftover output from a prior run would be mixed in. Remove it (\`rm -rf $OUT_DIR/$TASK\`) before re-running."
fi
mkdir -p "$OUT_DIR/$TASK"

DATA_ROOT="$(grep -E '^DATA_ROOT=' "$ENV_FILE" | cut -d= -f2-)"
DATA_ROOT="${DATA_ROOT:-../.claude-team-data}"
ORG_NAME="$(grep -E '^ORG_NAME=' "$ENV_FILE" | cut -d= -f2-)"

PROFILE_DATA_DIR="$DATA_ROOT/$PROFILE"
if [ -e "$PROFILE_DATA_DIR" ]; then
    die "$PROFILE_DATA_DIR already exists — leftover state from a prior run would leak into this one (acp_session_id, gitea repo, mattermost history). Run \`make clean PROFILE=$PROFILE\` first."
fi

EDGE_PORT="$(grep -E '^EDGE_HTTP_PORT=' "$ENV_FILE" | cut -d= -f2-)"
GITEA_ADMIN_USER="$(grep -E '^GITEA_ADMIN_USER=' "$ENV_FILE" | cut -d= -f2-)"
GITEA_ADMIN_PASSWORD="$(grep -E '^GITEA_ADMIN_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"

EDGE_MM_PORT="$(grep -E '^EDGE_MM_PORT=' "$ENV_FILE" | cut -d= -f2-)"
MATTERMOST_ADMIN_USER="$(grep -E '^MATTERMOST_ADMIN_USER=' "$ENV_FILE" | cut -d= -f2-)"
MATTERMOST_ADMIN_PASSWORD="$(grep -E '^MATTERMOST_ADMIN_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
MATTERMOST_TEAM_NAME="$(grep -E '^MATTERMOST_TEAM_NAME=' "$ENV_FILE" | cut -d= -f2- || true)"
MATTERMOST_TEAM_NAME="${MATTERMOST_TEAM_NAME:-$ORG_NAME}"
MM_BASE="http://localhost:${EDGE_MM_PORT}"

export_submission() {
    # Export committed repository HEAD; retain a failure marker for manual recovery.
    mkdir -p "$OUT_DIR/$TASK"

    local team_url="http://${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}@localhost:${EDGE_PORT}/${ORG_NAME}/${REPO}.git"
    log "exporting submission from Gitea repo ${ORG_NAME}/${REPO} → $OUT_DIR/$TASK/"
    local attempt
    for attempt in 1 2 3; do
        if python3 tools/pbench_submission.py export \
            --from-gitea "$team_url" --task "$TASK" --out-dir "$OUT_DIR" \
            2>>"$OUT_DIR/$TASK/export.log"; then
            log "submission.tar.gz written (attempt $attempt)"
            rm -f "$OUT_DIR/$TASK/EXPORT_FAILED"
            return 0
        fi
        log "WARN: gitea export attempt $attempt/3 failed (see export.log)"
        [ "$attempt" -lt 3 ] && sleep $(( attempt * 15 ))
    done

    log "ERROR: gitea export FAILED after 3 attempts — this task has NO submission."
    log "ERROR: the repo is still intact under \$DATA_ROOT; recover with:"
    log "ERROR:   python3 tools/pbench_submission.py export --from-gitea file://<data-root>/gitea/git/repositories/${ORG_NAME}/${REPO}.git --task $TASK --out-dir <dir>"
    {
        echo "export failed after 3 attempts at $(date -u +%FT%TZ)"
        echo "task=$TASK profile=$PROFILE url=localhost:${EDGE_PORT}/${ORG_NAME}/${REPO}.git"
        echo "the gitea repo under DATA_ROOT is intact; this is an export failure, not a zero"
    } > "$OUT_DIR/$TASK/EXPORT_FAILED"
    tar -czf "$OUT_DIR/$TASK/submission.tar.gz" -C "$OUT_DIR/$TASK" --files-from /dev/null 2>/dev/null || \
        : > "$OUT_DIR/$TASK/submission.tar.gz"
    return 1
}

dump_board_lifecycle() {
    local bs
    bs=$(sudo docker ps --filter "name=omcgitea-$PROFILE-board-service" \
         --format '{{.Names}}' 2>/dev/null | head -1)
    [ -z "$bs" ] && return 0
    log "dumping board lifecycle from $bs"
    sudo docker exec "$bs" python3 -c "
import json, urllib.request
try:
    boards = json.load(urllib.request.urlopen('http://127.0.0.1:8660/healthz', timeout=5))['boards']
except Exception as e:
    print('healthz failed:', e); raise SystemExit(0)
for b in boards:
    try:
        req = urllib.request.Request(
            f'http://127.0.0.1:8660/board/{b}/lifecycle?viewer=harness', method='POST')
        print(b, json.load(urllib.request.urlopen(req, timeout=15)).get('path'))
    except Exception as e:
        print(b, 'FAILED', e)
" >>"$OUT_DIR/$TASK/board-lifecycle.log" 2>&1 || true
}

quiesce_agents() {
    # Stop routers/CI first, then let workers archive while Gitea/MySQL stay up.
    local proj="omcgitea-$PROFILE"
    local ids agents
    ids=$(sudo docker ps -q \
            --filter "label=com.docker.compose.project=$proj" \
            --filter "name=mini-router" \
            --filter "name=act-runner" 2>/dev/null | sort -u)
    if [ -n "$ids" ]; then
        log "quiesce: stopping routers/runners for $proj before worker snapshots"
        sudo docker stop -t 10 $ids >/dev/null 2>&1 \
            || log "WARN: some routers/runners did not stop cleanly for $proj"
    fi
    agents=$(sudo docker ps -q \
            --filter "label=com.docker.compose.project=$proj" \
            --filter "name=agent-worker" 2>/dev/null | sort -u)
    if [ -n "$agents" ]; then
        log "quiesce: saving worker sessions for $proj (up to 600s; gitea/mysql stay up)"
        sudo docker stop -t 600 $agents >/dev/null 2>&1 \
            || log "WARN: some workers did not stop cleanly for $proj"
    fi
    sudo -n python3 "$ROOT/agent/archive.py" check "$PROFILE_DATA_DIR"
}

save_service_logs() {
    # Preserve router/proxy stdout before Compose removes the container records.
    local directory="$OUT_DIR/$TASK/service-logs" container service
    mkdir -p "$directory"
    while read -r container service; do
        [ -n "$container" ] && [ -n "$service" ] || continue
        sudo docker logs --timestamps "$container" >"$directory/$service.log" 2>&1 \
            || log "WARN: could not save $service logs for $PROFILE"
    done < <(sudo docker ps -a --filter "label=com.docker.compose.project=omcgitea-$PROFILE" \
        --format '{{.ID}} {{.Label "com.docker.compose.service"}}')
    date -u +%FT%TZ >"$directory/captured-at.txt"
    log "saved service stdout/stderr to $directory"
}

teardown() {
    # The exit trap also preserves recoverable state when the main path fails early.
    local rc=$? archives_ok=1
    log "teardown (rc=$rc): quiescing agents, exporting submission, stopping profile"
    stop_background_loops
    dump_board_lifecycle || true
    quiesce_agents || archives_ok=0
    export_submission || true
    save_service_logs || true
    if [ "$archives_ok" = 1 ]; then
        make down PROFILE="$PROFILE" >/dev/null 2>&1 || true
    else
        log "ERROR: incomplete shutdown archives; preserving containers and DATA_ROOT for recovery"
        return 1
    fi
    return 0
}

seed_repo() {
    log "seeding cleanroom workspace from $CLEANROOM_IMG"
    if ! sudo docker image inspect "$CLEANROOM_IMG" >/dev/null 2>&1; then
        log "pulling $CLEANROOM_IMG (first run; agents get NO internet so this MUST happen host-side now)"
        sudo docker pull "$CLEANROOM_IMG" >/dev/null 2>&1 \
            || die "cannot pull $CLEANROOM_IMG (check task id / dockerhub access)"
    fi
    local cleanroom_id
    # Resolve the tag once so extracted assets and recorded provenance agree.
    cleanroom_id="$(sudo docker image inspect --format '{{.Id}}' "$CLEANROOM_IMG")" \
        || die "cannot identify reference image"
    local seed_dir="$OUT_DIR/$TASK/_seed"
    rm -rf "$seed_dir"; mkdir -p "$seed_dir"
    PROGRAMBENCH_DOCKER_ORG="$DOCKER_ORG" \
        python3 tools/pbench_submission.py seed --image "$cleanroom_id" \
        --into "$seed_dir" --bin-out "$BIN_PATH" \
        || die "seed extraction failed"
    if [ -f "$BIN_PATH" ]; then
        # Workers may execute the reference as UID 10000, but may not read its bytes.
        sudo chown 0:0 "$BIN_PATH"
        sudo chmod 0111 "$BIN_PATH"
        sudo -n python3 - "$BIN_PATH" "$OUT_DIR/$TASK/reference.json" "$CLEANROOM_IMG" "$cleanroom_id" <<'PY'
import hashlib, json, pathlib, sys
binary, metadata, image, image_id = sys.argv[1:]
with open(binary, 'rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
pathlib.Path(metadata).write_text(json.dumps(dict(image=image, image_id=image_id,
    executable_sha256=digest, executable_bytes=pathlib.Path(binary).stat().st_size), indent=2) + '\n')
PY
        log "reference binary staged 0111 at $BIN_PATH (mounted /opt/pbench/executable)"
    else
        log "WARN: no reference binary extracted; agents will get /dev/null mount"
    fi
    log "seed workspace ready at $seed_dir (push into Gitea is handled by bootstrap/initial-commit)"
    echo "$seed_dir" > "$OUT_DIR/$TASK/.seed_path"
}

MM_ADMIN_TOKEN=""
mm_login() {
    [ -n "$MM_ADMIN_TOKEN" ] && return 0
    [ -n "$EDGE_MM_PORT" ] || { log "WARN: EDGE_MM_PORT unset; MM drive disabled"; return 1; }
    MM_ADMIN_TOKEN=$(curl -sS -i \
        -d "{\"login_id\":\"${MATTERMOST_ADMIN_USER}\",\"password\":\"${MATTERMOST_ADMIN_PASSWORD}\"}" \
        "${MM_BASE}/api/v4/users/login" \
        | awk -F': ' '/^[Tt]oken:/ {gsub(/\r/,""); print $2; exit}')
    [ -n "$MM_ADMIN_TOKEN" ] || { log "WARN: mattermost admin login failed; MM drive disabled"; return 1; }
    return 0
}
mm_user_id() {
    mm_login || return 1
    curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" \
        "${MM_BASE}/api/v4/users/username/$1" \
        | jq -r 'select(.status_code == null) | .id // empty'
}
mm_post() {
    mm_login || return 1
    curl -fsS -H "Authorization: Bearer $MM_ADMIN_TOKEN" -H 'Content-Type: application/json' \
        -X POST -d "$(jq -nc --arg c "$1" --arg m "$2" '{channel_id:$c, message:$m}')" \
        "${MM_BASE}/api/v4/posts" >/dev/null 2>&1
}

mm_dm_channel() {
    local user="$1"
    mm_login || return 1
    local me_id user_id
    me_id="$(mm_user_id "$MATTERMOST_ADMIN_USER")" || return 1
    user_id="$(mm_user_id "$user")" || return 1
    [ -n "$me_id" ] && [ -n "$user_id" ] || return 1
    local ch
    ch=$(curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" -H 'Content-Type: application/json' \
        -X POST -d "[\"$me_id\",\"$user_id\"]" \
        "${MM_BASE}/api/v4/channels/direct" | jq -r '.id // empty')
    [ -n "$ch" ] || return 1
    printf '%s' "$ch"
}

TASK_CHANNEL_ID=""
MM_TEAM_ID=""
mm_ensure_task_channel() {
    mm_login || return 1
    local team_id
    team_id=$(curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" \
        "${MM_BASE}/api/v4/teams/name/${MATTERMOST_TEAM_NAME}" | jq -r 'select(.status_code == null) | .id // empty')
    if [ -z "$team_id" ]; then
        log "MM team ${MATTERMOST_TEAM_NAME} missing; creating it"
        team_id=$(curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" -H 'Content-Type: application/json' \
            -X POST -d "$(jq -nc --arg n "$MATTERMOST_TEAM_NAME" \
                '{name:$n, display_name:$n, type:"O"}')" \
            "${MM_BASE}/api/v4/teams" | jq -r '.id // empty')
        [ -n "$team_id" ] || { log "WARN: could not create MM team"; return 1; }
    fi
    local admin_id; admin_id=$(mm_user_id "$MATTERMOST_ADMIN_USER") || true
    local n_workers
    n_workers="$(grep -E '^PBENCH_WORKERS_PER_TEAM=' "$ENV_FILE" 2>/dev/null | cut -d= -f2)"
    n_workers="${n_workers:-4}"
    local extra_team_members=()
    local wi
    for wi in $(seq 1 "$n_workers"); do
        extra_team_members+=("${ORG_NAME}-worker${wi}")
    done
    local m agent
    for m in "$admin_id"; do
        [ -n "$m" ] && curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" -H 'Content-Type: application/json' \
            -X POST -d "$(jq -nc --arg t "$team_id" --arg u "$m" '{team_id:$t, user_id:$u}')" \
            "${MM_BASE}/api/v4/teams/${team_id}/members" >/dev/null 2>&1 || true
    done
    for agent in "${extra_team_members[@]}"; do
        m=$(mm_user_id "$agent") || true
        [ -n "$m" ] && curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" -H 'Content-Type: application/json' \
            -X POST -d "$(jq -nc --arg t "$team_id" --arg u "$m" '{team_id:$t, user_id:$u}')" \
            "${MM_BASE}/api/v4/teams/${team_id}/members" >/dev/null 2>&1 || true
    done
    local chan_name="pbench-task"
    local ch
    ch=$(curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" \
        "${MM_BASE}/api/v4/teams/${team_id}/channels/name/${chan_name}" \
        | jq -r 'select(.status_code == null) | .id // empty')
    if [ -z "$ch" ]; then
        ch=$(curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" -H 'Content-Type: application/json' \
            -X POST -d "$(jq -nc --arg t "$team_id" --arg n "$chan_name" \
                '{team_id:$t, name:$n, display_name:"pbench task", type:"P"}')" \
            "${MM_BASE}/api/v4/channels" | jq -r '.id // empty')
        [ -n "$ch" ] || { log "WARN: could not create MM task channel"; return 1; }
    fi
    local uid code
    for agent in "${extra_team_members[@]}"; do
        uid=$(mm_user_id "$agent") || true
        [ -n "$uid" ] || { log "WARN: no MM user id for $agent"; continue; }
        code=$(curl -sS -o /dev/null -w '%{http_code}' \
            -H "Authorization: Bearer $MM_ADMIN_TOKEN" -H 'Content-Type: application/json' \
            -X POST -d "$(jq -nc --arg u "$uid" '{user_id:$u}')" \
            "${MM_BASE}/api/v4/channels/${ch}/members" 2>/dev/null || echo 000)
        case "$code" in
            2*) ;;
            *) log "WARN: MM channel join failed for $agent (http=$code)" ;;
        esac
    done
    TASK_CHANNEL_ID="$ch"
    MM_TEAM_ID="$team_id"
    printf '%s %s' "$team_id" "$ch"
}

task_brief() {
    render_prompt "$PROMPTS_DIR/task_brief.txt" \
        TASK="$TASK" REPO="$REPO" MM_TEAM_ID="$MM_TEAM_ID" TASK_CHANNEL_ID="$TASK_CHANNEL_ID"
}

deadline_reminder_loop() {
    # Reminders are channel messages timed against the remaining run budget.
    local secs="$1"
    local t45=$(( secs - 45 * 60 ))
    local t5=$((  secs - 5  * 60 ))
    if [ "$t45" -gt 0 ]; then
        sleep "$t45"
        mm_post "$TASK_CHANNEL_ID" "$(render_prompt "$PROMPTS_DIR/deadline_45m.txt")" \
            || log "WARN: T-45m reminder failed"
        log "posted T-45m reminder"
    fi
    local rest=$(( t5 - (t45 > 0 ? t45 : 0) ))
    if [ "$rest" -gt 0 ]; then
        sleep "$rest"
        mm_post "$TASK_CHANNEL_ID" "$(render_prompt "$PROMPTS_DIR/deadline_5m.txt")" \
            || log "WARN: T-5m reminder failed"
        log "posted T-5m reminder"
    fi
}

wake_stagger_for() {
    # Switch by worker index, not elapsed time; startup/settle can exceed either target.
    local _i="$1"
    local _base="${PBENCH_WAKE_STAGGER_S:-30}"
    local _switch=$(( ${PBENCH_WAKE_RAMP_SUBJ_S:-3600} / _base ))
    if [ "$_i" -le "$_switch" ]; then
        echo "$_base"
    else
        echo "${PBENCH_WAKE_FAST_STAGGER_S:-3}"
    fi
}

start_agent_containers() {
    local wi="$1" wname="$2" out try=1
    until out="$(cd "$ROOT" && make up PROFILE="$PROFILE" UP_FLAGS=--no-deps \
            SERVICES="agent-worker${wi} mini-router-worker${wi}" 2>&1)"; do
        log "WARN: container start failed for $wname (try $try); retrying in ${PBENCH_START_RETRY_S:-30}s"
        printf '%s\n' "$out" | tail -n 5 | while IFS= read -r l; do log "    $l"; done
        try=$((try + 1))
        sleep "${PBENCH_START_RETRY_S:-30}"
    done
    log "started containers for $wname"
}

push_seed_and_drive() {
    local seed_dir; seed_dir="$(cat "$OUT_DIR/$TASK/.seed_path")"
    local repo_url="http://${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}@localhost:${EDGE_PORT}/${ORG_NAME}/${REPO}.git"
    local push_tmp="$OUT_DIR/$TASK/_push"
    rm -rf "$push_tmp"
    log "cloning team repo to seed initial commit"
    local _seeded=0 _try
    for _try in 1 2 3 4 5; do
        rm -rf "$push_tmp"
        if git clone --quiet "$repo_url" "$push_tmp" 2>/dev/null; then _seeded=1; break; fi
        log "WARN: clone attempt $_try/5 failed; retrying in $((_try * 5))s"
        sleep $((_try * 5))
    done
    if [ "$_seeded" != 1 ]; then
        log "WARN: clone failed after 5 attempts; skipping seed push (agents are still woken below)"
    fi
    if [ "$_seeded" = 1 ]; then
    cp -a "$seed_dir/." "$push_tmp/" 2>/dev/null || true
    ( cd "$push_tmp" \
        && git config user.email "chairman@${ORG_NAME}.local" \
        && git config user.name "$GITEA_ADMIN_USER" \
        && git add -A \
        && git commit -qm "pbench: seed cleanroom workspace ($TASK)" \
        && git push -q origin HEAD ) \
        || log "WARN: seed push failed (repo may already be seeded)"
    fi

    local _mm ch
    _mm="$(mm_ensure_task_channel)" || _mm=""
    MM_TEAM_ID="${_mm%% *}"
    ch="${_mm##* }"
    [ "$_mm" = "" ] && { MM_TEAM_ID=""; ch=""; }
    TASK_CHANNEL_ID="$ch"

    local brief; brief="$(task_brief)"
    local kickoff; kickoff="$(render_prompt "$PROMPTS_DIR/kickoff.txt" TASK_BRIEF="$brief")"

    log "opening task issue (no assignee; peers self-select)"
    curl -fsS -u "${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}" \
        -H 'Content-Type: application/json' \
        -d "$(python3 -c 'import json,sys; print(json.dumps({"title": f"[pbench] {sys.argv[1]}", "body": sys.argv[2]}))' "$TASK" "$brief")" \
        "http://localhost:${EDGE_PORT}/api/v1/repos/${ORG_NAME}/${REPO}/issues" \
        >/dev/null 2>&1 \
        && log "task issue opened" \
        || log "WARN: could not open task issue"

    local stagger_s="${PBENCH_WAKE_STAGGER_S:-30}"
    local fast_stagger_s="${PBENCH_WAKE_FAST_STAGGER_S:-3}"
    local switch_at; switch_at=$(( ${PBENCH_WAKE_RAMP_SUBJ_S:-3600} / ${PBENCH_WAKE_STAGGER_S:-30} ))
    local n_workers_wake wi wname dmch woke=0
    n_workers_wake="$(grep -E '^PBENCH_WORKERS_PER_TEAM=' "$ENV_FILE" 2>/dev/null | cut -d= -f2)"
    n_workers_wake="${n_workers_wake:-4}"
    if [ "$n_workers_wake" -gt "$switch_at" ]; then
        log "waking $n_workers_wake agents by DM: ${stagger_s}s apart for the first $switch_at (one hour), then ${fast_stagger_s}s"
    else
        log "waking $n_workers_wake agents by DM, ${stagger_s}s apart"
    fi
    # Charge activation time to the shared wall-clock budget, starting before ramp-up.
    PBENCH_RUN_T0=$(date +%s)
    export PBENCH_RUN_T0

    if [ "${PBENCH_WATCHDOG_EARLY:-1}" = "1" ]; then
        local _wd_secs
        _wd_secs="$(python3 -c "print(int(round(float('${HOURS:-6}')*3600)))" 2>/dev/null || echo 21600)"
        worker_watchdog_loop "$_wd_secs" &
        WATCHDOG_PID=$!
        log "idle watchdog started BEFORE the ramp (pid $WATCHDOG_PID, ${_wd_secs}s)"
    fi

    for wi in $(seq 1 "$n_workers_wake"); do
        wname="${ORG_NAME}-worker${wi}"
        _wake_started=$(date +%s)
        if [ "${PBENCH_STAGGERED_BRINGUP:-1}" = "1" ]; then
            start_agent_containers "$wi" "$wname"
            sleep "${PBENCH_BRINGUP_SETTLE_S:-20}"
        fi
        dmch="$(mm_dm_channel "$wname" 2>/dev/null)" || dmch=""
        if [ -z "$dmch" ]; then
            dmch="$(mm_dm_channel "$wname" 2>/dev/null)" || dmch=""
        fi
        if [ -n "$dmch" ]; then
            mm_post "$dmch" "$kickoff" >/dev/null 2>&1 \
                && { woke=$((woke+1)); log "woke $wname ($woke/$n_workers_wake)"; } \
                || log "WARN: DM wake failed for $wname"
        else
            log "WARN: no DM channel for $wname"
        fi
        if [ "$wi" -lt "$n_workers_wake" ]; then
            _spent=$(( $(date +%s) - ${_wake_started:-$(date +%s)} ))
            _remain=$(( $(wake_stagger_for "$wi") - _spent ))
            [ "$_remain" -gt 0 ] && sleep "$_remain"
        fi
    done
    log "wake complete: $woke/$n_workers_wake agents"

    if [ -n "$ch" ]; then
        mm_post "$ch" "$kickoff" \
            && log "task posted to MM channel pbench-task (record; agents already woken)" \
            || log "WARN: MM channel post failed"
    else
        log "WARN: no MM channel for the task record (agents were woken by DM)"
    fi
}

WORKER_IDLE_THRESHOLD="${WORKER_IDLE_THRESHOLD:-600}"
WORKER_IDLE_REPEAT="${WORKER_IDLE_REPEAT:-600}"
WORKER_CHECK_INTERVAL="${WORKER_CHECK_INTERVAL:-60}"

watchdog_uem_pending() {
    local w="$1"
    local sql="SELECT COUNT(*) FROM events WHERE agent='${w}' AND state IN ('pending','sending','retrying','failed');"
    if [ -n "${MYSQL_CONTAINER:-}" ] && [ -n "${MYSQL_ROOT_PW:-}" ]; then
        sudo docker exec "$MYSQL_CONTAINER" \
            mysql -N -B -uroot -p"$MYSQL_ROOT_PW" -D omcgitea -e "$sql" \
            2>/dev/null | tr -d '[:space:]' || true
    fi
}

watchdog_consider() {
    # Nudge idle workers only after checking queue activity and the last nudge time.
    local worker_name="$1" idle="$2" now="$3" dedup_dir="$4"
    [ "$idle" -ge 0 ] 2>/dev/null || return 0
    [ "$idle" -ge "$WORKER_IDLE_THRESHOLD" ] || return 0
    local last_ping
    last_ping=$(cat "$dedup_dir/$worker_name" 2>/dev/null || echo 0)
    [ $((now - last_ping)) -ge "$WORKER_IDLE_REPEAT" ] || return 0

    local pending_evts
    pending_evts="$(watchdog_uem_pending "$worker_name")"
    if [ -n "$pending_evts" ] && [ "$pending_evts" != "0" ]; then
        log "watchdog: ${worker_name} idle=${idle}s but ${pending_evts} UEM row(s) pending; letting the queue wake it"
        echo "$now" > "$dedup_dir/$worker_name"
        return 0
    fi

    local idle_msg
    if [ "${WORKER_IDLE_PHASE:-development}" = delivery ]; then
        idle_msg="$(render_prompt "$PROMPTS_DIR/idle_delivery.txt")"
    else
        idle_msg="$(render_prompt "$PROMPTS_DIR/idle.txt")"
    fi
    local pinged=0 dm=""
    dm="$(mm_dm_channel "$worker_name" 2>/dev/null)" || dm=""
    if [ -n "$dm" ]; then
        mm_post "$dm" "$idle_msg" \
            && { log "watchdog: DM ${worker_name} (idle=${idle}s, UEM queue empty)"; pinged=1; } \
            || log "WARN: watchdog DM to ${worker_name} failed"
    fi
    if [ "$pinged" = "0" ] && [ -n "$TASK_CHANNEL_ID" ]; then
        mm_post "$TASK_CHANNEL_ID" "@${worker_name} ${idle_msg}" \
            && log "watchdog: channel-fallback ping for ${worker_name} (idle ${idle}s)" \
            || log "WARN: watchdog channel fallback failed for ${worker_name}"
    fi
    echo "$now" > "$dedup_dir/$worker_name"
}

worker_watchdog_loop() {
    local total_secs="$1"
    local agents_root="${DATA_ROOT}/${PROFILE}/agents"
    local dedup_dir="${OUT_DIR}/${TASK}/_watchdog"
    local session_subdir
    case "$(awk -F= '$1=="AGENT_HARNESS"{print $2;exit}' "$ENV_FILE")" in
        copilot) session_subdir=home/.copilot/session-state ;;
        codex) session_subdir=home/.codex/sessions ;;
        claude) session_subdir=home/.claude/projects ;;
        *) session_subdir=home/.pi/agent/sessions ;;
    esac
    mkdir -p "$dedup_dir"
    local start now elapsed
    start=$(date +%s)
    if ! sudo -n true 2>/dev/null; then
        log "WARN: watchdog cannot sudo -n; private native journals cannot be scanned, so idle nudges will be skipped"
    fi
    local MYSQL_CONTAINER MYSQL_ROOT_PW
    MYSQL_CONTAINER=$(sudo docker ps --filter "name=omcgitea-$PROFILE-mysql" \
                      --format '{{.Names}}' 2>/dev/null | head -1 || true)
    MYSQL_ROOT_PW=$(grep -E '^MYSQL_ROOT_PASSWORD=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)
    if [ -z "$MYSQL_CONTAINER" ] || [ -z "$MYSQL_ROOT_PW" ]; then
        log "WARN: watchdog cannot read the UEM queue (container='${MYSQL_CONTAINER:-none}'); it will nudge on idle alone"
    fi
    while :; do
        now=$(date +%s)
        elapsed=$((now - start))
        [ "$elapsed" -ge "$total_secs" ] && break
        local WORKER_IDLE_PHASE
        WORKER_IDLE_PHASE="$(worker_idle_phase "$total_secs" "$((total_secs - elapsed))")"
        if [ ! -d "$agents_root" ]; then sleep "$WORKER_CHECK_INTERVAL"; continue; fi
        local agent_dir worker_name last_mtime idle
        for agent_dir in "$agents_root"/${ORG_NAME}-*worker*; do
            [ -d "$agent_dir" ] || continue
            worker_name="$(basename "$agent_dir")"
            local session_dir="$agent_dir/$session_subdir"
            # Native session-log modification times are the liveness signal.
            last_mtime=$(worker_last_activity "$session_dir" || true)
            [ -n "$last_mtime" ] || continue
            idle=$((now - last_mtime))
            watchdog_consider "$worker_name" "$idle" "$now" "$dedup_dir"
        done
        sleep "$WORKER_CHECK_INTERVAL"
    done
}

agent_image() {
    local img="${AGENT_IMAGE:-}"
    [ -n "$img" ] || img="$(grep -E '^AGENT_IMAGE=' "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d ' \r')"
    [ -n "$img" ] && printf '%s\n' "$img"
}

clear_stale_containers() {
    local stale
    stale="$(sudo docker ps -aq --filter "label=com.docker.compose.project=omcgitea-$PROFILE" 2>/dev/null || true)"
    [ -n "$stale" ] || return 0
    log "clearing $(echo "$stale" | wc -l) stale container record(s) for $PROFILE"
    echo "$stale" | xargs -r sudo docker rm -f >/dev/null 2>&1 || true
}

main() {
    log "TASK=$TASK HOURS=$HOURS OUT_DIR=$OUT_DIR PROFILE=$PROFILE"
    trap teardown EXIT

    seed_repo
    local agent_img
    agent_img="$(agent_image)" || die "AGENT_IMAGE is not set in .env.$PROFILE"
    log "agent image: $agent_img"
    sudo docker image inspect "$agent_img" >/dev/null 2>&1 \
        || die "agent image missing: $agent_img (build it with scripts/pbench_build_pertask_images.sh)"
    log "bringing up $PROFILE stack"
    make -s render-pbench-base PROFILE="$PROFILE" >/dev/null 2>&1 \
        || die "render-pbench-base failed for $PROFILE"
    local _want_w _got_w _base="$ROOT/docker/_gen_prod.$PROFILE.yml"
    _want_w="$(grep -E '^PBENCH_WORKERS_PER_TEAM=' "$ROOT/.env.$PROFILE" 2>/dev/null | cut -d= -f2 | tr -d ' ')"
    if [ -n "$_want_w" ]; then
        [ -f "$_base" ] || die "compose base not rendered: $_base"
        _got_w="$(grep -cE '^  agent-worker[0-9]+:' "$_base" || true)"
        [ "$_got_w" = "$_want_w" ] \
            || die "compose base $_base has $_got_w workers, .env asks for $_want_w"
        log "compose base rendered: $_want_w workers/team"
    fi
    local up_lock="/tmp/pbench-make-up.lock"
    # Serialize infrastructure bring-up across experiments sharing this host.
    exec 9>"$up_lock"
    flock -w 900 9 || die "could not acquire $up_lock in 15min"
    log "acquired make-up lock (pid $$)"
    if [ "${PBENCH_STAGGERED_BRINGUP:-1}" = "1" ]; then
        local infra
        infra="$(cd "$ROOT" && make -s compose-services PROFILE="$PROFILE" 2>/dev/null \
                 | grep -vE '^(agent|mini-router)-worker[0-9]+$' | tr '\n' ' ')"
        [ -n "$infra" ] || die "could not enumerate infra services for $PROFILE"
        clear_stale_containers
        log "bringing up INFRA only ($(echo $infra | wc -w) services); agents start on the stagger"
        make up PROFILE="$PROFILE" SERVICES="$infra" || die "make up (infra) failed"
    else
        make up PROFILE="$PROFILE" || die "make up failed"
    fi
    exec 9>&-

    push_seed_and_drive

    local secs
    secs="$(run_budget_seconds)"
    if [ -n "${PBENCH_RUN_T0:-}" ]; then
        _elapsed=$(( $(date +%s) - PBENCH_RUN_T0 ))
        [ "$_elapsed" -lt 0 ] && _elapsed=0
        _remain="$(run_budget_remaining "$secs" "$_elapsed")"
        log "agents working for ${HOURS}h (${secs}s); ${_elapsed}s spent waking, sleeping ${_remain}s"
        secs="$_remain"
    else
        log "agents working for ${HOURS}h (${secs}s); waiting…"
    fi
    if [ -n "$WATCHDOG_PID" ]; then
        log "reusing pre-ramp idle watchdog (pid $WATCHDOG_PID)"
    else
        worker_watchdog_loop "$secs" &
        WATCHDOG_PID=$!
    fi
    deadline_reminder_loop "$secs" &
    REMINDER_PID=$!
    sleep "$secs"
    stop_background_loops
    log "wall-clock budget elapsed; exporting + evaluating"

    trap - EXIT
    export_submission || true
    quiesce_agents || {
        save_service_logs || true
        die "incomplete shutdown archives; preserving containers and DATA_ROOT for recovery"
    }
    save_service_logs
    make down PROFILE="$PROFILE" >/dev/null 2>&1 || true

    if [ "${SKIP_EVAL:-0}" = "1" ]; then
        log "SKIP_EVAL=1 → deferring programbench eval (submission left at $OUT_DIR/$TASK/submission.tar.gz)"
        return 0
    fi
    log "running programbench eval on $OUT_DIR"
    # The Docker shim applies evaluator limits without changing ProgramBench itself.
    export PROGRAMBENCH_DOCKER_EXECUTABLE="${PROGRAMBENCH_DOCKER_EXECUTABLE:-$ROOT/scripts/pbench_docker_sudo.sh}"
    local pbench_tmp="$OUT_DIR/$TASK/_evaltmp"
    rm -rf "$pbench_tmp"; mkdir -p "$pbench_tmp"
    export TMPDIR="$pbench_tmp"
      local in_slice=()
      if command -v systemd-run >/dev/null 2>&1 && systemctl cat pbench.slice >/dev/null 2>&1; then
          in_slice=(sudo -n systemd-run --scope --quiet --slice=pbench.slice --collect --uid="$(id -u)" --gid="$(id -g)")
          log "eval runs inside pbench.slice (aggregate ceiling)"
      else
          log "WARN: pbench.slice not installed -- eval runs UNCAPPED (see docker/pbench.slice)"
      fi
    local uv_bin programbench_bin
    uv_bin="$(command -v uv 2>/dev/null || true)"
    programbench_bin="$(command -v programbench 2>/dev/null || true)"
    if [ -n "$uv_bin" ]; then
        ( cd "$PB_REPO" && "${in_slice[@]}" env PROGRAMBENCH_DOCKER_EXECUTABLE="$PROGRAMBENCH_DOCKER_EXECUTABLE" \
            TMPDIR="$pbench_tmp" \
            "$uv_bin" run programbench eval "$OUT_DIR" --filter "$TASK" --image-tag task_cleanroom_v6 ) \
            || log "WARN: programbench eval returned non-zero"
    elif [ -n "$programbench_bin" ]; then
        "${in_slice[@]}" env PROGRAMBENCH_DOCKER_EXECUTABLE="$PROGRAMBENCH_DOCKER_EXECUTABLE" \
            TMPDIR="$pbench_tmp" "$programbench_bin" eval "$OUT_DIR" --filter "$TASK" --image-tag task_cleanroom_v6 \
            || log "WARN: eval non-zero"
    else
        die "neither 'uv' nor 'programbench' on PATH — cannot evaluate (task #4 eval side must be installed)"
    fi

    local eval_json="$OUT_DIR/$TASK/$TASK.eval.json"
    [ -f "$eval_json" ] && log "eval.json written: $eval_json" \
        || log "WARN: eval.json not found at $eval_json"
}

main "$@"
