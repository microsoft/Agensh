#!/usr/bin/env bash
# T2: pbench compose overlay shape test -- verify that org-pbench's network-cutoff topology holds
# up in `docker compose config` (real compose parsing, no mock):
#
#   1. Overlay file docker/docker-compose.pbench.yml exists
#   2. Makefile pulls it in with -f when PROFILE=org-pbench (and only for org-pbench)
#   3. After parsing: the project's default network is internal: true (agent/infra have zero public egress)
#   4. After parsing: an egress-proxy service exists, dual-homed (internal default net + one bridge
#      egress net), UPSTREAM points at the LLM VM 20.9.234.247
#   5. The agent's ANTHROPIC_BASE_URL points at egress-proxy (egress via proxy, not directly)
#
# This is the contract test for the "green" implementation: the real connectivity of the
# network-cutoff mechanism itself is proven with real containers by
# test_net_isolation.sh; this test pins its landing in the compose template.
#
# Run:  bash tests/pbench/test_compose_netlock.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"
OVERLAY="docker/docker-compose.pbench.yml"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok()   { echo "  ok: $*"; }

# 1. overlay file present
[ -f "$OVERLAY" ] || fail "overlay $OVERLAY missing"
ok "overlay file present: $OVERLAY"

# 2. Makefile wires it for org-pbench only
grep -qE 'docker-compose\.pbench\.yml' Makefile \
    || fail "Makefile does not reference the pbench overlay"
ok "Makefile references the pbench overlay"

# 3-5. Render the full config the way `make up PROFILE=org-pbench` would and
# assert the network lock + egress-proxy + agent base url.
CONFIG="$(env -u ANTHROPIC_BASE_URL -u ANTHROPIC_MODEL -u ANTHROPIC_API_KEY \
    sudo -E docker compose \
      -f docker/docker-compose.prod.yml -f "$OVERLAY" \
      --project-name omcgitea-org-pbench --env-file .env.org-pbench \
      --profile org-pbench config 2>/dev/null)" \
    || fail "docker compose config failed for org-pbench (overlay invalid?)"
ok "compose config parses with overlay"

# 3. default network internal: true
echo "$CONFIG" | python3 -c '
import sys, yaml
c = yaml.safe_load(sys.stdin)
nets = c.get("networks", {})
# the project default network (compose names it "default")
d = nets.get("default")
assert d is not None, f"no default network in config; nets={list(nets)}"
assert d.get("internal") is True, f"default network not internal: {d}"
print("  ok: default network is internal: true (no public egress)")
' || fail "default network is not internal"

# 4. egress-proxy service dual-homed + UPSTREAM == whatever .env configures.
#    Do NOT hardcode the backend here — the proxy's UPSTREAM is purely
#    ${PBENCH_LLM_UPSTREAM} from .env.org-pbench, so the contract is "the
#    rendered UPSTREAM equals the configured value (and is non-empty)". This
#    stays correct across backend changes (no hardcoded host).
EXPECT_UPSTREAM="$(grep -E '^PBENCH_LLM_UPSTREAM=' .env.org-pbench | head -1 | cut -d= -f2-)"
[ -n "$EXPECT_UPSTREAM" ] || fail "PBENCH_LLM_UPSTREAM not set in .env.org-pbench"
echo "$CONFIG" | EXPECT_UPSTREAM="$EXPECT_UPSTREAM" python3 -c '
import sys, os, yaml
c = yaml.safe_load(sys.stdin)
svcs = c.get("services", {})
p = svcs.get("egress-proxy")
assert p is not None, f"no egress-proxy service; services include {list(svcs)[:5]}..."
pnets = p.get("networks", {})
names = set(pnets.keys()) if isinstance(pnets, dict) else set(pnets)
assert "default" in names, f"egress-proxy not on default net: {names}"
assert any(n != "default" for n in names), f"egress-proxy not dual-homed: {names}"
env = p.get("environment", {})
if isinstance(env, list):
    env = dict(e.split("=",1) for e in env if "=" in e)
up = env.get("UPSTREAM","")
want = os.environ["EXPECT_UPSTREAM"]
assert up == want, f"egress-proxy UPSTREAM={up!r} != configured PBENCH_LLM_UPSTREAM={want!r}"
print(f"  ok: egress-proxy dual-homed {sorted(names)} UPSTREAM={up} (matches .env)")
' || fail "egress-proxy service shape wrong"

# 5. an agent points ANTHROPIC_BASE_URL at the egress proxy
echo "$CONFIG" | python3 -c '
import sys, yaml
c = yaml.safe_load(sys.stdin)
svcs = c.get("services", {})
agent = next((s for n,s in svcs.items() if n.startswith("hermes-agent-")), None)
assert agent is not None, "no hermes-agent-* service found"
env = agent.get("environment", {})
if isinstance(env, list):
    env = dict(e.split("=",1) for e in env if "=" in e)
base = env.get("ANTHROPIC_BASE_URL","")
assert "egress-proxy" in base, f"agent ANTHROPIC_BASE_URL not via proxy: {base!r}"
print(f"  ok: agent ANTHROPIC_BASE_URL={base} (egress via proxy)")
' || fail "agent ANTHROPIC_BASE_URL not routed through egress-proxy"

# 6. agent mounts the reference binary at /opt/pbench/executable. The mount is
#    env-gated (${PBENCH_BIN:-/dev/null}); with PBENCH_BIN set it must resolve to
#    that path (org-pbench), and unset it must fall back to /dev/null (dev/prod safe).
echo "$CONFIG" | PBENCH_BIN_EXPECT="" python3 -c '
import sys, os, yaml
c = yaml.safe_load(sys.stdin)
svcs = c.get("services", {})
agent = next((s for n,s in svcs.items() if n.startswith("hermes-agent-")), None)
assert agent is not None, "no hermes-agent-* service found"
mounts = agent.get("volumes", [])
def tgt(m):
    return m.get("target") if isinstance(m, dict) else (m.split(":")[1] if ":" in m else "")
binm = [m for m in mounts if tgt(m) == "/opt/pbench/executable"]
assert binm, f"no /opt/pbench/executable mount on agent; mounts={mounts}"
print("  ok: agent mounts /opt/pbench/executable (reference binary; RUN-only 0111)")
' || fail "agent missing reference-binary mount"

PBENCH_BIN_CFG="$(PBENCH_BIN="/tmp/pbench-bin-probe" sudo -E env -u ANTHROPIC_BASE_URL -u ANTHROPIC_MODEL -u ANTHROPIC_API_KEY \
    docker compose -f docker/docker-compose.prod.yml -f "$OVERLAY" \
    --project-name omcgitea-org-pbench --env-file .env.org-pbench \
    --profile org-pbench config 2>/dev/null)"
grep -q 'source: /tmp/pbench-bin-probe' <<<"$PBENCH_BIN_CFG" \
  || fail "PBENCH_BIN not honored — bin mount did not resolve to the staged binary"
ok "PBENCH_BIN env-gate resolves bin mount to the staged 0111 binary"

echo "PASS: tests/pbench/test_compose_netlock.sh"
