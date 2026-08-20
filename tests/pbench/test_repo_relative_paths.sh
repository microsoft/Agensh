#!/usr/bin/env bash
# test_repo_relative_paths.sh — the snapshot must operate on ITSELF.
#
# WHY
# This tree is a standalone snapshot: it gets copied, unpacked next to the
# original, or handed to someone else entirely. Every script that resolves the
# repo root has to derive it from its OWN location, the way pbench_run_1team.sh
# already does:
#
#     ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
#
# A script that instead says ROOT="$HOME/agensteam" reads its compose files, its
# .env.<profile>, its templates and its out/ from a DIFFERENT checkout than the
# one it was invoked from. Nothing errors — the paths all exist over there — so a
# run launched from the snapshot quietly builds images from the other tree's
# Dockerfiles, writes results into the other tree's out/, and can collide with a
# sweep already running there. The failure mode is a correct-looking run that
# measured the wrong code.
#
# Same for DATA_ROOT: an absolute default pins every profile's container state
# under one fixed checkout, so two trees fight over the same data dir.
#
# Env-var overrides (PBENCH_ROOT, TRAJ_ROOT, DATA_ROOT=...) are fine — the
# default is what must be relative.
#
# Usage: bash tests/pbench/test_repo_relative_paths.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
rc=0
ok()   { echo "PASS $*"; }
fail() { echo "FAIL $*"; rc=1; }

# Scripts that drive a run: they read compose files, .env.<profile> and templates
# out of the repo, so their ROOT must be this repo.
DRIVERS="
scripts/pbench_run_1team.sh
scripts/pbench_chain.sh
scripts/pbench_build_pertask_images.sh
scripts/pbench_1team_sweep.sh
scripts/pbench_gen_env_sweep.sh
scripts/pbench_reboot_guard.sh
"

for rel in $DRIVERS; do
    f="$ROOT/$rel"
    [ -f "$f" ] || continue
    b="$(basename "$rel")"
    # The ROOT assignment, comments stripped.
    line="$(sed 's/#.*//' "$f" | grep -m1 -E '^[[:space:]]*ROOT=')"
    if [ -z "$line" ]; then
        ok "$b does not resolve a repo root"
        continue
    fi
    case "$line" in
        *BASH_SOURCE*)
            ok "$b derives ROOT from its own location" ;;
        *'$HOME'*|*/home/*)
            fail "$b pins ROOT to a fixed checkout ($(echo "$line" | tr -s ' ')) — it would run against that tree, not this one" ;;
        *)
            fail "$b sets ROOT in an unrecognised way: $(echo "$line" | tr -s ' ')" ;;
    esac
done

# No script may bake an absolute path to a sibling checkout as a DEFAULT.
# tests/ is exempt: it legitimately points at external trajectory archives that
# live outside any checkout, and skips cleanly when they are absent.
hits="$(grep -rn 'HOME/agensteam\|/home/[a-z]*/agensteam' \
          "$ROOT"/scripts "$ROOT"/tools "$ROOT"/Makefile 2>/dev/null \
        | grep -v __pycache__ \
        | grep -vE '^\S+:[0-9]+:[[:space:]]*#' \
        | grep -vE 'TRAJ_ROOT=' || true)"
[ -z "$hits" ] \
    && ok "no script or tool hard-codes a path into another checkout" \
    || fail "hard-coded checkout paths remain:
$hits"

exit $rc
