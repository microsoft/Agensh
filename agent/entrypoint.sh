#!/bin/bash
# Render each worker's credentials, cooperation prompt and MCP configuration,
# then supervise the Copilot ACP bridge using the profile's persistent HOME.
set -euo pipefail

: "${AGENT_KIND:=copilot}"
: "${AGENT_NAME:?AGENT_NAME required}"
: "${GITEA_HOST:=http://gitea:3000}"
: "${GITEA_TOKEN_FILE:=/run/omcgitea/agent.token}"
: "${ANTHROPIC_BASE_URL:?ANTHROPIC_BASE_URL required}"
: "${ANTHROPIC_MODEL:=gpt-5.6-sol}"
: "${ANTHROPIC_API_KEY:=local-proxy-no-auth}"

[ "$AGENT_KIND" = "copilot" ] || { echo "[entrypoint] FATAL: this release supports AGENT_KIND=copilot only" >&2; exit 1; }

COPILOT_BIN="${COPILOT_BIN:-/opt/copilot-cli/node_modules/.bin/copilot}"
export AGENT_NODE="${AGENT_NODE:-/usr/local/bin/node}"

export MCP_TOOL_TIMEOUT_MS=180000
AGENT_HOME="${AGENT_HOME:-/opt/data}"
TMPL_DIR=/opt/omcgitea
PROMPTS_DIR="$TMPL_DIR/prompts"
CONFIG_DIR="$TMPL_DIR/config"

if [ ! -r "$GITEA_TOKEN_FILE" ]; then
    echo "[entrypoint] FATAL: GITEA_TOKEN_FILE=$GITEA_TOKEN_FILE not readable" >&2
    exit 1
fi

GITEA_TOKEN=$(cat "$GITEA_TOKEN_FILE")
export GITEA_TOKEN GITEA_HOST

MATTERMOST_TOKEN=""
if [ -n "${MATTERMOST_HOST:-}" ]; then
    MATTERMOST_TOKEN_FILE="${MATTERMOST_TOKEN_FILE:-/run/omcgitea/tokens/agent-${AGENT_NAME}-mm.token}"
    if [ -r "$MATTERMOST_TOKEN_FILE" ]; then
        MATTERMOST_TOKEN=$(cat "$MATTERMOST_TOKEN_FILE")
    else
        echo "[entrypoint] WARN: MATTERMOST_TOKEN_FILE=$MATTERMOST_TOKEN_FILE not readable; mm mcp will be unauthenticated" >&2
    fi
fi
export MATTERMOST_TOKEN MATTERMOST_HOST

mkdir -p "$AGENT_HOME"

prune_mcp_servers() {
    # envsubst emits timeout strings; Copilot requires numeric MCP timeouts.
    local f="$1"
    local filter='.mcpServers |= with_entries(.value.timeout |= tonumber)'
    [ -z "${BOARD_SERVICE_URL:-}" ] && filter="$filter | del(.mcpServers.board)"
    jq "$filter" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
}

sqlite_lockable() {
    # Probe the mounted session store before Copilot creates its SQLite database.
    local d="$1" p
    p="$d/.sqlite-probe.$$"
    mkdir -p "$d" 2>/dev/null || return 1
    python3 - "$p" <<'PY' >/dev/null 2>&1
import os, sqlite3, sys
p = sys.argv[1]
try:
    c = sqlite3.connect(p, timeout=2)
    c.execute("create table t(x)")
    c.execute("insert into t values(1)")
    c.commit()
    c.close()
finally:
    for suffix in ("", "-wal", "-shm", "-journal"):
        try:
            os.remove(p + suffix)
        except OSError:
            pass
PY
}

export GITEA_HOST AGENT_NAME GITEA_TOKEN \
       ANTHROPIC_BASE_URL ANTHROPIC_MODEL ANTHROPIC_API_KEY \
       MATTERMOST_HOST MATTERMOST_TOKEN

shutdown_bridge() {
    # Keep the container alive while the bridge cancels tools and seals its archive.
    trap - TERM INT
    local status=0
    if [ -n "${ACP_BRIDGE_PID:-}" ]; then
        kill -TERM "$ACP_BRIDGE_PID" 2>/dev/null || true
        wait "$ACP_BRIDGE_PID" || status=$?
    fi
    exit "$status"
}
trap shutdown_bridge TERM INT

GITEA_HOST_NOPROTO=${GITEA_HOST#http://}
GITEA_HOST_NOPROTO=${GITEA_HOST_NOPROTO#https://}
mkdir -p "$AGENT_HOME/home"
cred="$AGENT_HOME/home/.git-credentials"
echo "http://${AGENT_NAME}:${GITEA_TOKEN}@${GITEA_HOST_NOPROTO}" > "$cred"
chmod 600 "$cred"
git_cfg="$AGENT_HOME/home/.gitconfig"
cat > "$git_cfg" <<EOF
[credential]
    helper = store
[user]
    name = ${AGENT_NAME}
    email = ${AGENT_NAME}@omcgitea.local
[init]
    defaultBranch = main
[safe]
    directory = *
EOF
chmod 600 "$git_cfg"

ACP_SOCK_DIR=/var/run/acp
ACP_SOCK="$ACP_SOCK_DIR/agent.sock"
mkdir -p "$ACP_SOCK_DIR"
rm -f "$ACP_SOCK" 2>/dev/null || true
chown 10000:10000 "$ACP_SOCK_DIR" 2>/dev/null || true

mkdir -p /work
# Repository .txt templates retain their historical .md names inside the image.
export PBENCH_BRIEF="$(cat "$PROMPTS_DIR/pbench-brief.md")"
envsubst < "$PROMPTS_DIR/agents.md" > /work/AGENTS.md
cp /work/AGENTS.md /work/CLAUDE.md
envsubst < "$CONFIG_DIR/mcp.json.tmpl" > /work/.mcp.json
prune_mcp_servers /work/.mcp.json
chmod 644 /work/AGENTS.md /work/CLAUDE.md /work/.mcp.json || true

if [ "$(id -u)" = "0" ]; then
    chown -R 10000:10000 "$AGENT_HOME"
    chown -R 10000:10000 /work || true
fi

export HOME="$AGENT_HOME/home"
export COPILOT_HOME="$HOME/.copilot"
mkdir -p "$COPILOT_HOME"
if [ "$(id -u)" = "0" ]; then
    chown 10000:10000 "$HOME" "$COPILOT_HOME" 2>/dev/null || true
fi
if ! sqlite_lockable "$COPILOT_HOME"; then
    fs="$(stat -f -c %T "$COPILOT_HOME" 2>/dev/null || echo unknown)"
    echo "[entrypoint] FATAL: COPILOT_HOME=$COPILOT_HOME cannot host Copilot's SQLite session store" >&2
    echo "[entrypoint]   filesystem is '$fs'; SQLite cannot take fcntl byte-range locks on it." >&2
    echo "[entrypoint]   Copilot would answer EVERY prompt with 'database is locked' and end the" >&2
    echo "[entrypoint]   turn without calling the model." >&2
    echo "[entrypoint]   Use a profile data directory that supports SQLite locking." >&2
    exit 1
fi

provider_key="$ANTHROPIC_API_KEY"
# Translate the launcher's legacy ANTHROPIC_* names to Copilot's OpenAI provider.
COPILOT_PROVIDER_TYPE="${COPILOT_PROVIDER_TYPE:-openai}"
if [ "$COPILOT_PROVIDER_TYPE" != "openai" ]; then
    echo "[entrypoint] FATAL: unsupported COPILOT_PROVIDER_TYPE=$COPILOT_PROVIDER_TYPE" >&2
    exit 1
fi
export COPILOT_OFFLINE=true
export COPILOT_AUTO_UPDATE=false
export COPILOT_LARGE_OUTPUT_THRESHOLD_BYTES=1048576
export COPILOT_ENABLE_ALT_PROVIDERS=true
export COPILOT_PROVIDER_TYPE
export COPILOT_PROVIDER_BASE_URL="$ANTHROPIC_BASE_URL"
export COPILOT_PROVIDER_API_KEY="$provider_key"
export COPILOT_MODEL="$ANTHROPIC_MODEL"
export OPENAI_API_KEY="$provider_key"
unset ANTHROPIC_API_KEY

if [ -n "${COPILOT_PROVIDER_WIRE_API:-}" ]; then
    export COPILOT_PROVIDER_WIRE_API
fi
if [ -n "${COPILOT_AGENT_REASONING_EFFORT:-}" ]; then
    case "$COPILOT_AGENT_REASONING_EFFORT" in
      none|minimal|low|medium|high|xhigh|max) ;;
      *)
        echo "[entrypoint] FATAL: COPILOT_AGENT_REASONING_EFFORT=$COPILOT_AGENT_REASONING_EFFORT is not a Copilot effort level (none|minimal|low|medium|high|xhigh|max)" >&2
        exit 1
        ;;
    esac
    export COPILOT_AGENT_REASONING_EFFORT
fi
if [ -n "${COPILOT_PROVIDER_MAX_PROMPT_TOKENS:-}" ]; then
    export COPILOT_PROVIDER_MAX_PROMPT_TOKENS
fi

unset COPILOT_GITHUB_TOKEN GH_TOKEN GITHUB_TOKEN GITHUB_COPILOT_API_TOKEN

COPILOT_ARGS=(
    --excluded-tools=task --excluded-tools=list_agents
    --acp
    --stdio
    --no-auto-login
    --no-auto-update
    --no-remote
    --disable-builtin-mcps
    --additional-mcp-config=@/work/.mcp.json
    --no-ask-user
)
if [ -n "${COPILOT_AGENT_REASONING_EFFORT:-}" ]; then
    COPILOT_ARGS+=(--effort "$COPILOT_AGENT_REASONING_EFFORT")
fi
COPILOT_DENY_COUNT=0
# Apply both permission denials and model-visible exclusions for each MCP rule.
while IFS= read -r deny_tool; do
    COPILOT_ARGS+=("--deny-tool=$deny_tool")
    model_tool="${deny_tool/(/-}"
    COPILOT_ARGS+=("--excluded-tools=${model_tool%)}")
    COPILOT_DENY_COUNT=$((COPILOT_DENY_COUNT + 1))
done < <(
    jq -r '.[]' "$CONFIG_DIR/copilot-deny-tools.json"
)
if [ "$COPILOT_DENY_COUNT" -eq 0 ]; then
    echo "[entrypoint] FATAL: no Copilot tool deny rules configured" >&2
    exit 1
fi

echo "[entrypoint] omcgitea AGENT_KIND=copilot agent=$AGENT_NAME gitea=$GITEA_HOST provider=$COPILOT_PROVIDER_BASE_URL model=$COPILOT_MODEL"
/opt/omcgitea/acp-bridge.py "$ACP_SOCK" 10000 10000 -- \
    "$COPILOT_BIN" "${COPILOT_ARGS[@]}" \
    >&2 &
ACP_BRIDGE_PID=$!
echo "[entrypoint] acp bridge started pid=$ACP_BRIDGE_PID sock=$ACP_SOCK kind=copilot"
wait $ACP_BRIDGE_PID
