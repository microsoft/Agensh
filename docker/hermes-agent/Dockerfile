# omcgitea agent image — supports AGENT_KIND=claude (default),
# AGENT_KIND=copilot (opt-in), and AGENT_KIND=hermes (dormant). The kind is
# picked at container runtime by entrypoint.sh based on the AGENT_KIND env var.
#
# Builds on the upstream Hermes image (kept as base for the dormant hermes
# path; provides python venv + git + tini) and adds:
#   - git CLI (for clone/push to Gitea)
#   - Gitea official MCP server binary (gitea-mcp) from docker.gitea.com
#   - mcp-server-mattermost (PyPI) for both kinds
#   - node + @agentclientprotocol/claude-agent-acp (for AGENT_KIND=claude)
#   - official, unmodified @github/copilot CLI (for AGENT_KIND=copilot)
#   - Custom entrypoint that picks the right path at boot.
#
# Hermes/Gitea/claude-agent-acp/Copilot CLI source code is NOT modified. We
# only COPY new files in and RUN package managers to add dependencies.

ARG BASE_IMAGE=hermes-agent:local
ARG HERMES_IMAGE
ARG GITEA_MCP_IMAGE=docker.gitea.com/gitea-mcp-server:latest

FROM ${GITEA_MCP_IMAGE} AS mcp_src

FROM ${HERMES_IMAGE:-${BASE_IMAGE}}

USER root

# Common tools needed by the claude path (entrypoint.sh + acp-bridge.py +
# git push/pull + envsubst rendering). Distro-agnostic so cleanroom bases
# from any debian/ubuntu/alpine/rhel family work — ProgramBench cleanrooms
# happen to all be Ubuntu 22.04 today, but pinning to apt-only would bite
# the moment that changes. Node intentionally NOT installed via distro
# package — Ubuntu 22.04 ships node v12, claude-agent-acp needs >=18; we
# install Node ${NODE_VERSION} from the official static tarball below.
RUN set -eux; \
    if command -v apt-get >/dev/null 2>&1; then \
        apt-get update && apt-get install -y --no-install-recommends \
            git ca-certificates curl jq tini gettext-base socat xz-utils \
            python3 python3-pip && \
        rm -rf /var/lib/apt/lists/*; \
    elif command -v apk >/dev/null 2>&1; then \
        apk add --no-cache git ca-certificates curl jq tini gettext socat xz \
            python3 py3-pip bash libstdc++; \
    elif command -v dnf >/dev/null 2>&1; then \
        dnf install -y git ca-certificates curl jq gettext socat xz \
            python3 python3-pip && dnf clean all; \
    elif command -v yum >/dev/null 2>&1; then \
        yum install -y git ca-certificates curl jq gettext socat xz \
            python3 python3-pip && yum clean all; \
    else \
        echo "no known package manager (apt/apk/dnf/yum) on base image" >&2; exit 1; \
    fi

# Node.js via the official static linux tarball (distro-agnostic, version-pinned).
ARG NODE_VERSION=22.14.0
RUN set -eux; \
    arch="$(uname -m)"; \
    case "$arch" in \
        x86_64)        nodearch=x64 ;; \
        aarch64|arm64) nodearch=arm64 ;; \
        *) echo "unsupported arch: $arch" >&2; exit 1 ;; \
    esac; \
    curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${nodearch}.tar.xz" -o /tmp/node.tar.xz; \
    mkdir -p /opt/node; \
    tar -xJf /tmp/node.tar.xz -C /opt/node --strip-components=1; \
    rm -f /tmp/node.tar.xz; \
    ln -sf /opt/node/bin/node /usr/local/bin/node; \
    ln -sf /opt/node/bin/npm  /usr/local/bin/npm; \
    ln -sf /opt/node/bin/npx  /usr/local/bin/npx; \
    node --version

# Bring the Gitea MCP server binary into our image.
# Upstream image (docker.gitea.com/gitea-mcp-server) ships the binary at
# /app/gitea-mcp.
COPY --from=mcp_src /app/gitea-mcp /usr/local/bin/gitea-mcp
RUN chmod +x /usr/local/bin/gitea-mcp && /usr/local/bin/gitea-mcp --version || true

# R8: pre-install mcp-server-mattermost via uv into a dedicated venv so
# `uvx` (or direct binary) starts in <0.5s instead of resolving + downloading
# on every ACP session spawn. Upstream: cloud-ru-tech/mcp-server-mattermost
# (PyPI v0.4+, MIT, 37 tools, FastMCP-based stdio transport).
#
# The installed wrapper's shebang points at the venv python UNDER /root
# (uv installs to /root/.local when building as root). The agent's ACP child
# runs as uid 10000 but gid 0 (root group), so when the kernel posix_spawn()s
# the MCP server it must *traverse* /root — and because egid=0 matches /root's
# group, the GROUP permission class applies. /root defaults to 0700 (group ---),
# so traversal is denied → `EACCES: posix_spawn`. chmod 0711 grants group+other
# search (traverse) only, not read/list, so /root stays otherwise private.
RUN set -eux; \
    if command -v uv >/dev/null 2>&1; then \
        uv tool install --no-cache mcp-server-mattermost && \
        /root/.local/bin/mcp-server-mattermost --help >/dev/null 2>&1 && \
        cp /root/.local/bin/mcp-server-mattermost /usr/local/bin/mcp-server-mattermost && \
        chmod 0711 /root; \
    else \
        # Cleanroom bases lack `uv`; fall back to plain pip.
        pip3 install --no-cache-dir mcp-server-mattermost \
            || pip3 install --no-cache-dir --break-system-packages mcp-server-mattermost; \
        mcp-server-mattermost --help >/dev/null 2>&1; \
    fi
ENV PATH="/root/.local/bin:${PATH}"

# R-cache-bug: install @agentclientprotocol/claude-agent-acp (the default
# AGENT_KIND=claude). Pinned to a version known good at integration time;
# the upstream package itself bundles the Claude Agent SDK as an optional
# platform-dep (linux-x64 binary).
ENV CLAUDE_AGENT_ACP_VERSION=0.33.1
RUN mkdir -p /opt/claude-agent-acp && \
    cd /opt/claude-agent-acp && \
    npm init -y >/dev/null && \
    npm install --omit=dev --no-audit --no-fund \
        @agentclientprotocol/claude-agent-acp@${CLAUDE_AGENT_ACP_VERSION} && \
    # Hoist the package contents up so dist/index.js sits at /opt/claude-agent-acp/dist/
    cp -r node_modules/@agentclientprotocol/claude-agent-acp/dist . && \
    # Sanity check: agent stub responds to ACP initialize
    (echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1,"clientCapabilities":{}}}'; sleep 1) \
        | timeout 5 node dist/index.js 2>/dev/null | grep -q '"protocolVersion":1'

# R-copilot: install the official Copilot CLI npm package at an exact,
# contract-tested version. COPILOT_AUTO_UPDATE is set before the first CLI
# invocation, and runtime also supplies --no-auto-update.
ARG COPILOT_CLI_VERSION=1.0.70
ENV COPILOT_CLI_VERSION=${COPILOT_CLI_VERSION} \
    COPILOT_AUTO_UPDATE=false
RUN mkdir -p /opt/copilot-cli && \
    cd /opt/copilot-cli && \
    npm init -y >/dev/null && \
    npm install --omit=dev --no-audit --no-fund --save-exact \
        @github/copilot@${COPILOT_CLI_VERSION} && \
    test -x /opt/copilot-cli/node_modules/.bin/copilot && \
    mkdir -p /tmp/copilot-version-check && \
    copilot_version="$(HOME=/tmp/copilot-version-check \
        COPILOT_HOME=/tmp/copilot-version-check/.copilot \
        /opt/copilot-cli/node_modules/.bin/copilot --no-auto-update --version \
        | sed -n '1p')" && \
    test "${copilot_version}" = "GitHub Copilot CLI ${COPILOT_CLI_VERSION}." && \
    rm -rf /tmp/copilot-version-check

# Pre-install playwright + chromium so all agents can use mcp__playwright__*
# tools without the per-container 170MB chromium download on first use.
# Image grows ~280MB (chromium + playwright npm deps); shared across all
# agent containers via the single base layer.
RUN if command -v apt-get >/dev/null 2>&1; then \
        apt-get update && apt-get install -y --no-install-recommends \
            libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
            libcups2 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
            libgbm1 libxkbcommon0 libpango-1.0-0 libcairo2 libasound2 \
            libatspi2.0-0 fonts-liberation libdrm2 && \
        rm -rf /var/lib/apt/lists/*; \
    else \
        echo "[hermes-agent.Dockerfile] WARN: non-apt base — playwright chromium libs not preinstalled; mcp__playwright__* will fail at runtime"; \
    fi && \
    # Install chromium into shared playwright cache so npx @playwright/mcp@latest
    # finds it instead of re-downloading per session.
    npx -y playwright install chromium 2>&1 | tail -5

# Templates baked into the image; Copilot reuses the Claude AGENTS/MCP sources
# and only changes the runtime-specific launch flags.
COPY templates-claude/ /opt/omcgitea/templates-claude/
COPY templates-hermes/ /opt/omcgitea/templates-hermes/
COPY entrypoint.sh     /opt/omcgitea/entrypoint.sh
COPY acp-bridge.py     /opt/omcgitea/acp-bridge.py
RUN chmod +x /opt/omcgitea/entrypoint.sh \
             /opt/omcgitea/acp-bridge.py

# Default CMD: hermes path treats it as `gateway` arg; claude path ignores it.
ENV HERMES_HOME=/opt/data
ENV AGENT_KIND=claude
EXPOSE 8644

ENTRYPOINT ["/opt/omcgitea/entrypoint.sh"]
CMD ["gateway"]
