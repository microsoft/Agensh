#!/usr/bin/env bash
# pbench bin anti-reverse-engineering hard-isolation test (real container, real ACP socket, no mock).
#
# Verify the env-gated privilege-drop in acp-bridge.py: ProgramBench requires the agent to only be
# able to "run" the reference binary, not to "read" its bytes. We mount the bin with `root:root` +
# mode 0111, and drop the ACP child process (node claude-agent-acp) down to non-root (uid 10000).
# Three hard assertions:
#
#   A. Privilege-drop container (ACP_CHILD_UID=10000):
#        - ACP `initialize` still round-trips (privilege-drop did not break the agent path)
#        - The ACP child process node actually runs as uid 10000 (privilege-drop truly took effect)
#        - Child can EXEC the bin (`./executable RUNOK` -> RUNOK)
#        - Child `cat`/`od` bin -> Permission denied (cannot read the bytes)
#   B. Control container (ACP_CHILD_UID unset):
#        - Child is still root (uid 0, default behavior unchanged)
#        - root can `od` out the ELF magic (proves isolation truly relies on privilege-drop, not something else)
#
# This is the regression protection for dev/prod default root path staying unchanged + pbench opt-in privilege-drop.
#
# Run:  bash tests/pbench/test_bin_isolation.sh
# Expect: exit 0 only if all of the above assertions pass.
#
# Dependencies: sudo docker (image omcgitea-hermes-agent:local), python3, sudo
# (the socket is mode 0660 owned uid 10000, the host tester is not in that group, so read/write goes through sudo).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE="${PBENCH_AGENT_IMAGE:-omcgitea-hermes-agent:local}"
DOCKER="sudo docker"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok()   { echo "  ok: $*"; }

WORK="$(mktemp -d /tmp/pbench-bin-iso.XXXXXX)"
RED_CN="pbench-iso-test-priv"
CTRL_CN="pbench-iso-test-root"

cleanup() {
    $DOCKER rm -f "$RED_CN" "$CTRL_CN" >/dev/null 2>&1 || true
    sudo rm -rf "$WORK" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Pre-flight: image present.
$DOCKER image inspect "$IMAGE" >/dev/null 2>&1 \
    || fail "agent image $IMAGE not found (build it first)"
ok "agent image present: $IMAGE"

# Fixtures: fake token + a real ELF bin mounted root:root 0111.
mkdir -p "$WORK/priv/acp" "$WORK/priv/tok" "$WORK/ctrl/acp" "$WORK/ctrl/tok"
echo "faketoken-bin-iso" > "$WORK/priv/tok/agent.token"
echo "faketoken-bin-iso" > "$WORK/ctrl/tok/agent.token"
cp /bin/echo "$WORK/executable"          # a genuinely runnable ELF
sudo chown root:root "$WORK/executable"
sudo chmod 0111 "$WORK/executable"
ok "0111 root:root bin staged ($(stat -c '%A %U:%G' "$WORK/executable"))"

# --- helper: launch one agent container ----------------------------------
# $1 container name, $2 host subdir (priv|ctrl), $3 extra docker args...
launch() {
    local cn="$1" sub="$2"; shift 2
    $DOCKER rm -f "$cn" >/dev/null 2>&1 || true
    $DOCKER run -d --name "$cn" \
        -e AGENT_KIND=claude -e AGENT_NAME=pbtest \
        -e ANTHROPIC_BASE_URL=http://127.0.0.1:4141 \
        -e GITEA_TOKEN_FILE=/run/tok/agent.token \
        "$@" \
        -v "$WORK/$sub/acp":/var/run/acp \
        -v "$WORK/$sub/tok":/run/tok:ro \
        -v "$WORK/executable":/opt/pbench/executable:ro \
        "$IMAGE" >/dev/null
}

# --- helper: send one ACP initialize, hold the conn open N seconds -------
# Spawns the child and keeps it alive so we can inspect it.  Prints the
# initialize response line to stdout.
acp_initialize_hold() {
    local sock="$1" hold="${2:-8}"
    sudo python3 -u -c '
import socket,json,time,sys
sock=sys.argv[1]; hold=float(sys.argv[2])
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
s.connect(sock)
req={"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1,"clientCapabilities":{},"clientInfo":{"name":"bin-iso","version":"0"}}}
s.sendall((json.dumps(req)+"\n").encode())
s.settimeout(30)
buf=b""
try:
    while b"\n" not in buf:
        d=s.recv(65536)
        if not d: break
        buf+=d
except Exception as e:
    sys.stderr.write("recv-err %s\n"%e)
line=buf.split(b"\n",1)[0].decode(errors="replace")
print(line)
sys.stdout.flush()
time.sleep(hold)   # keep child alive for inspection
' "$sock" "$hold"
}

# wait until acp-bridge prints "listening"
wait_listen() {
    local cn="$1" i
    for i in $(seq 1 30); do
        if $DOCKER logs "$cn" 2>&1 | grep -q "acp-bridge.*listening"; then return 0; fi
        sleep 1
    done
    $DOCKER logs "$cn" 2>&1 | tail -20 >&2
    fail "$cn: acp-bridge never reported listening"
}

# =========================================================================
# A. PRIVILEGE-DROP CONTAINER (ACP_CHILD_UID=10000)
# =========================================================================
echo "== A. privilege-drop container =="
launch "$RED_CN" priv -e ACP_CHILD_UID=10000 -e ACP_CHILD_GID=10000
wait_listen "$RED_CN"
ok "priv: acp-bridge listening"

PRIV_SOCK="$WORK/priv/acp/agent.sock"
# Hold the ACP connection open in background; capture the init response.
acp_initialize_hold "$PRIV_SOCK" 12 > "$WORK/priv.init" 2>"$WORK/priv.init.err" &
HOLD_PID=$!
sleep 4   # give child time to spawn + respond

# A1: initialize round-trip
grep -q '"id":1' "$WORK/priv.init" && grep -q '"result"' "$WORK/priv.init" \
    || { cat "$WORK/priv.init" "$WORK/priv.init.err" >&2; fail "priv: no initialize result"; }
ok "priv: ACP initialize round-trip succeeded"

# A2: child node actually runs as uid 10000
PRIV_CHILD_LINE="$($DOCKER exec "$RED_CN" ps -e -o uid,args 2>/dev/null \
    | grep 'index.js' | grep -v acp-bridge || true)"
[ -n "$PRIV_CHILD_LINE" ] || fail "priv: no node child found while conn held"
PRIV_UID="$(echo "$PRIV_CHILD_LINE" | awk '{print $1}')"
[ "$PRIV_UID" = "10000" ] \
    || fail "priv: child uid=$PRIV_UID expected 10000 (privilege drop not in effect)"
ok "priv: ACP child node runs as uid 10000"

# A3: child's user CAN execute the bin
RUN_OUT="$($DOCKER exec -u 10000:10000 "$RED_CN" /opt/pbench/executable RUNOK 2>&1 || true)"
echo "$RUN_OUT" | grep -q RUNOK \
    || fail "priv: uid 10000 could not run the bin (got: $RUN_OUT)"
ok "priv: uid 10000 can EXECUTE the bin"

# A4: child's user CANNOT read the bin bytes
CAT_RC=0
$DOCKER exec -u 10000:10000 "$RED_CN" sh -c 'cat /opt/pbench/executable >/dev/null 2>&1' || CAT_RC=$?
[ "$CAT_RC" -ne 0 ] || fail "priv: uid 10000 was able to READ the bin (cat succeeded) — isolation broken"
OD_RC=0
$DOCKER exec -u 10000:10000 "$RED_CN" sh -c 'od -An -tx1 -N4 /opt/pbench/executable >/dev/null 2>&1' || OD_RC=$?
[ "$OD_RC" -ne 0 ] || fail "priv: uid 10000 was able to READ the bin (od succeeded) — isolation broken"
ok "priv: uid 10000 CANNOT read the bin (cat & od both denied)"

wait "$HOLD_PID" 2>/dev/null || true

# =========================================================================
# B. CONTROL CONTAINER (no ACP_CHILD_UID → default root)
# =========================================================================
echo "== B. control container (default root) =="
launch "$CTRL_CN" ctrl
wait_listen "$CTRL_CN"
ok "ctrl: acp-bridge listening"

CTRL_SOCK="$WORK/ctrl/acp/agent.sock"
acp_initialize_hold "$CTRL_SOCK" 12 > "$WORK/ctrl.init" 2>"$WORK/ctrl.init.err" &
HOLD_PID2=$!
sleep 4

grep -q '"result"' "$WORK/ctrl.init" \
    || { cat "$WORK/ctrl.init" "$WORK/ctrl.init.err" >&2; fail "ctrl: no initialize result"; }
ok "ctrl: ACP initialize round-trip succeeded"

# B1: child stays root (default behavior unchanged)
CTRL_CHILD_LINE="$($DOCKER exec "$CTRL_CN" ps -e -o uid,args 2>/dev/null \
    | grep 'index.js' | grep -v acp-bridge || true)"
[ -n "$CTRL_CHILD_LINE" ] || fail "ctrl: no node child found while conn held"
CTRL_UID="$(echo "$CTRL_CHILD_LINE" | awk '{print $1}')"
[ "$CTRL_UID" = "0" ] \
    || fail "ctrl: child uid=$CTRL_UID expected 0 (default root path changed!)"
ok "ctrl: ACP child node stays root (uid 0) — default unchanged"

# B2: root CAN read the bin (proves isolation hinges on the privilege drop)
ELF="$($DOCKER exec -u 0:0 "$CTRL_CN" sh -c 'od -An -tx1 -N4 /opt/pbench/executable 2>/dev/null' || true)"
echo "$ELF" | grep -qi '7f 45 4c 46' \
    || fail "ctrl: root could not read ELF magic (got: $ELF) — unexpected"
ok "ctrl: root CAN read the bin (ELF magic 7f454c46) — isolation is gated by privilege drop"

wait "$HOLD_PID2" 2>/dev/null || true

echo "PASS: tests/pbench/test_bin_isolation.sh"
