#!/usr/bin/env bash
# Compare rendered prompts, profiles and Compose files between a base revision and
# this working tree. Exit status is 3 when the rendered outputs differ and 1 when
# rendering itself fails.
# Usage: render_check.sh [BASE_REF] [render_snapshot.py options...]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${RENDER_CHECK_OUT:-$ROOT/out/render-check}"

default_base() {
    local ref
    for ref in upstream/main origin/main main; do
        git -C "$ROOT" rev-parse --verify --quiet "$ref^{commit}" >/dev/null && { echo "$ref"; return; }
    done
    echo "[render-check] FATAL: no base revision found; pass one explicitly" >&2
    return 1
}
if [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; then
    BASE_REF="$1"
    shift
else
    BASE_REF="$(default_base)"
fi

work="$(mktemp -d)"
cleanup() {
    git -C "$ROOT" worktree remove --force "$work/base" >/dev/null 2>&1 || true
    rm -rf "$work"
}
trap cleanup EXIT

git -C "$ROOT" worktree add --quiet --detach "$work/base" "$BASE_REF"
# Both trees are rendered by this checkout's tool, so they share fixtures and options.
python3 "$ROOT/tools/render_snapshot.py" --root "$work/base" --out "$OUT/base" "$@"
python3 "$ROOT/tools/render_snapshot.py" --root "$ROOT" --out "$OUT/head" "$@"

if diff -ru "$OUT/base" "$OUT/head" > "$OUT/render.diff"; then
    echo "[render-check] no rendered differences from $BASE_REF"
else
    echo "[render-check] rendered outputs differ from $BASE_REF; see $OUT/render.diff" >&2
    diff -rq "$OUT/base" "$OUT/head" >&2 || true
    exit 3
fi
