#!/usr/bin/env bash
# 20-task sweep2 chain on org-pbench-4team profile, v48-matched image
# (Ubuntu 22.04 base, toolchain byte-for-byte aligned with the ProgramBench
# eval sandbox: gcc 11.4.0, rustc 1.92.0, go 1.21.0, ghc 8.8.4, jdk 11,
# python 3.10). Launched via ACP -> claude-agent-acp -> claude-opus-4.7,
# via egress-proxy -> Azure FrontDoor upstream. xhigh effort.
#
# Two-phase design (2026-07-10 rewrite):
#   Phase 1 (RUN):  all 20 tasks x 6h back-to-back with SKIP_EVAL=1.
#                   No eval containers spun up between runs → keeps the host
#                   quiet during the 120h agent phase and avoids the risk of
#                   eval failures polluting the run pipeline. Trajectory
#                   snapshots (DATA_ROOT + out/<task>) still captured after
#                   each task, then make clean wipes DATA_ROOT for the next.
#                   out/<task> is preserved between phases (needed for eval).
#   Phase 2 (EVAL): after all 20 runs are done, loop again and run
#                   `programbench eval --filter <task>` per task, tee scores
#                   into the summary, copy the produced *.eval.json into the
#                   trajectory snapshot, then archive out/<task>.
#
# Task order per operator brief (2026-07-09):
#   ffmpeg, ctags, typst, php-src, gromacs, pandoc, quickjs, cppcheck,
#   gdal, duckdb, pueue, samtools, lnav, ast-grep, chroma, miller,
#   ditaa, tinycc, zk, proj
#
# 20 tasks x 6h = 120h wall-clock (~5 days) for RUN phase.
# EVAL phase is ~5-30 min per task depending on test suite size.
#
# Prereq (one-time): retag the matched image so `make up` picks it up.
#   sudo docker tag omcgitea-hermes-agent:v48-matched omcgitea-hermes-agent:local
#
# Logs: out/chain-v48matched-20task-4team-eng-sweep2.log
# Per-task run logs: out/pbench-<repo>-opus47-4team-v48matched-sweep2.log

set -u
# Repo root = where THIS script lives, not a fixed checkout. This tree is a
# standalone snapshot; a pinned $HOME/agensteam would read compose files,
# .env.<profile> and templates from a different tree than the one invoked.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="${PROFILE:-org-pbench-4team}"
# INSTANCE lets multiple chains coexist by keying LOG/SUMMARY/SUFFIX/OUT_ROOT
# off a distinct short name (e.g. "1team-a"). Defaults to PROFILE so single-
# chain callers keep the historical filenames.
INSTANCE="${INSTANCE:-$PROFILE}"
LOG="${LOG:-$ROOT/out/chain-${INSTANCE}.log}"
SUMMARY="${SUMMARY:-$ROOT/out/chain-${INSTANCE}.summary}"
TRAJ_ROOT="${TRAJ_ROOT:-$HOME/agensteam_traj_eng_sweep_2}"
OUT_ROOT="${OUT_ROOT:-$ROOT/out/pbench-${INSTANCE}}"
SUFFIX="${SUFFIX:-opus47-${INSTANCE}-v48matched-sweep2}"
PB_REPO="${PROGRAMBENCH_REPO:-$HOME/programbench}"
DOCKER_SUDO_SHIM="$ROOT/scripts/pbench-docker-sudo.sh"
ENV_FILE="$ROOT/.env.$PROFILE"
# Resolve host bind-mount root the same way compose does. Precedence:
#   1. DATA_ROOT already exported by the caller
#   2. DATA_ROOT= line inside $ENV_FILE (parallel drivers pin per-chain dirs)
#   3. $ROOT/.claude-team-data (matches compose's ${DATA_ROOT:-../.claude-team-data})
# Without step 2 the parallel-driver stacks silently skipped snapshotting
# because DATA_DIR pointed at the shared default while the stacks actually
# mounted isolated per-chain dirs.
if [ -z "${DATA_ROOT:-}" ] && [ -f "$ENV_FILE" ]; then
    DATA_ROOT="$(awk -F= '$1=="DATA_ROOT"{sub(/\r$/,"",$2); print $2; exit}' "$ENV_FILE")"
fi
DATA_ROOT="${DATA_ROOT:-$ROOT/.claude-team-data}"
DATA_DIR="$DATA_ROOT/$PROFILE"
# Which per-task launcher to invoke. The 6.11 sweep drivers set this explicitly;
# the default matches them so a manual chain run does not need the override.
RUN_SCRIPT="${RUN_SCRIPT:-./scripts/pbench_run_1team.sh}"

mkdir -p "$TRAJ_ROOT" "$ROOT/out"
touch "$SUMMARY"

log() { echo "[chain $(date -u +%H:%M:%S)] $*" | tee -a "$LOG"; }

# --- Auto-allocate free host ports (multi-chain / multi-tenant safe) --------
# The compose stack publishes Gitea + Mattermost via $EDGE_HTTP_PORT and
# $EDGE_MM_PORT (read from $ENV_FILE by both `make up` and pbench_run_*.sh).
# If either is already bound (another chain, another user, whatever), pick a
# free ephemeral port from the kernel and rewrite $ENV_FILE so the compose
# stack and every internal curl agree. Original $ENV_FILE is restored on
# EXIT so subsequent runs start from the pinned defaults.
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
        # R4 fix: stable backup name (was `.chain-orig-$$` — leaked orphans
        # on crash, and PID reuse could restore the wrong content). If an
        # earlier run left one behind, treat that as our source-of-truth
        # (it's the pristine on-disk env before any port rewrites) and
        # avoid overwriting it with our already-mutated $ENV_FILE.
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

# Salvage any partial in-flight run (host reboot, chain restart mid-task).
# Re-exports submission from Gitea if the trap didn't run, then snapshots +
# cleans. Eval is intentionally deferred to Phase 2 (matches new design).
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
    nohup env \
        TASK="$task" \
        HOURS="$hours" \
        PROFILE="$PROFILE" \
        OUT_DIR="$OUT_ROOT" \
        PROGRAMBENCH_REPO="$PB_REPO" \
        PATH="$HOME/.local/bin:$PATH" \
        SKIP_EVAL=1 \
        ${WORK_HOST_PATH:+WORK_HOST_PATH="$WORK_HOST_PATH"} \
        "$RUN_SCRIPT" \
        > "$ROOT/out/pbench-${task%%__*}-${SUFFIX}.log" 2>&1 &
    local pid=$!
    disown
    log "launched $task pid=$pid"
    while kill -0 "$pid" 2>/dev/null; do sleep 60; done
    log "$task pid=$pid exited"
}

TASKS=(
    "ffmpeg__ffmpeg.360a402"
    "universal-ctags__ctags.243595e"
    "typst__typst.88356d0"
    "php__php-src.c891263"
    "gromacs__gromacs.665ea4c"
    "jgm__pandoc.5caad90"
    "bellard__quickjs.d7ae12a"
    "danmar__cppcheck.0a5b103"
    "osgeo__gdal.0847f12"
    "duckdb__duckdb.bdb65ec"
    "nukesor__pueue.8b9d6fe"
    "samtools__samtools.aa823b5"
    "tstack__lnav.ee34494"
    "ast-grep__ast-grep.dde0fe0"
    "alecthomas__chroma.8d04def"
    "johnkerl__miller.8d85b46"
    "stathissideris__ditaa.f2286c4"
    "tinycc__tinycc.9b8765d"
    "zk-org__zk.10d93d5"
    "osgeo__proj.75d455c"
)

# TASKS_ENV (comma-separated) lets a parallel driver hand each chain a
# different partition of the master list without editing the script.
if [ -n "${TASKS_ENV:-}" ]; then
    IFS=',' read -r -a TASKS <<< "$TASKS_ENV"
fi

log "=== chain start (${#TASKS[@]} tasks x 6h; profile=$PROFILE; suffix=$SUFFIX; traj=$TRAJ_ROOT) ==="
log "image expected at :local — retag with 'docker tag omcgitea-hermes-agent:v48-matched omcgitea-hermes-agent:local' first"

wait_for_docker || exit 1
allocate_ports || exit 1
salvage_interrupted

# --- Phase 1: RUN all 20 tasks with eval deferred ----------------------------
log "=== Phase 1: RUN (SKIP_EVAL=1) ==="
for t in "${TASKS[@]}"; do
    if [ -d "$OUT_ROOT/${t}.${SUFFIX}.archived" ]; then
        log "skipping $t (already archived from a prior chain)"
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

# --- Phase 2: EVAL all tasks in a batch --------------------------------------
log "=== Phase 2: EVAL ==="
for t in "${TASKS[@]}"; do
    if [ -d "$OUT_ROOT/${t}.${SUFFIX}.archived" ]; then
        log "eval-skip $t (already archived)"
        continue
    fi
    eval_and_archive "$t"
done
log "=== Phase 2 complete ==="

log "=== chain complete ==="
log "summary written to $SUMMARY:"
cat "$SUMMARY" | tee -a "$LOG"
