#!/usr/bin/env bash
# ProgramBench prepare hook: extract the cleanroom workspace as the team's seed and
# stage the reference binary outside it, executable but unreadable by workers.
# Writes $AGENSH_TASK_OUT/.seed_path and compose.env (PBENCH_BIN for the mount).
set -euo pipefail

ROOT="${AGENSH_ROOT:?}"; TASK="${AGENSH_TASK:?}"; TASK_OUT="${AGENSH_TASK_OUT:?}"
ENV_FILE="${AGENSH_ENV_FILE:?}"
DOCKER_ORG="${PROGRAMBENCH_DOCKER_ORG:-programbench}"
BIN_PATH="$TASK_OUT/bin/executable"

log() { echo "[pbench] $*" >&2; }
die() { echo "[pbench] FATAL: $*" >&2; exit 1; }

source "$ROOT/tasks/programbench/scripts/lib_images.sh"
img_base="$DOCKER_ORG/$(printf '%s' "$TASK" | sed 's/__/_1776_/')"
CLEANROOM_TAG="$(pbench_cleanroom_tag "$ENV_FILE")" || die "reference image configuration mismatch"
CLEANROOM_IMG="$img_base:$CLEANROOM_TAG"

log "seeding cleanroom workspace from $CLEANROOM_IMG"
if ! sudo docker image inspect "$CLEANROOM_IMG" >/dev/null 2>&1; then
    log "pulling $CLEANROOM_IMG (first run; agents get NO internet so this MUST happen host-side now)"
    sudo docker pull "$CLEANROOM_IMG" >/dev/null 2>&1 \
        || die "cannot pull $CLEANROOM_IMG (check task id / dockerhub access)"
fi
# Resolve the tag once so extracted assets and recorded provenance agree.
cleanroom_id="$(sudo docker image inspect --format '{{.Id}}' "$CLEANROOM_IMG")" \
    || die "cannot identify reference image"
seed_dir="$TASK_OUT/_seed"
rm -rf "$seed_dir"; mkdir -p "$seed_dir"
PROGRAMBENCH_DOCKER_ORG="$DOCKER_ORG" \
    python3 "$ROOT/tasks/programbench/tools/submission.py" seed --image "$cleanroom_id" \
    --into "$seed_dir" --bin-out "$BIN_PATH" \
    || die "seed extraction failed"
if [ -f "$BIN_PATH" ]; then
    # Workers may execute the reference as UID 10000, but may not read its bytes.
    sudo chown 0:0 "$BIN_PATH"
    sudo chmod 0111 "$BIN_PATH"
    sudo -n python3 - "$BIN_PATH" "$TASK_OUT/reference.json" "$CLEANROOM_IMG" "$cleanroom_id" <<'PY'
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
echo "$seed_dir" > "$TASK_OUT/.seed_path"
echo "PBENCH_BIN=$BIN_PATH" > "$TASK_OUT/compose.env"
