#!/usr/bin/env bash
# Writes .env.pbench-single-node-<short task>[-<PROFILE_SUFFIX>], one per task.
# Needs no base profile: every key is written here.
#
#   MODE      single-node (the only supported mode; also the default)
#   TASKS     task ids, space-separated (default jgm__pandoc.5caad90)
#   WORKERS   agents per team (default 8)
#   ENV_DIR   where the profiles go (default: the repo root)
#   PROFILE_SUFFIX  optional name for an isolated concurrent run
#   PORT_BASE / SUBNET_OCTET  host port and 10.x subnet ranges (22000 / 216)
#   AGENT_IMAGE_TAG  per-task agent tag (pbench); component *_IMAGE overrides
#
# The upstream comes from ~/.pbench-upstream.env (LLM_UPSTREAM,
# LLM_UPSTREAM_TOKEN, REASONING_EFFORT); the same variables in the environment
# win. The five local passwords are generated on first write and kept on every
# regeneration. Profiles are mode 600 and hold secrets: never commit them.
#
# A task's ports and subnets come from its position in TASK_TABLE, so a profile
# gets the same ranges whether it is generated alone or with others, and two
# profiles never overlap at the same worker count.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_DIR="${ENV_DIR:-$ROOT}"
umask 077

MODE="${MODE:-single-node}"
[ "$MODE" = "single-node" ] || { echo "FATAL: MODE='$MODE'; this release supports single-node only" >&2; exit 2; }
PROFILE_SUFFIX="${PROFILE_SUFFIX:-}"
[[ -z "$PROFILE_SUFFIX" || "$PROFILE_SUFFIX" =~ ^[a-z0-9][a-z0-9-]*$ ]] \
    || { echo "FATAL: PROFILE_SUFFIX must begin with a lowercase letter or digit and contain only lowercase letters, digits and hyphens" >&2; exit 2; }
PORT_BASE="${PORT_BASE:-22000}"
SUBNET_OCTET="${SUBNET_OCTET:-216}"
WORKERS="${WORKERS:-8}"
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
    out="$ENV_DIR/.env.pbench-$MODE-$short${PROFILE_SUFFIX:+-$PROFILE_SUFFIX}"
    python3 - "$out" "$MODE" "$short" "$(task_index "$task")" "$PORT_BASE" "$SUBNET_OCTET" \
              "$WORKERS" "$ROOT" <<'PY' || { echo "FATAL: generating $out failed" >&2; exit 1; }
import os, re, secrets, string, sys
out, mode, short, idx, port_base, octet, workers, root = sys.argv[1:]
idx, port_base, workers = int(idx), int(port_base), int(workers)
profile = f"pbench-{mode}-{short}"
suffix = os.environ.get("PROFILE_SUFFIX", "")
if suffix:
    profile += f"-{suffix}"
http = port_base + idx * 10
mm = http + 2
if not 1 <= http <= 65533 or not 0 <= int(octet) <= 255:
    sys.exit("FATAL: PORT_BASE or SUBNET_OCTET produces an invalid port/subnet")

# Compose puts every agent, its mini-router and 8 infra containers on the
# default network, so it widens past a /24 with the worker count. It is
# followed by the egress and edge /24s, and each profile's block is a multiple
# of the default's width so the wider network stays aligned.
prefix = 24
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
    ("PBENCH_CLEANROOM_TAG", "task_cleanroom_v6"),
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
    ("PBENCH_WORKERS_PER_TEAM", workers),
    ("REPOS", "main"),
    ("MINI_ROUTER_STUCK_MS", 1200000),
    ("AGENT_IMAGE", f"omcgitea-agent-{short}:{os.environ.get('AGENT_IMAGE_TAG') or 'pbench'}"),
    ("PBENCH_SUBNET_DEFAULT", f"10.{octet}.{sub}.0/{prefix}"),
    ("PBENCH_SUBNET_EGRESS", f"10.{octet}.{sub + units}.0/24"),
    ("PBENCH_SUBNET_EDGE", f"10.{octet}.{sub + units + 1}.0/24"),
    # gpt-5.6-sol takes tools with reasoning effort only on the responses API.
    ("COPILOT_PROVIDER_WIRE_API", "responses"),
    ("COPILOT_AGENT_REASONING_EFFORT", os.environ["REASONING_EFFORT"]),
    # Copilot's catalogue has no window for this model and would assume 128000.
    ("COPILOT_PROVIDER_MAX_PROMPT_TOKENS", 272000),
    ("UPSTREAM_AUTH_STYLE", "bearer"),
]
for key in ("MINI_ROUTER_IMAGE", "BOARD_IMAGE", "BOOTSTRAP_IMAGE", "SECRET_SERVICE_IMAGE"):
    if os.environ.get(key):
        keys.append((key, os.environ[key]))
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
