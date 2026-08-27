#!/usr/bin/env bash
# pbench-docker-sudo.sh — a one-token "docker executable" for ProgramBench eval.
#
# ProgramBench's container layer shells out to a SINGLE docker executable
# (PROGRAMBENCH_DOCKER_EXECUTABLE, default "docker"). On hosts where the user
# isn't in the docker group (this DEV box) the daemon socket is root-only, so
# eval must run `sudo docker`. But a single env value can't carry two words.
# This shim is that single token: it forwards every arg to `sudo docker`.
#
# We point HOME at a writable dir so docker doesn't try to read the root-owned
# ~/.docker/config.json (which emits a permission-denied warning that the eval
# harness mistakes for a container-start failure).
exec sudo HOME=/tmp docker "$@"
