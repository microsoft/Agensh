#!/usr/bin/env bash
# pbench-docker-sudo.sh — a one-token "docker executable" for ProgramBench eval.
#
# ProgramBench's container layer shells out to a SINGLE docker executable
# (PROGRAMBENCH_DOCKER_EXECUTABLE, default "docker"). On hosts where the user
# isn't in the docker group (a dev box) the daemon socket is root-only, so
# eval must run `sudo docker`. But a single env value can't carry two words.
# This shim is that single token: it forwards every arg to `sudo docker`.
#
# We point HOME at a writable dir so docker doesn't try to read the root-owned
# ~/.docker/config.json (which emits a permission-denied warning that the eval
# harness mistakes for a container-start failure).
#
# ---------------------------------------------------------------------------
# MEMORY CAP. A single runaway test binary (a submission's own compiled
# `executable`) can allocate hundreds of GB and take the host down with global
# OOM kills, and ProgramBench's eval runs that same submitted binary through
# ./eval/run.sh after every agent stack is down. The agents' per-container
# mem_limit cannot reach it — this container is created by ProgramBench, not by
# our compose, so neither mem_limit nor cgroup_parent applies.
#
# ProgramBench hardcodes `DOCKER_RUN_ARGS: list[str] = []` (constants.py) with no
# env hook, and patching the grader is out of the question. But it does read
# PROGRAMBENCH_DOCKER_EXECUTABLE, and we already occupy that slot — so the cap
# goes here. Still glue; the grader is untouched.
#
# 128g, not the agents' 64g: eval legitimately runs a whole hidden suite in one
# process (php's gold branch alone is 18,095 tests) and must not be throttled
# into a timeout, which is its own scoring artifact. 128g is far above any
# healthy eval and still leaves a 503 GB host alive with three concurrent
# runaways.
#
# ONLY `run` is touched, for the cap and the network alike. This shim is the executable for EVERY docker call the
# eval makes — cp, exec, inspect, rm — and injecting a flag into those breaks
# them.
set -u

CAP="${PBENCH_EVAL_MEM_CAP:-128g}"

# NETWORK (opt-in). ProgramBench's `docker run` uses the default bridge, and on a
# shared host another daemon can remove docker0, after which no eval container
# starts. PBENCH_EVAL_NETWORK names a bridge network this project created, and
# every `run` joins it. `--network none` is not a substitute: eval pip-installs
# pytest-rerunfailures in the container, and without it the tests get no reruns.
# Only omcgitea-* names are accepted, so eval never joins another project's network.
NET="${PBENCH_EVAL_NETWORK:-}"
case "$NET" in
    ""|omcgitea-*) ;;
    *) echo "pbench-docker-sudo: PBENCH_EVAL_NETWORK must name an omcgitea-* network, not '$NET'" >&2
       exit 2 ;;
esac

# Locate the subcommand: the first token that is not a global flag.
sub=""; idx=0
for a in "$@"; do
    idx=$((idx + 1))
    case "$a" in
        -*) continue ;;
        *)  sub="$a"; break ;;
    esac
done

if [ "$sub" = "run" ]; then
    # Insert the cap immediately after `run` — before the image name, so docker
    # parses it instead of handing it to the container. --memory-swap equal to
    # --memory disables swap; without it the ceiling is porous and a leak just
    # swaps instead of dying.
    extra=(--memory="$CAP" --memory-swap="$CAP")
    [ -n "$NET" ] && extra+=(--network="$NET")
    set -- "${@:1:$idx}" "${extra[@]}" "${@:$((idx + 1))}"
fi

if [ -n "${PBENCH_DOCKER_SHIM_DRYRUN:-}" ]; then
    echo "sudo HOME=/tmp docker $*"
    exit 0
fi

exec sudo HOME=/tmp docker "$@"
