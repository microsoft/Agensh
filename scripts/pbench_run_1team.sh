#!/usr/bin/env bash
# pbench_run_1team.sh — ProgramBench runner for the org-pbench-1team topology.
#
# Fork of scripts/pbench_run.sh with the 5-team / director / auditor scaffolding
# replaced by 1-team wording. Base script stays untouched (used by the 37-agent
# runs); this variant is only invoked by scripts/pbench_chain_v48_opus48_1team.sh
# and by manual 1team smoke launches.
#
# Differences from the base script:
#   1. DIRECTOR_AGENT / AUDITOR_AGENT are read from .env.<profile>
#      (PBENCH_DIRECTOR_AGENT / PBENCH_AUDITOR_AGENT). In 1team both resolve to
#      pbench-team1-lead — the merged director_lead role.
#   2. The initial MM task post dedupes @-mentions when director == auditor and
#      says "break down work, dispatch sub-issues" instead of "assign to each lead".
#   3. worker_watchdog_loop pings the merged director/lead about individual
#      workers, not "each team".
#   4. Pre-flight guard: refuse to start if omcgitea-hermes-agent:local is not
#      already loaded (the v48 tar must be `docker load`-ed first).
#
# Everything else — seed, submission export, eval, teardown — is byte-identical
# to the base script.
#
#   TASK=<instance_id> HOURS=<wall_clock> PROFILE=org-pbench-1team \
#     scripts/pbench_run_1team.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TASK="${TASK:?TASK=<instance_id> required (e.g. abishekvashok__cmatrix.5c082c6)}"
HOURS="${HOURS:-2}"
OUT_DIR="${OUT_DIR:-$ROOT/out/pbench}"
# PROFILE is overridable so several instances can run side-by-side, each with
# its own compose project (omcgitea-$PROFILE), DATA_ROOT/$PROFILE data dir and
# host port triple. Default keeps the single-instance behavior (org-pbench).
# Any org-pbench* profile loads the pbench overlay (see Makefile).
PROFILE="${PROFILE:-org-pbench}"
ENV_FILE="$ROOT/.env.$PROFILE"
DOCKER_ORG="${PROGRAMBENCH_DOCKER_ORG:-programbench}"
REPO="${PBENCH_REPO:-main}"          # the Gitea repo the team works in
PB_REPO="${PROGRAMBENCH_REPO:-$HOME/programbench}"
# docker needs sudo on this host; pbench_submission.py honors PBENCH_DOCKER.
export PBENCH_DOCKER="${PBENCH_DOCKER:-sudo docker}"

# Where the reference binary is parked on the host (root:root 0111) and then
# bind-mounted into every agent at /opt/pbench/executable. gen-compose-prod.py's
# AGENT_BLOCK reads ${PBENCH_BIN:-/dev/null}, so exporting PBENCH_BIN makes the
# real binary mount for org-pbench while dev/prod (unset) get a harmless /dev/null.
BIN_PATH="$OUT_DIR/$TASK/bin/executable"
export PBENCH_BIN="$BIN_PATH"

log() { echo "[pbench] $*" >&2; }
die() { echo "[pbench] FATAL: $*" >&2; exit 1; }

[ -f "$ENV_FILE" ] || die "$ENV_FILE missing (task #1 should have created it)"

# instance_id "a__b.sha" → image "<org>/a_1776_b.sha:task_cleanroom_v6"
#
# The _v6 suffix is not optional. ProgramBench publishes several cleanroom tags
# per task and they are NOT rebuilds of each other — for ffmpeg the bare
# :task_cleanroom is ffmpeg git-2026-04-13 built --disable-ffplay --disable-ffprobe,
# while :task_cleanroom_v6 is git-2026-06-11 with --disable-autodetect --enable-zlib
# --enable-lzma --enable-iconv on top. Different commit, different compiled-in
# demuxers, zero shared layers.
#
# This tag has to match the one pbench_build_pertask_images.sh feeds to
# Dockerfile.pertask as TASK_IMAGE, because the two halves meet in the agent:
# the image fixes the toolchain it compiles with, this tag fixes the reference
# binary it studies at /opt/pbench/executable. 6.11 moved the build path to _v6
# and left this line behind, so agents reverse-engineered April behaviour on the
# June toolchain and were graded on June. Nothing errored; the score was just
# measured against the wrong target. tests/pbench/test_cleanroom_tag.sh pins them
# together.
img_base="$DOCKER_ORG/$(printf '%s' "$TASK" | sed 's/__/_1776_/')"
CLEANROOM_IMG="$img_base:task_cleanroom_v6"

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
# AGENT_IMAGE selects the per-task agent image, and compose reads it from
# .env.<profile> via --env-file. The preflight further down re-checks it, so it
# has to resolve from the SAME place: reading only the shell meant the guard
# inspected the v48 fallback tag while the run used the per-task image, and on a
# host without that stale tag every task refused to start naming an image the
# profile never asked for. Nothing exports it — pbench_chain.sh does not, and
# pbench_1team_sweep.sh only validates the value in the file. An explicit
# AGENT_IMAGE in the environment still wins, for one-off overrides.
AGENT_IMAGE="${AGENT_IMAGE:-$(grep -E '^AGENT_IMAGE=' "$ENV_FILE" | cut -d= -f2-)}"

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

# Mattermost edge port + admin creds — agents are PASSIVE (mini-router pulls
# Gitea notifications + MM websocket and only then prompts the ACP turn). An
# admin-opened gitea issue with no assignee/@mention notifies nobody, so the
# director never wakes. We therefore drive the team via MM DM/@mention (the
# reliable wakeup path) AND @director on the gitea issue, with a periodic MM
# reminder as a fallback.
EDGE_MM_PORT="$(grep -E '^EDGE_MM_PORT=' "$ENV_FILE" | cut -d= -f2-)"
MATTERMOST_ADMIN_USER="$(grep -E '^MATTERMOST_ADMIN_USER=' "$ENV_FILE" | cut -d= -f2-)"
MATTERMOST_ADMIN_PASSWORD="$(grep -E '^MATTERMOST_ADMIN_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
MATTERMOST_TEAM_NAME="$(grep -E '^MATTERMOST_TEAM_NAME=' "$ENV_FILE" | cut -d= -f2- || true)"
# prod/org compose sets the MM team name to ORG_NAME (see gen-compose-prod.py),
# so default to that rather than the dev "omcgitea".
MATTERMOST_TEAM_NAME="${MATTERMOST_TEAM_NAME:-$ORG_NAME}"
DIRECTOR_AGENT="$(grep -E '^PBENCH_DIRECTOR_AGENT=' "$ENV_FILE" | cut -d= -f2- || true)"
DIRECTOR_AGENT="${DIRECTOR_AGENT:-${ORG_NAME}-director}"
AUDITOR_AGENT="$(grep -E '^PBENCH_AUDITOR_AGENT=' "$ENV_FILE" | cut -d= -f2- || true)"
AUDITOR_AGENT="${AUDITOR_AGENT:-${ORG_NAME}-auditor}"
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

    # DeLM baselines write source files directly to a shared /work bind-mount
    # (WORK_HOST_PATH) instead of committing to a Gitea repo. When that env is
    # set, use the workdir path; otherwise fall back to gitea export.
    if [ -n "${WORK_HOST_PATH:-}" ] && [ -d "$WORK_HOST_PATH" ]; then
        log "exporting submission from shared workdir $WORK_HOST_PATH → $OUT_DIR/$TASK/"
        if sudo python3 tools/pbench_submission.py export \
            --from-workdir "$WORK_HOST_PATH" --task "$TASK" --out-dir "$OUT_DIR" \
            2>>"$OUT_DIR/$TASK/export.log"; then
            log "submission.tar.gz written from workdir"
            # Fix ownership so downstream (unarchive/eval) can read it as the user
            sudo chown -R "$(id -u):$(id -g)" "$OUT_DIR/$TASK" 2>/dev/null || true
            return 0
        else
            log "WARN: workdir export failed (see export.log); writing empty stub"
            tar -czf "$OUT_DIR/$TASK/submission.tar.gz" -C "$OUT_DIR/$TASK" --files-from /dev/null 2>/dev/null || \
                : > "$OUT_DIR/$TASK/submission.tar.gz"
            return 0
        fi
    fi

    local team_url="http://${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}@localhost:${EDGE_PORT}/${ORG_NAME}/${REPO}.git"
    log "exporting submission from Gitea repo ${ORG_NAME}/${REPO} → $OUT_DIR/$TASK/"
    # Retry with backoff. In 6.11 this was a single attempt, and one transient 504 was terminal
    # for the whole 6-hour task. Gitea is quiesced by now (see quiesce_agents) so an attempt
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

    # Every attempt failed. This is NOT a score: 6.11 wrote an empty-but-valid tarball here and
    # eval duly recorded 2579 not_run -> 0.00%, indistinguishable from a team that built
    # nothing. The submission existed the whole time; only the export failed. Leave a marker so
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
    bs=$(sudo docker ps --filter "name=${COMPOSE_PROJECT:-omcgitea-$PROFILE}-board-service" \
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
    # Stop everything that TALKS to Gitea, and nothing else, before we clone from it.
    #
    # Sweep 6.11 lost ctags and pandoc here. The export used to run with all 5 agents still
    # live on Gitea over MCP and act_runner still able to start CI jobs; four stacks hit their
    # 6h deadline inside 19 minutes and tore down into the same host. Both exports got HTTP 504
    # at exactly nginx's proxy_read_timeout 300s, and the two that succeeded still took 7.5 and
    # 13.5 minutes for a shallow clone of an 8 MB repo. Cloned offline afterwards the same
    # repos exported in under a second, so the repos were never the problem -- the contention
    # was. See tests/pbench/test_export_resilience.sh.
    #
    # gitea, mysql and nginx-edge must SURVIVE this: they are what we are about to clone from.
    local proj="${COMPOSE_PROJECT:-omcgitea-$PROFILE}"
    local ids
    # Scoped by the compose PROJECT LABEL, never by name alone. CLAUDE.md forbids touching a
    # container this project did not create, and this host runs other people's clusters.
    ids=$(sudo docker ps -q \
            --filter "label=com.docker.compose.project=$proj" \
            --filter "name=hermes-agent" \
            --filter "name=mini-router" \
            --filter "name=act-runner" 2>/dev/null | sort -u)
    if [ -z "$ids" ]; then
        log "quiesce: no agent/router/runner containers running for $proj"
        return 0
    fi
    log "quiesce: stopping $(echo "$ids" | wc -l) agent/router/runner containers (gitea stays up)"
    # A short timeout: these are being torn down anyway, and a graceful stop that waits on an
    # in-flight LLM turn would reintroduce the delay we are removing.
    sudo docker stop -t 10 $ids >/dev/null 2>&1 || true
}

teardown() {
    local rc=$?
    log "teardown (rc=$rc): quiescing agents, exporting submission, stopping profile"
    dump_board_lifecycle || true
    quiesce_agents || true
    export_submission || true
    make down PROFILE="$PROFILE" >/dev/null 2>&1 || true
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
    local seed_dir="$OUT_DIR/$TASK/_seed"
    rm -rf "$seed_dir"; mkdir -p "$seed_dir"
    # The reference binary is pulled OUT of the repo tree (never committed; a git
    # blob is world-readable = anti-reverse-engineering leak) and parked at $BIN_PATH, which we then
    # mount root:root 0111 into every agent at /opt/pbench/executable.
    PROGRAMBENCH_DOCKER_ORG="$DOCKER_ORG" \
        python3 tools/pbench_submission.py seed --image "$CLEANROOM_IMG" \
        --into "$seed_dir" --bin-out "$BIN_PATH" \
        || die "seed extraction failed"
    if [ -f "$BIN_PATH" ]; then
        # root:root 0111 — agents (uid 10000) can EXECUTE but never READ the bytes.
        sudo chown 0:0 "$BIN_PATH"
        sudo chmod 0111 "$BIN_PATH"
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
declare -A MM_DM_CACHE=()
mm_dm_channel() {
    local user="$1"
    if [ -n "${MM_DM_CACHE[$user]:-}" ]; then
        printf '%s' "${MM_DM_CACHE[$user]}"; return 0
    fi
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
    MM_DM_CACHE[$user]="$ch"
    printf '%s' "$ch"
}

# Open (or reuse) a private task channel pulling in director + auditor, returns
# the channel_id on stdout. Posting a message that @mentions both wakes them.
TASK_CHANNEL_ID=""
# The mattermost MCP takes only a URL + token — upstream exposes no default
# team — so every team-scoped tool (post_message, search_messages,
# list_my_channels) needs ids the agent must otherwise discover. Agents that
# fail that discovery invent 26-char ids, and mattermost answers 403 for a
# team you are not in. 47 of 80 workers in sweep 6.3 read that as a lockout and
# went silent, which the lead then misread as "worker stuck". We know both ids
# here, so we hand them over instead. See tests/pbench/test_mm_ids.sh.
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
    # Ensure admin + director + auditor + workers + reviewer are team members
    # (needed to add them to the channel and for the @mention to actually
    # notify them). bootstrap.sh:675 already does this on a fresh install; we
    # repeat here so a re-run after a data wipe with a stale .bootstrap-done
    # mark still ends up with a fully populated team.
    local admin_id; admin_id=$(mm_user_id "$MATTERMOST_ADMIN_USER") || true
    # Derive the full agent list from PBENCH_TEAMS / PBENCH_WORKERS_PER_TEAM so
    # multi-team topologies (org-pbench-4team, org-pbench-method-2ab, ...) pull
    # every lead/worker/reviewer into the MM team + channel. Falls back to the
    # historical 1team list when the env vars are unset.
    local n_teams n_workers
    n_teams="$(grep -E '^PBENCH_TEAMS=' "$ENV_FILE" 2>/dev/null | cut -d= -f2)"
    n_workers="$(grep -E '^PBENCH_WORKERS_PER_TEAM=' "$ENV_FILE" 2>/dev/null | cut -d= -f2)"
    n_teams="${n_teams:-1}"
    n_workers="${n_workers:-4}"
    local extra_team_members=()
    local ti wi
    for ti in $(seq 1 "$n_teams"); do
        extra_team_members+=("${ORG_NAME}-team${ti}-lead")
        extra_team_members+=("${ORG_NAME}-team${ti}-reviewer")
        for wi in $(seq 1 "$n_workers"); do
            extra_team_members+=("${ORG_NAME}-team${ti}-worker${wi}")
        done
    done
    local m agent
    for m in "$admin_id" "$(mm_user_id "$DIRECTOR_AGENT")" "$(mm_user_id "$AUDITOR_AGENT")"; do
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
    # Pull director + auditor + workers + reviewer into the channel so the
    # @mention notifies them and the lead can DM without needing MCP
    # channel-admin tools (mattermost__create_channel /join_channel
    # /add_user_to_channel are on the deny list — see
    # templates-claude-1team/settings.json.tmpl:50-53).
    local uid code
    for agent in "$DIRECTOR_AGENT" "$AUDITOR_AGENT" "${extra_team_members[@]}"; do
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

# The canonical task brief reused across gitea issue + MM channel + reminders.
task_brief() {
    cat <<EOF
ProgramBench task: $TASK

You are given a reference program as a compiled binary at \`/opt/pbench/executable\`
(you can RUN it to observe behavior, but you CANNOT read its bytes) plus its
documentation in this repo. Rebuild a complete codebase that reproduces the
program's behavior.

Requirements:
- Put a working \`compile.sh\` at the repo ROOT that builds \`./executable\`.
- Commit all source to the \`$REPO\` repo's default branch.
- You have NO internet access. Do not attempt to fetch the original source.
- This is FULLY autonomous: there is NO human to ask. Define requirements,
  split the work, decide, and ship by yourselves. Do not wait for instructions.

First step: run \`/opt/pbench/executable\` and observe.

Mattermost coordination: your team is \`$MM_TEAM_ID\` and the shared task
channel \`pbench-task\` is \`$TASK_CHANNEL_ID\`. Pass those ids straight to the
mattermost tools — do not guess them and do not go looking them up. If a
mattermost call returns 403 or 404 you have used a wrong id, not lost access:
you are a member of that team and that channel.
EOF
}

# Deadline reminders, posted to the shared task channel.
#
# The brief deliberately does NOT state the total budget. A team told it has
# six hours plans for six hours: on sweep_6.2 the failures cluster at the end
# rather than being spread through it — gdal filed its last sub-issue at +95m
# and spent the remaining 4h25m with the lead coding alone, pandoc's four
# writer PRs all opened after +109m and none merged, ditaa never ran compile.sh
# in a clean tree at all.
#
# What the agents actually need is not a number to pace against but a signal at
# the two points where the right action changes. director_lead/workflow.md
# already describes both ("Stage 3: convergence (last 45 minutes)"), but there
# is no clock in the container and no external trigger, so the team cannot tell
# when it has arrived. The runner tells it.
deadline_reminder_loop() {
    local secs="$1"
    local t45=$(( secs - 45 * 60 ))
    local t5=$((  secs - 5  * 60 ))
    if [ "$t45" -gt 0 ]; then
        sleep "$t45"
        mm_post "$TASK_CHANNEL_ID" \
"@all **45 minutes left.** Stop dispatching new features. From here the only \
goal is that root \`compile.sh\` builds \`./executable\` and that everything \
already written is merged to the default branch. Land the open PRs; work that \
is not merged does not count. If a PR cannot be merged, say so and move on." \
            || log "WARN: T-45m reminder failed"
        log "posted T-45m reminder"
    fi
    local rest=$(( t5 - (t45 > 0 ? t45 : 0) ))
    if [ "$rest" -gt 0 ]; then
        sleep "$rest"
        mm_post "$TASK_CHANNEL_ID" \
"@all **5 minutes left.** Merge anything that is ready right now, then stop. \
Confirm root \`bash compile.sh && ./executable\` still works on the default \
branch and post the final state." \
            || log "WARN: T-5m reminder failed"
        log "posted T-5m reminder"
    fi
}

# --- 3. drive: seed initial commit + wake the director (MM + gitea) ---------
push_seed_and_drive() {
    local seed_dir; seed_dir="$(cat "$OUT_DIR/$TASK/.seed_path")"
    local repo_url="http://${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}@localhost:${EDGE_PORT}/${ORG_NAME}/${REPO}.git"
    local push_tmp="$OUT_DIR/$TASK/_push"
    rm -rf "$push_tmp"
    log "cloning team repo to seed initial commit"
    git clone --quiet "$repo_url" "$push_tmp" || { log "WARN: clone failed; skipping seed push"; return 0; }
    cp -a "$seed_dir/." "$push_tmp/" 2>/dev/null || true
    ( cd "$push_tmp" \
        && git config user.email "chairman@${ORG_NAME}.local" \
        && git config user.name "$GITEA_ADMIN_USER" \
        && git add -A \
        && git commit -qm "pbench: seed cleanroom workspace ($TASK)" \
        && git push -q origin HEAD ) \
        || log "WARN: seed push failed (repo may already be seeded)"

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

    # (a) Gitea issue — assign the director AND @mention so the per-user
    #     notification fires (an admin-opened, unassigned issue notifies nobody
    #     because bootstrap unwatches every agent from the repo).
    log "opening task issue (assignee + @${DIRECTOR_AGENT})"
    local issue_body="@${DIRECTOR_AGENT} ${brief}"
    curl -fsS -u "${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}" \
        -H 'Content-Type: application/json' \
        -d "$(python3 -c 'import json,sys; print(json.dumps({"title": f"[pbench] {sys.argv[1]}", "body": sys.argv[2], "assignees": [sys.argv[3]]}))' "$TASK" "$issue_body" "$DIRECTOR_AGENT")" \
        "http://localhost:${EDGE_PORT}/api/v1/repos/${ORG_NAME}/${REPO}/issues" \
        >/dev/null 2>&1 \
        && log "task issue opened (assignee=$DIRECTOR_AGENT)" \
        || log "WARN: could not open task issue"

    # (b) Mattermost task channel pulling in director + auditor — the reliable
    #     wakeup path. @mention both so the websocket notification fires.
    # The channel was already created above (the brief needs its id), and
    # TASK_CHANNEL_ID / MM_TEAM_ID are set in THIS shell there — which also
    # gives the background worker_watchdog_loop, forked from this shell at
    # main(), a non-empty TASK_CHANNEL_ID to guard on.
    if [ -n "$ch" ]; then
        # In 1team, DIRECTOR_AGENT == AUDITOR_AGENT (both roles merged onto
        # team1-lead); mentioning the same handle twice adds nothing and looks
        # like an accident.
        local mentions="@${DIRECTOR_AGENT}"
        if [ "$AUDITOR_AGENT" != "$DIRECTOR_AGENT" ]; then
            mentions="$mentions @${AUDITOR_AGENT}"
        fi
        mm_post "$ch" "${mentions} New task. ${brief}

@${DIRECTOR_AGENT} You are the initiator: immediately break down the work, dispatch sub-issues, actively push forward, do not wait for any human input." \
            && log "task posted to MM channel pbench-task (mentions=$mentions)" \
            || log "WARN: MM channel post failed"
    else
        # Fallback to a direct DM to the director if channel creation failed.
        local me dir dm
        me="$(mm_user_id "$MATTERMOST_ADMIN_USER")" || me=""
        dir="$(mm_user_id "$DIRECTOR_AGENT")" || dir=""
        if [ -n "$me" ] && [ -n "$dir" ]; then
            dm=$(curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" -H 'Content-Type: application/json' \
                -X POST -d "[\"$me\",\"$dir\"]" "${MM_BASE}/api/v4/channels/direct" | jq -r '.id // empty')
            [ -n "$dm" ] && mm_post "$dm" "$brief" \
                && log "task delivered via MM DM to $DIRECTOR_AGENT" \
                || log "WARN: MM DM to director failed"
        fi
    fi
}

# --- worker idle watchdog: per-agent activity check every 60s ---------------
# Each agent's turns/tool-calls append to a jsonl trail under
# ${DATA_ROOT}/${PROFILE}/hermes/<agent>/home/.claude/projects/-work/*.jsonl
# (AGENT_KIND=claude) or .../home/.copilot/session-state/<id>/events.jsonl
# (AGENT_KIND=copilot, which every pbench profile uses),
# so the newest jsonl mtime under an agent = its last activity time. When a
# worker crosses WORKER_IDLE_THRESHOLD (default 600s = 10m) with no new
# events, we DM the director-and-lead (the merged team1-lead role in 1team;
# separate director + team-lead DMs in any multi-team profile that reuses this
# script) asking to feed that specific worker fresh work. Falls back to the
# shared task channel if DMs can't be opened. Per-worker rate limit
# (WORKER_IDLE_REPEAT default 600s = 10m) prevents spam on stuck workers.
WORKER_IDLE_THRESHOLD="${WORKER_IDLE_THRESHOLD:-600}"
WORKER_IDLE_REPEAT="${WORKER_IDLE_REPEAT:-600}"
WORKER_CHECK_INTERVAL="${WORKER_CHECK_INTERVAL:-60}"
worker_watchdog_loop() {
    local total_secs="$1"
    local hermes_root="${DATA_ROOT}/${PROFILE}/hermes"
    local dedup_dir="${OUT_DIR}/${TASK}/_watchdog"
    mkdir -p "$dedup_dir"
    local start now elapsed
    start=$(date +%s)
    while :; do
        now=$(date +%s)
        elapsed=$((now - start))
        [ "$elapsed" -ge "$total_secs" ] && break
        if [ ! -d "$hermes_root" ]; then sleep "$WORKER_CHECK_INTERVAL"; continue; fi
        local agent_dir worker_name team_prefix lead_name last_mtime idle last_ping
        for agent_dir in "$hermes_root"/${ORG_NAME}-*worker*; do
            [ -d "$agent_dir" ] || continue
            worker_name="$(basename "$agent_dir")"
            team_prefix=""
            if [[ "$worker_name" =~ -(team[0-9]+)- ]]; then
                team_prefix="${BASH_REMATCH[1]}"
            fi
            lead_name=""
            [ -n "$team_prefix" ] && lead_name="${ORG_NAME}-${team_prefix}-lead"
            # Agent turn log. AGENT_KIND=claude writes home/.claude/projects/*.jsonl;
            # AGENT_KIND=copilot writes home/.copilot/session-state/<id>/events.jsonl.
            # This only looked at the claude path, and every pbench profile runs
            # copilot -- so `continue` fired for every worker on every tick and this
            # watchdog has never nudged anyone. Verified across sweeps 6.2/6.5/6.6:
            # 0 .claude dirs, 100+ .copilot dirs, and not one `watchdog:` log line.
            # Agent may not have been prompted yet; find exits 1 then, which under
            # pipefail+set -e would kill the subshell -- hence `|| true`.
            local claude_dir="$agent_dir/home/.claude/projects"
            local copilot_dir="$agent_dir/home/.copilot/session-state"
            local -a scan=()
            [ -d "$claude_dir" ] && scan+=("$claude_dir")
            [ -d "$copilot_dir" ] && scan+=("$copilot_dir")
            [ ${#scan[@]} -gt 0 ] || continue
            last_mtime=$(find "${scan[@]}" -type f -name '*.jsonl' \
                -printf '%T@\n' 2>/dev/null | sort -rn | head -1 | cut -d. -f1 || true)
            [ -n "$last_mtime" ] || continue
            idle=$((now - last_mtime))
            [ "$idle" -ge "$WORKER_IDLE_THRESHOLD" ] || continue
            last_ping=$(cat "$dedup_dir/$worker_name" 2>/dev/null || echo 0)
            [ $((now - last_ping)) -ge "$WORKER_IDLE_REPEAT" ] || continue

            local idle_min=$((idle/60))
            local dir_msg="One worker in \`${team_prefix:-unknown-team}\` has been idle for ${idle_min} minutes. Push that team: tell its lead to hand out a concrete new work item now. There is always new work — do not be bounded by the previous plan's scope: pick up /opt/pbench/executable, run it against untried inputs, and derive fresh tasks from what interaction with it reveals."
            local lead_msg="Your worker \`${worker_name}\` has been idle for ${idle_min} minutes. Assign it a concrete new work item now. There is always new work — pick up /opt/pbench/executable, run it against untried inputs, look for behaviors nobody has covered yet, and derive the next task from what interaction with the executable reveals."

            local pinged=0
            if [ -n "$lead_name" ] && [ "$lead_name" = "$DIRECTOR_AGENT" ]; then
                # 1team merged role: one recipient serves both audiences. Send
                # a single message combining director-scope (push the team) and
                # lead-scope (specific worker) so it's obvious what to do.
                local merged_msg="Worker \`${worker_name}\` in \`${team_prefix:-unknown-team}\` has been idle for ${idle_min} minutes. As director+lead, assign it a concrete new work item now. There is always new work — do not be bounded by the previous plan's scope: pick up /opt/pbench/executable, run it against untried inputs, look for behaviors nobody has covered yet, and derive the next task from what interaction with the executable reveals."
                local dm
                dm="$(mm_dm_channel "$DIRECTOR_AGENT" 2>/dev/null)" || dm=""
                if [ -n "$dm" ]; then
                    mm_post "$dm" "$merged_msg" \
                        && { log "watchdog: DM $DIRECTOR_AGENT (merged director/lead) re ${worker_name} idle=${idle}s"; pinged=1; } \
                        || log "WARN: watchdog DM to $DIRECTOR_AGENT failed"
                fi
            else
                local director_dm="" lead_dm=""
                director_dm="$(mm_dm_channel "$DIRECTOR_AGENT" 2>/dev/null)" || director_dm=""
                [ -n "$lead_name" ] && lead_dm="$(mm_dm_channel "$lead_name" 2>/dev/null)" || lead_dm=""
                if [ -n "$director_dm" ]; then
                    mm_post "$director_dm" "$dir_msg" \
                        && { log "watchdog: DM director re ${team_prefix:-?}/${worker_name} idle=${idle}s"; pinged=1; } \
                        || log "WARN: watchdog DM to $DIRECTOR_AGENT failed"
                fi
                if [ -n "$lead_dm" ]; then
                    mm_post "$lead_dm" "$lead_msg" \
                        && { log "watchdog: DM $lead_name re ${worker_name} idle=${idle}s"; pinged=1; } \
                        || log "WARN: watchdog DM to $lead_name failed"
                fi
            fi
            if [ "$pinged" = "0" ] && [ -n "$TASK_CHANNEL_ID" ]; then
                # DMs failed — fall back to the shared channel with mentions
                local mentions="@${DIRECTOR_AGENT}"
                [ -n "$lead_name" ] && [ "$lead_name" != "$DIRECTOR_AGENT" ] \
                    && mentions="$mentions @${lead_name}"
                mm_post "$TASK_CHANNEL_ID" \
"${mentions} worker \`${worker_name}\` has been idle for ${idle_min} minutes. Assign it a concrete new work item now." \
                    && log "watchdog: channel-fallback ping for ${worker_name} (idle ${idle}s)" \
                    || log "WARN: watchdog channel fallback failed for ${worker_name}"
            fi
            echo "$now" > "$dedup_dir/$worker_name"
        done
        sleep "$WORKER_CHECK_INTERVAL"
    done
}

main() {
    log "TASK=$TASK HOURS=$HOURS OUT_DIR=$OUT_DIR PROFILE=$PROFILE"
    trap teardown EXIT

    seed_repo
    # DeLM baseline path: pre-populate the shared /work bind-mount with the
    # cleanroom seed contents so planner + workers start with the same docs +
    # a stub compile.sh in a single writable dir. Chown to uid 10000 (the
    # non-root ACP child) so agents can write.
    if [ -n "${WORK_HOST_PATH:-}" ]; then
        log "seeding shared /work at $WORK_HOST_PATH (DeLM baseline path)"
        sudo mkdir -p "$WORK_HOST_PATH"
        # $OUT_DIR/$TASK/_seed contains the cleanroom /workspace contents minus the reference binary
        sudo cp -a "$OUT_DIR/$TASK/_seed/." "$WORK_HOST_PATH/" 2>/dev/null || true
        # Stage a WORKING default compile.sh if the seed has none. It must
        # actually build, not just fail loudly: the first DeLM smoke had a
        # planner produce 42 correct source files and still score 0 because it
        # never replaced an `exit 1` placeholder. A wildcard build over src/
        # means the team's code compiles even when nobody finalizes, and the
        # planner is still free to overwrite this with something better.
        if [ ! -f "$WORK_HOST_PATH/compile.sh" ]; then
            sudo tee "$WORK_HOST_PATH/compile.sh" >/dev/null <<'DEFAULT_COMPILE'
#!/bin/sh
# Default build: compile every C source under src/ into ./executable.
# Staged by the harness so a team that writes sources but never finalizes
# still produces a binary. Overwrite this if your project needs more.
set -e
cd "$(dirname "$0")"
if [ -f Makefile ]; then
    make
    exit $?
fi
SRCS=$(find src -name '*.c' 2>/dev/null | sort)
if [ -z "$SRCS" ]; then
    echo "compile.sh: no sources found under src/" >&2
    exit 1
fi
${CC:-cc} -O2 -Isrc -o executable $SRCS -lm ${LDLIBS:-}
DEFAULT_COMPILE
            sudo chmod +x "$WORK_HOST_PATH/compile.sh"
        fi
        sudo mkdir -p "$WORK_HOST_PATH/src"
        sudo chown -R 10000:10000 "$WORK_HOST_PATH"
    fi
    # Which agent image this run uses. Two supported shapes:
    #
    #   AGENT_IMAGE unset — the historical v48 reproduction path. Agents run in
    #     omcgitea-hermes-agent:local, loaded from ~/omcgitea-hermes-agent.v48.tar
    #     (see MEMORY: pbench-cleanroom-base). Refuse to start if it is not
    #     already loaded; silently rebuilding here would drift from v48.
    #
    #   AGENT_IMAGE set — the per-task path (Dockerfile.pertask). The image is
    #     built FROM this task's own cleanroom, so the agent's toolchain and
    #     crate versions are the grader's by construction. Compose reads
    #     AGENT_IMAGE from .env.<profile>; it is resolved from that same file at
    #     the top of this script, so this check now sees the image the run will
    #     really use and a typo fails in 2 seconds rather than after `make up`
    #     has provisioned a stack.
    local agent_img="${AGENT_IMAGE:-omcgitea-hermes-agent:local}"
    log "agent image: $agent_img"
    sudo docker image inspect "$agent_img" >/dev/null 2>&1 \
        || die "agent image missing: $agent_img (for the v48 path: docker load -i ~/omcgitea-hermes-agent.v48.tar; for per-task: scripts/pbench_build_pertask_images.sh)"
    log "bringing up $PROFILE stack"
    # R3 fix: serialize `make up` across sibling chains. When 4 parallel
    # chains rotate to a new task within seconds of each other (common at
    # kickoff or when tasks happen to finish clustered), simultaneous
    # `docker compose up -d` calls race the docker daemon and mysql's
    # `depends_on: service_healthy` can time out on the loser (see R1).
    # flock lets only one `make up` progress at a time; others block on the
    # lock and start their bringup once the daemon is quiet again. The
    # 900s timeout is a hard ceiling — if we can't grab the lock in 15 min
    # something else is very wrong.
    local up_lock="/tmp/pbench-make-up.lock"
    exec 9>"$up_lock"
    flock -w 900 9 || die "could not acquire $up_lock in 15min"
    log "acquired make-up lock (pid $$)"
    make up PROFILE="$PROFILE" || die "make up failed"
    exec 9>&-  # release the lock — bringup is done, other chains may proceed

    push_seed_and_drive

    local secs
    secs="$(python3 -c "print(int(float('$HOURS')*3600))")"
    log "agents working for ${HOURS}h (${secs}s); waiting…"
    # Per-worker idle watchdog runs in the background — targets the specific
    # worker that has stopped emitting jsonl events and DMs the merged
    # director/lead (single recipient in 1team) to feed it new work drawn
    # from executable interaction. Falls back to the shared task channel if
    # DMs can't be opened.
    worker_watchdog_loop "$secs" &
    local watchdog_pid=$!
    deadline_reminder_loop "$secs" &
    local reminder_pid=$!
    sleep "$secs"
    kill "$watchdog_pid" 2>/dev/null || true
    kill "$reminder_pid" 2>/dev/null || true
    log "wall-clock budget elapsed; exporting + evaluating"

    # teardown (trap) exports the submission and stops the stack. Run eval
    # AFTER export, so do it here before exit by exporting explicitly first.
    trap - EXIT
    export_submission
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
      # explicitly. In 6.10 a single `executable` reached 474 GB of 503 GB and took the machine
      # down; a build that forks a runaway compiler is the same shape.
      # See docker/pbench.slice and v2docs/INCIDENT_6.10_MEMORY.md.
      local in_slice=()
      if command -v systemd-run >/dev/null 2>&1 && systemctl cat pbench.slice >/dev/null 2>&1; then
          in_slice=(systemd-run --scope --quiet --slice=pbench.slice --collect)
          log "eval runs inside pbench.slice (aggregate ceiling)"
      else
          log "WARN: pbench.slice not installed -- eval runs UNCAPPED (see docker/pbench.slice)"
      fi
    if command -v uv >/dev/null 2>&1; then
        ( cd "$PB_REPO" && PROGRAMBENCH_DOCKER_EXECUTABLE="$PROGRAMBENCH_DOCKER_EXECUTABLE" TMPDIR="$pbench_tmp" \
            "${in_slice[@]}" uv run programbench eval "$OUT_DIR" --filter "$TASK" ) \
            || log "WARN: programbench eval returned non-zero"
    elif command -v programbench >/dev/null 2>&1; then
        "${in_slice[@]}" programbench eval "$OUT_DIR" --filter "$TASK" || log "WARN: eval non-zero"
    else
        die "neither 'uv' nor 'programbench' on PATH — cannot evaluate (task #4 eval side must be installed)"
    fi

    local eval_json="$OUT_DIR/$TASK/$TASK.eval.json"
    [ -f "$eval_json" ] && log "eval.json written: $eval_json" \
        || log "WARN: eval.json not found at $eval_json"
}

main "$@"
