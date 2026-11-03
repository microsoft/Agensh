#!/usr/bin/env bash
# ProgramBench evaluate hook: run `programbench eval` on the exported submission,
# inside agensh.slice when available, through the Docker shim's evaluator limits.
set -uo pipefail

ROOT="${AGENSH_ROOT:?}"; TASK="${AGENSH_TASK:?}"; OUT_DIR="${AGENSH_OUT_DIR:?}"
TASK_OUT="${AGENSH_TASK_OUT:?}"
PB_REPO="${PROGRAMBENCH_REPO:-$HOME/programbench}"

log() { echo "[pbench] $*" >&2; }
die() { echo "[pbench] FATAL: $*" >&2; exit 1; }

log "running programbench eval on $OUT_DIR"
# The Docker shim applies evaluator limits without changing ProgramBench itself.
export PROGRAMBENCH_DOCKER_EXECUTABLE="${PROGRAMBENCH_DOCKER_EXECUTABLE:-$ROOT/tasks/programbench/scripts/eval_docker_shim.sh}"
pbench_tmp="$TASK_OUT/_evaltmp"
rm -rf "$pbench_tmp"; mkdir -p "$pbench_tmp"
export TMPDIR="$pbench_tmp"
in_slice=()
if command -v systemd-run >/dev/null 2>&1 && systemctl cat agensh.slice >/dev/null 2>&1; then
    in_slice=(sudo -n systemd-run --scope --quiet --slice=agensh.slice --collect --uid="$(id -u)" --gid="$(id -g)")
    log "eval runs inside agensh.slice (aggregate ceiling)"
else
    log "WARN: agensh.slice not installed -- eval runs UNCAPPED (see docker/agensh.slice)"
fi
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

eval_json="$TASK_OUT/$TASK.eval.json"
if [ -f "$eval_json" ]; then
    log "eval.json written: $eval_json"
else
    log "WARN: eval.json not found at $eval_json"
fi
