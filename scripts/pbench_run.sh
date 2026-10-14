#!/usr/bin/env bash
# ProgramBench runner: one task on one profile. Seeds the task repo into Gitea,
# brings the stack up (docker compose, or AKS when the profile sets
# PBENCH_ORCHESTRATOR=k8s), wakes the workers on a stagger, runs for HOURS,
# exports the submission and tears the stack down.
#
# Called by scripts/pbench_chain.sh and by scripts/launch_multi_node.sh smoke.
#
#   TASK=<instance_id> HOURS=<wall_clock> PROFILE=pbench-<mode>-<task> \
#     scripts/pbench_run.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TASK="${TASK:?TASK=<instance_id> required (e.g. abishekvashok__cmatrix.5c082c6)}"
HOURS="${HOURS:-2}"
OUT_DIR="${OUT_DIR:-$ROOT/out/pbench}"
# Each profile has its own compose project (omcgitea-$PROFILE), data dir
# (DATA_ROOT/$PROFILE), host ports and k8s namespace ($PROFILE).
PROFILE="${PROFILE:?PROFILE=pbench-<mode>-<task> required}"
ENV_FILE="$ROOT/.env.$PROFILE"

# One source of truth for the wall-clock budget. The scale-smoke-only gate below
# and the normal post-ramp wait must stop on the same second.
run_budget_seconds() {
    python3 -c "print(int(round(float('$HOURS')*3600)))"
}

# By default a run finishes its full wake ramp even when it exceeds HOURS. A
# bounded scale smoke opts in to stopping at the budget, because most of its
# 1,024 accounts are deliberately never started during its short capacity check.
wake_budget_expired() {  # optional $1 = now, for deterministic tests
    [ "${PBENCH_WAKE_STOP_AT_BUDGET:-0}" = "1" ] || return 1
    [ -n "${PBENCH_RUN_T0:-}" ] || return 1
    local now="${1:-$(date +%s)}"
    [ "$now" -ge $(( PBENCH_RUN_T0 + $(run_budget_seconds) )) ]
}

run_budget_remaining() {  # $1 total real seconds  $2 elapsed real seconds
    local remain=$(( $1 - $2 )) floor
    if [ "${PBENCH_WAKE_STOP_AT_BUDGET:-0}" = "1" ]; then
        [ "$remain" -lt 0 ] && remain=0
        echo "$remain"
        return
    fi
    floor=60
    [ "$remain" -lt "$floor" ] && remain="$floor"
    echo "$remain"
}
# Shared run-start anchor, epoch ms. Every event the router renders into a
# prompt is expressed as an age relative to THIS instant, so it reads on the
# same run clock as the board's "+{rel}m" and the T-45m / T-5m notices. It
# must be published by the RUNNER, not
# derived per-container: four sidecars starting on a stagger would otherwise
# anchor to four different instants and disagree about how old the same event
# is. Without it each router falls back to its own process start, which is
# close but drifts with restarts.
export PBENCH_RUN_START_MS="${PBENCH_RUN_START_MS:-$(python3 -c 'import time; print(int(time.time()*1000))')}"
DOCKER_ORG="${PROGRAMBENCH_DOCKER_ORG:-programbench}"
REPO="${PBENCH_REPO:-main}"          # the Gitea repo the team works in
PB_REPO="${PROGRAMBENCH_REPO:-$HOME/programbench}"
# docker needs sudo on this host; pbench_submission.py honors PBENCH_DOCKER.
export PBENCH_DOCKER="${PBENCH_DOCKER:-sudo docker}"

# Where the reference binary is parked on the host (root:root 0111) and then
# bind-mounted into every agent at /opt/pbench/executable. gen-compose-prod.py's
# AGENT_BLOCK reads ${PBENCH_BIN:-/dev/null}, so exporting PBENCH_BIN makes the
# real binary mount on a pbench run, while a stack without it gets /dev/null.
BIN_PATH="$OUT_DIR/$TASK/bin/executable"
export PBENCH_BIN="$BIN_PATH"

log() { echo "[pbench] $*" >&2; }
die() { echo "[pbench] FATAL: $*" >&2; exit 1; }

source "$ROOT/scripts/lib_prompts.sh"
command -v envsubst >/dev/null 2>&1 || die "envsubst not found (apt install gettext-base); it renders the prompts under prompts/"

# ORCHESTRATOR. `compose` runs the stack on this host. `k8s` runs the
# same task against the AKS deployment (tools/gen-k8s.py): the stack is brought
# up by scripts/pbench_k8s_up.sh, agents are StatefulSet replicas rather than
# per-agent services, and gitea/mattermost are reached over a port-forward -- so
# every localhost:$EDGE_*_PORT call below works unchanged.
# Read from .env.<profile> first, exactly like PBENCH_WORKERS_PER_TEAM and the other
# topology switches: the deployment target is a property of the profile, not of
# whoever happens to launch it. The env var still wins so a one-off can override,
# and an absent key keeps every existing profile on the single-host compose path.
ORCH="$(grep -E '^PBENCH_ORCHESTRATOR=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d ' \r' || true)"
ORCH="${PBENCH_ORCHESTRATOR:-${ORCH:-compose}}"
case "$ORCH" in
    compose|k8s) ;;
    *) echo "[pbench] FATAL: PBENCH_ORCHESTRATOR='$ORCH' (expected compose|k8s)" >&2; exit 1 ;;
esac
NS="$PROFILE"
# Current-run tunnel ownership. Kept global because both the EXIT teardown and
# the explicit happy-path ending must stop the same supervisor.
PF_PID=""
PF_PIDFILE=""
# The idle watchdog and the deadline reminders, both forked from this shell.
# Global so teardown can stop them: after a die or a signal they would keep
# nudging a torn-down stack for the rest of the budget, and their pbench_run.sh
# command line makes refuse_double_launch refuse the next launch of the profile.
WATCHDOG_PID=""
REMINDER_PID=""
# Resolved the same way as ORCH -- profile first, env override wins -- because
# the prewarm placeholders must reserve exactly what gen-k8s.py gives an agent
# pod, and gen-k8s.py reads this same key from this same file.
AGENT_CPU_REQ="$(grep -E '^PBENCH_AGENT_CPU=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d ' \r' || true)"
AGENT_CPU_REQ="${PBENCH_AGENT_CPU:-${AGENT_CPU_REQ:-2}}"

k8s_agents() {  # replicas
    kubectl -n "$NS" scale statefulset/agent --replicas="$1" >/dev/null 2>&1 || true
}

# OrderedReady is required while real CLIs start, but it also serializes a plain
# scale-to-zero: 1,024 Pods with a 30-second grace period can retain the node pool
# for more than eight hours. First prevent replacements, then submit every agent
# deletion together. --wait=false returns control while their grace periods overlap.
k8s_agents_down() {
    [ "$ORCH" = "k8s" ] || return 0
    k8s_agents 0
    kubectl -n "$NS" delete pods -l app=agent \
        --wait=false --ignore-not-found >/dev/null 2>&1 || true
}

# A private gateway relay is provisioned before the runner and owns both exact
# Kubernetes objects and local supervisor processes. The multi-node launcher
# passes this profile's state directory after preflight; the relay's own stop path
# revalidates namespace UID, resource UIDs, labels, and process start times
# before touching any of them.
k8s_gateway_relay_stop() {
    [ "$ORCH" = "k8s" ] || return 0
    local state_dir="${PBENCH_GATEWAY_RELAY_STATE_DIR:-}"
    [ -n "$state_dir" ] || return 0
    if [ ! -d "$state_dir" ]; then
        log "WARN: gateway relay state directory is missing: $state_dir"
        return 1
    fi
    log "stopping the profile-owned private gateway relay"
    if bash "$ROOT/scripts/pbench_k8s_gateway_relay.sh" stop "$state_dir" >/dev/null; then
        return 0
    fi
    log "WARN: private gateway relay cleanup failed; its ownership checks refused or could not complete"
    return 1
}

# A valid host-side submission makes the live namespace disposable. If export
# failed, retain central Gitea/PVC state for the recovery command but never retain
# agent compute (k8s_agents_down has already run). The relay is not recovery state
# and can pin its selected D32 node, so stop it in both cases.
k8s_finish_teardown() {  # $1: 1 when export succeeded, 0 otherwise
    [ "$ORCH" = "k8s" ] || return 0
    local export_ok="${1:-0}"
    k8s_gateway_relay_stop || true
    if [ "$export_ok" != "1" ]; then
        log "submission export failed; retaining namespace $NS and central PVCs for recovery"
        return 0
    fi
    log "submission preserved; deleting profile namespace $NS"
    if KEEP=0 PROFILE="$PROFILE" NS="$NS" \
            bash "$ROOT/scripts/pbench_k8s_down.sh"; then
        return 0
    fi
    log "WARN: profile namespace cleanup failed"
    return 1
}

# --- node prewarm -------------------------------------------------------------
# The agents pool runs min=0 and the bringup raises the StatefulSet by ONE
# replica per agent under OrderedReady, so at most one pod is ever Pending --
# and the autoscaler sizes a scale-up to the pods pending right now. One pending
# pod asks for one node, so N nodes arrive one at a time at ~5 min each. At 32
# agents on a cold pool that is ~80 min of provisioning, charged unevenly to the
# agents' own working budget, and every ready-wait that overruns posts a wake DM
# into a mini-router that has not connected yet.
#
# Prewarm holds every slot up front with pause pods, so the pool grows in ONE
# scale-up, then hands the slots back one at a time as real agents arrive.
PREWARM="${PBENCH_K8S_PREWARM:-0}"
PREWARM_IMAGE="${PBENCH_PREWARM_IMAGE:-mcr.microsoft.com/oss/kubernetes/pause:3.9}"

cpu_millis() {  # "14" | "14000m" -> 14000
    case "$1" in
        *m) echo "${1%m}" ;;
        *)  echo $(( ${1%%.*} * 1000 )) ;;
    esac
}

# Plain Pods, deliberately: a Deployment would recreate every placeholder we
# release, the replacement would be Pending, and the autoscaler would grow the
# pool past the size we are trying to pin. Nothing recreates a plain pod.
# grace 0 because the slot has to be free BEFORE the agent pod is created, not
# 30 seconds later.
k8s_prewarm_manifest() {  # $1 count  $2 cpu request -> yaml
    local n="$1" cpu="$2" i=0
    while [ "$i" -lt "$n" ]; do
        cat <<YAML
apiVersion: v1
kind: Pod
metadata:
  name: pbench-prewarm-$i
  namespace: $NS
  labels:
    app: pbench-prewarm
spec:
  terminationGracePeriodSeconds: 0
  restartPolicy: Never
  nodeSelector:
    workload: agents
  containers:
  - name: pause
    image: $PREWARM_IMAGE
    resources:
      requests:
        cpu: "$cpu"
        memory: "64Mi"
      limits:
        memory: "64Mi"
---
YAML
        i=$((i + 1))
    done
}

k8s_prewarm_up() {  # $1 slots to reserve
    local n="$1" cpu held=0 nodes=0 deadline
    [ "$PREWARM" = "1" ] || return 0
    [ "$ORCH" = "k8s" ] || return 0
    # One placeholder must reserve exactly what one agent POD reserves: the
    # agent container plus its 100m router sidecar. Reserve less and two
    # placeholders fit where one agent pod will not.
    cpu="$(( $(cpu_millis "${AGENT_CPU_REQ:-${PBENCH_AGENT_CPU:-2}}") + 100 ))m"
    log "prewarm: reserving $n slots at $cpu each so the pool grows in ONE autoscaler pass, not $n serial ones"
    if ! k8s_prewarm_manifest "$n" "$cpu" | kubectl apply -f - >/dev/null 2>&1; then
        log "WARN: prewarm apply failed; falling back to one node per pending pod (slow ramp)"
        return 0
    fi
    deadline=$(( $(date +%s) + ${PBENCH_PREWARM_TIMEOUT_S:-2400} ))
    while [ "$(date +%s)" -lt "$deadline" ]; do
        # `|| true`: under pipefail one transient kubectl error would otherwise
        # abort the runner; wc still prints 0 for it.
        held="$(kubectl -n "$NS" get pods -l app=pbench-prewarm \
                --field-selector=status.phase=Running -o name 2>/dev/null | wc -l || true)"
        nodes="$(kubectl get nodes -l workload=agents --no-headers 2>/dev/null | wc -l || true)"
        [ "$held" -ge "$n" ] && break
        log "prewarm: $held/$n slots held on $nodes node(s); waiting for the autoscaler"
        sleep 30
    done
    if [ "$held" -ge "$n" ]; then
        log "prewarm: all $n slots held on $nodes node(s); the ramp will not wait on Azure"
    else
        log "WARN: prewarm timed out at $held/$n slots on $nodes node(s); the remaining agents will each wait on a node"
    fi
}

k8s_prewarm_release() {  # $1 1-based agent index -> free exactly one slot
    [ "$PREWARM" = "1" ] || return 0
    [ "$ORCH" = "k8s" ] || return 0
    kubectl -n "$NS" delete pod "pbench-prewarm-$(( $1 - 1 ))" \
        --grace-period=0 --ignore-not-found >/dev/null 2>&1 || true
}

# Ungated on the knob on purpose: a run launched with prewarm on and torn down
# after the knob was flipped off would otherwise leave 14-core reservations
# holding a full pool of D32ds_v5 nodes alive.
k8s_prewarm_down() {
    [ "$ORCH" = "k8s" ] || return 0
    kubectl -n "$NS" delete pods -l app=pbench-prewarm \
        --grace-period=0 --ignore-not-found >/dev/null 2>&1 || true
}

# --- exact agent-image preparation --------------------------------------------
# Pause placeholders reserve the nodes but do not populate their kubelet image
# caches. The first real Pod on each cold node then spends ~42s pulling the 4.45
# GB agent image, stretching a nine-second scale-smoke stagger. Opt-in preparation
# runs one exit-only Pod on every node occupied by a Running placeholder, using
# the exact digest-pinned image already rendered into the live StatefulSet.
PREPULL_AGENT="${PBENCH_K8S_PREPULL_AGENT:-0}"
PREPULL_IMAGE_PULL_SECRET=""

k8s_agent_prepull_manifest() {  # $1 exact image; unique node names on stdin
    local image="$1" node i=0
    while IFS= read -r node; do
        [ -n "$node" ] || continue
        cat <<YAML
apiVersion: v1
kind: Pod
metadata:
  name: pbench-agent-prepull-$i
  namespace: $NS
  labels:
    app: pbench-agent-prepull
spec:
  automountServiceAccountToken: false
  terminationGracePeriodSeconds: 0
  restartPolicy: Never
  nodeName: $node
YAML
        if [ -n "${PREPULL_IMAGE_PULL_SECRET:-}" ]; then
            cat <<YAML
  imagePullSecrets:
  - name: $PREPULL_IMAGE_PULL_SECRET
YAML
        fi
        cat <<YAML
  containers:
  - name: prepull
    image: $image
    imagePullPolicy: IfNotPresent
    command: ["/bin/sh", "-c", "exit 0"]
---
YAML
        i=$((i + 1))
    done
}

# Deliberately ungated: an interrupted opt-in preparation must be removable even
# if the environment knob is absent by the time teardown runs.
k8s_agent_prepull_down() {
    [ "$ORCH" = "k8s" ] || return 0
    kubectl -n "$NS" delete pods -l app=pbench-agent-prepull \
        --grace-period=0 --ignore-not-found >/dev/null 2>&1 || true
}

k8s_agent_prepull_up() {
    local image base nodes node_count expected phases total done failed deadline
    [ "$PREPULL_AGENT" = "1" ] || return 0
    [ "$ORCH" = "k8s" ] || return 0

    image="$(kubectl -n "$NS" get statefulset agent \
        -o 'jsonpath={.spec.template.spec.containers[?(@.name=="agent")].image}' \
        2>/dev/null || true)"
    base="${image%@*}"
    case "$image" in *@sha256:*) ;; *)
        log "FATAL: agent image pre-pull requires the live StatefulSet image to be digest-pinned"
        return 1 ;;
    esac
    case "$base" in */*) ;; *)
        log "FATAL: agent image pre-pull requires a registry-qualified live StatefulSet image"
        return 1 ;;
    esac

    PREPULL_IMAGE_PULL_SECRET="$(kubectl -n "$NS" get statefulset agent \
        -o 'jsonpath={.spec.template.spec.imagePullSecrets[0].name}' \
        2>/dev/null || true)"
    nodes="$(kubectl -n "$NS" get pods -l app=pbench-prewarm \
        --field-selector=status.phase=Running \
        -o 'jsonpath={range .items[*]}{.spec.nodeName}{"\n"}{end}' \
        2>/dev/null | sed '/^$/d' | LC_ALL=C sort -u || true)"
    node_count="$(printf '%s\n' "$nodes" | sed '/^$/d' | wc -l)"
    [ "$node_count" -gt 0 ] || {
        log "FATAL: agent image pre-pull found no nodes occupied by Running placeholders"
        return 1
    }
    expected="${PBENCH_PREPULL_EXPECTED_NODES:-}"
    if [ -n "$expected" ] && [ "$node_count" -ne "$expected" ]; then
        log "FATAL: agent image pre-pull found $node_count occupied node(s), expected $expected"
        return 1
    fi

    # Clear only this namespace's labelled leftovers from an interrupted attempt,
    # then create all node-pinned Pods in one apply so pulls proceed concurrently.
    k8s_agent_prepull_down
    log "prepull: caching the live digest-pinned agent image on $node_count occupied node(s) before the run clock"
    if ! printf '%s\n' "$nodes" | k8s_agent_prepull_manifest "$image" \
            | kubectl apply -f - >/dev/null 2>&1; then
        log "FATAL: could not create agent image pre-pull Pods"
        k8s_agent_prepull_down
        return 1
    fi

    deadline=$(( $(date +%s) + ${PBENCH_PREPULL_TIMEOUT_S:-1800} ))
    while [ "$(date +%s)" -lt "$deadline" ]; do
        phases="$(kubectl -n "$NS" get pods -l app=pbench-agent-prepull \
            -o 'jsonpath={range .items[*]}{.status.phase}{"\n"}{end}' \
            2>/dev/null || true)"
        total="$(printf '%s\n' "$phases" | grep -c . || true)"
        done="$(printf '%s\n' "$phases" | grep -c '^Succeeded$' || true)"
        failed="$(printf '%s\n' "$phases" | grep -c '^Failed$' || true)"
        if [ "$failed" -gt 0 ]; then
            log "FATAL: $failed/$node_count agent image pre-pull Pod(s) failed"
            k8s_agent_prepull_down
            return 1
        fi
        if [ "$total" -eq "$node_count" ] && [ "$done" -eq "$node_count" ]; then
            log "prepull: exact agent image cached on all $node_count occupied node(s)"
            k8s_agent_prepull_down
            return 0
        fi
        log "prepull: $done/$node_count occupied node(s) complete"
        sleep 15
    done

    log "FATAL: agent image pre-pull timed out before all $node_count occupied nodes completed"
    k8s_agent_prepull_down
    return 1
}

# RFC3339 (.status.startTime) -> seconds of age, or empty when the field is not
# there yet. Empty means "cannot tell", and every caller skips rather than
# inventing a number from a missing field.
k8s_pod_age() {  # $1 startTime  $2 now -> seconds
    local t="$1" now="$2" epoch
    [ -n "$t" ] || return 0
    epoch="$(date -d "$t" +%s 2>/dev/null)" || return 0
    [ -n "$epoch" ] || return 0
    echo $(( now - epoch ))
}

# Keep the edge port-forward alive for the whole run. Run in the BACKGROUND;
# it never returns.
#
# `set +e` IS THE ENTIRE POINT OF THIS FUNCTION -- do not remove it.
# This runs as a background subshell, and a background subshell INHERITS the
# `set -euo pipefail` at the top of this script. Under errexit, a command that
# fails in a `while` BODY aborts the loop, so without it
#
#     ( while :; do kubectl ... port-forward ... >/dev/null 2>&1; sleep 2; done ) &
#
# is a ONE-SHOT wearing a loop's clothing: the first time the forward exits,
# the supervisor dies with it and nothing is bound on either port for the rest
# of the run. Every later wake DM, the task-channel post, the reminders and
# finally the SUBMISSION EXPORT then fail against a dead tunnel, and the
# export's non-zero return kills the script before teardown, leaving the nodes
# up. One inherited shell option, that whole chain.
#
# STDERR GOES TO A FILE, NOT /dev/null, so why a forward exited can be
# diagnosed afterwards. The cost of keeping it is a few KB.
# Block until the edge tunnel answers again, up to $1 seconds. Returns 1 on
# timeout so the caller can still log its own failure.
#
# Exists because pf_supervise's 2s restart window is invisible to callers: the
# wake loop treats one failed DM lookup as "this agent has no channel" and moves
# on, so that agent is skipped for the whole run. Probes MM_BASE
# rather than gitea because the DM path is what depends on it.
pf_wait_healthy() {  # $1 timeout seconds (default 30)
    local budget="${1:-30}" waited=0
    [ "$ORCH" = "k8s" ] || return 0          # compose has no tunnel to wait on
    while [ "$waited" -lt "$budget" ]; do
        curl -fsS --max-time 5 "${MM_BASE:-}/api/v4/system/ping" >/dev/null 2>&1 && {
            [ "$waited" -gt 0 ] && log "edge tunnel healthy again after ${waited}s"
            return 0
        }
        sleep 2
        waited=$((waited + 2))
    done
    log "WARN: edge tunnel still unhealthy after ${budget}s (see ${PF_LOG:-the port-forward log})"
    return 1
}

pf_supervise() {  # $1 ns  $2 gitea_local_port  $3 mm_local_port  $4 logfile
    local ns="$1" gp="$2" mp="$3" logf="$4" n=0 rc=0 started=0 child=0
    # Both, because pipefail can also abort the loop on a piped failure.
    set +e +o pipefail
    # The pidfile records this supervisor, not its current kubectl. A background
    # function is not a process-group leader with job control off, so killing the
    # supervisor alone would orphan kubectl and leave both local ports bound.
    # Track the child explicitly and forward shutdown to that exact process.
    trap - EXIT
    trap '
        if [ "${child:-0}" -gt 0 ]; then
            kill "$child" 2>/dev/null || true
            wait "$child" 2>/dev/null || true
        fi
        exit 0
    ' TERM INT
    while :; do
        n=$((n + 1))
        started=$(date +%s)
        echo "[pf $(date -u +%FT%TZ)] attempt #$n: forwarding $gp->80 $mp->81 in $ns" >> "$logf"
        kubectl -n "$ns" port-forward svc/nginx-edge "${gp}:80" "${mp}:81" >> "$logf" 2>&1 &
        child=$!
        wait "$child"
        rc=$?
        child=0
        echo "[pf $(date -u +%FT%TZ)] attempt #$n exited rc=$rc after $(( $(date +%s) - started ))s; restarting in 2s" >> "$logf"
        sleep 2
    done
}

pf_stop() {
    local pid="${PF_PID:-}"
    [ -n "$pid" ] || return 0
    # pf_supervise's TERM handler owns its active kubectl child. Waiting here
    # guarantees neither process still owns the local ports when teardown moves on.
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    if [ -n "${PF_PIDFILE:-}" ] && [ -f "$PF_PIDFILE" ] \
        && [ "$(cat "$PF_PIDFILE" 2>/dev/null)" = "$pid" ]; then
        rm -f "$PF_PIDFILE"
    fi
    PF_PID=""
}

stop_background_loops() {
    local pid
    for pid in "$WATCHDOG_PID" "$REMINDER_PID"; do
        [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
    done
    WATCHDOG_PID=""
    REMINDER_PID=""
}

[ -f "$ENV_FILE" ] || die "$ENV_FILE missing (task #1 should have created it)"

# instance_id "a__b.sha" → image "<org>/a_1776_b.sha:task_cleanroom"
img_base="$DOCKER_ORG/$(printf '%s' "$TASK" | sed 's/__/_1776_/')"
# The SEED tag. scripts/pbench_build_pertask_images.sh builds the agent image
# FROM :task_cleanroom_v6, and the two tags are different builds of the task (a
# different upstream commit and different configure flags), so seeding from the
# other one has the team reverse-engineering a binary that is not the one its
# toolchain and grader belong to. Overridable rather than flipped outright:
# compose runs are compared with each other on the default, and silently
# changing the target would make a run incomparable to the rest.
CLEANROOM_TAG="${PBENCH_CLEANROOM_TAG:-task_cleanroom}"
CLEANROOM_IMG="$img_base:$CLEANROOM_TAG"

# Benchmark integrity: refuse to start if a prior run's output dir for this
# task already exists. Re-running the same TASK without removing $OUT_DIR/$TASK
# would mix prior submission.tar.gz / *.eval.json / export.log into this run's
# outputs. Operator must `rm -rf $OUT_DIR/$TASK` before re-running.
if [ -e "$OUT_DIR/$TASK" ]; then
    die "$OUT_DIR/$TASK already exists — leftover output from a prior run would be mixed in. Remove it (\`rm -rf $OUT_DIR/$TASK\`) before re-running."
fi
mkdir -p "$OUT_DIR/$TASK"

# Resolve compose plumbing the same way the Makefile does.
DATA_ROOT="$(grep -E '^DATA_ROOT=' "$ENV_FILE" | cut -d= -f2-)"
DATA_ROOT="${DATA_ROOT:-../.claude-team-data}"
ORG_NAME="$(grep -E '^ORG_NAME=' "$ENV_FILE" | cut -d= -f2-)"

# Benchmark integrity: refuse to start if leftover state from a prior run
# exists. MySQL's agent_kv (acp_session_id), Gitea repo state, Mattermost
# history, and per-agent /opt/data would otherwise persist into this run via
# loadSession() — effectively rejection-sampling the score. Operator must
# `make clean PROFILE=$PROFILE` (DESTRUCTIVE) before re-running.
PROFILE_DATA_DIR="$DATA_ROOT/$PROFILE"
if [ "$ORCH" = "k8s" ]; then
    # The equivalent guard for k8s is pbench_k8s_down.sh, which drops the
    # namespace and its PVCs; there is no host-side data dir to inspect.
    PROFILE_DATA_DIR="/nonexistent-on-k8s"
fi
if [ -e "$PROFILE_DATA_DIR" ]; then
    die "$PROFILE_DATA_DIR already exists — leftover state from a prior run would leak into this one (acp_session_id, gitea repo, mattermost history). Run \`make clean PROFILE=$PROFILE\` first."
fi

# Gitea edge port for cloning the team repo after the run.
EDGE_PORT="$(grep -E '^EDGE_HTTP_PORT=' "$ENV_FILE" | cut -d= -f2-)"
GITEA_ADMIN_USER="$(grep -E '^GITEA_ADMIN_USER=' "$ENV_FILE" | cut -d= -f2-)"
GITEA_ADMIN_PASSWORD="$(grep -E '^GITEA_ADMIN_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"

# Mattermost edge port + admin creds — agents are PASSIVE (mini-router pulls
# Gitea notifications + MM websocket and only then prompts the ACP turn). An
# admin-opened gitea issue with no assignee/@mention notifies nobody, so the
# director never wakes. We therefore drive the team via MM DM/@mention (the
# reliable wakeup path) AND @director on the gitea issue, with a periodic MM
# reminder as a fallback.
EDGE_MM_PORT="$(grep -E '^EDGE_MM_PORT=' "$ENV_FILE" | cut -d= -f2-)"
MATTERMOST_ADMIN_USER="$(grep -E '^MATTERMOST_ADMIN_USER=' "$ENV_FILE" | cut -d= -f2-)"
MATTERMOST_ADMIN_PASSWORD="$(grep -E '^MATTERMOST_ADMIN_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
MATTERMOST_TEAM_NAME="$(grep -E '^MATTERMOST_TEAM_NAME=' "$ENV_FILE" | cut -d= -f2- || true)"
# prod/org compose sets the MM team name to ORG_NAME (see gen-compose-prod.py),
# so default to that rather than the dev "omcgitea".
MATTERMOST_TEAM_NAME="${MATTERMOST_TEAM_NAME:-$ORG_NAME}"
DIRECTOR_AGENT="$(grep -E '^PBENCH_DIRECTOR_AGENT=' "$ENV_FILE" | cut -d= -f2- || true)"
DIRECTOR_AGENT="${DIRECTOR_AGENT:-${ORG_NAME}-director}"
AUDITOR_AGENT="$(grep -E '^PBENCH_AUDITOR_AGENT=' "$ENV_FILE" | cut -d= -f2- || true)"
AUDITOR_AGENT="${AUDITOR_AGENT:-${ORG_NAME}-auditor}"
MM_BASE="http://localhost:${EDGE_MM_PORT}"

# Always export a submission on the way out, even if a step failed/timed out:
# the smoke test asserts submission.tar.gz exists regardless of pass/fail.
export_submission() {
    # Defense against $OUT_DIR/$TASK vanishing (e.g. external mv-to-archive
    # from a parallel driver, or a manual cleanup racing our teardown).
    # Without this, the `2>>export.log` redirect below would fail-open and
    # eat the python export's stderr, and the tar fallback would silently
    # create a file in the wrong place.
    mkdir -p "$OUT_DIR/$TASK"

    # DeLM baselines write source files directly to a shared /work bind-mount
    # (WORK_HOST_PATH) instead of committing to a Gitea repo. When that env is
    # set, use the workdir path; otherwise fall back to gitea export.
    if [ -n "${WORK_HOST_PATH:-}" ] && [ -d "$WORK_HOST_PATH" ]; then
        log "exporting submission from shared workdir $WORK_HOST_PATH → $OUT_DIR/$TASK/"
        if sudo python3 tools/pbench_submission.py export \
            --from-workdir "$WORK_HOST_PATH" --task "$TASK" --out-dir "$OUT_DIR" \
            2>>"$OUT_DIR/$TASK/export.log"; then
            log "submission.tar.gz written from workdir"
            # Fix ownership so downstream (unarchive/eval) can read it as the user
            sudo chown -R "$(id -u):$(id -g)" "$OUT_DIR/$TASK" 2>/dev/null || true
            return 0
        else
            log "WARN: workdir export failed (see export.log); writing empty stub"
            tar -czf "$OUT_DIR/$TASK/submission.tar.gz" -C "$OUT_DIR/$TASK" --files-from /dev/null 2>/dev/null || \
                : > "$OUT_DIR/$TASK/submission.tar.gz"
            return 0
        fi
    fi

    local team_url="http://${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}@localhost:${EDGE_PORT}/${ORG_NAME}/${REPO}.git"
    log "exporting submission from Gitea repo ${ORG_NAME}/${REPO} → $OUT_DIR/$TASK/"
    # Retry with backoff: with a single attempt, one transient 504 is terminal for the whole
    # task. Gitea is quiesced by now (see quiesce_agents) so an attempt
    # that fails is far more likely to be a tail-latency blip than a real outage.
    local attempt
    for attempt in 1 2 3; do
        if python3 tools/pbench_submission.py export \
            --from-gitea "$team_url" --task "$TASK" --out-dir "$OUT_DIR" \
            2>>"$OUT_DIR/$TASK/export.log"; then
            log "submission.tar.gz written (attempt $attempt)"
            rm -f "$OUT_DIR/$TASK/EXPORT_FAILED"
            return 0
        fi
        log "WARN: gitea export attempt $attempt/3 failed (see export.log)"
        [ "$attempt" -lt 3 ] && sleep $(( attempt * 15 ))
    done

    # Every attempt failed. This is NOT a score: an empty-but-valid tarball here would be
    # scored 0.00% with every test not_run, indistinguishable from a team that built
    # nothing, while the repo is intact and only the export failed. Leave a marker so
    # the scorer and a human can tell "we never got the code" from "the code scored zero".
    log "ERROR: gitea export FAILED after 3 attempts — this task has NO submission."
    log "ERROR: the repo is still intact under \$DATA_ROOT; recover with:"
    log "ERROR:   python3 tools/pbench_submission.py export --from-gitea file://<data-root>/gitea/git/repositories/${ORG_NAME}/${REPO}.git --task $TASK --out-dir <dir>"
    {
        echo "export failed after 3 attempts at $(date -u +%FT%TZ)"
        echo "task=$TASK profile=$PROFILE url=localhost:${EDGE_PORT}/${ORG_NAME}/${REPO}.git"
        echo "the gitea repo under DATA_ROOT is intact; this is an export failure, not a zero"
    } > "$OUT_DIR/$TASK/EXPORT_FAILED"
    tar -czf "$OUT_DIR/$TASK/submission.tar.gz" -C "$OUT_DIR/$TASK" --files-from /dev/null 2>/dev/null || \
        : > "$OUT_DIR/$TASK/submission.tar.gz"
    return 1
}

dump_board_lifecycle() {
    # Ask the board to write its per-gist lifecycle log before we tear the
    # profile down. render_count — how many times an entry was actually
    # selected into somebody's window — lives only in the board process, so
    # skipping this loses the one measurement that distinguishes "an agent
    # published" from "a peer read it".
    local bs
    bs=$(sudo docker ps --filter "name=omcgitea-$PROFILE-board-service" \
         --format '{{.Names}}' 2>/dev/null | head -1)
    [ -z "$bs" ] && return 0
    log "dumping board lifecycle from $bs"
    sudo docker exec "$bs" python3 -c "
import json, urllib.request
try:
    boards = json.load(urllib.request.urlopen('http://127.0.0.1:8660/healthz', timeout=5))['boards']
except Exception as e:
    print('healthz failed:', e); raise SystemExit(0)
for b in boards:
    try:
        req = urllib.request.Request(
            f'http://127.0.0.1:8660/board/{b}/lifecycle?viewer=harness', method='POST')
        print(b, json.load(urllib.request.urlopen(req, timeout=15)).get('path'))
    except Exception as e:
        print(b, 'FAILED', e)
" >>"$OUT_DIR/$TASK/board-lifecycle.log" 2>&1 || true
}

TRAJ_SNAPPED=0
snapshot_trajectories_k8s() {
    # Pull every agent's turn log off the pods BEFORE anything scales them down.
    #
    # WHERE THE TURN LOG ACTUALLY IS. tools/gen-k8s.py re-exports
    # AGENT_HOME="/opt/data-root/$AGENT_NAME" in the container command, BEFORE
    # exec'ing the entrypoint, so entrypoint.sh's /opt/data default never
    # applies and the AGENT_HOME=/opt/data seen in `kubectl exec env` is a
    # decoy -- that env var was already overridden by the shell that started the
    # agent. The real HOME is /opt/data-root/<agent>/home, on the Azure Files
    # share, which is mounted read-write in every agent pod.
    #
    # /opt/data does not exist in the pod; /opt/data-root holds every agent's
    # home, and the trajectories on it are durable.
    #
    # `kubectl cp` of a source that does not exist EXITS 0 AND COPIES NOTHING,
    # and the empty result would fall through to the arm below that logs
    # "copied but holds NO jsonl -- that agent never took a turn", a confident
    # claim about the RUN produced by a broken COPY. So the source is resolved
    # by asking the pod, and a pod that exposes no home is an explicit WARN
    # rather than a silent empty dir.
    #
    # Two sources, because COPILOT_STATE_DIR splits them: Copilot's SQLite
    # session store -- which holds session-state/<id>/events.jsonl, the copilot
    # turn log -- cannot live on the share (SQLite gets `database is locked` on
    # CIFS), so it sits on pod-local disk and really does
    # die with the pod. $HOME still carries the claude layout.
    #
    # Idempotent: three teardown paths reach a scale-down (quiesce_agents, the
    # EXIT trap, and the normal end of main) and which ones run depends on how
    # the run ended. Guarding here is cheaper than reasoning about that, and a
    # second pass over deleted pods would otherwise overwrite good data with
    # nothing.
    [ "$ORCH" = "k8s" ] || return 0
    [ "$TRAJ_SNAPPED" = "1" ] && return 0
    TRAJ_SNAPPED=1
    local dst="$OUT_DIR/$TASK/_traj"
    mkdir -p "$dst"
    local pods pod n=0 got=0
    # `|| true` on both pipelines below is load-bearing under `set -euo pipefail`:
    # this runs inside teardown, and a non-zero pipeline in a command
    # substitution kills the script -- taking export_submission and eval with it.
    # kubectl failing here must degrade to "no pods found", not to no result.
    pods="$(kubectl -n "$NS" get pods -l app=agent \
            --field-selector=status.phase=Running -o name 2>/dev/null \
            | sed 's|^pod/||' || true)"
    if [ -z "$pods" ]; then
        log "WARN: trajectory snapshot found NO running agent pods in $NS — nothing to archive"
        return 0
    fi
    for pod in $pods; do
        n=$((n + 1))
        # Copy the whole HOME rather than a per-kind glob. The layout is a
        # property of AGENT_KIND, not of the platform -- claude writes
        # .claude/projects/*/*.jsonl, copilot writes
        # .copilot/session-state/<id>/events.jsonl -- and this arm is
        # COPILOT. Naming only the claude path is the mistake that makes an idle
        # check read every worker as busy: it scans a directory the agent kind
        # in use never creates.
        # kubectl cp takes no globs, so one recursive copy per source covers all
        # three layouts and cannot go stale when a fourth kind is added.
        #
        # Resolve the source IN THE POD. Matching on the worker ordinal mirrors
        # gen-k8s.py (AGENT_NAME=<org>-worker$((i+1)) from HOSTNAME)
        # without hardcoding the org, so the two cannot drift.
        local srcs src label copied=0
        srcs="$(kubectl -n "$NS" exec "$pod" -c agent -- sh -c '
            i=${HOSTNAME##*-}
            for d in /opt/data-root/*worker$((i+1))/home "${COPILOT_STATE_DIR:-}"; do
                [ -n "$d" ] && [ -d "$d" ] && echo "$d"
            done' 2>/dev/null || true)"
        if [ -z "$srcs" ]; then
            log "WARN: trajectory: $pod exposes NO source dir (looked for /opt/data-root/*worker<n>/home and \$COPILOT_STATE_DIR) — nothing archived for it"
            continue
        fi
        for src in $srcs; do
            # /opt/data-root/x/home -> home ; /opt/copilot-state -> copilot-state
            case "$src" in
                */home) label=home ;;
                *)      label="$(basename "$src")" ;;
            esac
            if kubectl -n "$NS" cp "$pod:$src" "$dst/$pod/$label" -c agent >/dev/null 2>&1; then
                copied=$((copied + 1))
            else
                log "WARN: trajectory: kubectl cp failed for $pod:$src"
            fi
        done
        if [ "$copied" -gt 0 ]; then
            local files
            files=$(find "$dst/$pod" -type f -name '*.jsonl' 2>/dev/null | wc -l || true)
            files="${files:-0}"
            if [ "$files" -gt 0 ]; then
                got=$((got + 1))
                log "trajectory: $pod -> _traj/$pod ($files turn-log file(s) from $copied source(s))"
            else
                # Now that the source is known to EXIST and to have been copied,
                # this really is a statement about the run.
                log "WARN: trajectory: $pod copied $copied source(s) but holds NO jsonl — that agent never took a turn"
            fi
        fi
    done
    log "trajectory snapshot: $got/$n agent pod(s) yielded turn logs -> $dst"
}

quiesce_agents() {
    # Stop everything that talks to Gitea, and nothing else. Normal completion
    # calls this after its deadline export; emergency teardown calls it before a
    # best-effort recovery export.
    #
    # An export that runs while the agents are still live on Gitea over MCP, and act_runner
    # can still start CI jobs, contends with them: the clone can take minutes or hit nginx's
    # proxy_read_timeout (300s) as a 504, even for a small repo that clones offline in under
    # a second.
    #
    # gitea, mysql and nginx-edge must SURVIVE this: they are what we are about to clone from.
    if [ "$ORCH" = "k8s" ]; then
        # BEFORE the scale-down, always. /opt/data is the pod's ephemeral layer.
        snapshot_trajectories_k8s
        log "quiesce: deleting agent Pods in parallel after setting StatefulSet replicas to 0 (gitea/mysql stay up)"
        k8s_agents_down
        sleep 10
        return 0
    fi
    local proj="omcgitea-$PROFILE"
    local ids
    # Scoped by the compose PROJECT LABEL, never by name alone. CLAUDE.md forbids touching a
    # container this project did not create, and this host runs other people's clusters.
    ids=$(sudo docker ps -q \
            --filter "label=com.docker.compose.project=$proj" \
            --filter "name=agent-worker" \
            --filter "name=mini-router" \
            --filter "name=act-runner" 2>/dev/null | sort -u)
    if [ -z "$ids" ]; then
        log "quiesce: no agent/router/runner containers running for $proj"
        return 0
    fi
    log "quiesce: stopping $(echo "$ids" | wc -l) agent/router/runner containers (gitea stays up)"
    # A short timeout: these are being torn down anyway, and a graceful stop that waits on an
    # in-flight LLM turn would reintroduce the delay we are removing.
    sudo docker stop -t 10 $ids >/dev/null 2>&1 || true
}

teardown() {
    local rc=$? export_ok=1
    log "teardown (rc=$rc): quiescing agents, exporting submission, stopping profile"
    stop_background_loops
    dump_board_lifecycle || true
    quiesce_agents || true
    export_submission || export_ok=0
    pf_stop
    if [ "$ORCH" = "k8s" ]; then
        # quiesce_agents already preserved trajectories and deleted agent Pods;
        # repeating it here would repeat the serial fleet-wide copy.
        # Remove exit-only image preparation Pods even if preparation was
        # interrupted before its normal pre-clock cleanup.
        k8s_agent_prepull_down
        # Placeholders outlive the StatefulSet otherwise, and each one is a
        # multi-core reservation keeping a D32ds_v5 alive at pool prices.
        k8s_prewarm_down
        k8s_finish_teardown "$export_ok" || true
    else
        make down PROFILE="$PROFILE" >/dev/null 2>&1 || true
    fi
    return 0
}

# --- 1. seed cleanroom workspace into the team repo -------------------------
seed_repo() {
    log "seeding cleanroom workspace from $CLEANROOM_IMG"
    if ! sudo docker image inspect "$CLEANROOM_IMG" >/dev/null 2>&1; then
        log "pulling $CLEANROOM_IMG (first run; agents get NO internet so this MUST happen host-side now)"
        sudo docker pull "$CLEANROOM_IMG" >/dev/null 2>&1 \
            || die "cannot pull $CLEANROOM_IMG (check task id / dockerhub access)"
    fi
    local seed_dir="$OUT_DIR/$TASK/_seed"
    rm -rf "$seed_dir"; mkdir -p "$seed_dir"
    # The reference binary is pulled OUT of the repo tree (never committed; a git
    # blob is world-readable = anti-reverse-engineering leak) and parked at $BIN_PATH, which we then
    # mount root:root 0111 into every agent at /opt/pbench/executable.
    PROGRAMBENCH_DOCKER_ORG="$DOCKER_ORG" \
        python3 tools/pbench_submission.py seed --image "$CLEANROOM_IMG" \
        --into "$seed_dir" --bin-out "$BIN_PATH" \
        || die "seed extraction failed"
    if [ -f "$BIN_PATH" ]; then
        # root:root 0111 — agents (uid 10000) can EXECUTE but never READ the bytes.
        sudo chown 0:0 "$BIN_PATH"
        sudo chmod 0111 "$BIN_PATH"
        log "reference binary staged 0111 at $BIN_PATH (mounted /opt/pbench/executable)"
    else
        log "WARN: no reference binary extracted; agents will get /dev/null mount"
    fi
    log "seed workspace ready at $seed_dir (push into Gitea is handled by bootstrap/initial-commit)"
    # The actual push into the agent team's Gitea repo happens once the stack
    # is up (the repo only exists post-bootstrap). We stage it here and the
    # post-up step commits it.
    echo "$seed_dir" > "$OUT_DIR/$TASK/.seed_path"
}

# --- mattermost helpers (admin session token cached for the whole run) ------
# Agents wake on real MM events (websocket) far more reliably than on a stray
# gitea issue, so the primary task-delivery path is a MM channel/@mention.
MM_ADMIN_TOKEN=""
mm_login() {
    [ -n "$MM_ADMIN_TOKEN" ] && return 0
    [ -n "$EDGE_MM_PORT" ] || { log "WARN: EDGE_MM_PORT unset; MM drive disabled"; return 1; }
    MM_ADMIN_TOKEN=$(curl -sS -i \
        -d "{\"login_id\":\"${MATTERMOST_ADMIN_USER}\",\"password\":\"${MATTERMOST_ADMIN_PASSWORD}\"}" \
        "${MM_BASE}/api/v4/users/login" \
        | awk -F': ' '/^[Tt]oken:/ {gsub(/\r/,""); print $2; exit}')
    [ -n "$MM_ADMIN_TOKEN" ] || { log "WARN: mattermost admin login failed; MM drive disabled"; return 1; }
    return 0
}
mm_user_id() {  # username → id
    mm_login || return 1
    curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" \
        "${MM_BASE}/api/v4/users/username/$1" \
        | jq -r 'select(.status_code == null) | .id // empty'
}
mm_post() {  # channel_id message
    mm_login || return 1
    curl -fsS -H "Authorization: Bearer $MM_ADMIN_TOKEN" -H 'Content-Type: application/json' \
        -X POST -d "$(jq -nc --arg c "$1" --arg m "$2" '{channel_id:$c, message:$m}')" \
        "${MM_BASE}/api/v4/posts" >/dev/null 2>&1
}

# mm_dm_channel <username> → prints channel_id of the admin↔user DM.
# MM's /channels/direct is idempotent — returns the existing one if any.
declare -A MM_DM_CACHE=()
mm_dm_channel() {
    local user="$1"
    if [ -n "${MM_DM_CACHE[$user]:-}" ]; then
        printf '%s' "${MM_DM_CACHE[$user]}"; return 0
    fi
    mm_login || return 1
    local me_id user_id
    me_id="$(mm_user_id "$MATTERMOST_ADMIN_USER")" || return 1
    user_id="$(mm_user_id "$user")" || return 1
    [ -n "$me_id" ] && [ -n "$user_id" ] || return 1
    local ch
    ch=$(curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" -H 'Content-Type: application/json' \
        -X POST -d "[\"$me_id\",\"$user_id\"]" \
        "${MM_BASE}/api/v4/channels/direct" | jq -r '.id // empty')
    [ -n "$ch" ] || return 1
    MM_DM_CACHE[$user]="$ch"
    printf '%s' "$ch"
}

# Open (or reuse) a private task channel pulling in director + auditor, returns
# the channel_id on stdout. Posting a message that @mentions both wakes them.
TASK_CHANNEL_ID=""
# The mattermost MCP takes only a URL + token — upstream exposes no default
# team — so every team-scoped tool (post_message, search_messages,
# list_my_channels) needs ids the agent must otherwise discover. Agents that
# fail that discovery invent 26-char ids, and mattermost answers 403 for a
# team you are not in, which an agent reads as a lockout and goes silent. We
# know both ids here, so we hand them over instead.
MM_TEAM_ID=""
mm_ensure_task_channel() {
    mm_login || return 1
    local team_id
    team_id=$(curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" \
        "${MM_BASE}/api/v4/teams/name/${MATTERMOST_TEAM_NAME}" | jq -r 'select(.status_code == null) | .id // empty')
    if [ -z "$team_id" ]; then
        # Bootstrap may have skipped MM provisioning (reused .bootstrap-done
        # mark after a data wipe). Create the team so the drive path still works.
        log "MM team ${MATTERMOST_TEAM_NAME} missing; creating it"
        team_id=$(curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" -H 'Content-Type: application/json' \
            -X POST -d "$(jq -nc --arg n "$MATTERMOST_TEAM_NAME" \
                '{name:$n, display_name:$n, type:"O"}')" \
            "${MM_BASE}/api/v4/teams" | jq -r '.id // empty')
        [ -n "$team_id" ] || { log "WARN: could not create MM team"; return 1; }
    fi
    # Ensure admin + director + auditor + workers are team members
    # (needed to add them to the channel and for the @mention to actually
    # notify them). bootstrap.sh:675 already does this on a fresh install; we
    # repeat here so a re-run after a data wipe with a stale .bootstrap-done
    # mark still ends up with a fully populated team.
    local admin_id; admin_id=$(mm_user_id "$MATTERMOST_ADMIN_USER") || true
    # Derive the worker list from PBENCH_WORKERS_PER_TEAM so every worker is
    # pulled into the MM team + channel.
    local n_workers
    n_workers="$(grep -E '^PBENCH_WORKERS_PER_TEAM=' "$ENV_FILE" 2>/dev/null | cut -d= -f2)"
    n_workers="${n_workers:-4}"
    local extra_team_members=()
    local wi
    for wi in $(seq 1 "$n_workers"); do
        extra_team_members+=("${ORG_NAME}-worker${wi}")
    done
    local m agent
    for m in "$admin_id" "$(mm_user_id "$DIRECTOR_AGENT")" "$(mm_user_id "$AUDITOR_AGENT")"; do
        [ -n "$m" ] && curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" -H 'Content-Type: application/json' \
            -X POST -d "$(jq -nc --arg t "$team_id" --arg u "$m" '{team_id:$t, user_id:$u}')" \
            "${MM_BASE}/api/v4/teams/${team_id}/members" >/dev/null 2>&1 || true
    done
    for agent in "${extra_team_members[@]}"; do
        m=$(mm_user_id "$agent") || true
        [ -n "$m" ] && curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" -H 'Content-Type: application/json' \
            -X POST -d "$(jq -nc --arg t "$team_id" --arg u "$m" '{team_id:$t, user_id:$u}')" \
            "${MM_BASE}/api/v4/teams/${team_id}/members" >/dev/null 2>&1 || true
    done
    local chan_name="pbench-task"
    local ch
    ch=$(curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" \
        "${MM_BASE}/api/v4/teams/${team_id}/channels/name/${chan_name}" \
        | jq -r 'select(.status_code == null) | .id // empty')
    if [ -z "$ch" ]; then
        ch=$(curl -sS -H "Authorization: Bearer $MM_ADMIN_TOKEN" -H 'Content-Type: application/json' \
            -X POST -d "$(jq -nc --arg t "$team_id" --arg n "$chan_name" \
                '{team_id:$t, name:$n, display_name:"pbench task", type:"P"}')" \
            "${MM_BASE}/api/v4/channels" | jq -r '.id // empty')
        [ -n "$ch" ] || { log "WARN: could not create MM task channel"; return 1; }
    fi
    # Pull director + auditor + workers + reviewer into the channel so the
    # @mention notifies them and the lead can DM without needing MCP
    # channel-admin tools (mattermost__create_channel /join_channel
    # /add_user_to_channel are on the deny list — see
    # docker/agent/config/settings.json.tmpl).
    local uid code
    for agent in "$DIRECTOR_AGENT" "$AUDITOR_AGENT" "${extra_team_members[@]}"; do
        uid=$(mm_user_id "$agent") || true
        [ -n "$uid" ] || { log "WARN: no MM user id for $agent"; continue; }
        # mm_join_ok: a discarded failure here surfaces hours later as an
        # unexplained 403 in an agent's transcript, so record it now.
        code=$(curl -sS -o /dev/null -w '%{http_code}' \
            -H "Authorization: Bearer $MM_ADMIN_TOKEN" -H 'Content-Type: application/json' \
            -X POST -d "$(jq -nc --arg u "$uid" '{user_id:$u}')" \
            "${MM_BASE}/api/v4/channels/${ch}/members" 2>/dev/null || echo 000)
        case "$code" in
            2*) ;;
            *) log "WARN: MM channel join failed for $agent (http=$code)" ;;
        esac
    done
    TASK_CHANNEL_ID="$ch"
    MM_TEAM_ID="$team_id"
    # Both ids on stdout: the caller runs this in a $() subshell, so plain
    # assignment to the globals above is lost to the parent shell.
    printf '%s %s' "$team_id" "$ch"
}

# The canonical task brief: the gitea issue #1 body, the wake DMs and the MM
# task channel post all carry it.
task_brief() {
    render_prompt "$PROMPTS_DIR/team/task-brief.md" \
        TASK="$TASK" REPO="$REPO" MM_TEAM_ID="$MM_TEAM_ID" TASK_CHANNEL_ID="$TASK_CHANNEL_ID"
}

# Deadline reminders, posted to the shared task channel.
#
# The brief deliberately does NOT state the total budget. A team told it has
# six hours plans for six hours, and its failures cluster at the end rather
# than being spread through it.
#
# What the agents actually need is not a number to pace against but a signal at
# the two points where the right action changes: stop starting new work, and
# land what exists. There is no clock in the container and no external trigger,
# so the team cannot tell when either has arrived. The runner tells it.
deadline_reminder_loop() {
    local secs="$1"
    # 45 and 5 minutes before the end, matching the board's +{rel}m stamps.
    local t45=$(( secs - 45 * 60 ))
    local t5=$((  secs - 5  * 60 ))
    if [ "$t45" -gt 0 ]; then
        sleep "$t45"
        mm_post "$TASK_CHANNEL_ID" "$(render_prompt "$PROMPTS_DIR/team/deadline-45m.md")" \
            || log "WARN: T-45m reminder failed"
        log "posted T-45m reminder"
    fi
    local rest=$(( t5 - (t45 > 0 ? t45 : 0) ))
    if [ "$rest" -gt 0 ]; then
        sleep "$rest"
        mm_post "$TASK_CHANNEL_ID" "$(render_prompt "$PROMPTS_DIR/team/deadline-5m.md")" \
            || log "WARN: T-5m reminder failed"
        log "posted T-5m reminder"
    fi
}

# --- 3. drive: seed initial commit + wake the director (MM + gitea) ---------
# Per-agent wake interval. The base rate applies for the first hour of the
# ramp, then a fast rate for the remainder.
#
# WHY A FIXED RATE DOES NOT SCALE. 30s per agent is fine to 32 and ruinous past
# it, because HOURS counts the whole run including the ramp -- every second of
# stagger comes out of the LAST agent's working budget:
#     128 agents   64 min      1000 agents   8.3 h
#
# The base rate covers the first PBENCH_WAKE_RAMP_SUBJ_S (default 3600) seconds
# of the ramp, so the switch lands on agent 3600/30 = 120.
#
# Agents 1..switch_at get the base rate; the rest get the fast one. At 4-32
# workers nothing reaches the switch, so they run at the base rate throughout.
wake_stagger_for() {   # wake_stagger_for <1-based agent index> -> seconds
    local _i="$1"
    local _base="${PBENCH_WAKE_STAGGER_S:-30}"
    local _switch=$(( ${PBENCH_WAKE_RAMP_SUBJ_S:-3600} / _base ))
    if [ "$_i" -le "$_switch" ]; then
        echo "$_base"
    else
        echo "${PBENCH_WAKE_FAST_STAGGER_S:-3}"
    fi
}

# Start one worker's agent and router, retrying until the start works: an agent
# that never starts would leave the run going for its whole budget without it.
# Each failure logs the end of make's output.
# --no-deps is load-bearing: without it compose restarts this agent's dependency
# chain (gitea/mysql/mattermost/bootstrap) on EVERY agent start. Infra is
# already up from the infra-only bringup.
start_agent_containers() {  # start_agent_containers <worker index> <agent name>
    local wi="$1" wname="$2" out try=1
    until out="$(cd "$ROOT" && make up PROFILE="$PROFILE" UP_FLAGS=--no-deps \
            SERVICES="agent-worker${wi} mini-router-worker${wi}" 2>&1)"; do
        log "WARN: container start failed for $wname (try $try); retrying in ${PBENCH_START_RETRY_S:-30}s"
        printf '%s\n' "$out" | tail -n 5 | while IFS= read -r l; do log "    $l"; done
        try=$((try + 1))
        sleep "${PBENCH_START_RETRY_S:-30}"
    done
    log "started containers for $wname"
}

push_seed_and_drive() {
    local seed_dir; seed_dir="$(cat "$OUT_DIR/$TASK/.seed_path")"
    local repo_url="http://${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}@localhost:${EDGE_PORT}/${ORG_NAME}/${REPO}.git"
    local push_tmp="$OUT_DIR/$TASK/_push"
    rm -rf "$push_tmp"
    log "cloning team repo to seed initial commit"
    # RETRY, AND NEVER RETURN FROM HERE.
    #
    # A `return` here leaves the WHOLE drive phase: a single failed clone would
    # skip the mattermost team/channel setup, the task issue and the entire wake
    # loop, and the run would sleep out its budget having woken nobody and exit
    # 0. The first clone can be reset ("Recv failure: Connection reset by peer")
    # while hundreds of containers are coming up.
    #
    # The seed is a convenience; the wake is the run. A failure here must cost
    # the seed only, so this retries and then falls through either way.
    local _seeded=0 _try
    for _try in 1 2 3 4 5; do
        rm -rf "$push_tmp"
        if git clone --quiet "$repo_url" "$push_tmp" 2>/dev/null; then _seeded=1; break; fi
        log "WARN: clone attempt $_try/5 failed; retrying in $((_try * 5))s"
        sleep $((_try * 5))
    done
    if [ "$_seeded" != 1 ]; then
        log "WARN: clone failed after 5 attempts; skipping seed push (agents are still woken below)"
    fi
    if [ "$_seeded" = 1 ]; then
    cp -a "$seed_dir/." "$push_tmp/" 2>/dev/null || true
    ( cd "$push_tmp" \
        && git config user.email "chairman@${ORG_NAME}.local" \
        && git config user.name "$GITEA_ADMIN_USER" \
        && git add -A \
        && git commit -qm "pbench: seed cleanroom workspace ($TASK)" \
        && git push -q origin HEAD ) \
        || log "WARN: seed push failed (repo may already be seeded)"
    fi

    # The MM team/channel must exist BEFORE the brief is rendered: the brief
    # quotes both ids so agents never have to discover them, and it is reused
    # verbatim for the gitea issue below.
    local _mm ch
    _mm="$(mm_ensure_task_channel)" || _mm=""
    MM_TEAM_ID="${_mm%% *}"
    ch="${_mm##* }"
    [ "$_mm" = "" ] && { MM_TEAM_ID=""; ch=""; }
    TASK_CHANNEL_ID="$ch"

    local brief; brief="$(task_brief)"
    local kickoff; kickoff="$(render_prompt "$PROMPTS_DIR/team/kickoff.md" TASK_BRIEF="$brief")"

    # (a) Gitea issue #1, the task record every agent's prompt points at.
    # NO ASSIGNEE: peers self-select, and gitea rejects the whole request when
    # the assignee is an account that does not exist, so issue #1 would never
    # be created. An admin-opened, unassigned issue notifies nobody (bootstrap
    # unwatches every agent from the repo); the wake comes from the staggered
    # DMs below, not from a notification.
    log "opening task issue (no assignee; peers self-select)"
    curl -fsS -u "${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}" \
        -H 'Content-Type: application/json' \
        -d "$(python3 -c 'import json,sys; print(json.dumps({"title": f"[pbench] {sys.argv[1]}", "body": sys.argv[2]}))' "$TASK" "$brief")" \
        "http://localhost:${EDGE_PORT}/api/v1/repos/${ORG_NAME}/${REPO}/issues" \
        >/dev/null 2>&1 \
        && log "task issue opened" \
        || log "WARN: could not open task issue"

    # (b) Mattermost task channel pulling in director + auditor — the reliable
    #     wakeup path. @mention both so the websocket notification fires.
    # The channel was already created above (the brief needs its id), and
    # TASK_CHANNEL_ID / MM_TEAM_ID are set in THIS shell there — which also
    # gives the background worker_watchdog_loop, forked from this shell at
    # main(), a non-empty TASK_CHANNEL_ID to guard on.
    # WAKE AGENTS ONE AT A TIME.
    #
    # One channel post wakes every member at once, and agents woken together all
    # read an empty board and claim the same first areas within seconds. A
    # sequenced DM gives agent N a board with N-1 claims already on it, which
    # is the difference between "explore the unexplored areas" meaning something
    # and meaning nothing. At 16 agents, 15 x 30s = 7.5 min of a 360 min run (2%).
    #
    # The channel record is posted LAST, on purpose: posting it first would wake
    # everyone and defeat the stagger.
    local stagger_s="${PBENCH_WAKE_STAGGER_S:-30}"
    local fast_stagger_s="${PBENCH_WAKE_FAST_STAGGER_S:-3}"
    local switch_at; switch_at=$(( ${PBENCH_WAKE_RAMP_SUBJ_S:-3600} / ${PBENCH_WAKE_STAGGER_S:-30} ))
    local n_workers_wake wi wname dmch woke=0
    n_workers_wake="$(grep -E '^PBENCH_WORKERS_PER_TEAM=' "$ENV_FILE" 2>/dev/null | cut -d= -f2)"
    n_workers_wake="${n_workers_wake:-4}"
    if [ "$n_workers_wake" -gt "$switch_at" ]; then
        log "waking $n_workers_wake agents by DM: ${stagger_s}s apart for the first $switch_at (one hour), then ${fast_stagger_s}s"
    else
        log "waking $n_workers_wake agents by DM, ${stagger_s}s apart"
    fi
    # Reserve every agent slot BEFORE the clock starts. Node provisioning is
    # setup, not agent working time; charging it to the budget would silently
    # shorten the run by however long Azure took. No-op unless
    # PBENCH_K8S_PREWARM=1 on the k8s path.
    k8s_prewarm_up "$n_workers_wake"
    # The pause image above does not cache the real agent image. The multi-node
    # launcher opts into one exact-image, exit-only Pod per occupied node; this must complete
    # before t0 so registry transfer is setup rather than smoke working time.
    k8s_agent_prepull_up || die "agent image pre-pull failed"

    # HOURS is the WHOLE run, stagger included: a 0.5h run must finish 30 min
    # after the first agent wakes, not 30 min after the last one. Stamp t0 here
    # and subtract the wake time from the sleep below, otherwise a 16-agent
    # 30s stagger silently turns "0.5h" into 37.5 min and "6h" into 6h07.
    PBENCH_RUN_T0=$(date +%s)
    export PBENCH_RUN_T0

    # START THE IDLE WATCHDOG BEFORE THE RAMP, not after it.
    #
    # Forked after the wake loop instead, it would leave the whole ramp without
    # an idle nudge, because container bringup runs on the stagger:
    #     8 agents x30s ->  4 min with no idle nudge
    #   128 agents x30s -> 64 min
    # and the earliest-woken agents are the ones most likely to run out of
    # events and sit idle in that window.
    #
    # Forked HERE, TASK_CHANNEL_ID is already set (just above), which is the
    # value the loop guards on. Duration is the whole run; the loop exits on
    # its own deadline.
    if [ "${PBENCH_WATCHDOG_EARLY:-1}" = "1" ]; then
        local _wd_secs
        _wd_secs="$(python3 -c "print(int(round(float('${HOURS:-6}')*3600)))" 2>/dev/null || echo 21600)"
        worker_watchdog_loop "$_wd_secs" &
        WATCHDOG_PID=$!
        log "idle watchdog started BEFORE the ramp (pid $WATCHDOG_PID, ${_wd_secs}s)"
    fi

    for wi in $(seq 1 "$n_workers_wake"); do
        if wake_budget_expired; then
            log "wake budget elapsed: started $woke/$n_workers_wake agents; stopping the ramp"
            break
        fi
        wname="${ORG_NAME}-worker${wi}"
        # START THE CONTAINER ON THE STAGGER, not just the DM.
        #
        # Bringing every agent up at once and relying on the DM to sequence them
        # does not work:
        #   - every copilot CLI unpacks its package simultaneously, and at scale
        #     most of them never finish unpacking or create a session.
        #   - the first DM-woken agent's channel post wakes every agent that has
        #     a session, because an idle agent is dispatched by any event, not
        #     only by its own kickoff DM.
        # An agent that has not been started yet cannot be woken early by a
        # peer's post, and cannot contend for unpack I/O. That makes the stagger
        # real instead of advisory, and needs no event-holding machinery.
        # Stamp BEFORE the bringup, not after: the interval must absorb the
        # container start (~30s) rather than add to it. Stamped after, each
        # interval becomes the stagger plus the bringup, and since HOURS counts
        # the whole run the last agent loses that much more of its budget.
        _wake_started=$(date +%s)
        if [ "${PBENCH_STAGGERED_BRINGUP:-1}" = "1" ]; then
            if [ "$ORCH" = "k8s" ]; then
                # podManagementPolicy: OrderedReady already starts pod N+1 only
                # after N is Ready, so raising the replica count by one IS the
                # stagger -- the same property the compose path hand-rolls.
                #
                # Give the slot back FIRST. Scaling the StatefulSet against a
                # full cluster makes the new pod Pending, and a Pending pod is
                # exactly what makes the autoscaler add a node we do not want.
                k8s_prewarm_release "$wi"
                k8s_agents "$wi"
                kubectl -n "$NS" wait --for=condition=ready "pod/agent-$((wi-1))" \
                    --timeout="${PBENCH_POD_READY_TIMEOUT_S:-300}s" >/dev/null 2>&1 \
                    && log "started pod agent-$((wi-1)) for $wname" \
                    || log "WARN: pod agent-$((wi-1)) not ready for $wname"
            else
                start_agent_containers "$wi" "$wname"
            fi
            # Let the CLI unpack and the ACP socket appear before the DM lands;
            # a DM to an agent whose session is not up yet is simply lost.
            sleep "${PBENCH_BRINGUP_SETTLE_S:-20}"
        fi
        dmch="$(mm_dm_channel "$wname" 2>/dev/null)" || dmch=""
        # A failed lookup is far more often a tunnel that is mid-restart than a
        # missing user: pf_supervise rebinds in ~2s, and the wake loop would
        # otherwise skip this agent for the entire run on a two-second window.
        # Costs nothing on the healthy path -- it only runs after a failure.
        if [ -z "$dmch" ]; then
            pf_wait_healthy 30 && dmch="$(mm_dm_channel "$wname" 2>/dev/null)" || dmch=""
        fi
        if [ -n "$dmch" ]; then
            mm_post "$dmch" "$kickoff" >/dev/null 2>&1 \
                && { woke=$((woke+1)); log "woke $wname ($woke/$n_workers_wake)"; } \
                || log "WARN: DM wake failed for $wname"
        else
            log "WARN: no DM channel for $wname"
        fi
        # The interval between agents must be stagger_s TOTAL, not stagger_s
        # PLUS however long bringup and settling took. At 128 agents a naive
        # `sleep $stagger_s` here turns a 64-minute ramp into ~2 hours, and
        # HOURS counts the whole run, so the last agent would lose that time
        # from its budget.
        if [ "$wi" -lt "$n_workers_wake" ]; then
            _spent=$(( $(date +%s) - ${_wake_started:-$(date +%s)} ))
            _remain=$(( $(wake_stagger_for "$wi") - _spent ))
            [ "$_remain" -gt 0 ] && sleep "$_remain"
        fi
    done
    log "wake complete: $woke/$n_workers_wake agents"

    if [ -n "$ch" ]; then
        mm_post "$ch" "$kickoff" \
            && log "task posted to MM channel pbench-task (record; agents already woken)" \
            || log "WARN: MM channel post failed"
    else
        # No fallback needed: the DM wake above already delivered the task to
        # every agent individually.
        log "WARN: no MM channel for the task record (agents were woken by DM)"
    fi
}

# --- worker idle watchdog: per-agent activity check every 60s ---------------
# Each agent's turns/tool-calls append to a jsonl trail under
# ${DATA_ROOT}/${PROFILE}/agents/<agent>/home/.claude/projects/-work/*.jsonl
# (AGENT_KIND=claude) or .../home/.copilot/session-state/<id>/events.jsonl
# (AGENT_KIND=copilot), so the newest jsonl mtime under an agent = its last
# activity time. When a worker crosses WORKER_IDLE_THRESHOLD (default 600s =
# 10m) with no new events and nothing queued for it, we DM that worker a nudge
# toward fresh work. Falls back to the shared task channel if DMs can't be
# opened. Per-worker rate limit
# (WORKER_IDLE_REPEAT default 600s = 10m) prevents spam on stuck workers.
WORKER_IDLE_THRESHOLD="${WORKER_IDLE_THRESHOLD:-600}"
WORKER_IDLE_REPEAT="${WORKER_IDLE_REPEAT:-600}"
WORKER_CHECK_INTERVAL="${WORKER_CHECK_INTERVAL:-60}"

# The k8s last-activity probe, as ONE string, because it runs inside the pod and
# is therefore the part this host cannot see fail.
#
# Emits "<worker-name> <idle-seconds>", or "<worker-name> -1" when the agent has
# no turn log yet. -1 rather than a big number on purpose: "never prompted" and
# "stalled for an hour" need different handling, and a never-prompted agent that
# read as maximally idle would be nudged before it ever started.
#
# Notes that are load-bearing:
#   - idle is computed with the POD's clock, not this host's, so node clock skew
#     cannot manufacture a stall.
#   - `*worker$((i+1))` is anchored at the end by the glob, so worker1 does not
#     also match worker11 -- which starts mattering at 32 agents.
#   - COPILOT_STATE_DIR is searched IN ADDITION to $HOME, never instead of it:
#     copilot's session store is on pod-local disk, so the
#     newest activity lives there while $HOME can look stale.
#   - `stat -c %Y` over `find -printf`: busybox find has no -printf, and the
#     probe failing inside the image would look exactly like a busy fleet.
#   - double quotes only; the whole thing is single-quoted here.
PBENCH_K8S_IDLE_PROBE='
i=${HOSTNAME##*-}
root=${PBENCH_POD_DATA_ROOT:-/opt/data-root}
d=""
for c in "$root"/*worker$((i+1)); do
    [ -d "$c" ] && d="$c" && break
done
[ -n "$d" ] || exit 0
name=${d##*/}
set -- "$d/home"
if [ -n "${COPILOT_STATE_DIR:-}" ] && [ -d "${COPILOT_STATE_DIR:-}" ]; then
    set -- "$@" "$COPILOT_STATE_DIR"
fi
newest=$(find "$@" -type f -name "*.jsonl" \
         -exec stat -c %Y {} + 2>/dev/null | sort -rn | head -1)
now=$(date +%s)
if [ -n "$newest" ]; then echo "$name $((now - newest))"; else echo "$name -1"; fi
'

# Pending UEM rows for one agent. Both orchestrators, one answer, because the
# caller must not care: an agent with queued events will be woken by the queue,
# and nudging on top of that races the dispatcher and buries the event.
# Empty output = "could not tell", which the caller treats as "nudge anyway"
# rather than as zero -- failing closed here silences this watchdog entirely.
watchdog_uem_pending() {  # $1 worker_name -> count, or empty
    local w="$1"
    local sql="SELECT COUNT(*) FROM events WHERE agent='${w}' AND state IN ('pending','sending','retrying','failed');"
    if [ "$ORCH" = "k8s" ]; then
        printf '%s\n' "$sql" | kubectl -n "$NS" exec -i "${PBENCH_MYSQL_POD:-mysql-0}" -- \
            sh -c 'mysql -N -B -uroot -p"$MYSQL_ROOT_PASSWORD" -D omcgitea' 2>/dev/null \
            | tr -d '[:space:]' || true
    elif [ -n "${MYSQL_CONTAINER:-}" ] && [ -n "${MYSQL_ROOT_PW:-}" ]; then
        sudo docker exec "$MYSQL_CONTAINER" \
            mysql -N -B -uroot -p"$MYSQL_ROOT_PW" -D omcgitea -e "$sql" \
            2>/dev/null | tr -d '[:space:]' || true
    fi
}

# Threshold + rate-limit + queue check + nudge for ONE agent. Extracted so the
# compose and k8s paths share one policy; the only thing that differs between
# them is HOW last-activity is read, and that difference stops here.
watchdog_consider() {  # $1 worker_name  $2 idle_secs  $3 now  $4 dedup_dir
    local worker_name="$1" idle="$2" now="$3" dedup_dir="$4"
    [ "$idle" -ge 0 ] 2>/dev/null || return 0          # -1 => never prompted
    [ "$idle" -ge "$WORKER_IDLE_THRESHOLD" ] || return 0
    local last_ping
    last_ping=$(cat "$dedup_dir/$worker_name" 2>/dev/null || echo 0)
    [ $((now - last_ping)) -ge "$WORKER_IDLE_REPEAT" ] || return 0

    local pending_evts
    pending_evts="$(watchdog_uem_pending "$worker_name")"
    if [ -n "$pending_evts" ] && [ "$pending_evts" != "0" ]; then
        log "watchdog: ${worker_name} idle=${idle}s but ${pending_evts} UEM row(s) pending; letting the queue wake it"
        echo "$now" > "$dedup_dir/$worker_name"
        return 0
    fi

    local idle_msg; idle_msg="$(render_prompt "$PROMPTS_DIR/team/idle.md")"
    local pinged=0 dm=""
    dm="$(mm_dm_channel "$worker_name" 2>/dev/null)" || dm=""
    if [ -n "$dm" ]; then
        mm_post "$dm" "$idle_msg" \
            && { log "watchdog: DM ${worker_name} (idle=${idle}s, UEM queue empty)"; pinged=1; } \
            || log "WARN: watchdog DM to ${worker_name} failed"
    fi
    if [ "$pinged" = "0" ] && [ -n "$TASK_CHANNEL_ID" ]; then
        mm_post "$TASK_CHANNEL_ID" "@${worker_name} ${idle_msg}" \
            && log "watchdog: channel-fallback ping for ${worker_name} (idle ${idle}s)" \
            || log "WARN: watchdog channel fallback failed for ${worker_name}"
    fi
    echo "$now" > "$dedup_dir/$worker_name"
}

# One node-scoped watchdog worker. Rows arrive from the supervisor's single pod
# snapshot; this worker ignores every row not assigned to its node, then runs
# the sequential probe and idle policy for the local agents.
watchdog_tick_k8s_node() {  # $1 node  $2 now  $3 dedup_dir; pod rows on stdin
    local node="$1" now="$2" dedup_dir="$3"
    local pod started pod_node out worker_name idle age seen=0 n=0
    while IFS='|' read -r pod started pod_node; do
        [ -n "$pod" ] || continue
        [ "$pod_node" = "$node" ] || continue
        n=$((n + 1))
        out="$(kubectl -n "$NS" exec "$pod" -c agent -- sh -c "$PBENCH_K8S_IDLE_PROBE" 2>/dev/null || true)"
        [ -n "$out" ] || continue
        worker_name="${out%% *}"; idle="${out##* }"
        case "$worker_name" in *worker*) ;; *) continue ;; esac
        # -1 means no turn log AT ALL. Treating that as "not started yet" is
        # right for the first minutes and wrong forever after: an agent whose
        # wake DM was posted while its router was still connecting never writes
        # one, so it would read -1 on every tick and be skipped for the whole
        # run -- the exact failure this watchdog exists to catch. Pod age
        # is the honest lower bound on how long it has had nothing to show.
        if [ "$idle" = "-1" ]; then
            age="$(k8s_pod_age "$started" "$now")"
            [ -n "$age" ] || continue
            idle="$age"
        fi
        seen=$((seen + 1))
        watchdog_consider "$worker_name" "$idle" "$now" "$dedup_dir"
    done
    # A node shard that probed nobody is distinguishable from a healthy node.
    [ "$seen" -gt 0 ] || log "WARN: watchdog node $node probed $n pod(s) and got NO usable reading"
}

# One authoritative Running-pod snapshot per tick, then one concurrent watchdog
# worker per occupied node. At 16 x 64 placement each worker performs at most 64
# sequential kubectl exec calls instead of one process performing all 1,024.
watchdog_tick_k8s() {  # $1 now  $2 dedup_dir
    local now="$1" dedup_dir="$2" rows nodes node pid i
    local -a pids=() shard_nodes=()
    # startTime and nodeName come back on the SAME call that lists the pods.
    # A non-whitespace delimiter preserves an empty startTime as an empty field.
    rows="$(kubectl -n "$NS" get pods -l app=agent --field-selector=status.phase=Running \
            -o jsonpath='{range .items[*]}{.metadata.name}{"|"}{.status.startTime}{"|"}{.spec.nodeName}{"\n"}{end}' \
            2>/dev/null || true)"
    [ -n "$rows" ] || { log "WARN: watchdog tick found NO running agent pods in $NS"; return 0; }
    nodes="$(while IFS='|' read -r _pod _started _node; do
        [ -n "$_node" ] && printf '%s\n' "$_node"
    done <<ROWS
$rows
ROWS
    )"
    nodes="$(printf '%s\n' "$nodes" | LC_ALL=C sort -u)"
    [ -n "$nodes" ] || { log "WARN: watchdog tick found Running pods but NO assigned nodes in $NS"; return 0; }

    # The runner kills the watchdog supervisor at the budget boundary. Arm the
    # trap before starting the first child so no launch window can orphan a node
    # worker or its kubectl exec.
    trap 'for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done; wait 2>/dev/null || true; exit 0' TERM INT HUP
    while IFS= read -r node; do
        [ -n "$node" ] || continue
        watchdog_tick_k8s_node "$node" "$now" "$dedup_dir" <<<"$rows" &
        pids+=("$!")
        shard_nodes+=("$node")
    done <<<"$nodes"

    for i in "${!pids[@]}"; do
        pid="${pids[$i]}"
        wait "$pid" || log "WARN: watchdog node ${shard_nodes[$i]} worker failed"
    done
    trap - TERM INT HUP
}

worker_watchdog_loop() {
    local total_secs="$1"
    local agents_root="${DATA_ROOT}/${PROFILE}/agents"
    local dedup_dir="${OUT_DIR}/${TASK}/_watchdog"
    mkdir -p "$dedup_dir"
    local start now elapsed
    start=$(date +%s)
    # k8s: the turn logs live in the pods, so the probe goes to them. Without
    # it, a stalled agent stays stalled until some other event wakes it.
    if [ "$ORCH" = "k8s" ]; then
        log "idle watchdog: k8s path, probing agent pods in $NS every ${WORKER_CHECK_INTERVAL}s (threshold ${WORKER_IDLE_THRESHOLD}s, repeat ${WORKER_IDLE_REPEAT}s)"
        while :; do
            now=$(date +%s)
            elapsed=$((now - start))
            [ "$elapsed" -ge "$total_secs" ] && break
            watchdog_tick_k8s "$now" "$dedup_dir"
            sleep "$WORKER_CHECK_INTERVAL"
        done
        return 0
    fi
    # A watchdog that cannot read the agent dirs (a wrong path, a permission
    # wall) looks identical to a healthy run, because a scan that yields nothing
    # reads as "everyone is busy". If it cannot read them, say so once, loudly,
    # rather than tick quietly for six hours.
    if ! sudo -n true 2>/dev/null; then
        log "WARN: watchdog cannot sudo -n; agent turn logs are 0700 ACP_CHILD_UID, so every worker will read as busy and NO idle nudge will ever fire"
    fi
    # UEM-queue probe. Resolved ONCE, and every use is guarded: if either
    # piece is missing the watchdog still nudges, it just cannot skip agents that
    # already have work queued. Failing closed here would silence the watchdog
    # while it looks healthy.
    local MYSQL_CONTAINER MYSQL_ROOT_PW
    MYSQL_CONTAINER=$(sudo docker ps --filter "name=omcgitea-$PROFILE-mysql" \
                      --format '{{.Names}}' 2>/dev/null | head -1 || true)
    MYSQL_ROOT_PW=$(grep -E '^MYSQL_ROOT_PASSWORD=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)
    if [ -z "$MYSQL_CONTAINER" ] || [ -z "$MYSQL_ROOT_PW" ]; then
        log "WARN: watchdog cannot read the UEM queue (container='${MYSQL_CONTAINER:-none}'); it will nudge on idle alone"
    fi
    while :; do
        now=$(date +%s)
        elapsed=$((now - start))
        [ "$elapsed" -ge "$total_secs" ] && break
        if [ ! -d "$agents_root" ]; then sleep "$WORKER_CHECK_INTERVAL"; continue; fi
        local agent_dir worker_name last_mtime idle last_ping
        for agent_dir in "$agents_root"/${ORG_NAME}-*worker*; do
            [ -d "$agent_dir" ] || continue
            worker_name="$(basename "$agent_dir")"
            # Agent turn log. AGENT_KIND=claude writes home/.claude/projects/*.jsonl;
            # AGENT_KIND=copilot writes home/.copilot/session-state/<id>/events.jsonl.
            # Scan both: watching one path only makes `continue` fire for every
            # worker of the other kind, and the watchdog never nudges anyone.
            # Agent may not have been prompted yet; find exits 1 then, which under
            # pipefail+set -e would kill the subshell -- hence `|| true`.
            local claude_dir="$agent_dir/home/.claude/projects"
            local copilot_dir="$agent_dir/home/.copilot/session-state"
            local -a scan=()
            [ -d "$claude_dir" ] && scan+=("$claude_dir")
            [ -d "$copilot_dir" ] && scan+=("$copilot_dir")
            [ ${#scan[@]} -gt 0 ] || continue
            # sudo: the agent writes these as ACP_CHILD_UID with the session dir at
            # 0700, so an unprivileged find cannot descend and returns EMPTY --
            # which this loop cannot tell apart from "the agent is busy".
            last_mtime=$(sudo -n find "${scan[@]}" -type f -name '*.jsonl' \
                -printf '%T@\n' 2>/dev/null | sort -rn | head -1 | cut -d. -f1 || true)
            [ -n "$last_mtime" ] || continue
            idle=$((now - last_mtime))
            # Threshold, rate limit, UEM check and nudge all live in
            # watchdog_consider() so this path and the k8s one cannot drift
            # apart on policy. What differs between them is only HOW
            # last-activity is read, and that difference ends on the line above.
            watchdog_consider "$worker_name" "$idle" "$now" "$dedup_dir"
        done
        sleep "$WORKER_CHECK_INTERVAL"
    done
}

# The agent image compose runs: the shell's AGENT_IMAGE if set (make runs compose
# under sudo -E, and a shell value beats --env-file), else .env.<profile>'s.
agent_image() {
    local img="${AGENT_IMAGE:-}"
    [ -n "$img" ] || img="$(grep -E '^AGENT_IMAGE=' "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d ' \r')"
    [ -n "$img" ] && printf '%s\n' "$img"
}

# Clear stale container records for this profile's compose project before
# bringup. compose can hold a reference to a container the daemon no longer has
# ("dependency failed to start: No such container"), left behind by containers
# that died outside compose (docker kill, cgroup.kill, OOM), and the infra
# bringup then fails with only a few services up. Selected by the project label,
# exactly; never a global rm or prune.
clear_stale_containers() {
    local stale
    stale="$(sudo docker ps -aq --filter "label=com.docker.compose.project=omcgitea-$PROFILE" 2>/dev/null || true)"
    [ -n "$stale" ] || return 0
    log "clearing $(echo "$stale" | wc -l) stale container record(s) for $PROFILE"
    echo "$stale" | xargs -r sudo docker rm -f >/dev/null 2>&1 || true
}

main() {
    log "TASK=$TASK HOURS=$HOURS OUT_DIR=$OUT_DIR PROFILE=$PROFILE"
    trap teardown EXIT

    seed_repo
    # DeLM baseline path: pre-populate the shared /work bind-mount with the
    # cleanroom seed contents so planner + workers start with the same docs +
    # a stub compile.sh in a single writable dir. Chown to uid 10000 (the
    # non-root ACP child) so agents can write.
    if [ -n "${WORK_HOST_PATH:-}" ]; then
        log "seeding shared /work at $WORK_HOST_PATH (DeLM baseline path)"
        sudo mkdir -p "$WORK_HOST_PATH"
        # $OUT_DIR/$TASK/_seed contains the cleanroom /workspace contents minus the reference binary
        sudo cp -a "$OUT_DIR/$TASK/_seed/." "$WORK_HOST_PATH/" 2>/dev/null || true
        # Stage a WORKING default compile.sh if the seed has none. It must
        # actually build, not just fail loudly: the first DeLM smoke had a
        # planner produce 42 correct source files and still score 0 because it
        # never replaced an `exit 1` placeholder. A wildcard build over src/
        # means the team's code compiles even when nobody finalizes, and the
        # planner is still free to overwrite this with something better.
        if [ ! -f "$WORK_HOST_PATH/compile.sh" ]; then
            sudo tee "$WORK_HOST_PATH/compile.sh" >/dev/null <<'DEFAULT_COMPILE'
#!/bin/sh
# Default build: compile every C source under src/ into ./executable.
# Staged by the harness so a team that writes sources but never finalizes
# still produces a binary. Overwrite this if your project needs more.
set -e
cd "$(dirname "$0")"
if [ -f Makefile ]; then
    make
    exit $?
fi
SRCS=$(find src -name '*.c' 2>/dev/null | sort)
if [ -z "$SRCS" ]; then
    echo "compile.sh: no sources found under src/" >&2
    exit 1
fi
${CC:-cc} -O2 -Isrc -o executable $SRCS -lm ${LDLIBS:-}
DEFAULT_COMPILE
            sudo chmod +x "$WORK_HOST_PATH/compile.sh"
        fi
        sudo mkdir -p "$WORK_HOST_PATH/src"
        sudo chown -R 10000:10000 "$WORK_HOST_PATH"
    fi
    # Checked here so a typo fails in seconds, not after make up has
    # provisioned a stack. On k8s the nodes pull the image from ACR, which
    # launch_multi_node.sh checks by digest; a local copy is optional there.
    local agent_img
    agent_img="$(agent_image)" || die "AGENT_IMAGE is not set in .env.$PROFILE"
    log "agent image: $agent_img"
    if [ "$ORCH" != "k8s" ]; then
        sudo docker image inspect "$agent_img" >/dev/null 2>&1 \
            || die "agent image missing: $agent_img (build it with scripts/pbench_build_pertask_images.sh)"
    fi
    log "bringing up $PROFILE stack"
    # Render this profile's compose base BEFORE `make up`. `make up` renders it
    # too; rendering here keeps the assertion below independent of the
    # Makefile. Rendering is idempotent and costs ~0.2s.
    make -s render-pbench-base PROFILE="$PROFILE" >/dev/null 2>&1 \
        || die "render-pbench-base failed for $PROFILE"
    # Assert the rendered base actually carries the topology the .env asks for,
    # so a generator regression fails loudly instead of silently under-sizing.
    local _want_w _got_w _base="$ROOT/docker/_gen-prod.$PROFILE.yml"
    _want_w="$(grep -E '^PBENCH_WORKERS_PER_TEAM=' "$ROOT/.env.$PROFILE" 2>/dev/null | cut -d= -f2 | tr -d ' ')"
    if [ -n "$_want_w" ]; then
        [ -f "$_base" ] || die "compose base not rendered: $_base"
        _got_w="$(grep -cE '^  agent-worker[0-9]+:' "$_base" || true)"
        [ "$_got_w" = "$_want_w" ] \
            || die "compose base $_base has $_got_w workers, .env asks for $_want_w"
        log "compose base rendered: $_want_w workers/team"
    fi
    # Serialize `make up` across concurrent runs on this host. Simultaneous
    # `docker compose up -d` calls race the docker daemon, and mysql's
    # `depends_on: service_healthy` can time out on the loser.
    # flock lets only one `make up` progress at a time; others block on the
    # lock and start their bringup once the daemon is quiet again. The
    # 900s timeout is a hard ceiling — if we can't grab the lock in 15 min
    # something else is very wrong.
    if [ "$ORCH" = "k8s" ]; then
        log "bringing up $PROFILE on k8s (namespace $NS)"
        REPLICAS=0 PROFILE="$PROFILE" bash "$ROOT/scripts/pbench_k8s_up.sh" \
            || die "pbench_k8s_up.sh failed"
        # gitea + mattermost are reached over a port-forward, which is what makes
        # every localhost:$EDGE_*_PORT call in this script work unchanged.
        # RESTARTING port-forward, not a one-shot. A single kubectl port-forward
        # dies on the first connection error and never comes back, and nothing
        # downstream notices: every wake after the drop logs "no DM channel" even
        # though in-cluster board context still reaches that agent.
        # Kill a forward left behind by an earlier run of THIS profile. Those
        # loops restart forever, so one killed without its process group keeps
        # holding the port -- pointing at an nginx-edge pod that has since been
        # replaced. The new run then cannot bind, its requests go down the dead
        # tunnel, and gitea answers nothing: `remote: Not found` on a repo that
        # is present and public. A pidfile is used rather than pgrep -f because
        # the pattern would also match the grep's own command line.
        # ALLOCATE the local ports, never reuse the profile's fixed pair.
        # On k8s nothing publishes EDGE_HTTP_PORT/EDGE_MM_PORT -- they are only
        # the local end of a port-forward -- so pinning them buys nothing and
        # costs a whole class of failure: a forward left by an earlier run keeps
        # the port and points at an nginx-edge pod that has since been replaced,
        # so clone, issue-open and every mattermost DM go down a dead tunnel and
        # report "not found" against a repo that is present. Same fix
        # pbench_chain.sh:92 already uses for the compose path.
        _pick_free_port() {
            python3 -c 'import socket;s=socket.socket();s.bind(("0.0.0.0",0));print(s.getsockname()[1]);s.close()'
        }
        EDGE_PORT="$(_pick_free_port)"
        EDGE_MM_PORT="$(_pick_free_port)"
        while [ "$EDGE_MM_PORT" = "$EDGE_PORT" ]; do EDGE_MM_PORT="$(_pick_free_port)"; done
        log "allocated local edge ports: gitea=$EDGE_PORT mm=$EDGE_MM_PORT"
        MM_BASE="http://localhost:${EDGE_MM_PORT}"
        PF_PIDFILE="/tmp/pbench-pf-$PROFILE.pid"
        if [ -f "$PF_PIDFILE" ]; then
            kill "$(cat "$PF_PIDFILE")" 2>/dev/null || true
            sleep 3
            log "cleared a port-forward left by a previous run"
        fi
        PF_LOG="${OUT_DIR}/${TASK}/port-forward.log"
        mkdir -p "$(dirname "$PF_LOG")"
        pf_supervise "$NS" "$EDGE_PORT" "$EDGE_MM_PORT" "$PF_LOG" &
        PF_PID=$!
        echo "$PF_PID" > "$PF_PIDFILE"
        # teardown, armed at the top of main, stays armed here: it stops this
        # supervisor after its export, so a die below still leaves the
        # EXPORT_FAILED marker and releases the relay and the nodes.
        for _i in $(seq 1 30); do
            curl -fsS "http://localhost:${EDGE_PORT}/api/v1/version" >/dev/null 2>&1 && break
            sleep 2
        done
        curl -fsS "http://localhost:${EDGE_PORT}/api/v1/version" >/dev/null 2>&1 \
            || die "port-forward to nginx-edge never became usable"
        # And specifically the git path this run depends on. /api/v1/version can
        # answer through a tunnel that cannot serve the repo.
        # Accept any answer that proves GITEA answered: 200, a redirect, or the
        # 401 a private repo gives an anonymous probe. `curl -f` treats 3xx and
        # 401 as failure, which would make this guard reject a perfectly good tunnel.
        local _gc=""
        for _i in $(seq 1 20); do
            # WITH credentials: gitea answers an anonymous git-upload-pack with
            # 404 even on a public repo, so an unauthenticated probe rejects a
            # tunnel that clones fine one command later.
            _gc=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 8 \
                -u "${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}" \
                "http://localhost:${EDGE_PORT}/${ORG_NAME}/${REPO}.git/info/refs?service=git-upload-pack" 2>/dev/null)
            case "$_gc" in 200|301|302|401) break ;; esac
            sleep 3
        done
        case "$_gc" in
            200|301|302|401) log "edge tunnel serves ${ORG_NAME}/${REPO}.git (HTTP $_gc)" ;;
            # WARN, not die. This guard catches a stale tunnel, but
            # gitea answers 404 to this exact URL even with admin credentials
            # while `git clone` of the same URL succeeds, so a hard failure here
            # blocks a working run. The clone below retries 3x and reports its
            # own outcome, which is the check that actually discriminates.
            *) log "WARN: git-upload-pack probe returned HTTP ${_gc:-none}; continuing (the clone below is the real check)" ;;
        esac
        log "port-forward up: gitea=localhost:${EDGE_PORT} mm=localhost:${EDGE_MM_PORT}"
        push_seed_and_drive
        _k8s_started=1
    fi
    local up_lock="/tmp/pbench-make-up.lock"
    if [ "${_k8s_started:-0}" = "1" ]; then
        # The k8s block above already brought the stack up and drove the kickoff.
        # Everything from here to the lock release is compose-only: the make-up
        # flock, the stale-container-record sweep, and BOTH `make up` variants
        # (infra-only and whole-stack). Guarding just one of them let the
        # infra-only call run on a cluster deployment and die with
        # "make up (infra) failed" AFTER the agents had already been woken.
        log "k8s: skipping the compose bringup block"
    else
    exec 9>"$up_lock"
    flock -w 900 9 || die "could not acquire $up_lock in 15min"
    log "acquired make-up lock (pid $$)"
    if [ "${PBENCH_STAGGERED_BRINGUP:-1}" = "1" ]; then
        # Infra only. Agent + router containers are started later, one pair at a
        # time, inside the wake loop -- see the comment there for why. The list
        # is DERIVED from compose
        # rather than hardcoded, so a new infra service is picked up
        # automatically and a renamed one fails loudly instead of silently
        # being left down.
        local infra
        infra="$(cd "$ROOT" && make -s compose-services PROFILE="$PROFILE" 2>/dev/null \
                 | grep -vE '^(agent|mini-router)-worker[0-9]+$' | tr '\n' ' ')"
        [ -n "$infra" ] || die "could not enumerate infra services for $PROFILE"
        clear_stale_containers
        log "bringing up INFRA only ($(echo $infra | wc -w) services); agents start on the stagger"
        make up PROFILE="$PROFILE" SERVICES="$infra" || die "make up (infra) failed"
    else
        [ "${_k8s_started:-0}" = "1" ] || make up PROFILE="$PROFILE" || die "make up failed"
    fi
    exec 9>&-  # release the lock — bringup is done, other chains may proceed
    fi

    [ "${_k8s_started:-0}" = "1" ] || push_seed_and_drive

    local secs
    # HOURS is the wall-clock budget.
    secs="$(run_budget_seconds)"
    if [ -n "${PBENCH_RUN_T0:-}" ]; then
        _elapsed=$(( $(date +%s) - PBENCH_RUN_T0 ))
        [ "$_elapsed" -lt 0 ] && _elapsed=0
        # By default a run keeps a 60-second floor when its ramp
        # overruns. A bounded scale smoke has already stopped at its deadline,
        # so adding that floor would extend the requested budget.
        _remain="$(run_budget_remaining "$secs" "$_elapsed")"
        log "agents working for ${HOURS}h (${secs}s); ${_elapsed}s spent waking, sleeping ${_remain}s"
        secs="$_remain"
    else
        log "agents working for ${HOURS}h (${secs}s); waiting…"
    fi
    # Per-worker idle watchdog runs in the background: it DMs the specific
    # worker that has stopped emitting jsonl events, pointing it at new work
    # drawn from executable interaction. Falls back to the shared task channel
    # if DMs can't be opened.
    # Already forked before the ramp (see push_seed_and_drive). Only fork here
    # if that was disabled, otherwise two watchdogs nudge the same agents.
    if [ -n "$WATCHDOG_PID" ]; then
        log "reusing pre-ramp idle watchdog (pid $WATCHDOG_PID)"
    else
        worker_watchdog_loop "$secs" &
        WATCHDOG_PID=$!
    fi
    deadline_reminder_loop "$secs" &
    REMINDER_PID=$!
    sleep "$secs"
    stop_background_loops
    log "wall-clock budget elapsed; exporting + evaluating"

    # teardown (trap) exports the submission and stops the stack. Run eval
    # AFTER export, so do it here before exit by exporting explicitly first.
    trap - EXIT
    # Export the scored Git artifact FIRST at the budget boundary. A Kubernetes
    # trajectory snapshot is serial and can take many minutes at scale; putting
    # it first would let live agents keep committing throughout the copy and
    # move the effective submission cutoff beyond HOURS.
    #
    # The guarded status capture IS LOAD-BEARING, exactly as at the teardown call
    # site. The EXIT trap is disarmed, so a non-zero export must not skip
    # trajectory capture, parallel agent deletion, tunnel cleanup, prewarm
    # removal, or eval diagnostics: an unguarded failure (a dead tunnel, say)
    # would leave every agent pod and its node up.
    # export_submission logs its own ERROR and writes an EXPORT_FAILED marker; the
    # status decides whether central PVCs can be deleted after compute is released.
    _pbench_export_ok=1
    export_submission || _pbench_export_ok=0
    # Preserve pod-local Copilot state only after the Git cutoff has been
    # captured, then set the StatefulSet target to zero and submit all remaining
    # Pod deletions together. quiesce_agents owns those operations in that order.
    quiesce_agents || true
    # The explicit export still needs the tunnel; nothing below does. `trap -
    # EXIT` also removed automatic ownership, so stop and reap it here.
    pf_stop
    if [ "$ORCH" = "k8s" ]; then
        # quiesce_agents already preserved trajectories and deleted agent Pods;
        # repeating it here would repeat the serial fleet-wide copy.
        # Remove exit-only image preparation Pods even if preparation was
        # interrupted before its normal pre-clock cleanup.
        k8s_agent_prepull_down
        # Placeholders outlive the StatefulSet otherwise, and each one is a
        # multi-core reservation keeping a D32ds_v5 alive at pool prices.
        k8s_prewarm_down
        k8s_finish_teardown "$_pbench_export_ok" || true
    else
        make down PROFILE="$PROFILE" >/dev/null 2>&1 || true
    fi

    # --- 6. eval -------------------------------------------------------------
    if [ "${SKIP_EVAL:-0}" = "1" ]; then
        log "SKIP_EVAL=1 → deferring programbench eval (submission left at $OUT_DIR/$TASK/submission.tar.gz)"
        return 0
    fi
    log "running programbench eval on $OUT_DIR"
    # This host's docker socket is root-only; ProgramBench shells out to a single
    # docker executable (PROGRAMBENCH_DOCKER_EXECUTABLE). Point it at our shim so
    # eval runs `sudo docker` with a writable HOME (avoids the root-owned
    # ~/.docker/config.json permission warning the harness treats as a failure).
    export PROGRAMBENCH_DOCKER_EXECUTABLE="${PROGRAMBENCH_DOCKER_EXECUTABLE:-$ROOT/scripts/pbench-docker-sudo.sh}"
    # The harness mkstemp()s a host temp file then `docker cp container:foo host_tmp`
    # over it. Because our shim runs docker as ROOT, that temp file ends up
    # root-owned; the harness's finally-block unlink() then fails inside the
    # default /tmp (sticky bit forbids non-owners deleting). Point TMPDIR at a
    # user-owned, NON-sticky dir so we can still unlink root-owned files there.
    local pbench_tmp="$OUT_DIR/$TASK/_evaltmp"
    rm -rf "$pbench_tmp"; mkdir -p "$pbench_tmp"
    export TMPDIR="$pbench_tmp"
      # Eval unpacks and BUILDS the submission on the HOST, outside every container, so it is
      # the one ProgramBench workload compose's cgroup_parent cannot reach. Enter the slice
      # explicitly: a single runaway `executable`, or a build that forks a runaway compiler, can
      # exhaust host memory and take the machine down.
      # See docker/pbench.slice.
      local in_slice=()
      if command -v systemd-run >/dev/null 2>&1 && systemctl cat pbench.slice >/dev/null 2>&1; then
          in_slice=(sudo -n systemd-run --scope --quiet --slice=pbench.slice --collect --uid="$(id -u)" --gid="$(id -g)")
          log "eval runs inside pbench.slice (aggregate ceiling)"
      else
          log "WARN: pbench.slice not installed -- eval runs UNCAPPED (see docker/pbench.slice)"
      fi
    local uv_bin programbench_bin
    uv_bin="$(command -v uv 2>/dev/null || true)"
    programbench_bin="$(command -v programbench 2>/dev/null || true)"
    if [ -n "$uv_bin" ]; then
        ( cd "$PB_REPO" && "${in_slice[@]}" env PROGRAMBENCH_DOCKER_EXECUTABLE="$PROGRAMBENCH_DOCKER_EXECUTABLE" \
            TMPDIR="$pbench_tmp" \
            "$uv_bin" run programbench eval "$OUT_DIR" --filter "$TASK" ) \
            || log "WARN: programbench eval returned non-zero"
    elif [ -n "$programbench_bin" ]; then
        "${in_slice[@]}" env PROGRAMBENCH_DOCKER_EXECUTABLE="$PROGRAMBENCH_DOCKER_EXECUTABLE" \
            TMPDIR="$pbench_tmp" "$programbench_bin" eval "$OUT_DIR" --filter "$TASK" \
            || log "WARN: eval non-zero"
    else
        die "neither 'uv' nor 'programbench' on PATH — cannot evaluate (task #4 eval side must be installed)"
    fi

    local eval_json="$OUT_DIR/$TASK/$TASK.eval.json"
    [ -f "$eval_json" ] && log "eval.json written: $eval_json" \
        || log "WARN: eval.json not found at $eval_json"
}

main "$@"
