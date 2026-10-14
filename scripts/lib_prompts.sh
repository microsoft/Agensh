# Prompt rendering for the launchers. Source after ROOT is set.
#
# The prompts the launchers send are files under prompts/. render_prompt FILE
# NAME=value... prints FILE with each listed ${NAME} replaced by its value. Any
# other $ in FILE stays as written, and a value is inserted as is, never expanded
# again. Each prompt file ends with one newline, which $(render_prompt ...) drops,
# as $(cat FILE) does.
PROMPTS_DIR="$ROOT/prompts"

render_prompt() {  # FILE [NAME=value...]
    local file="$1" names="" kv
    shift
    [ -s "$file" ] || { echo "render_prompt: $file is missing" >&2; return 1; }
    for kv in "$@"; do names+="\${${kv%%=*}}"; done
    env "$@" envsubst "$names" < "$file"
}
