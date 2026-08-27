#!/usr/bin/env bash
# test_cleanroom_tag.sh — the agent's toolchain and the binary it studies must
# come from ONE cleanroom tag.
#
# WHY
# ProgramBench ships more than one cleanroom tag per task, and they are not
# rebuilds of each other. For ffmpeg__ffmpeg.360a402 the two tags on this host
# share ZERO layers:
#
#   :task_cleanroom      Apr 19  ffmpeg git-2026-04-13-10ea080
#                                --disable-ffplay --disable-ffprobe
#   :task_cleanroom_v6   Jun 11  ffmpeg git-2026-06-11-7da4887c
#                                ...--disable-autodetect --enable-zlib --enable-lzma --enable-iconv
#
# Different upstream commit AND different configure flags, so a different set of
# demuxers/muxers is compiled in — for a reverse-rebuild task that is a different
# target behaviour, not a cosmetic version bump.
#
# Two independent paths name a tag:
#   * IMAGE  — pbench_build_pertask_images.sh feeds TASK_IMAGE to
#              Dockerfile.pertask:49 (`FROM ${TASK_IMAGE}`), which fixes the gcc /
#              rustc / crate versions the agent compiles against.
#   * SEED   — pbench_run_1team.sh's seed_repo() extracts /workspace out of
#              CLEANROOM_IMG: the starting repo AND the reference binary that gets
#              parked root:root 0111 at /opt/pbench/executable.
#
# When 6.11 moved the build path to _v6 the seed path was left on the old tag, so
# agents reverse-engineered the April binary while running the June toolchain and
# being graded on the June behaviour. Nothing failed loudly: both tags exist, both
# pull, the run completes and scores — just against the wrong target.
#
# This test does not care WHICH tag is chosen. It cares that all of them agree.
#
# Usage: bash tests/pbench/test_cleanroom_tag.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
rc=0
ok()   { echo "PASS $*"; }
fail() { echo "FAIL $*"; rc=1; }

# Pull the tag out of every construction site. A tag is whatever follows
# "task_cleanroom" up to the closing quote: "" for the bare tag, "_v6" for v6.
# Comments are stripped first — the code around these lines explains why the two
# tags differ and therefore names BOTH, which is documentation, not usage.
tags_in() {
    sed 's/#.*//' "$1" 2>/dev/null | grep -hoE 'task_cleanroom[a-z0-9_]*' | sort -u
}

SEED_FILE="$ROOT/scripts/pbench_run_1team.sh"
BUILD_FILE="$ROOT/scripts/pbench_build_pertask_images.sh"

seed_tag="$(tags_in "$SEED_FILE")"
build_tag="$(tags_in "$BUILD_FILE")"

[ -n "$seed_tag" ]  || fail "no cleanroom tag found in $(basename "$SEED_FILE")"
[ -n "$build_tag" ] || fail "no cleanroom tag found in $(basename "$BUILD_FILE")"

# Each file must be internally consistent first.
[ "$(printf '%s\n' "$seed_tag"  | wc -l)" = 1 ] \
    && ok "seed path names exactly one cleanroom tag ($seed_tag)" \
    || fail "seed path names several cleanroom tags: $(echo $seed_tag)"
[ "$(printf '%s\n' "$build_tag" | wc -l)" = 1 ] \
    && ok "image build path names exactly one cleanroom tag ($build_tag)" \
    || fail "image build path names several cleanroom tags: $(echo $build_tag)"

# The one that matters: seed == build.
[ "$seed_tag" = "$build_tag" ] \
    && ok "seed tag == image tag ($seed_tag) — agent studies the binary it is graded on" \
    || fail "seed tag '$seed_tag' != image tag '$build_tag' — agents reverse-engineer one binary while compiled against, and graded on, another"

# The sweep preflight only verifies the tag it knows about. If it checks a tag
# nobody uses, a missing cleanroom passes preflight and dies mid-run instead.
for sweep in "$ROOT"/scripts/pbench_1team_sweep*.sh; do
    [ -f "$sweep" ] || continue
    st="$(tags_in "$sweep")"
    [ -z "$st" ] && continue
    [ "$st" = "$build_tag" ] \
        && ok "$(basename "$sweep") preflights the tag actually used ($st)" \
        || fail "$(basename "$sweep") preflights '$st' but the run uses '$build_tag'"
done

# Dockerfile.pertask must keep taking the base from the build arg. If someone
# hard-codes a FROM there, the build script's tag becomes decoration.
DF="$ROOT/docker/hermes-agent/Dockerfile.pertask"
if [ -f "$DF" ]; then
    grep -qE '^FROM +\$\{TASK_IMAGE\}' "$DF" \
        && ok "Dockerfile.pertask still takes its base from \${TASK_IMAGE}" \
        || fail "Dockerfile.pertask no longer does FROM \${TASK_IMAGE} — the build tag is decorative"
    grep -qE '^FROM +programbench/' "$DF" \
        && fail "Dockerfile.pertask hard-codes a programbench base image" \
        || ok "Dockerfile.pertask hard-codes no cleanroom image"
fi

exit $rc
