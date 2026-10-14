#!/usr/bin/env bash
# Runs one launch's tasks on one profile, back to back, then scores them. Called
# by run_chain in scripts/lib_launch.sh, which passes the run identity.
#
#   PHASE=run   per task: the runner with SKIP_EVAL=1, then a trajectory snapshot
#               (DATA_ROOT + out/<task>) and `make clean`. out/<task> is kept for
#               the eval phase.
#   PHASE=eval  per task: `programbench eval --filter <task>`, the score into the
#               summary, the eval.json into the trajectory, then out/<task> is
#               archived.
#   unset       both, in that order.
#
# Required: PROFILE, TASKS_ENV (comma-separated task ids), SUFFIX, TRAJ_ROOT.
# Logs: out/chain-$PROFILE.log and .summary.

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
# Resolve the host bind-mount root the way compose does: DATA_ROOT exported by
# the caller, else the profile's DATA_ROOT, else $ROOT/.claude-team-data.
if [ -z "${DATA_ROOT:-}" ] && [ -f "$ENV_FILE" ]; then
    DATA_ROOT="$(awk -F= '$1=="DATA_ROOT"{sub(/\r$/,"",$2); print $2; exit}' "$ENV_FILE")"
fi
DATA_ROOT="${DATA_ROOT:-$ROOT/.claude-team-data}"
DATA_DIR="$DATA_ROOT/$PROFILE"
RUN_SCRIPT="${RUN_SCRIPT:-./scripts/pbench_run.sh}"

mkdir -p "$TRAJ_ROOT" "$ROOT/out"
touch "$SUMMARY"

log() { echo "[chain $(date -u +%H:%M:%S)] $*" | tee -a "$LOG"; }

# --- Free host ports ----------------------------------------------------------
# The compose stack publishes Gitea + Mattermost on $EDGE_HTTP_PORT and
# $EDGE_MM_PORT (read from $ENV_FILE by both `make up` and the runner). If either
# is already bound, pick a free ephemeral port from the kernel and rewrite
# $ENV_FILE so the stack and every internal curl agree. The original $ENV_FILE
# is restored on EXIT.
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
    # Kernel-assigned ephemeral port. TOCTOU window between here and docker's
    # actual bind is tiny in practice; if it loses the race, `make up` fails
    # loudly and the operator re-runs (idempotent — trap restores $ENV_FILE).
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
        # A backup left behind by a crashed chain is the pristine env from
        # before its port rewrite: restore it rather than back up the
        # already-rewritten $ENV_FILE over it.
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

# Salvage a partial in-flight run (host reboot, chain restart mid-task):
# re-export the submission from Gitea if the runner's trap did not, then
# snapshot and clean. Eval happens in the eval phase.
salvage_interrupted() {
    if [ ! -d "$DATA_DIR" ]; then return 0; fi
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
        (cd "$ROOT" && make up PROFILE="$PROFILE") >>"$LOG" 2>&1 || log "WARN: make up failed during salvage"
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
    snapshot_run_and_clean "$current"
    log "salvage complete for $current (eval deferred to Phase 2)"
}

# Phase-1 snapshot: DATA_ROOT + out/<task> → traj, then make clean.
# out/<task> is LEFT IN PLACE (not archived) so Phase 2 eval can consume it.
snapshot_run_and_clean() {
    local task="$1"
    local dst="$TRAJ_ROOT/${task}.${SUFFIX}"
    log "snapshotting $task -> $dst"
    sudo mkdir -p "$dst"
    if [ -d "$DATA_DIR" ]; then
        sudo cp -a "$DATA_DIR/." "$dst/data-root/" \
            && log "copied DATA_ROOT -> $dst/data-root/" \
            || log "WARN: DATA_ROOT copy failed"
    else
        log "WARN: $DATA_DIR missing, nothing to snapshot from data-root"
    fi
    if [ -d "$OUT_ROOT/$task" ]; then
        sudo cp -a "$OUT_ROOT/$task/." "$dst/out/" \
            && log "copied out/$task -> $dst/out/" \
            || log "WARN: out/$task copy failed"
    fi
    sudo chown -R "$(id -u):$(id -g)" "$dst" 2>/dev/null || true
    log "make clean PROFILE=$PROFILE (out/$task preserved for Phase 2 eval)"
    (cd "$ROOT" && make clean PROFILE="$PROFILE") >>"$LOG" 2>&1 \
        || log "WARN: make clean returned non-zero"
}

# Phase-2: run eval for one task, tee score, copy eval.json into traj, archive.
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
          uv run programbench eval "$OUT_ROOT" --filter "$task" ) >>"$LOG" 2>&1 \
            || log "WARN: eval $task returned non-zero"
    else
        log "FATAL eval $task: uv not on PATH"
        return 1
    fi
    report_score "$task"
    # copy the just-produced eval.json into the trajectory snapshot
    local eval_json="$task_out/$task.eval.json"
    if [ -f "$eval_json" ] && [ -d "$dst/out" ]; then
        sudo cp -a "$eval_json" "$dst/out/" \
            && sudo chown "$(id -u):$(id -g)" "$dst/out/$task.eval.json" 2>/dev/null || true
        log "eval.json copied into trajectory: $dst/out/"
    fi
    # archive out/<task> so a re-run of the chain won't rerun this task
    sudo mv "$task_out" "${task_out}.${SUFFIX}.archived" 2>/dev/null || true
}

# SCORE counts every rerun attempt as its own test, so it overstates the result.
# The canonical-kept score comes from tools/pbench_score_report.py.
report_score() {
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
    local task="$1"
    local hours="${HOURS:-6}"
    log "launching $task (${hours}h, SKIP_EVAL=1)"
    cd "$ROOT" || { log "FATAL: cd $ROOT failed"; return 1; }
    # Collect the runner's real exit status, so a stack that fails `make up`
    # in 60s is not reported like a clean session and then graded as 0.00%.
    # The runner is disowned, so `wait` is unavailable: the status goes through
    # a file written by the wrapping subshell.
    # Keyed on the full task id: tasks can share an owner (osgeo__gdal,
    # osgeo__proj), and an owner-keyed name would mix their logs and statuses.
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
        ${WORK_HOST_PATH:+WORK_HOST_PATH="$WORK_HOST_PATH"} \
        "$RUN_SCRIPT" \
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
        # Leave a marker next to the outputs. Scoring must treat this task as
        # NO RESULT rather than as a 0.00%: the difference is "the harness
        # broke" vs "the agents failed", and averaging the latter in silently
        # understates every configuration that happened to hit a bad stack.
        mkdir -p "$OUT_ROOT/$task" 2>/dev/null || true
        echo "run failed rc=$rc at $(date -u +%FT%TZ); see out/pbench-${task}-${SUFFIX}.log" \
            > "$OUT_ROOT/$task/RUN_FAILED" 2>/dev/null || true
        log "WARN: $task RUN FAILED (rc=$rc) — marked RUN_FAILED; any eval of it is meaningless"
    fi
    return 0
}

IFS=',' read -r -a TASKS <<< "$TASKS_ENV"

log "=== chain start (${#TASKS[@]} tasks x ${HOURS:-6}h; profile=$PROFILE; suffix=$SUFFIX; traj=$TRAJ_ROOT) ==="

# PHASE selects which halves run (see the header). Eval needs no containers (it
# works on the exported submission) and OUT_ROOT is per profile, so an eval and
# the next task's run cannot collide.
PHASE="${PHASE:-both}"

wait_for_docker || exit 1
allocate_ports || exit 1
# Salvage belongs to the run half: in an eval-only pass it would restart the
# stack and re-export over the submission taken at the budget boundary.
[ "$PHASE" = "eval" ] || salvage_interrupted

# --- Phase 1: RUN, eval deferred ---------------------------------------------
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

# --- Phase 2: EVAL ------------------------------------------------------------
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

# Only the EVAL phase has a summary worth printing; the RUN phase has no scores.
if [ "$PHASE" = "eval" ] || [ "$PHASE" = "both" ]; then
    log "=== chain complete ==="
    log "summary written to $SUMMARY:"
    cat "$SUMMARY" | tee -a "$LOG"
else
    log "=== run phase complete (eval detached; summary follows from it) ==="
fi
