#!/usr/bin/env bash
# test_agent_image_preflight.sh — the image the preflight checks must be the
# image the run actually uses.
#
# WHY
# pbench_run_1team.sh guards the agent image before `make up`:
#
#     local agent_img="${AGENT_IMAGE:-omcgitea-hermes-agent:local}"
#     sudo docker image inspect "$agent_img" || die "agent image missing: ..."
#
# and its own comment states the contract: "Compose reads AGENT_IMAGE from
# .env.<profile>; we re-check it here so a typo fails in 2 seconds rather than
# after `make up` has provisioned a stack."
#
# But it read AGENT_IMAGE from the SHELL, and nothing puts it there. Compose
# gets it via --env-file; the runner never greps it out of $ENV_FILE the way it
# greps DATA_ROOT / ORG_NAME / EDGE_HTTP_PORT. pbench_chain.sh does not export
# it either, and pbench_1team_sweep.sh only *validates* that .env.<profile>
# carries the right value — it never passes it through.
#
# So the guard checked the historical fallback tag instead, and had two failure
# modes, both silent in opposite directions:
#
#   * fallback tag present  — preflight passes while verifying an image the run
#     will not use. A typo'd or unbuilt per-task image then dies after `make up`
#     has provisioned a stack: exactly what the guard exists to prevent.
#   * fallback tag absent   — every task FATALs at preflight naming an image the
#     profile never asked for, even though the per-task image is built and fine.
#
# The v48 path (AGENT_IMAGE unset anywhere) must keep falling back to
# omcgitea-hermes-agent:local — that shape is still supported.
#
# Usage: bash tests/pbench/test_agent_image_preflight.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNNER="$ROOT/scripts/pbench_run_1team.sh"
rc=0
ok()   { echo "PASS $*"; }
fail() { echo "FAIL $*"; rc=1; }

# 1. The runner must source AGENT_IMAGE from the profile, like every other
#    compose variable it re-reads.
grep -qE "AGENT_IMAGE=.*(ENV_FILE|env_file)" "$RUNNER" \
    && ok "runner reads AGENT_IMAGE from .env.<profile>" \
    || fail "runner never reads AGENT_IMAGE from \$ENV_FILE — it guards the fallback tag while compose runs the per-task image"

# 2. The shell must still win when set, so a one-off override works.
grep -qE '^\s*AGENT_IMAGE="\$\{AGENT_IMAGE:-' "$RUNNER" \
    && ok "an explicit AGENT_IMAGE in the environment still overrides the profile" \
    || fail "runner ignores an AGENT_IMAGE exported by the caller"

# 3. The v48 shape survives: no profile value and no shell value -> :local.
grep -qE 'AGENT_IMAGE:-omcgitea-hermes-agent:local|agent_img=.*omcgitea-hermes-agent:local' "$RUNNER" \
    && ok "v48 fallback to omcgitea-hermes-agent:local is intact" \
    || fail "the AGENT_IMAGE-unset v48 path no longer falls back to :local"

# 4. Behavioural: resolve AGENT_IMAGE exactly as the runner does, against a real
#    profile file, and assert it lands on the profile's image. This is the bug —
#    a static grep alone would pass on a runner that reads the wrong file.
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cat >"$TMP/.env.probe" <<'EOF'
PROFILE=probe
DATA_ROOT=/tmp/probe
AGENT_IMAGE=omcgitea-agent-probe:pertask-claude
EOF
# Lift the runner's own resolution line(s) and run them against the probe file,
# so this test tracks whatever the runner does rather than a copy of it.
RESOLVE="$(grep -E '^\s*AGENT_IMAGE=' "$RUNNER" | sed 's/^[[:space:]]*//')"
if [ -n "$RESOLVE" ]; then
    got="$(ENV_FILE="$TMP/.env.probe"; unset AGENT_IMAGE; eval "$RESOLVE"; echo "${AGENT_IMAGE:-}")"
    [ "$got" = "omcgitea-agent-probe:pertask-claude" ] \
        && ok "resolution picks up the profile's image ($got)" \
        || fail "resolution yielded '${got:-<empty>}', not the profile's omcgitea-agent-probe:pertask-claude"

    # ...and an exported value must beat the file.
    got2="$(ENV_FILE="$TMP/.env.probe"; AGENT_IMAGE=omcgitea-agent-override:x; eval "$RESOLVE"; echo "${AGENT_IMAGE:-}")"
    [ "$got2" = "omcgitea-agent-override:x" ] \
        && ok "an exported AGENT_IMAGE overrides the profile ($got2)" \
        || fail "exported AGENT_IMAGE was ignored, got '${got2:-<empty>}'"
else
    fail "no AGENT_IMAGE assignment found in the runner at all"
fi

# 5. The sweep validates .env.<profile> AGENT_IMAGE. That check is only
#    meaningful if the runner then USES that value; assert the validation is
#    still there so the two halves cannot drift apart again.
SWEEP="$ROOT/scripts/pbench_1team_sweep.sh"
[ -f "$SWEEP" ] && {
    grep -q 'AGENT_IMAGE' "$SWEEP" \
        && ok "sweep preflight still validates each profile's AGENT_IMAGE" \
        || fail "sweep no longer validates AGENT_IMAGE per profile"
}

# 6. The image must not be STALE. Role fragments are bind-mounted precisely so a
#    prompt edit needs no rebuild — but entrypoint.sh is COPYed into the image
#    (Dockerfile.pertask:110) and mounted nowhere, so a change to it reaches a
#    run only after the per-task images are rebuilt.
#
#    This bit in anger: dropping the four placeholder fragments per role and
#    teaching entrypoint.sh to derive its required set left 20 images carrying
#    the old hard-coded six-fragment guard. The workers survived — the 1team
#    overlay mounts their fragments FILE-BY-FILE, so the baked copies stayed
#    visible underneath — but director_lead is mounted as a whole DIRECTORY,
#    which hides them, so every lead hit
#      FATAL: .../director_lead/dos.md missing or empty
#    and crash-looped while the other four agents ran on happily. A run with no
#    lead still boots, still opens the task issue, still exports a submission,
#    and still scores. It just scores a team that never got assigned any work.
#
#    Skips cleanly when the image is not built locally.
IMG_ENTRY=/opt/omcgitea/entrypoint.sh
REPO_ENTRY="$ROOT/docker/hermes-agent/entrypoint.sh"
DOCKER="${PBENCH_DOCKER:-sudo docker}"
imgs="$($DOCKER images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null \
        | grep -E '^omcgitea-agent-[a-z0-9_-]+:pertask' | sort || true)"
if [ -z "$imgs" ]; then
    ok "no per-task agent image built locally — staleness check skipped"
elif [ ! -f "$REPO_ENTRY" ]; then
    fail "repo entrypoint.sh not found at $REPO_ENTRY"
else
    want="$(md5sum <"$REPO_ENTRY" | cut -d' ' -f1)"
    for img in $imgs; do
        got="$($DOCKER run --rm --entrypoint cat "$img" "$IMG_ENTRY" 2>/dev/null \
               | md5sum | cut -d' ' -f1)"
        if [ "$got" = "$want" ]; then
            ok "$img bakes the current entrypoint.sh"
        else
            fail "$img bakes a STALE entrypoint.sh — rebuild it (scripts/pbench_build_pertask_images.sh) or the lead crash-loops while the workers run"
        fi
    done
fi

exit $rc
