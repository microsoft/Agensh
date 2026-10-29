#!/bin/bash
# Prepare team or standalone workers, then let the root bridge own supervision.
set -euo pipefail

worker_mode="${1:-team}"
case "$worker_mode" in
    team|standalone) ;;
    *) echo '[entrypoint] usage: entrypoint.sh [team|standalone]' >&2; exit 2 ;;
esac

TMPL_DIR=/opt/omcgitea
CONFIG_DIR="$TMPL_DIR/config"
harness_env=$(python3 "$TMPL_DIR/harness_config.py" shell) || exit $?
eval "$harness_env"
export ANTHROPIC_MODEL="$LLM_MODEL"
: "${ANTHROPIC_BASE_URL:?ANTHROPIC_BASE_URL required}"
: "${ANTHROPIC_API_KEY:=local-proxy-no-auth}"

python3 "$TMPL_DIR/check_harness.py" "$AGENT_HARNESS" >/dev/null
config_args=()
if [ "$worker_mode" = team ]; then
    : "${AGENT_NAME:?AGENT_NAME required}"
    : "${GITEA_HOST:=http://gitea:3000}"
    : "${GITEA_TOKEN_FILE:=/run/omcgitea/agent.token}"
    [ -r "$GITEA_TOKEN_FILE" ] || {
        echo "[entrypoint] FATAL: GITEA_TOKEN_FILE=$GITEA_TOKEN_FILE not readable" >&2
        exit 1
    }
    GITEA_TOKEN=$(cat "$GITEA_TOKEN_FILE")
    export GITEA_TOKEN GITEA_HOST AGENT_NAME
    export AGENT_NODE="${AGENT_NODE:-/usr/local/bin/node}"
    export ACP_CHILD_UID=10000 ACP_CHILD_GID=10000
    MATTERMOST_TOKEN=""
    if [ -n "${MATTERMOST_HOST:-}" ]; then
        MATTERMOST_TOKEN_FILE="${MATTERMOST_TOKEN_FILE:-/run/omcgitea/tokens/agent-${AGENT_NAME}-mm.token}"
        if [ -r "$MATTERMOST_TOKEN_FILE" ]; then
            MATTERMOST_TOKEN=$(cat "$MATTERMOST_TOKEN_FILE")
        else
            echo "[entrypoint] WARN: MATTERMOST_TOKEN_FILE=$MATTERMOST_TOKEN_FILE not readable; mm mcp will be unauthenticated" >&2
        fi
    fi
    export MATTERMOST_TOKEN MATTERMOST_HOST ANTHROPIC_BASE_URL ANTHROPIC_API_KEY

    AGENT_HOME="${AGENT_HOME:-/opt/data}"
    mkdir -p "$AGENT_HOME/home" /work /var/run/acp
    GITEA_HOST_NOPROTO=${GITEA_HOST#http://}
    GITEA_HOST_NOPROTO=${GITEA_HOST_NOPROTO#https://}
    cred="$AGENT_HOME/home/.git-credentials"
    echo "http://${AGENT_NAME}:${GITEA_TOKEN}@${GITEA_HOST_NOPROTO}" > "$cred"
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
    chmod 600 "$cred" "$git_cfg"

    # Repository .txt templates retain their historical .md names in the image.
    export PBENCH_BRIEF="$(cat "$TMPL_DIR/prompts/pbench_brief.md")"
    envsubst < "$TMPL_DIR/prompts/agents.md" > /work/AGENTS.md
    cp /work/AGENTS.md /work/CLAUDE.md
    export MCP_TOOL_TIMEOUT_MS=180000
    envsubst < "$CONFIG_DIR/mcp.json.tmpl" > /work/.mcp.json
    filter='.mcpServers |= with_entries(.value.timeout |= tonumber)'
    [ -z "${BOARD_SERVICE_URL:-}" ] && filter="$filter | del(.mcpServers.board)"
    jq "$filter" /work/.mcp.json > /work/.mcp.json.tmp
    mv /work/.mcp.json.tmp /work/.mcp.json
    chmod 644 /work/AGENTS.md /work/CLAUDE.md /work/.mcp.json
    if [ "$(id -u)" = 0 ]; then
        chown -R 10000:10000 "$AGENT_HOME" /var/run/acp
        chown -R 10000:10000 /work || true
    fi
    export HOME="$AGENT_HOME/home"
    ACP_SOCK=/var/run/acp/agent.sock
    config_args=(--mcp-config /work/.mcp.json)
    cd /work
else
    ACP_SOCK=/opt/data/acp.sock
fi

case "$AGENT_HARNESS" in
    copilot)
        source "$TMPL_DIR/copilot/config.sh"
        configure_copilot "$worker_mode"
        harness_command=("${COPILOT_BIN:-/usr/local/bin/copilot-wrapped}" "${COPILOT_ARGS[@]}")
        ;;
    pi|codex|claude)
        if [ "$AGENT_HARNESS" = codex ]; then
            export CODEX_HOME="$HOME/.codex" CODEX_PROVIDER_API_KEY="$ANTHROPIC_API_KEY"
        fi
        if [ "$worker_mode" = team ] && [ "$AGENT_HARNESS" != claude ]; then
            config_args+=(--deny-tools "$CONFIG_DIR/mcp_deny_tools.json")
        fi
        python3 "$TMPL_DIR/$AGENT_HARNESS/config.py" "${config_args[@]}"
        [ "$AGENT_HARNESS" = claude ] || unset ANTHROPIC_API_KEY
        harness_command=(python3 "$TMPL_DIR/$AGENT_HARNESS/acp.py")
        ;;
esac
unset COPILOT_GITHUB_TOKEN GH_TOKEN GITHUB_TOKEN GITHUB_COPILOT_API_TOKEN CLAUDE_CODE_OAUTH_TOKEN
# The bridge handles SIGTERM, native cancellation and the final HOME/work archive.
exec python3 "$TMPL_DIR/acp_bridge.py" "$ACP_SOCK" "${ACP_CHILD_UID:?}" "${ACP_CHILD_GID:?}" -- "${harness_command[@]}"
