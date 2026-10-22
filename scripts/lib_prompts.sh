# Render runtime prompt templates, substituting only explicitly supplied names.
# Source this library after setting the repository ROOT.
PROMPTS_DIR="$ROOT/prompts"

render_prompt() {
    local file="$1" names="" kv
    shift
    [ -s "$file" ] || { echo "render_prompt: $file is missing" >&2; return 1; }
    # Restrict envsubst so shell examples and unrelated placeholders stay literal.
    for kv in "$@"; do names+="\${${kv%%=*}}"; done
    env "$@" envsubst "$names" < "$file"
}
