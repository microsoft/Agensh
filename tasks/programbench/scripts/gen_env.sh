#!/usr/bin/env bash
# Generate private per-task Compose profiles with model, image and network settings.
# Reuse valid local passwords when regenerating an existing profile.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
harness_env=$(python3 "$ROOT/agent/harness_config.py" shell "$@") || exit $?
eval "$harness_env"
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

# Listed tasks keep stable port and subnet offsets across invocations. Other
# tasks get the first free slot after the table (see agensh/allocate.py), which
# is reused from their existing profile when one exists.
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
    task_index "$task" >/dev/null || echo "note: $task is not in TASK_TABLE; choosing free ports and subnets" >&2
done

creds="$HOME/.agensh/upstream.env"
cred() { [ -r "$creds" ] && awk -F= -v k="$1" '$1==k{print substr($0, length(k) + 2); exit}' "$creds"; }
LLM_UPSTREAM="${LLM_UPSTREAM:-$(cred LLM_UPSTREAM)}"
LLM_UPSTREAM_TOKEN="${LLM_UPSTREAM_TOKEN:-$(cred LLM_UPSTREAM_TOKEN)}"
[ -n "$LLM_UPSTREAM" ] && [ -n "$LLM_UPSTREAM_TOKEN" ] \
    || { echo "FATAL: LLM_UPSTREAM and LLM_UPSTREAM_TOKEN must be set in $creds or the environment" >&2; exit 1; }
export LLM_UPSTREAM LLM_UPSTREAM_TOKEN REASONING_EFFORT LLM_MODEL

mkdir -p "$ENV_DIR"
for task in $TASKS; do
    t="${task#*__}"; short="$(echo "${t%%.*}" | tr -cd 'a-z0-9-')"
    out="$ENV_DIR/.env.programbench-$short${PROFILE_SUFFIX:+-$PROFILE_SUFFIX}"
    # Size subnets for agent/router pairs and atomically publish a mode-600 file.
    python3 - "$out" "$MODE" "$short" "$(task_index "$task")" "$PORT_BASE" "$SUBNET_OCTET" \
              "$WORKERS" "$ROOT" "${#TASK_TABLE[@]}" "$ENV_DIR" <<'PY' || { echo "FATAL: generating $out failed" >&2; exit 1; }
import os, re, secrets, string, sys
out, mode, short, idx, port_base, octet, workers, root, listed, env_dir = sys.argv[1:]
port_base, workers, listed = int(port_base), int(workers), int(listed)
sys.path.insert(0, root)
from agensh import allocate
profile = f"programbench-{short}"
suffix = os.environ.get("PROFILE_SUFFIX", "")
if suffix:
    profile += f"-{suffix}"
if not 1 <= port_base <= 65533 or not 0 <= int(octet) <= 255:
    sys.exit("FATAL: PORT_BASE or SUBNET_OCTET produces an invalid port/subnet")

old = {}
if os.path.exists(out):
    for line in open(out):
        k, sep, v = line.rstrip("\n").partition("=")
        if sep and not k.startswith("#"):
            old[k] = v
SLOT_KEYS = ("EDGE_HTTP_PORT", "EDGE_MM_PORT", "AGENSH_SUBNET_DEFAULT", "AGENSH_SUBNET_EGRESS", "AGENSH_SUBNET_EDGE")
prefix = allocate.subnet_layout(workers)[0]
if idx:
    slot = allocate.slot(int(idx), port_base, octet, workers)
    if slot is None:
        sys.exit(f"FATAL: {profile}: {workers} workers at task index {idx} runs past 10.{octet}.255")
elif all(old.get(k) for k in SLOT_KEYS) and old["AGENSH_SUBNET_DEFAULT"].endswith(f"/{prefix}"):
    # Keep an unlisted task's earlier allocation while it still fits the team size.
    slot = {k: old[k] for k in SLOT_KEYS}
else:
    ports, networks = allocate.profile_claims(env_dir, out)
    index, slot = allocate.choose_slot(port_base, octet, workers, ports, networks + allocate.host_networks(),
                                       allocate.port_is_free, start=listed)
    print(f"allocated slot {index} for {profile}: ports {slot['EDGE_HTTP_PORT']}/{slot['EDGE_MM_PORT']}, "
          f"subnets {slot['AGENSH_SUBNET_DEFAULT']}", file=sys.stderr)
http, mm = int(slot["EDGE_HTTP_PORT"]), int(slot["EDGE_MM_PORT"])
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
    ("ANTHROPIC_BASE_URL", "http://egress-proxy:4180"),
    ("AGENSH_LLM_UPSTREAM", os.environ["LLM_UPSTREAM"]),
    ("AGENT_HARNESS", os.environ["AGENT_HARNESS"]),
    ("HARNESS_VERSION", os.environ["HARNESS_VERSION"]),
    ("HARNESS_CONFIG", os.environ["HARNESS_CONFIG"]),
    ("LLM_MODEL", os.environ["LLM_MODEL"]),
    ("REASONING_EFFORT", os.environ["REASONING_EFFORT"]),
    ("PROMPT_TOKENS", os.environ["PROMPT_TOKENS"]),
    ("OUTPUT_TOKENS", os.environ["OUTPUT_TOKENS"]),
    ("TOOL_OUTPUT_BYTES", os.environ["TOOL_OUTPUT_BYTES"]),
    ("COMPACT_FRACTION", os.environ["COMPACT_FRACTION"]),
    ("ANTHROPIC_MODEL", os.environ["LLM_MODEL"]),
    ("ANTHROPIC_API_KEY", "local-proxy-no-auth"),
    ("UPSTREAM_AUTH_TOKEN", os.environ["LLM_UPSTREAM_TOKEN"]),
    ("AGENSH_WORKERS", workers),
    ("REPOS", "main"),
    ("MINI_ROUTER_STUCK_MS", 1200000),
    ("AGENT_IMAGE", f"omcgitea-agent-{short}-{os.environ['AGENT_HARNESS']}:{os.environ.get('AGENT_IMAGE_TAG') or 'pbench'}"),
    ("AGENSH_SUBNET_DEFAULT", slot["AGENSH_SUBNET_DEFAULT"]),
    ("AGENSH_SUBNET_EGRESS", slot["AGENSH_SUBNET_EGRESS"]),
    ("AGENSH_SUBNET_EDGE", slot["AGENSH_SUBNET_EDGE"]),
    ("UPSTREAM_AUTH_STYLE", "bearer"),
]
prefix = os.environ["AGENT_HARNESS"].upper()
keys.extend([(f"{prefix}_CLI_VERSION", os.environ["HARNESS_VERSION"]),
             (f"{prefix}_PROVIDER_WIRE_API", "messages" if prefix == "CLAUDE" else "responses")])
if prefix == "COPILOT":
    keys.append(("COPILOT_PROVIDER_TYPE", "openai"))
for key in ("MINI_ROUTER_IMAGE", "BOARD_IMAGE", "BOOTSTRAP_IMAGE", "SECRET_SERVICE_IMAGE"):
    if os.environ.get(key):
        keys.append((key, os.environ[key]))
# Optional settings are recorded only when chosen, so default profiles stay unchanged.
if os.environ.get("AGENSH_PACK") and os.environ["AGENSH_PACK"] != "programbench":
    keys.append(("AGENSH_PACK", os.environ["AGENSH_PACK"]))
for key in ("WORKER_CPUS", "WORKER_MEMORY"):
    if os.environ.get(key):
        keys.append((key, os.environ[key]))
body = "".join(f"{k}={v}\n" for k, v in keys)
tmp = f"{out}.tmp.{os.getpid()}"
with open(tmp, "w") as f:
    f.write(body)
os.chmod(tmp, 0o600)
os.replace(tmp, out)
print(f"wrote {out}")
PY
done
