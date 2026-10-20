#!/usr/bin/env bash
# pbench_build_pertask_images.sh — build one agent image per ProgramBench task.
#
# Each image, omcgitea-agent-<repo>:pbench, is FROM that task's own
# programbench/<task>:task_cleanroom_v6, so the agent builds in the environment
# its submission is graded in (see agent/Dockerfile). The Gitea MCP binary
# comes from omcgitea-agent-base:pbench.
#
# Builds run in parallel with a concurrency cap — each is ~4 min and ~3.9 GB,
# and 20 unrestricted docker builds will thrash the layer store.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT" || exit 1
JOBS="${JOBS:-6}"
TAG="${TAG:-pbench}"
LOGDIR="$ROOT/out/pertask-build"; mkdir -p "$LOGDIR"
SUMMARY="$LOGDIR/summary.txt"; : > "$SUMMARY"

# TASKS is overridable so a launch rebuilds only the tasks it runs.
TASKS="${TASKS:-ffmpeg__ffmpeg.360a402 universal-ctags__ctags.243595e typst__typst.88356d0
php__php-src.c891263 gromacs__gromacs.665ea4c jgm__pandoc.5caad90
bellard__quickjs.d7ae12a danmar__cppcheck.0a5b103 osgeo__gdal.0847f12
duckdb__duckdb.bdb65ec nukesor__pueue.8b9d6fe samtools__samtools.aa823b5
tstack__lnav.ee34494 ast-grep__ast-grep.dde0fe0 alecthomas__chroma.8d04def
johnkerl__miller.8d85b46 stathissideris__ditaa.f2286c4 tinycc__tinycc.9b8765d
zk-org__zk.10d93d5 osgeo__proj.75d455c}"

log() { echo "[build $(date -u +%H:%M:%S)] $*"; }

# --- preflight -------------------------------------------------------------
fail=0
for t in $TASKS; do
    img="programbench/${t/__/_1776_}:task_cleanroom_v6"
    sudo docker image inspect "$img" >/dev/null 2>&1 || { log "FATAL: base missing: $img"; fail=1; }
done
sudo docker image inspect omcgitea-agent-base:pbench >/dev/null 2>&1 \
    || { log "FATAL: omcgitea-agent-base:pbench missing (source of gitea-mcp)"; fail=1; }
[ "$fail" = 0 ] || exit 1

# Name images after the REPO, not the org: osgeo__gdal and osgeo__proj both
# reduce to "osgeo" otherwise, and the second build silently overwrites the
# first — 20 tasks, 19 images, one of them wrong.
short() { t="${1#*__}"; echo "${t%%.*}" | tr -cd 'a-z0-9-'; }

build_one() {
    local t="$1"
    local base="programbench/${t/__/_1776_}:task_cleanroom_v6"
    local name="omcgitea-agent-$(short "$t"):$TAG"
    local lg="$LOGDIR/$(short "$t").log"
    if sudo docker build -f agent/Dockerfile \
         --build-arg TASK_IMAGE="$base" -t "$name" . >"$lg" 2>&1; then
        # Verify the property the whole design exists for: the agent image's
        # crate versions must equal the grader's, and our Node must stay off PATH.
        local ok
        ok=$(sudo docker run --rm --network none --entrypoint sh "$name" -c '
            b=$(ls /usr/local/cargo/registry/cache/*/ 2>/dev/null | grep -cE "^clap-4\.6\.1")
            n=$(command -v node >/dev/null && echo onpath || echo private)
            m=$(python3 -c "import json;print(\"board\" in json.load(open(\"/opt/omcgitea/config/mcp.json.tmpl\"))[\"mcpServers\"])" 2>/dev/null)
            a=$([ -x /usr/local/bin/copilot-wrapped ] && echo yes || echo NO)
            echo "clap461=$b node=$n board=$m copilot=$a"' 2>/dev/null)
        echo "OK   $name  $ok" >> "$SUMMARY"
    else
        echo "FAIL $name  (see $lg)" >> "$SUMMARY"
    fi
}

log "building $(echo $TASKS | wc -w) images, ${JOBS} at a time -> $LOGDIR"
for t in $TASKS; do
    build_one "$t" &
    while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do sleep 5; done
done
wait
log "=== done ==="
sort "$SUMMARY"
echo "  ok=$(grep -c '^OK' "$SUMMARY")  failed=$(grep -c '^FAIL' "$SUMMARY")"
