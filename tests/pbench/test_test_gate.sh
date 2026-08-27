#!/usr/bin/env bash
# test_test_gate.sh — the sweep 6.5 CI test gate must be wired end to end.
#
# WHY
# Sweep 6.4 measured that the human review gate cost more than it caught: the
# lead spent 26.3% of its budget reviewing and 19.4% polling gitea, PR
# throughput fell 34% and median open->merge went 4.0 -> 10.7 minutes, for no
# score gain. 6.5 replaces it with a gate that executes: the lead publishes a
# suite in tests/, CI runs it on every PR, and a green worker self-merges.
#
# Four things have to be true for that to be real rather than advisory, and all
# four are easy to get silently wrong:
#
#  1. CI must run in the TASK's image. The runner shipped
#     "ubuntu-latest:docker://node:20-bookworm", which has no go/cargo/java — so
#     roughly 8 of the 20 tasks could never have built in CI.
#  2. The job must be able to fetch the repo. act_runner creates a network per
#     job by default, where gitea:3000 does not resolve; that same auto-created
#     bridge is a NATed route to the internet, i.e. a hole through the offline
#     boundary the benchmark depends on. Pinning container.network fixes both.
#  3. Builds must run concurrently. act_runner defaults to capacity 1, which
#     would serialise four workers behind one another — reproducing, in CI, the
#     single-threaded bottleneck we just removed from the lead.
#  4. When there is no review, every review-derived blocker has to come off, or
#     merges stall forever waiting on an approval nobody will give.
#
# lead-tests is deliberately NOT required by default: a required status check
# whose job never runs sits at "pending", and pending blocks merge — so a
# misconfigured runner would deadlock every PR in a 20-task sweep instead of
# failing loudly. Prove it green on one task, then set PBENCH_REQUIRE_LEAD_TESTS=1.
#
# Usage: bash tests/pbench/test_test_gate.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BS="$ROOT/docker/bootstrap/bootstrap.sh"
GEN="$ROOT/tools/gen-compose-prod.py"
PROD="$ROOT/docker/docker-compose.prod.yml"
TMPL_LEAD="$ROOT/docker/hermes-agent/templates-claude-1team/roles/director_lead"
TMPL_CODER="$ROOT/docker/hermes-agent/templates-claude-1team/roles/coder"
# The prompt an agent actually sees is base.board.md with its role's fragments
# spliced in, so assert against THAT rather than a single file. The mechanics
# below have moved between files more than once (run.sh contract: workflow.md ->
# base.md); a per-file grep then reports "the rule is gone" when it merely moved.
RENDER_LEAD="$(mktemp)"; RENDER_CODER="$(mktemp)"
trap 'rm -f "$RENDER_LEAD" "$RENDER_CODER"' EXIT
cat "$TMPL_LEAD/../base.board.md" "$TMPL_LEAD"/*.md  > "$RENDER_LEAD"
cat "$TMPL_LEAD/../base.board.md" "$TMPL_CODER"/*.md > "$RENDER_CODER"
rc=0
ok()   { echo "PASS $*"; }
fail() { echo "FAIL $*"; rc=1; }

# --- 1. CI runs in the task's own image -----------------------------------
for f in "$GEN" "$PROD"; do
    n=$(basename "$f")
    grep -q 'GITEA_RUNNER_LABELS: "ubuntu-latest:docker://\${AGENT_IMAGE' "$f" \
        && ok "$n: CI job image follows AGENT_IMAGE (grader's toolchain)" \
        || fail "$n: runner still pinned to a generic image — Go/Rust/Java tasks cannot build in CI"
done

# --- 2. job container joins the stack network -----------------------------
for f in "$GEN" "$PROD"; do
    n=$(basename "$f")
    grep -q 'ACT_JOB_NETWORK' "$f" && grep -q 'network: "\$\$ACT_JOB_NETWORK"' "$f" \
        && ok "$n: job network pinned (gitea reachable, no auto-created NAT bridge)" \
        || fail "$n: job network not pinned — job cannot clone, and gets internet egress"
done

# --- 3. concurrency ---------------------------------------------------------
for f in "$GEN" "$PROD"; do
    n=$(basename "$f")
    grep -q 'capacity: \$\$ACT_CAPACITY' "$f" \
        && ok "$n: runner capacity is configurable (default >1)" \
        || fail "$n: capacity not set — builds serialise behind one another"
    grep -q 'ACT_CAPACITY:-[2-9]' "$f" \
        && ok "$n: default capacity is greater than 1" \
        || fail "$n: default capacity is 1 or unset"
done

# --- 4. the workflow itself -------------------------------------------------
grep -q 'ensure_lead_tests_workflow' "$BS" \
    && ok "bootstrap installs the lead-tests workflow" \
    || fail "bootstrap has no lead-tests workflow"
grep -q 'name: lead-tests' "$BS" && grep -qE '^\s+test:' "$BS" \
    && ok "workflow/job names yield context 'lead-tests / test (pull_request)'" \
    || fail "workflow or job name will not produce the expected status context"
# The gate must be NO-REGRESSION, not "all green". Gating on a green suite means
# the first PR has to implement the whole program, because the suite covers the
# whole program while a PR covers one worker's area. That deadlocked 17 of 20
# teams in sweep 6.5; six shipped a repo containing tests/ and no source at all.
# chroma opened one PR and watched the check fail 31 times over 4h11m while its
# lead grew the suite 15 -> 587 cases, moving the bar further away on every push.
# Every test in this project is the lead's. CI must NOT carry its own runner:
# when it did, the lead's run.sh was parallel and the CI copy was serial, so the
# gate ran ~20x slower than the identical suite locally and degraded from 3s to
# 200s+ within a single run as the suite grew.
grep -q 'bash tests/run.sh' "$BS" \
    && ok "CI runs the lead's tests/run.sh" \
    || fail "CI does not invoke the lead's run.sh"
grep -q 'for c in tests/cases' "$BS" \
    && fail "CI still implements its own case loop — two runners will drift again" \
    || ok "CI implements no tests of its own"
grep -q 'HEAD" -gt "\$BASE' "$BS" \
    && ok "gate is no-regression: blocks only when failures INCREASE" \
    || fail "gate is not comparing head failures against base"
grep -q "fail(ed|ures?)\[=: \]" "$BS" \
    && ok "summary parser prefers the explicit failed=N form" \
    || fail "parser may match 'N failed' first and misread ran=951 failed=334 as 951"
grep -q 'could not read a failure count' "$BS" \
    && ok "an unparseable summary PASSES (a lead's format cannot deadlock the team)" \
    || fail "unparseable run.sh output could block every merge"
grep -q 'no tests/run.sh yet' "$BS" \
    && ok "an absent suite passes (no deadlock before the lead publishes)" \
    || fail "a missing run.sh would fail every early PR"
grep -qE '^\s*-?\s*uses:\s*actions/checkout' "$BS" \
    && fail "workflow uses actions/checkout — unreachable, DEFAULT_ACTIONS_URL is github" \
    || ok "no JS action used (checkout is a plain git clone)"

tr -s '[:space:]' ' ' < "$RENDER_LEAD" | grep -qE 'xargs|-P [0-9]|nproc' \
    && fail "the suite fans out again — 6.6 took the host down at -P \$(nproc), nproc=256" \
    || ok "no fan-out at all, so no ceiling to get wrong"

# --- the WORKER's parallelism must be bounded too -------------------------------
# The lead's suite is bounded by JOBS=8 from the env (above). Everything the WORKER runs is
# not: it writes compile.sh and its own probe loops, and nothing caps either. 6.6 took the
# host down with `xargs -P $(nproc)` in a test loop; 6.11 shipped `make -j$(nproc)` in
# compile.sh. `nproc` reports the HOST's 256 from inside a container even under --cpus=4,
# because it reads sched_getaffinity and not the cgroup quota, and CI runs the job with
# --cpus=4 --pids-limit=512 (ACT_JOB_LIMITS).
#
# The prompt states the ceiling as a plain number and does NOT explain nproc -- an operator
# decision, kept short deliberately. So assert the NUMBER is present and do not require the
# reasoning; the hard bound is ACT_JOB_LIMITS regardless.
tr -s '[:space:]' ' ' < "$RENDER_CODER" | grep -qiE '8 workers|more than 8|at most 8|8 or fewer|8 in parallel' \
    && ok "the worker is given a parallelism ceiling of 8" \
    || fail "nothing caps the worker's fan-out — a build or probe loop can go 256 wide in CI"
tr -s '[:space:]' ' ' < "$RENDER_LEAD" | grep -qiE 'exits with an error or is killed|timeout is a FAIL' \
    && ok "a timeout is a FAIL and counts in failed= (not silently dropped)" \
    || fail "a timed-out case may not be counted — CI would read a low failure count and merge a regression"
tr -s '[:space:]' ' ' < "$RENDER_LEAD" | grep -qiE 'a fake pass is extremely dangerous|never ran (leaves no|counts as FAIL)' \
    && ok "counting is fail-SAFE: a case that never ran counts as a failure" \
    || fail "fail-safe rationale gone — a run.sh that runs nothing would report failed=0 and merge everything"
for f in "$GEN" "$PROD"; do
    n=$(basename "$f")
    grep -q 'pids-limit' "$f" \
        && ok "$n: CI job containers have a PID ceiling (fork-storm guard)" \
        || fail "$n: no --pids-limit on job containers"
    grep -q 'options: "\$\$ACT_JOB_LIMITS"' "$f" \
        && ok "$n: the limits are actually passed to act_runner" \
        || fail "$n: ACT_JOB_LIMITS defined but never applied"
    grep -qE 'ACT_CAPACITY:-[12]\}' "$f" \
        && ok "$n: per-stack CI capacity <= 2 (x18 stacks)" \
        || fail "$n: capacity too high for a full sweep"
done

# --- 4c. THE SUITE LIVES ON ITS OWN BRANCH ---------------------------------
# Under block_on_outdated_branch every commit to main invalidates every open PR.
# The lead authored 56% (s68a) / 81% (s68c) of all commits to main, all of them
# tests/ -- commits that cannot break a worker's build. Measured median gap
# between main commits: 42s / 87s, shorter than a CI run, so no branch could stay
# mergeable: s68c lost 5 PRs at 18-157 commits behind and its slowest worker
# merged 1 PR in 12 hours. With tests/ on its own branch, "main moved" means "a
# worker merged src/", which is exactly when a re-sync IS required. Overlaying
# that branch onto BOTH sides also removes the s68f defect where base ran 1185
# cases and head ran 1075 (11 of 67 runs had a >20-case gap).
grep -q 'ensure_tests_branch' "$BS" \
    && ok "bootstrap creates the tests branch" \
    || fail "no tests branch — the lead would publish to main and invalidate every PR"
grep -q 'git archive origin/tests tests' "$BS" \
    && ok "CI extracts the suite from the tests branch" \
    || fail "CI does not read the tests branch — the suite would be whatever the PR carries"
grep -q 'cp -r /tmp/suite/tests tests' "$BS" \
    && ok "the same suite is overlaid on BOTH base and head" \
    || fail "base and head can be graded on different suites again"
grep -q 'no tests branch yet' "$BS" \
    && ok "an absent tests branch PASSES (a lead cannot deadlock its team)" \
    || fail "gate would block before the lead has published anything"
tr -s '[:space:]' ' ' < "$RENDER_LEAD" | grep -qiE 'push (them |it )?to the .tests. branch|push origin tests' \
    && ok "lead is told to push the suite to the tests branch" \
    || fail "lead still publishes tests/ to main"
# The prompt gives no fetch command -- the worker picks one. What it must still carry is
# where the cases are and that they never get committed: `git checkout origin/tests -- tests`
# STAGES them (verified: status shows `A`), and the next `git add -A` would put the suite on
# main, which every other fragment forbids.
tr -s '[:space:]' ' ' < "$RENDER_CODER" | grep -q 'tests/cases/<goal>/' \
    && ok "the worker is told where its goal's cases are" \
    || fail "nothing says where a goal's cases live"
tr -s '[:space:]' ' ' < "$RENDER_CODER" | grep -qi 'never commit them' \
    && ok "the worker is told not to commit the suite it fetched" \
    || fail "a fetched suite can be swept onto main by git add -A"

# --- 4d. DELIVERY CADENCE AND LIVENESS -------------------------------------
# With review deleted, an unpushed worker is invisible: no reviewer, no lead
# merge, no liveness signal. Measured in 6.8 -- s68b worker3 made 78 edits to one
# file over 129 minutes, ran 55 git commands (clone, fetch, rebase, branch) and
# never once ran `git add`; s68a workers 1 and 2 pushed 3 times each and then
# burned 924 and 833 bash calls delivering nothing, with 9 and 7 issues assigned.
# They were not looping (91-92% of their commands were unique) and not idle --
# 42-48% of their calls were running the reference or reading files. They were
# building toward a private "ready" bar with nothing forcing delivery. The
# workers who finished pushed every 3-4 minutes; the ones that failed drifted to
# a 12-27 minute median and never recovered. 20min is above the p90 of every healthy
# worker (13min for the two that pushed 28-32 times) so it fires on stalls, not on work,
# and it matches the lead's own 'who has gone quiet' interval.
# Syncing a stale branch pulls another worker's src/ in and fires `synchronize`, so a new CI
# run starts. That run is the ONLY check of this worker's code against the other's -- an
# interface change on main (all of s68a's 7 conflicted PRs were on one src/main.c) breaks the
# branch and nothing else would catch it. The prompt used to say "sync, then merge", i.e. skip
# it; gitea blocks that today only because the required check goes pending on the new commit.
tr -s '[:space:]' ' ' < "$RENDER_CODER" | grep -qiE '(starts|wait for) (a |the )?fresh CI run|check restarts itself' \
    && ok "worker waits for CI after syncing a stale branch" \
    || fail "worker is told to merge straight after sync — skips the only cross-worker check"
# The lead's `git for-each-ref` liveness sweep went with workflow.md when the prompts were
# cut to how-pbench-works / what-each-role-does / how-to-use-tools. What remains is the
# worker-side rule (push at least every 20 min) -- nothing now tells the LEAD to look for a
# worker that has gone quiet. In 6.8 two of four workers went dark for hours and nothing
# noticed; if that recurs, this is the thing to restore.

# --- 4e. THE FRAGMENTS MUST DESCRIBE THE GATE WE ACTUALLY RUN ---------------
# The gate became set-based (it names the cases that regressed) and the suite moved
# to the `tests` branch. Three separate fragments were still describing the old
# count-based, tests-on-main system afterwards -- coder/one_liner ("CI counts how
# many cases pass"), coder/donts ("red means your branch passes FEWER cases") and
# coder/dos ("rebase often ... the lead pushes new cases"). None of that is caught
# by testing the gate itself: an agent reads the prompt, not bootstrap.sh. A worker
# told red means "fewer cases" will see red with an IMPROVED total and conclude the
# check is broken -- and the same bullet tells it not to route around a failing
# check. The rebase advice also contradicted workflow point 8, which says to merge.
for f in one_liner donts dos workflow failure_modes; do
    grep -qiE 'CI counts|FEWER cases' "$TMPL_CODER/$f.md" \
        && fail "coder/$f.md still describes a COUNT-based gate" \
        || ok "coder/$f.md does not describe the gate as counting cases"
done
grep -qE 'git rebase origin/main' "$TMPL_CODER/dos.md" "$TMPL_CODER/failure_modes.md" "$RENDER_CODER" \
    && fail "worker is told to rebase a pushed branch — contradicts the merge instruction" \
    || ok "worker syncs by merging main, consistently across fragments"
grep -q 'tests` branch' "$RENDER_CODER" && grep -q 'tests` branch' "$RENDER_LEAD" \
    && ok "both one-liners say where the suite lives" \
    || fail "a one-liner still implies the suite is on main"

# The 20-minute push cadence was removed from the prompt when it was cut to
# how-pbench-works / what-each-role-does / how-to-use-tools. Nothing now bounds how long
# a worker may hold unpushed work, and nothing tells the lead to look for one that has
# gone quiet either (the for-each-ref sweep went with workflow.md). In sweep 6.8 one
# worker made 78 edits over 129 minutes without a single commit and two others pushed
# 3 times each then burned ~900 tool calls apiece. If that recurs, restore both.
ok "(delivery cadence intentionally not in the prompt)"

# --- 5. protection adapts when review is deleted ---------------------------
grep -q 'rev_blockers' "$BS" \
    && ok "review-derived blockers are conditional on REQUIRED_APPROVALS" \
    || fail "block_on_official_review_requests etc. still hardcoded true — merges would stall"
grep -q 'block_on_outdated_branch:true' "$BS" \
    && ok "block_on_outdated_branch stays on (stale-branch corruption in 6.3)" \
    || fail "block_on_outdated_branch was turned off"
grep -q 'PBENCH_REQUIRE_LEAD_TESTS' "$BS" \
    && ok "lead-tests is opt-in as a REQUIRED check (no pending-deadlock by default)" \
    || fail "lead-tests requiredness is not gated"
grep -q 'push_whitelist_usernames:(if \$lead' "$BS" \
    && ok "the lead can push tests/ to main" \
    || fail "the lead cannot publish the spec without gating it on itself"

# --- 6. the run.sh OUTPUT FORMAT is a cross-component contract ---------------
# CI reads "failed=N" off the last 5 lines; workers grep '^FAIL' to see what they
# broke. Neither is inherent to a shell script -- the lead writes run.sh from its
# own prompt, and that prompt used to specify only "print the case name, the
# invocation, expected vs actual, and the diff". A lead that summarised as
# "3 tests did not match" satisfied its spec and produced a suite whose failure
# count CI cannot parse; because an unparseable count PASSES (by design, so a
# regex cannot deadlock 20 tasks), the merge gate becomes a silent no-op for the
# whole run. The two parsers and the one prompt that feeds them must agree.
LEADWF="$ROOT/docker/hermes-agent/templates-claude-1team/roles/director_lead/workflow.md"
grep -qE 'ran=<?N>? failed=<?M>?' "$RENDER_LEAD" \
    && ok "lead spec mandates the ran=/failed= summary line CI parses" \
    || fail "lead spec never requires the failed=N line -- CI would fail open and gate nothing"
tr -s '[:space:]' ' ' < "$RENDER_LEAD" | grep -qE 'FAIL <(case_name|goal>/<name)>' \
    && ok "lead spec mandates the FAIL <case> prefix workers grep for" \
    || fail "lead spec never requires ^FAIL lines -- worker no-regression diff compares two empty sets"
# The prompt no longer warns the lead that a nonstandard summary silently disables
# the gate -- deliberately trimmed when the prompts were cut to "how pbench works /
# what each role does / how to use the tools". CI still fails open (bootstrap:
# "could not read a failure count"), so a lead with an odd summary format gates
# nothing and is not told. Re-add the warning if that shows up in a sweep.
ok "(nonstandard-summary warning intentionally not in the prompt)"

# --- 7. partial slices must not close their sub-issue -----------------------
# Workers open one PR per behaviour, not per assignment. Requiring "Closes #N" on
# every PR body made gitea close the sub-issue on the FIRST slice, and the lead
# reads a closed sub-issue as "this worker is free" -- so it hands out the next
# area while two thirds of the previous one is unwritten.
grep -q "(closes|refs)\[\[:space:\]\]+#" "$BS" \
    && ok "PR-body check accepts Refs #N as well as Closes #N" \
    || fail "PR-body check still demands Closes on every PR -- first slice closes the issue"
# worker3 owned the smoke's stuck PR#7 and received NEITHER the CI block nor the lead's
# mattermost relay of it: gitea raises no notification for a finished Actions run, so the
# router (which polls /api/v1/notifications) could not emit one. lead-tests now posts its
# verdict as a PR comment, and comments DO notify participants -- so the prompt must say the
# result arrives, while still not letting a worker sit and wait on it.
tr -s '[:space:]' ' ' < "$RENDER_CODER" | grep -qiE 'commented at the PR|comments its verdict' \
    && ok "worker knows the verdict arrives as a comment, i.e. as a real event" \
    || fail "worker is not told the verdict is delivered — it will poll or stall"
# Measured across all 694 CI runs in the last 2h of each sweep-6.9 task (gitea actions_log
# timestamps): median 27-97s, worst case 103s (pandoc). ctags 27.4/33.7, gromacs 27.3/73.1,
# quickjs 32.6/35.3, ffmpeg 33.2/46.2, typst 38.0/52.0, php 51.1/74.8, cppcheck 1.2/69.0.
# Nothing queued badly despite ACT_CAPACITY=2, so waiting beats ending the turn and hoping.
tr -s '[:space:]' ' ' < "$RENDER_CODER" | grep -qi 'wait for the CI test to finish' \
    && ok "the worker waits for CI instead of leaving and collecting it later" \
    || fail "worker may end its turn on a check that finishes in ~30s"
grep -qE 'Refs #<[a-z]+>' "$RENDER_CODER" \
    && ok "worker is told to use Refs for a partial slice, Closes to finish" \
    || fail "worker still puts Closes on every PR"

# --- 8. the topology switches must actually be WIRED ------------------------
# bootstrap.sh implements the whole test-gate topology behind three env vars.
# Nothing set any of them, so sweeps 6.5 and 6.6 booted in the REVIEW
# configuration this code was written to replace. A 20-minute smoke on
# 2026-08-02 showed main protected with required_approvals=1 (no PR can merge
# without an approval from a lead we instruct never to approve) and
# push_whitelist=[chairman] (the lead cannot push the tests/ suite that is its
# entire job). Correct implementation, dead wiring, and no test looked at the
# rendered compose.
OVR="$ROOT/docker/docker-compose.pbench-1team.yml"
check_env() {  # service-key-prefix var expected
    python3 - "$OVR" "$1" "$2" "$3" <<'PY2'
import sys, yaml
f, key, var, want = sys.argv[1:5]
svc = (yaml.safe_load(open(f)).get("services") or {})
live = [k for k, v in svc.items()
        if k.startswith(key) and "_disabled" not in ((v or {}).get("profiles") or [])]
bad = [k for k in live
       if str((((svc[k] or {}).get("environment")) or {}).get(var, "")) != want]
print("OK" if live and not bad else "BAD:%d/%d" % (len(bad), len(live)))
PY2
}
r=$(check_env bootstrap REQUIRED_APPROVALS 0)
[ "$r" = OK ] && ok "REQUIRED_APPROVALS=0 (no approver exists; clears review blockers)" \
              || fail "REQUIRED_APPROVALS is not 0 ($r) — every PR waits for an approval nobody gives"
r=$(check_env bootstrap PBENCH_LEAD_USER '${ORG_NAME}-team1-lead')
[ "$r" = OK ] && ok "PBENCH_LEAD_USER set — the lead can push tests/ to main" \
              || fail "PBENCH_LEAD_USER unset ($r) — the lead cannot publish its suite"
r=$(check_env bootstrap PBENCH_REQUIRE_LEAD_TESTS 1)
[ "$r" = OK ] && ok "lead-tests is a required check on the team topology" \
              || fail "lead-tests not required ($r) — a worker can merge without the suite running"
r=$(check_env hermes-agent-team1- ACP_CHILD_UID 10000)
[ "$r" = OK ] && ok "ACP child drops to uid 10000 — 0111 reference is unreadable" \
              || fail "no privilege drop ($r) — child runs as root, CAP_DAC_OVERRIDE reads the binary"

# lead-tests triggers on pull_request [opened, synchronize, reopened]: pushing a branch alone
# starts nothing, opening the PR does, and every later push restarts it. A worker that thinks
# CI is something it invokes will wait for a run that never happens -- and this is also why a
# PR-body edit does not re-check.
tr -s '[:space:]' ' ' < "$RENDER_CODER" | grep -qi 'opening it is what starts' \
    && ok "the worker knows opening the PR is what starts CI" \
    || fail "nothing says what triggers lead-tests"


# --- trial findings: two agents did the job, then said what stayed unresolved ------
# 1. The prompt orders "publish the moment you establish something" and names only the READ
#    verb. The coder trial finished its hour with findings ready and nowhere to put them.
#    (mcp__board__board_write, 117 calls in the 0.5h smoke; board_unfold, 0.)
tr -s '[:space:]' ' ' < "$RENDER_CODER" | grep -q 'board_write' \
    && ok "the board's write verb is named, not just the read verb" \
    || fail "agents are told to publish to the board with no way to do it"


# --- 15. a goal is frozen once assigned ---------------------------------------
# Measured in sweep 6.10 (ctags): the lead committed cases to the tests branch every 5-7
# minutes for four hours and created NO new goal in that window -- every commit deepened a
# goal that was already assigned. The goals it grew most are exactly the ones workers returned
# to most: output +11 cases/6 PRs, lang-c +9/6, filemap +5/5, cli +5/5, while lang-make and
# lang-sh got no new cases and no revisits. Across the run: 23 `Refs #n` against 8 `Closes #n`.
#
# That is a closed loop, and every part of it follows the prompt correctly. A new case in an
# assigned goal shows up by name in the verdict comment's "your goal's cases still failing"
# block, which reads as unfinished work; the worker returns rather than taking new ground, so
# it sends Refs not Closes; the sub-issue stays open, so the lead never learns anyone is free;
# and "keep a prepared sub-issue waiting for each worker" is triggered by workers reporting
# free. With no trigger to open goals, the lead does the one thing always available to it --
# capture more cases -- and the loop repeats. Meanwhile ~120 ctags parsers had no goal at all,
# 736 of 1,658 missed tests.
#
# Freezing the sub-issue breaks it at step one: the target stops moving, "all of them passing
# means the sub-issue is done" becomes achievable, and adding coverage now costs a new
# sub-issue -- which forces the lead to weigh more depth against a language nobody has touched.
#
# NOTE ON VOCABULARY: the prompt was reworded so the frozen unit is the SUB-ISSUE (the thing
# assigned) rather than the goal (the `tests/cases/<goal>/` directory). These assertions test
# the RULE, not the noun, so they accept either word -- otherwise a pure rename reds the suite
# while the behaviour it guards is intact.
tr -s '[:space:]' ' ' < "$RENDER_LEAD" | grep -qiE 'frozen|do not add cases to a (goal|sub-issue)|never add cases to an assigned' \
    && ok "the assigned unit is frozen once assigned" \
    || fail "the lead may grow an assigned unit — the target moves and the worker never closes it"
tr -s '[:space:]' ' ' < "$RENDER_LEAD" | grep -qiE 'new\*{0,2} (goal|sub-issue)|calculator2|second goal' \
    && ok "more coverage for a covered area goes to a NEW sub-issue" \
    || fail "nothing says where later observations go"
# Freezing coverage must not freeze a BUG. .expected is captured, and can be captured wrongly:
# our own trial lead shipped a case where `-s ' -> '` collapsed to `-s ->`, so it passed while
# testing the wrong thing. A rule that forbids touching an assigned goal at all would make that
# permanent.
tr -s '[:space:]' ' ' < "$RENDER_LEAD" | grep -qiE 'wrong|correct' \
    && ok "a case that is WRONG may still be fixed in place" \
    || fail "freezing the goal would freeze a miscaptured .expected into the suite forever"


# --- 16. probing the reference must be memory-bounded -------------------------
# 6.10 died when one `/opt/pbench/executable` reached 474 GB of 503 GB (11 machine-wide OOM
# kills). 6.11 reproduced it live: two `energy -f junk.edr` probes at 206.8 GB and 128.8 GB
# inside the gromacs lead's container. Both were the LEAD probing the reference with malformed
# input -- which is exactly what "observe the reference" asks for. A corrupt binary file makes
# these tools read a bogus length field and allocate against it.
#
# The per-case `timeout -k 2 $CASE_TIMEOUT` does not cover this: a direct probe is not a suite
# case, and a time limit does not bound memory anyway.
#
# The bound must be applied BY the agent, not by wrapping the binary. A wrapper would make the
# limit indistinguishable from the program's own behaviour, and a lead whose job is to capture
# what it observes would faithfully record our ENOMEM as a case -- encoding our limit into
# .expected forever, green locally and wrong in the grade.
for R in "$RENDER_LEAD" "$RENDER_CODER"; do
    n=$(basename "$(dirname "$R")")
    tr -s '[:space:]' ' ' < "$R" | grep -q 'ulimit -v' \
        && ok "$(basename "$R" .md): probes the reference under a memory bound" \
        || fail "$(basename "$R" .md): an unbounded probe can take the machine down (6.10, 6.11)"
done

exit $rc
