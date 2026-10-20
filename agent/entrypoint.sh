#!/bin/bash
# Agensh single-node agent entrypoint: official Copilot CLI native ACP + BYOK.
# Instructions come from /work/AGENTS.md and MCP config from /work/.mcp.json.
#
# Inputs (env, common):
#   AGENT_KIND              "copilot" (the only supported runtime)
#   AGENT_NAME              identity used in Gitea + DNS
#   GITEA_HOST              http://gitea:3000
#   GITEA_TOKEN_FILE        /run/omcgitea/agent.token
#   ANTHROPIC_BASE_URL      e.g. http://host.docker.internal:4141
#   ANTHROPIC_MODEL         gpt-5.6-sol
#   ANTHROPIC_API_KEY       (any string for local proxy)
#   MATTERMOST_HOST         optional
#   MATTERMOST_TOKEN_FILE   optional, /run/omcgitea/tokens/agent-<name>-mm.token
#
# Inputs (volume): the agent state dir, mounted at $AGENT_HOME (/opt/data).
# HOME is $AGENT_HOME/home.
set -euo pipefail

: "${AGENT_KIND:=copilot}"
: "${AGENT_NAME:?AGENT_NAME required}"
: "${GITEA_HOST:=http://gitea:3000}"
: "${GITEA_TOKEN_FILE:=/run/omcgitea/agent.token}"
: "${ANTHROPIC_BASE_URL:?ANTHROPIC_BASE_URL required}"
: "${ANTHROPIC_MODEL:=gpt-5.6-sol}"
: "${ANTHROPIC_API_KEY:=local-proxy-no-auth}"

[ "$AGENT_KIND" = "copilot" ] || { echo "[entrypoint] FATAL: this release supports AGENT_KIND=copilot only" >&2; exit 1; }

# The per-task image supplies absolute paths for the agent runtime. Node
# stays off PATH so the experiment does not add a runtime to the task toolchain.
#
# AGENT_NODE must be exported before any mcp.json.tmpl render: envsubst can
# only substitute variables that are already in the environment, and a blank
# `command` makes the board MCP fail to register silently.
COPILOT_BIN="${COPILOT_BIN:-/opt/copilot-cli/node_modules/.bin/copilot}"
export AGENT_NODE="${AGENT_NODE:-/usr/local/bin/node}"

# MCP_TOOL_TIMEOUT_MS is consumed by mcp.json.tmpl and MUST be exported before
# any render: envsubst substitutes only what is already in the environment, and
# it renders an UNSET variable to the empty string.
#
# Copilot CLI caps a single MCP tools/call at a hardcoded 180000 ms and only
# honours a per-server `timeout` field as an override; this pins it explicitly.
# resetTimeoutOnProgress does not help: these servers emit no progress
# notifications, and the shim forwards verbatim.
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

# Per-agent mattermost token (optional). If MATTERMOST_HOST is unset
# or the token file is missing, render an empty token — mattermost mcp
# server simply won't authenticate / agent's MM tools will fail. The
# gitea path is unaffected.
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

# Make sure the volume exists.
mkdir -p "$AGENT_HOME"

# Render the MCP timeouts as numbers and omit the board when unconfigured.
prune_mcp_servers() {
    local f="$1"
    local filter='.mcpServers |= with_entries(.value.timeout |= tonumber)'
    [ -z "${BOARD_SERVICE_URL:-}" ] && filter="$filter | del(.mcpServers.board)"
    jq "$filter" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
}

# Can this directory host Copilot's SQLite session store?
#
# Copilot keeps session state in SQLite (session-store.db, and
# session-state/<id>/session.db). SQLite's locking protocol needs fcntl
# byte-range locks. A bind mount on a filesystem without those locks can fail
# even for one connection, before any model call. Probe the backing filesystem
# rather than interpreting this as contention between agents.
#
# This is worth a startup probe because the failure is invisible from outside.
# Copilot answers every ACP prompt with
#   session.error{errorType: query, message: "database is locked"}
# and stopReason end_turn, in about ten seconds, so the container looks healthy
# and makes ZERO model calls for the entire run. Nothing else on the share is
# affected -- config.json, the package cache and events.jsonl all write fine --
# which is exactly why it reads as healthy.
#
# Probed with python3's sqlite3 rather than node's better-sqlite3: same locking
# protocol, and it reproduces the failure exactly on both
# filesystems. Runs as the current user (root at this point); what it catches is
# a property of the MOUNT and is uid-independent, while the child's permissions
# are handled by the chown at the call site.
sqlite_lockable() {
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
    trap - TERM INT
    local status=0
    if [ -n "${ACP_BRIDGE_PID:-}" ]; then
        kill -TERM "$ACP_BRIDGE_PID" 2>/dev/null || true
        wait "$ACP_BRIDGE_PID" || status=$?
    fi
    exit "$status"
}
trap shutdown_bridge TERM INT

# Per-agent Git credentials for real clone/push operations.
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

# ACP socket directory shared with this agent's mini-router.
ACP_SOCK_DIR=/var/run/acp
ACP_SOCK="$ACP_SOCK_DIR/agent.sock"
mkdir -p "$ACP_SOCK_DIR"
rm -f "$ACP_SOCK" 2>/dev/null || true
chown 10000:10000 "$ACP_SOCK_DIR" 2>/dev/null || true

# Copilot reads AGENTS.md and receives the MCP config explicitly on argv.
mkdir -p /work
export PBENCH_BRIEF="$(cat "$PROMPTS_DIR/pbench-brief.md")"
envsubst < "$PROMPTS_DIR/agents.md" > /work/AGENTS.md
# Copilot discovers both instruction filenames. Preserve the experiment's
# generated inputs even though the alternate agent adapter was removed.
cp /work/AGENTS.md /work/CLAUDE.md
envsubst < "$CONFIG_DIR/mcp.json.tmpl" > /work/.mcp.json
prune_mcp_servers /work/.mcp.json
chmod 644 /work/AGENTS.md /work/CLAUDE.md /work/.mcp.json || true

if [ "$(id -u)" = "0" ]; then
    chown -R 10000:10000 "$AGENT_HOME"
    chown -R 10000:10000 /work || true
fi

export HOME="$AGENT_HOME/home"
# Keep the session store in this agent's persistent home.
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

# ACP 1.0.70 needs provider ApiKeyAuthInfo in addition to the BYOK
# provider config. Seed the matching alternate-provider auth path with the
# same deployment-owned key.
provider_key="$ANTHROPIC_API_KEY"
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

# Optional Responses-API transport. Copilot CLI carries a responses
# transport (runtime responses_transport.rs) selected by
# COPILOT_PROVIDER_WIRE_API. It matters for reasoning models: gpt-5.6-sol
# refuses `tools + reasoning_effort` on /v1/chat/completions --
#   400 Function tools with reasoning_effort are not supported ... use
#       /v1/responses or set reasoning_effort to 'none'
# -- and an agent always sends tools, while 'none' is literally zero
# reasoning tokens. On the responses transport the same CLI sends the BARE
# model id (the wider provider pool) and a proper `reasoning` object.
#
# Supplied by the generated experiment profile; keep the value explicit.
if [ -n "${COPILOT_PROVIDER_WIRE_API:-}" ]; then
    export COPILOT_PROVIDER_WIRE_API
fi
# Copilot defaults to medium. This variable alone sets only the FIRST
# prompt of an ACP session; every later prompt goes out at medium. The
# --effort flag added to COPILOT_ARGS below holds for the whole session.
# Note the name: COPILOT_REASONING_EFFORT looks right and is silently
# IGNORED. The CLI exits on a level it does not know, which would fail
# every session, so an unknown one stops here.
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
# Copilot sizes the context window from its own model catalogue, and our
# gateway's model record carries NO context field at all, so an unrecognised
# id falls back to 128000 -- the same silent-default failure mode as the
# reasoning effort above. gpt-5.6-sol actually accepts 400,014 input tokens
# (probed on /v1/responses). At 128k the tool definitions and system prompt
# re-sent every turn take about a quarter of the window before any work, so
# an agent sheds context constantly and spends its tool calls re-reading
# what it lost instead of writing code.
#
# PRESENCE-GUARDED, no default: other models on this arm really are 128k.
if [ -n "${COPILOT_PROVIDER_MAX_PROMPT_TOKENS:-}" ]; then
    export COPILOT_PROVIDER_MAX_PROMPT_TOKENS
fi

# A GitHub identity is neither required nor allowed on the BYOK path.
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
# PRESENCE-GUARDED, no default: absent env => Copilot's own default.
if [ -n "${COPILOT_AGENT_REASONING_EFFORT:-}" ]; then
    COPILOT_ARGS+=(--effort "$COPILOT_AGENT_REASONING_EFFORT")
fi
COPILOT_DENY_COUNT=0
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
