#!/bin/bash
# omcgitea agent entrypoint — supports these AGENT_KIND values:
#
#   AGENT_KIND=claude  (default, main path)
#       Runs @agentclientprotocol/claude-agent-acp on stdio, exposed via
#       acp-bridge.py over /var/run/acp/agent.sock. MCP servers come from
#       /work/.mcp.json (rendered from config/mcp.json.tmpl).
#       Permissions/whitelist come from /work/.claude/settings.json.
#
#   AGENT_KIND=copilot (opt-in)
#       Runs the official, unmodified GitHub Copilot CLI native ACP server
#       (`copilot --acp --stdio`) with deployment-owned BYOK credentials.
#       No GitHub login/token/hosted model is used. Instructions come from
#       /work/AGENTS.md and MCP servers from /work/.mcp.json.
#
# Inputs (env, common):
#   AGENT_KIND              "claude" (default) | "copilot" | "sim"
#   AGENT_NAME              identity used in Gitea + DNS
#   GITEA_HOST              http://gitea:3000
#   GITEA_TOKEN_FILE        /run/omcgitea/agent.token
#   ANTHROPIC_BASE_URL      e.g. http://host.docker.internal:4141
#   ANTHROPIC_MODEL         claude-opus-4.7
#   ANTHROPIC_API_KEY       (any string for local proxy)
#   MATTERMOST_HOST         optional
#   MATTERMOST_TOKEN_FILE   optional, /run/omcgitea/tokens/agent-<name>-mm.token
#
# Inputs (volume): the agent state dir, mounted at $AGENT_HOME (/opt/data).
# HOME is $AGENT_HOME/home for every kind.
set -euo pipefail

: "${AGENT_KIND:=claude}"
: "${AGENT_NAME:?AGENT_NAME required}"
: "${GITEA_HOST:=http://gitea:3000}"
: "${GITEA_TOKEN_FILE:=/run/omcgitea/agent.token}"
: "${ANTHROPIC_BASE_URL:?ANTHROPIC_BASE_URL required}"
: "${ANTHROPIC_MODEL:=claude-opus-4.7}"
: "${ANTHROPIC_API_KEY:=local-proxy-no-auth}"

case "$AGENT_KIND" in
  claude|copilot|sim) ;;
  *)
    echo "[entrypoint] FATAL: unknown AGENT_KIND=$AGENT_KIND (expected claude|copilot|sim)" >&2
    exit 1
    ;;
esac

# Where the agent runtime lives. On the sim image (built on docker/agent-base)
# Node is a normal PATH install and these defaults find it. The agent image
# (docker/agent/Dockerfile) is built FROM the task's own ProgramBench cleanroom, so our Node must stay OFF $PATH — putting
# it there would hand a JS runtime to an agent whose grader has none, which is
# the divergence the per-task image exists to remove. Both are therefore
# addressed by absolute path, supplied by the image itself.
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
# Claude Code moves a main-conversation MCP call to a BACKGROUND TASK once it
# crosses CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS; pinned at its 2 min default so the
# threshold is explicit in every run.
export CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS=120000

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

render() {
    # render < $TMPL_DIR/foo.tmpl > target — substitute ${VAR} from current env.
    local src="$1" dst="$2"
    envsubst < "$src" > "$dst"
}

# Remove MCP server entries that cannot start in this image. A server whose
# command is missing is not a warning to the agent runtime — the subprocess
# dies and the tool namespace it owns is simply absent, so a board MCP that
# cannot start goes unregistered without anyone noticing.
#
# Both entries are pruned by presence, not by profile, because the board
# overlay bind-mounts the host's mcp.json.tmpl over the image's own — so any
# fix baked at build time is shadowed at runtime and has to be re-applied here.
#   board      — profiles that run no board-service (BOARD_SERVICE_URL unset).
#   playwright — needs /usr/bin/npx + chromium; no ProgramBench cleanroom has
#                either, and the per-task images deliberately do not add them.
prune_mcp_servers() {
    local f="$1"
    command -v jq >/dev/null 2>&1 || return 0
    local filter='.'
    [ -z "${BOARD_SERVICE_URL:-}" ] && filter="$filter | del(.mcpServers.board)"
    [ -x "$(command -v npx 2>/dev/null)" ] || filter="$filter | del(.mcpServers.playwright)"
    # `timeout` has to reach Copilot as a JSON NUMBER, but the template must
    # stay parseable as JSON with the ${...} placeholders still in it --
    # docker/agent/Dockerfile json.loads() it at BUILD time to rewrite the board
    # command, so a bare `"timeout": ${VAR},` breaks the image build. So it is
    # rendered as a quoted string and converted here, after envsubst.
    #
    # An empty value means the entrypoint never exported MCP_TOOL_TIMEOUT_MS:
    # drop the key entirely so Copilot falls back to its own default rather than receiving
    # "" and failing to parse. That empty case is not hypothetical -- a pinned
    # image whose baked entrypoint predates this export renders `"timeout": ,`
    # and every agent crash-loops on `parse error: Expected value before ','`.
    filter="$filter | .mcpServers |= with_entries(
        if (.value.timeout // \"\") == \"\" then .value |= del(.timeout)
        else .value.timeout |= tonumber end)"
    jq "$filter" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
}

# Can this directory host Copilot's SQLite session store?
#
# Copilot keeps session state in SQLite (session-store.db, and
# session-state/<id>/session.db). SQLite's locking protocol needs fcntl
# byte-range locks, and the Azure Files (CIFS) share that backs $HOME on the k8s
# path cannot serve them: a SINGLE-connection CREATE TABLE + INSERT fails there
# with `database is locked`, while the identical statements succeed on local
# disk -- WAL enabled, and with two concurrent connections. So it is the mount,
# not contention between agents.
#
# This is worth a startup probe because the failure is invisible from outside.
# Copilot answers every ACP prompt with
#   session.error{errorType: query, message: "database is locked"}
# and stopReason end_turn, in about ten seconds, so the pod sits at 2/2 Running
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
    # Fails OPEN if there is no interpreter to probe with: this is a safety net,
    # not a dependency, and refusing to boot over a missing python3 would invent
    # a failure mode nobody has measured. Loud, because an unrun check must not
    # read like a passed one.
    if ! command -v python3 >/dev/null 2>&1; then
        echo "[entrypoint] WARN: no python3; the SQLite-lock probe on $d did NOT run" >&2
        return 0
    fi
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

resolve_pbench_brief() {
    PBENCH_BRIEF=""
    # Two ways to opt in. ACP_CHILD_UID is the single-agent pbench path, which
    # sets it anyway for the privilege drop. The team profiles do NOT set it, so
    # they opt in with PBENCH_BRIEF_ENABLE=1. Without either, ${PBENCH_BRIEF}
    # expands to the empty string: no goal statement, no iron rules, and no
    # "root compile.sh must produce ./executable, or 0 points" in any agent's
    # system prompt. Only the runner's opening mattermost post carries it, once,
    # in hour zero.
    # Gating on the file existing is NOT an option: the image ships
    # pbench-brief.md, so every profile would start rendering it.
    if { [ -n "${ACP_CHILD_UID:-}" ] || [ "${PBENCH_BRIEF_ENABLE:-0}" = "1" ]; } \
       && [ -f "$PROMPTS_DIR/pbench-brief.md" ]; then
        PBENCH_BRIEF="$(cat "$PROMPTS_DIR/pbench-brief.md")"
    fi
    export PBENCH_BRIEF
}

export GITEA_HOST AGENT_NAME GITEA_TOKEN \
       ANTHROPIC_BASE_URL ANTHROPIC_MODEL ANTHROPIC_API_KEY \
       MATTERMOST_HOST MATTERMOST_TOKEN

# Common: per-agent git credentials (used by both kinds — agents do real
# git clone/push to gitea regardless of which LLM brain is driving them).
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

# Common: ACP socket dir for both kinds (acp-bridge listens here)
ACP_SOCK_DIR=/var/run/acp
ACP_SOCK="$ACP_SOCK_DIR/agent.sock"
mkdir -p "$ACP_SOCK_DIR"
rm -f "$ACP_SOCK" 2>/dev/null || true
chown 10000:10000 "$ACP_SOCK_DIR" 2>/dev/null || true

case "$AGENT_KIND" in
  claude)
    # ---------- CLAUDE PATH (default, main path) ----------------------------------
    # Renders /work/CLAUDE.md (from prompts/agents.md),
    # /work/.mcp.json (auto-loaded by claude CLI), and
    # /work/.claude/settings.json (effortLevel + permissions deny list),
    # then starts @agentclientprotocol/claude-agent-acp on stdio behind
    # acp-bridge.
    mkdir -p /work /work/.claude

    # pbench-only task brief (opt-in): only the pbench profiles set the
    # pbench gate (ACP_CHILD_UID, injected solely by docker-compose.pbench.yml).
    # When gated on, splice the ProgramBench brief into CLAUDE.md so the whole
    # team knows it's a reverse-engineering benchmark (run the binary, rebuild
    # from behavior, fully autonomous, no internet). dev/prod leave the gate
    # unset → PBENCH_BRIEF stays empty → CLAUDE.md byte-for-byte unchanged.
    resolve_pbench_brief

    envsubst < "$PROMPTS_DIR/agents.md" > /work/CLAUDE.md
    # Mirror to AGENTS.md for any tool that still expects that filename
    # (claude CLI itself only reads CLAUDE.md).
    cp /work/CLAUDE.md /work/AGENTS.md

    render "$CONFIG_DIR/mcp.json.tmpl"      "/work/.mcp.json"
    render "$CONFIG_DIR/settings.json.tmpl" "/work/.claude/settings.json"
    prune_mcp_servers /work/.mcp.json
    chmod 644 /work/AGENTS.md /work/CLAUDE.md /work/.mcp.json /work/.claude/settings.json || true

    # claude-agent-acp expects HOME for ~/.claude/* state. Point it at the
    # bind-mounted volume so memories/sessions persist across container
    # restarts. Must happen
    # BEFORE the chown block so the recursive chown covers .claude and the
    # uid-10000 ACP child can write sessions/projects/plans into it.
    export HOME="$AGENT_HOME/home"
    mkdir -p "$HOME/.claude"

    if [ "$(id -u)" = "0" ]; then
        chown -R 10000:10000 "$AGENT_HOME"
        chown -R 10000:10000 /work || true
    fi

    echo "[entrypoint] omcgitea AGENT_KIND=claude agent=$AGENT_NAME gitea=$GITEA_HOST llm=$ANTHROPIC_BASE_URL ($ANTHROPIC_MODEL)"

    CLAUDE_ACP_DIR=/opt/claude-agent-acp
    # pbench bin anti-reverse (opt-in): when ACP_CHILD_UID is injected (only by the
    # pbench compose override), acp-bridge.py spawns the ACP child as that
    # non-root uid so a root:root 0111 reference binary can be executed but
    # not read. The var is inherited by the bridge child automatically; we
    # only surface it here so `docker logs` shows the mode is active. dev/prod
    # never set it → child stays root, unchanged.
    if [ -n "${ACP_CHILD_UID:-}" ]; then
        echo "[entrypoint] pbench mode: ACP child privilege drop uid=${ACP_CHILD_UID} gid=${ACP_CHILD_GID:-$ACP_CHILD_UID}"
    fi
    # NODE_BIN mirrors COPILOT_BIN: the per-task images keep our Node OFF PATH
    # so it cannot shadow a task cleanroom's own toolchain (the grader builds in
    # that same environment). dev/prod images have node on PATH and are unchanged.
    /opt/omcgitea/acp-bridge.py "$ACP_SOCK" 10000 10000 -- \
        "${NODE_BIN:-node}" "$CLAUDE_ACP_DIR/dist/index.js" \
        >&2 &
    ACP_BRIDGE_PID=$!
    echo "[entrypoint] acp bridge started pid=$ACP_BRIDGE_PID sock=$ACP_SOCK kind=claude"

    # Block forever — bridge runs in background; entrypoint must not exit
    # or container will go Restarting.
    wait $ACP_BRIDGE_PID
    ;;

  sim)
    # ---------- SIM PATH (no LLM) ------------------------------------------
    # Deliberately IDENTICAL to the claude path above except for the binary
    # behind acp-bridge. Rendering the same CLAUDE.md / .mcp.json /
    # settings.json is the point: the sim then exercises template rendering,
    # prune_mcp_servers and the uid-10000 privilege drop, and template drift
    # breaks the sim run rather than surfacing six hours into a real run.
    #
    # The sim reads /work/.mcp.json and spawns those servers itself, so the
    # MCP surface (gitea + mattermost + board, each behind mcp-notice-shim) is
    # real. ANTHROPIC_* stays set and is never contacted.
    mkdir -p /work /work/.claude

    resolve_pbench_brief

    envsubst < "$PROMPTS_DIR/agents.md" > /work/CLAUDE.md
    cp /work/CLAUDE.md /work/AGENTS.md

    render "$CONFIG_DIR/mcp.json.tmpl"      "/work/.mcp.json"
    render "$CONFIG_DIR/settings.json.tmpl" "/work/.claude/settings.json"
    prune_mcp_servers /work/.mcp.json
    chmod 644 /work/AGENTS.md /work/CLAUDE.md /work/.mcp.json /work/.claude/settings.json || true

    export HOME="$AGENT_HOME/home"
    mkdir -p "$HOME/.claude"
    # The sim's durable memory (processed event_ids + turn budget) lives here,
    # on the bind-mounted volume: acp-bridge spawns a fresh child per socket
    # connection, so in-memory dedup would reset on every router reconnect.
    export SIM_STATE_DIR="${SIM_STATE_DIR:-$AGENT_HOME/sim}"
    mkdir -p "$SIM_STATE_DIR"

    if [ "$(id -u)" = "0" ]; then
        chown -R 10000:10000 "$AGENT_HOME"
        chown -R 10000:10000 /work || true
    fi

    echo "[entrypoint] omcgitea AGENT_KIND=sim agent=$AGENT_NAME gitea=$GITEA_HOST turns=${PBENCH_SIM_TURNS:-4} (NO LLM)"

    if [ -n "${ACP_CHILD_UID:-}" ]; then
        echo "[entrypoint] pbench mode: ACP child privilege drop uid=${ACP_CHILD_UID} gid=${ACP_CHILD_GID:-$ACP_CHILD_UID}"
    fi

    /opt/omcgitea/acp-bridge.py "$ACP_SOCK" 10000 10000 -- \
        "${NODE_BIN:-node}" /opt/sim-agent/src/main.js \
        >&2 &
    ACP_BRIDGE_PID=$!
    echo "[entrypoint] acp bridge started pid=$ACP_BRIDGE_PID sock=$ACP_SOCK kind=sim"

    wait $ACP_BRIDGE_PID
    ;;

  copilot)
    # ---------- COPILOT CLI PATH (opt-in, native ACP + BYOK) ---------------
    # Keep this path independent from Claude's settings files: Copilot reads
    # AGENTS.md itself and receives the MCP config explicitly on argv.
    mkdir -p /work
    resolve_pbench_brief
    envsubst < "$PROMPTS_DIR/agents.md" > /work/AGENTS.md
    cp /work/AGENTS.md /work/CLAUDE.md
    render "$CONFIG_DIR/mcp.json.tmpl" "/work/.mcp.json"
    prune_mcp_servers /work/.mcp.json
    chmod 644 /work/AGENTS.md /work/CLAUDE.md /work/.mcp.json || true

    if [ "$(id -u)" = "0" ]; then
        chown -R 10000:10000 "$AGENT_HOME"
        chown -R 10000:10000 /work || true
    fi

    export HOME="$AGENT_HOME/home"
    # COPILOT_STATE_DIR relocates ONLY the SQLite-backed session store. $HOME
    # stays where it is -- config.json, the package cache under .cache/copilot,
    # and events.jsonl all write fine on the share, and moving $HOME would
    # change every trajectory path in the repo. Presence-guarded with the
    # previous value as the default: the 149 compose profiles run on ext4, where
    # SQLite works, and must keep their layout byte-for-byte.
    export COPILOT_HOME="${COPILOT_STATE_DIR:-$HOME/.copilot}"
    mkdir -p "$COPILOT_HOME"
    if [ "$(id -u)" = "0" ]; then
        chown 10000:10000 "$HOME" "$COPILOT_HOME" 2>/dev/null || true
    fi
    if ! sqlite_lockable "$COPILOT_HOME"; then
        fs="$(stat -f -c %T "$COPILOT_HOME" 2>/dev/null || echo unknown)"
        echo "[entrypoint] FATAL: COPILOT_HOME=$COPILOT_HOME cannot host Copilot's SQLite session store" >&2
        echo "[entrypoint]   filesystem is '$fs'; SQLite cannot take fcntl byte-range locks on it." >&2
        echo "[entrypoint]   Copilot would answer EVERY prompt with 'database is locked' and end the" >&2
        echo "[entrypoint]   turn without calling the model, while this pod reported 2/2 Running." >&2
        echo "[entrypoint]   Set COPILOT_STATE_DIR to a path on local disk." >&2
        exit 1
    fi

    # ACP 1.0.70 needs provider ApiKeyAuthInfo in addition to the BYOK
    # provider config. Seed the matching alternate-provider auth path with the
    # same deployment-owned key.
    provider_key="$ANTHROPIC_API_KEY"
    COPILOT_PROVIDER_TYPE="${COPILOT_PROVIDER_TYPE:-openai}"
    if [ "$COPILOT_PROVIDER_TYPE" != "openai" ] && [ "$COPILOT_PROVIDER_TYPE" != "anthropic" ]; then
        echo "[entrypoint] FATAL: unsupported COPILOT_PROVIDER_TYPE=$COPILOT_PROVIDER_TYPE" >&2
        exit 1
    fi
    export COPILOT_OFFLINE=true
    export COPILOT_AUTO_UPDATE=false
    export COPILOT_ENABLE_ALT_PROVIDERS=true
    export COPILOT_PROVIDER_TYPE
    export COPILOT_PROVIDER_BASE_URL="$ANTHROPIC_BASE_URL"
    export COPILOT_PROVIDER_API_KEY="$provider_key"
    export COPILOT_MODEL="$ANTHROPIC_MODEL"
    if [ "$COPILOT_PROVIDER_TYPE" = "openai" ]; then
        export OPENAI_API_KEY="$provider_key"
        unset ANTHROPIC_API_KEY
    else
        export ANTHROPIC_API_KEY="$provider_key"
        unset OPENAI_API_KEY
    fi

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
    # PRESENCE-GUARDED, no default: 149 existing profiles run this arm on
    # chat/completions and must keep doing so untouched.
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
        COPILOT_DENY_COUNT=$((COPILOT_DENY_COUNT + 1))
    done < <(
        jq -r '.permissions.deny[]
          | capture("^mcp__(?<server>[^_]+)__(?<tool>.+)$")
          | "\(.server)(\(.tool))"' \
          "$CONFIG_DIR/settings.json.tmpl"
    )
    if [ "$COPILOT_DENY_COUNT" -eq 0 ]; then
        echo "[entrypoint] FATAL: no Copilot deny rules derived from Claude settings" >&2
        exit 1
    fi

    echo "[entrypoint] omcgitea AGENT_KIND=copilot agent=$AGENT_NAME gitea=$GITEA_HOST provider=$COPILOT_PROVIDER_BASE_URL model=$COPILOT_MODEL"
    /opt/omcgitea/acp-bridge.py "$ACP_SOCK" 10000 10000 -- \
        "$COPILOT_BIN" "${COPILOT_ARGS[@]}" \
        >&2 &
    ACP_BRIDGE_PID=$!
    echo "[entrypoint] acp bridge started pid=$ACP_BRIDGE_PID sock=$ACP_SOCK kind=copilot"
    wait $ACP_BRIDGE_PID
    ;;

  *)
    echo "[entrypoint] FATAL: unknown AGENT_KIND=$AGENT_KIND (expected claude|copilot|sim)" >&2
    exit 1
    ;;
esac
