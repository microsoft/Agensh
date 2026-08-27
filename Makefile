# omcgitea — Hermes ↔ Gitea M1 Makefile
#
# All targets run the docker stack under docker/docker-compose.yml with sudo
# (the dev box has docker.sock owned by root:docker; the user is not in
# the docker group). Override SUDO= to skip sudo.

SHELL := /bin/bash

# Profile selector — dev (default) vs prod. Each profile has its own
# .env.<profile>, data dir (.claude-team-data/<profile>/), compose project
# name (omcgitea-<profile>) and edge port. See DESIGN §5.A.
PROFILE ?= dev
ENV_FILE := .env.$(PROFILE)
PROJECT  := omcgitea-$(PROFILE)
DATA_DIR := .claude-team-data/$(PROFILE)

# For org-* profiles the compose template uses ${DATA_ROOT}/${PROFILE} instead
# of the fixed ../.claude-team-data/${PROFILE}; read DATA_ROOT from the env
# file so prep-mm-dirs / clean chown the right directory.
ifneq (,$(filter org-%,$(PROFILE)))
ENV_DATA_ROOT := $(shell grep -E '^DATA_ROOT=' $(ENV_FILE) 2>/dev/null | cut -d= -f2)
ifneq (,$(ENV_DATA_ROOT))
DATA_DIR := $(ENV_DATA_ROOT)/$(PROFILE)
endif
endif

# host.docker.internal:host-gateway needs Docker 20.10+; we already have 29.x.
# We deliberately strip the user's shell ANTHROPIC_* / GITEA_* / HERMES_*
# vars before invoking compose so .env.<profile> is the single source of
# truth — the user's ~/.bashrc may set ANTHROPIC_BASE_URL=http://localhost:4141
# (works only on the host, not inside containers) and we must not let it leak in.
SUDO ?= sudo -E

# org-pbench*: the agent topology is generated per-profile from
# tools/gen-compose-prod.py into docker/_gen-prod.<profile>.yml (so
# .env.<profile> can set PBENCH_TEAMS / PBENCH_WORKERS_PER_TEAM / PBENCH_AUDITOR
# to deploy a smaller team — default = the original 37). It also layers
# docker-compose.pbench.yml — the ProgramBench egress-lock overlay
# (internal:true default net + egress-proxy). dev/prod are unaffected.
ifneq (,$(filter org-pbench org-pbench-%,$(PROFILE)))
# Recursive (=) so COMPOSE_BASE picks up the file render-pbench-base writes.
# There is no fallback: a missing _gen-prod.<profile>.yml must fail loudly
# rather than silently deploy a different topology.
COMPOSE_BASE = docker/_gen-prod.$(PROFILE).yml
COMPOSE_OVERLAY := -f docker/docker-compose.pbench.yml
# org-pbench-method-2a[-<inst>]: our-method 1team + one shared context board.
# This is the sweep-6.11 arm — the 1-team subset overlay (which disables the
# other 60 services via profiles: [_disabled]) plus the board overlay. Sibling
# profiles (org-pbench-method-2a-s611a/-s611b/...) reuse the same two files so
# parallel chains can run in isolated data-roots + compose projects.
ifneq (,$(filter org-pbench-method-2a org-pbench-method-2a-%,$(PROFILE)))
COMPOSE_OVERLAY := $(COMPOSE_OVERLAY) -f docker/docker-compose.pbench-1team.yml -f docker/docker-compose.pbench-1team-board.yml
endif
else ifneq (,$(filter org-%,$(PROFILE)))
# Any other org-* profile: the frozen 37-agent prod template, unlayered.
COMPOSE_BASE := docker/docker-compose.prod.yml
COMPOSE_OVERLAY :=
else
COMPOSE_BASE := docker/docker-compose.yml
COMPOSE_OVERLAY :=
endif

COMPOSE ?= env -u ANTHROPIC_BASE_URL -u ANTHROPIC_MODEL -u ANTHROPIC_API_KEY \
            -u AGENT_KIND -u COPILOT_PROVIDER_TYPE \
            -u HERMES_INFERENCE_PROVIDER -u HERMES_MODEL \
            -u GITEA_HOST -u GITEA_TOKEN \
            $(SUDO) docker compose -f $(COMPOSE_BASE) $(COMPOSE_OVERLAY) \
            --project-name $(PROJECT) --env-file $(ENV_FILE) \
            --profile $(PROFILE)


.PHONY: help up down logs ps build pull rebuild clean clean-artifacts wipe \
        bootstrap-rerun reset-tokens hermes-image-prepare check-env prep-mm-dirs render-pbench-base

help:
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

check-env: ## Verify .env.<profile> has the required keys
	@test -f $(ENV_FILE) || (echo "ERROR: $(ENV_FILE) missing — copy .env.example to $(ENV_FILE) and fill GITEA_ADMIN_PASSWORD" && exit 1)
	@grep -q '^GITEA_ADMIN_PASSWORD=.\+' $(ENV_FILE) || (echo "ERROR: GITEA_ADMIN_PASSWORD not set in $(ENV_FILE)" && exit 1)


# Render the per-profile pbench base compose from tools/gen-compose-prod.py,
# passing the topology knobs from .env.<profile> (absent → the 37-agent
# default; the 6.11 1-team arm sets PBENCH_TEAMS=1 / PBENCH_WORKERS_PER_TEAM=3).
# Only fires for org-pbench*; other profiles are no-ops. The emitted
# docker/_gen-prod.<profile>.yml is picked up by COMPOSE_BASE above.
render-pbench-base:
	@case "$(PROFILE)" in \
	    org-pbench|org-pbench-*) \
	        PBENCH_TEAMS="$$(grep -E '^PBENCH_TEAMS=' $(ENV_FILE) 2>/dev/null | cut -d= -f2)" \
	        PBENCH_WORKERS_PER_TEAM="$$(grep -E '^PBENCH_WORKERS_PER_TEAM=' $(ENV_FILE) 2>/dev/null | cut -d= -f2)" \
	        PBENCH_AUDITOR="$$(grep -E '^PBENCH_AUDITOR=' $(ENV_FILE) 2>/dev/null | cut -d= -f2)" \
	        PBENCH_TEMPLATES_DIR="$$(grep -E '^PBENCH_TEMPLATES_DIR=' $(ENV_FILE) 2>/dev/null | cut -d= -f2-)" \
	        PBENCH_CC_BIN="$$(grep -E '^PBENCH_CC_BIN=' $(ENV_FILE) 2>/dev/null | cut -d= -f2-)" \
	        python3 tools/gen-compose-prod.py > docker/_gen-prod.$(PROFILE).yml \
	        && echo "[render-pbench-base] wrote docker/_gen-prod.$(PROFILE).yml" ;; \
	    *) : ;; \
	esac

HERMES_BASE_REGISTRY ?= localhost:9091/omcgitea/hermes-agent:base

hermes-image-prepare: ## Ensure hermes-agent:local is available (pull from registry, fallback to build)
	@if [ -n "$(AGENT_IMAGE)" ]; then \
		echo "hermes-image-prepare skipped — AGENT_IMAGE=$(AGENT_IMAGE) is in use"; \
	elif $(SUDO) docker image inspect hermes-agent:local >/dev/null 2>&1; then \
		echo "hermes-agent:local already present"; \
	elif $(SUDO) docker pull $(HERMES_BASE_REGISTRY) >/dev/null 2>&1; then \
		echo "Pulled $(HERMES_BASE_REGISTRY); tagging as hermes-agent:local"; \
		$(SUDO) docker tag $(HERMES_BASE_REGISTRY) hermes-agent:local; \
	else \
		echo "Building upstream hermes-agent image (one-time, ~5-10 min)..."; \
		$(SUDO) docker build -t hermes-agent:local -t $(HERMES_BASE_REGISTRY) hermes-agent; \
		$(SUDO) docker push $(HERMES_BASE_REGISTRY) || echo "(push to $(HERMES_BASE_REGISTRY) skipped)"; \
	fi

up: check-env hermes-image-prepare prep-mm-dirs render-pbench-base ## Start the full stack (build if needed)
	$(COMPOSE) up -d --build

# Mattermost runs as uid 2000; on a fresh profile its bind-mount dirs
# don't exist yet and would be auto-created by docker as root, which
# then makes the container fail with "permission denied" on
# /mattermost/config/config.json. Pre-create + chown so first `make up`
# works without manual intervention.
prep-mm-dirs:
	@$(SUDO) mkdir -p $(DATA_DIR)/mattermost/data $(DATA_DIR)/mattermost/logs $(DATA_DIR)/mattermost/config $(DATA_DIR)/mattermost/plugins
	@$(SUDO) chown -R 2000:2000 $(DATA_DIR)/mattermost

# down/logs/ps/build/pull re-render the base first: COMPOSE_BASE points at
# docker/_gen-prod.$(PROFILE).yml with no fallback, and that file is generated
# (gitignored), so a fresh checkout would otherwise fail with "no such file".
# gen-compose-prod.py is deterministic, so re-rendering an existing stack's base
# is a no-op.
down: render-pbench-base ## Stop containers (keep data)
	$(COMPOSE) down

logs: render-pbench-base ## Tail logs
	$(COMPOSE) logs -f --tail=200

ps: render-pbench-base ## List service status
	$(COMPOSE) ps

build: hermes-image-prepare render-pbench-base ## (Re)build images
	$(COMPOSE) build

pull: render-pbench-base ## Pull base images
	$(COMPOSE) pull

rebuild: down build up ## Force rebuild + restart

clean: down ## Stop containers and wipe THIS profile's data dir (DESTRUCTIVE)
	$(SUDO) rm -rf $(DATA_DIR)
	@echo "Cleaned $(DATA_DIR)/"

clean-artifacts: ## Wipe tests/_artifacts/
	rm -rf tests/_artifacts
	@echo "Cleaned tests/_artifacts/"

wipe: clean ## Alias for clean

bootstrap-rerun: ## Re-run bootstrap (idempotent)
	$(SUDO) rm -f $(DATA_DIR)/tokens/.bootstrap-done
	$(COMPOSE) up bootstrap

reset-tokens: ## Wipe tokens but keep gitea data (forces token rotation)
	$(SUDO) rm -rf $(DATA_DIR)/tokens

# ---------------------------------------------------------------------------
# ProgramBench sweep 6.11, one team (5 agents + shared context board).
#
# There is no `make pbench`-style entry point here: a 6.11 run is driven by
# scripts/pbench_1team_sweep.sh, which preflights 20 profiles and then hands
# each task to scripts/pbench_chain.sh -> scripts/pbench_run_1team.sh. Those
# scripts call `make up/down/clean PROFILE=org-pbench-method-2a-s611<letter>`
# themselves. See the header of scripts/pbench_1team_sweep.sh.
# ---------------------------------------------------------------------------
