#!/usr/bin/env bash
# test_traj_metrics.sh — the trajectory metrics script must agree with ground truth.
#
# WHY THIS TEST COMPUTES ITS OWN ANSWERS
# A metrics script is only useful if you trust its numbers, and hardcoded golden values rot the
# moment a trajectory is re-archived. So this test derives ground truth INDEPENDENTLY (straight
# from the bare git repo) and requires the script to agree. Where a metric can only be a proxy
# -- issues and PRs live in Gitea's MySQL, not in the repo, so nothing on disk records them
# exactly -- the test asserts the script LABELS it as a proxy rather than asserting a value.
#
# Real data, not fixtures: this runs against the archived sweeps in
# ~/agensteam_traj_eng_sweep_6.1{0,1}_1_team, which are complete on-disk trajectories.
#
# Usage: bash tests/pbench/test_traj_metrics.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/scripts/pbench_traj_metrics.sh"
T11="$HOME/agensteam_traj_eng_sweep_6.11_1_team"
CTAGS="$T11/universal-ctags__ctags.243595e.2a-s611b-sweep6.11"
rc=0
ok()   { echo "PASS $*"; }
fail() { echo "FAIL $*"; rc=1; }

[ -f "$SCRIPT" ] && ok "the metrics script exists" || { echo "FAIL missing $SCRIPT"; exit 1; }
[ -x "$SCRIPT" ] && ok "it is executable" || fail "not executable"

if [ ! -d "$CTAGS" ]; then
    echo "SKIP everything else (no archived trajectory at $CTAGS)"
    exit $rc
fi

OUT=$(timeout 900 bash "$SCRIPT" "$CTAGS" --json 2>/dev/null)
[ -n "$OUT" ] && ok "it produces output for a real trajectory" || fail "no output"
printf '%s' "$OUT" | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null \
    && ok "--json emits valid JSON" \
    || fail "--json did not emit valid JSON"

g() { printf '%s' "$OUT" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('$1',''))" 2>/dev/null; }

# --- 1. EXACT metrics must match ground truth computed here, independently -----
REPO="$CTAGS/data-root/gitea/git/repositories/pbench/main.git"
TRUE_MERGED=$(sudo git --git-dir="$REPO" log main --oneline 2>/dev/null | grep -c 'Merge pull request')
GOT_MERGED=$(g pr_merged)
[ -n "$GOT_MERGED" ] && [ "$GOT_MERGED" = "$TRUE_MERGED" ] \
    && ok "pr_merged=$GOT_MERGED matches git log ($TRUE_MERGED)" \
    || fail "pr_merged=$GOT_MERGED but git log says $TRUE_MERGED"

TRUE_LANDED=$(sudo git --git-dir="$REPO" show main:src/ci-list.txt 2>/dev/null | grep -c .)
GOT_LANDED=$(g subissue_landed)
[ -n "$GOT_LANDED" ] && [ "$GOT_LANDED" = "$TRUE_LANDED" ] \
    && ok "subissue_landed=$GOT_LANDED matches src/ci-list.txt ($TRUE_LANDED)" \
    || fail "subissue_landed=$GOT_LANDED but ci-list.txt has $TRUE_LANDED lines"

# --- 2. turns and rate must be real and self-consistent -----------------------
TURNS=$(g total_turns); MINS=$(g elapsed_min); RPM=$(g requests_per_min)
[ "${TURNS:-0}" -gt 100 ] 2>/dev/null \
    && ok "total_turns=$TURNS (a 6h five-agent run has thousands)" \
    || fail "total_turns=$TURNS implausible — transcripts are root-owned; did it forget sudo?"
python3 -c "
import sys
t,m,r=float('${TURNS:-0}'),float('${MINS:-0}'),float('${RPM:-0}')
sys.exit(0 if m>0 and abs(r-t/m)<0.05 else 1)" 2>/dev/null \
    && ok "requests_per_min is consistent with turns/elapsed" \
    || fail "requests_per_min=$RPM does not equal total_turns/elapsed_min ($TURNS/$MINS)"
# The run was ~5.5h. A wildly wrong figure means timestamps were misparsed.
python3 -c "import sys; sys.exit(0 if 60 <= float('${MINS:-0}') <= 480 else 1)" 2>/dev/null \
    && ok "elapsed_min=$MINS is in the right ballpark for a 6h run" \
    || fail "elapsed_min=$MINS — timestamps misparsed"

# --- 3. activity proportions must be a partition -------------------------------
# If categories overlap or leak, the percentages stop meaning anything. They must sum to ~100.
printf '%s' "$OUT" | python3 -c "
import json,sys
d=json.load(sys.stdin); a=d.get('activity_pct') or {}
if not a: print('NO activity_pct'); sys.exit(1)
s=sum(a.values())
sys.exit(0 if 99.0 <= s <= 101.0 else 2)
" 2>/dev/null \
    && ok "activity_pct sums to 100 — the categories are a partition" \
    || fail "activity_pct missing or does not sum to 100 (categories overlap or leak)"
for k in probe_reference own_build write_code git_or_gitea mattermost board; do
    printf '%s' "$OUT" | python3 -c "
import json,sys; sys.exit(0 if '$k' in (json.load(sys.stdin).get('activity_pct') or {}) else 1)" 2>/dev/null \
        && ok "activity_pct has '$k'" \
        || fail "activity_pct is missing the '$k' category"
done

# --- 4. proxies must be declared, not passed off as exact ----------------------
printf '%s' "$OUT" | python3 -c "
import json,sys
d=json.load(sys.stdin)
p=d.get('proxy_metrics')
sys.exit(0 if isinstance(p,list) and any('issue' in x or 'pr_opened' in x for x in p) else 1)" 2>/dev/null \
    && ok "metrics that cannot be derived exactly are declared in proxy_metrics" \
    || fail "nothing declares which metrics are proxies — issues/PRs live in MySQL, not on disk"

# --- 5. it must work on the OTHER sweep's layout too ---------------------------
# 6.10 and 6.11 archive identically, but a path assumption baked to one sweep is easy to make.
OTHER="$HOME/agensteam_traj_eng_sweep_6.10_1_team/universal-ctags__ctags.243595e.2a-s610b-sweep6.10"
if [ -d "$OTHER" ]; then
    O2=$(timeout 900 bash "$SCRIPT" "$OTHER" --json 2>/dev/null)
    printf '%s' "$O2" | python3 -c "
import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('total_turns',0)>100 else 1)" 2>/dev/null \
        && ok "it also reads the 6.10 trajectory" \
        || fail "it works on 6.11 but not 6.10 — a path assumption is baked in"
else
    echo "SKIP 6.10 layout check (not archived here)"
fi

# --- 6. it must fail loudly on a bad path, not print zeros ---------------------
# A metrics tool that returns 0 for a missing directory silently produces fiction.
if timeout 60 bash "$SCRIPT" /nonexistent/trajectory >/dev/null 2>&1; then
    fail "a nonexistent trajectory exited 0 — zeros would read as real measurements"
else
    ok "a nonexistent trajectory is an error, not a row of zeros"
fi

# --- 7. FREEZE DETECTION --------------------------------------------------------
# On 2026-08-12 all four stacks froze for 43 min (dockerd's stdio copier failed; agents blocked
# in write()). Measured as (last - first) the span still read as 329-360 min, so the outage was
# invisible and looked like a per-task throughput regression. The tool must surface the HOLE.
printf '%s' "$OUT" | python3 -c "
import json,sys
d=json.load(sys.stdin)
sys.exit(0 if 'max_gap_min' in d and 'active_min' in d else 1)" 2>/dev/null \
    && ok "reports max_gap_min and active_min, so a freeze cannot hide inside the span" \
    || fail "no max_gap_min/active_min — a 43-minute outage would read as normal elapsed time"
printf '%s' "$OUT" | python3 -c "
import json,sys
d=json.load(sys.stdin)
sys.exit(0 if d.get('active_min',0) <= d.get('elapsed_min',0)+0.1 else 1)" 2>/dev/null \
    && ok "active_min <= elapsed_min" \
    || fail "active_min exceeds elapsed_min — the gap arithmetic is wrong"
# The SAME outage shows up two different ways depending on where a stack's clock fell:
#   ffmpeg  froze mid-run and resumed  -> a 42.6 min HOLE (max_gap_min)
#   ctags   froze and never resumed    -> no hole at all, just a short run (shortfall_min)
# A detector that only looks for holes misses three of the four tasks.
FF="$T11/ffmpeg__ffmpeg.360a402.2a-s611a-sweep6.11"
if [ -d "$FF" ]; then
    FGAP=$(timeout 900 bash "$SCRIPT" "$FF" --json 2>/dev/null \
        | python3 -c "import json,sys;print(json.load(sys.stdin).get('max_gap_min',0))" 2>/dev/null)
    python3 -c "import sys; sys.exit(0 if float('${FGAP:-0}') > 20 else 1)" 2>/dev/null \
        && ok "detects the mid-run freeze as a hole (ffmpeg max_gap_min=$FGAP)" \
        || fail "ffmpeg max_gap_min=$FGAP — missed the known 42.6-minute hole"
else
    echo "SKIP mid-run freeze check (ffmpeg trajectory absent)"
fi
SHORT=$(g shortfall_min)
python3 -c "import sys; sys.exit(0 if float('${SHORT:-0}') > 20 else 1)" 2>/dev/null \
    && ok "detects a run that ended short of its budget (ctags shortfall_min=$SHORT)" \
    || fail "ctags shortfall_min=$SHORT — a freeze that runs past the deadline is invisible"

exit $rc
