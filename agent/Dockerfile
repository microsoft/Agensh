# Extend a ProgramBench cleanroom with Copilot and the organization's MCP tools.
# Build from the repository root so board-service/ and prompts/ are available.
ARG TASK_IMAGE
ARG AGENT_BASE_IMAGE=omcgitea-agent-base:pbench
ARG NODE_IMAGE=node:22.14.0-bookworm-slim

FROM ${AGENT_BASE_IMAGE} AS mcp_src

FROM ${NODE_IMAGE} AS node_src

FROM ${TASK_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git jq gettext-base openssh-client sudo procps \
    && rm -rf /var/lib/apt/lists/*

# Keep the agent's Node runtime separate from the task image's toolchain.
COPY --from=node_src /usr/local/bin/node /opt/agentrt/bin/node
COPY --from=node_src /usr/local/lib/node_modules /opt/agentrt/lib/node_modules
RUN ln -sf /opt/agentrt/lib/node_modules/npm/bin/npm-cli.js /opt/agentrt/bin/npm \
    && chmod +x /opt/agentrt/bin/node /opt/agentrt/bin/npm \
    && /opt/agentrt/bin/node --version

COPY --from=mcp_src /usr/local/bin/gitea-mcp /usr/local/bin/gitea-mcp
RUN chmod +x /usr/local/bin/gitea-mcp

ARG MATTERMOST_MCP_VERSION=0.5.1
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && /root/.local/bin/uv tool install --no-cache "mcp-server-mattermost==${MATTERMOST_MCP_VERSION}" \
    && cp /root/.local/bin/mcp-server-mattermost /usr/local/bin/mcp-server-mattermost \
    && chmod 0711 /root

ARG COPILOT_CLI_VERSION=1.0.70
# Pin the harness version so worker runs use the same tool and session behavior.
ENV COPILOT_CLI_VERSION=${COPILOT_CLI_VERSION} \
    COPILOT_AUTO_UPDATE=false
RUN export PATH=/opt/agentrt/bin:$PATH \
    && mkdir -p /opt/copilot-cli && cd /opt/copilot-cli \
    && npm init -y >/dev/null \
    && npm install --omit=dev --no-audit --no-fund --save-exact \
        @github/copilot@${COPILOT_CLI_VERSION} \
    && test -x /opt/copilot-cli/node_modules/.bin/copilot

# Resolve Copilot's entry point and force it to use the bundled Node binary.
RUN entry="$(/opt/agentrt/bin/node -e "console.log(require.resolve('@github/copilot/package.json'))" 2>/dev/null || true)"; \
    pkgdir="$(dirname "${entry:-/opt/copilot-cli/node_modules/@github/copilot/package.json}")"; \
    bin="$(/opt/agentrt/bin/node -e "const p=require('${pkgdir}/package.json');const b=p.bin;console.log(typeof b==='string'?b:Object.values(b)[0])")"; \
    printf '%s\n' '#!/bin/sh' "exec /opt/agentrt/bin/node ${pkgdir}/${bin} \"\$@\"" > /usr/local/bin/copilot-wrapped; \
    chmod +x /usr/local/bin/copilot-wrapped; \
    HOME=/tmp/cv COPILOT_HOME=/tmp/cv/.copilot /usr/local/bin/copilot-wrapped --no-auto-update --version

COPY board-service/mcp.cjs /opt/mcp-board.cjs
COPY prompts/agents.txt       /opt/omcgitea/prompts/agents.md
COPY prompts/pbench-brief.txt /opt/omcgitea/prompts/pbench-brief.md
COPY agent/config/         /opt/omcgitea/config/
COPY agent/entrypoint.sh   /opt/omcgitea/entrypoint.sh
COPY agent/acp-bridge.py   /opt/omcgitea/acp-bridge.py
COPY agent/archive.py      /opt/omcgitea/archive.py
RUN chmod +x /opt/omcgitea/entrypoint.sh /opt/omcgitea/acp-bridge.py

ENV AGENT_HOME=/opt/data \
    AGENT_KIND=copilot \
    COPILOT_BIN=/usr/local/bin/copilot-wrapped \
    AGENT_NODE=/opt/agentrt/bin/node
ENTRYPOINT ["/opt/omcgitea/entrypoint.sh"]
