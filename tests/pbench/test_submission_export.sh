#!/usr/bin/env bash
# T3: submission export path test (real git repo + real tar, no mock).
#
# ProgramBench's eval streams submission.tar.gz into the container via `tar -xzf - -C /workspace`
# (see ProgramBench/src/programbench/container.py copy_in_tar), then
# `chmod +x ./compile.sh && ./compile.sh` produces ./executable (see eval.py
# _compile_executable). So the **hard constraints** on the submission are:
#
#   1. The tar root is directly the workspace content -- compile.sh is at the root, must not be nested
#      inside a subdirectory (otherwise after extracting to /workspace it becomes
#      /workspace/<repo>/compile.sh, and eval cannot find it)
#   2. The output path must be <run>/<task_id>/submission.tar.gz
#   3. .git / temporary artifacts the agent may have stuffed into git should not pollute (.git is seeded by eval itself)
#
# This test uses a real git repo (simulating the agent team's Gitea repo HEAD after finishing work)
# and runs tools/pbench_submission.py export, asserting that the produced tar.gz satisfies the above constraints.
#
# Run:  bash tests/pbench/test_submission_export.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TOOL="$REPO_ROOT/tools/pbench_submission.py"
TASK="abishekvashok__cmatrix.5c082c6"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok()   { echo "  ok: $*"; }

[ -f "$TOOL" ] || fail "tool $TOOL missing"
ok "tool present: tools/pbench_submission.py"

WORK="$(mktemp -d /tmp/pbench-sub.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

# --- Build a realistic "finished" repo: source tree + compile.sh at root ----
SRC="$WORK/agent-repo"
mkdir -p "$SRC/src"
cat > "$SRC/compile.sh" <<'EOF'
#!/bin/bash
cc -o executable src/main.c
EOF
echo 'int main(){return 0;}' > "$SRC/src/main.c"
echo '# cmatrix clone' > "$SRC/README.md"
# a stray build artifact, gitignored (untracked) — must NOT ship
echo 'build/' > "$SRC/.gitignore"
mkdir -p "$SRC/build"; echo 'JUNK' > "$SRC/build/executable"
( cd "$SRC" && git init -q && git config user.email t@t && git config user.name t \
    && git add -A && git commit -qm "agent work" )
ok "fake finished repo built (git HEAD has compile.sh + src/; build/ gitignored)"

# --- Run the exporter against a local repo path (no Gitea needed here; the
#     smoke test covers the real Gitea clone). --from-dir takes a working tree.
OUT="$WORK/run-out"
python3 "$TOOL" export \
    --from-dir "$SRC" \
    --task "$TASK" \
    --out-dir "$OUT" \
    || fail "exporter exited non-zero"
ok "exporter ran"

# --- Assertion 1: path layout <run>/<task_id>/submission.tar.gz -------------
SUB="$OUT/$TASK/submission.tar.gz"
[ -s "$SUB" ] || fail "submission.tar.gz missing/empty at $SUB"
ok "layout OK: $TASK/submission.tar.gz ($(stat -c%s "$SUB") bytes)"

# --- Assertion 2: compile.sh sits at the TAR ROOT (./compile.sh) ------------
LIST="$(tar -tzf "$SUB")"
echo "$LIST" | grep -qxE '\./compile\.sh|compile\.sh' \
    || { echo "$LIST" >&2; fail "compile.sh not at tar root"; }
# must NOT be nested under a subdir like agent-repo/compile.sh
if echo "$LIST" | grep -qE '/compile\.sh$' && ! echo "$LIST" | grep -qxE '\./compile\.sh'; then
    echo "$LIST" >&2; fail "compile.sh is nested under a subdir (eval will not find it)"
fi
ok "compile.sh at tar root (extracts flat into /workspace)"

# --- Assertion 3: extract into a fresh /workspace-like dir, compile.sh runs --
WS="$WORK/workspace"; mkdir -p "$WS"
tar -xzf "$SUB" -C "$WS"
[ -f "$WS/compile.sh" ] || fail "after extract, /workspace/compile.sh missing"
[ -f "$WS/src/main.c" ] || fail "after extract, source tree missing"
ok "extracts flat: compile.sh + src/ land directly in workspace"

# --- Assertion 4: .git is NOT shipped (eval seeds its own deterministic git) -
echo "$LIST" | grep -qE '(^|/)\.git/' \
    && fail ".git/ leaked into submission (eval seeds its own)"
ok ".git/ excluded from submission"

# --- Assertion 5: gitignored build/ artifact excluded -----------------------
# The exporter ships the SOURCE the agent committed (git archive HEAD), not
# untracked/gitignored build junk. Anti-cheat: eval must compile from source,
# and a stale prebuilt ./executable must not slip through.
if [ -f "$WS/build/executable" ]; then
    fail "gitignored build/executable leaked into submission"
fi
ok "untracked/gitignored build/ artifacts excluded"

echo "PASS: tests/pbench/test_submission_export.sh"
