#!/usr/bin/env bash
# test_memory_ceiling.sh — ProgramBench work must not be able to take the machine down.
#
# WHY
# Sweep 6.10 died at 2026-08-06 20:02 PDT with 11 CONSTRAINT_NONE (machine-wide) OOM kills.
# The last complete kernel task dump showed 492.6 GB of 503 GB in use and ONE process holding
# 474.13 GB: `executable`, ProgramBench's binary, run by a test case. See
# v2docs/INCIDENT_6.10_MEMORY.md.
#
# The fixes that already existed did not apply:
#   - CI job containers are capped (--memory=8g), but workers run the suite INSIDE the agent
#     container, which had no limit at all.
#   - the per-case `timeout -k 2 30` never fired: 30s is ample to allocate 474 GB at this
#     memory bandwidth. A time limit does not bound memory.
#   - 6.6's fan-out fixes (-P 8, then sequential) are irrelevant to a single allocation.
#
# So the ceiling has to be an AGGREGATE cap over everything ProgramBench runs -- rollout, eval
# and sweep alike -- placed where a process inside a container cannot raise it. On cgroup v2
# with the systemd driver that is a slice: a container's cgroup is created UNDER its parent, so
# the child can only ever lower its own limit, never exceed the parent's.
#
# Usage: bash tests/pbench/test_memory_ceiling.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SLICE="$ROOT/docker/pbench.slice"
GEN="$ROOT/tools/gen-compose-prod.py"
rc=0
ok()   { echo "PASS $*"; }
fail() { echo "FAIL $*"; rc=1; }

# --- 1. the slice itself ------------------------------------------------------
[ -f "$SLICE" ] \
    && ok "a pbench.slice unit is shipped in the repo" \
    || fail "no slice unit — nothing defines the aggregate ceiling"
grep -qE '^MemoryMax=80%' "$SLICE" 2>/dev/null \
    && ok "the slice caps memory at 80% of physical RAM" \
    || fail "slice does not declare MemoryMax=80%"
# A percentage, not a byte count: this repo runs on more than one machine, and a hardcoded
# figure silently becomes the wrong fraction on the next host.
grep -qE '^MemoryMax=[0-9]+[GM]' "$SLICE" 2>/dev/null \
    && fail "MemoryMax is an absolute size — it will be the wrong fraction on another host" \
    || ok "the cap is relative to the machine, not hardcoded"

# --- 2. everything ProgramBench starts must land in the slice ------------------
# Agent containers are the layer that was unprotected: workers run tests/run.sh there.
grep -q 'cgroup_parent' "$GEN" \
    && ok "compose places containers under a cgroup parent" \
    || fail "containers are not placed in the slice — the cap applies to nothing"
for anchor in x-hermes-agent x-mini-router; do
    awk -v a="$anchor" '$0 ~ "^"a":" {f=1} f && /cgroup_parent/ {print; exit} f && /^[a-z]/ && $0 !~ "^"a":" {exit}' "$GEN" \
        | grep -q 'pbench.slice' \
        && ok "$anchor is in pbench.slice" \
        || fail "$anchor is NOT in the slice — the agent container is where the 474 GB was"
done
# act_runner spawns CI job containers itself, over the docker socket. They do not inherit
# compose's cgroup_parent, so the flag has to be in the runner's own container options.
grep -E 'ACT_JOB_LIMITS' "$GEN" | grep -q 'cgroup-parent=pbench.slice' \
    && ok "CI job containers are placed in the slice too" \
    || fail "CI job containers escape the slice — act_runner creates them directly"

# --- 3. eval runs on the HOST, not in a container -----------------------------
# `programbench eval` unpacks and builds the submission outside docker, so the slice has to be
# entered explicitly there or the largest single consumer stays uncapped.
grep -rqE 'systemd-run.*--slice=pbench' "$ROOT/scripts/" 2>/dev/null \
    && ok "host-side eval is run inside the slice" \
    || fail "eval runs on the host outside any ceiling"

# --- 4. BEHAVIOURAL: prove the kernel enforces it, and that a container cannot escape ---
# Asserting the config is not enough -- 6.10's lesson is that a ceiling nobody verified is a
# ceiling that turns out not to apply. Build a tiny slice, run a container under it that tries
# to allocate past the cap, and require the kernel to stop it.
if ! command -v systemd-run >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
    echo "SKIP behavioural check (needs systemd-run + docker)"
else
    # `set-property` on a slice that has never run is a no-op, which would make the check
    # pass vacuously. Start it first, then bind the limit, then confirm the kernel took it.
    sudo systemd-run --unit=pbench-test-probe --slice=pbench-test.slice --quiet sleep 30 2>/dev/null
    # MemorySwapMax=0 as well as MemoryMax -- and this is not a detail. With swap available,
    # a 512M allocation under a 256M cap simply pages out and SURVIVES: verified on this host,
    # both a dd buffer and a tmpfs write completed fine under MemoryMax alone. The cap only
    # binds when the slice cannot fall back to swap, which is why docker/pbench.slice sets it.
    sudo systemctl set-property --runtime pbench-test.slice MemoryMax=256M MemorySwapMax=0 2>/dev/null
    BOUND=$(systemctl show pbench-test.slice -p MemoryMax --value 2>/dev/null)
    [ "$BOUND" = "268435456" ] \
        && ok "the probe slice really carries a 256M cap (kernel value $BOUND)" \
        || fail "could not bind a limit to the probe slice (got '$BOUND') — check is vacuous"
    # dd allocates its block size as ONE anonymous buffer -- a single 512M allocation, the
    # shape of the 6.10 failure. (`tail -c N /dev/zero` never terminates: /dev/zero has no EOF,
    # so it buffers forever and hangs the test instead of testing anything.)
    OUT=$(timeout 120 sudo docker run --rm --cgroup-parent=pbench-test.slice \
            --entrypoint sh alpine:3 -c \
            'dd if=/dev/zero of=/dev/null bs=512M count=1 2>/dev/null && echo SURVIVED' 2>&1)
    STAT=$?
    printf '%s' "$OUT" | grep -q SURVIVED \
        && fail "a container in a 256M slice allocated 512M — the cap does not bind" \
        || ok "the kernel killed an over-allocating container inside its slice (rc=$STAT)"
    # ...and the container must not be able to raise its own ceiling.
    RAISED=$(timeout 60 sudo docker run --rm --cgroup-parent=pbench-test.slice --entrypoint sh alpine:3 -c \
            'echo 8G > /sys/fs/cgroup/memory.max 2>/dev/null && echo RAISED || echo REFUSED' 2>&1)
    printf '%s' "$RAISED" | grep -q REFUSED \
        && ok "a process inside the container cannot raise the ceiling" \
        || fail "the container rewrote its own memory.max — the cap is advisory"
    sudo systemctl stop pbench-test-probe.service 2>/dev/null || true
    sudo systemctl stop pbench-test.slice 2>/dev/null || true
fi

exit $rc
