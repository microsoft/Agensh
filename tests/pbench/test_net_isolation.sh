#!/usr/bin/env bash
# pbench agent network-cutoff hard-isolation test (real containers, real docker networks, no mock, no iptables).
#
# ProgramBench requires the agent to be unable to pull the original project source from the public internet
# (a `git clone` of the real repo on github is a full copy = cheating). But the agent must still be able to reach:
#   - the docker internal network (Gitea / Mattermost / MySQL / secret-service / sidecar)
#   - the LLM backend (via a dual-homed egress proxy forwarding to 20.9.234.247)
#
# Mechanism (native docker, zero image changes): pbench's agent container attaches to only one
# `internal: true` network -- docker does not hook a NAT gateway onto this kind of network, so the container
# has zero egress to the public internet, but containers on the same network still intercommunicate as normal.
# The LLM exit is bridged by an egress-proxy container attached to both "internal net + a normal bridge"
# (in real deployment this is strip_metadata_proxy.py).
#
# Three hard assertions (locked = an agent container attached only to the internal net):
#   A. Public internet blocked: curl https://github.com / http://8.8.8.8 -> fails
#   B. egress proxy reachable: the locked agent can reach the dual-homed proxy (represents the LLM path)
#   C. Internal peer reachable: services on the same internal net are reachable (internal traffic is not collateral-damaged)
# Control (open = an agent container attached to a normal bridge net): github.com reachable
#   -> proves the isolation truly comes from the internal net, not from the image itself having no networking.
#
# Run:  bash tests/pbench/test_net_isolation.sh
# Expect: exit 0 only if all assertions pass.
# Dependencies: sudo docker (image omcgitea-hermes-agent:local, contains curl + python3).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE="${PBENCH_AGENT_IMAGE:-omcgitea-hermes-agent:local}"
DOCKER="sudo docker"

INTNET="pbench-net-iso-internal"   # internal: true (no public egress)
EXTNET="pbench-net-iso-external"   # normal bridge (has internet) for the proxy
PEER_CN="pbench-net-iso-peer"      # in-network stand-in for Gitea
PROXY_CN="pbench-net-iso-proxy"    # dual-homed egress proxy (LLM path)
RED_CN="pbench-net-iso-locked"
CTRL_CN="pbench-net-iso-open"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok()   { echo "  ok: $*"; }

cleanup() {
    $DOCKER rm -f "$PEER_CN" "$PROXY_CN" "$RED_CN" "$CTRL_CN" >/dev/null 2>&1 || true
    $DOCKER network rm "$INTNET" "$EXTNET" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

$DOCKER image inspect "$IMAGE" >/dev/null 2>&1 \
    || fail "agent image $IMAGE not found (build it first)"
ok "agent image present: $IMAGE"

# Internal network = the anti-cheat boundary (no NAT to the outside world).
$DOCKER network create --internal "$INTNET" >/dev/null
$DOCKER network create "$EXTNET" >/dev/null
ok "networks created: $INTNET (internal) + $EXTNET (bridge)"

ip_on() {  # $1 container, $2 network -> IP on that network
    $DOCKER inspect -f '{{(index .NetworkSettings.Networks "'"$2"'").IPAddress}}' "$1"
}

# In-internal-network peer (stand-in for Gitea): a real HTTP listener so an
# intra-network request returns a concrete 200 PEER_OK (no guessing at
# connection-refused wording across curl versions).
$DOCKER run -d --name "$PEER_CN" --network "$INTNET" \
    --entrypoint python3 "$IMAGE" \
    -c 'import http.server,socketserver
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"PEER_OK")
    def log_message(self,*a): pass
socketserver.TCPServer(("0.0.0.0",8080),H).serve_forever()' >/dev/null
PEER_IP="$(ip_on "$PEER_CN" "$INTNET")"
[ -n "$PEER_IP" ] || fail "could not resolve peer IP on $INTNET"
ok "in-network peer up @ $PEER_IP"

# Dual-homed egress proxy: a tiny TCP listener reachable from the internal
# net, itself attached to the external net (could reach the real LLM). For
# the test we just need the locked agent to PROVE it can reach this dual-homed
# box from inside the internal network (the LLM path).
$DOCKER run -d --name "$PROXY_CN" --network "$INTNET" \
    --entrypoint python3 "$IMAGE" \
    -c 'import http.server,socketserver
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"PROXY_OK")
    def log_message(self,*a): pass
socketserver.TCPServer(("0.0.0.0",4180),H).serve_forever()' >/dev/null
$DOCKER network connect "$EXTNET" "$PROXY_CN"
PROXY_IP="$(ip_on "$PROXY_CN" "$INTNET")"
[ -n "$PROXY_IP" ] || fail "could not resolve proxy IP on $INTNET"
ok "dual-homed egress proxy up @ $PROXY_IP (internal) + external net"

# helper: run a shell snippet in a transient agent container on a given net
run_on() {  # $1 net, $2 name, $3 script
    $DOCKER run --rm --name "$2" --network "$1" \
        --entrypoint /bin/bash "$IMAGE" -c "$3" 2>&1
}

# =========================================================================
# LOCKED container (internal net only)
# =========================================================================
echo "== locked container (internal network only) =="

# A. public internet blocked (DNS name)
OUT="$(run_on "$INTNET" "$RED_CN" '
curl -sS --max-time 6 https://github.com >/dev/null 2>&1 && echo PUBLIC_OK || echo PUBLIC_BLOCKED' || true)"
echo "$OUT" | grep -q PUBLIC_BLOCKED \
    || { echo "$OUT" >&2; fail "locked: github.com reachable (internal net leaks)"; }
ok "locked: public internet (github.com) BLOCKED"

# A2. public internet blocked (raw IP — rules out DNS-only)
OUT="$(run_on "$INTNET" "$RED_CN" '
curl -sS --max-time 6 http://8.8.8.8 >/dev/null 2>&1 && echo IP_OK || echo IP_BLOCKED' || true)"
echo "$OUT" | grep -q IP_BLOCKED \
    || { echo "$OUT" >&2; fail "locked: 8.8.8.8 reachable (internal net leaks)"; }
ok "locked: arbitrary public IP (8.8.8.8) BLOCKED"

# C. in-network peer reachable — real HTTP 200 PEER_OK
OUT="$(run_on "$INTNET" "$RED_CN" '
curl -sS --max-time 6 "http://'"$PEER_IP"':8080/" 2>/dev/null || echo PEER_FAIL' || true)"
echo "$OUT" | grep -q PEER_OK \
    || { echo "$OUT" >&2; fail "locked: in-network peer unreachable (internal traffic broken)"; }
ok "locked: in-network peer REACHABLE (intra-network preserved)"

# B. egress proxy reachable (the LLM path) — real HTTP 200 PROXY_OK
OUT="$(run_on "$INTNET" "$RED_CN" '
curl -sS --max-time 8 "http://'"$PROXY_IP"':4180/" 2>/dev/null || echo PROXY_FAIL' || true)"
echo "$OUT" | grep -q PROXY_OK \
    || { echo "$OUT" >&2; fail "locked: egress proxy unreachable (LLM path broken)"; }
ok "locked: egress proxy REACHABLE (LLM path via dual-homed proxy)"

# =========================================================================
# CONTROL container (normal bridge) — github.com must be reachable
# =========================================================================
echo "== control container (normal bridge) =="
OUT="$(run_on "$EXTNET" "$CTRL_CN" '
curl -sS --max-time 8 -o /dev/null https://github.com 2>/dev/null && echo PUBLIC_OK || echo PUBLIC_BLOCKED' || true)"
echo "$OUT" | grep -q PUBLIC_OK \
    || { echo "$OUT" >&2; fail "control: github.com unreachable even on bridge — host has no internet? cannot prove isolation"; }
ok "control: github.com REACHABLE on bridge (isolation is gated by the internal network)"

echo "PASS: tests/pbench/test_net_isolation.sh"
