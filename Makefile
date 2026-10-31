# Profile-scoped lifecycle commands for the generated single-node team stack.
# Runtime settings come from .env.<profile>; generated Compose files are disposable.
SHELL := /bin/bash

PROFILE ?=
# Restrict every lifecycle command to one explicitly named single-node profile.
ifneq (,$(PROFILE))
ifneq (1,$(words $(PROFILE)))
$(error PROFILE="$(PROFILE)" must be a single word)
endif
ifeq (,$(shell printf '%s' '$(PROFILE)' | grep -xE '[a-z0-9][a-z0-9-]*'))
$(error PROFILE=$(PROFILE) must be lowercase letters, digits and hyphens, e.g. programbench-pandoc)
endif
endif
ENV_FILE := .env.$(PROFILE)
PROJECT  := omcgitea-$(PROFILE)

ENV_DATA_ROOT := $(shell grep -E '^DATA_ROOT=' $(ENV_FILE) 2>/dev/null | tail -n1 | cut -d= -f2-)
DATA_DIR := $(if $(ENV_DATA_ROOT),$(ENV_DATA_ROOT),.claude-team-data)/$(PROFILE)
ifneq (1,$(words $(DATA_DIR)))
$(error DATA_DIR "$(DATA_DIR)" must be a single path; check DATA_ROOT in $(ENV_FILE))
endif

SUDO ?= sudo -E

COMPOSE_BASE := docker/_gen_prod.$(PROFILE).yml
# The profile names its task pack (default programbench); the pack's network mode
# selects the overlay: `offline` keeps workers on the internal network only.
profile_value = $(shell grep -E '^$(1)=' $(ENV_FILE) 2>/dev/null | tail -n1 | cut -d= -f2-)
PACK := $(or $(call profile_value,AGENSH_PACK),programbench)
# A project may override the pack's network mode with AGENSH_NETWORK in its profile;
# a run's prepare hook resolves `auto` and exports AGENSH_RUN_NETWORK.
NETWORK_MODE := $(or $(AGENSH_RUN_NETWORK),$(call profile_value,AGENSH_NETWORK),$(shell python3 -c 'import sys; from agensh.pack import load_pack; print(load_pack(sys.argv[1]).network)' $(PACK) 2>/dev/null))
NETWORK_OVERLAY := $(if $(filter open,$(NETWORK_MODE)),-f docker/network_open.yml)$(if $(filter allowlist,$(NETWORK_MODE)),-f docker/network_allowlist.yml)
# COMPOSE_EXTRA_FILES (space-separated, absolute paths) layers further overrides,
# such as the smoke test's stub harness mounts.
COMPOSE_OVERLAY := -f docker/docker_compose.team.yml $(NETWORK_OVERLAY) $(foreach f,$(COMPOSE_EXTRA_FILES),-f $(f))

# Unset these legacy model/identity keys; the launcher scrubs other profile conflicts.
COMPOSE ?= env -u ANTHROPIC_BASE_URL -u ANTHROPIC_MODEL -u ANTHROPIC_API_KEY \
            -u AGENT_HARNESS -u COPILOT_PROVIDER_TYPE \
            -u GITEA_HOST -u GITEA_TOKEN \
            $(SUDO) docker compose -f $(COMPOSE_BASE) $(COMPOSE_OVERLAY) \
            --project-name $(PROJECT) --env-file $(ENV_FILE) \
            --profile $(PROFILE)

.PHONY: help up down logs ps build pull rebuild clean wipe \
        bootstrap-rerun reset-tokens check-env require-profile prep-mm-dirs render-base compose-services

help:
	@printf '%s\t%s\n' \
	    check-env 'Verify .env.<profile> has the required keys' \
	    up 'Start the team stack for PROFILE (build if needed)' \
	    compose-services 'Print every service name for PROFILE (used to split infra from agents)' \
	    down 'Stop containers (keep data)' \
	    logs 'Tail logs' \
	    ps 'List service status' \
	    build '(Re)build images' \
	    pull 'Pull base images' \
	    rebuild 'Force rebuild + restart' \
	    clean 'Stop containers and wipe THIS profile'"'"'s data dir (DESTRUCTIVE)' \
	    wipe 'Alias for clean' \
	    bootstrap-rerun 'Re-run bootstrap (idempotent)' \
	    reset-tokens 'Wipe tokens but keep gitea data (forces token rotation)'

require-profile:
	@test -n "$(PROFILE)" || (echo "ERROR: PROFILE is required, e.g. make up PROFILE=programbench-pandoc" >&2 && exit 1)

check-env: require-profile
	@test -f $(ENV_FILE) || (echo "ERROR: $(ENV_FILE) missing — generate it with the pack's profile generator, e.g. tasks/programbench/scripts/gen_env.sh" && exit 1)
	@grep -q '^GITEA_ADMIN_PASSWORD=.\+' $(ENV_FILE) || (echo "ERROR: GITEA_ADMIN_PASSWORD not set in $(ENV_FILE)" && exit 1)

render-base: require-profile
	@AGENSH_WORKERS="$$(grep -E '^AGENSH_WORKERS=' $(ENV_FILE) 2>/dev/null | cut -d= -f2)" \
	AGENT_HARNESS="$$(grep -E '^AGENT_HARNESS=' $(ENV_FILE) 2>/dev/null | cut -d= -f2)" \
	AGENSH_PACK="$(PACK)" AGENSH_NETWORK_MODE="$(NETWORK_MODE)" WORKER_MEMORY="$(call profile_value,WORKER_MEMORY)" \
	WORKER_CPUS="$(call profile_value,WORKER_CPUS)" \
	python3 tools/gen_compose_prod.py > docker/_gen_prod.$(PROFILE).yml \
	&& echo "[render-base] wrote docker/_gen_prod.$(PROFILE).yml" >&2

up: check-env prep-mm-dirs render-base
	@test "$(NETWORK_MODE)" != auto || (echo "ERROR: network mode auto is resolved by the run's prepare hook (AGENSH_RUN_NETWORK); start the team with team_run" >&2 && exit 1)
	$(COMPOSE) up -d --build $(UP_FLAGS) $(SERVICES)

SERVICES ?=

# Packs with per-run prompts require AGENSH_TASK_PROMPTS to start workers; commands
# that only inspect or stop a profile get a placeholder so they work outside a run.
down logs ps pull compose-services clean wipe bootstrap-rerun: export AGENSH_TASK_PROMPTS ?= /nonexistent-task-prompts

UP_FLAGS ?=

compose-services: render-base
	@$(COMPOSE) config --services

# Mattermost writes its host-mounted directories as container UID/GID 2000.
prep-mm-dirs: require-profile
	@$(SUDO) mkdir -p $(DATA_DIR)/mattermost/data $(DATA_DIR)/mattermost/logs $(DATA_DIR)/mattermost/config $(DATA_DIR)/mattermost/plugins
	@$(SUDO) chown -R 2000:2000 $(DATA_DIR)/mattermost

down: render-base
	$(COMPOSE) down

logs: render-base
	$(COMPOSE) logs -f --tail=200

ps: render-base
	$(COMPOSE) ps

build: render-base
	$(COMPOSE) build

pull: render-base
	$(COMPOSE) pull

rebuild: down build up

# Explicitly destructive: stop the selected profile and delete its persistent data.
clean: down
	@test -n "$(PROFILE)"
	$(SUDO) rm -rf $(DATA_DIR)
	@echo "Cleaned $(DATA_DIR)/"

wipe: clean

bootstrap-rerun: render-base
	$(SUDO) rm -f $(DATA_DIR)/tokens/.bootstrap-done
	$(COMPOSE) up bootstrap

reset-tokens: require-profile
	$(SUDO) rm -rf $(DATA_DIR)/tokens
