#!/usr/bin/env bash
# test_gate_feedback.sh — the merge gate must (a) tell a worker WHICH cases it
# broke, and (b) grade both sides on the SAME, CURRENT suite.
#
# WHY (a)
# A red gate used to produce only:
#     base 6949cca failures=885 / head 55a6a3b failures=903
#     REGRESSION: failures 885 -> 903. Something that passed on main now fails.
# The worker learned it broke 18 things and nothing about which 18. Sending the
# whole log is not an option: measured on s68a's real 1681-case suite at 1233
# failures it is 7.4 MB / 141,201 lines / ~1.9M tokens, ~10x a context window,
# and one single FAIL block is 25,658 lines. What CI uniquely knows is the SET
# DIFFERENCE -- it is the only thing that runs both sides -- and that is small.
#
# WHY (b)
# tests/ does NOT live on main. It lives on the `tests` branch, because a lead
# push to main invalidates every open PR under block_on_outdated_branch, and the
# lead authored 56% (s68a) to 81% (s68c) of all commits to main. Measured median
# gap between main commits: 42s (s68a) / 87s (s68c) -- shorter than a CI run, so
# any branch open longer than that is structurally doomed (s68c had 5 PRs die at
# 18-157 commits behind). With tests off main, "main moved" means "a worker
# merged src", which is exactly when a re-sync IS required.
#
# CI therefore overlays the current suite from origin/tests onto BOTH sides.
# That also kills the s68f defect where base ran 1185 cases and head ran 1075
# (11 of 67 runs had a >20-case gap) -- the two sides can no longer disagree
# about what the exam is.
#
# Uses a REAL git repository, so the workflow's real branch operations run.
#
# Usage: bash tests/pbench/test_gate_feedback.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BS="$ROOT/docker/bootstrap/bootstrap.sh"
rc=0
ok()   { echo "PASS $*"; }
fail() { echo "FAIL $*"; rc=1; }

WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t

# --- extract the workflow's run: block verbatim from bootstrap.sh -------------
python3 - "$BS" > "$WORK/gate.sh" <<'PY'
import sys, re
src = open(sys.argv[1]).read()
blocks = re.findall(r"content_b64=\$\(base64 -w0 <<'YML'\n(.*?)\nYML", src, re.S)
yml = next((b for b in blocks if re.search(r"^name: lead-tests\s*$", b, re.M)), None)
if yml is None: sys.exit("could not find the lead-tests YAML in bootstrap.sh")
m2 = re.search(r"^( +)run: \|\n(.*)", yml, re.S | re.M)
if not m2: sys.exit("could not find the run: block")
indent = len(m2.group(1)) + 2
# Stop at the first line that dedents out of the block. The workflow has more than one
# `run:` now (a second step posts the verdict), and taking (.*) to end-of-file would splice
# that step's YAML into the script and execute it as shell.
body = []
for l in m2.group(2).splitlines():
    if l.strip() and not l.startswith(" " * indent): break
    body.append(l[indent:] if len(l) > indent else "")
print("\n".join(body))
PY
grep -q 'failures_at' "$WORK/gate.sh" \
    || { echo "FAIL extracted the wrong workflow (no failures_at)"; exit 1; }

# --- a real repo: main carries src/, the tests branch carries the suite -------
# run.sh emits one FAIL per name in src/broken.txt, so a commit's failing set is
# whatever that file says -- which lets a fixture state any base/head shape.
mk_suite() {  # $1=dest dir — real case files, so the scoped head run is exercised
  # One directory per goal: a case is <goal>/<task>, so a worker assigned goal `core`
  # finds every case it owns in tests/cases/core/ without parsing filenames.
  for c in core/a core/shared1 core/shared2 core/BROKE1 parse/stale1 parse/stale2 parse/d orphan/none; do
    mkdir -p "$1/tests/cases/$(dirname "$c")"
    printf '#!/bin/sh\necho %s\n' "$c" > "$1/tests/cases/$c.sh"
    printf '%s\n' "$c" > "$1/tests/cases/$c.expected"
  done
  cat > "$1/tests/run.sh" <<'EOF'
#!/bin/sh
# A case FAILS iff its name is listed in src/broken.txt. Only cases still present
# in tests/cases are run, so CI's pruning to a keep-list is observable here.
n=0; ran=0
for f in $(find tests/cases -name '*.sh' | sort); do
  [ -e "$f" ] || continue
  c=${f#tests/cases/}; c=${c%.sh}; ran=$((ran+1))
  if grep -qxF "$c" src/broken.txt 2>/dev/null; then
    echo "FAIL $c"; echo "  CMD: ./executable --$c"
    echo "  --- expected ---"; echo "want-$c"
    echo "  --- actual ---";   echo "got-$c"
    n=$((n+1))
  fi
done
echo "ran=$ran failed=$n"
EOF
}

ORIGIN="$WORK/origin.git"
git init -q --bare "$ORIGIN"
SEED="$WORK/seed"; mkdir -p "$SEED/src"; cd "$SEED"
git init -q -b main .; git remote add origin "$ORIGIN"
printf 'core/a\n' > src/broken.txt; echo '#!/bin/sh' > compile.sh
# src/ci-list.txt records the goals in CI's range; a worker appends its own in the PR that
# lands the goal. Seeded at repo init, so empty is a valid state.
printf '# one goal per line\n' > src/ci-list.txt
git add -A; git commit -qm seed; git push -q origin main
# the suite lives ONLY on the tests branch
git checkout -q --orphan tests; git rm -qrf .; mk_suite "$SEED"
git add -A; git commit -qm "suite"; git push -q origin tests
# base: main advances (a worker merged). head: a branch off it.
git checkout -q main
printf 'core/shared1\ncore/shared2\nparse/stale1\nparse/stale2\nparse/d\n' > src/broken.txt
git add -A; git commit -qm "base"; git push -q origin main
BASE_SHA=$(git rev-parse HEAD)
git checkout -qb feat
printf 'core/shared1\ncore/shared2\ncore/BROKE1\nparse/d\n' > src/broken.txt
printf "# one goal per line\nparse\n" > src/ci-list.txt   # this PR lands goal `parse`
git add -A; git commit -qm "head"; git push -q origin feat
HEAD_SHA=$(git rev-parse HEAD)

# The gate now requires a readable sub-issue naming real cases, so every run needs
# one. #7 names `parse/d` (which fails on both sides) and a case that does not exist.
mkdir -p "$WORK/api/issues"
cat > "$WORK/api/issues/7" <<'EOF'
{"number":7,"title":"[goal] parse","body":"Goal: `parse`. Its cases define it done."}
EOF

run_gate() {  # -> sets OUT / GATE_RC
    rm -rf "$WORK/run"; mkdir -p "$WORK/run"; cd "$WORK/run"
    OUT=$(REPO_URL="$ORIGIN" BASE_SHA="$1" HEAD_SHA="$2" \
          BODY="Refs #7" API_BASE="file://$WORK/api" bash "$WORK/gate.sh" 2>&1)
    GATE_RC=$?
}

# --- 1. a case that regressed must block, and be named ------------------------
run_gate "$BASE_SHA" "$HEAD_SHA"
[ "$GATE_RC" -ne 0 ] \
    && ok "a case that passed on main and fails on the branch blocks the merge" \
    || fail "gate PASSED a real regression (totals fell 4->3; only the SET shows it)"
printf '%s\n' "$OUT" | grep -qw 'core/BROKE1' \
    && ok "the regressed case is named in the log" \
    || fail "log never names core/BROKE1 — worker cannot know what it broke"
printf '%s\n' "$OUT" | grep -qE '^ +shared[12]$' \
    && fail "log lists cases that fail on main too — noise, not a regression" \
    || ok "cases already failing on main are not reported as regressions"
printf '%s\n' "$OUT" | grep -qE '^ +stale[12]$' \
    && fail "log lists cases this branch FIXED" \
    || ok "a case the branch fixed is not reported as a regression"
printf '%s\n' "$OUT" | grep -q 'want-core/BROKE1' \
    && ok "the failing case's expected/actual block is included" \
    || fail "only the name is given — worker must re-derive the diff by hand"
n=$(printf '%s\n' "$OUT" | wc -l)
[ "$n" -lt 500 ] \
    && ok "gate output is bounded ($n lines; a full log is 141,201)" \
    || fail "gate output is $n lines — unbounded logs cannot reach an agent"
grep -q 'more' "$WORK/gate.sh" \
    && ok "the workflow announces how much it truncated" \
    || fail "truncation is silent — '10 shown' would read as '10 total'"

# --- 2. the suite comes from the tests branch, for BOTH sides -----------------
# The head branch carries its own STALE tests/ that reports one failure and no
# FAIL lines at all. If CI honoured it, the gate would read failed=1 for head
# and merge the regression. It must be overlaid away.
cd "$SEED"; git checkout -q feat
mkdir -p tests; printf '#!/bin/sh\necho "ran=1 failed=1"\n' > tests/run.sh
git add -A; git commit -qm "stale tests/ on the branch"; git push -q origin feat
STALE_HEAD=$(git rev-parse HEAD)
run_gate "$BASE_SHA" "$STALE_HEAD"
[ "$GATE_RC" -ne 0 ] \
    && ok "a stale tests/ on the branch is overlaid away, not honoured" \
    || fail "head's own tests/ was used — a branch can grade itself on an easier exam"
printf '%s\n' "$OUT" | grep -qw 'core/BROKE1' \
    && ok "the regression is still found with the current suite applied" \
    || fail "overlay did not take effect"

# --- 3. a lead push to the tests branch must NOT need a re-sync ---------------
# The whole point of moving tests off main: the suite can grow while a PR is
# open, and that PR is still measurable without touching the branch.
cd "$SEED"; git checkout -q tests
printf '#!/bin/sh\necho parse/late\n' > tests/cases/parse/late.sh
printf 'parse/late\n' > tests/cases/parse/late.expected
git add -A; git commit -qm "lead grows the suite"; git push -q origin tests
run_gate "$BASE_SHA" "$HEAD_SHA"
printf '%s\n' "$OUT" | grep -qE 'of 9 in the suite' \
    && ok "the newest suite is used without the PR being touched" \
    || fail "a lead push to the tests branch did not reach the gate"
[ "$GATE_RC" -ne 0 ] \
    && ok "verdict still correct after the suite grew under an open PR" \
    || fail "growing the suite lost the regression"

# --- 4. no tests branch yet must PASS, never deadlock ------------------------
BARE2="$WORK/o2.git"; git init -q --bare "$BARE2"
cd "$SEED"; git checkout -q main; git push -q "$BARE2" main
rm -rf "$WORK/run"; mkdir -p "$WORK/run"; cd "$WORK/run"
O4=$(REPO_URL="$BARE2" BASE_SHA="$BASE_SHA" HEAD_SHA="$BASE_SHA" bash "$WORK/gate.sh" 2>&1); R4=$?
[ "$R4" -eq 0 ] \
    && ok "no tests branch yet → PASSES (a lead cannot deadlock its team)" \
    || fail "gate blocks before the lead has published a suite: $O4"

# --- 4. SCOPE: head runs only (assigned cases + what already passes on main) ---
# Running all N cases on the head is mostly noise: cases nobody has implemented fail on
# both sides and can never be a regression. The head run is therefore restricted to the
# union of (a) the cases this PR's sub-issue names -- read from the issue body via the
# unauthenticated API -- and (b) the set passing on main, i.e. what previous merged PRs
# established. A case outside that union is not run at all.
cd "$SEED"; git checkout -q feat 2>/dev/null || git checkout -q -b feat
run_gate_scoped() {
    rm -rf "$WORK/run"; mkdir -p "$WORK/run"; cd "$WORK/run"
    OUT=$(REPO_URL="$ORIGIN" BASE_SHA="$1" HEAD_SHA="$2" \
          BODY="Refs #7" API_BASE="file://$WORK/api" bash "$WORK/gate.sh" 2>&1)
    GATE_RC=$?
}
run_gate_scoped "$BASE_SHA" "$HEAD_SHA"
printf '%s\n' "$OUT" | grep -qE 'scope: [0-9]+ case' \
    && ok "gate reports the reduced scope it ran on the head" \
    || fail "gate does not report a reduced head scope"
# parse/stale1/parse/stale2 fail on base, are not assigned -> must not be run on the head at all
printf '%s\n' "$OUT" | grep -qE '^ +stale[12]$' \
    && fail "a case failing on main and not assigned was still run/reported" \
    || ok "cases failing on main and unassigned are excluded from the head run"
# core/BROKE1 passes on main -> it is in P -> still caught
printf '%s\n' "$OUT" | grep -qw 'core/BROKE1' \
    && ok "a regression in the passing set is still caught under the reduced scope" \
    || fail "reducing the scope lost a real regression"
[ "$GATE_RC" -ne 0 ] \
    && ok "regression still blocks under the reduced scope" \
    || fail "regression no longer blocks"

# --- 4b. the ASSIGNED half: run them, report them, do not block on them --------
# `d` is named by sub-issue #7 and fails on BOTH sides. It can never be a regression,
# so the scope rule would drop it -- but it is the worker's own goal, so it must still
# be run and reported. And it must NOT block: gating on assigned cases is the all-green
# gate that deadlocked 17 of 20 teams in 6.5.
run_gate_scoped "$BASE_SHA" "$HEAD_SHA"
printf '%s\n' "$OUT" | grep -q "sub-issue's cases still failing" \
    && ok "assigned cases that still fail are reported" \
    || fail "assigned failures are invisible — worker cannot see its goal is unfinished"
printf '%s\n' "$OUT" | grep -qE '^ +parse/d$' \
    && ok "the assigned-but-still-red case is named" \
    || fail "assigned case 'parse/d' was dropped by the scope rule"
printf '%s\n' "$OUT" | grep -q 'do NOT block' \
    && ok "worker is told assigned failures do not block the merge" \
    || fail "nothing says assigned failures are non-blocking"

# --- 4c. learning the goal range must NEVER block ------------------------------
# The range now comes from `src/ci-list.txt` at the head commit, so there is nothing to
# retrieve and nothing that can fail to be retrieved. Every way of ending up with no goals
# has to PASS: the base side runs the FULL suite, so `passing` is complete and the verdict
# `fails.head n passing` does not depend on the goal list at all -- it only ever ADDS to what
# the head runs. Blocking on it would gate a merge on something that cannot change the merge
# verdict, and (measured, 0.5h smoke) the blocked worker could not find out.
#
# CLEAN is base itself: no regression is possible, so a block here could ONLY come from the
# goal list. Without that, a fixture with a real regression makes these pass for the wrong
# reason.
cd "$SEED"; git checkout -q -B clean "$BASE_SHA"; git push -q -f origin clean
CLEAN=$(git rev-parse HEAD)
run_head() {   # $1 = head sha
    rm -rf "$WORK/run"; mkdir -p "$WORK/run"; cd "$WORK/run"
    OUT=$(REPO_URL="$ORIGIN" BASE_SHA="$BASE_SHA" HEAD_SHA="$1" bash "$WORK/gate.sh" 2>&1)
    GATE_RC=$?
}
run_head "$CLEAN"
[ "$GATE_RC" -eq 0 ] \
    && ok "a head listing no goal passes (an empty range is valid)" \
    || fail "a PR that lists no goal was blocked: $OUT"
# the file removed entirely
cd "$SEED"; git checkout -q -B nolist "$BASE_SHA"; rm -f src/ci-list.txt
git add -A; git commit -qm "no ci-list"; git push -q -f origin nolist
run_head "$(git rev-parse HEAD)"
[ "$GATE_RC" -eq 0 ] \
    && ok "a head with no src/ci-list.txt at all passes" \
    || fail "a missing goal list blocked the merge: $OUT"
# ...and with no goal information the verdict is still sound
cd "$SEED"; git checkout -q -B nolistbad "$HEAD_SHA"; rm -f src/ci-list.txt
git add -A; git commit -qm "regression, no ci-list"; git push -q -f origin nolistbad
run_head "$(git rev-parse HEAD)"
[ "$GATE_RC" -ne 0 ] \
    && ok "a regression still blocks with no goal information at all" \
    || fail "deleting src/ci-list.txt suppressed a real regression — the range can hide bugs"
printf '%s\n' "$OUT" | grep -qw 'core/BROKE1' \
    && ok "the regression is still named without any goal information" \
    || fail "regression unnamed when the goal list is empty"
# a goal that owns no cases is reported, not blocked
cd "$SEED"; git checkout -q -B typo "$HEAD_SHA"
printf '# one goal per line\nparse\nparser\n' > src/ci-list.txt
git add -A; git commit -qm "goal list with a typo"; git push -q -f origin typo
run_head "$(git rev-parse HEAD)"
printf '%s\n' "$OUT" | grep -qi 'has no cases' \
    && ok "a goal owning no cases is named, not silently empty" \
    || fail "a misspelled goal selects nothing and reads as 'my goal is green'"
printf '%s\n' "$OUT" | grep -qE '^ +parse/d$' \
    && ok "a valid goal still expands when listed beside a bad one" \
    || fail "one unmatched goal suppressed a valid one"
# the PR body is no longer read at all
# API_BASE is legitimate now -- it POSTs the verdict comment. What must not come back is
# RETRIEVAL: reading the PR body, or GETting an issue to decide the scope.
grep -qE '\$\{?BODY|issue\.json|curl [^|]*/issues/\$ISSUE' "$WORK/gate.sh" \
    && fail "the gate reads the PR body or fetches an issue to decide scope" \
    || ok "scope comes from the repo, not from anything that can fail to be retrieved"

# --- 5. the count comparison must survive as a backstop -----------------------
grep -qE '"\$HEAD" -gt "\$BASE"' "$WORK/gate.sh" \
    && ok "count comparison retained as a backstop when no FAIL names are emitted" \
    || fail "count check removed — a run.sh without FAIL lines would gate nothing"


# --- 6. the verdict must reach the worker ------------------------------------
# Gitea raises no notification for a finished Actions run, and the router's only gitea source
# is /api/v1/notifications -- so no [event] can ever announce a check. In the 0.5h smoke a
# blocked PR sat for the run's last ~15 minutes because its owner never learned. A PR comment
# DOES notify its participants, so it is the one push path back to the author.
grep -q 'issues/.*/comments' "$WORK/gate.sh" 2>/dev/null || GATE_HAS_COMMENT=no
python3 - "$BS" <<'PYW' > "$WORK/wf.yml"
import sys, re
src=open(sys.argv[1]).read()
b=re.findall(r"content_b64=\$\(base64 -w0 <<'YML'\n(.*?)\nYML", src, re.S)
print(next(x for x in b if re.search(r"^name: lead-tests\s*$", x, re.M)))
PYW
grep -q 'issues/\$PR_NUMBER/comments' "$WORK/wf.yml" \
    && ok "CI posts its verdict as a PR comment — the only signal that reaches the author" \
    || fail "the verdict exists only in a job log nobody is told about"
# It must be ONE step. act_runner planned only workflow/0.sh in the s6v smoke and dropped a
# second step silently -- no error, no `evaluating expression 'always()'` -- so all four runs
# produced a verdict nobody received. A subshell around the body lets its `exit N` return a
# code without ending the job before the post.
[ "$(grep -c '^ *- name:' "$WORK/wf.yml")" = 1 ] \
    && ok "the workflow is a single step (a second one is silently dropped)" \
    || fail "a second step was added — act_runner does not run it"
grep -q 'exit \$rc' "$WORK/wf.yml" \
    && ok "the gate's own exit code survives the post" \
    || fail "posting the comment would mask the verdict"
grep -q 'head -c' "$WORK/wf.yml" \
    && ok "the comment body is size-bounded" \
    || fail "an unbounded verdict would exceed what a comment can carry (141k lines measured)"
grep -qE '\|\| *(true|echo)' "$WORK/wf.yml" \
    && ok "a failed comment cannot change the gate's verdict" \
    || fail "a comment failure would mark a passing PR red"

exit $rc
