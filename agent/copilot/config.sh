#!/bin/bash
# Shared Copilot provider and permissions setup for team and standalone workers.

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

configure_copilot() {
    local mode="$1" deny_tool model_tool count=0
    export COPILOT_HOME="$HOME/.copilot"
    mkdir -p "$COPILOT_HOME"
    if [ "$(id -u)" = 0 ]; then
        chown 10000:10000 "$HOME" "$COPILOT_HOME" 2>/dev/null || true
    fi
    if [ "$mode" = team ] && ! sqlite_lockable "$COPILOT_HOME"; then
        echo "[entrypoint] FATAL: $COPILOT_HOME does not support Copilot SQLite locking" >&2
        exit 1
    fi
    export COPILOT_PROVIDER_TYPE="${COPILOT_PROVIDER_TYPE:-openai}"
    [ "$COPILOT_PROVIDER_TYPE" = openai ] || { echo '[entrypoint] FATAL: Copilot requires the openai provider' >&2; exit 1; }
    export COPILOT_OFFLINE=true COPILOT_AUTO_UPDATE=false COPILOT_ENABLE_ALT_PROVIDERS=true
    export COPILOT_PROVIDER_BASE_URL="$ANTHROPIC_BASE_URL"
    export COPILOT_PROVIDER_API_KEY="$ANTHROPIC_API_KEY" OPENAI_API_KEY="$ANTHROPIC_API_KEY"
    export COPILOT_PROVIDER_WIRE_API=responses COPILOT_MODEL="$LLM_MODEL"
    export COPILOT_AGENT_REASONING_EFFORT="$REASONING_EFFORT"
    export COPILOT_PROVIDER_MAX_PROMPT_TOKENS="$PROMPT_TOKENS"
    export COPILOT_LARGE_OUTPUT_THRESHOLD_BYTES="$TOOL_OUTPUT_BYTES"
    if [ -n "$COMPACT_FRACTION" ]; then
        export COPILOT_BACKGROUND_COMPACTION_THRESHOLD="$COMPACT_FRACTION"
    else
        unset COPILOT_BACKGROUND_COMPACTION_THRESHOLD
    fi
    unset ANTHROPIC_API_KEY COPILOT_GITHUB_TOKEN GH_TOKEN GITHUB_TOKEN GITHUB_COPILOT_API_TOKEN
    COPILOT_ARGS=(
        --excluded-tools=task --excluded-tools=list_agents --excluded-tools=read_agent
        --excluded-tools=session_store_sql --acp --stdio --no-auto-login
        --no-auto-update --no-remote --disable-builtin-mcps --no-ask-user
        --effort "$REASONING_EFFORT"
    )
    if [ "$mode" = team ]; then
        COPILOT_ARGS+=(--additional-mcp-config=@/work/.mcp.json)
        while IFS= read -r deny_tool; do
            COPILOT_ARGS+=("--deny-tool=$deny_tool")
            model_tool="${deny_tool/(/-}"
            COPILOT_ARGS+=("--excluded-tools=${model_tool%)}")
            count=$((count + 1))
        done < <(jq -r '.[]' "$CONFIG_DIR/mcp_deny_tools.json")
        [ "$count" -gt 0 ] || { echo '[entrypoint] FATAL: no Copilot MCP exclusions configured' >&2; exit 1; }
    fi
}
