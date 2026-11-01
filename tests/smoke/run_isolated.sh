#!/usr/bin/env bash
# Run the smoke test inside a private Docker-in-Docker daemon whose storage lives
# under DATA_DIR, so a shared host's daemon, image tags, networks and root disk are
# left alone. The host only runs one capped, privileged container.
# Usage: run_isolated.sh DATA_DIR [COMMAND...]   (default: the smoke test; SMOKE_* and
# LIVE_* settings are passed through; ISOLATED_MOUNTS adds host directories at the same path)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA_DIR="${1:?usage: run_isolated.sh DATA_DIR [COMMAND...]}"
shift
COMMAND=("$@")
[ $# -gt 0 ] || COMMAND=(bash tests/smoke/run_smoke.sh)
IMAGE="${SMOKE_DIND_IMAGE:-docker:dind}"
CPUS="${SMOKE_DIND_CPUS:-8}"
MEMORY="${SMOKE_DIND_MEMORY:-16g}"
# Optional private bridge, for hosts whose default bridge network is unusable.
SUBNET="${SMOKE_DIND_SUBNET:-}"
NAME="agensh-smoke-dind-$$"
DOCKER=(sudo -n docker)

log() { echo "[smoke-isolated $(date -u +%H:%M:%S)] $*" >&2; }

mkdir -p "$DATA_DIR/docker"
DATA_DIR="$(cd "$DATA_DIR" && pwd)"

cleanup() {
    log "removing $NAME (daemon storage kept in $DATA_DIR/docker for caching)"
    "${DOCKER[@]}" rm -f "$NAME" >/dev/null 2>&1 || true
    [ -z "$SUBNET" ] || "${DOCKER[@]}" network rm "$NAME-net" >/dev/null 2>&1 || true
}
trap cleanup EXIT

log "starting $IMAGE as $NAME (cpus=$CPUS memory=$MEMORY, storage $DATA_DIR/docker)"
# Temporary files and inner state go to DATA_DIR; only the small tool layer and a
# capped log stay in the host's container storage.
mkdir -p "$DATA_DIR/tmp"
network_args=()
extra_mounts=()
for dir in ${ISOLATED_MOUNTS:-}; do
    extra_mounts+=(-v "$dir:$dir")
done
if [ -n "$SUBNET" ]; then
    "${DOCKER[@]}" network create --driver bridge --subnet "$SUBNET" "$NAME-net" >/dev/null
    network_args=(--network "$NAME-net")
fi
"${DOCKER[@]}" run -d --privileged --name "$NAME" "${network_args[@]}" --cpus "$CPUS" --memory "$MEMORY" \
    --log-opt max-size=10m --log-opt max-file=1 \
    -e DOCKER_TLS_CERTDIR= -v "$DATA_DIR/docker:/var/lib/docker" -v "$DATA_DIR/tmp:/tmp" \
    -v "$ROOT:$ROOT" "${extra_mounts[@]}" -w "$ROOT" "$IMAGE" >/dev/null

for _ in $(seq 1 60); do
    "${DOCKER[@]}" exec "$NAME" docker info >/dev/null 2>&1 && break
    sleep 2
done
"${DOCKER[@]}" exec "$NAME" docker info >/dev/null 2>&1 || { log "inner daemon did not start"; exit 1; }
log "inner daemon ready: $("${DOCKER[@]}" exec "$NAME" docker version --format '{{.Server.Version}}')"

# The runner and smoke script expect a GNU userland with sudo, make and Python.
"${DOCKER[@]}" exec "$NAME" apk add --no-cache -q bash make python3 git curl jq gettext sudo \
    util-linux findutils coreutils gawk procps tar >/dev/null

# sudo drops the caller's environment, so settings are passed with their values.
env_args=()
while IFS= read -r setting; do
    env_args+=(-e "$setting")
done < <(env | grep -E '^(SMOKE_(PACK|WORKERS|MINUTES|KEEP|INTERRUPT|HUMAN|SNAPSHOT|PORT_BASE|SUBNET_OCTET)|LIVE_[A-Z_]+)=' || true)

log "running ${COMMAND[*]} inside $NAME"
"${DOCKER[@]}" exec "${env_args[@]}" "$NAME" "${COMMAND[@]}"
