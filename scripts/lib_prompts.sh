#!/usr/bin/env bash
# Prompt rendering shared by the runner and tools/render_snapshot.py.
# Core messages live in prompts/; task messages in the task pack's prompts/.

# render_prompt FILE [NAME=VALUE...]
# Substitute only the named variables so shell examples and unrelated
# placeholders in the template stay literal.
render_prompt() {
    local file="$1" names="" kv
    shift
    [ -s "$file" ] || { echo "render_prompt: $file is missing" >&2; return 1; }
    for kv in "$@"; do names+="\${${kv%%=*}}"; done
    env "$@" envsubst "$names" < "$file"
}
