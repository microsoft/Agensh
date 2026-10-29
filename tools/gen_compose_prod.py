#!/usr/bin/env python3
# Emit the team Compose base to stdout, expanding one worker/router pair per agent.
# Make writes this to docker/_gen_prod.<profile>.yml and adds the pbench overlay.

import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agent'))
from harness_config import load_config

SETTINGS = load_config()

WORKERS_PER_TEAM = int(os.environ.get("PBENCH_WORKERS_PER_TEAM") or 16)
AGENT_HARNESS = SETTINGS.harness
if AGENT_HARNESS not in ("pi", "copilot", "codex", "claude"):
    raise ValueError("AGENT_HARNESS must be pi, copilot, codex or claude")

ALL_AGENTS = [f"worker{w}" for w in range(1, WORKERS_PER_TEAM + 1)]

# Shared anchors keep model settings, limits and board access identical across workers.
HEADER = '''
name: omcgitea

x-agent: &agent-base
  init: true
  working_dir: /work
  stop_grace_period: 10m
  cgroup_parent: pbench.slice
  mem_limit: 64g
  memswap_limit: 64g
  image: "${AGENT_IMAGE:?AGENT_IMAGE required}"
  restart: unless-stopped
  extra_hosts:
    - "host.docker.internal:host-gateway"

x-agent-env: &agent-env-base
  GITEA_HOST: "http://gitea:3000"
  ANTHROPIC_BASE_URL: "${ANTHROPIC_BASE_URL:?ANTHROPIC_BASE_URL required}"
  ANTHROPIC_MODEL: "${ANTHROPIC_MODEL:-gpt-5.6-sol}"
  ANTHROPIC_API_KEY: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY required}"
  JOBS: "${JOBS:-8}"
  AGENT_HARNESS: "${AGENT_HARNESS:-copilot}"
__HARNESS_ENV__
  GITEA_ORG: "${ORG_NAME:?ORG_NAME required}"
  MATTERMOST_HOST: "http://mattermost:8065"
  ACP_CHILD_UID: "10000"
  ACP_CHILD_GID: "10000"
  PBENCH_WORKERS: "${PBENCH_WORKERS_PER_TEAM}"
  BOARD_SERVICE_URL: "http://board-service:8660"
  BOARD_IDS: "pbench-top"

x-mini-router: &mini-router-base
  cgroup_parent: pbench.slice
  mem_limit: 8g
  memswap_limit: 8g
  image: "${MINI_ROUTER_IMAGE:-omcgitea-mini-router:local}"
  restart: unless-stopped
  extra_hosts:
    - "host.docker.internal:host-gateway"

x-mini-router-env: &mini-router-env-base
  AGENT_HARNESS: "${AGENT_HARNESS:-copilot}"
  GITEA_HOST: "http://gitea:3000"
  MYSQL_DSN: "mysql://omcgitea:${MYSQL_PASSWORD}@mysql:3306/omcgitea"
  SECRET_SERVICE_URL: "http://secret-service:8650"
  SECRET_SERVICE_INTERNAL_AUTH: "${SECRET_SERVICE_INTERNAL_AUTH}"
  ACP_SOCKET_PATH: "/var/run/acp/agent.sock"
  MINI_ROUTER_PORT: "8645"
  MATTERMOST_HOST: "http://mattermost:8065"
  MINI_ROUTER_STUCK_MS: "${MINI_ROUTER_STUCK_MS:-1200000}"
  PBENCH_RUN_START_MS: "${PBENCH_RUN_START_MS:-}"
  BOARD_SERVICE_URL: "http://board-service:8660"
  BOARD_IDS: "pbench-top"
'''

# Shared services and one-shot provisioning are independent of worker activation.
INFRA = '''
services:
  gitea:
    image: docker.gitea.com/gitea:1.22.6
    restart: unless-stopped
    cgroup_parent: pbench.slice
    depends_on:
      mysql: { condition: service_healthy }
    ulimits:
      nofile: { soft: "${GITEA_NOFILE:-65536}", hard: "${GITEA_NOFILE:-65536}" }
    environment:
      USER_UID: "1000"
      USER_GID: "1000"
      GITEA__server__ROOT_URL: "http://gitea.${EDGE_DOMAIN:-localhost}:${EDGE_HTTP_PORT}/"
      GITEA__server__DOMAIN: "gitea.${EDGE_DOMAIN:-localhost}"
      GITEA__server__HTTP_PORT: "3000"
      GITEA__security__INSTALL_LOCK: "true"
      GITEA__service__DISABLE_REGISTRATION: "true"
      GITEA__service__REQUIRE_SIGNIN_VIEW: "false"
      GITEA__service__AUTO_WATCH_ON_CHANGES: "false"
      GITEA__service__AUTO_WATCH_NEW_REPOS: "false"
      GITEA__actions__ENABLED: "true"
      GITEA__actions__DEFAULT_ACTIONS_URL: "github"
      GITEA__database__DB_TYPE: "sqlite3"
      GITEA__database__MAX_OPEN_CONNS: "${GITEA_DB_MAX_OPEN:-100}"
      GITEA__database__MAX_IDLE_CONNS: "${GITEA_DB_MAX_IDLE:-20}"
      GITEA__database__CONN_MAX_LIFETIME: "${GITEA_DB_CONN_LIFETIME:-3600s}"
      GITEA__log__LEVEL: Info
      GITEA_ADMIN_USER: "${GITEA_ADMIN_USER:-chairman}"
      GITEA_ADMIN_PASSWORD: "${GITEA_ADMIN_PASSWORD:?GITEA_ADMIN_PASSWORD required}"
      GITEA_ADMIN_EMAIL: "chairman@${ORG_NAME}.local"
    volumes:
      - ${DATA_ROOT:-../.claude-team-data}/${PROFILE}/gitea:/data
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:3000/api/v1/version || exit 1"]
      interval: 5s
      timeout: 5s
      retries: 60

  nginx-edge:
    image: nginx:1.27-alpine
    restart: unless-stopped
    cgroup_parent: pbench.slice
    depends_on:
      gitea:
        condition: service_healthy
    ports:
      - "${EDGE_HTTP_PORT}:80"
      - "${EDGE_MM_PORT}:81"
    volumes:
      - ./nginx-edge/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx-edge/conf.d:/etc/nginx/conf.d:ro
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- --header='Host: gitea.localhost' http://127.0.0.1/api/v1/version >/dev/null 2>&1 || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 12

  gitea-admin-init:
    image: docker.gitea.com/gitea:1.22.6
    restart: "no"
    cgroup_parent: pbench.slice
    depends_on:
      gitea:
        condition: service_healthy
    environment:
      GITEA_ADMIN_USER: "${GITEA_ADMIN_USER:-chairman}"
      GITEA_ADMIN_PASSWORD: "${GITEA_ADMIN_PASSWORD}"
      GITEA_ADMIN_EMAIL: "chairman@${ORG_NAME}.local"
    user: "1000:1000"
    volumes:
      - ${DATA_ROOT:-../.claude-team-data}/${PROFILE}/gitea:/data
    entrypoint:
      - /bin/sh
      - -c
      - |
        set -e
        cfg=/data/gitea/conf/app.ini
        export GITEA_WORK_DIR=/data/gitea
        export GITEA_CUSTOM=/data/gitea
        if gitea --config "$$cfg" admin user list 2>/dev/null | awk 'NR>1 {print $$2}' | grep -qx "$$GITEA_ADMIN_USER"; then
          echo "[admin-init] admin user $$GITEA_ADMIN_USER already exists"; exit 0;
        fi
        echo "[admin-init] creating admin user $$GITEA_ADMIN_USER";
        gitea --config "$$cfg" admin user create \\
          --username "$$GITEA_ADMIN_USER" --password "$$GITEA_ADMIN_PASSWORD" \\
          --email "$$GITEA_ADMIN_EMAIL" --admin --must-change-password=false

  bootstrap:
    build:
      context: ./bootstrap
    image: "${BOOTSTRAP_IMAGE:-omcgitea-bootstrap:local}"
    restart: "no"
    cgroup_parent: pbench.slice
    depends_on:
      gitea: { condition: service_healthy }
      gitea-admin-init: { condition: service_completed_successfully }
      mattermost: { condition: service_healthy }
    environment:
      GITEA_HOST: "http://gitea:3000"
      GITEA_ADMIN_USER: "${GITEA_ADMIN_USER:-chairman}"
      GITEA_ADMIN_PASSWORD: "${GITEA_ADMIN_PASSWORD}"
      GITEA_ORG: "${ORG_NAME:?ORG_NAME required}"
      AGENTS: "{AGENTS_CSV}"
      REPOS: "${REPOS:-main}"
      BOOTSTRAP_DATA_DIR: "/data"
      MATTERMOST_HOST: "http://mattermost:8065"
      MATTERMOST_ADMIN_USER: "${MATTERMOST_ADMIN_USER:-mmadmin}"
      MATTERMOST_ADMIN_PASSWORD: "${MATTERMOST_ADMIN_PASSWORD:?MATTERMOST_ADMIN_PASSWORD required}"
      MATTERMOST_ADMIN_EMAIL: "mmadmin@${ORG_NAME}.local"
      MATTERMOST_TEAM_NAME: "${ORG_NAME}"
      MATTERMOST_TEAM_DISPLAY: "${ORG_NAME}"
    volumes:
      - ${DATA_ROOT:-../.claude-team-data}/${PROFILE}:/data

  secret-service:
    build:
      context: ../secret-service
    image: "${SECRET_SERVICE_IMAGE:-omcgitea-secret-service:local}"
    restart: unless-stopped
    cgroup_parent: pbench.slice
    depends_on:
      bootstrap: { condition: service_completed_successfully }
    environment:
      SECRET_SERVICE_INTERNAL_AUTH: "${SECRET_SERVICE_INTERNAL_AUTH:?SECRET_SERVICE_INTERNAL_AUTH required}"
      SECRET_SERVICE_TOKENS_DIR: /data/tokens
      SECRET_SERVICE_PORT: "8650"
    volumes:
      - ${DATA_ROOT:-../.claude-team-data}/${PROFILE}/tokens:/data/tokens:ro
    expose: ["8650"]
    healthcheck:
      test: ["CMD-SHELL", "python -c \\"import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8650/healthz', timeout=2).read()==b'ok\\\\n' else 1)\\""]
      interval: 5s
      timeout: 5s
      retries: 12

  act-runner:
    image: gitea/act_runner:0.2.11
    restart: unless-stopped
    cgroup_parent: pbench.slice
    depends_on:
      bootstrap: { condition: service_completed_successfully }
    environment:
      GITEA_INSTANCE_URL: "http://gitea:3000"
      GITEA_RUNNER_NAME: "omcgitea-${PROFILE}-runner"
      GITEA_RUNNER_LABELS: "ubuntu-latest:docker://${AGENT_IMAGE:?AGENT_IMAGE required}"
      ACT_JOB_NETWORK: "${ACT_JOB_NETWORK:-omcgitea-${PROFILE}_default}"
      ACT_CAPACITY: "${ACT_CAPACITY:-2}"
      ACT_JOB_LIMITS: "${ACT_JOB_LIMITS:---memory=8g --memory-swap=8g --cpus=4 --pids-limit=512 --cgroup-parent=pbench.slice}"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ${DATA_ROOT:-../.claude-team-data}/${PROFILE}/tokens:/run/omcgitea/tokens:ro
      - ${DATA_ROOT:-../.claude-team-data}/${PROFILE}/act-runner:/data
    working_dir: /data
    entrypoint:
      - /bin/sh
      - -c
      - |
        set -e
        cat > /data/config.yaml <<EOF
        runner:
          capacity: $$ACT_CAPACITY
          timeout: $${ACT_JOB_TIMEOUT:-5m}
        container:
          network: "$$ACT_JOB_NETWORK"
          options: "$$ACT_JOB_LIMITS"
          valid_volumes: []
        EOF
        if [ ! -f /data/.runner ]; then
          tok=$$(cat /run/omcgitea/tokens/runner.token)
          /usr/local/bin/act_runner register --no-interactive \\
            --instance "$$GITEA_INSTANCE_URL" --token "$$tok" \\
            --name "$$GITEA_RUNNER_NAME" --labels "$$GITEA_RUNNER_LABELS"
        fi
        exec /usr/local/bin/act_runner daemon --config /data/config.yaml

  mysql:
    image: mysql:8.4
    restart: unless-stopped
    cgroup_parent: pbench.slice
    command: ["--innodb-use-native-aio=0", "--max-connections=${MYSQL_MAX_CONNECTIONS:-1000}", "--innodb-buffer-pool-size=${MYSQL_INNODB_BUFFER_POOL_SIZE:-134217728}"]
    environment:
      MYSQL_ROOT_PASSWORD: "${MYSQL_ROOT_PASSWORD:?MYSQL_ROOT_PASSWORD required}"
      MYSQL_DATABASE: omcgitea
      MYSQL_USER: omcgitea
      MYSQL_PASSWORD: "${MYSQL_PASSWORD:?MYSQL_PASSWORD required}"
    volumes:
      - ${DATA_ROOT:-../.claude-team-data}/${PROFILE}/mysql:/var/lib/mysql
      - ../mini-router/sql:/docker-entrypoint-initdb.d:ro
    expose: ["3306"]
    healthcheck:
      test: ["CMD-SHELL", "mysqladmin ping -uroot -p$$MYSQL_ROOT_PASSWORD"]
      interval: 5s
      timeout: 3s
      retries: 30

  mattermost:
    image: mattermost/mattermost-team-edition:10.6
    restart: unless-stopped
    cgroup_parent: pbench.slice
    ulimits:
      nofile: { soft: "${MM_NOFILE:-65536}", hard: "${MM_NOFILE:-65536}" }
    environment:
      MM_SQLSETTINGS_DRIVERNAME: mysql
      MM_SQLSETTINGS_DATASOURCE: "omcgitea:${MYSQL_PASSWORD}@tcp(mysql:3306)/mattermost?charset=utf8mb4,utf8&readTimeout=30s&writeTimeout=30s"
      MM_SERVICESETTINGS_SITEURL: "${MATTERMOST_SITE_URL:-http://mattermost:8065}"
      MM_SERVICESETTINGS_ENABLELOCALMODE: "true"
      MM_SERVICESETTINGS_ENABLEUSERACCESSTOKENS: "true"
      MM_TEAMSETTINGS_ENABLEOPENSERVER: "true"
      MM_TEAMSETTINGS_MAXUSERSPERTEAM: "${MM_MAX_USERS_PER_TEAM:-200}"
      MM_SQLSETTINGS_MAXOPENCONNS: "${MM_SQL_MAX_OPEN_CONNS:-300}"
      MM_SQLSETTINGS_MAXIDLECONNS: "${MM_SQL_MAX_IDLE_CONNS:-20}"
    depends_on:
      mysql: { condition: service_healthy }
    volumes:
      - ${DATA_ROOT:-../.claude-team-data}/${PROFILE}/mattermost/data:/mattermost/data
      - ${DATA_ROOT:-../.claude-team-data}/${PROFILE}/mattermost/logs:/mattermost/logs
      - ${DATA_ROOT:-../.claude-team-data}/${PROFILE}/mattermost/config:/mattermost/config
      - ${DATA_ROOT:-../.claude-team-data}/${PROFILE}/mattermost/plugins:/mattermost/plugins
    expose: ["8065"]
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8065/api/v4/system/ping || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 30

  board-service:
    image: "${BOARD_IMAGE:-omcgitea-board:local}"
    restart: unless-stopped
    cgroup_parent: pbench.slice
    depends_on:
      mysql: { condition: service_healthy }
    environment:
      MYSQL_DSN: "mysql://omcgitea:${MYSQL_PASSWORD}@mysql:3306/omcgitea"
      BOARD_LISTEN_PORT: "8660"
      BOARD_LIFECYCLE_DIR: "/data/lifecycle"
      BOARD_MEMBERS_JSON: >-
        {"pbench-top":[
{BOARD_MEMBERS}
        ]}
    volumes:
      - ${DATA_ROOT:-../.claude-team-data}/${PROFILE}/board-lifecycle:/data/lifecycle
    healthcheck:
      test: ["CMD-SHELL", "python3 -c \\"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8660/healthz', timeout=2)\\""]
      interval: 10s
      timeout: 5s
      retries: 12
'''

# Each worker owns a persistent HOME and socket directory; runtime inputs are mounted.
AGENT_BLOCK = '''
  agent-__SHORT__:
    <<: *agent-base
    depends_on:
      bootstrap:
        condition: service_completed_successfully
    environment:
      <<: *agent-env-base
      AGENT_NAME: "${ORG_NAME}-__SHORT__"
      GITEA_TOKEN_FILE: "/run/omcgitea/tokens/agent-${ORG_NAME}-__SHORT__.token"
    volumes:
      - ${DATA_ROOT:-../.claude-team-data}/${PROFILE}/agents/${ORG_NAME}-__SHORT__:/opt/data
      - ${DATA_ROOT:-../.claude-team-data}/${PROFILE}/acp/${ORG_NAME}-__SHORT__:/var/run/acp
      - ${DATA_ROOT:-../.claude-team-data}/${PROFILE}/tokens/agent-${ORG_NAME}-__SHORT__.token:/run/omcgitea/tokens/agent-${ORG_NAME}-__SHORT__.token:ro
      - ${DATA_ROOT:-../.claude-team-data}/${PROFILE}/tokens/agent-${ORG_NAME}-__SHORT__-mm.token:/run/omcgitea/tokens/agent-${ORG_NAME}-__SHORT__-mm.token:ro
      - ${PBENCH_BIN:-/dev/null}:/opt/pbench/executable:ro
      - ../prompts/agents.txt:/opt/omcgitea/prompts/agents.md:ro
      - ../prompts/pbench_brief.txt:/opt/omcgitea/prompts/pbench_brief.md:ro
      - ../agent/config/mcp_deny_tools.json:/opt/omcgitea/config/mcp_deny_tools.json:ro
      - ../agent/config/mcp_allowed_tools.json:/opt/omcgitea/config/mcp_allowed_tools.json:ro
      - ../agent/config/mcp_tool_metadata.json:/opt/omcgitea/config/mcp_tool_metadata.json:ro
      - ../agent/config/mcp.json.tmpl:/opt/omcgitea/config/mcp.json.tmpl:ro
      - ../board-service/mcp.cjs:/opt/mcp-board.cjs:ro
      - ../mini-router/mcp_notice_shim.cjs:/opt/mcp_notice_shim.cjs:ro
      - ../agent/acp_bridge.py:/opt/omcgitea/acp_bridge.py:ro
      - ../agent/archive.py:/opt/omcgitea/archive.py:ro
      - ../agent/harness_config.py:/opt/omcgitea/harness_config.py:ro
__HARNESS_MOUNTS__
'''

# Mount the worker's socket/backlog plus its read-only Gitea password, not all HOME.
ROUTER_BLOCK = '''
  mini-router-__SHORT__:
    <<: *mini-router-base
    depends_on:
      mysql:
        condition: service_healthy
      secret-service:
        condition: service_healthy
      agent-__SHORT__:
        condition: service_started
    environment:
      <<: *mini-router-env-base
      AGENT_NAME: "${ORG_NAME}-__SHORT__"
      GITEA_PASSWORD_FILE: "/run/omcgitea/tokens/agent-${ORG_NAME}-__SHORT__.password"
    volumes:
      - ${DATA_ROOT:-../.claude-team-data}/${PROFILE}/acp/${ORG_NAME}-__SHORT__:/var/run/acp:ro
      - ${DATA_ROOT:-../.claude-team-data}/${PROFILE}/agents/${ORG_NAME}-__SHORT__/home/group-messages:/opt/data/home/group-messages
      - ${DATA_ROOT:-../.claude-team-data}/${PROFILE}/tokens/agent-${ORG_NAME}-__SHORT__.password:/run/omcgitea/tokens/agent-${ORG_NAME}-__SHORT__.password:ro
    expose: ["8645"]
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1:8645/healthz >/dev/null 2>&1 || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 6
'''

def build():
    # Bootstrap identities, board membership and service names use the same worker list.
    agents_csv = ",".join(f"${{ORG_NAME}}-{s}" for s in ALL_AGENTS)
    out = []
    prefix = AGENT_HARNESS.upper()
    wire_api = 'messages' if AGENT_HARNESS == 'claude' else 'responses'
    harness_env = f'  {prefix}_PROVIDER_WIRE_API: "${{{prefix}_PROVIDER_WIRE_API:-{wire_api}}}"'
    for name, default in SETTINGS.environment().items():
        if name != 'AGENT_HARNESS':
            harness_env += f'\n  {name}: "${{{name}-{default}}}"'
    if AGENT_HARNESS == 'copilot':
        harness_env += '\n  COPILOT_PROVIDER_TYPE: "${COPILOT_PROVIDER_TYPE:-openai}"'
    out.append(HEADER.replace('__HARNESS_ENV__', harness_env)
               .replace('${AGENT_HARNESS:-copilot}', '${AGENT_HARNESS:-' + AGENT_HARNESS + '}'))
    members = ",\n".join(f'          "${{ORG_NAME}}-{s}"' for s in ALL_AGENTS)
    out.append(INFRA.replace("{AGENTS_CSV}", agents_csv)
               .replace("{BOARD_MEMBERS}", members))
    for short in ALL_AGENTS:
        harness_files = ('config.sh',) if AGENT_HARNESS == 'copilot' else ('acp.py', 'config.py')
        harness_mounts = '\n'.join(
            f"      - ../agent/{AGENT_HARNESS}/{name}:/opt/omcgitea/{AGENT_HARNESS}/{name}:ro"
            for name in harness_files)
        out.append(AGENT_BLOCK.replace("__SHORT__", short).replace("__HARNESS_MOUNTS__", harness_mounts))
    for short in ALL_AGENTS:
        out.append(ROUTER_BLOCK.replace("__SHORT__", short))
    return "".join(out)

if __name__ == "__main__":
    print(build())
