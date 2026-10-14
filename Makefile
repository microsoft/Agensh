# omcgitea — ProgramBench fleet Makefile
#
# Every compose target runs the pbench stack for PROFILE=pbench-* with sudo
# (the dev box has docker.sock owned by root:docker; the user is not in the
# docker group). Override SUDO= to skip sudo.

SHELL := /bin/bash

# Profile selector. Each pbench-* profile has its own .env.<profile>, data
# dir (${DATA_ROOT}/<profile>, default .claude-team-data/<profile>), compose
# project name (omcgitea-<profile>) and host ports. There is no default: the
# only stack this repo runs is the pbench one, and a mistyped or missing
# PROFILE must not silently act on some other compose project.
PROFILE ?=
ifneq (,$(PROFILE))
ifneq (1,$(words $(PROFILE)))
$(error PROFILE="$(PROFILE)" must be a single word)
endif
ifeq (,$(filter pbench-%,$(PROFILE)))
$(error PROFILE=$(PROFILE) is not a pbench-* profile; use PROFILE=pbench-<mode>-<task>)
endif
endif
ENV_FILE := .env.$(PROFILE)
PROJECT  := omcgitea-$(PROFILE)

# The compose template uses ${DATA_ROOT}/${PROFILE}; read DATA_ROOT from the env
# file so prep-mm-dirs / clean chown the right directory.
# compose keeps the last DATA_ROOT line, so this does too. `clean` hands
# DATA_DIR to rm -rf, so a value that splits into two words is refused.
ENV_DATA_ROOT := $(shell grep -E '^DATA_ROOT=' $(ENV_FILE) 2>/dev/null | tail -n1 | cut -d= -f2-)
DATA_DIR := $(if $(ENV_DATA_ROOT),$(ENV_DATA_ROOT),.claude-team-data)/$(PROFILE)
ifneq (1,$(words $(DATA_DIR)))
$(error DATA_DIR "$(DATA_DIR)" must be a single path; check DATA_ROOT in $(ENV_FILE))
endif

# host.docker.internal:host-gateway needs Docker 20.10+; we already have 29.x.
# We deliberately strip the user's shell ANTHROPIC_* / GITEA_* / AGENT_KIND
# vars before invoking compose so .env.<profile> is the single source of
# truth — the user's ~/.bashrc may set ANTHROPIC_BASE_URL=http://localhost:4141
# (works only on the host, not inside containers) and we must not let it leak in.
# The -E is load-bearing: PBENCH_RUN_START_MS is exported by
# scripts/pbench_run.sh, not written into any .env file, so plain `sudo` would
# strip it and each mini-router would fall back to its own process start as the
# run-clock origin, and event ages would disagree with each other and with the
# board. If you change SUDO, keep -E or move the anchor into the env-file.
SUDO ?= sudo -E

# The base is rendered per profile by tools/gen-compose-prod.py into
# docker/_gen-prod.<profile>.yml (infra + PBENCH_WORKERS_PER_TEAM peer coders),
# then layered with docker-compose.pbench.yml -- the egress-lock overlay
# (internal:true default net + egress-proxy). Every per-worker setting (resource
# guard, prompt mounts, board env, board-service) is emitted by the generator, so
# there is no per-N overlay to keep in step with the worker count.
COMPOSE_BASE := docker/_gen-prod.$(PROFILE).yml
COMPOSE_OVERLAY := -f docker/docker-compose.pbench.yml

COMPOSE ?= env -u ANTHROPIC_BASE_URL -u ANTHROPIC_MODEL -u ANTHROPIC_API_KEY \
            -u AGENT_KIND -u COPILOT_PROVIDER_TYPE \
            -u GITEA_HOST -u GITEA_TOKEN \
            $(SUDO) docker compose -f $(COMPOSE_BASE) $(COMPOSE_OVERLAY) \
            --project-name $(PROJECT) --env-file $(ENV_FILE) \
            --profile $(PROFILE)


.PHONY: help up down logs ps build pull rebuild clean wipe pbench-single-agent \
        bootstrap-rerun reset-tokens check-env require-profile prep-mm-dirs render-pbench-base compose-services

help:
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

require-profile:
	@test -n "$(PROFILE)" || (echo "ERROR: PROFILE is required, e.g. make up PROFILE=pbench-single-node-pandoc" >&2 && exit 1)

check-env: require-profile ## Verify .env.<profile> has the required keys
	@test -f $(ENV_FILE) || (echo "ERROR: $(ENV_FILE) missing — generate it with scripts/pbench_gen_env.sh" && exit 1)
	@grep -q '^GITEA_ADMIN_PASSWORD=.\+' $(ENV_FILE) || (echo "ERROR: GITEA_ADMIN_PASSWORD not set in $(ENV_FILE)" && exit 1)


# Render the per-profile pbench base compose from tools/gen-compose-prod.py,
# passing PBENCH_WORKERS_PER_TEAM (+ optional mounts) from .env.<profile>.
# Every target that runs $(COMPOSE) depends on it, so COMPOSE_BASE always exists.
render-pbench-base: require-profile
	@PBENCH_WORKERS_PER_TEAM="$$(grep -E '^PBENCH_WORKERS_PER_TEAM=' $(ENV_FILE) 2>/dev/null | cut -d= -f2)" \
	python3 tools/gen-compose-prod.py > docker/_gen-prod.$(PROFILE).yml \
	&& echo "[render-pbench-base] wrote docker/_gen-prod.$(PROFILE).yml" >&2

up: check-env prep-mm-dirs render-pbench-base ## Start the pbench stack for PROFILE (build if needed)
	$(COMPOSE) up -d --build $(UP_FLAGS) $(SERVICES)

# SERVICES limits `up` to a subset; empty means the whole stack.
# pbench_run.sh brings infra up first and then starts the agent containers on a
# stagger: started all at once, many copilot CLIs unpacking their package
# together never finish, and an agent that does not exist yet cannot be woken
# early by a peer's channel post.
SERVICES ?=

# UP_FLAGS passes extra flags to `compose up`. The staggered per-agent bringup
# uses --no-deps: `compose up <agent>` otherwise starts and may recreate that
# service's depends_on chain, restarting gitea/mysql/mattermost and re-running
# bootstrap on every agent start, which loses the agents' Mattermost accounts.
UP_FLAGS ?=

compose-services: render-pbench-base ## Print every service name for PROFILE (used to split infra from agents)
	@$(COMPOSE) config --services

# Mattermost runs as uid 2000; on a fresh profile its bind-mount dirs
# don't exist yet and would be auto-created by docker as root, which
# then makes the container fail with "permission denied" on
# /mattermost/config/config.json. Pre-create + chown so first `make up`
# works without manual intervention.
prep-mm-dirs: require-profile
	@$(SUDO) mkdir -p $(DATA_DIR)/mattermost/data $(DATA_DIR)/mattermost/logs $(DATA_DIR)/mattermost/config $(DATA_DIR)/mattermost/plugins
	@$(SUDO) chown -R 2000:2000 $(DATA_DIR)/mattermost

down: render-pbench-base ## Stop containers (keep data)
	$(COMPOSE) down

logs: render-pbench-base ## Tail logs
	$(COMPOSE) logs -f --tail=200

ps: render-pbench-base ## List service status
	$(COMPOSE) ps

build: render-pbench-base ## (Re)build images
	$(COMPOSE) build

pull: render-pbench-base ## Pull base images
	$(COMPOSE) pull

rebuild: down build up ## Force rebuild + restart

clean: down ## Stop containers and wipe THIS profile's data dir (DESTRUCTIVE)
	@test -n "$(PROFILE)"
	$(SUDO) rm -rf $(DATA_DIR)
	@echo "Cleaned $(DATA_DIR)/"

wipe: clean ## Alias for clean

bootstrap-rerun: render-pbench-base ## Re-run bootstrap (idempotent)
	$(SUDO) rm -f $(DATA_DIR)/tokens/.bootstrap-done
	$(COMPOSE) up bootstrap

reset-tokens: require-profile ## Wipe tokens but keep gitea data (forces token rotation)
	$(SUDO) rm -rf $(DATA_DIR)/tokens

# ---------------------------------------------------------------------------
# ProgramBench single-agent baseline: one Copilot CLI agent (BYOK, native ACP)
# in a standalone container (no forge/chat), with the team runs' anti-cheat
# (no internet for agents, binary 0111, non-root agent). The team runs are
# launched by scripts/launch_single_node.sh / launch_multi_node.sh.
# See scripts/launch_single_agent.sh.
# ---------------------------------------------------------------------------
pbench-single-agent: ## Run a ProgramBench task with a single Copilot ACP agent: make pbench-single-agent TASK=<id> HOURS=<h> [OUT_DIR=...]
	TASK="$(TASK)" HOURS="$(HOURS)" OUT_DIR="$(OUT_DIR)" ./scripts/launch_single_agent.sh
