#!/usr/bin/env bash
# Build one worker image per task from its v6 cleanroom and the cached MCP artifact.
# JOBS bounds concurrent builds; individual logs and a summary are written under out/.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT" || exit 1
harness_env=$(python3 "$ROOT/agent/harness_config.py" shell "$@") || exit $?
eval "$harness_env"
JOBS="${JOBS:-6}"
TAG="${TAG:-pbench}"
LOGDIR="$ROOT/out/pertask-build"; mkdir -p "$LOGDIR"
SUMMARY="$LOGDIR/summary.txt"; : > "$SUMMARY"

TASKS="${TASKS:-ffmpeg__ffmpeg.360a402 universal-ctags__ctags.243595e typst__typst.88356d0
php__php-src.c891263 gromacs__gromacs.665ea4c jgm__pandoc.5caad90
bellard__quickjs.d7ae12a danmar__cppcheck.0a5b103 osgeo__gdal.0847f12
duckdb__duckdb.bdb65ec nukesor__pueue.8b9d6fe samtools__samtools.aa823b5
tstack__lnav.ee34494 ast-grep__ast-grep.dde0fe0 alecthomas__chroma.8d04def
johnkerl__miller.8d85b46 stathissideris__ditaa.f2286c4 tinycc__tinycc.9b8765d
zk-org__zk.10d93d5 osgeo__proj.75d455c}"

log() { echo "[build $(date -u +%H:%M:%S)] $*"; }

fail=0
# Require all base images before spending time on any per-task build.
for t in $TASKS; do
    img="programbench/${t/__/_1776_}:task_cleanroom_v6"
    sudo docker image inspect "$img" >/dev/null 2>&1 || { log "FATAL: base missing: $img"; fail=1; }
done
sudo docker image inspect omcgitea-agent-base:pbench >/dev/null 2>&1 \
    || { log "FATAL: omcgitea-agent-base:pbench missing (source of gitea-mcp)"; fail=1; }
[ "$fail" = 0 ] || exit 1

short() { t="${1#*__}"; echo "${t%%.*}" | tr -cd 'a-z0-9-'; }

build_one() {
    local t="$1"
    local base="programbench/${t/__/_1776_}:task_cleanroom_v6"
    local name="omcgitea-agent-$(short "$t")-$AGENT_HARNESS:$TAG"
    local lg="$LOGDIR/$(short "$t").log"
    if sudo docker build -f agent/Dockerfile \
         --build-arg TASK_IMAGE="$base" --build-arg AGENT_HARNESS="$AGENT_HARNESS" \
         --build-arg "${AGENT_HARNESS^^}_CLI_VERSION=$HARNESS_VERSION" -t "$name" . >"$lg" 2>&1; then
        local ok
        if ! sudo docker run --rm --network none --entrypoint python3 "$name" \
            /opt/omcgitea/check_harness.py "$AGENT_HARNESS" "$HARNESS_VERSION" >>"$lg" 2>&1; then
            echo "FAIL $name (harness check; see $lg)" >> "$SUMMARY"
            return
        fi
        ok=$(sudo docker run --rm --network none --entrypoint sh "$name" -c '
            b=$(ls /usr/local/cargo/registry/cache/*/ 2>/dev/null | grep -cE "^clap-4\.6\.1")
            n=$(command -v node >/dev/null && echo onpath || echo private)
            m=$(python3 -c "import json;print(\"board\" in json.load(open(\"/opt/omcgitea/config/mcp.json.tmpl\"))[\"mcpServers\"])" 2>/dev/null)
            echo "clap461=$b node=$n board=$m harness=$AGENT_HARNESS"' 2>/dev/null)
        echo "OK   $name  $ok" >> "$SUMMARY"
    else
        echo "FAIL $name  (see $lg)" >> "$SUMMARY"
    fi
}

log "building $(echo $TASKS | wc -w) images, ${JOBS} at a time -> $LOGDIR"
# Each build appends one result; wait for a slot before starting another.
for t in $TASKS; do
    build_one "$t" &
    while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do sleep 5; done
done
wait
log "=== done ==="
sort "$SUMMARY"
failed=$(grep -c '^FAIL' "$SUMMARY" || true)
echo "  ok=$(grep -c '^OK' "$SUMMARY" || true)  failed=$failed"
[ "$failed" -eq 0 ]
