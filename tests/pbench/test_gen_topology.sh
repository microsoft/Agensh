#!/usr/bin/env bash
# T: pbench 拓扑参数化测试 —— tools/gen-compose-prod.py 现在按 env 生成任意规模的
# 团队(默认仍是 37),且反作弊(reference binary 0111 挂载)在任意规模都跟着带。
#
#   PBENCH_TEAMS            队数(默认 5)
#   PBENCH_WORKERS_PER_TEAM 每队 worker 数(默认 5)
#   PBENCH_AUDITOR          1=带 auditor(默认),0=不带
#
# 直接解析生成器 stdout 的 YAML(真实输出,无 mock):
#   1. 不带 env → 37 agents(向后兼容,跟冻结模板一致)
#   2. PBENCH_TEAMS=2 / WORKERS=2 / AUDITOR=0 → 正好 9 个 agent + 9 个 mini-router,
#      名字精确匹配 1 director + 2×(lead+reviewer+2 worker),无 auditor
#   3. 缩小后每个 hermes-agent 仍挂 /opt/pbench/executable(反作弊不丢)
#   4. bootstrap 的 AGENTS / ROLES 反映真实的 9 人名单
#   5. Makefile 为 org-pbench* 接了动态 base(per-profile 生成),而非写死 37 模板
#
# Run:  bash tests/pbench/test_gen_topology.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"
GEN="tools/gen-compose-prod.py"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok()   { echo "  ok: $*"; }

[ -f "$GEN" ] || fail "generator $GEN missing"

# 1. default (no env) → 37 agents
python3 "$GEN" | python3 -c '
import sys, yaml
c = yaml.safe_load(sys.stdin)
svcs = c.get("services", {})
agents = [n for n in svcs if n.startswith("hermes-agent-")]
routers = [n for n in svcs if n.startswith("mini-router-")]
assert len(agents) == 37, f"default should be 37 agents, got {len(agents)}"
assert len(routers) == 37, f"default should be 37 routers, got {len(routers)}"
print("  ok: default topology = 37 agents + 37 routers (backward compatible)")
' || fail "default topology is not 37"

# 2 + 3 + 4. small config: 2 teams, 2 workers/team, no auditor → 9 agents
PBENCH_TEAMS=2 PBENCH_WORKERS_PER_TEAM=2 PBENCH_AUDITOR=0 python3 "$GEN" | python3 -c '
import sys, yaml
c = yaml.safe_load(sys.stdin)
svcs = c.get("services", {})
agents = sorted(n[len("hermes-agent-"):] for n in svcs if n.startswith("hermes-agent-"))
routers = sorted(n[len("mini-router-"):] for n in svcs if n.startswith("mini-router-"))

expected = sorted([
    "director",
    "team1-lead", "team1-reviewer", "team1-worker1", "team1-worker2",
    "team2-lead", "team2-reviewer", "team2-worker1", "team2-worker2",
])
assert agents == expected, f"agent roster mismatch:\n got={agents}\n want={expected}"
assert routers == expected, f"router roster mismatch:\n got={routers}\n want={expected}"
assert "auditor" not in agents, "auditor should be absent when PBENCH_AUDITOR=0"
print(f"  ok: small config = {len(agents)} agents, names match 1 director + 2x(lead+reviewer+2 worker), no auditor")

# 3. anti-cheat binary mount on every agent at any size. Raw generator output
#    keeps the unresolved ${PBENCH_BIN:-/dev/null} source (which itself contains
#    colons), so match the target by substring rather than splitting on ":".
def has_bin_mount(s):
    for m in s.get("volumes", []):
        v = m if isinstance(m, str) else (str(m.get("source","")) + ":" + str(m.get("target","")))
        if "/opt/pbench/executable" in v:
            return True
    return False
for n, s in svcs.items():
    if not n.startswith("hermes-agent-"):
        continue
    assert has_bin_mount(s), f"{n} missing /opt/pbench/executable anti-cheat mount"
print("  ok: every (downsized) agent still mounts /opt/pbench/executable (anti-cheat preserved)")

# 4. bootstrap AGENTS / ROLES reflect the 9-person roster
boot = svcs.get("bootstrap")
assert boot is not None, "no bootstrap service"
env = boot.get("environment", {})
if isinstance(env, list):
    env = dict(e.split("=",1) for e in env if "=" in e)
agents_csv = env.get("AGENTS","")
n_csv = len([a for a in agents_csv.split(",") if a.strip()])
assert n_csv == 9, f"bootstrap AGENTS should list 9, got {n_csv}: {agents_csv!r}"
roles = env.get("ROLES","")
assert "auditor=" not in roles, f"ROLES should not contain auditor: {roles!r}"
assert "lead=" in roles and "reviewer=" in roles and "coder=" in roles and "director=" in roles, \
    f"ROLES missing a role bucket: {roles!r}"
print("  ok: bootstrap AGENTS/ROLES reflect the 9-person roster")
' || fail "small (9-agent) topology wrong"

# 5. Makefile wires a per-profile dynamic base for org-pbench* (not the frozen 37)
grep -qE 'render-pbench-base' Makefile \
    || fail "Makefile has no render-pbench-base target (dynamic base not wired)"
# Assert against COMPOSE_BASE itself, not a prose mention: this check used to
# grep for docker/generated/prod.$(PROFILE).yml, a path the Makefile had only
# ever named in comments, so it passed while saying nothing about the wiring.
grep -qE '^COMPOSE_BASE\s*=\s*docker/_gen-prod\.\$\(PROFILE\)\.yml' Makefile \
    || fail "Makefile does not use docker/_gen-prod.\$(PROFILE).yml as the pbench base"
grep -qE 'gen-compose-prod\.py > docker/_gen-prod\.\$\(PROFILE\)\.yml' Makefile \
    || fail "render-pbench-base does not write docker/_gen-prod.\$(PROFILE).yml"
ok "Makefile wires a per-profile dynamic base for org-pbench*"

echo "PASS: tests/pbench/test_gen_topology.sh"
