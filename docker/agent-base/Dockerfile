# The agent base image, omcgitea-agent-base:pbench. Nothing runs it directly:
# docker/agent/Dockerfile takes gitea-mcp and /opt/claude-agent-acp from it,
# and docker/sim-agent/Dockerfile builds on it.
#
# Ubuntu 22.04 with the ProgramBench eval sandbox's toolchains (gcc 11.4.0,
# rustc 1.92.0, go 1.21.0, ghc 8.8.4, JDK 11, Python 3.10), plus the agent
# runtime: node, the Gitea MCP server (gitea-mcp), mcp-server-mattermost,
# @agentclientprotocol/claude-agent-acp, the official @github/copilot CLI and
# playwright chromium. Gitea/claude-agent-acp/Copilot CLI source code is NOT
# modified; we only RUN package managers to add them.
#
# The tagged image is frozen: docker.gitea.com is unreachable from this host, so
# it cannot be rebuilt here. Where docker.gitea.com is reachable:
#   sudo docker build -t omcgitea-agent-base:pbench docker/agent-base

ARG GITEA_MCP_SERVER_IMAGE=docker.gitea.com/gitea-mcp-server:latest

# Stage A: the Gitea MCP binary, from the upstream image.
FROM ${GITEA_MCP_SERVER_IMAGE} AS mcp_src

FROM ubuntu:22.04

USER root
ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC

# 1. Base toolchain at the eval sandbox's versions from Ubuntu 22.04 apt:
#    gcc 11.4.0, g++, make 4.3, python 3.10.12, cmake 3.22.1, openjdk-11-jdk
#    (JDK, not JRE: the team needs javac; eval has the JRE only), ghc 8.8.4 +
#    cabal-install, the per-task build deps and the agent-runtime deps. maven is
#    pulled with --no-install-recommends alongside openjdk-11 so apt does NOT
#    satisfy maven's default-jdk dep with openjdk-17, which would flip
#    `javac`/`java` to 17 and break the parity check at the end.
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential make cmake \
      python3 python3-pip python3-venv \
      openjdk-11-jdk-headless maven \
      ghc cabal-install \
      git curl ca-certificates jq tini gettext-base socat xz-utils \
      autoconf automake libtool libtool-bin pkg-config m4 \
      bison flex wget \
      nasm yasm re2c texinfo gettext \
      libbz2-dev liblzma-dev zlib1g-dev \
      libssl-dev libcurl4-openssl-dev \
      libxml2-dev libxslt1-dev libjansson-dev libjson-c-dev libyaml-dev \
      libsqlite3-dev libpcre2-dev libpcre3-dev \
      libjpeg-dev libpng-dev libwebp-dev libfreetype6-dev libtiff-dev \
      libx264-dev libx265-dev libvpx-dev libmp3lame-dev \
      libopus-dev libvorbis-dev libtheora-dev libass-dev \
      libonig-dev libreadline-dev libedit-dev libargon2-dev \
      libsodium-dev libtidy-dev libicu-dev libzip-dev \
      libproj-dev libgeos-dev libgeotiff-dev \
      libfftw3-dev libarchive-dev libncurses-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. Rust 1.92.0 (pinned, matches eval) via rustup, system-wide so all
#    agent UIDs (including ACP_CHILD_UID=10000) can read/exec it.
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:/usr/local/go/bin:/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
      | sh -s -- -y --default-toolchain 1.92.0 --profile minimal --no-modify-path \
    && chmod -R a+rX,a+w /usr/local/rustup /usr/local/cargo

# 3. Go 1.21.0 (pinned, matches eval) via official tarball.
RUN GO_VERSION=1.21.0 \
    && curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" -o /tmp/go.tgz \
    && tar -C /usr/local -xzf /tmp/go.tgz \
    && rm /tmp/go.tgz \
    && chmod -R a+rX /usr/local/go

# 4. Node.js via official static tarball. Ubuntu 22.04 apt ships node 12
#    (too old for claude-agent-acp which needs >=18). Node is agent-runtime
#    only — never touched by eval — so no parity constraint here.
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

# 5. The Gitea MCP server binary; the upstream image ships it at /app/gitea-mcp.
COPY --from=mcp_src /app/gitea-mcp /usr/local/bin/gitea-mcp
RUN chmod +x /usr/local/bin/gitea-mcp && /usr/local/bin/gitea-mcp --version || true

# 6. uv + mcp-server-mattermost. Ubuntu 22.04 has no `uv` in apt, so install
#    it first (astral standalone installer), then use `uv tool install`.
#    The installed wrapper's shebang points at the venv python under /root. The
#    ACP child runs as uid 10000 but gid 0, so spawning the MCP server must
#    traverse /root under its GROUP bits; 0711 grants traverse only.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && /root/.local/bin/uv tool install --no-cache mcp-server-mattermost \
    && /root/.local/bin/mcp-server-mattermost --help >/dev/null 2>&1 \
    && cp /root/.local/bin/mcp-server-mattermost /usr/local/bin/mcp-server-mattermost \
    && chmod 0711 /root

# 7. @agentclientprotocol/claude-agent-acp, for AGENT_KIND=claude. The dist is
#    hoisted to /opt/claude-agent-acp/dist and must answer an ACP initialize.
ENV CLAUDE_AGENT_ACP_VERSION=0.33.1
RUN mkdir -p /opt/claude-agent-acp \
    && cd /opt/claude-agent-acp \
    && npm init -y >/dev/null \
    && npm install --omit=dev --no-audit --no-fund \
        @agentclientprotocol/claude-agent-acp@${CLAUDE_AGENT_ACP_VERSION} \
    && cp -r node_modules/@agentclientprotocol/claude-agent-acp/dist . \
    && (echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1,"clientCapabilities":{}}}'; sleep 1) \
        | timeout 5 node dist/index.js 2>/dev/null | grep -q '"protocolVersion":1'

# 8. The official Copilot CLI at an exact, contract-tested version.
#    COPILOT_AUTO_UPDATE is set before the first CLI invocation, and runtime
#    also supplies --no-auto-update.
ARG COPILOT_CLI_VERSION=1.0.70
ENV COPILOT_CLI_VERSION=${COPILOT_CLI_VERSION} \
    COPILOT_AUTO_UPDATE=false
RUN mkdir -p /opt/copilot-cli \
    && cd /opt/copilot-cli \
    && npm init -y >/dev/null \
    && npm install --omit=dev --no-audit --no-fund --save-exact \
        @github/copilot@${COPILOT_CLI_VERSION} \
    && test -x /opt/copilot-cli/node_modules/.bin/copilot \
    && mkdir -p /tmp/copilot-version-check \
    && copilot_version="$(HOME=/tmp/copilot-version-check \
        COPILOT_HOME=/tmp/copilot-version-check/.copilot \
        /opt/copilot-cli/node_modules/.bin/copilot --no-auto-update --version \
        | sed -n '1p')" \
    && test "${copilot_version}" = "GitHub Copilot CLI ${COPILOT_CLI_VERSION}." \
    && rm -rf /tmp/copilot-version-check

# 9. Playwright chromium + system libs. Avoids the per-container 170 MB
#    chromium download on first use.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
      libcups2 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
      libgbm1 libxkbcommon0 libpango-1.0-0 libcairo2 libasound2 \
      libatspi2.0-0 fonts-liberation libdrm2 \
    && rm -rf /var/lib/apt/lists/* \
    && npx -y playwright install chromium 2>&1 | tail -5

# 10. Hard-fail the build if any toolchain drifted from the eval sandbox's
#     versions: if an apt security update bumps a pinned version, the build
#     breaks rather than silently drifting.
RUN set -e; \
    gcc_v=$(gcc -dumpfullversion); \
    [ "$gcc_v" = "11.4.0" ] || { echo "gcc drift: got $gcc_v"; exit 1; }; \
    rust_v=$(rustc --version | awk '{print $2}'); \
    [ "$rust_v" = "1.92.0" ] || { echo "rustc drift: got $rust_v"; exit 1; }; \
    go_v=$(go version | awk '{print $3}'); \
    [ "$go_v" = "go1.21.0" ] || { echo "go drift: got $go_v"; exit 1; }; \
    ghc_v=$(ghc --numeric-version); \
    [ "$ghc_v" = "8.8.4" ] || { echo "ghc drift: got $ghc_v"; exit 1; }; \
    jdk_major=$(javac -version 2>&1 | awk '{print $2}' | cut -d. -f1); \
    [ "$jdk_major" = "11" ] || { echo "jdk drift: got $jdk_major"; exit 1; }; \
    python3 --version | grep -qE '^Python 3\.10\.' || { python3 --version; exit 1; }; \
    echo "toolchain parity OK: gcc=$gcc_v rustc=$rust_v go=$go_v ghc=$ghc_v jdk=$jdk_major"
