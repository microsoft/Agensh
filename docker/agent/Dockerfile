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
#   sudo docker build -f docker/agent/Dockerfile \
#     --build-arg TASK_IMAGE=programbench/<task>:task_cleanroom_v6 \
#     -t omcgitea-agent-<task>:pbench .           # context = repo root

ARG TASK_IMAGE
ARG AGENT_BASE_IMAGE=omcgitea-agent-base:pbench
ARG NODE_IMAGE=node:22.14.0-bookworm-slim

# Stage A: the gitea-mcp binary and claude-agent-acp, taken from the agent base
# image (docker/agent-base), which already holds them: docker.gitea.com is
# unreachable from this host.
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
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && /root/.local/bin/uv tool install --no-cache mcp-server-mattermost \
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
COPY mcp-board/ /opt/mcp-board/
# The prompts the entrypoint reads, config templates and entrypoint, current
# at build time. The launcher prompts in prompts/ are sent from the host.
COPY prompts/team/agents.md       /opt/omcgitea/prompts/agents.md
COPY prompts/team/pbench-brief.md /opt/omcgitea/prompts/pbench-brief.md
COPY docker/agent/config/         /opt/omcgitea/config/
COPY docker/agent/entrypoint.sh   /opt/omcgitea/entrypoint.sh
COPY docker/agent/acp-bridge.py   /opt/omcgitea/acp-bridge.py
RUN chmod +x /opt/omcgitea/entrypoint.sh /opt/omcgitea/acp-bridge.py

# Point the MCP template at the private Node, and drop playwright (no chromium
# here). Fail loudly if the board entry is missing — a silently absent board
# server goes unnoticed for a whole run.
RUN python3 -c "\
import json, pathlib; \
p = pathlib.Path('/opt/omcgitea/config/mcp.json.tmpl'); \
d = json.loads(p.read_text()); \
s = d['mcpServers']; \
s.pop('playwright', None); \
assert 'board' in s, 'mcp.json.tmpl has no board server'; \
s['board']['command'] = '/opt/agentrt/bin/node'; \
p.write_text(json.dumps(d, indent=2) + '\n')"

# @agentclientprotocol/claude-agent-acp for AGENT_KIND=claude. Copied from the
# agent base image rather than re-installed, so the adapter is the same
# in every task image and no npm reaches the network.
# NODE_BIN points the entrypoint at our PRIVATE node: putting it on PATH would
# shadow whatever node the task cleanroom ships, and the grader builds in that
# same cleanroom. Same reason copilot gets a wrapper instead of a symlink.
COPY --from=mcp_src /opt/claude-agent-acp/ /opt/claude-agent-acp/
RUN test -f /opt/claude-agent-acp/dist/index.js \
    && /opt/agentrt/bin/node -e "require('/opt/claude-agent-acp/dist/index.js')" --help >/dev/null 2>&1 || true

# AGENT_KIND defaults to copilot; a profile sets AGENT_KIND=claude for the
# claude path. Both adapters are present either way.
ENV AGENT_HOME=/opt/data \
    AGENT_KIND=copilot \
    COPILOT_BIN=/usr/local/bin/copilot-wrapped \
    NODE_BIN=/opt/agentrt/bin/node \
    AGENT_NODE=/opt/agentrt/bin/node
ENTRYPOINT ["/opt/omcgitea/entrypoint.sh"]
