#!/usr/bin/env bash
# T1: .env.org-pbench shape test
# Verifies the new pbench profile env file exists at repo root, routes the
# agent LLM egress through the in-cluster egress-proxy, and pins that
# proxy's upstream to the LLM VM (20.9.234.247), with required secrets.
#
# Run: bash tests/pbench/test_env.sh
# Expected: all assertions pass; non-zero exit on any failure.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env.org-pbench"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok()   { echo "  ok: $*"; }

[ -f "$ENV_FILE" ] || fail ".env.org-pbench not found at $ENV_FILE"
ok "env file exists"

# Pull values without sourcing (avoid side effects).
get() { grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2- ; }

[ "$(get PROFILE)" = "org-pbench" ]                       || fail "PROFILE must be org-pbench"
ok "PROFILE=org-pbench"

[ "$(get ORG_NAME)" = "pbench" ]                          || fail "ORG_NAME must be pbench"
ok "ORG_NAME=pbench"

# Agents must egress via the in-cluster proxy (internal net has no public
# route), NOT a direct public IP.
[ "$(get ANTHROPIC_BASE_URL)" = "http://egress-proxy:4180" ] \
    || fail "ANTHROPIC_BASE_URL must route via egress-proxy (http://egress-proxy:4180)"
ok "ANTHROPIC_BASE_URL routed through egress-proxy"

# The proxy's upstream is the real LLM backend.
[ -n "$(get PBENCH_LLM_UPSTREAM)" ] \
    || fail "PBENCH_LLM_UPSTREAM must be set (egress-proxy upstream)"
ok "PBENCH_LLM_UPSTREAM set ($(get PBENCH_LLM_UPSTREAM))"

# pbench bin anti-reverse-engineering -- privilege-drop vars must be present.
[ "$(get ACP_CHILD_UID)" = "10000" ]                     || fail "ACP_CHILD_UID must be 10000"
[ "$(get ACP_CHILD_GID)" = "10000" ]                     || fail "ACP_CHILD_GID must be 10000"
ok "ACP_CHILD_UID/GID=10000 (bin anti-reverse-engineering privilege drop)"

key="$(get ANTHROPIC_API_KEY)"
[ -n "$key" ] && [ "$key" != "CHANGE_ME" ]                || fail "ANTHROPIC_API_KEY missing or placeholder"
ok "ANTHROPIC_API_KEY set"

# Secrets must be present and non-placeholder.
for v in GITEA_ADMIN_PASSWORD MYSQL_ROOT_PASSWORD MYSQL_PASSWORD \
         SECRET_SERVICE_INTERNAL_AUTH MATTERMOST_ADMIN_PASSWORD; do
    val="$(get "$v")"
    [ -n "$val" ] && [[ "$val" != CHANGE_ME* ]] || fail "$v missing or placeholder"
    ok "$v set"
done

# Port base must avoid org-test's 3300/3302 (DEV2 colocation).
port="$(get EDGE_HTTP_PORT)"
[ -n "$port" ] && [ "$port" != "3300" ]                   || fail "EDGE_HTTP_PORT must not collide with org-test (3300)"
ok "EDGE_HTTP_PORT=$port (no collision with org-test)"

echo "PASS: tests/pbench/test_env.sh"
