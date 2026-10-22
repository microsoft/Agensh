#!/usr/bin/env bash
# Preflight the recorded fleet configuration, then launch tasks sequentially.
# lib_launch.sh runs each inference phase and overlaps its evaluation with the next.

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || { echo "FATAL: cannot cd $ROOT" >&2; exit 1; }

MODE=single-node
TASKS="${TASKS:-jgm__pandoc.5caad90 gromacs__gromacs.665ea4c universal-ctags__ctags.243595e php__php-src.c891263 ffmpeg__ffmpeg.360a402}"
HOURS="${HOURS:-6}"
WORKERS="${WORKERS:-8}"
source "$ROOT/scripts/lib_launch.sh"
source "$ROOT/scripts/lib_pbench_images.sh"
mkdir -p "$TRAJ_ROOT" "$ROOT/out"

pv() { awk -F= -v k="$2" '$1==k{print substr($0, length(k) + 2); exit}' "$ROOT/.env.$1"; }
n_tasks=$(wc -w <<<"$TASKS")

log "preflight over $n_tasks tasks, run $SUFFIX"

for task in $TASKS; do
    scrub_shadowed_env "$ROOT/.env.$(task_profile "$task")"
done

fail=0
# Check every selected profile before starting any experiment containers.
refuse_double_launch || fail=1
for task in $TASKS; do
    p="$(task_profile "$task")"
    [ -f "$ROOT/.env.$p" ] || { log "FATAL: .env.$p missing — run scripts/pbench_gen_env.sh"; fail=1; continue; }

    o="$(pv "$p" PBENCH_ORCHESTRATOR)"
    [ "${o:-compose}" = "compose" ] || { log "FATAL: .env.$p supports single-node Compose only"; fail=1; }
    [ "${PBENCH_ORCHESTRATOR:-compose}" = "compose" ] || { log "FATAL: PBENCH_ORCHESTRATOR supports single-node Compose only"; fail=1; }

    img="$(pv "$p" AGENT_IMAGE)"
    [ -n "$img" ] || { log "FATAL: .env.$p AGENT_IMAGE missing"; fail=1; continue; }
    sudo docker image inspect "$img" >/dev/null 2>&1 || { log "FATAL: image missing: $img"; fail=1; }
    sudo docker run --rm --network none --entrypoint sh "$img" -c 'test -x /usr/local/bin/copilot-wrapped' \
        2>/dev/null || { log "FATAL: $img has no copilot-wrapped"; fail=1; }

    k="$(pv "$p" AGENT_KIND)"
    [ "$k" = "copilot" ] || { log "FATAL: .env.$p AGENT_KIND=$k expected copilot"; fail=1; }
    m="$(pv "$p" ANTHROPIC_MODEL)"
    [ "$m" = "gpt-5.6-sol" ] || { log "FATAL: .env.$p ANTHROPIC_MODEL=$m expected gpt-5.6-sol"; fail=1; }
    w="$(pv "$p" COPILOT_PROVIDER_WIRE_API)"
    [ "$w" = "responses" ] || { log "FATAL: .env.$p COPILOT_PROVIDER_WIRE_API='$w' expected responses"; fail=1; }
    r="$(pv "$p" COPILOT_AGENT_REASONING_EFFORT)"
    [ "$r" = "high" ] || { log "FATAL: .env.$p COPILOT_AGENT_REASONING_EFFORT='$r' expected high"; fail=1; }
    m="$(pv "$p" COPILOT_PROVIDER_MAX_PROMPT_TOKENS)"
    [ "$m" = "272000" ] || { log "FATAL: .env.$p COPILOT_PROVIDER_MAX_PROMPT_TOKENS='$m' expected 272000"; fail=1; }

    gw="$(pv "$p" PBENCH_WORKERS_PER_TEAM)"
    [ "$gw" = "$WORKERS" ] || { log "FATAL: .env.$p PBENCH_WORKERS_PER_TEAM=$gw expected $WORKERS"; fail=1; }
    sn="$(pv "$p" PBENCH_SUBNET_DEFAULT)"
    python3 -c "
import ipaddress,sys
n=ipaddress.ip_network('$sn'); need=2*int('${WORKERS:-0}' or 0)+8
sys.exit(0 if n.num_addresses-2 >= need else 1)
" 2>/dev/null || { log "FATAL: .env.$p PBENCH_SUBNET_DEFAULT=$sn too small for $WORKERS workers (need $((2*WORKERS+8)) IPs)"; fail=1; }

    cleanroom_tag="$(pbench_cleanroom_tag "$ROOT/.env.$p")" || { fail=1; continue; }
    ci="${PROGRAMBENCH_DOCKER_ORG:-programbench}/${task/__/_1776_}:$cleanroom_tag"
    sudo docker image inspect "$ci" >/dev/null 2>&1 || { log "FATAL: cleanroom missing: $ci"; fail=1; }

    dd="$(pv "$p" DATA_ROOT)"; dd="${dd:-$ROOT/.claude-team-data}/$p"
    if [ -d "$dd" ] && [ -n "$(sudo ls -A "$dd" 2>/dev/null)" ]; then
        log "FATAL: $dd is not empty — once its trajectory is exported, run make clean PROFILE=$p"; fail=1
    fi
    left="$(unfinished_runs "$ROOT/out/$p" | tr '\n' ' ')"
    [ -z "$left" ] || { log "FATAL: out/$p holds unfinished run(s): $left— archive them first"; fail=1; }
done

stale_img() {
    # Detect source edits newer than the image, excluding installed dependencies.
    local img="$1" label="$2"; shift 2
    sudo docker image inspect "$img" >/dev/null 2>&1 || { log "FATAL: image missing: $img"; return 1; }
    local built newest
    built=$(sudo docker image inspect "$img" --format '{{.Created}}')
    built=$(date -d "$built" +%s 2>/dev/null) || return 0
    newest=$(find "$@" \( -name node_modules -o -name __pycache__ \) -prune -o -type f -printf '%T@\n' 2>/dev/null \
             | cut -d. -f1 | sort -rn | head -1)
    [ -n "$newest" ] || return 0
    if [ "$newest" -gt "$built" ]; then
        log "FATAL: $img built $(date -d @$built -u +%m-%d\ %H:%M) but $label changed $(date -d @$newest -u +%m-%d\ %H:%M) — rebuild it"
        return 1
    fi
    log "image OK: $img is newer than $label"
}
BS="$ROOT/board-service"; MR="$ROOT/mini-router"
for task in $TASKS; do
    p="$(task_profile "$task")"
    board_img="$(pv "$p" BOARD_IMAGE)"
    router_img="$(pv "$p" MINI_ROUTER_IMAGE)"
    stale_img "${board_img:-omcgitea-board:local}" board-service/ \
        "$BS/Dockerfile" "$BS/requirements.txt" "$BS"/*.py || fail=1
    stale_img "${router_img:-omcgitea-mini-router:local}" mini-router/ \
        "$MR/Dockerfile" "$MR/package.json" "$MR/package-lock.json" "$MR/tsconfig.json" \
        "$MR/src" || fail=1
done

for task in $TASKS; do
    p="$(task_profile "$task")"; img="$(pv "$p" AGENT_IMAGE 2>/dev/null)"
    if image_file_matches "$img" /opt/omcgitea/entrypoint.sh "$ROOT/agent/entrypoint.sh"; then
        log "image OK: $img bakes this checkout's agent/entrypoint.sh"
    else
        log "FATAL: ${img:-$p has no AGENT_IMAGE, which} does not bake this checkout's agent/entrypoint.sh -- rebuild it: TASKS=$task bash scripts/pbench_build_pertask_images.sh"
        fail=1
    fi
done

sm="$(systemctl show pbench.slice -p MemoryMax --value 2>/dev/null)"
case "$sm" in
    ''|infinity)
        if [ "${PBENCH_SKIP_HOST_GUARDS:-0}" = "1" ]; then
            log "WARN: pbench.slice has no MemoryMax — skipped by PBENCH_SKIP_HOST_GUARDS=1"
        else
            log "FATAL: pbench.slice has no MemoryMax"; fail=1
        fi ;;
    *) log "pbench.slice MemoryMax=$sm ($(( sm / 1073741824 )) GiB)" ;;
esac

if [ "$(systemctl is-enabled pbench-reboot-guard.service 2>/dev/null)" = "enabled" ]; then
    log "reboot guard enabled — a maintenance reboot will stop stacks cleanly"
else
    if [ "${PBENCH_SKIP_HOST_GUARDS:-0}" = "1" ]; then
        log "WARN: pbench-reboot-guard.service not enabled — skipped by PBENCH_SKIP_HOST_GUARDS=1 (a maintenance reboot will kill stacks mid-run)"
    else
        log "FATAL: pbench-reboot-guard.service not enabled (see docker/pbench-reboot-guard.service)"; fail=1
    fi
fi

TOOLSPROBE='[{"type":"function","name":"read_file","description":"r","parameters":{"type":"object","properties":{"p":{"type":"string"}}}}]'
# Exercise the actual Responses route with tools and the configured reasoning level.
probed=""
for task in $TASKS; do
    p="$(task_profile "$task")"
    [ -f "$ROOT/.env.$p" ] || continue
    U="$(pv "$p" PBENCH_LLM_UPSTREAM)"
    K="$(pv "$p" UPSTREAM_AUTH_TOKEN)"
    M="$(pv "$p" ANTHROPIC_MODEL)"
    R="$(pv "$p" COPILOT_AGENT_REASONING_EFFORT)"
    case "$probed" in *"|$U|"*) continue;; esac
    probed="$probed|$U|"
    code=$(upstream_auth_header "$(pv "$p" UPSTREAM_AUTH_STYLE)" "$K" \
        | curl -sS -o /dev/null -w '%{http_code}' --max-time 90 \
        -H @- -H 'content-type: application/json' \
        -X POST "$U/v1/responses" \
        -d "{\"model\":\"$M\",\"input\":\"ok\",\"reasoning\":{\"effort\":\"$R\"},\"tools\":$TOOLSPROBE,\"max_output_tokens\":2000}" 2>/dev/null)
    host="${U#*://}"
    [ "$code" = "200" ] && log "upstream OK [$p] ${host%%/*} $M effort=$R -> HTTP 200" \
                        || { log "FATAL: upstream [$p] ${host%%/*} $M effort=$R -> HTTP $code"; fail=1; }
done

first_p="$(task_profile "${TASKS%% *}")"
PSRC="$ROOT/prompts/agents.txt"
want=$(wc -c < "$PSRC" 2>/dev/null)
img="$(pv "$first_p" AGENT_IMAGE 2>/dev/null)"
got=$(sudo docker run --rm --network none -v "$PSRC:/opt/omcgitea/prompts/agents.md:ro" \
      --entrypoint sh "$img" -c \
      "wc -c < /opt/omcgitea/prompts/agents.md" 2>/dev/null | tr -d ' ')
if [ -n "$want" ] && [ "$got" = "$want" ]; then
    log "prompt OK: prompts/agents.txt = $want bytes (host file reaches the container)"
else
    log "FATAL: prompts/agents.txt reads '$got' bytes in-container, host has $want -- the mount is not effective"
    fail=1
fi

for task in $TASKS; do
    p="$(task_profile "$task")"; ef="$ROOT/.env.$p"
    [ -f "$ef" ] || continue
    # Render the same Compose inputs that Make will use, then verify worker counts.
    make -s render-pbench-base PROFILE="$p" >/dev/null 2>&1 || true
    make -n up PROFILE="$p" >/dev/null 2>&1 || { log "FATAL: make -n up PROFILE=$p fails"; fail=1; continue; }
    ovl=$(make -n up PROFILE="$p" 2>/dev/null | grep -oE '\-f docker/docker-compose[^ ]*' | tr '\n' ' ')
    if ! rendered=$(env -u ANTHROPIC_BASE_URL -u ANTHROPIC_MODEL -u ANTHROPIC_API_KEY -u AGENT_KIND \
            -u COPILOT_PROVIDER_TYPE sudo docker compose -f "$ROOT/docker/_gen-prod.$p.yml" $ovl \
            --project-name "omcgitea-$p" --env-file "$ef" config 2>/dev/null); then
        log "FATAL: $p compose config FAILED to render -- tasks would exit in 60s scoring 0.00%"
        fail=1; continue
    fi
    na=$(grep -cE '^  agent-worker[0-9]+:' <<<"$rendered")
    nl=$(grep -oE 'AGENTS: .*' <<<"$rendered" | head -1 | tr ',' '\n' | grep -cE -- '-worker[0-9]+')
    if [ "$na" = "$WORKERS" ] && [ "$nl" = "$WORKERS" ]; then
        log "compose OK: $p renders $na agent services and a $nl-name AGENTS list"
    else
        log "FATAL: $p renders $na agent services / $nl AGENTS names, expected $WORKERS each"
        fail=1
    fi

done

[ "$fail" = "0" ] || { log "preflight FAILED — nothing launched"; exit 1; }
log "preflight OK: $n_tasks profiles, copilot path, host guards, /v1/responses tools+high live"
if [ "${PREFLIGHT_ONLY:-0}" = "1" ]; then
    log "PREFLIGHT_ONLY=1 -- not launching"
    exit 0
fi

eta_h=$(python3 -c "print(f'{$n_tasks * float(\"$HOURS\"):.1f}')")
log "=== launching $n_tasks tasks x ${HOURS}h (~${eta_h}h), run $SUFFIX ==="
run_chain
log "=== single-node launch $SUFFIX complete ==="
