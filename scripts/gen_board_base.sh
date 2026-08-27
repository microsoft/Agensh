#!/usr/bin/env bash
# Generate roles/base.board.md = base.md with the board protocol INLINED.
#
# Why not just use ${BOARD_PREAMBLE}: entrypoint.sh is baked into
# omcgitea-hermes-agent:v48-cleanroom, and that image predates
# resolve_board_preamble(). The repo's entrypoint has the function, the image
# does not, so envsubst expands ${BOARD_PREAMBLE} to the empty string and the
# board protocol never reaches an agent. The image is pinned deliberately
# (sweep_5 reproducibility) and pbench_run_1team.sh refuses to rebuild it, so
# we inline the text at template-generation time instead.
#
# ${BOARD_IDS} inside the preamble survives into the generated file and IS
# expanded normally, because envsubst now sees it directly rather than as text
# it just substituted in.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PRE="$ROOT/docker/hermes-agent/board-preamble.md"
[ -f "$PRE" ] || { echo "missing $PRE" >&2; exit 1; }
for tmpl in templates-claude-1team templates-claude-4team templates-claude-delm; do
    src="$ROOT/docker/hermes-agent/$tmpl/roles/base.md"
    dst_probe="$ROOT/docker/hermes-agent/$tmpl/roles/base.board.md"
    if [ ! -f "$src" ]; then
        # templates-claude-4team has a base.board.md and no base.md, so this loop
        # used to `continue` past it in silence -- while two compose files
        # (pbench-4team-board, pbench-4team-1board) mount it. A generated file
        # with no source can never be regenerated and drifts from
        # board-preamble.md forever. Say so instead of skipping quietly.
        if [ -f "$dst_probe" ]; then
            echo "  WARN: $tmpl/roles/base.board.md exists but $tmpl/roles/base.md does not" >&2
            echo "        -> it is hand-maintained and will NOT track board-preamble.md" >&2
        fi
        continue
    fi
    dst="$ROOT/docker/hermes-agent/$tmpl/roles/base.board.md"
    if grep -q '${BOARD_PREAMBLE}' "$src"; then
        python3 - "$src" "$PRE" "$dst" <<'PY'
import sys
src, pre, dst = sys.argv[1:4]
body = open(src).read().replace("${BOARD_PREAMBLE}", open(pre).read().rstrip("\n"))
open(dst, "w").write(body)
PY
    else
        # No marker in this template — append the protocol at the end.
        { cat "$src"; printf '\n\n'; cat "$PRE"; } > "$dst"
    fi
    echo "  wrote $tmpl/roles/base.board.md ($(wc -l < "$dst") lines, board protocol inlined)"
done
