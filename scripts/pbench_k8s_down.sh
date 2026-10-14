#!/usr/bin/env bash
# pbench_k8s_down.sh — tear a profile's stack down. The k8s counterpart of
# `make down` (KEEP=1) and `make clean` (the default, DESTRUCTIVE).
#
# WHY THE DEFAULT IS DESTRUCTIVE
# pbench_run.sh refuses to start when a profile's data dir exists, because
# leftover state (gitea repo, mattermost history, mysql agent_kv acp_session_id)
# leaks into the next run and effectively rejection-samples the score. The same
# hazard exists here, plus one the compose path does not have: bootstrap issues
# each agent a password it writes ONLY into the tokens dir. Wipe that dir while
# leaving gitea's users in place and the next bootstrap cannot re-authenticate
# them -- it fails with HTTP 401 on a user it can see. Gitea/mattermost state and
# the tokens must therefore be dropped together or not at all.
#
# Usage:
#   PROFILE=pbench-multi-node-pandoc bash scripts/pbench_k8s_down.sh           # wipe
#   PROFILE=... KEEP=1 bash scripts/pbench_k8s_down.sh                          # stop only
set -euo pipefail
PROFILE="${PROFILE:?PROFILE=<profile> required}"
# NS= tears down a namespace not named after its profile; the label check below
# still has to match PROFILE.
NS="${NS:-$PROFILE}"
KEEP="${KEEP:-0}"

log() { echo "[k8s-down] $*" >&2; }

# Only ever touch a namespace this tool created for THIS profile. The label is
# written by tools/gen-k8s.py; refusing without it is what keeps a mistyped
# PROFILE from deleting somebody else's namespace.
got="$(kubectl get ns "$NS" -o jsonpath='{.metadata.labels.pbench-profile}' 2>/dev/null || true)"
if [ -z "$got" ]; then
    log "namespace $NS does not exist or is not a pbench namespace — nothing to do"
    exit 0
fi
if [ "$got" != "$PROFILE" ]; then
    log "REFUSING: namespace $NS belongs to profile '$got', not '$PROFILE'"
    exit 1
fi

if [ "$KEEP" = "1" ]; then
    log "stopping workloads in $NS (data kept)"
    kubectl -n "$NS" scale statefulset/agent --replicas=0 >/dev/null 2>&1 || true
    kubectl -n "$NS" scale --replicas=0 deployment --all >/dev/null 2>&1 || true
    kubectl -n "$NS" scale --replicas=0 statefulset --all >/dev/null 2>&1 || true
    log "stopped; PVCs retained"
    exit 0
fi

log "deleting namespace $NS (pods, PVCs, secrets — DESTRUCTIVE)"
kubectl delete namespace "$NS" --wait=true >/dev/null
log "gone"
