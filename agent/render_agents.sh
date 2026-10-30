#!/bin/bash
# Render a worker's AGENTS.md: the core collaboration template with the task
# pack's fragments substituted. Identity variables come from the environment.
# Usage: render_agents.sh CORE_TEMPLATE TASK_PROMPT_DIR > AGENTS.md
set -euo pipefail

core="${1:?usage: render_agents.sh CORE_TEMPLATE TASK_PROMPT_DIR}"
task_dir="${2:?usage: render_agents.sh CORE_TEMPLATE TASK_PROMPT_DIR}"

# A missing fragment renders empty; $(...) drops each fragment's trailing newlines.
fragment() {
    if [ -r "$task_dir/$1.txt" ]; then cat "$task_dir/$1.txt"; fi
}
TASK_OBJECTIVE="$(fragment objective)"
TASK_FOCUS="$(fragment focus)"
TASK_WORK_CYCLE="$(fragment work_cycle)"
TASK_DELIVERY="$(fragment delivery)"
export TASK_OBJECTIVE TASK_FOCUS TASK_WORK_CYCLE TASK_DELIVERY

# Unrestricted, as before: identity and team variables are also expanded here.
# Fragment text is inserted verbatim; envsubst does not expand it again.
envsubst < "$core"
