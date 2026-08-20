#!/usr/bin/env bash
# test_role_fragments.sh — the 1team prompt contract.
#
# Two things are asserted here: that every role defines all six fragments itself,
# and that the prompts stay task-agnostic (EdgeBench prompts: how the benchmark
# works, what each role does, how to use the tools — never what the task is).
#
# WHY (fragments)
# entrypoint.sh:150-155 reads six fragments per role unconditionally:
#   name, one_liner, dos, donts, workflow, failure_modes
# Dockerfile.pertask:107-108 copies templates-claude/ and THEN overlays
# templates-claude-1team/ onto the same path, so any fragment the 1team dir
# does not define silently inherits the base copy.
#
# Before sweep 6.5 the coder role only defined workflow/dos/donts, so
# name.md, one_liner.md and failure_modes.md came from templates-claude/ —
# which still describes the OLD topology ("open the PR, get through review").
# Rewriting the 1team files would have left an agent whose one-liner told it to
# wait for a review that no longer exists.
#
# The compose overlay must also bind-mount every fragment, otherwise the file
# on disk is right and the file in the container is the stale baked one — the
# rewrite would apply only after rebuilding all 20 per-task images.
#
# Usage: bash tests/pbench/test_role_fragments.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMPL="$ROOT/docker/hermes-agent/templates-claude-1team/roles"
OVERLAY="$ROOT/docker/docker-compose.pbench-1team.yml"
FRAGS="name one_liner dos donts workflow failure_modes"
rc=0
ok()   { echo "PASS $*"; }
fail() { echo "FAIL $*"; rc=1; }

# Which fragments does the 1team prompt actually splice? base.md is the OUTER
# template and the board profile mounts base.board.md over it, so the union of
# the two is what can ever be rendered. Everything else is dead weight: the
# 6.11 prompts were cut to how-the-benchmark-works / what-each-role-does /
# how-to-use-tools, which left dos/donts/workflow/failure_modes as four
# byte-identical placeholder stubs per role, kept alive only by entrypoint's
# guard. They are gone; this asserts they cannot creep back.
SPLICED="$(grep -ohE '\$\{ROLE_[A-Z_]+\}' "$TMPL"/base.md "$TMPL"/base.board.md 2>/dev/null \
           | sed -e 's/^\${ROLE_//' -e 's/}$//' | tr '[:upper:]' '[:lower:]' | sort -u)"
# Collapse to a single space-separated line: the `case` membership test below
# cannot match a token inside a newline-separated list.
SPLICED="$(echo $SPLICED)"
[ -n "$SPLICED" ] \
    && ok "1team prompt splices: $(echo $SPLICED)" \
    || fail "no \${ROLE_*} placeholder found in base.md/base.board.md — prompt would render no role at all"

for role in director_lead coder; do
    for f in $SPLICED; do
        p="$TMPL/$role/$f.md"
        [ -s "$p" ] \
            && ok "$role/$f.md defined in 1team ($(wc -c <"$p") bytes)" \
            || fail "$role/$f.md missing — would inherit the stale templates-claude base"
    done
    # No fragment may sit in the role dir that the prompt never renders.
    for p in "$TMPL/$role"/*.md; do
        [ -e "$p" ] || continue
        b="$(basename "$p" .md)"
        case " $SPLICED " in
            *" $b "*) ;;
            *) fail "$role/$b.md is never spliced by base.md — dead fragment, delete it" ;;
        esac
    done
done

# entrypoint.sh must require exactly what the prompt splices, not a hard-coded
# six. director_lead is bind-mounted as a whole DIRECTORY, so it has no baked
# fallback: a guard demanding a fragment the prompt does not use makes the agent
# exit 1 at boot rather than render a shorter prompt.
EP_="$ROOT/docker/hermes-agent/entrypoint.sh"
grep -q 'ROLE_\[A-Z_\]\+' "$EP_" \
    && ok "entrypoint derives its required fragments from the base template" \
    || fail "entrypoint still hard-codes the six-fragment list — dropping a dead fragment would break boot"

# Every spliced coder fragment must be mounted, or the container keeps the baked copy.
for f in $SPLICED; do
    if grep -q "roles/coder/$f.md:/opt/omcgitea/templates-claude/roles/coder/$f.md" "$OVERLAY"; then
        ok "coder/$f.md is bind-mounted by the 1team overlay"
    else
        fail "coder/$f.md not mounted — rewrite would need an image rebuild to apply"
    fi
done
# ...and no mount may point at a fragment that no longer exists: a bind-mount
# with a missing source makes docker create a DIRECTORY at the target, and
# `cat` on a directory is the empty prompt section this guard exists to stop.
while IFS= read -r src; do
    [ -e "$ROOT/docker/$src" ] \
        || fail "overlay mounts $src which does not exist — docker would mount a directory there"
done < <(grep -oE '\./hermes-agent/templates-claude-1team/roles/[a-z_/.]+\.md' "$OVERLAY" | sort -u)
ok "every role-fragment mount in the 1team overlay resolves to a real file"


# The topology: nobody reviews, nobody approves, a worker merges its own PR.
# Assert the PROHIBITION, not the vocabulary. The fragments deliberately no longer
# use the word "review" -- naming the thing kept the concept alive in a prompt for a
# topology that has no such stage. What must survive is the concrete ban.
# The explicit "do not APPROVE / REQUEST_CHANGES / close a PR / merge" bans lived in
# donts.md, which was removed when the prompts were cut to how-the-benchmark-works /
# what-each-role-does / how-to-use-tools. What survives is structural, in base.md:
# "Nobody signs off on anything" + the worker line "opens a PR, merges it himself".
# Sweep 6.4 measured leads spending 26.3% of budget reviewing, so if that recurs the
# explicit ban is the thing to restore.
grep -qi "Nobody signs off on anything" "$TMPL/base.md" \
    && ok "no sign-off exists (structural, replaces the explicit APPROVE ban)" \
    || fail "base.md no longer says nobody signs off — leads may resume reviewing"
# The lead's own fragment has to keep it out of the work and on the assigning loop:
# its one deliverable is that no worker sits idle.
tr -s "[:space:]" " " < "$TMPL/director_lead/one_liner.md" | grep -qiE "assign|holding work" \
    && ok "lead role is built around keeping workers assigned" \
    || fail "lead role no longer describes assigning work"
# whitespace-normalised: these phrases wrap across a line break, and a plain grep
# cannot match across newlines.
SELFMERGE="merges? it (him|her|them)self|merges? (your|their|its) own branch|merge it into .main. yourself|self-merge"
tr -s "[:space:]" " " < "$TMPL/base.md" | grep -qiE "$SELFMERGE" \
    && ok "base.md says a worker merges its own PR" \
    || fail "base.md no longer says a worker merges its own PR"
tr -s "[:space:]" " " < "$TMPL/coder/one_liner.md" | grep -qiE "$SELFMERGE" \
    && ok "worker is told to merge its own PR (coder/one_liner.md)" \
    || fail "nothing tells a worker to self-merge"

# base.md is the OUTER template: entrypoint.sh:274 renders it to /work/CLAUDE.md and the
# 1team overlay bind-mounts it, so it sits ABOVE every role fragment in the same document.
# It went stale through 6.5 and 6.6 — last touched by "fold the reviewer role into the
# director/lead", it still told the lead it "reviews and approves PRs" and "never pushes to
# main", and told workers to "self-merge after the lead's APPROVE", while the fragments
# underneath said the opposite. An agent reading a document that contradicts itself will
# follow one of the two, and we cannot choose which. Assert the outer frame agrees.
BASE="$TMPL/base.md"
grep -qiE "reviews and approves|self-merge after the lead|never push to .main. yourself|request_review" "$BASE" \
    && fail "base.md still describes the review topology — it overrides the role fragments" \
    || ok "base.md carries no review-era role description"
grep -qiE "Nobody signs off|no approver" "$BASE" \
    && ok "base.md states plainly that nobody signs off" \
    || fail "base.md does not tell agents there is no sign-off"
# And the word itself must be GONE from every 1team fragment: the topology is
# described by what happens, not by naming the stage that was removed.
if grep -rqi "review" "$TMPL"/*.md "$TMPL"/*/*.md 2>/dev/null; then
    fail "the word 'review' reappeared in a 1team fragment: $(grep -rli review "$TMPL"/*.md "$TMPL"/*/*.md | tr '\n' ' ')"
else
    ok "no 1team fragment mentions review at all"
fi
# The prompts must stay TASK-AGNOSTIC. They describe how the benchmark works, what each
# role does and how to use the tools -- never what the task is. The task arrives through
# ${PBENCH_BRIEF} (pbench-brief.md) and issue #1, so a role fragment that names a language,
# a build step or a fixed layout quietly narrows every task to the one it was written for.
# The 6.11 fragments hard-coded the ProgramBench shape (`/opt/pbench/executable`, a root
# `compile.sh`, `tests/cases/`, `src/ci-list.txt`); those are gone and must not come back.
# NOTE the scope: this checks base.md and the role fragments ONLY. pbench-brief.md is the
# task statement and is SUPPOSED to be ProgramBench-specific -- see the brief-gate block
# further down, which asserts it actually reaches the prompt.
CODING_SPECIFIC='/opt/pbench/executable|compile\.sh|tests/cases|src/ci-list\.txt|\./executable|reference (binary|program)|decompile'
hits=$(grep -rlEi "$CODING_SPECIFIC" "$TMPL"/*.md "$TMPL"/*/*.md 2>/dev/null | tr '\n' ' ')
[ -z "$hits" ] \
    && ok "no 1team role fragment hard-codes a coding-specific task shape" \
    || fail "coding-specific task detail leaked back into the role prompts: $hits"

# base.board.md is GENERATED from base.md by scripts/gen_board_base.sh and mounted by the
# -1team-board profile. If it drifts, the board arm silently runs the old topology.
BB="$TMPL/base.board.md"
PRE="$ROOT/docker/hermes-agent/board-preamble.md"
# base.board.md is GENERATED: base.md with ${BOARD_PREAMBLE} replaced by
# board-preamble.md (scripts/gen_board_base.sh). Assert exactly that, rather
# than diffing a shared prefix -- the board text now sits INSIDE "Where you are",
# so the two files legitimately differ before any trailing sentinel, and a
# prefix check reports drift that is not there.
if [ -f "$BB" ] && [ -f "$PRE" ]; then
    if diff -q "$BB" <(python3 -c "
import sys
src, pre = sys.argv[1:3]
sys.stdout.write(open(src).read().replace('\${BOARD_PREAMBLE}', open(pre).read().rstrip(chr(10))))
" "$TMPL/base.md" "$PRE") >/dev/null 2>&1; then
        ok "base.board.md == base.md with the board preamble inlined"
    else
        fail "base.board.md has drifted from base.md — run scripts/gen_board_base.sh"
    fi
fi

# The task brief must actually reach the system prompt. entrypoint.sh gates
# ${PBENCH_BRIEF} on ACP_CHILD_UID, which only the SINGLE-agent pbench scripts
# set -- so through sweeps 6.5 and 6.6 every team agent rendered base.md with an
# empty brief: no goal statement, no "no internet" rule, and no "root compile.sh
# must produce ./executable or 0 points". Grepping ten 6.6 lead prompts for
# "Iron rules" / "reverse rebuild" returned zero hits apiece while role fragments
# in the same prompt were present. The gate cannot simply test for the file:
# templates-claude ships a pbench-brief.md in the base image, so dev and prod
# would start rendering it.
EP="$ROOT/docker/hermes-agent/entrypoint.sh"
grep -q 'PBENCH_BRIEF_ENABLE' "$EP" \
    && ok "entrypoint honours an explicit brief opt-in" \
    || fail "brief is still gated only on ACP_CHILD_UID — team profiles get an empty brief"
# The brief is the ONE place the task shape is stated, now that the role prompts are
# task-agnostic. Every rule below is enforced elsewhere by the harness, so a brief that
# stops saying them leaves agents to discover them by failing: the binary is mounted
# root:root 0111 (test_bin_isolation.sh), egress is cut (test_net_isolation.sh), and the
# evaluator deletes any committed ./executable before running compile.sh
# (test_submission_export.sh). Assert the brief still carries all three.
BRIEF="$ROOT/docker/hermes-agent/templates-claude-1team/pbench-brief.md"
for want in '/opt/pbench/executable' 'No internet' 'compile\.sh' 'Iron rules'; do
    grep -qiE "$want" "$BRIEF" \
        && ok "brief still states: $want" \
        || fail "brief no longer states '$want' — the harness enforces it regardless"
done
n=$(python3 - "$OVERLAY" <<'PY2'
import sys, yaml
d = yaml.safe_load(open(sys.argv[1]))
svc = d.get("services", {}) or {}
live = [k for k, v in svc.items()
        if k.startswith("hermes-agent-team1-")
        and "_disabled" not in ((v or {}).get("profiles") or [])]
print(sum(1 for k in live
          if str((( svc[k] or {}).get("environment") or {}).get("PBENCH_BRIEF_ENABLE", "")) == "1"))
PY2
)
[ "$n" = "5" ] \
    && ok "all 5 live 1team agents render the brief" \
    || fail "only $n/5 live 1team agents set PBENCH_BRIEF_ENABLE"
for f in "$ROOT/docker/docker-compose.yml" "$ROOT/docker/docker-compose.prod.yml"; do
    [ -f "$f" ] || continue
    grep -q 'PBENCH_BRIEF_ENABLE' "$f" \
        && fail "$(basename "$f") enables the pbench brief — it would leak into non-pbench runs" \
        || ok "$(basename "$f") does not render the pbench brief"
done

exit $rc
