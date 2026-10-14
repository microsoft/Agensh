#!/usr/bin/env bash
# Writes the ProgramBench profiles .env.pbench-<MODE>-<short task>, one per task.
# Needs no base profile: every key is written here.
#
#   MODE      single-node | multi-node | multi-node-smoke          (required)
#   TASKS     task ids, space-separated (default jgm__pandoc.5caad90)
#   WORKERS   agents per team (default 8 single-node, 1024 multi-node)
#   ENV_DIR   where the profiles go (default: the repo root)
#
# The upstream comes from ~/.pbench-upstream.env (LLM_UPSTREAM,
# LLM_UPSTREAM_TOKEN, REASONING_EFFORT); the same variables in the environment
# win. The five local passwords are generated on first write and kept on every
# regeneration. Profiles are mode 600 and hold secrets: never commit them.
#
# A task's ports and subnets come from its position in TASK_TABLE, so a profile
# gets the same ranges whether it is generated alone or with others, and two
# profiles of one mode never overlap.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_DIR="${ENV_DIR:-$ROOT}"
umask 077

MODE="${MODE:-}"
case "$MODE" in
    single-node)      PORT_BASE=22000; SUBNET_OCTET=216; WORKERS="${WORKERS:-8}" ;;
    multi-node)       PORT_BASE=18000; SUBNET_OCTET=199; WORKERS="${WORKERS:-1024}" ;;
    multi-node-smoke) PORT_BASE=18400; SUBNET_OCTET=200; WORKERS="${WORKERS:-1024}" ;;
    *) echo "FATAL: MODE='$MODE' must be single-node, multi-node or multi-node-smoke" >&2; exit 2 ;;
esac
TASKS="${TASKS:-jgm__pandoc.5caad90}"

TASK_TABLE=(
    ffmpeg__ffmpeg.360a402 universal-ctags__ctags.243595e typst__typst.88356d0
    php__php-src.c891263 gromacs__gromacs.665ea4c jgm__pandoc.5caad90
    bellard__quickjs.d7ae12a danmar__cppcheck.0a5b103 alecthomas__chroma.8d04def
    ast-grep__ast-grep.dde0fe0 duckdb__duckdb.bdb65ec johnkerl__miller.8d85b46
    nukesor__pueue.8b9d6fe osgeo__gdal.0847f12 osgeo__proj.75d455c
    samtools__samtools.aa823b5 stathissideris__ditaa.f2286c4 tinycc__tinycc.9b8765d
    tstack__lnav.ee34494 doxygen__doxygen.966d98e
)
task_index() {
    local i
    for i in "${!TASK_TABLE[@]}"; do [ "${TASK_TABLE[$i]}" = "$1" ] && { echo "$i"; return 0; }; done
    return 1
}
for task in $TASKS; do
    task_index "$task" >/dev/null || { echo "FATAL: unknown task $task (not in TASK_TABLE)" >&2; exit 2; }
done

creds="$HOME/.pbench-upstream.env"
cred() { [ -r "$creds" ] && awk -F= -v k="$1" '$1==k{print substr($0, length(k) + 2); exit}' "$creds"; }
LLM_UPSTREAM="${LLM_UPSTREAM:-$(cred LLM_UPSTREAM)}"
LLM_UPSTREAM_TOKEN="${LLM_UPSTREAM_TOKEN:-$(cred LLM_UPSTREAM_TOKEN)}"
REASONING_EFFORT="${REASONING_EFFORT:-$(cred REASONING_EFFORT)}"
REASONING_EFFORT="${REASONING_EFFORT:-high}"
[ -n "$LLM_UPSTREAM" ] && [ -n "$LLM_UPSTREAM_TOKEN" ] \
    || { echo "FATAL: LLM_UPSTREAM and LLM_UPSTREAM_TOKEN must be set in $creds or the environment" >&2; exit 1; }
export LLM_UPSTREAM LLM_UPSTREAM_TOKEN REASONING_EFFORT

mkdir -p "$ENV_DIR"
for task in $TASKS; do
    t="${task#*__}"; short="$(echo "${t%%.*}" | tr -cd 'a-z0-9-')"
    out="$ENV_DIR/.env.pbench-$MODE-$short"
    python3 - "$out" "$MODE" "$short" "$(task_index "$task")" "$PORT_BASE" "$SUBNET_OCTET" \
              "$WORKERS" "$ROOT" <<'PY' || { echo "FATAL: generating $out failed" >&2; exit 1; }
import os, re, secrets, string, sys
out, mode, short, idx, port_base, octet, workers, root = sys.argv[1:]
idx, port_base, workers = int(idx), int(port_base), int(workers)
profile = f"pbench-{mode}-{short}"
k8s = mode != "single-node"
http = port_base + idx * 10
mm = http + 2

# Compose puts every agent, its mini-router and 8 infra containers on the
# default network, so it widens past a /24 with the worker count. It is
# followed by the egress and edge /24s, and each profile's block is a multiple
# of the default's width so the wider network stays aligned. On k8s these are
# only rendered, so a /24 is enough.
prefix, units = 24, 1
if not k8s:
    need = 2 * workers + 8 + 6          # +6: restarts and one-shot containers
    while (1 << (32 - prefix)) - 2 < need and prefix > 16:
        prefix -= 1
    units = 1 << (24 - prefix)
stride = 3 if units == 1 else 2 * units
sub = idx * stride
if sub + units + 1 > 255:
    sys.exit(f"FATAL: {profile}: {workers} workers at task index {idx} runs past 10.{octet}.255")

old = {}
if os.path.exists(out):
    for line in open(out):
        k, sep, v = line.rstrip("\n").partition("=")
        if sep and not k.startswith("#"):
            old[k] = v
alnum = string.ascii_letters + string.digits
def password(key, n):
    if re.fullmatch(r"[A-Za-z0-9]{20,}", old.get(key, "")):
        return old[key]
    return "".join(secrets.choice(alnum) for _ in range(n))

keys = [
    ("ORG_NAME", "pbench"),
    ("PROFILE", profile),
    ("EDGE_HTTP_PORT", http),
    ("EDGE_MM_PORT", mm),
    ("EDGE_DOMAIN", "localhost"),
    ("MATTERMOST_SITE_URL", f"http://localhost:{mm}"),
    ("DATA_ROOT", f"{root}/.claude-team-data"),
    ("GITEA_ADMIN_USER", "chairman"),
    ("GITEA_ADMIN_PASSWORD", password("GITEA_ADMIN_PASSWORD", 22)),
    ("MYSQL_ROOT_PASSWORD", password("MYSQL_ROOT_PASSWORD", 64)),
    ("MYSQL_PASSWORD", password("MYSQL_PASSWORD", 64)),
    ("SECRET_SERVICE_INTERNAL_AUTH", password("SECRET_SERVICE_INTERNAL_AUTH", 64)),
    ("MATTERMOST_ADMIN_USER", "mmadmin"),
    ("MATTERMOST_ADMIN_PASSWORD", password("MATTERMOST_ADMIN_PASSWORD", 23)),
    # Agents talk only to egress-proxy, which injects the real credential.
    ("ANTHROPIC_BASE_URL", "http://egress-proxy:4180"),
    ("PBENCH_LLM_UPSTREAM", os.environ["LLM_UPSTREAM"]),
    ("AGENT_KIND", "copilot"),
    ("COPILOT_PROVIDER_TYPE", "openai"),
    ("ANTHROPIC_MODEL", "gpt-5.6-sol"),
    # Compose requires a non-empty value; the proxy replaces it upstream.
    ("ANTHROPIC_API_KEY", "local-proxy-no-auth"),
    ("UPSTREAM_AUTH_TOKEN", os.environ["LLM_UPSTREAM_TOKEN"]),
    # Empty: the proxy forwards /v1/responses unmodified.
    ("UPSTREAM_PATH_OVERRIDE", ""),
    ("PBENCH_TEAMS", 1),
    ("PBENCH_WORKERS_PER_TEAM", workers),
    ("PBENCH_AUDITOR", 0),
    ("ACP_CHILD_UID", 10000),
    ("ACP_CHILD_GID", 10000),
    ("REPOS", "main"),
    ("REQUIRED_APPROVALS", 1),
    ("MINI_ROUTER_STUCK_MS", 1200000),
    ("AGENT_IMAGE", f"omcgitea-agent-{short}:pbench"),
    ("PBENCH_SUBNET_DEFAULT", f"10.{octet}.{sub}.0/{prefix}"),
    ("PBENCH_SUBNET_EGRESS", f"10.{octet}.{sub + units}.0/24"),
    ("PBENCH_SUBNET_EDGE", f"10.{octet}.{sub + units + 1}.0/24"),
    # gpt-5.6-sol takes tools with reasoning effort only on the responses API.
    ("COPILOT_PROVIDER_WIRE_API", "responses"),
    ("COPILOT_AGENT_REASONING_EFFORT", os.environ["REASONING_EFFORT"]),
    # Copilot's catalogue has no window for this model and would assume 128000.
    ("COPILOT_PROVIDER_MAX_PROMPT_TOKENS", 272000),
    # Empty disables board-service's merge poller.
    ("MERGE_WATCH_REPO", "pbench/main"),
    ("PBENCH_CI_GATE", 0),
    ("UPSTREAM_AUTH_STYLE", "bearer"),
]
if k8s:
    keys += [
        ("PBENCH_ORCHESTRATOR", "k8s"),
        ("PBENCH_AGENT_CPU", "383m"),
        ("PBENCH_AGENT_MEM", "1Gi"),
        ("PBENCH_AGENT_MEM_LIMIT", "8Gi"),
        # $HOME is an Azure Files share there, and SQLite cannot lock on it.
        ("COPILOT_STATE_DIR", "/opt/copilot-state"),
        # 1,024 agents: Mattermost team size, MySQL connections, Gitea's pool,
        # and the shared files volume.
        ("MM_MAX_USERS_PER_TEAM", 2048),
        ("MYSQL_MAX_CONNECTIONS", 5000),
        ("GITEA_DB_TYPE", "mysql"),
        ("GITEA_DB_MAX_OPEN", 200),
        ("GITEA_DB_MAX_IDLE", 50),
        ("PBENCH_FILES_SIZE", "256Gi"),
    ]

body = (f"# .env.{profile}\n"
        "# Generated by scripts/pbench_gen_env.sh: regenerate, do not hand-edit.\n"
        + "".join(f"{k}={v}\n" for k, v in keys))
tmp = f"{out}.tmp.{os.getpid()}"
with open(tmp, "w") as f:
    f.write(body)
os.chmod(tmp, 0o600)
os.replace(tmp, out)
print(f"wrote {out}")
PY
done
