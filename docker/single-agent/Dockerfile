# The single-agent ProgramBench baseline image, Copilot CLI variant.
#
# Layers Node.js + @github/copilot on the task's cleanroom base, with a
# uid-10000 HOME. scripts/launch_single_agent.sh then drives the ACP entrypoint at
# /opt/copilot-cli/node_modules/.bin/copilot via
#   docker exec -i <cc> /opt/copilot-cli/node_modules/.bin/copilot \
#       --acp --stdio --no-auto-login --no-auto-update --no-remote \
#       --disable-builtin-mcps --no-ask-user
# speaking JSON-RPC 2.0 over stdio (same protocol as claude-agent-acp).
#
# Built per-task on the HOST (which has network) BEFORE the net-lock stack
# comes up; the running agent has ZERO public egress.
ARG CLEANROOM_IMG
FROM ${CLEANROOM_IMG}

USER root

# --- Node.js ---------------------------------------------------------------
ARG NODE_VERSION=22.14.0
RUN set -eux; \
    if command -v apt-get >/dev/null 2>&1; then \
        apt-get update && apt-get install -y --no-install-recommends curl xz-utils ca-certificates git && rm -rf /var/lib/apt/lists/*; \
    elif command -v apk >/dev/null 2>&1; then \
        apk add --no-cache curl xz ca-certificates git libstdc++; \
    elif command -v dnf >/dev/null 2>&1; then \
        dnf install -y curl xz ca-certificates git; \
    elif command -v yum >/dev/null 2>&1; then \
        yum install -y curl xz ca-certificates git; \
    fi; \
    command -v git >/dev/null 2>&1 || { echo "git missing and no known pkg manager to install it" >&2; exit 1; }; \
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

# --- @github/copilot CLI (BYOK / native ACP) --------------------------------
# The same pinned version as docker/agent/Dockerfile, so the single-agent
# baseline uses the identical binary bundle as the multi-agent copilot stack.
ARG COPILOT_CLI_VERSION=1.0.70
ENV COPILOT_CLI_VERSION=${COPILOT_CLI_VERSION} \
    COPILOT_AUTO_UPDATE=false
RUN set -eux; \
    mkdir -p /opt/copilot-cli; \
    cd /opt/copilot-cli; \
    npm init -y >/dev/null; \
    npm install --omit=dev --no-audit --no-fund --save-exact \
        @github/copilot@${COPILOT_CLI_VERSION}; \
    test -x /opt/copilot-cli/node_modules/.bin/copilot; \
    mkdir -p /tmp/copilot-version-check; \
    copilot_version="$(HOME=/tmp/copilot-version-check \
        COPILOT_HOME=/tmp/copilot-version-check/.copilot \
        /opt/copilot-cli/node_modules/.bin/copilot --no-auto-update --version \
        | sed -n '1p')"; \
    test "${copilot_version}" = "GitHub Copilot CLI ${COPILOT_CLI_VERSION}."; \
    rm -rf /tmp/copilot-version-check

# --- non-root HOME for the ACP child ---------------------------------------
# copilot writes to $HOME/.copilot at runtime; needs a writable HOME.
# uid 10000 matches the 0111 root:root binary anti-cheat.
RUN mkdir -p /home/ccagent && chown 10000:10000 /home/ccagent
ENV HOME=/home/ccagent

# Idle; scripts/acp_driver.py drives ACP via
#   docker exec -i ... /opt/copilot-cli/node_modules/.bin/copilot --acp --stdio ...
ENTRYPOINT []
CMD ["sleep", "infinity"]
