#!/usr/bin/env bash
# Run one task for a team. The task-neutral driver is agensh/team_run.py; the
# ProgramBench seeding, export and evaluation steps are the hooks in
# tasks/programbench/. Settings come from the environment as before: TASK,
# PROFILE, HOURS, OUT_DIR, SKIP_EVAL, PROGRAMBENCH_*, PBENCH_* and WORKER_*.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python3 -c 'import tomllib' 2>/dev/null \
    || { echo "[agensh] FATAL: Python 3.11 or newer is required (tomllib)" >&2; exit 1; }
exec python3 -m agensh.team_run "$@"
