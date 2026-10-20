# The agent image, built ON TOP OF one task's own cleanroom.
#
# The agent builds in exactly the environment its submission is graded in:
# the same toolchains, libraries and crate versions. A shared image for all
# tasks drifts from each grader (a one-patch-version crate skew is enough for
# "failed to select a version" at eval, scoring 0.00%) and hands every task
# toolchains its grader lacks. Nothing is added that the grader lacks, except
# the agent runtime below.
#
# THE AGENT RUNTIME IS DELIBERATELY OFF $PATH
# copilot-CLI and mcp-board are Node programs, and most cleanrooms have no
# Node (samtools does not; quickjs does). Installing Node on $PATH would
# re-create the same divergence at smaller scale — and worse, hand a JS
# runtime to an agent whose grader has none. So our Node lives at
# /opt/agentrt/bin and is invoked by absolute path only. A cleanroom that
# legitimately ships Node keeps its own, untouched, on $PATH.
#
# Build:
#   sudo docker build -f agent/Dockerfile \
#     --build-arg TASK_IMAGE=programbench/<task>:task_cleanroom_v6 \
#     -t omcgitea-agent-<task>:pbench .           # context = repo root

ARG TASK_IMAGE
ARG AGENT_BASE_IMAGE=omcgitea-agent-base:pbench
ARG NODE_IMAGE=node:22.14.0-bookworm-slim

# Stage A: the unmodified Gitea MCP binary, cached in a small artifact image.
FROM ${AGENT_BASE_IMAGE} AS mcp_src

# Stage B: a Node runtime we relocate under /opt/agentrt (never onto $PATH).
FROM ${NODE_IMAGE} AS node_src

# Stage C: the task's own cleanroom — toolchains, libs and crate versions
# exactly as the grader will have them.
FROM ${TASK_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive

# Only what the harness itself needs. Everything a task needs to BUILD is
# already in the cleanroom; if an agent needs more it must apt-get it at dev
# time, which is the same request path a real cleanroom-eval agent has.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git jq gettext-base openssh-client sudo procps \
    && rm -rf /var/lib/apt/lists/*

# Agent runtime: Node off $PATH (see header).
COPY --from=node_src /usr/local/bin/node /opt/agentrt/bin/node
COPY --from=node_src /usr/local/lib/node_modules /opt/agentrt/lib/node_modules
RUN ln -sf /opt/agentrt/lib/node_modules/npm/bin/npm-cli.js /opt/agentrt/bin/npm \
    && chmod +x /opt/agentrt/bin/node /opt/agentrt/bin/npm \
    && /opt/agentrt/bin/node --version

# gitea half of the coordination deps.
COPY --from=mcp_src /usr/local/bin/gitea-mcp /usr/local/bin/gitea-mcp
RUN chmod +x /usr/local/bin/gitea-mcp

# mattermost half. uv is fetched to /root/.local; /root stays 0711 so an ACP
# child on a non-root uid can traverse to the venv shebang.
# Match the main experiment's cached image rather than adding tools on rebuild.
ARG MATTERMOST_MCP_VERSION=0.5.1
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && /root/.local/bin/uv tool install --no-cache "mcp-server-mattermost==${MATTERMOST_MCP_VERSION}" \
    && cp /root/.local/bin/mcp-server-mattermost /usr/local/bin/mcp-server-mattermost \
    && chmod 0711 /root

# copilot-CLI, run through the private Node.
ARG COPILOT_CLI_VERSION=1.0.70
ENV COPILOT_CLI_VERSION=${COPILOT_CLI_VERSION} \
    COPILOT_AUTO_UPDATE=false
# PATH is set for THIS RUN only (npm's own stub is `#!/usr/bin/env node`);
# the image's runtime PATH never gains Node.
RUN export PATH=/opt/agentrt/bin:$PATH \
    && mkdir -p /opt/copilot-cli && cd /opt/copilot-cli \
    && npm init -y >/dev/null \
    && npm install --omit=dev --no-audit --no-fund --save-exact \
        @github/copilot@${COPILOT_CLI_VERSION} \
    && test -x /opt/copilot-cli/node_modules/.bin/copilot

# copilot's own bin stub is `#!/usr/bin/env node`, which would need Node on
# $PATH — the exact thing we are avoiding. Resolve the real entry script and
# point the wrapper at it.
RUN entry="$(/opt/agentrt/bin/node -e "console.log(require.resolve('@github/copilot/package.json'))" 2>/dev/null || true)"; \
    pkgdir="$(dirname "${entry:-/opt/copilot-cli/node_modules/@github/copilot/package.json}")"; \
    bin="$(/opt/agentrt/bin/node -e "const p=require('${pkgdir}/package.json');const b=p.bin;console.log(typeof b==='string'?b:Object.values(b)[0])")"; \
    printf '%s\n' '#!/bin/sh' "exec /opt/agentrt/bin/node ${pkgdir}/${bin} \"\$@\"" > /usr/local/bin/copilot-wrapped; \
    chmod +x /usr/local/bin/copilot-wrapped; \
    HOME=/tmp/cv COPILOT_HOME=/tmp/cv/.copilot /usr/local/bin/copilot-wrapped --no-auto-update --version

# mcp-board: the shared-context board client. Baked in rather than
# bind-mounted — the bind mount is why the board MCP silently failed to
# register for an entire round when the baked mcp.json.tmpl predated it.
COPY board-service/mcp.cjs /opt/mcp-board.cjs
# The prompts the entrypoint reads, config templates and entrypoint, current
# at build time. The launcher prompts in prompts/ are sent from the host.
COPY prompts/agents.md       /opt/omcgitea/prompts/agents.md
COPY prompts/pbench-brief.md /opt/omcgitea/prompts/pbench-brief.md
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
