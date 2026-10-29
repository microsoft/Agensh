# Extend a task cleanroom with exactly one harness, selected by AGENT_HARNESS.
# npm stays in build stages; final images include only the selected runtime.
ARG TASK_IMAGE
ARG AGENT_BASE_IMAGE=omcgitea-agent-base:pbench
ARG AGENT_HARNESS=copilot
ARG PI_NODE_IMAGE=node:22.19.0-bookworm-slim
ARG COPILOT_NODE_IMAGE=node:22.14.0-bookworm-slim

FROM ${AGENT_BASE_IMAGE} AS mcp_src

FROM ${PI_NODE_IMAGE} AS pi_install
ARG PI_CLI_VERSION=1.4.0
WORKDIR /opt/pi-cli
RUN npm init -y >/dev/null \
    && npm install --ignore-scripts --omit=dev --no-audit --no-fund --save-exact \
        @earendil-works/pi-coding-agent@${PI_CLI_VERSION}

FROM ${COPILOT_NODE_IMAGE} AS copilot_install
ARG COPILOT_CLI_VERSION=1.0.70
WORKDIR /opt/copilot-cli
RUN npm init -y >/dev/null \
    && npm install --omit=dev --no-audit --no-fund --save-exact \
        @github/copilot@${COPILOT_CLI_VERSION}

FROM ${PI_NODE_IMAGE} AS codex_install
ARG CODEX_CLI_VERSION=0.164.0
WORKDIR /opt/codex-install
RUN npm init -y >/dev/null \
    && npm install --ignore-scripts --omit=dev --no-audit --no-fund --save-exact \
        @openai/codex@${CODEX_CLI_VERSION} \
    && native="$(find node_modules/@openai -path '*/vendor/*/bin/codex' -type f -print -quit)" \
    && test -n "$native" \
    && vendor="$(dirname "$(dirname "$native")")" \
    && mkdir -p /opt/codex-native/bin /opt/codex-native/codex-path \
    && cp "$native" /opt/codex-native/bin/codex \
    && cp "$vendor/bin/codex-code-mode-host" /opt/codex-native/bin/codex-code-mode-host \
    && cp "$vendor/codex-path/rg" /opt/codex-native/codex-path/rg

FROM ${PI_NODE_IMAGE} AS claude_install
ARG CLAUDE_CLI_VERSION=latest
WORKDIR /opt/claude-install
RUN npm init -y >/dev/null \
    && npm install --ignore-scripts --omit=dev --no-audit --no-fund --save-exact \
        @anthropic-ai/claude-code@${CLAUDE_CLI_VERSION} \
    && native="node_modules/@anthropic-ai/claude-code-linux-$(node -p process.arch)/claude" \
    && test -n "$native" \
    && mkdir -p /opt/claude-native \
    && cp "$native" /opt/claude-native/claude \
    && cp node_modules/@anthropic-ai/claude-code/package.json /opt/claude-native/release.json

FROM ${TASK_IMAGE} AS common
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git jq gettext-base openssh-client sudo procps \
    && rm -rf /var/lib/apt/lists/*

COPY --from=mcp_src /usr/local/bin/gitea-mcp /usr/local/bin/gitea-mcp
RUN chmod +x /usr/local/bin/gitea-mcp
ARG MATTERMOST_MCP_VERSION=0.5.1
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && /root/.local/bin/uv tool install --no-cache "mcp-server-mattermost==${MATTERMOST_MCP_VERSION}" \
    && cp /root/.local/bin/mcp-server-mattermost /usr/local/bin/mcp-server-mattermost \
    && chmod 0711 /root

COPY board-service/mcp.cjs /opt/mcp-board.cjs
COPY prompts/agents.txt       /opt/omcgitea/prompts/agents.md
COPY prompts/pbench_brief.txt /opt/omcgitea/prompts/pbench_brief.md
COPY agent/config/         /opt/omcgitea/config/
COPY agent/entrypoint.sh   /opt/omcgitea/entrypoint.sh
COPY agent/acp_bridge.py   /opt/omcgitea/acp_bridge.py
COPY agent/archive.py      /opt/omcgitea/archive.py
COPY agent/harness_config.py /opt/omcgitea/harness_config.py
COPY agent/check_harness.py /opt/omcgitea/check_harness.py
RUN chmod +x /opt/omcgitea/entrypoint.sh /opt/omcgitea/acp_bridge.py

ENV AGENT_HOME=/opt/data AGENT_NODE=/opt/agentrt/bin/node
ENTRYPOINT ["/opt/omcgitea/entrypoint.sh"]

FROM common AS copilot
COPY --from=copilot_install /usr/local/bin/node /opt/agentrt/bin/node
COPY --from=copilot_install /opt/copilot-cli /opt/copilot-cli
COPY --from=copilot_install /opt/copilot-cli/node_modules/@github/copilot/package.json /opt/omcgitea/copilot/release.json
COPY agent/copilot/ /opt/omcgitea/copilot/
# Keep the selected Copilot dependency and private Node; never use the task's Node.
RUN pkgdir=/opt/copilot-cli/node_modules/@github/copilot; \
    bin="$(/opt/agentrt/bin/node -e "const p=require('${pkgdir}/package.json');const b=p.bin;console.log(typeof b==='string'?b:Object.values(b)[0])")"; \
    printf '%s\n' '#!/bin/sh' "exec /opt/agentrt/bin/node ${pkgdir}/${bin} \"\$@\"" > /usr/local/bin/copilot-wrapped; \
    chmod +x /usr/local/bin/copilot-wrapped; \
    HOME=/tmp/cv COPILOT_HOME=/tmp/cv/.copilot /usr/local/bin/copilot-wrapped --no-auto-update --version
ARG COPILOT_CLI_VERSION=1.0.70
ENV AGENT_HARNESS=copilot COPILOT_CLI_VERSION=${COPILOT_CLI_VERSION} \
    COPILOT_BIN=/usr/local/bin/copilot-wrapped COPILOT_AUTO_UPDATE=false

FROM common AS pi
COPY --from=pi_install /usr/local/bin/node /opt/agentrt/bin/node
COPY --from=pi_install /opt/pi-cli /opt/pi-cli
COPY --from=pi_install /opt/pi-cli/node_modules/@earendil-works/pi-coding-agent/package.json /opt/omcgitea/pi/release.json
COPY agent/pi/ /opt/omcgitea/pi/
RUN printf '%s\n' '#!/bin/sh' \
        'exec /opt/agentrt/bin/node /opt/pi-cli/node_modules/@earendil-works/pi-coding-agent/dist/rpc-entry.js "$@"' \
        > /usr/local/bin/pi-wrapped \
    && chmod +x /usr/local/bin/pi-wrapped \
    && HOME=/tmp/pv PI_OFFLINE=1 /usr/local/bin/pi-wrapped --version
ARG PI_CLI_VERSION=1.4.0
ENV AGENT_HARNESS=pi PI_CLI_VERSION=${PI_CLI_VERSION} PI_BIN=/usr/local/bin/pi-wrapped PI_OFFLINE=1

FROM common AS codex
# Codex is native. This Node binary is only for the existing team MCP helpers.
COPY --from=codex_install /usr/local/bin/node /opt/agentrt/bin/node
COPY --from=codex_install /opt/codex-native /opt/codex-cli
COPY --from=codex_install /opt/codex-install/node_modules/@openai/codex/package.json /opt/omcgitea/codex/release.json
COPY agent/codex/ /opt/omcgitea/codex/
RUN printf '%s\n' '#!/bin/sh' 'export PATH="/opt/codex-cli/codex-path:$PATH"' \
        'exec /opt/codex-cli/bin/codex "$@"' > /usr/local/bin/codex-wrapped \
    && chmod +x /usr/local/bin/codex-wrapped \
    && CODEX_HOME=/opt/codex-build-check /usr/local/bin/codex-wrapped --version \
    && rm -rf /opt/codex-build-check
RUN /usr/local/bin/codex-wrapped debug models --bundled > /opt/omcgitea/codex/models.json
ARG CODEX_CLI_VERSION=0.164.0
ENV AGENT_HARNESS=codex CODEX_CLI_VERSION=${CODEX_CLI_VERSION} CODEX_BIN=/usr/local/bin/codex-wrapped

FROM common AS claude
# Claude Code is native; Node remains only for the shared MCP helpers.
COPY --from=claude_install /usr/local/bin/node /opt/agentrt/bin/node
COPY --from=claude_install /opt/claude-native /opt/claude-cli
COPY --from=claude_install /opt/claude-native/release.json /opt/omcgitea/claude/release.json
COPY agent/claude/ /opt/omcgitea/claude/
RUN printf '%s\n' '#!/bin/sh' 'exec /opt/claude-cli/claude "$@"' > /usr/local/bin/claude-wrapped \
    && chmod +x /usr/local/bin/claude-wrapped \
    && /usr/local/bin/claude-wrapped --version
ARG CLAUDE_CLI_VERSION=latest
ENV AGENT_HARNESS=claude CLAUDE_CLI_VERSION=${CLAUDE_CLI_VERSION} CLAUDE_BIN=/usr/local/bin/claude-wrapped

FROM ${AGENT_HARNESS} AS worker
