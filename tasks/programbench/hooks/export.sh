#!/usr/bin/env bash
# ProgramBench export hook: archive committed main as $AGENSH_TASK_OUT/submission.tar.gz.
# Retries three times; on failure leaves EXPORT_FAILED and an empty archive, since
# the repository is still intact under the profile data for manual recovery.
set -uo pipefail

ROOT="${AGENSH_ROOT:?}"; TASK="${AGENSH_TASK:?}"; OUT_DIR="${AGENSH_OUT_DIR:?}"
TASK_OUT="${AGENSH_TASK_OUT:?}"; PROFILE="${AGENSH_PROFILE:?}"
TEAM_URL="${AGENSH_GITEA_URL:?}"; REPO_PATH="${AGENSH_GITEA_REPO:?}"
PUBLIC_URL="${AGENSH_GITEA_PUBLIC_URL:?}"

log() { echo "[pbench] $*" >&2; }

mkdir -p "$TASK_OUT"
log "exporting submission from Gitea repo $REPO_PATH → $TASK_OUT/"
for attempt in 1 2 3; do
    if python3 "$ROOT/tasks/programbench/tools/submission.py" export \
        --from-gitea "$TEAM_URL" --task "$TASK" --out-dir "$OUT_DIR" \
        2>>"$TASK_OUT/export.log"; then
        log "submission.tar.gz written (attempt $attempt)"
        rm -f "$TASK_OUT/EXPORT_FAILED"
        exit 0
    fi
    log "WARN: gitea export attempt $attempt/3 failed (see export.log)"
    [ "$attempt" -lt 3 ] && sleep $(( attempt * 15 ))
done

log "ERROR: gitea export FAILED after 3 attempts — this task has NO submission."
log "ERROR: the repo is still intact under \$DATA_ROOT; recover with:"
log "ERROR:   python3 tasks/programbench/tools/submission.py export --from-gitea file://<data-root>/gitea/git/repositories/$REPO_PATH.git --task $TASK --out-dir <dir>"
{
    echo "export failed after 3 attempts at $(date -u +%FT%TZ)"
    echo "task=$TASK profile=$PROFILE url=$PUBLIC_URL"
    echo "the gitea repo under DATA_ROOT is intact; this is an export failure, not a zero"
} > "$TASK_OUT/EXPORT_FAILED"
tar -czf "$TASK_OUT/submission.tar.gz" -C "$TASK_OUT" --files-from /dev/null 2>/dev/null || \
    : > "$TASK_OUT/submission.tar.gz"
exit 1
