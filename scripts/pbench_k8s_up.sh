#!/usr/bin/env bash
# pbench_k8s_up.sh — bring a profile's stack up on AKS. The k8s counterpart of
# `make up PROFILE=...`.
#
# WHAT IT DOES THAT `kubectl apply` ALONE DOES NOT
#   1. Creates the namespace and the ACR pull secret first. Attaching the ACR to
#      the cluster needs an AcrPull role assignment (Owner-level); this deployer
#      is Contributor, so pulls go through a docker-registry secret built from
#      the registry's admin credential instead.
#   2. Deletes any prior bootstrap Job before applying. A Job's pod template is
#      IMMUTABLE, so `kubectl apply` over a finished one fails with "field is
#      immutable" and the stack silently keeps running the old bootstrap.
#   3. Holds the agent StatefulSet at 0 replicas. Agents are started by the
#      runner on the stagger (or by `kubectl scale`), never all at once --
#      the same reason pbench_run.sh staggers container bringup.
#
# Usage:
#   PROFILE=pbench-multi-node-pandoc bash scripts/pbench_k8s_up.sh
#   PROFILE=... REPLICAS=16 bash scripts/pbench_k8s_up.sh     # and scale up
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROFILE="${PROFILE:?PROFILE=<profile> required}"
NS="$PROFILE"
# No defaults: a registry or subscription baked in here would silently point
# someone else's run at the author's environment.
ACR="${PBENCH_ACR:?PBENCH_ACR=<acr name> required}"
SUB="${AZ_SUBSCRIPTION:?AZ_SUBSCRIPTION=<subscription id> required}"
REPLICAS="${REPLICAS:-0}"
OUT="${OUT:-/tmp/pbench-k8s-$PROFILE.yaml}"

log() { echo "[k8s-up] $*" >&2; }

log "namespace $NS"
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

log "ACR pull secret from $ACR admin credential"
PW="$(az acr credential show -n "$ACR" --subscription "$SUB" --query 'passwords[0].value' -o tsv)"
kubectl -n "$NS" create secret docker-registry acr-pull \
    --docker-server="$ACR.azurecr.io" --docker-username="$ACR" --docker-password="$PW" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null

log "rendering manifests -> $OUT"
PROFILE="$PROFILE" python3 tools/gen-k8s.py > "$OUT"

# A finished Job cannot be re-applied (immutable pod template). Removing it here
# is what makes `up` idempotent instead of failing halfway with the stack partly
# updated.
kubectl -n "$NS" delete job bootstrap --ignore-not-found --wait=true >/dev/null 2>&1 || true

log "applying $(grep -c '^kind:' "$OUT") objects"
kubectl apply -f "$OUT" >/dev/null

# THE ACCOUNT COUNT IS THE CEILING, NOT THE REPLICA COUNT.
#
# bootstrap freezes AGENTS/ROLES at the PBENCH_WORKERS_PER_TEAM it saw, and issues
# one token per name. Scaling the StatefulSet past that gives every extra pod a
# router that exits with `secret-service /tokens/<agent> -> 404`, and because
# podManagementPolicy is OrderedReady the whole queue stops at the first one --
# silently, since `kubectl get pods` shows a healthy prefix and nothing reports
# the stall. A namespace bootstrapped at 16 and later scaled to 250 sat at 16
# ready with one pod restarting for SIX HOURS.
#
# So refuse to scale past what bootstrap actually provisioned. Re-running
# bootstrap (it is idempotent, and PBENCH_BOOTSTRAP_FORCE=1 is set on the k8s
# path) is what raises the ceiling.
want_w="$(grep -E '^PBENCH_WORKERS_PER_TEAM=' "$ROOT/.env.$PROFILE" 2>/dev/null | cut -d= -f2 | tr -d ' \r')"
want_w="${want_w:-0}"
if [ "$REPLICAS" -gt 0 ] && [ "$want_w" -gt 0 ] && [ "$REPLICAS" -gt "$want_w" ]; then
    log "FATAL: asked for $REPLICAS replicas but the profile provisions $want_w agents."
    log "       Raise PBENCH_WORKERS_PER_TEAM in .env.$PROFILE and re-run this script"
    log "       (bootstrap re-runs and issues the missing tokens), then scale."
    exit 1
fi
kubectl -n "$NS" scale statefulset/agent --replicas="$REPLICAS" >/dev/null
log "agent StatefulSet held at $REPLICAS replicas (profile provisions $want_w)"

log "waiting for bootstrap to complete (it issues every agent's tokens)"
if kubectl -n "$NS" wait --for=condition=complete job/bootstrap --timeout=900s >/dev/null 2>&1; then
    log "bootstrap complete"
else
    log "FATAL: bootstrap did not complete — kubectl -n $NS logs job/bootstrap"
    exit 1
fi

log "up: namespace=$NS  agents=$REPLICAS"
log "  scale:   kubectl -n $NS scale statefulset/agent --replicas=16"
log "  gitea:   kubectl -n $NS port-forward svc/nginx-edge 8080:80"
