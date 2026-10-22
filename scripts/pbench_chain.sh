#!/usr/bin/env bash
# Sequence inference, verified trajectory copies, profile cleanup and evaluation.
# PHASE separates run/eval so the launcher can overlap evaluation with later tasks.

set -u
PROFILE="${PROFILE:?PROFILE=pbench-<mode>-<task> required}"
: "${TASKS_ENV:?TASKS_ENV (comma-separated task ids) required}"
: "${SUFFIX:?SUFFIX (<mode>.<RUN_ID>) required}"
: "${TRAJ_ROOT:?TRAJ_ROOT required}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="${LOG:-$ROOT/out/chain-${PROFILE}.log}"
SUMMARY="${SUMMARY:-$ROOT/out/chain-${PROFILE}.summary}"
OUT_ROOT="${OUT_ROOT:-$ROOT/out/$PROFILE}"
PB_REPO="${PROGRAMBENCH_REPO:-$HOME/programbench}"
DOCKER_SUDO_SHIM="$ROOT/scripts/pbench-docker-sudo.sh"
ENV_FILE="$ROOT/.env.$PROFILE"
if [ -z "${DATA_ROOT:-}" ] && [ -f "$ENV_FILE" ]; then
    DATA_ROOT="$(awk -F= '$1=="DATA_ROOT"{sub(/\r$/,"",$2); print $2; exit}' "$ENV_FILE")"
fi
DATA_ROOT="${DATA_ROOT:-$ROOT/.claude-team-data}"
DATA_DIR="$DATA_ROOT/$PROFILE"

mkdir -p "$TRAJ_ROOT" "$ROOT/out"
touch "$SUMMARY"

log() { echo "[chain $(date -u +%H:%M:%S)] $*" | tee -a "$LOG"; }

port_is_free() {
    python3 - "$1" <<'PY' >/dev/null 2>&1
import socket, sys
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(("0.0.0.0", int(sys.argv[1])))
except OSError:
    sys.exit(1)
finally:
    s.close()
PY
}

pick_free_port() {
    python3 - <<'PY'
import socket
s = socket.socket()
s.bind(("0.0.0.0", 0))
print(s.getsockname()[1])
s.close()
PY
}

ENV_BACKUP=""
restore_env() {
    if [ -n "$ENV_BACKUP" ] && [ -f "$ENV_BACKUP" ]; then
        sudo mv "$ENV_BACKUP" "$ENV_FILE" \
            && log "restored $ENV_FILE from $ENV_BACKUP" \
            || log "WARN: failed to restore $ENV_FILE from $ENV_BACKUP"
        ENV_BACKUP=""
    fi
}

allocate_ports() {
    # Temporarily rewrite occupied profile ports and restore the original file on exit.
    if [ ! -f "$ENV_FILE" ]; then
        log "FATAL: $ENV_FILE missing — cannot resolve ports for profile $PROFILE"
        return 1
    fi
    local orig_http orig_mm
    orig_http=$(sudo grep -E '^EDGE_HTTP_PORT=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
    orig_mm=$(  sudo grep -E '^EDGE_MM_PORT='   "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
    EDGE_HTTP_PORT="$orig_http"
    EDGE_MM_PORT="$orig_mm"
    local changed=0
    if [ -z "$EDGE_HTTP_PORT" ] || ! port_is_free "$EDGE_HTTP_PORT"; then
        local new; new=$(pick_free_port)
        log "EDGE_HTTP_PORT ${EDGE_HTTP_PORT:-unset} unavailable → reallocating to $new"
        EDGE_HTTP_PORT="$new"; changed=1
    fi
    if [ -z "$EDGE_MM_PORT" ] || [ "$EDGE_MM_PORT" = "$EDGE_HTTP_PORT" ] || ! port_is_free "$EDGE_MM_PORT"; then
        local new; new=$(pick_free_port)
        while [ "$new" = "$EDGE_HTTP_PORT" ]; do new=$(pick_free_port); done
        log "EDGE_MM_PORT ${EDGE_MM_PORT:-unset} unavailable → reallocating to $new"
        EDGE_MM_PORT="$new"; changed=1
    fi
    if [ $changed -eq 1 ]; then
        ENV_BACKUP="$ENV_FILE.chain-orig"
        if [ -f "$ENV_BACKUP" ]; then
            log "WARN: $ENV_BACKUP already exists (leftover from crashed prior chain); restoring it before re-backing-up"
            sudo mv "$ENV_BACKUP" "$ENV_FILE" \
                || { log "FATAL: cannot restore stale $ENV_BACKUP"; return 1; }
        fi
        sudo cp -a "$ENV_FILE" "$ENV_BACKUP" || { log "FATAL: cannot back up $ENV_FILE"; return 1; }
        sudo sed -i -E "s|^EDGE_HTTP_PORT=.*|EDGE_HTTP_PORT=$EDGE_HTTP_PORT|" "$ENV_FILE"
        sudo sed -i -E "s|^EDGE_MM_PORT=.*|EDGE_MM_PORT=$EDGE_MM_PORT|"       "$ENV_FILE"
        trap 'restore_env' EXIT
        log "rewrote $ENV_FILE: EDGE_HTTP_PORT=$EDGE_HTTP_PORT EDGE_MM_PORT=$EDGE_MM_PORT (orig at $ENV_BACKUP)"
    else
        log "ports free: EDGE_HTTP_PORT=$EDGE_HTTP_PORT EDGE_MM_PORT=$EDGE_MM_PORT"
    fi
    export EDGE_HTTP_PORT EDGE_MM_PORT
}

wait_for_docker() {
    local i=0
    while ! sudo docker info >/dev/null 2>&1; do
        i=$((i+1))
        if [ $i -gt 60 ]; then
            log "FATAL: docker daemon did not become ready in 5 min"
            return 1
        fi
        sleep 5
    done
    log "docker daemon ready"
}

salvage_interrupted() {
    # An incomplete worker archive must be recovered before any automatic cleanup.
    if [ ! -d "$DATA_DIR" ]; then return 0; fi
    sudo -n python3 "$ROOT/agent/archive.py" check "$DATA_DIR" || return 1
    local current
    current=$(ls "$OUT_ROOT" 2>/dev/null | grep '__' | grep -vE '\.archived$|\.aborted$|\.interrupted$' | head -1)
    if [ -z "$current" ]; then
        log "no in-flight task dir; wiping stale DATA_DIR"
        (cd "$ROOT" && make clean PROFILE="$PROFILE") >>"$LOG" 2>&1 || true
        return 0
    fi
    log "salvaging interrupted task: $current"
    local retry=0
    while [ $retry -lt 36 ]; do
        if curl -fsS "http://localhost:${EDGE_HTTP_PORT}/api/v1/version" >/dev/null 2>&1; then break; fi
        retry=$((retry+1)); sleep 5
    done
    if ! curl -fsS "http://localhost:${EDGE_HTTP_PORT}/api/v1/version" >/dev/null 2>&1; then
        log "gitea not reachable — starting stack for salvage"
        (cd "$ROOT" && make up PROFILE="$PROFILE" SERVICES="mysql gitea nginx-edge") >>"$LOG" 2>&1 || log "WARN: make up failed during salvage"
        sleep 30
    fi
    sudo rm -f "$OUT_ROOT/$current/submission.tar.gz" "$OUT_ROOT/$current/export.log"
    local team_url="http://chairman:$(sudo grep -E '^GITEA_ADMIN_PASSWORD=' "$ENV_FILE" 2>/dev/null | cut -d= -f2)@localhost:${EDGE_HTTP_PORT}/pbench/main.git"
    if python3 "$ROOT/tools/pbench_submission.py" export \
            --from-gitea "$team_url" --task "$current" --out-dir "$OUT_ROOT" \
            >>"$OUT_ROOT/$current/export.log" 2>&1; then
        log "salvage: submission re-exported"
    else
        log "WARN: salvage export failed, submission.tar.gz will be empty"
        echo "salvage export failed" > "$OUT_ROOT/$current/export.log" || true
    fi
    snapshot_run_and_clean "$current" || return 1
    log "salvage complete for $current (eval deferred to Phase 2)"
}

snapshot_run_and_clean() {
    # Preserve both service data and task output, then verify source and copied archives.
    local task="$1"
    local dst="$TRAJ_ROOT/${task}.${SUFFIX}"
    log "snapshotting $task -> $dst"
    sudo mkdir -p "$dst" || return 1
    if [ -d "$DATA_DIR" ]; then
        sudo cp -a "$DATA_DIR/." "$dst/data-root/" \
            && log "copied DATA_ROOT -> $dst/data-root/" \
            || { log "ERROR: DATA_ROOT copy failed; refusing cleanup"; return 1; }
    else
        log "WARN: $DATA_DIR missing, nothing to snapshot from data-root"
    fi
    if [ -d "$OUT_ROOT/$task" ]; then
        sudo cp -a "$OUT_ROOT/$task/." "$dst/out/" \
            && log "copied out/$task -> $dst/out/" \
            || { log "ERROR: out/$task copy failed; refusing cleanup"; return 1; }
    fi
    sudo chown -R "$(id -u):$(id -g)" "$dst" 2>/dev/null || true
    sudo -n python3 "$ROOT/agent/archive.py" check "$DATA_DIR" || return 1
    sudo -n python3 "$ROOT/agent/archive.py" check "$dst/data-root" || return 1
    log "make clean PROFILE=$PROFILE (out/$task preserved for Phase 2 eval)"
    (cd "$ROOT" && make clean PROFILE="$PROFILE") >>"$LOG" 2>&1 \
        || log "WARN: make clean returned non-zero"
}

eval_and_archive() {
    local task="$1"
    local task_out="$OUT_ROOT/$task"
    local dst="$TRAJ_ROOT/${task}.${SUFFIX}"
    if [ ! -d "$task_out" ]; then
        log "SKIP eval $task: no $task_out (already archived?)"
        return 0
    fi
    if [ ! -f "$task_out/submission.tar.gz" ]; then
        log "WARN eval $task: no submission.tar.gz — running eval anyway"
    fi
    log "eval: $task"
    local pbench_tmp="$task_out/_evaltmp"
    rm -rf "$pbench_tmp"; mkdir -p "$pbench_tmp"
    if command -v uv >/dev/null 2>&1; then
        ( cd "$PB_REPO" && \
          PROGRAMBENCH_DOCKER_EXECUTABLE="$DOCKER_SUDO_SHIM" \
          TMPDIR="$pbench_tmp" \
          PATH="$HOME/.local/bin:$PATH" \
          uv run programbench eval "$OUT_ROOT" --filter "$task" --image-tag task_cleanroom_v6 ) >>"$LOG" 2>&1 \
            || log "WARN: eval $task returned non-zero"
    else
        log "FATAL eval $task: uv not on PATH"
        return 1
    fi
    report_score "$task"
    local eval_json="$task_out/$task.eval.json"
    if [ -f "$eval_json" ] && [ -d "$dst/out" ]; then
        sudo cp -a "$eval_json" "$dst/out/" \
            && sudo chown "$(id -u):$(id -g)" "$dst/out/$task.eval.json" 2>/dev/null || true
        log "eval.json copied into trajectory: $dst/out/"
    fi
    sudo mv "$task_out" "${task_out}.${SUFFIX}.archived" 2>/dev/null || true
}

report_score() {
    # This diagnostic counts raw attempt rows; use tools/pbench_score_report.py
    # for the official canonical-kept score when comparing experiments.
    local task="$1"
    local eval_json="$OUT_ROOT/$task/$task.eval.json"
    if [ -f "$eval_json" ]; then
        python3 - "$eval_json" "$task" <<'PY' | tee -a "$LOG" "$SUMMARY"
import json,sys,collections
p=sys.argv[1]; task=sys.argv[2]
d=json.load(open(p))
tr=d.get("test_results",[])
c=collections.Counter(t.get("status","unknown") for t in tr)
passed=c.get("passed",0); total=len(tr)
pct=(100*passed/total) if total else 0
print(f"SCORE {task}: {pct:.2f}% ({passed}/{total}) breakdown={dict(c)}")
PY
    else
        log "SCORE $task: NO eval.json at $eval_json"
        echo "SCORE $task: NO eval.json" >> "$SUMMARY"
    fi
}

launch_task() {
    # Keep inference alive across terminal disconnects and record its exit separately.
    local task="$1"
    local hours="${HOURS:-6}"
    log "launching $task (${hours}h, SKIP_EVAL=1)"
    cd "$ROOT" || { log "FATAL: cd $ROOT failed"; return 1; }
    local run_log="$ROOT/out/pbench-${task}-${SUFFIX}.log"
    local rcfile="$ROOT/out/pbench-${task}-${SUFFIX}.rc"
    rm -f "$rcfile"
    { nohup env \
        TASK="$task" \
        HOURS="$hours" \
        PROFILE="$PROFILE" \
        OUT_DIR="$OUT_ROOT" \
        PROGRAMBENCH_REPO="$PB_REPO" \
        PATH="$HOME/.local/bin:$PATH" \
        SKIP_EVAL=1 \
        "$ROOT/scripts/pbench_run.sh" \
        > "$run_log" 2>&1
      echo $? > "$rcfile"
    } &
    local pid=$!
    disown
    log "launched $task pid=$pid"
    while kill -0 "$pid" 2>/dev/null; do sleep 60; done
    local rc; rc="$(cat "$rcfile" 2>/dev/null || true)"; rc="${rc:-unknown}"
    log "$task pid=$pid exited rc=$rc"
    if [ "$rc" != "0" ]; then
        mkdir -p "$OUT_ROOT/$task" 2>/dev/null || true
        echo "run failed rc=$rc at $(date -u +%FT%TZ); see out/pbench-${task}-${SUFFIX}.log" \
            > "$OUT_ROOT/$task/RUN_FAILED" 2>/dev/null || true
        log "WARN: $task RUN FAILED (rc=$rc) — marked RUN_FAILED; any eval of it is meaningless"
    fi
    return 0
}

IFS=',' read -r -a TASKS <<< "$TASKS_ENV"

log "=== chain start (${#TASKS[@]} tasks x ${HOURS:-6}h; profile=$PROFILE; suffix=$SUFFIX; traj=$TRAJ_ROOT) ==="

PHASE="${PHASE:-both}"

wait_for_docker || exit 1
if [ "$PHASE" != "eval" ]; then
    allocate_ports || exit 1
    salvage_interrupted
fi

if [ "$PHASE" = "both" ] || [ "$PHASE" = "run" ]; then
log "=== Phase 1: RUN (SKIP_EVAL=1) ==="
for t in "${TASKS[@]}"; do
    if [ -d "$OUT_ROOT/${t}.${SUFFIX}.archived" ]; then
        log "skipping $t (already archived by this launch)"
        continue
    fi
    if [ -d "$OUT_ROOT/$t" ] && [ -f "$OUT_ROOT/$t/submission.tar.gz" ]; then
        log "skipping run for $t (submission already present from prior salvage)"
        continue
    fi
    launch_task "$t"
    snapshot_run_and_clean "$t"
done
log "=== Phase 1 complete ==="
fi

if [ "$PHASE" = "both" ] || [ "$PHASE" = "eval" ]; then
log "=== Phase 2: EVAL ==="
for t in "${TASKS[@]}"; do
    if [ -d "$OUT_ROOT/${t}.${SUFFIX}.archived" ]; then
        log "eval-skip $t (already archived)"
        continue
    fi
    eval_and_archive "$t"
done
log "=== Phase 2 complete ==="
fi

if [ "$PHASE" = "eval" ] || [ "$PHASE" = "both" ]; then
    log "=== chain complete ==="
    log "summary written to $SUMMARY:"
    cat "$SUMMARY" | tee -a "$LOG"
else
    log "=== run phase complete (eval detached; summary follows from it) ==="
fi
