#!/usr/bin/env bash
# ProgramBench runner: one task on one profile. Seeds the task repo into Gitea,
# brings the Docker Compose stack up, wakes the workers on a stagger, runs for HOURS,
# exports the submission and tears the stack down.
#
# Called by scripts/pbench_chain.sh through scripts/launch_single_node.sh.
#
#   TASK=<instance_id> HOURS=<wall_clock> PROFILE=pbench-single-node-<task> \
#     scripts/pbench_run.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TASK="${TASK:?TASK=<instance_id> required (e.g. abishekvashok__cmatrix.5c082c6)}"
HOURS="${HOURS:-2}"
OUT_DIR="${OUT_DIR:-$ROOT/out/pbench}"
# Each profile has its own compose project (omcgitea-$PROFILE), data dir
# (DATA_ROOT/$PROFILE) and host ports.
PROFILE="${PROFILE:?PROFILE=pbench-single-node-<task> required}"
case "$PROFILE" in
    pbench-single-node-?*) ;;
    *) echo "[pbench] FATAL: this release supports PROFILE=pbench-single-node-<task> only" >&2; exit 1 ;;
esac
ENV_FILE="$ROOT/.env.$PROFILE"

# One source of truth for the wall-clock budget, including the wake ramp.
run_budget_seconds() {
    python3 -c "print(int(round(float('$HOURS')*3600)))"
}

run_budget_remaining() {  # $1 total real seconds  $2 elapsed real seconds
    local remain=$(( $1 - $2 )) floor
    floor=60
    [ "$remain" -lt "$floor" ] && remain="$floor"
    echo "$remain"
}
# Shared run-start anchor, epoch ms. Every event the router renders into a
# prompt is expressed as an age relative to THIS instant, so it reads on the
# same run clock as the board's "+{rel}m" and the T-45m / T-5m notices. It
# must be published by the RUNNER, not
# derived per-container: four sidecars starting on a stagger would otherwise
# anchor to four different instants and disagree about how old the same event
# is. Without it each router falls back to its own process start, which is
# close but drifts with restarts.
export PBENCH_RUN_START_MS="${PBENCH_RUN_START_MS:-$(python3 -c 'import time; print(int(time.time()*1000))')}"
DOCKER_ORG="${PROGRAMBENCH_DOCKER_ORG:-programbench}"
REPO="${PBENCH_REPO:-main}"          # the Gitea repo the team works in
PB_REPO="${PROGRAMBENCH_REPO:-$HOME/programbench}"
# docker needs sudo on this host; pbench_submission.py honors PBENCH_DOCKER.
export PBENCH_DOCKER="${PBENCH_DOCKER:-sudo docker}"

# Where the reference binary is parked on the host (root:root 0111) and then
# bind-mounted into every agent at /opt/pbench/executable. gen-compose-prod.py's
# AGENT_BLOCK reads ${PBENCH_BIN:-/dev/null}, so exporting PBENCH_BIN makes the
# real binary mount on a pbench run, while a stack without it gets /dev/null.
BIN_PATH="$OUT_DIR/$TASK/bin/executable"
export PBENCH_BIN="$BIN_PATH"

log() { echo "[pbench] $*" >&2; }
die() { echo "[pbench] FATAL: $*" >&2; exit 1; }

source "$ROOT/scripts/lib_prompts.sh"
source "$ROOT/scripts/lib_pbench_images.sh"
command -v envsubst >/dev/null 2>&1 || die "envsubst not found (apt install gettext-base); it renders the prompts under prompts/"

# Reject stale profiles and overrides for deployment modes outside this release.
ORCH="$(grep -E '^PBENCH_ORCHESTRATOR=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d ' \r' || true)"
ORCH="${PBENCH_ORCHESTRATOR:-${ORCH:-compose}}"
[ "$ORCH" = "compose" ] || die "PBENCH_ORCHESTRATOR='$ORCH'; this release supports single-node Compose only"

# Global so teardown can stop the idle watchdog and deadline reminders.
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

# instance_id "a__b.sha" → image "<org>/a_1776_b.sha:task_cleanroom_v6"
img_base="$DOCKER_ORG/$(printf '%s' "$TASK" | sed 's/__/_1776_/')"
CLEANROOM_TAG="$(pbench_cleanroom_tag "$ENV_FILE")" || die "reference image configuration mismatch"
CLEANROOM_IMG="$img_base:$CLEANROOM_TAG"

# Benchmark integrity: refuse to start if a prior run's output dir for this
# task already exists. Re-running the same TASK without removing $OUT_DIR/$TASK
# would mix prior submission.tar.gz / *.eval.json / export.log into this run's
# outputs. Operator must `rm -rf $OUT_DIR/$TASK` before re-running.
if [ -e "$OUT_DIR/$TASK" ]; then
    die "$OUT_DIR/$TASK already exists — leftover output from a prior run would be mixed in. Remove it (\`rm -rf $OUT_DIR/$TASK\`) before re-running."
fi
mkdir -p "$OUT_DIR/$TASK"

# Resolve compose plumbing the same way the Makefile does.
DATA_ROOT="$(grep -E '^DATA_ROOT=' "$ENV_FILE" | cut -d= -f2-)"
DATA_ROOT="${DATA_ROOT:-../.claude-team-data}"
ORG_NAME="$(grep -E '^ORG_NAME=' "$ENV_FILE" | cut -d= -f2-)"

# Benchmark integrity: refuse to start if leftover state from a prior run
# exists. MySQL's agent_kv (acp_session_id), Gitea repo state, Mattermost
# history, and per-agent /opt/data would otherwise persist into this run via
# loadSession() — effectively rejection-sampling the score. Operator must
# `make clean PROFILE=$PROFILE` (DESTRUCTIVE) before re-running.
PROFILE_DATA_DIR="$DATA_ROOT/$PROFILE"
if [ -e "$PROFILE_DATA_DIR" ]; then
    die "$PROFILE_DATA_DIR already exists — leftover state from a prior run would leak into this one (acp_session_id, gitea repo, mattermost history). Run \`make clean PROFILE=$PROFILE\` first."
fi

# Gitea edge port for cloning the team repo after the run.
EDGE_PORT="$(grep -E '^EDGE_HTTP_PORT=' "$ENV_FILE" | cut -d= -f2-)"
GITEA_ADMIN_USER="$(grep -E '^GITEA_ADMIN_USER=' "$ENV_FILE" | cut -d= -f2-)"
GITEA_ADMIN_PASSWORD="$(grep -E '^GITEA_ADMIN_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"

# Deliver the task through Mattermost DMs; agents are passive until an event
# reaches their mini-router. The unassigned Gitea issue is the task record.
EDGE_MM_PORT="$(grep -E '^EDGE_MM_PORT=' "$ENV_FILE" | cut -d= -f2-)"
MATTERMOST_ADMIN_USER="$(grep -E '^MATTERMOST_ADMIN_USER=' "$ENV_FILE" | cut -d= -f2-)"
MATTERMOST_ADMIN_PASSWORD="$(grep -E '^MATTERMOST_ADMIN_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
MATTERMOST_TEAM_NAME="$(grep -E '^MATTERMOST_TEAM_NAME=' "$ENV_FILE" | cut -d= -f2- || true)"
# prod/org compose sets the MM team name to ORG_NAME (see gen-compose-prod.py),
# so default to that rather than the dev "omcgitea".
MATTERMOST_TEAM_NAME="${MATTERMOST_TEAM_NAME:-$ORG_NAME}"
MM_BASE="http://localhost:${EDGE_MM_PORT}"

# Always export a submission on the way out, even if a step failed/timed out:
# the smoke test asserts submission.tar.gz exists regardless of pass/fail.
export_submission() {
    # Defense against $OUT_DIR/$TASK vanishing (e.g. external mv-to-archive
    # from a parallel driver, or a manual cleanup racing our teardown).
    # Without this, the `2>>export.log` redirect below would fail-open and
    # eat the python export's stderr, and the tar fallback would silently
    # create a file in the wrong place.
    mkdir -p "$OUT_DIR/$TASK"

    local team_url="http://${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}@localhost:${EDGE_PORT}/${ORG_NAME}/${REPO}.git"
    log "exporting submission from Gitea repo ${ORG_NAME}/${REPO} → $OUT_DIR/$TASK/"
    # Retry with backoff: with a single attempt, one transient 504 is terminal for the whole
    # task. Gitea is quiesced by now (see quiesce_agents) so an attempt
    # that fails is far more likely to be a tail-latency blip than a real outage.
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

    # Every attempt failed. This is NOT a score: an empty-but-valid tarball here would be
    # scored 0.00% with every test not_run, indistinguishable from a team that built
    # nothing, while the repo is intact and only the export failed. Leave a marker so
    # the scorer and a human can tell "we never got the code" from "the code scored zero".
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
    # Ask the board to write its per-gist lifecycle log before we tear the
    # profile down. render_count — how many times an entry was actually
    # selected into somebody's window — lives only in the board process, so
    # skipping this loses the one measurement that distinguishes "an agent
    # published" from "a peer read it".
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
    # Stop everything that talks to Gitea, and nothing else. Normal completion
    # calls this after its deadline export; emergency teardown calls it before a
    # best-effort recovery export.
    #
    # An export that runs while the agents are still live on Gitea over MCP, and act_runner
    # can still start CI jobs, contends with them: the clone can take minutes or hit nginx's
    # proxy_read_timeout (300s) as a 504, even for a small repo that clones offline in under
    # a second.
    #
    # gitea, mysql and nginx-edge must SURVIVE this: they are what we are about to clone from.
    local proj="omcgitea-$PROFILE"
    local ids agents
    # Scoped by the compose PROJECT LABEL, never by name alone. CLAUDE.md forbids touching a
    # container this project did not create, and this host runs other people's clusters.
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

teardown() {
    local rc=$? archives_ok=1
    log "teardown (rc=$rc): quiescing agents, exporting submission, stopping profile"
    stop_background_loops
    dump_board_lifecycle || true
    quiesce_agents || archives_ok=0
    export_submission || true
    if [ "$archives_ok" = 1 ]; then
        make down PROFILE="$PROFILE" >/dev/null 2>&1 || true
    else
        log "ERROR: incomplete shutdown archives; preserving containers and DATA_ROOT for recovery"
        return 1
    fi
    return 0
}

# --- 1. seed cleanroom workspace into the team repo -------------------------
seed_repo() {
    log "seeding cleanroom workspace from $CLEANROOM_IMG"
    if ! sudo docker image inspect "$CLEANROOM_IMG" >/dev/null 2>&1; then
        log "pulling $CLEANROOM_IMG (first run; agents get NO internet so this MUST happen host-side now)"
        sudo docker pull "$CLEANROOM_IMG" >/dev/null 2>&1 \
            || die "cannot pull $CLEANROOM_IMG (check task id / dockerhub access)"
    fi
    local cleanroom_id
    cleanroom_id="$(sudo docker image inspect --format '{{.Id}}' "$CLEANROOM_IMG")" \
        || die "cannot identify reference image"
    local seed_dir="$OUT_DIR/$TASK/_seed"
    rm -rf "$seed_dir"; mkdir -p "$seed_dir"
    # The reference binary is pulled OUT of the repo tree (never committed; a git
    # blob is world-readable = anti-reverse-engineering leak) and parked at $BIN_PATH, which we then
    # mount root:root 0111 into every agent at /opt/pbench/executable.
    PROGRAMBENCH_DOCKER_ORG="$DOCKER_ORG" \
        python3 tools/pbench_submission.py seed --image "$cleanroom_id" \
        --into "$seed_dir" --bin-out "$BIN_PATH" \
        || die "seed extraction failed"
    if [ -f "$BIN_PATH" ]; then
        # root:root 0111 — agents (uid 10000) can EXECUTE but never READ the bytes.
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
    # The actual push into the agent team's Gitea repo happens once the stack
    # is up (the repo only exists post-bootstrap). We stage it here and the
    # post-up step commits it.
    echo "$seed_dir" > "$OUT_DIR/$TASK/.seed_path"
}

# --- mattermost helpers (admin session token cached for the whole run) ------
# Agents wake on real MM events (websocket) far more reliably than on a stray
# gitea issue, so the primary task-delivery path is a MM channel/@mention.
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
mm_user_id() {  # username → id
    mm_login || return 1
    curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" \
        "${MM_BASE}/api/v4/users/username/$1" \
        | jq -r 'select(.status_code == null) | .id // empty'
}
mm_post() {  # channel_id message
    mm_login || return 1
    curl -fsS -H "Authorization: Bearer $MM_ADMIN_TOKEN" -H 'Content-Type: application/json' \
        -X POST -d "$(jq -nc --arg c "$1" --arg m "$2" '{channel_id:$c, message:$m}')" \
        "${MM_BASE}/api/v4/posts" >/dev/null 2>&1
}

# mm_dm_channel <username> → prints channel_id of the admin↔user DM.
# MM's /channels/direct is idempotent — returns the existing one if any.
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

# Open or reuse the private task channel for the peer coders; return its id.
TASK_CHANNEL_ID=""
# The mattermost MCP takes only a URL + token — upstream exposes no default
# team — so every team-scoped tool (post_message, search_messages,
# list_my_channels) needs ids the agent must otherwise discover. Agents that
# fail that discovery invent 26-char ids, and mattermost answers 403 for a
# team you are not in, which an agent reads as a lockout and goes silent. We
# know both ids here, so we hand them over instead.
MM_TEAM_ID=""
mm_ensure_task_channel() {
    mm_login || return 1
    local team_id
    team_id=$(curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" \
        "${MM_BASE}/api/v4/teams/name/${MATTERMOST_TEAM_NAME}" | jq -r 'select(.status_code == null) | .id // empty')
    if [ -z "$team_id" ]; then
        # Bootstrap may have skipped MM provisioning (reused .bootstrap-done
        # mark after a data wipe). Create the team so the drive path still works.
        log "MM team ${MATTERMOST_TEAM_NAME} missing; creating it"
        team_id=$(curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" -H 'Content-Type: application/json' \
            -X POST -d "$(jq -nc --arg n "$MATTERMOST_TEAM_NAME" \
                '{name:$n, display_name:$n, type:"O"}')" \
            "${MM_BASE}/api/v4/teams" | jq -r '.id // empty')
        [ -n "$team_id" ] || { log "WARN: could not create MM team"; return 1; }
    fi
    # Ensure admin and every worker are team members
    # (needed to add them to the channel and for the @mention to actually
    # notify them). bootstrap.sh:675 already does this on a fresh install; we
    # repeat here so a re-run after a data wipe with a stale .bootstrap-done
    # mark still ends up with a fully populated team.
    local admin_id; admin_id=$(mm_user_id "$MATTERMOST_ADMIN_USER") || true
    # Derive the worker list from PBENCH_WORKERS_PER_TEAM so every worker is
    # pulled into the MM team + channel.
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
    # Provision channel membership here: channel administration tools are
    # excluded by agent/config/copilot-deny-tools.json.
    local uid code
    for agent in "${extra_team_members[@]}"; do
        uid=$(mm_user_id "$agent") || true
        [ -n "$uid" ] || { log "WARN: no MM user id for $agent"; continue; }
        # mm_join_ok: a discarded failure here surfaces hours later as an
        # unexplained 403 in an agent's transcript, so record it now.
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
    # Both ids on stdout: the caller runs this in a $() subshell, so plain
    # assignment to the globals above is lost to the parent shell.
    printf '%s %s' "$team_id" "$ch"
}

# The canonical task brief: the gitea issue #1 body, the wake DMs and the MM
# task channel post all carry it.
task_brief() {
    render_prompt "$PROMPTS_DIR/task-brief.md" \
        TASK="$TASK" REPO="$REPO" MM_TEAM_ID="$MM_TEAM_ID" TASK_CHANNEL_ID="$TASK_CHANNEL_ID"
}

# Deadline reminders, posted to the shared task channel.
#
# The brief deliberately does NOT state the total budget. A team told it has
# six hours plans for six hours, and its failures cluster at the end rather
# than being spread through it.
#
# What the agents actually need is not a number to pace against but a signal at
# the two points where the right action changes: stop starting new work, and
# land what exists. There is no clock in the container and no external trigger,
# so the team cannot tell when either has arrived. The runner tells it.
deadline_reminder_loop() {
    local secs="$1"
    # 45 and 5 minutes before the end, matching the board's +{rel}m stamps.
    local t45=$(( secs - 45 * 60 ))
    local t5=$((  secs - 5  * 60 ))
    if [ "$t45" -gt 0 ]; then
        sleep "$t45"
        mm_post "$TASK_CHANNEL_ID" "$(render_prompt "$PROMPTS_DIR/deadline-45m.md")" \
            || log "WARN: T-45m reminder failed"
        log "posted T-45m reminder"
    fi
    local rest=$(( t5 - (t45 > 0 ? t45 : 0) ))
    if [ "$rest" -gt 0 ]; then
        sleep "$rest"
        mm_post "$TASK_CHANNEL_ID" "$(render_prompt "$PROMPTS_DIR/deadline-5m.md")" \
            || log "WARN: T-5m reminder failed"
        log "posted T-5m reminder"
    fi
}

# --- 3. drive: seed initial commit + wake peer coders -----------------------
# Per-agent wake interval. The base rate applies for the first hour of the
# ramp, then a fast rate for the remainder.
#
# WHY A FIXED RATE DOES NOT SCALE. 30s per agent is fine to 32 and ruinous past
# it, because HOURS counts the whole run including the ramp -- every second of
# stagger comes out of the LAST agent's working budget:
#     128 agents   64 min      1000 agents   8.3 h
#
# The base rate covers the first PBENCH_WAKE_RAMP_SUBJ_S (default 3600) seconds
# of the ramp, so the switch lands on agent 3600/30 = 120.
#
# Agents 1..switch_at get the base rate; the rest get the fast one. At 4-32
# workers nothing reaches the switch, so they run at the base rate throughout.
wake_stagger_for() {   # wake_stagger_for <1-based agent index> -> seconds
    local _i="$1"
    local _base="${PBENCH_WAKE_STAGGER_S:-30}"
    local _switch=$(( ${PBENCH_WAKE_RAMP_SUBJ_S:-3600} / _base ))
    if [ "$_i" -le "$_switch" ]; then
        echo "$_base"
    else
        echo "${PBENCH_WAKE_FAST_STAGGER_S:-3}"
    fi
}

# Start one worker's agent and router, retrying until the start works: an agent
# that never starts would leave the run going for its whole budget without it.
# Each failure logs the end of make's output.
# --no-deps is load-bearing: without it compose restarts this agent's dependency
# chain (gitea/mysql/mattermost/bootstrap) on EVERY agent start. Infra is
# already up from the infra-only bringup.
start_agent_containers() {  # start_agent_containers <worker index> <agent name>
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
    # RETRY, AND NEVER RETURN FROM HERE.
    #
    # A `return` here leaves the WHOLE drive phase: a single failed clone would
    # skip the mattermost team/channel setup, the task issue and the entire wake
    # loop, and the run would sleep out its budget having woken nobody and exit
    # 0. The first clone can be reset ("Recv failure: Connection reset by peer")
    # while hundreds of containers are coming up.
    #
    # The seed is a convenience; the wake is the run. A failure here must cost
    # the seed only, so this retries and then falls through either way.
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

    # The MM team/channel must exist BEFORE the brief is rendered: the brief
    # quotes both ids so agents never have to discover them, and it is reused
    # verbatim for the gitea issue below.
    local _mm ch
    _mm="$(mm_ensure_task_channel)" || _mm=""
    MM_TEAM_ID="${_mm%% *}"
    ch="${_mm##* }"
    [ "$_mm" = "" ] && { MM_TEAM_ID=""; ch=""; }
    TASK_CHANNEL_ID="$ch"

    local brief; brief="$(task_brief)"
    local kickoff; kickoff="$(render_prompt "$PROMPTS_DIR/kickoff.md" TASK_BRIEF="$brief")"

    # (a) Gitea issue #1, the task record every agent's prompt points at.
    # NO ASSIGNEE: peers self-select, and gitea rejects the whole request when
    # the assignee is an account that does not exist, so issue #1 would never
    # be created. An admin-opened, unassigned issue notifies nobody (bootstrap
    # unwatches every agent from the repo); the wake comes from the staggered
    # DMs below, not from a notification.
    log "opening task issue (no assignee; peers self-select)"
    curl -fsS -u "${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}" \
        -H 'Content-Type: application/json' \
        -d "$(python3 -c 'import json,sys; print(json.dumps({"title": f"[pbench] {sys.argv[1]}", "body": sys.argv[2]}))' "$TASK" "$brief")" \
        "http://localhost:${EDGE_PORT}/api/v1/repos/${ORG_NAME}/${REPO}/issues" \
        >/dev/null 2>&1 \
        && log "task issue opened" \
        || log "WARN: could not open task issue"

    # (b) Deliver the kickoff to each peer coder over Mattermost.
    # The channel was already created above (the brief needs its id), and
    # TASK_CHANNEL_ID / MM_TEAM_ID are set in THIS shell there — which also
    # gives the background worker_watchdog_loop, forked from this shell at
    # main(), a non-empty TASK_CHANNEL_ID to guard on.
    # WAKE AGENTS ONE AT A TIME.
    #
    # One channel post wakes every member at once, and agents woken together all
    # read an empty board and claim the same first areas within seconds. A
    # sequenced DM gives agent N a board with N-1 claims already on it, which
    # is the difference between "explore the unexplored areas" meaning something
    # and meaning nothing. At 16 agents, 15 x 30s = 7.5 min of a 360 min run (2%).
    #
    # The channel record is posted LAST, on purpose: posting it first would wake
    # everyone and defeat the stagger.
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
    # HOURS is the WHOLE run, stagger included: a 0.5h run must finish 30 min
    # after the first agent wakes, not 30 min after the last one. Stamp t0 here
    # and subtract the wake time from the sleep below, otherwise a 16-agent
    # 30s stagger silently turns "0.5h" into 37.5 min and "6h" into 6h07.
    PBENCH_RUN_T0=$(date +%s)
    export PBENCH_RUN_T0

    # START THE IDLE WATCHDOG BEFORE THE RAMP, not after it.
    #
    # Forked after the wake loop instead, it would leave the whole ramp without
    # an idle nudge, because container bringup runs on the stagger:
    #     8 agents x30s ->  4 min with no idle nudge
    #   128 agents x30s -> 64 min
    # and the earliest-woken agents are the ones most likely to run out of
    # events and sit idle in that window.
    #
    # Forked HERE, TASK_CHANNEL_ID is already set (just above), which is the
    # value the loop guards on. Duration is the whole run; the loop exits on
    # its own deadline.
    if [ "${PBENCH_WATCHDOG_EARLY:-1}" = "1" ]; then
        local _wd_secs
        _wd_secs="$(python3 -c "print(int(round(float('${HOURS:-6}')*3600)))" 2>/dev/null || echo 21600)"
        worker_watchdog_loop "$_wd_secs" &
        WATCHDOG_PID=$!
        log "idle watchdog started BEFORE the ramp (pid $WATCHDOG_PID, ${_wd_secs}s)"
    fi

    for wi in $(seq 1 "$n_workers_wake"); do
        wname="${ORG_NAME}-worker${wi}"
        # START THE CONTAINER ON THE STAGGER, not just the DM.
        #
        # Bringing every agent up at once and relying on the DM to sequence them
        # does not work:
        #   - every copilot CLI unpacks its package simultaneously, and at scale
        #     most of them never finish unpacking or create a session.
        #   - the first DM-woken agent's channel post wakes every agent that has
        #     a session, because an idle agent is dispatched by any event, not
        #     only by its own kickoff DM.
        # An agent that has not been started yet cannot be woken early by a
        # peer's post, and cannot contend for unpack I/O. That makes the stagger
        # real instead of advisory, and needs no event-holding machinery.
        # Stamp BEFORE the bringup, not after: the interval must absorb the
        # container start (~30s) rather than add to it. Stamped after, each
        # interval becomes the stagger plus the bringup, and since HOURS counts
        # the whole run the last agent loses that much more of its budget.
        _wake_started=$(date +%s)
        if [ "${PBENCH_STAGGERED_BRINGUP:-1}" = "1" ]; then
            start_agent_containers "$wi" "$wname"
            # Let the CLI unpack and the ACP socket appear before the DM lands;
            # a DM to an agent whose session is not up yet is simply lost.
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
        # The interval between agents must be stagger_s TOTAL, not stagger_s
        # PLUS however long bringup and settling took. At 128 agents a naive
        # `sleep $stagger_s` here turns a 64-minute ramp into ~2 hours, and
        # HOURS counts the whole run, so the last agent would lose that time
        # from its budget.
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
        # No fallback needed: the DM wake above already delivered the task to
        # every agent individually.
        log "WARN: no MM channel for the task record (agents were woken by DM)"
    fi
}

# --- worker idle watchdog: per-agent activity check every 60s ---------------
# Each agent's turns/tool-calls append to a jsonl trail under
# ${DATA_ROOT}/${PROFILE}/agents/<agent>/home/.copilot/session-state/<id>/events.jsonl,
# so the newest event-log mtime under an agent is its last
# activity time. When a worker crosses WORKER_IDLE_THRESHOLD (default 600s =
# 10m) with no new events and nothing queued for it, we DM that worker a nudge
# toward fresh work. Falls back to the shared task channel if DMs can't be
# opened. Per-worker rate limit
# (WORKER_IDLE_REPEAT default 600s = 10m) prevents spam on stuck workers.
WORKER_IDLE_THRESHOLD="${WORKER_IDLE_THRESHOLD:-600}"
WORKER_IDLE_REPEAT="${WORKER_IDLE_REPEAT:-600}"
WORKER_CHECK_INTERVAL="${WORKER_CHECK_INTERVAL:-60}"

# Pending UEM rows for one agent. An agent with queued events will be woken by the queue,
# and nudging on top of that races the dispatcher and buries the event.
# Empty output = "could not tell", which the caller treats as "nudge anyway"
# rather than as zero -- failing closed here silences this watchdog entirely.
watchdog_uem_pending() {  # $1 worker_name -> count, or empty
    local w="$1"
    local sql="SELECT COUNT(*) FROM events WHERE agent='${w}' AND state IN ('pending','sending','retrying','failed');"
    if [ -n "${MYSQL_CONTAINER:-}" ] && [ -n "${MYSQL_ROOT_PW:-}" ]; then
        sudo docker exec "$MYSQL_CONTAINER" \
            mysql -N -B -uroot -p"$MYSQL_ROOT_PW" -D omcgitea -e "$sql" \
            2>/dev/null | tr -d '[:space:]' || true
    fi
}

# Threshold + rate-limit + queue check + nudge for one agent.
watchdog_consider() {  # $1 worker_name  $2 idle_secs  $3 now  $4 dedup_dir
    local worker_name="$1" idle="$2" now="$3" dedup_dir="$4"
    [ "$idle" -ge 0 ] 2>/dev/null || return 0          # -1 => never prompted
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

    local idle_msg; idle_msg="$(render_prompt "$PROMPTS_DIR/idle.md")"
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
    mkdir -p "$dedup_dir"
    local start now elapsed
    start=$(date +%s)
    # A watchdog that cannot read the agent dirs (a wrong path, a permission
    # wall) looks identical to a healthy run, because a scan that yields nothing
    # reads as "everyone is busy". If it cannot read them, say so once, loudly,
    # rather than tick quietly for six hours.
    if ! sudo -n true 2>/dev/null; then
        log "WARN: watchdog cannot sudo -n; agent turn logs are 0700 ACP_CHILD_UID, so every worker will read as busy and NO idle nudge will ever fire"
    fi
    # UEM-queue probe. Resolved ONCE, and every use is guarded: if either
    # piece is missing the watchdog still nudges, it just cannot skip agents that
    # already have work queued. Failing closed here would silence the watchdog
    # while it looks healthy.
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
        if [ ! -d "$agents_root" ]; then sleep "$WORKER_CHECK_INTERVAL"; continue; fi
        local agent_dir worker_name last_mtime idle
        for agent_dir in "$agents_root"/${ORG_NAME}-*worker*; do
            [ -d "$agent_dir" ] || continue
            worker_name="$(basename "$agent_dir")"
            # Each Copilot session writes its event log under this persistent home.
            local copilot_dir="$agent_dir/home/.copilot/session-state"
            local scan=()
            [ -d "$copilot_dir" ] && scan+=("$copilot_dir")
            [ ${#scan[@]} -gt 0 ] || continue
            # sudo: the agent writes these as ACP_CHILD_UID with the session dir at
            # 0700, so an unprivileged find cannot descend and returns EMPTY --
            # which this loop cannot tell apart from "the agent is busy".
            last_mtime=$(sudo -n find "${scan[@]}" -type f -name '*.jsonl' \
                -printf '%T@\n' 2>/dev/null | sort -rn | head -1 | cut -d. -f1 || true)
            [ -n "$last_mtime" ] || continue
            idle=$((now - last_mtime))
            # Threshold, rate limit, UEM check and nudge all live in
            # watchdog_consider() to keep the idle policy in one place.
            watchdog_consider "$worker_name" "$idle" "$now" "$dedup_dir"
        done
        sleep "$WORKER_CHECK_INTERVAL"
    done
}

# The agent image compose runs: the shell's AGENT_IMAGE if set (make runs compose
# under sudo -E, and a shell value beats --env-file), else .env.<profile>'s.
agent_image() {
    local img="${AGENT_IMAGE:-}"
    [ -n "$img" ] || img="$(grep -E '^AGENT_IMAGE=' "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d ' \r')"
    [ -n "$img" ] && printf '%s\n' "$img"
}

# Clear stale container records for this profile's compose project before
# bringup. compose can hold a reference to a container the daemon no longer has
# ("dependency failed to start: No such container"), left behind by containers
# that died outside compose (docker kill, cgroup.kill, OOM), and the infra
# bringup then fails with only a few services up. Selected by the project label,
# exactly; never a global rm or prune.
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
    # Checked here so a typo fails in seconds, not after make up has
    # provisioned a stack.
    local agent_img
    agent_img="$(agent_image)" || die "AGENT_IMAGE is not set in .env.$PROFILE"
    log "agent image: $agent_img"
    sudo docker image inspect "$agent_img" >/dev/null 2>&1 \
        || die "agent image missing: $agent_img (build it with scripts/pbench_build_pertask_images.sh)"
    log "bringing up $PROFILE stack"
    # Render this profile's compose base BEFORE `make up`. `make up` renders it
    # too; rendering here keeps the assertion below independent of the
    # Makefile. Rendering is idempotent and costs ~0.2s.
    make -s render-pbench-base PROFILE="$PROFILE" >/dev/null 2>&1 \
        || die "render-pbench-base failed for $PROFILE"
    # Assert the rendered base actually carries the topology the .env asks for,
    # so a generator regression fails loudly instead of silently under-sizing.
    local _want_w _got_w _base="$ROOT/docker/_gen-prod.$PROFILE.yml"
    _want_w="$(grep -E '^PBENCH_WORKERS_PER_TEAM=' "$ROOT/.env.$PROFILE" 2>/dev/null | cut -d= -f2 | tr -d ' ')"
    if [ -n "$_want_w" ]; then
        [ -f "$_base" ] || die "compose base not rendered: $_base"
        _got_w="$(grep -cE '^  agent-worker[0-9]+:' "$_base" || true)"
        [ "$_got_w" = "$_want_w" ] \
            || die "compose base $_base has $_got_w workers, .env asks for $_want_w"
        log "compose base rendered: $_want_w workers/team"
    fi
    # Serialize `make up` across concurrent runs on this host. Simultaneous
    # `docker compose up -d` calls race the docker daemon, and mysql's
    # `depends_on: service_healthy` can time out on the loser.
    # flock lets only one `make up` progress at a time; others block on the
    # lock and start their bringup once the daemon is quiet again. The
    # 900s timeout is a hard ceiling — if we can't grab the lock in 15 min
    # something else is very wrong.
    local up_lock="/tmp/pbench-make-up.lock"
    exec 9>"$up_lock"
    flock -w 900 9 || die "could not acquire $up_lock in 15min"
    log "acquired make-up lock (pid $$)"
    if [ "${PBENCH_STAGGERED_BRINGUP:-1}" = "1" ]; then
        # Infra only. Agent + router containers are started later, one pair at a
        # time, inside the wake loop -- see the comment there for why. The list
        # is DERIVED from compose
        # rather than hardcoded, so a new infra service is picked up
        # automatically and a renamed one fails loudly instead of silently
        # being left down.
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
    exec 9>&-  # release the lock — bringup is done, other chains may proceed

    push_seed_and_drive

    local secs
    # HOURS is the wall-clock budget.
    secs="$(run_budget_seconds)"
    if [ -n "${PBENCH_RUN_T0:-}" ]; then
        _elapsed=$(( $(date +%s) - PBENCH_RUN_T0 ))
        [ "$_elapsed" -lt 0 ] && _elapsed=0
        # Preserve the experiment's 60-second floor when its ramp overruns.
        _remain="$(run_budget_remaining "$secs" "$_elapsed")"
        log "agents working for ${HOURS}h (${secs}s); ${_elapsed}s spent waking, sleeping ${_remain}s"
        secs="$_remain"
    else
        log "agents working for ${HOURS}h (${secs}s); waiting…"
    fi
    # Per-worker idle watchdog runs in the background: it DMs the specific
    # worker that has stopped emitting jsonl events, pointing it at new work
    # drawn from executable interaction. Falls back to the shared task channel
    # if DMs can't be opened.
    # Already forked before the ramp (see push_seed_and_drive). Only fork here
    # if that was disabled, otherwise two watchdogs nudge the same agents.
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

    # teardown (trap) exports the submission and stops the stack. Run eval
    # AFTER export, so do it here before exit by exporting explicitly first.
    trap - EXIT
    # Preserve the experiment's cutoff order: export first, then stop agents.
    # A failed export must still release compute; DATA_ROOT retains the repo
    # for recovery and EXPORT_FAILED distinguishes it from a measured zero.
    export_submission || true
    quiesce_agents || die "incomplete shutdown archives; preserving containers and DATA_ROOT for recovery"
    make down PROFILE="$PROFILE" >/dev/null 2>&1 || true

    # --- 6. eval -------------------------------------------------------------
    if [ "${SKIP_EVAL:-0}" = "1" ]; then
        log "SKIP_EVAL=1 → deferring programbench eval (submission left at $OUT_DIR/$TASK/submission.tar.gz)"
        return 0
    fi
    log "running programbench eval on $OUT_DIR"
    # This host's docker socket is root-only; ProgramBench shells out to a single
    # docker executable (PROGRAMBENCH_DOCKER_EXECUTABLE). Point it at our shim so
    # eval runs `sudo docker` with a writable HOME (avoids the root-owned
    # ~/.docker/config.json permission warning the harness treats as a failure).
    export PROGRAMBENCH_DOCKER_EXECUTABLE="${PROGRAMBENCH_DOCKER_EXECUTABLE:-$ROOT/scripts/pbench-docker-sudo.sh}"
    # The harness mkstemp()s a host temp file then `docker cp container:foo host_tmp`
    # over it. Because our shim runs docker as ROOT, that temp file ends up
    # root-owned; the harness's finally-block unlink() then fails inside the
    # default /tmp (sticky bit forbids non-owners deleting). Point TMPDIR at a
    # user-owned, NON-sticky dir so we can still unlink root-owned files there.
    local pbench_tmp="$OUT_DIR/$TASK/_evaltmp"
    rm -rf "$pbench_tmp"; mkdir -p "$pbench_tmp"
    export TMPDIR="$pbench_tmp"
      # Eval unpacks and BUILDS the submission on the HOST, outside every container, so it is
      # the one ProgramBench workload compose's cgroup_parent cannot reach. Enter the slice
      # explicitly: a single runaway `executable`, or a build that forks a runaway compiler, can
      # exhaust host memory and take the machine down.
      # See docker/pbench.slice.
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
