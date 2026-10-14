#!/usr/bin/env bash
# Multi-node launcher: runs TASKS one after another on AKS, each on profile
# pbench-<mode>-<task> in namespace <profile>, with WORKERS agents packed 64 per
# Standard_D32ds_v5 node (1,024 agents = 16 nodes), for HOURS of wall-clock.
#
#   launch_multi_node.sh [main|smoke]   (or PBENCH_MULTI_NODE_MODE)
#     main   MODE=multi-node: 6h, a 30s-then-3s wake ramp, run and eval through
#            pbench_chain.sh
#     smoke  MODE=multi-node-smoke: 10 minutes, 3s stagger, stop at the budget,
#            one task, the runner called directly
#
#   TASKS     task ids, space-separated (default: pandoc)
#   WORKERS   agents per namespace; every profile must carry it (default 1024)
#   HOURS     wall-clock hours per task (default per mode)
#   RUN_ID    names this launch (default: the UTC start time)
#   PREFLIGHT_ONLY=1   validate everything, launch nothing
#   PBENCH_MULTI_NODE_REUSE_PREPARED=0   smoke refuses an existing namespace
#
# Profiles come from scripts/pbench_gen_env.sh. Every check below is FATAL, and
# nothing launches unless all pass.
#
# Logs: out/<mode>.driver.log; main adds out/chain-<profile>.{log,summary};
# the runner writes out/pbench-<task>-<mode>.<RUN_ID>.log.
# Trajectories: $TRAJ_ROOT/<task>.<mode>.<RUN_ID> (default ~/pbench-trajectories).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || { echo "FATAL: cannot cd $ROOT" >&2; exit 1; }

WORKERS="${WORKERS:-1024}"
MODE_ARG="${PBENCH_MULTI_NODE_MODE:-${1:-main}}"

multi_node_configure_mode() {
    local mode="${1:-main}"
    case "$mode" in
        main)
            MODE=multi-node
            HOURS="${HOURS:-6}"
            # Two-stage ramp: 120 workers in the first hour, then the remaining
            # 904 at 3s each (~45 minutes).
            PBENCH_WAKE_STAGGER_S=30
            PBENCH_WAKE_FAST_STAGGER_S=3
            PBENCH_WAKE_RAMP_SUBJ_S=3600
            PBENCH_WAKE_STOP_AT_BUDGET=0
            MULTI_NODE_DIRECT=0
            ;;
        smoke)
            MODE=multi-node-smoke
            HOURS="${HOURS:-0.16666666666666666}" # 10 minutes
            PBENCH_WAKE_STAGGER_S=3
            PBENCH_WAKE_FAST_STAGGER_S=3
            PBENCH_WAKE_RAMP_SUBJ_S=0
            PBENCH_WAKE_STOP_AT_BUDGET=1
            MULTI_NODE_DIRECT=1
            ;;
        *)
            echo "FATAL: mode '$mode' must be 'main' or 'smoke'" >&2
            return 2
            ;;
    esac

    # The wake cadence absorbs ready waiting; no fixed settle is added.
    PBENCH_BRINGUP_SETTLE_S=0

    # Node reservation and the agent-image pull happen before the clock starts.
    # Both are opt-in in the runner.
    PBENCH_K8S_PREWARM="${PBENCH_K8S_PREWARM:-1}"
    PBENCH_K8S_PREPULL_AGENT="${PBENCH_K8S_PREPULL_AGENT:-1}"
    PBENCH_PREPULL_EXPECTED_NODES="${PBENCH_PREPULL_EXPECTED_NODES:-16}"
    PBENCH_POD_READY_TIMEOUT_S="${PBENCH_POD_READY_TIMEOUT_S:-900}"

    # MySQL sized for 1,024 agents. The generators default to 128 MiB / 20 GiB
    # for every smaller launch.
    MYSQL_INNODB_BUFFER_POOL_SIZE="${MYSQL_INNODB_BUFFER_POOL_SIZE:-8589934592}"
    PBENCH_MYSQL_SIZE="${PBENCH_MYSQL_SIZE:-512Gi}"
    PBENCH_SC_DISK="${PBENCH_SC_DISK:-managed-csi-premium}"

    export PBENCH_WAKE_STOP_AT_BUDGET MULTI_NODE_DIRECT
    export PBENCH_WAKE_STAGGER_S PBENCH_WAKE_FAST_STAGGER_S
    export PBENCH_WAKE_RAMP_SUBJ_S PBENCH_BRINGUP_SETTLE_S
    export PBENCH_K8S_PREWARM PBENCH_K8S_PREPULL_AGENT
    export PBENCH_PREPULL_EXPECTED_NODES PBENCH_POD_READY_TIMEOUT_S
    export MYSQL_INNODB_BUFFER_POOL_SIZE PBENCH_MYSQL_SIZE PBENCH_SC_DISK
}
multi_node_configure_mode "$MODE_ARG" || exit $?

TASKS="${TASKS:-jgm__pandoc.5caad90}"
mkdir -p "$ROOT/out"
source "$ROOT/scripts/lib_launch.sh"
mkdir -p "$TRAJ_ROOT"

# gen-k8s.py and pbench_k8s_up.sh have no defaults for these, so a run cannot
# silently resolve images against another registry or tenant.
ACR="${PBENCH_ACR:-agensteamacr}"
export PBENCH_ACR="$ACR"
export PBENCH_REGISTRY="${PBENCH_REGISTRY:-${ACR}.azurecr.io}"
# pbench_k8s_up.sh needs it to attach the ACR pull identity.
export AZ_SUBSCRIPTION="${AZ_SUBSCRIPTION:-a2bd7a81-579e-45e8-8d88-22db48695abd}"

# Support images, pinned by digest from these ACR tags. Never :local in ACR:
# other fleets pull that tag.
SUPPORT_IMAGES=(
  "omcgitea-board:pbench"
  "omcgitea-mini-router:pbench"
  "omcgitea-bootstrap:pbench"
  "omcgitea-secret-service:pbench"
)
# repo -> build context, for the freshness check: every tracked file there goes
# into the image (mini-router's package files and tsconfig.json as well as src/).
# mcp-board is a ConfigMap on k8s and needs no rebuild.
declare -A IMG_SRC=(
  [omcgitea-board]="board-service"
  [omcgitea-mini-router]="mini-router"
  [omcgitea-secret-service]="secret-service"
  [omcgitea-bootstrap]="docker/bootstrap"
)
# The per-task agent images are built from here (docker/agent/Dockerfile bakes
# in entrypoint.sh, config/ and prompts/team/).
AGENT_SRC="docker/agent"
AGENT_TAG=pbench

# A profile value, whole ($1 env file, $2 key): `print $2` would cut a token or
# URL at its first '='.
pv() { awk -F= -v k="$2" '$1==k{print substr($0, length(k) + 2); exit}' "$1"; }

# Millicores from either "900m" or "2".
mcpu() { case "$1" in *m) echo "${1%m}" ;; *) echo $(( ${1%%.*} * 1000 )) ;; esac; }
n_tasks=$(wc -w <<<"$TASKS")

# The MySQL capacity 1,024 agents need. A profile value counts only when the
# launch environment has none, matching Compose/gen-k8s precedence after
# scrub_shadowed_env has removed a conflicting shell override.
multi_node_validate_mysql_capacity() {  # $1 optional profile env file
    local ef="${1:-}" bad=0 buffer size storage_class
    buffer="${MYSQL_INNODB_BUFFER_POOL_SIZE:-}"
    size="${PBENCH_MYSQL_SIZE:-}"
    storage_class="${PBENCH_SC_DISK:-}"
    if [ -n "$ef" ] && [ -r "$ef" ]; then
        [ -n "$buffer" ] || buffer="$(pv "$ef" MYSQL_INNODB_BUFFER_POOL_SIZE)"
        [ -n "$size" ] || size="$(pv "$ef" PBENCH_MYSQL_SIZE)"
        [ -n "$storage_class" ] || storage_class="$(pv "$ef" PBENCH_SC_DISK)"
    fi
    if [ "$buffer" != "8589934592" ]; then
        log "FATAL: effective MYSQL_INNODB_BUFFER_POOL_SIZE=${buffer:-unset}, expected 8589934592 for 1,024 agents"
        bad=1
    fi
    if [ "$size" != "512Gi" ]; then
        log "FATAL: effective PBENCH_MYSQL_SIZE=${size:-unset}, expected 512Gi for 1,024 agents"
        bad=1
    fi
    if [ "$storage_class" != "managed-csi-premium" ]; then
        log "FATAL: effective PBENCH_SC_DISK=${storage_class:-unset}, expected managed-csi-premium for 1,024 agents"
        bad=1
    fi
    return "$bad"
}

# --- Preflight --------------------------------------------------------------
log "preflight over $n_tasks task(s), run $SUFFIX, k8s path, registry=$PBENCH_REGISTRY"
fail=0

# scrub_shadowed_env (lib_launch.sh): the profile, not the launch shell,
# decides what runs.
for task in $TASKS; do
    scrub_shadowed_env "$ROOT/.env.$(task_profile "$task")"
done

# True when namespace <profile> holds exactly the profile's private gateway
# relay (Pod, Service, Secret, ConfigMap, NetworkPolicy, one owner) and nothing
# else. Main creates that relay before the launch, so it is the only existing
# namespace main accepts.
multi_node_relay_only_namespace() {  # $1 profile (= namespace)  $2 profile env
    local profile="$1" ef="$2" ns="$1"
    local upstream authority host relay_name ns_json inventory
    upstream="$(pv "$ef" PBENCH_LLM_UPSTREAM)"
    authority="${upstream#*://}"; authority="${authority%%/*}"
    host="${authority%%:*}"; relay_name="${host%%.*}"
    case "$relay_name" in omcgitea-gateway-relay-*) : ;; *) return 1 ;; esac
    [ "$host" = "$relay_name.$ns.svc.cluster.local" ] || return 1

    ns_json="$(kubectl get namespace "$ns" -o json 2>/dev/null)" || return 1
    printf '%s' "$ns_json" | python3 -c '
import json, sys
want = sys.argv[1]
try:
    got = json.load(sys.stdin)["metadata"].get("labels", {}).get("pbench-profile")
except Exception:
    raise SystemExit(1)
raise SystemExit(0 if got == want else 1)
' "$profile" || return 1

    inventory="$(kubectl -n "$ns" get \
        pod,service,secret,configmap,networkpolicy,statefulset,deployment,daemonset,job,cronjob,persistentvolumeclaim \
        -o json 2>/dev/null)" || return 1
    printf '%s' "$inventory" | python3 -c '
import json, sys
relay, profile = sys.argv[1:]
required = {"Pod", "Service", "Secret", "ConfigMap", "NetworkPolicy"}
try:
    items = json.load(sys.stdin)["items"]
except Exception:
    raise SystemExit(1)
seen = []
owner = None
for item in items:
    kind = item.get("kind")
    meta = item.get("metadata") or {}
    name = meta.get("name")
    labels = meta.get("labels") or {}
    if kind == "ConfigMap" and name == "kube-root-ca.crt":
        continue
    run = labels.get("pbench-relay-run")
    if (kind not in required or name != relay
            or labels.get("app") != "pbench-gateway-relay"
            or labels.get("pbench-profile") != profile
            or not run or (owner is not None and run != owner)):
        raise SystemExit(1)
    owner = run
    seen.append(kind)
raise SystemExit(0 if len(seen) == len(required) and set(seen) == required else 1)
' "$relay_name" "$profile"
}

refuse_double_launch || fail=1

# --- cluster reachable, and the namespace is free ---------------------------
if ! kubectl get nodes >/dev/null 2>&1; then
    log "FATAL: kubectl cannot reach the cluster — run: az aks get-credentials -g h100 -n agensteam-aks --overwrite-existing"
    fail=1
fi

for task in $TASKS; do
    p="$(task_profile "$task")"; ef="$ROOT/.env.$p"
    [ -f "$ef" ] || { log "FATAL: .env.$p missing — run scripts/pbench_gen_env.sh"; fail=1; continue; }
    v() { pv "$ef" "$1"; }
    multi_node_validate_mysql_capacity "$ef" || fail=1

    # --- the k8s path, not a second compose stack on this host ---------------
    orch="$(v PBENCH_ORCHESTRATOR)"
    [ "$orch" = "k8s" ] || { log "FATAL: .env.$p PBENCH_ORCHESTRATOR='$orch' expected k8s — this would build a second stack on THIS host"; fail=1; }
    # The namespace is the profile. Main needs it absent, or holding only its
    # own private relay. The smoke may reuse a prepared namespace only when it
    # holds exactly the 1,024-slot/16-node placeholder baseline and no agent Pod.
    ns="$p"
    if kubectl get ns "$ns" >/dev/null 2>&1; then
        if [ "$MODE" = multi-node-smoke ] && [ "${PBENCH_MULTI_NODE_REUSE_PREPARED:-1}" = "1" ]; then
            _agents="$(kubectl -n "$ns" get pods -l app=agent --no-headers 2>/dev/null | wc -l)"
            _held="$(kubectl -n "$ns" get pods -l app=pbench-prewarm \
                --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)"
            _shape="$(kubectl -n "$ns" get pods -l app=pbench-prewarm \
                --field-selector=status.phase=Running \
                -o 'jsonpath={range .items[*]}{.spec.nodeName}{"\n"}{end}' 2>/dev/null \
                | sed '/^$/d' | sort | uniq -c)"
            if [ "$_agents" -eq 0 ] && [ "$_held" -eq "$WORKERS" ] \
               && printf '%s\n' "$_shape" | awk -v want=64 '
                    NF == 2 {nodes++; if ($1 != want) bad=1}
                    END {exit !(nodes == 16 && !bad)}'; then
                log "prepared namespace OK: $ns has $WORKERS Running placeholders on 16 nodes x 64 and zero agent Pods"
            else
                log "FATAL: existing namespace $ns is not the exact prepared smoke baseline (agents=$_agents held=$_held)"
                fail=1
            fi
        elif [ "$MODE" = multi-node ] && multi_node_relay_only_namespace "$p" "$ef"; then
            log "relay namespace OK: $ns contains only the exact profile-owned private relay"
        else
            log "FATAL: namespace $ns already exists and is not an exact relay-only launch namespace — tear it down first (PROFILE=$p bash scripts/pbench_k8s_down.sh)"
            fail=1
        fi
    fi

    # --- placement: by CPU request, and pinning must be absent ---------------
    # The autoscaler simulates a node-group template with no hostname, so a pod
    # pinned to a node that does not exist yet triggers no scale-up and Pends
    # forever.
    nodes="$(v PBENCH_AGENT_NODES)"
    [ -z "$nodes" ] || {
        log "FATAL: .env.$p sets PBENCH_AGENT_NODES='$nodes' — autoscaled nodes must be selected by the 64-Pod CPU packing contract, not hostnames"
        fail=1
    }
    acpu="$(v PBENCH_AGENT_CPU)"
    [ -n "$acpu" ] || { log "FATAL: .env.$p has no PBENCH_AGENT_CPU"; fail=1; }
    # The request is the placement mechanism. A D32ds_v5 has 31,580m
    # allocatable and daemonsets reserve 310m. With a 100m router sidecar,
    # 64 x 483m + 310m = 31,222m fits and 65 x 483m + 310m = 31,705m does not.
    if [ -n "$acpu" ]; then
        am=$(mcpu "$acpu")
        pn=$(( (31580 - 310) / (am + 100) ))
        if [ "$am" = "383" ] && [ "$pn" = "64" ]; then
            log "cpu OK: ${am}m+100m router => $pn agents/node, $WORKERS agents => $(( (WORKERS + 63) / 64 )) nodes"
        else
            log "FATAL: PBENCH_AGENT_CPU=$acpu packs $pn agents/node, expected exactly 383m and 64/node — $WORKERS agents would converge on $(( (WORKERS + pn - 1) / pn )) nodes, not 16"
            fail=1
        fi
    fi

    # Copilot's SQLite session store must not sit on the Azure Files share:
    # CIFS serves no fcntl byte-range locks, so every prompt ends in ~10s with
    # session.error "database is locked" and never reaches the model, while all
    # pods read 2/2 Running. The entrypoint also refuses to start on it; this
    # check fails in seconds instead of after a full bringup.
    sd="$(v COPILOT_STATE_DIR)"
    if [ -z "$sd" ]; then
        log "FATAL: .env.$p sets no COPILOT_STATE_DIR — on k8s \$HOME is the Azure Files share, where Copilot's SQLite session store cannot take a lock"
        fail=1
    else
        case "$sd" in
            /opt/data-root*|/opt/data/*)
                log "FATAL: .env.$p COPILOT_STATE_DIR='$sd' is on the Azure Files share — that is the exact path that fails"
                fail=1 ;;
            *) log "state OK: COPILOT_STATE_DIR=$sd (off the SMB share)" ;;
        esac
    fi

    # --- the copilot wire contract (as on single-node) -----------------------
    k="$(v AGENT_KIND)"
    [ "$k" = "copilot" ] || { log "FATAL: .env.$p AGENT_KIND=$k expected copilot"; fail=1; }
    m="$(v ANTHROPIC_MODEL)"
    [ "$m" = "gpt-5.6-sol" ] || { log "FATAL: .env.$p ANTHROPIC_MODEL=$m expected gpt-5.6-sol"; fail=1; }
    o="$(v UPSTREAM_PATH_OVERRIDE)"
    [ -z "$o" ] || { log "FATAL: .env.$p UPSTREAM_PATH_OVERRIDE='$o' must be empty on the responses transport"; fail=1; }
    w="$(v COPILOT_PROVIDER_WIRE_API)"
    [ "$w" = "responses" ] || { log "FATAL: .env.$p COPILOT_PROVIDER_WIRE_API='$w' expected responses — the bare model id is Responses-only"; fail=1; }
    r="$(v COPILOT_AGENT_REASONING_EFFORT)"
    [ "$r" = "high" ] || { log "FATAL: .env.$p COPILOT_AGENT_REASONING_EFFORT='$r' expected high"; fail=1; }
    cw="$(v COPILOT_PROVIDER_MAX_PROMPT_TOKENS)"
    [ "$cw" = "272000" ] || { log "FATAL: .env.$p COPILOT_PROVIDER_MAX_PROMPT_TOKENS='$cw' expected 272000 — Copilot otherwise falls back to a 128000 window"; fail=1; }

    # --- the 1,024-agent capacity contract -----------------------------------
    gw="$(v PBENCH_WORKERS_PER_TEAM)"
    [ "$gw" = "$WORKERS" ] || { log "FATAL: .env.$p PBENCH_WORKERS_PER_TEAM=$gw expected $WORKERS"; fail=1; }
    amem="$(v PBENCH_AGENT_MEM)"; alim="$(v PBENCH_AGENT_MEM_LIMIT)"
    [ "$amem" = "1Gi" ] || { log "FATAL: .env.$p PBENCH_AGENT_MEM=$amem expected 1Gi"; fail=1; }
    [ "$alim" = "8Gi" ] || { log "FATAL: .env.$p PBENCH_AGENT_MEM_LIMIT=$alim expected 8Gi"; fail=1; }
    mmmax="$(v MM_MAX_USERS_PER_TEAM)"
    [ "$mmmax" = "2048" ] || { log "FATAL: .env.$p MM_MAX_USERS_PER_TEAM=$mmmax expected 2048 for 1,024 workers plus administrator"; fail=1; }
    mysqlmax="$(v MYSQL_MAX_CONNECTIONS)"
    [ "$mysqlmax" = "5000" ] || { log "FATAL: .env.$p MYSQL_MAX_CONNECTIONS=$mysqlmax expected 5000 for 1,024 mini-router pools plus service pools"; fail=1; }
    gdb="$(v GITEA_DB_TYPE)"; gopen="$(v GITEA_DB_MAX_OPEN)"; gidle="$(v GITEA_DB_MAX_IDLE)"
    [ "$gdb" = "mysql" ] || { log "FATAL: .env.$p GITEA_DB_TYPE=$gdb expected mysql at 1,024-agent write volume"; fail=1; }
    [ "$gopen" = "200" ] || { log "FATAL: .env.$p GITEA_DB_MAX_OPEN=$gopen expected 200"; fail=1; }
    [ "$gidle" = "50" ] || { log "FATAL: .env.$p GITEA_DB_MAX_IDLE=$gidle expected 50"; fail=1; }
    fsize="$(v PBENCH_FILES_SIZE)"
    [ "$fsize" = "256Gi" ] || { log "FATAL: .env.$p PBENCH_FILES_SIZE=$fsize expected 256Gi for 1,024 durable agent homes"; fail=1; }
    mw="$(v MERGE_WATCH_REPO)"
    [ "$mw" = "pbench/main" ] || { log "FATAL: .env.$p MERGE_WATCH_REPO='$mw' expected pbench/main — merge notices would be off"; fail=1; }
    cg="$(v PBENCH_CI_GATE)"
    [ "$cg" = "0" ] || { log "FATAL: .env.$p PBENCH_CI_GATE='$cg' expected 0"; fail=1; }

    # --- the agent image, resolved in ACR rather than on this host -----------
    # A bare name is correct: gen-k8s.py qualify() prefixes PBENCH_REGISTRY.
    repo="omcgitea-agent-$(short "$task")"
    got="$(v AGENT_IMAGE)"
    case "$got" in
        "$repo:$AGENT_TAG"|*/"$repo:$AGENT_TAG") : ;;
        *) log "FATAL: .env.$p AGENT_IMAGE='$got' expected $repo:$AGENT_TAG"; fail=1 ;;
    esac

    # --- the ProgramBench cleanroom, needed host-side by eval ----------------
    ci="programbench/${task/__/_1776_}:task_cleanroom_v6"
    sudo docker image inspect "$ci" >/dev/null 2>&1 || { log "FATAL: cleanroom missing: $ci — eval cannot score without it"; fail=1; }

    # An unfinished task dir makes the chain salvage a dead run into this
    # launch, and the runner refuses an existing one. There is no data-dir
    # check: on k8s the agents' state lives in the cluster.
    left="$(unfinished_runs "$ROOT/out/$p" | tr '\n' ' ')"
    [ -z "$left" ] || { log "FATAL: out/$p holds unfinished run(s): $left— archive them first"; fail=1; }
done

# --- every variable the k8s bringup demands is set ---------------------------
# Derived from pbench_k8s_up.sh's own `${VAR:?...}` guards, so a variable added
# there is caught here rather than aborting bringup after the preflight passed
# (and leaving eval to score an empty repo 0.00%). PROFILE is set per task.
req_vars="$(grep -oE '\$\{[A-Z_]+:\?' scripts/pbench_k8s_up.sh 2>/dev/null \
            | sed 's/^\${//; s/:?$//' | sort -u | grep -v '^PROFILE$')"
for rv in $req_vars; do
    if [ -n "${!rv:-}" ]; then
        # AZ_SUBSCRIPTION is a tenant id, not a credential, but print it short.
        log "env OK: $rv=${!rv:0:20}"
    else
        log "FATAL: pbench_k8s_up.sh requires $rv and it is unset — bringup would abort AFTER this preflight passes"
        fail=1
    fi
done
# A stale subscription authenticates fine and attaches the pull identity to nothing.
if [ -n "${AZ_SUBSCRIPTION:-}" ]; then
    cur="$(az account show --query id -o tsv 2>/dev/null)"
    if [ -n "$cur" ] && [ "$cur" != "$AZ_SUBSCRIPTION" ]; then
        log "FATAL: AZ_SUBSCRIPTION=$AZ_SUBSCRIPTION but az is logged into $cur"
        fail=1
    fi
fi

# --- image digests, resolved from ACR ---------------------------------------
# Pinning makes the run reproducible and keeps a node from serving a stale
# cached layer for a mutable tag.
#
# The JMESPath: `tags[0]=='x'` misses a manifest that carries x as its second
# tag, and `contains(tags,'x')` returns nothing at all (no error) once any
# manifest in the repo has tags:null. Filter the nulls out first. -r is the
# registry and -n the repository.
acr_digest() {  # $1 repo  $2 tag
    az acr manifest list-metadata -r "$ACR" -n "$1" \
        --query "[?tags != null] | [?contains(tags, '$2')].digest | [0]" -o tsv 2>/dev/null
}
acr_updated() {  # $1 repo  $2 tag -> epoch seconds
    local t
    t=$(az acr manifest list-metadata -r "$ACR" -n "$1" \
        --query "[?tags != null] | [?contains(tags, '$2')].lastUpdateTime | [0]" -o tsv 2>/dev/null)
    [ -n "$t" ] && date -d "$t" +%s 2>/dev/null
}

# A commit timestamp may postdate an image that was built from the same
# then-uncommitted file. Accept that case only when the local image is the exact
# ACR digest and the baked file is byte-for-byte identical to the current source.
acr_image_file_matches() {  # $1 image  $2 ACR digest  $3 path in image  $4 host path
    local image="$1" expected="$2" inside="$3" host="$4"
    local digests
    digests="$(sudo docker image inspect "$image" --format '{{range .RepoDigests}}{{.}} {{end}}' \
        2>/dev/null | tr ' ' '\n' | grep -o 'sha256:[0-9a-f]*' || true)"
    printf '%s\n' "$digests" | grep -Fxq "$expected" || return 1
    image_file_matches "$image" "$inside" "$host"
}

DIGESTS=""
for task in $TASKS; do
    arepo="omcgitea-agent-$(short "$task")"
    case "$DIGESTS" in *"$arepo="*) continue ;; esac
    d="$(acr_digest "$arepo" "$AGENT_TAG")"
    if [ -n "$d" ]; then
        DIGESTS="${DIGESTS}${arepo}=${d},"
        log "digest OK: $arepo:$AGENT_TAG ${d:0:19}…"
    else
        log "FATAL: $arepo:$AGENT_TAG not in $ACR — push it before launching"
        fail=1
        continue
    fi

    # The agent config has two halves that age independently: the templates
    # reach the pod as a ConfigMap from this checkout, while entrypoint.sh is
    # baked into the image. An image older than its entrypoint pairs a new
    # template with an old entrypoint, which can render a config Copilot
    # refuses behind a green 2/2 Running.
    built="$(acr_updated "$arepo" "$AGENT_TAG")"
    cts="$(git -C "$ROOT" log -1 --format=%ct -- "$AGENT_SRC" 2>/dev/null)"
    if [ -n "$built" ] && [ -n "$cts" ] && [ "$cts" -gt "$built" ]; then
        if acr_image_file_matches "$PBENCH_REGISTRY/$arepo:$AGENT_TAG" "$d" \
                /opt/omcgitea/entrypoint.sh "$ROOT/$AGENT_SRC/entrypoint.sh"; then
            log "image OK: $arepo timestamp predates the commit, but ACR/local digest and baked entrypoint bytes match exactly"
        else
            log "FATAL: $ACR/$arepo:$AGENT_TAG built $(date -d @"$built" -u +'%m-%d %H:%M') but $AGENT_SRC last changed $(date -d @"$cts" -u +'%m-%d %H:%M') and exact baked-file attestation failed — rebuild: TASKS=$task bash scripts/pbench_build_pertask_images.sh"
            fail=1
        fi
    elif [ -n "$built" ]; then
        log "image OK: $arepo:$AGENT_TAG ($(date -d @"$built" -u +'%m-%d %H:%M')) is newer than $AGENT_SRC"
    fi

    # Freshness catches "image older than source", not "image renders a config
    # Copilot refuses". Render the pairing k8s deploys: this checkout's
    # mcp.json template against the image's baked entrypoint. Only meaningful
    # when the local image is the digest ACR serves.
    ld="$(sudo docker image inspect "$PBENCH_REGISTRY/$arepo:$AGENT_TAG" \
          --format '{{range .RepoDigests}}{{.}} {{end}}' 2>/dev/null \
          | tr ' ' '\n' | grep -o 'sha256:[0-9a-f]*' | head -1 || true)"
    if [ -z "$ld" ] || [ "$ld" != "$d" ]; then
        log "WARN: cannot verify $arepo's MCP render locally (local ${ld:-none} vs ACR ${d:0:19}…) — the Copilot-valid-config invariant is UNCHECKED for this launch"
    else
        tv="$(sudo docker run --rm --network none \
            -v "$ROOT/$AGENT_SRC/config/mcp.json.tmpl:/tmpl/mcp.json.tmpl:ro" \
            --entrypoint sh "$PBENCH_REGISTRY/$arepo:$AGENT_TAG" -c '
            export AGENT_NODE=/usr/local/bin/node
            export BOARD_SERVICE_URL=http://board-service:8660
            export MCP_TOOL_TIMEOUT_MS=180000
            envsubst < /tmpl/mcp.json.tmpl > /tmp/m.json 2>/dev/null
            sed -n "/^prune_mcp_servers()/,/^}/p" /opt/omcgitea/entrypoint.sh > /tmp/fn.sh
            . /tmp/fn.sh 2>/dev/null && prune_mcp_servers /tmp/m.json
            python3 -c "
import json
d=json.load(open(\"/tmp/m.json\"))
bad=[k for k,v in d[\"mcpServers\"].items() if \"timeout\" in v and not isinstance(v[\"timeout\"],int)]
print(\"BAD:\"+\",\".join(bad) if bad else d[\"mcpServers\"][\"gitea\"][\"timeout\"])
" 2>&1' 2>/dev/null | tail -1 || true)"
        want=180000
        if [ "$tv" = "$want" ]; then
            log "mcp OK: $arepo + host template render integer timeout $tv"
        else
            log "FATAL: $arepo + host template render MCP timeout '$tv', expected integer $want — Copilot answers 'Expected integer' and every ACP child exits rc=1 behind a green 2/2 Running"
            fail=1
        fi
    fi
done
for pair in "${SUPPORT_IMAGES[@]}"; do
    repo="${pair%:*}"; tag="${pair##*:}"
    d="$(acr_digest "$repo" "$tag")"
    if [ -z "$d" ]; then
        log "FATAL: $repo:$tag not in $ACR"; fail=1; continue
    fi
    DIGESTS="${DIGESTS}${repo}=${d},"
    # Freshness by the last commit touching the source, not mtime: a checkout
    # rewrites the mtime of every file that differs.
    src="${IMG_SRC[$repo]:-}"
    built="$(acr_updated "$repo" "$tag")"
    if [ -n "$src" ] && [ -n "$built" ] && [ -d "$ROOT/$src" ]; then
        cts="$(git -C "$ROOT" log -1 --format=%ct -- "$src" 2>/dev/null)"
        if [ -n "$cts" ] && [ "$cts" -gt "$built" ]; then
            log "FATAL: $ACR/$repo:$tag built $(date -d @"$built" -u +'%m-%d %H:%M') but $src last changed $(date -d @"$cts" -u +'%m-%d %H:%M') — rebuild and push"
            fail=1
        else
            log "image OK: $repo:$tag ($(date -d @"$built" -u +'%m-%d %H:%M')) is newer than $src"
        fi
    fi
done
export PBENCH_IMAGE_DIGESTS="${DIGESTS%,}"

# --- the pool can grow to hold the agents ------------------------------------
# What matters is whether the autoscaler is allowed to reach the node count.
# Read the pool from `az aks show`: this identity lacks agentPools/read, and
# `az aks nodepool list` then answers `[]` with exit 0. It also lacks
# agentPools/write, so a too-small max is FATAL with the fix spelled out.
need_nodes=$(( (WORKERS + 63) / 64 ))
pool_json="$(az aks show -g "${AKS_RG:-h100}" -n "${AKS_NAME:-agensteam-aks}" \
             --query "agentPoolProfiles[?name=='${AKS_AGENT_POOL:-agents}'] | [0]" -o json 2>/dev/null || true)"
if [ -z "$pool_json" ] || [ "$pool_json" = "null" ]; then
    log "WARN: could not read the agents pool from az aks show — pool capacity is UNVERIFIED for this launch"
else
    pmax="$(printf '%s' "$pool_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("maxCount") or 0)')"
    pauto="$(printf '%s' "$pool_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("enableAutoScaling"))')"
    pnow="$(printf '%s' "$pool_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("count") or 0)')"
    if [ "$pauto" != "True" ]; then
        log "FATAL: the agents pool has autoscaling DISABLED and sits at $pnow node(s) — nothing will create the $need_nodes this run needs"
        fail=1
    elif [ "$pmax" -lt "$need_nodes" ]; then
        log "FATAL: agents pool max=$pmax < $need_nodes needed — raise it first (needs agentPools/write, which this identity lacks: az aks nodepool update -g ${AKS_RG:-h100} --cluster-name ${AKS_NAME:-agensteam-aks} -n agents --max-count $need_nodes)"
        fail=1
    else
        log "pool OK: agents autoscale $pnow -> max $pmax, need $need_nodes for $WORKERS agents at 64/node"
    fi
fi
# Labelled nodes are not required up front: prewarm is what makes them appear.
have="$(kubectl get nodes -l workload=agents --no-headers 2>/dev/null | wc -l)"
log "pool state: $have node(s) labelled workload=agents right now; prewarm will request $WORKERS slot(s) before the clock starts"

# --- the gateway is alive on the exact wire the run uses ---------------------
# A cluster-local relay URL is not routable from this host. For it, validate
# the supervised relay (its state and ownership) and the matching Service
# endpoint, without a second model request. Any other upstream gets a live
# Responses request with tools + reasoning.effort.
TOOLSPROBE='[{"type":"function","name":"read_file","description":"r","parameters":{"type":"object","properties":{"p":{"type":"string"}}}}]'
GATEWAY_RELAY_SCRIPT="${GATEWAY_RELAY_SCRIPT:-$ROOT/scripts/pbench_k8s_gateway_relay.sh}"
declare -A RELAY_STATE_DIRS=()
multi_node_probe_upstream() {  # $1 profile (= namespace)  $2 profile env
    local profile="$1" ef="$2" ns="$1"
    local U K M R authority host relay_port service route_ns svc_ports addresses
    local state_dir status code
    U="$(pv "$ef" PBENCH_LLM_UPSTREAM)"
    K="$(pv "$ef" UPSTREAM_AUTH_TOKEN)"
    M="$(pv "$ef" ANTHROPIC_MODEL)"
    R="$(pv "$ef" COPILOT_AGENT_REASONING_EFFORT)"
    authority="${U#*://}"; authority="${authority%%/*}"
    host="${authority%%:*}"

    case "$host" in
        *.svc.cluster.local)
            relay_port="${authority##*:}"
            [ "$relay_port" != "$authority" ] || relay_port=80
            service="${host%%.*}"
            route_ns="${host#*.}"; route_ns="${route_ns%%.*}"
            [ "$route_ns" = "$ns" ] || {
                log "FATAL: cluster-local upstream namespace $route_ns does not match profile namespace $ns"
                return 1
            }

            svc_ports="$(kubectl -n "$ns" get service "$service" \
                -o 'jsonpath={.spec.clusterIP}{" "}{range .spec.ports[*]}{.port}{" "}{end}' \
                2>/dev/null || true)"
            addresses="$(kubectl -n "$ns" get endpointslice \
                -l "kubernetes.io/service-name=$service" \
                -o 'jsonpath={range .items[*].endpoints[*].addresses[*]}{.}{"\n"}{end}' \
                2>/dev/null || true)"
            # The relay owns a selector-less Service plus a manually managed
            # Endpoints object, so clusters need not synthesize an EndpointSlice.
            if [ -z "$addresses" ]; then
                addresses="$(kubectl -n "$ns" get endpoints "$service" \
                    -o 'jsonpath={range .subsets[*].addresses[*]}{.ip}{"\n"}{end}' \
                    2>/dev/null || true)"
            fi
            [ -n "$svc_ports" ] && [ -n "$addresses" ] \
                && printf ' %s ' "$svc_ports" | grep -q " $relay_port " || {
                    log "FATAL: relay Service $service in $ns has no live endpoint on port $relay_port"
                    return 1
                }

            state_dir="${PBENCH_GATEWAY_RELAY_STATE_DIR:-}"
            if [ -z "$state_dir" ]; then
                local -a candidates=()
                shopt -s nullglob
                candidates=("$ROOT"/out/pbench-gateway-relay-"$profile"-*)
                shopt -u nullglob
                [ "${#candidates[@]}" -eq 1 ] || {
                    log "FATAL: expected one relay state directory out/pbench-gateway-relay-$profile-*, found ${#candidates[@]}"
                    return 1
                }
                state_dir="${candidates[0]}"
            fi
            status="$(bash "$GATEWAY_RELAY_SCRIPT" status "$state_dir" 2>/dev/null)" || {
                log "FATAL: supervised relay for $profile is not ready"
                return 1
            }
            python3 - "$U" "$status" <<'PY' || {
import json, sys
want, raw = sys.argv[1:]
try:
    got = json.loads(raw)
except Exception:
    raise SystemExit(1)
raise SystemExit(0 if got.get("ready") is True and got.get("endpoint", "").rstrip("/") == want.rstrip("/") else 1)
PY
                log "FATAL: relay status is not ready on the profile's exact endpoint"
                return 1
            }
            # The runner's teardown stops the relay through this exact state
            # directory before deleting the namespace, so no local supervisor
            # outlives the run. Recorded per profile, never exported: a later
            # profile of this launch must resolve, and stop, its own relay.
            RELAY_STATE_DIRS[$profile]="$state_dir"
            log "upstream OK [$profile] supervised private relay + Service endpoint ${host}:$relay_port"
            ;;
        *)
            code=$(upstream_auth_header "$(pv "$ef" UPSTREAM_AUTH_STYLE)" "$K" \
                | curl -sS -o /dev/null -w '%{http_code}' --max-time 90 \
                -H @- -H 'content-type: application/json' \
                -X POST "$U/v1/responses" \
                -d "{\"model\":\"$M\",\"input\":\"ok\",\"reasoning\":{\"effort\":\"$R\"},\"tools\":$TOOLSPROBE,\"max_output_tokens\":2000}" 2>/dev/null)
            [ "$code" = "200" ] && log "upstream OK [$profile] ${host%%/*} $M effort=$R -> HTTP 200" \
                                || { log "FATAL: upstream [$profile] ${host%%/*} $M effort=$R -> HTTP $code"; return 1; }
            ;;
    esac
}

probed=""
for task in $TASKS; do
    p="$(task_profile "$task")"; ef="$ROOT/.env.$p"
    [ -f "$ef" ] || continue
    U="$(pv "$ef" PBENCH_LLM_UPSTREAM)"
    case "$probed" in *"|$U|"*) continue;; esac
    probed="$probed|$U|"
    multi_node_probe_upstream "$p" "$ef" || fail=1
done

# --- the manifests render, and say what they must ----------------------------
# The render is the deployment artifact. One that fails or has the wrong worker
# count makes the runner exit in ~60s, the chain log rc=0, and eval score the
# empty repo 0.00%. It carries real secrets in stringData, so it goes to a 600
# temp file that is removed at once, and nothing below prints matched lines.
for task in $TASKS; do
    prof="$(task_profile "$task")"
    [ -f "$ROOT/.env.$prof" ] || continue
    rf=$(mktemp); chmod 600 "$rf"
    make -s render-pbench-base PROFILE="$prof" >/dev/null 2>&1 || true
    if ! PROFILE="$prof" python3 tools/gen-k8s.py > "$rf" 2>"$rf.err"; then
        log "FATAL: $prof gen-k8s.py FAILED to render — the task would exit in 60s scoring 0.00%"
        sed -n '1,5p' "$rf.err" | while read -r l; do log "    $l"; done
        fail=1; rm -f "$rf" "$rf.err"; continue
    fi
    acpu="$(pv "$ROOT/.env.$prof" PBENCH_AGENT_CPU)"
    # One pass over the parsed manifests: MySQL capacity, replicas, bootstrap
    # AGENTS, placement, images, and the poller and gate.
    if PYTHONWARNINGS=ignore python3 - "$rf" "$WORKERS" "$acpu" "$(pv "$ROOT/.env.$prof" ANTHROPIC_MODEL)" <<'PY'
import sys, yaml
path, want_w, want_cpu = sys.argv[1], int(sys.argv[2]), sys.argv[3]
want_model = sys.argv[4]
docs = [d for d in yaml.safe_load_all(open(path)) if d]
bad = []
mysql = next((d for d in docs if d.get("kind") == "StatefulSet"
              and d.get("metadata", {}).get("name") == "mysql"), None)
if not mysql:
    bad.append("no mysql StatefulSet")
else:
    mysql_c = next((c for c in mysql["spec"]["template"]["spec"]["containers"]
                    if c.get("name") == "mysql"), None)
    args = [str(v) for v in (mysql_c or {}).get("args", [])]
    pool_args = [v for v in args if v.startswith("--innodb-buffer-pool-size=")]
    if pool_args != ["--innodb-buffer-pool-size=8589934592"]:
        bad.append(f"mysql buffer-pool args={pool_args!r}, expected exactly 8589934592")
mysql_pvc = next((d for d in docs if d.get("kind") == "PersistentVolumeClaim"
                  and d.get("metadata", {}).get("name") == "mysql-mysql"), None)
if not mysql_pvc:
    bad.append("no mysql-mysql PersistentVolumeClaim")
else:
    pvc_spec = mysql_pvc.get("spec", {})
    storage = ((pvc_spec.get("resources") or {}).get("requests") or {}).get("storage")
    if storage != "512Gi":
        bad.append(f"mysql-mysql PVC storage={storage!r}, expected '512Gi'")
    if pvc_spec.get("storageClassName") != "managed-csi-premium":
        bad.append(f"mysql-mysql storageClassName={pvc_spec.get('storageClassName')!r}, "
                   "expected 'managed-csi-premium'")
sts = next((d for d in docs if d.get("kind") == "StatefulSet"
            and d["metadata"]["name"] == "agent"), None)
if not sts:
    bad.append("no agent StatefulSet")
else:
    spec = sts["spec"]; pod = spec["template"]["spec"]
    # The model the container really gets. scrub_shadowed_env keeps the launch
    # shell from outranking the profile; this is the check on the artifact.
    if want_model:
        agent_c = next((c for c in pod["containers"] if c["name"] == "agent"), None)
        got = next((e.get("value") for e in (agent_c or {}).get("env", [])
                    if e.get("name") == "ANTHROPIC_MODEL"), None)
        if got is None:
            envfrom = (agent_c or {}).get("envFrom") or []
            src = ", ".join(sorted(
                (r.get("secretRef") or r.get("configMapRef") or {}).get("name", "?")
                for r in envfrom))
            for d in docs:
                if d.get("kind") in ("Secret", "ConfigMap") and d["metadata"]["name"] in src:
                    got = (d.get("stringData") or d.get("data") or {}).get("ANTHROPIC_MODEL", got)
            if got is None:
                bad.append(f"agent env carries no ANTHROPIC_MODEL (envFrom: {src or 'none'})")
        if got is not None and got != want_model:
            bad.append(f"rendered ANTHROPIC_MODEL={got!r} but the profile says {want_model!r} "
                       "-- the launch shell is outranking the profile")
    if spec.get("replicas") != want_w:
        bad.append(f"agent replicas={spec.get('replicas')} expected {want_w}")
    # A real agent needs OrderedReady: CLIs unpacking all at once break.
    # Parallel is only correct for AGENT_KIND=sim.
    if spec.get("podManagementPolicy") != "OrderedReady":
        bad.append(f"podManagementPolicy={spec.get('podManagementPolicy')} expected OrderedReady for a real agent")
    # No pinning, and the CPU request that packs 64 per node: together these
    # are the placement plan.
    if "affinity" in pod:
        bad.append(f"pod has affinity {pod['affinity']} -- a hostname pin against an autoscaled-from-zero pool matches nothing and never triggers a scale-up")
    if pod.get("topologySpreadConstraints"):
        bad.append("pod has topologySpreadConstraints -- maxSkew:1 does not enforce the 64/node packing contract")
    if pod.get("nodeSelector", {}).get("workload") != "agents":
        bad.append(f"nodeSelector {pod.get('nodeSelector')} -- without workload=agents the agents land on the system pool")
    agent_c = next((c for c in pod["containers"] if c["name"] == "agent"), None)
    got_cpu = ((agent_c or {}).get("resources", {}).get("requests", {}) or {}).get("cpu")
    if str(got_cpu) != str(want_cpu):
        bad.append(f"agent cpu request {got_cpu!r} != profile's {want_cpu!r} -- the request IS the node count")
    if "cpu" in ((agent_c or {}).get("resources", {}).get("limits", {}) or {}):
        bad.append("agent has a CPU LIMIT; the request is a placement reservation, and a limit would throttle every compile")
    # An agent owns hours of unrecoverable work in an emptyDir; an
    # under-utilised node must not be drained mid-run.
    ev = ((sts["spec"]["template"]["metadata"].get("annotations") or {})
          .get("cluster-autoscaler.kubernetes.io/safe-to-evict"))
    if ev != "false":
        bad.append(f'safe-to-evict={ev!r}, expected the string "false" -- the autoscaler may drain an under-utilised node mid-run')
    for c in pod["containers"]:
        # Digest-pinned, so a mutable tag cannot change under the fleet.
        if "@sha256:" not in c["image"]:
            bad.append(f"container {c['name']} image not digest-pinned: {c['image']}")
        # Registry-qualified: an unset PBENCH_REGISTRY renders a bare name that
        # pins correctly and sends the kubelet to Docker Hub.
        if "/" not in c["image"].split("@")[0]:
            bad.append(f"container {c['name']} image is not registry-qualified "
                       f"({c['image']}) -- is PBENCH_REGISTRY exported?")
# bootstrap freezes the AGENTS list; an agent above it gets a router that exits
# on `secret-service /tokens/<agent> -> 404`, and OrderedReady stops there.
bs = next((d for d in docs if d.get("kind") == "Secret"
           and d["metadata"]["name"] == "bootstrap-env"), None)
agents = (bs or {}).get("stringData", {}).get("AGENTS", "")
n = len([a for a in agents.split(",") if a.strip()])
if n != want_w:
    bad.append(f"bootstrap AGENTS lists {n} names, expected {want_w}")
# The poller disables itself on an empty repo after one log line, and the gate
# defaults to on.
board = next((d for d in docs if d.get("kind") == "Secret"
              and d["metadata"]["name"] == "board-service-env"), None)
if (board or {}).get("stringData", {}).get("MERGE_WATCH_REPO") != "pbench/main":
    bad.append("board-service renders without MERGE_WATCH_REPO=pbench/main")
if str((bs or {}).get("stringData", {}).get("PBENCH_CI_GATE")) != "0":
    bad.append("bootstrap renders without PBENCH_CI_GATE=0")
# The host prompt reaches k8s as a ConfigMap. Without it the agents silently
# run the prompt baked into the image.
if not any(k.endswith("prompts_team_agents.md")
           for d in docs if d.get("kind") == "ConfigMap"
           for k in (d.get("data") or {})):
    bad.append("prompts/team/agents.md is not in any ConfigMap -- agents would run the image's baked prompt")
for b in bad:
    print(b)
sys.exit(1 if bad else 0)
PY
    then
        log "manifests OK: $prof renders MySQL 8Gi/512Gi/premium, $WORKERS agents, unpinned + ${acpu}/agent (64/node), unevictable, digest-pinned images, poller+gate on, prompt ConfigMap present"
    else
        log "FATAL: $prof manifest assertions failed (see above)"
        fail=1
    fi
    rm -f "$rf" "$rf.err"
done

[ "$fail" = "0" ] || { log "preflight FAILED — nothing launched"; exit 1; }
log "preflight OK: $n_tasks profile(s), k8s path, digests pinned, pool can reach ${need_nodes} nodes, prewarm+prepull on"
log "  PBENCH_IMAGE_DIGESTS=$(echo "$PBENCH_IMAGE_DIGESTS" | tr ',' '\n' | sed 's/=\(sha256:.\{12\}\).*/=\1…/' | tr '\n' ' ')"
if [ "${PREFLIGHT_ONLY:-0}" = "1" ]; then
    log "PREFLIGHT_ONLY=1 -- not launching"
    exit 0
fi

# The smoke calls the runner directly: it already does bootstrap, dispatch,
# collection, export, teardown and eval for one task, and a chain around a
# 10-minute run would only add salvage and a second controller.
multi_node_run_direct() {  # $1 task id
    local task="$1" profile
    profile="$(task_profile "$task")"
    local run_log="$ROOT/out/pbench-${task}-$SUFFIX.log"
    log "smoke: starting $task (${HOURS}h, ${PBENCH_WAKE_STAGGER_S}s stagger) profile=$profile"
    env -u PBENCH_RUN_T0 \
        PROFILE="$profile" \
        TASK="$task" \
        OUT_DIR="$ROOT/out/$profile" \
        PROGRAMBENCH_REPO="$PB_REPO" \
        HOURS="$HOURS" \
        PBENCH_WAKE_STAGGER_S="$PBENCH_WAKE_STAGGER_S" \
        PBENCH_WAKE_FAST_STAGGER_S="$PBENCH_WAKE_FAST_STAGGER_S" \
        PBENCH_WAKE_RAMP_SUBJ_S="$PBENCH_WAKE_RAMP_SUBJ_S" \
        PBENCH_BRINGUP_SETTLE_S="$PBENCH_BRINGUP_SETTLE_S" \
        PBENCH_WAKE_STOP_AT_BUDGET="$PBENCH_WAKE_STOP_AT_BUDGET" \
        PBENCH_K8S_PREWARM="$PBENCH_K8S_PREWARM" \
        PBENCH_K8S_PREPULL_AGENT="$PBENCH_K8S_PREPULL_AGENT" \
        PBENCH_PREPULL_EXPECTED_NODES="$PBENCH_PREPULL_EXPECTED_NODES" \
        PBENCH_POD_READY_TIMEOUT_S="$PBENCH_POD_READY_TIMEOUT_S" \
        MYSQL_INNODB_BUFFER_POOL_SIZE="$MYSQL_INNODB_BUFFER_POOL_SIZE" \
        PBENCH_MYSQL_SIZE="$PBENCH_MYSQL_SIZE" \
        PBENCH_SC_DISK="$PBENCH_SC_DISK" \
        PBENCH_ACR="$PBENCH_ACR" \
        PBENCH_REGISTRY="$PBENCH_REGISTRY" \
        AZ_SUBSCRIPTION="$AZ_SUBSCRIPTION" \
        PBENCH_IMAGE_DIGESTS="$PBENCH_IMAGE_DIGESTS" \
        PBENCH_GATEWAY_RELAY_STATE_DIR="${RELAY_STATE_DIRS[$profile]:-}" \
        PATH="$HOME/.local/bin:$PATH" \
        ./scripts/pbench_run.sh >"$run_log" 2>&1
}

if [ "$MULTI_NODE_DIRECT" = "1" ]; then
    [ "$n_tasks" -eq 1 ] || { log "FATAL: the smoke runs exactly one task, TASKS has $n_tasks"; exit 1; }
    multi_node_run_direct "$TASKS"
    _rc=$?
    log "smoke: runner finished rc=$_rc"
    exit "$_rc"
fi

# --- Launch -----------------------------------------------------------------
# The registry and digest vars go into both phases: gen-k8s.py has no defaults
# for them, and an unpinned render sends the pods into ImagePullBackOff.
LAUNCH_RUN_VARS=(
    PBENCH_ACR PBENCH_REGISTRY AZ_SUBSCRIPTION PBENCH_IMAGE_DIGESTS
    PBENCH_WAKE_STAGGER_S PBENCH_WAKE_FAST_STAGGER_S PBENCH_WAKE_RAMP_SUBJ_S
    PBENCH_BRINGUP_SETTLE_S PBENCH_WAKE_STOP_AT_BUDGET
    PBENCH_K8S_PREWARM PBENCH_K8S_PREPULL_AGENT PBENCH_PREPULL_EXPECTED_NODES
    PBENCH_POD_READY_TIMEOUT_S
    MYSQL_INNODB_BUFFER_POOL_SIZE PBENCH_MYSQL_SIZE PBENCH_SC_DISK
    PBENCH_GATEWAY_RELAY_STATE_DIR
)
LAUNCH_EVAL_VARS=(PBENCH_ACR PBENCH_REGISTRY AZ_SUBSCRIPTION PBENCH_IMAGE_DIGESTS)
# Each task's runner gets its own profile's relay state directory, or none.
launch_profile_env() { PBENCH_GATEWAY_RELAY_STATE_DIR="${RELAY_STATE_DIRS[$1]:-}"; }

eta_h=$(python3 -c "print(f'{$n_tasks * float(\"$HOURS\"):.1f}')")
log "=== launching $n_tasks task(s) x ${HOURS}h (~${eta_h}h), run $SUFFIX ==="
log "=== verify the spread: kubectl -n <profile> get pods -l app=agent -o wide | awk '{print \$7}' | sort | uniq -c  => $need_nodes nodes x 64 ==="
run_chain
log "=== multi-node launch $SUFFIX complete ==="
