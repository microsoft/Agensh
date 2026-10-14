# omcgitea-sim-agent — the AGENT_KIND=sim runtime.
#
# FROM the agent base image, which already carries everything the sim needs to
# be real: the gitea-mcp binary, mcp-server-mattermost and node. The sim adds
# one Node program plus the same entrypoint, bridge, prompts and config the
# agent image bakes.
#
# Deliberately NOT built from a ProgramBench cleanroom. The per-task images are
# ~3.9 GB each and exist so the agents' compiler and crate versions match the
# grader's — which matters only when code is being compiled for a score. A sim
# submission scores ~0 by construction, so paying for the cleanroom would buy
# nothing and make a "quick pipeline check" a multi-gigabyte build.
#
# Build from the REPO ROOT (context = .), like docker/agent/Dockerfile:
#   sudo docker build -t omcgitea-sim-agent:local -f docker/sim-agent/Dockerfile .
#
# mcp-board/ and mcp-notice-shim/ are NOT baked: the board overlays bind-mount
# them at /opt/mcp-board and /opt/mcp-notice-shim, and taking the mount means the
# sim runs whatever the working tree has, same as a real agent on those profiles.
ARG BASE_IMAGE=omcgitea-agent-base:pbench
FROM ${BASE_IMAGE}

# The sim agent itself. No npm install: it is dependency-free on purpose, so the
# image build cannot break on a registry the sealed host cannot reach.
COPY sim-agent/ /opt/sim-agent/

# The entrypoint (with its `sim)` branch), bridge, prompts and config, current
# at build time. A stale baked entrypoint is invisible at runtime until it isn't.
COPY docker/agent/entrypoint.sh /opt/omcgitea/entrypoint.sh
COPY docker/agent/acp-bridge.py /opt/omcgitea/acp-bridge.py
COPY docker/agent/config/       /opt/omcgitea/config/
COPY prompts/team/agents.md       /opt/omcgitea/prompts/agents.md
COPY prompts/team/pbench-brief.md /opt/omcgitea/prompts/pbench-brief.md

RUN chmod +x /opt/omcgitea/entrypoint.sh /opt/omcgitea/acp-bridge.py

# entrypoint.sh exports AGENT_NODE="${AGENT_NODE:-/usr/local/bin/node}" and
# mcp.json.tmpl renders that as the command for all three MCP servers. Base
# images disagree on where node lives (/usr/local/bin/node or /usr/bin/node),
# and when the path is wrong every server dies with `spawn ... ENOENT`. That
# failure is silent: the agent boots, prints "(NO LLM)", answers ACP, and
# reports failed tool calls.
# Normalise it here rather than in the shared entrypoint, which the other kinds
# also read.
RUN [ -x /usr/local/bin/node ] || ln -sf "$(command -v node)" /usr/local/bin/node \
    && /usr/local/bin/node --version

# Fail the BUILD, not the run, if the sim cannot even be parsed.
RUN node --check /opt/sim-agent/src/main.js \
    && node --check /opt/sim-agent/src/acp.js \
    && node --check /opt/sim-agent/src/mcp.js \
    && node --check /opt/sim-agent/src/policy.js \
    && node --check /opt/sim-agent/src/state.js

ENV AGENT_KIND=sim
ENTRYPOINT ["/opt/omcgitea/entrypoint.sh"]
