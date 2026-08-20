#!/bin/bash
# omcgitea agent entrypoint — supports three AGENT_KIND values:
#
#   AGENT_KIND=claude  (default, main path after R-cache-bug switchover)
#       Runs @agentclientprotocol/claude-agent-acp on stdio, exposed via
#       acp-bridge.py over /var/run/acp/agent.sock. MCP servers come from
#       /work/.mcp.json (rendered from templates-claude/mcp.json.tmpl).
#       Permissions/whitelist come from /work/.claude/settings.json.
#
#   AGENT_KIND=copilot (opt-in)
#       Runs the official, unmodified GitHub Copilot CLI native ACP server
#       (`copilot --acp --stdio`) with deployment-owned BYOK credentials.
#       No GitHub login/token/hosted model is used. Instructions come from
#       /work/AGENTS.md and MCP servers from /work/.mcp.json.
#
#   AGENT_KIND=hermes  (dormant, kept for compatibility & A/B fallback)
#       Original hermes path: render config.yaml/.env/AGENTS.md, exec
#       upstream hermes entrypoint, expose acp_adapter via acp-bridge.
#
# Inputs (env, common):
#   AGENT_KIND              "claude" (default) | "copilot" | "hermes"
#   AGENT_NAME              identity used in Gitea + DNS
#   GITEA_HOST              http://gitea:3000
#   GITEA_TOKEN_FILE        /run/omcgitea/agent.token
#   ANTHROPIC_BASE_URL      e.g. http://host.docker.internal:4141
#   ANTHROPIC_MODEL         claude-opus-4.7
#   ANTHROPIC_API_KEY       (any string for local proxy)
#   MATTERMOST_HOST         optional
#   MATTERMOST_TOKEN_FILE   optional, /run/omcgitea/tokens/agent-<name>-mm.token
#
# Inputs (volume): mounted at $HERMES_HOME (/opt/data) — kept name HERMES_HOME
# for backward compatibility; under AGENT_KIND=claude this is the agent state
# dir for claude-agent-acp / Claude Agent SDK as well.
set -euo pipefail

: "${AGENT_KIND:=claude}"
: "${AGENT_NAME:?AGENT_NAME required}"
: "${GITEA_HOST:=http://gitea:3000}"
: "${GITEA_TOKEN_FILE:=/run/omcgitea/agent.token}"
: "${ANTHROPIC_BASE_URL:?ANTHROPIC_BASE_URL required}"
: "${ANTHROPIC_MODEL:=claude-opus-4.7}"
: "${ANTHROPIC_API_KEY:=local-proxy-no-auth}"

case "$AGENT_KIND" in
  claude|copilot|hermes) ;;
  *)
    echo "[entrypoint] FATAL: unknown AGENT_KIND=$AGENT_KIND (expected claude|copilot|hermes)" >&2
    exit 1
    ;;
esac

# Where the agent runtime lives. On the union image (v48-cleanroom) Node is a
# normal PATH install and these defaults reproduce the historical behaviour
# exactly. On a per-task image (Dockerfile.pertask) the image is built FROM the
# task's own ProgramBench cleanroom, so our Node must stay OFF $PATH — putting
# it there would hand a JS runtime to an agent whose grader has none, which is
# the divergence the per-task image exists to remove. Both are therefore
# addressed by absolute path, supplied by the image itself.
#
# AGENT_NODE must be exported before any mcp.json.tmpl render: envsubst can
# only substitute variables that are already in the environment, and a blank
# `command` makes the board MCP fail to register silently.
COPILOT_BIN="${COPILOT_BIN:-/opt/copilot-cli/node_modules/.bin/copilot}"
export AGENT_NODE="${AGENT_NODE:-/usr/local/bin/node}"

HERMES_HOME="${HERMES_HOME:-/opt/data}"
TMPL_DIR=/opt/omcgitea
UPSTREAM_ENTRYPOINT=/opt/hermes/docker/entrypoint.sh

# Persistence note: Hermes writes memories/skills/sessions under
# $HERMES_HOME (NOT $HOME). Container $HOME stays /root, but the upstream
# entrypoint creates $HERMES_HOME/{memories,skills,sessions,...} and the
# python code resolves those via hermes_constants.get_hermes_home(), so
# memories survive `make down && make up` because /opt/data is bind-mounted
# to .claude-team-data/hermes/<agent>/. Don't be tempted to set HOME=$HERMES_HOME.

if [ ! -r "$GITEA_TOKEN_FILE" ]; then
    echo "[entrypoint] FATAL: GITEA_TOKEN_FILE=$GITEA_TOKEN_FILE not readable" >&2
    exit 1
fi

GITEA_TOKEN=$(cat "$GITEA_TOKEN_FILE")
export GITEA_TOKEN GITEA_HOST

# R8: per-agent mattermost token (optional). If MATTERMOST_HOST is unset
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
mkdir -p "$HERMES_HOME"

render() {
    # render < $TMPL_DIR/foo.tmpl > target — substitute ${VAR} from current env.
    local src="$1" dst="$2"
    envsubst < "$src" > "$dst"
}

# Remove MCP server entries that cannot start in this image. A server whose
# command is missing is not a warning to the agent runtime — the subprocess
# dies and the tool namespace it owns is simply absent, which is how the board
# MCP went unregistered for a whole round without anyone noticing.
#
# Both entries are pruned by presence, not by profile, because the board
# overlay bind-mounts the host's mcp.json.tmpl over the image's own — so any
# fix baked at build time is shadowed at runtime and has to be re-applied here.
#   board      — dev/prod/sweep_5 profiles run no board-service.
#   playwright — needs /usr/bin/npx + chromium; no ProgramBench cleanroom has
#                either, and the per-task images deliberately do not add them.
prune_mcp_servers() {
    local f="$1"
    command -v jq >/dev/null 2>&1 || return 0
    local filter='.'
    [ -z "${BOARD_SERVICE_URL:-}" ] && filter="$filter | del(.mcpServers.board)"
    [ -x "$(command -v npx 2>/dev/null)" ] || filter="$filter | del(.mcpServers.playwright)"
    [ "$filter" = "." ] && return 0
    jq "$filter" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
}

resolve_role_fragments() {
    if [ -z "${AGENT_ROLE:-}" ]; then
        case "$AGENT_NAME" in
            *director*) AGENT_ROLE=director ;;
            *lead*)     AGENT_ROLE=lead ;;
            *reviewer*) AGENT_ROLE=reviewer ;;
            *worker*|*coder*) AGENT_ROLE=coder ;;
            *) AGENT_ROLE=coder ;;
        esac
    fi
    export AGENT_ROLE
    echo "[entrypoint] AGENT_ROLE=$AGENT_ROLE (resolved for $AGENT_NAME)"

    ROLES_DIR="$TMPL_DIR/templates-claude/roles"
    ROLE_DIR="$ROLES_DIR/${AGENT_ROLE}"
    if [ ! -d "$ROLE_DIR" ]; then
        echo "[entrypoint] WARN: $ROLE_DIR missing, falling back to coder/" >&2
        ROLE_DIR="$ROLES_DIR/coder"
    fi

    # `export X="$(cat missing)"` returns 0 -- the export builtin masks the
    # substitution's status -- so a missing fragment silently rendered that whole
    # prompt section as the empty string with nothing but a `cat:` line on
    # stderr. That is not hypothetical: through sweep 6.4 the 1team coder role
    # shipped only three of the six files. Fail loudly instead.
    #
    # Require exactly the fragments THIS prompt splices, not a hard-coded six.
    # base.md is the outer template (the board profile mounts base.board.md over
    # it), so reading it here reflects the prompt that will actually render.
    # templates-claude/ splices all six; the 1team prompt carries only how the
    # benchmark works and the role's one-liner. Demanding the other four there
    # meant four byte-identical placeholder stubs per role -- and director_lead
    # is bind-mounted as a whole DIRECTORY, so it has no baked fallback and the
    # agent would exit 1 at boot rather than render a shorter prompt.
    local _need
    _need="$(grep -ohE '\$\{ROLE_[A-Z_]+\}' "$ROLES_DIR/base.md" 2>/dev/null \
             | sed -e 's/^\${ROLE_//' -e 's/}$//' \
             | tr '[:upper:]' '[:lower:]' | sort -u)"
    # A guard that silently requires nothing is worse than one that over-requires:
    # if base.md is unreadable, fall back to demanding the full set.
    [ -n "$_need" ] || _need="name one_liner dos donts workflow failure_modes"

    local _f
    for _f in $_need; do
        if [ ! -s "$ROLE_DIR/$_f.md" ]; then
            echo "[entrypoint] FATAL: $ROLE_DIR/$_f.md missing or empty --" \
                 "the agent would boot with an empty prompt section" >&2
            exit 1
        fi
    done

    # Unspliced fragments may legitimately be absent now, so read them tolerantly
    # instead of letting `cat` spray "No such file" for every agent start.
    _frag() { [ -s "$ROLE_DIR/$1.md" ] && cat "$ROLE_DIR/$1.md"; }
    export ROLE_NAME="$(_frag name)"
    export ROLE_ONE_LINER="$(_frag one_liner)"
    export ROLE_DOS="$(_frag dos)"
    export ROLE_DONTS="$(_frag donts)"
    export ROLE_WORKFLOW="$(_frag workflow)"
    export ROLE_FAILURE_MODES="$(_frag failure_modes)"
}

resolve_pbench_brief() {
    PBENCH_BRIEF=""
    # Two ways to opt in. ACP_CHILD_UID is the single-agent pbench path, which
    # sets it anyway for the privilege drop. The team profiles do NOT set it, so
    # they went through sweeps 6.5 and 6.6 with ${PBENCH_BRIEF} expanding to the
    # empty string: no goal statement, no iron rules, and no "root compile.sh
    # must produce ./executable, or 0 points" in any agent's system prompt. Only
    # the runner's opening mattermost post carried it, once, in hour zero.
    # Gating on the file existing is NOT an option: templates-claude ships a
    # pbench-brief.md in the base image, so dev/prod would start rendering it.
    if { [ -n "${ACP_CHILD_UID:-}" ] || [ "${PBENCH_BRIEF_ENABLE:-0}" = "1" ]; } \
       && [ -f "$TMPL_DIR/templates-claude/pbench-brief.md" ]; then
        PBENCH_BRIEF="$(cat "$TMPL_DIR/templates-claude/pbench-brief.md")"
    fi
    export PBENCH_BRIEF
}

# DeLM shared context: splice the board protocol into CLAUDE.md/AGENTS.md when
# this profile runs a board-service. Gated on BOARD_SERVICE_URL so dev/prod and
# the non-board pbench profiles render byte-for-byte unchanged (same contract as
# resolve_pbench_brief above).
resolve_board_preamble() {
    BOARD_PREAMBLE=""
    if [ -n "${BOARD_SERVICE_URL:-}" ] && [ -f "$TMPL_DIR/templates-claude/board-preamble.md" ]; then
        # envsubst on base.md expands ${BOARD_PREAMBLE}, but does NOT re-expand
        # the text it just inserted — so any ${VAR} inside the preamble would
        # reach the agent literally (it did: agents were told to publish "on
        # board ${BOARD_IDS}"). Expand the preamble first.
        BOARD_PREAMBLE="$(envsubst < "$TMPL_DIR/templates-claude/board-preamble.md")"
    fi
    export BOARD_PREAMBLE
}

export GITEA_HOST AGENT_NAME GITEA_TOKEN \
       ANTHROPIC_BASE_URL ANTHROPIC_MODEL ANTHROPIC_API_KEY \
       MATTERMOST_HOST MATTERMOST_TOKEN

# Common: per-agent git credentials (used by both kinds — agents do real
# git clone/push to gitea regardless of which LLM brain is driving them).
GITEA_HOST_NOPROTO=${GITEA_HOST#http://}
GITEA_HOST_NOPROTO=${GITEA_HOST_NOPROTO#https://}
HERMES_TOOLS_HOME="$HERMES_HOME/home"
mkdir -p "$HERMES_TOOLS_HOME"
cred="$HERMES_TOOLS_HOME/.git-credentials"
echo "http://${AGENT_NAME}:${GITEA_TOKEN}@${GITEA_HOST_NOPROTO}" > "$cred"
chmod 600 "$cred"
git_cfg="$HERMES_TOOLS_HOME/.gitconfig"
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
  hermes)
    # ---------- HERMES PATH (dormant; kept for AGENT_KIND=hermes opt-in) ----
    # Render hermes-specific config + .env + AGENTS.md into HERMES_HOME / /work.
    render "$TMPL_DIR/templates-hermes/config.yaml.tmpl" "$HERMES_HOME/config.yaml"
    render "$TMPL_DIR/templates-hermes/env.tmpl"         "$HERMES_HOME/.env"
    chmod 600 "$HERMES_HOME/.env" "$HERMES_HOME/config.yaml" || true
    mkdir -p /work
    render "$TMPL_DIR/templates-hermes/AGENTS.md.tmpl" "/work/AGENTS.md"
    chmod 644 /work/AGENTS.md || true

    if [ "$(id -u)" = "0" ]; then
        chown -R 10000:10000 "$HERMES_HOME"
        chown -R 10000:10000 /work || true
    fi

    echo "[entrypoint] omcgitea AGENT_KIND=hermes agent=$AGENT_NAME gitea=$GITEA_HOST llm=$ANTHROPIC_BASE_URL ($ANTHROPIC_MODEL)"
    echo "[entrypoint] handing off to upstream entrypoint with args: $*"

    # R7 ACP bridge over hermes' acp_adapter.entry
    ACP_PY=/opt/hermes/.venv/bin/python
    [ -x "$ACP_PY" ] || ACP_PY=python
    /opt/omcgitea/acp-bridge.py "$ACP_SOCK" 10000 10000 -- \
        "$ACP_PY" -m acp_adapter.entry \
        >&2 &
    ACP_BRIDGE_PID=$!
    echo "[entrypoint] acp bridge started pid=$ACP_BRIDGE_PID sock=$ACP_SOCK kind=hermes"

    # Hermes upstream gateway scans MATTERMOST_TOKEN/MATTERMOST_URL env to
    # auto-enable a built-in mattermost messaging platform — we don't want
    # that (router is the sole event source). Unset right before exec.
    unset MATTERMOST_TOKEN MATTERMOST_HOST

    exec "$UPSTREAM_ENTRYPOINT" "$@"
    ;;

  claude)
    # ---------- CLAUDE PATH (default, main path after R-cache-bug) ----------------
    # Renders /work/CLAUDE.md (assembled from role-aware templates),
    # /work/.mcp.json (auto-loaded by claude CLI), and
    # /work/.claude/settings.json (effortLevel + permissions deny list),
    # then starts @agentclientprotocol/claude-agent-acp on stdio behind
    # acp-bridge.
    mkdir -p /work /work/.claude

    # Assemble CLAUDE.md from the shared role fragments. Compose-injected
    # AGENT_ROLE wins; otherwise infer it from AGENT_NAME.
    resolve_role_fragments

    # pbench-only task brief (opt-in): only the org-pbench profile sets the
    # pbench gate (ACP_CHILD_UID, injected solely by docker-compose.pbench.yml).
    # When gated on, splice the ProgramBench brief into CLAUDE.md so the whole
    # team knows it's a reverse-engineering benchmark (run the binary, rebuild
    # from behavior, fully autonomous, no internet). dev/prod leave the gate
    # unset → PBENCH_BRIEF stays empty → CLAUDE.md byte-for-byte unchanged.
    resolve_pbench_brief
    resolve_board_preamble

    envsubst < "$ROLES_DIR/base.md" > /work/CLAUDE.md
    # Mirror to AGENTS.md for any tool that still expects that filename
    # (claude CLI itself only reads CLAUDE.md).
    cp /work/CLAUDE.md /work/AGENTS.md

    render "$TMPL_DIR/templates-claude/mcp.json.tmpl"    "/work/.mcp.json"
    render "$TMPL_DIR/templates-claude/settings.json.tmpl" "/work/.claude/settings.json"
    prune_mcp_servers /work/.mcp.json
    chmod 644 /work/AGENTS.md /work/CLAUDE.md /work/.mcp.json /work/.claude/settings.json || true

    # claude-agent-acp expects HOME for ~/.claude/* state. Point it at the
    # bind-mounted volume so memories/sessions persist across container
    # restarts (parallel to hermes' HERMES_HOME contract). Must happen
    # BEFORE the chown block so the recursive chown covers .claude and the
    # uid-10000 ACP child can write sessions/projects/plans into it.
    export HOME="$HERMES_HOME/home"
    mkdir -p "$HOME/.claude"

    if [ "$(id -u)" = "0" ]; then
        chown -R 10000:10000 "$HERMES_HOME"
        chown -R 10000:10000 /work || true
    fi

    echo "[entrypoint] omcgitea AGENT_KIND=claude agent=$AGENT_NAME gitea=$GITEA_HOST llm=$ANTHROPIC_BASE_URL ($ANTHROPIC_MODEL)"

    # claude-agent-acp expects HOME for ~/.claude/* state. Point it at the
    # bind-mounted volume so memories/sessions persist across container
    # restarts (parallel to hermes' HERMES_HOME contract).
    export HOME="$HERMES_HOME/home"
    mkdir -p "$HOME/.claude"
    # mkdir runs as root AFTER the chown -R above; on a freshly-created data
    # dir this leaves $HOME/.claude root-owned, so the non-root (uid 10000)
    # claude child (pbench profiles drop privileges via ACP_CHILD_UID) cannot
    # write its ~/.claude/projects/<session>.jsonl transcript. chown it back.
    [ "$(id -u)" = "0" ] && chown 10000:10000 "$HOME" "$HOME/.claude" 2>/dev/null || true

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

  copilot)
    # ---------- COPILOT CLI PATH (opt-in, native ACP + BYOK) ---------------
    # Keep this path independent from Claude's settings files: Copilot reads
    # AGENTS.md itself and receives the MCP config explicitly on argv.
    mkdir -p /work
    resolve_role_fragments
    resolve_pbench_brief
    resolve_board_preamble
    envsubst < "$ROLES_DIR/base.md" > /work/AGENTS.md
    cp /work/AGENTS.md /work/CLAUDE.md
    render "$TMPL_DIR/templates-claude/mcp.json.tmpl" "/work/.mcp.json"
    prune_mcp_servers /work/.mcp.json
    chmod 644 /work/AGENTS.md /work/CLAUDE.md /work/.mcp.json || true

    if [ "$(id -u)" = "0" ]; then
        chown -R 10000:10000 "$HERMES_HOME"
        chown -R 10000:10000 /work || true
    fi

    export HOME="$HERMES_HOME/home"
    export COPILOT_HOME="$HOME/.copilot"
    mkdir -p "$COPILOT_HOME"
    if [ "$(id -u)" = "0" ]; then
        chown 10000:10000 "$HOME" "$COPILOT_HOME" 2>/dev/null || true
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
    COPILOT_DENY_COUNT=0
    while IFS= read -r deny_tool; do
        COPILOT_ARGS+=("--deny-tool=$deny_tool")
        COPILOT_DENY_COUNT=$((COPILOT_DENY_COUNT + 1))
    done < <(
        jq -r '.permissions.deny[]
          | capture("^mcp__(?<server>[^_]+)__(?<tool>.+)$")
          | "\(.server)(\(.tool))"' \
          "$TMPL_DIR/templates-claude/settings.json.tmpl"
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
    echo "[entrypoint] FATAL: unknown AGENT_KIND=$AGENT_KIND (expected claude|copilot|hermes)" >&2
    exit 1
    ;;
esac
