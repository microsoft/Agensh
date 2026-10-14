#!/usr/bin/env bash
# pbench_traj_metrics.sh — static metrics for one archived ProgramBench trajectory.
#
# Usage:
#   scripts/pbench_traj_metrics.sh <traj-dir> [--json]
#   scripts/pbench_traj_metrics.sh ~/pbench-trajectories/universal-ctags__*
#
# Compare runs of one task:
#   for d in ~/pbench-trajectories/universal-ctags__*; do
#       scripts/pbench_traj_metrics.sh "$d"; done
#
# The transcript metrics read Claude Code transcripts (AGENT_KIND=claude); on a trajectory
# whose agents ran another ACP agent they come out as 0.
#
# WHAT IS EXACT AND WHAT IS A PROXY -- read this before quoting a number.
#
#   EXACT, from the bare git repo:
#     pr_merged          `Merge pull request` commits on main
#     subissue_landed    lines in main:src/ci-list.txt (goals a worker actually landed)
#     branches           refs in the repo
#   EXACT, from the agent transcripts:
#     total_turns, elapsed_min, requests_per_min, api_errors, tool_errors, tool-call counts,
#     activity_pct
#     NOTE api_errors counts only STRUCTURALLY MARKED failures. Do not reintroduce a substring
#     scan for "429"/"529" -- it matches digits inside `—` escapes and words like
#     "unbalanced", and fabricates an error cascade out of ordinary transcript text.
#   PROXY (declared in `proxy_metrics`):
#     subissue_opened, pr_opened -- issues and PRs live in Gitea's MySQL, which is NOT in the
#     archive as queryable data. These are counted from create-shaped calls in the transcripts
#     (POST to /issues or /pulls, or the matching MCP write tools). Agents also read and comment
#     through the same endpoints, so treat these as upper-ish bounds, not counts.
#
# TRANSCRIPTS ARE ROOT-OWNED. Everything below reads them through sudo. A plain read returns
# nothing and silently reports zeros, so on a Claude trajectory a total_turns of 0 means the
# read failed. On a Copilot trajectory (session-state/*/events.jsonl + session-store.db, no
# Claude transcripts) every transcript metric, agents included, is 0 by construction:
# expected, not a failed read.
set -u

TRAJ="${1:-}"
JSON=0
[ "${2:-}" = "--json" ] && JSON=1
[ "${1:-}" = "--json" ] && { echo "usage: $0 <traj-dir> [--json]" >&2; exit 2; }

if [ -z "$TRAJ" ] || [ ! -d "$TRAJ" ]; then
    echo "FATAL: no such trajectory directory: '${TRAJ:-<none>}'" >&2
    echo "usage: $0 <traj-dir> [--json]" >&2
    exit 2
fi

REPO="$TRAJ/data-root/gitea/git/repositories/pbench/main.git"

# --- exact, from git ---------------------------------------------------------
PR_MERGED=0; LANDED=0; BRANCHES=0
# `grep -c` ALREADY prints 0 when it matches nothing -- but it also EXITS 1, so a
# `... | grep -c X || echo 0` fallback fires as well and emits "0\n0", which int() rejects.
# That only bites on a repo with zero merges, i.e. a run killed mid-flight -- exactly the
# trajectory you most need to inspect. Take the first line and default an empty value to 0.
num() { local v; v=$(cat); v=$(printf '%s' "$v" | head -1 | tr -cd '0-9'); echo "${v:-0}"; }
if sudo test -d "$REPO"; then
    PR_MERGED=$(sudo git --git-dir="$REPO" log main --oneline 2>/dev/null | grep -c 'Merge pull request' | num)
    # STRIP COMMENTS. ci-list.txt can carry an explanatory header, and counting every non-empty
    # line then reports more goals landed than authored -- a >100% conversion that looks like a
    # finding and is a bug.
    LANDED=$(sudo git --git-dir="$REPO" show main:src/ci-list.txt 2>/dev/null \
             | grep -v '^[[:space:]]*#' | grep -c '[^[:space:]]' | num)
    BRANCHES=$(sudo git --git-dir="$REPO" branch -a 2>/dev/null | grep -c . | num)
    # Goals AUTHORED is exact and lives on the `tests` branch: one directory per goal under
    # tests/cases/. It is the denominator for conversion (landed/authored) and the other half
    # of the picture -- subissue_landed alone cannot tell you whether a lead under-authored
    # or the workers under-delivered.
    # PRs. `prs_opened` IS exact (Gitea keeps every PR head at refs/pull/N/head).
    # `prs_landed` is NOT a count of PRs merged as units -- read the caveat below.
    # and not the transcript proxy. "Landed" = the head is an ancestor of main, which is the
    # only strategy-independent test: counting `Merge pull request` commits measures the MERGE
    # STRATEGY, not success. php-src landed 45 of 46 PRs but shows only 17 merge commits
    # because it squash/rebase-merged -- reported as a 37% merge rate that never existed.
    #
    # BUT prs_landed is an UPPER bound, not a merged-as-a-unit count: a superseded or closed
    # PR whose branch later merged also has its head in main. quickjs shows 43 heads in main
    # from only 28 distinct merged branches. So the two available measures bracket the truth:
    #   pr_merge_commits  = LOWER bound (misses squash/rebase)
    #   prs_landed        = UPPER bound (includes superseded)
    # `branches_merged` below is the best single proxy for "units actually merged".
    PRS_OPENED=$(sudo git --git-dir="$REPO" for-each-ref --format='%(refname)' 'refs/pull/*/head' 2>/dev/null | grep -c . | num)
    PRS_LANDED=0
    for _ref in $(sudo git --git-dir="$REPO" for-each-ref --format='%(refname)' 'refs/pull/*/head' 2>/dev/null); do
        sudo git --git-dir="$REPO" merge-base --is-ancestor "$_ref" main 2>/dev/null && PRS_LANDED=$((PRS_LANDED+1))
    done
    # Merges INTO main only: the first-parent line. The rest of `git log main` also carries merges
    # into worker branches ("Merge remote-tracking branch 'origin/main' into worker3/x") and
    # ordinary subjects with a "from" in them. The branch, full name (worker1/lexer and
    # worker2/lexer are two units), comes from the subject Gitea or git wrote. A merge the agent
    # gave its own title names no branch, so fall back to the branch whose tip is the merged head,
    # and failing that (branch since deleted or moved on) count that merge on its own.
    # Syncing main into itself ("Merge branch 'main' of ...") is not a unit.
    declare -A _tip_of=()
    while read -r _sha _ref; do
        [ "$_ref" = main ] || _tip_of[$_sha]=$_ref
    done < <(sudo git --git-dir="$REPO" for-each-ref --format='%(objectname) %(refname:strip=2)' refs/heads/ 2>/dev/null)
    _re_pr="^Merge pull request '.*' \(#[0-9]+\) from ([^ ]+) into [^ ]+$"
    _re_git="^Merge (remote-tracking )?branch '([^']+)'"
    BRANCHES_MERGED=$(sudo git --git-dir="$REPO" log main --first-parent --merges --format='%P%x09%s' 2>/dev/null \
        | while IFS=$'\t' read -r _parents _subj; do
              _p2=${_parents#* }; _p2=${_p2%% *}
              if [[ $_subj =~ $_re_pr ]]; then _b=${BASH_REMATCH[1]}
              elif [[ $_subj =~ $_re_git ]]; then _b=${BASH_REMATCH[2]#origin/}
              else _b=${_tip_of[$_p2]:-merge:$_p2}; fi
              [ "$_b" = main ] || echo "$_b"
          done | sort -u | grep -c . | num)
    GOALS=$(sudo git --git-dir="$REPO" ls-tree -d --name-only tests:tests/cases 2>/dev/null | grep -c . | num)
    CASES=$(sudo git --git-dir="$REPO" ls-tree -r --name-only tests:tests/cases 2>/dev/null | grep -c '\.sh$' | num)
fi

# --- everything else, from the transcripts -----------------------------------
sudo python3 - "$TRAJ" "$PR_MERGED" "$LANDED" "$BRANCHES" "$JSON" "${GOALS:-0}" "${CASES:-0}" "${PRS_OPENED:-0}" "${PRS_LANDED:-0}" "${BRANCHES_MERGED:-0}" <<'PY'
import json, sys, glob, os, re, collections
from datetime import datetime

traj, pr_merged, landed, branches, as_json = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5] == "1"
goals_authored, cases_authored = int(sys.argv[6]), int(sys.argv[7])
prs_opened_exact, prs_landed = int(sys.argv[8]), int(sys.argv[9])
branches_merged = int(sys.argv[10])

# data-root/<layout>/<agent>/...: agents/, or hermes/ in trajectories archived before the rename.
files = [f for layout in ("agents", "hermes")
         for f in glob.glob(os.path.join(traj, "data-root", layout, "*/home/.claude/projects/-work/*.jsonl"))]

# Tool calls are bucketed into ONE category each, by precedence, so the percentages partition.
# Ordering matters: a Bash line can mention both the reference binary and a tests path, and the
# more specific intent wins. Categories that overlap would make activity_pct meaningless -- the
# test asserts it sums to 100.
BASH_RULES = [
    ("probe_reference", r"/opt/pbench/executable"),
    ("own_build",       r"\./executable|compile\.sh|\bmake\b"),
    ("run_tests",       r"tests/run\.sh|tests/cases"),
    ("git_or_gitea",    r"\bgit\b|api/v1|\btea\b"),
    ("write_code",      r"\bsrc/|\.c\b|\.py\b|\.cpp\b|cat > |tee "),
]
def bucket_bash(cmd):
    for name, pat in BASH_RULES:
        if re.search(pat, cmd):
            return name
    return "other"

def bucket_tool(name, inp):
    if name in ("Write", "Edit", "NotebookEdit", "MultiEdit"):
        return "write_code"
    if name.startswith("mcp__board__"):
        return "board"
    if name.startswith("mcp__mattermost__"):
        return "mattermost"
    if name.startswith("mcp__gitea__"):
        return "git_or_gitea"
    if name == "Bash":
        return bucket_bash(json.dumps(inp))
    if name in ("Read", "Grep", "Glob", "ToolSearch", "TodoWrite"):
        return "read_search"
    return "other"

ERR_PATTERNS = []  # see below: substring matching on transcripts does not work
# Counting API/network failures by searching transcript text is WRONG. A substring scan for
# "429"/"529"/"balance" matches digits inside `—` escapes ("—29" contains "429") and
# ordinary prose ("unbalanced" contains "balance"), so it reports a 429 cascade in a run
# whose structured markers show no API errors at all.
#
# So we count only what is structurally marked:
#   tool_errors  -- tool_result blocks with is_error true (ordinary failed commands)
#   api_errors   -- Claude Code's own isApiErrorMessage flag, plus text that begins "API Error"
#                   or carries a typed rate_limit_error / overloaded_error
def classify_error(d, block):
    if d.get("isApiErrorMessage"):
        return "api_error"
    if isinstance(block, dict):
        if block.get("type") == "tool_result" and block.get("is_error"):
            return "tool_error"
        if block.get("type") == "text":
            tx = block.get("text", "")
            if tx.startswith("API Error") or "rate_limit_error" in tx or "overloaded_error" in tx:
                return "api_error"
    return None
# Create-shaped only: agents read and comment through the same endpoints all run long.
ISSUE_CREATE = re.compile(r"-X\s+POST[^|;&]*api/v1/repos/[^/\s\"]+/[^/\s\"]+/issues\b", re.I)
PR_CREATE    = re.compile(r"-X\s+POST[^|;&]*api/v1/repos/[^/\s\"]+/[^/\s\"]+/pulls\b", re.I)

turns = 0
agent_names = set()   # one agent can leave several session files
per_agent = collections.Counter()
cats = collections.Counter()
tools = collections.Counter()
errs = collections.Counter()
stamps = []
issue_opened = 0
pr_opened = 0
# CONTEXT COMPACTION. Agents auto-compact at ~175k tokens; on quickjs that fired 77 times
# across five agents, one reset every ~20 min against a median goal of 44 worker-minutes -- so
# a goal routinely outlives the context that started it. None of that is visible in turns or
# elapsed. Count the `subtype == "compact_boundary"` system entry, NOT the substring "compact":
# the word occurs in ordinary prose and inside the preCompactDiscoveredTools payload.
compactions = collections.Counter()
compact_stamps = collections.defaultdict(list)

for f in files:
    agent = os.path.relpath(f, os.path.join(traj, "data-root")).split(os.sep)[1]
    agent_names.add(agent)
    # Per FILE: message ids are unique within a session, not across agents.
    seen_ids = set()
    try:
        fh = open(f, errors="replace")
    except OSError:
        continue
    for line in fh:
        try:
            d = json.loads(line)
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        ts = d.get("timestamp")
        if ts:
            stamps.append(ts[:19])
        if d.get("subtype") == "compact_boundary":
            compactions[agent] += 1
            if ts:
                compact_stamps[agent].append(ts[:19])
        if d.get("type") == "assistant":
            # One API response is written as ONE ENTRY PER CONTENT BLOCK, all sharing
            # message.id, so counting entries overstates turns. An entry without an id counts
            # on its own rather than collapsing a whole run under one missing key.
            mid = (d.get("message") or {}).get("id")
            if not mid or mid not in seen_ids:
                if mid:
                    seen_ids.add(mid)
                turns += 1
                per_agent[agent] += 1
        for b in (d.get("message") or {}).get("content") or []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                name = b.get("name", "")
                inp = b.get("input") or {}
                tools[name] += 1
                cats[bucket_tool(name, inp)] += 1
                s = json.dumps(inp)
                if ISSUE_CREATE.search(s):
                    issue_opened += 1
                if PR_CREATE.search(s) or name == "mcp__gitea__issue_write":
                    pass
                if PR_CREATE.search(s):
                    pr_opened += 1
                if name == "mcp__gitea__issue_write":
                    issue_opened += 1
                if name == "mcp__gitea__pull_request_write":
                    pr_opened += 1
            k = classify_error(d, b)
            if k:
                errs[k] += 1
    fh.close()

elapsed_min = 0.0
if len(stamps) >= 2:
    stamps.sort()
    try:
        a = datetime.fromisoformat(stamps[0])
        b = datetime.fromisoformat(stamps[-1])
        elapsed_min = round((b - a).total_seconds() / 60.0, 1)
    except ValueError:
        elapsed_min = 0.0

# FREEZE DETECTION. A whole-stack outage is invisible in (last - first): a stack that freezes
# for most of an hour still reports a near-full span. Measure the HOLES: sort every
# timestamp in the trajectory and find gaps where NO agent produced anything. active_min is the
# span minus those holes -- the time actually worked.
GAP_MIN = 5.0
# A freeze at the END of a run leaves no gap -- the span simply stops short of the budget
# (max_gap 0, but minutes missing), while the same outage mid-run shows as a hole. Report
# BOTH or half the cases hide.
BUDGET = float(os.environ.get("PBENCH_BUDGET_MIN", "360"))
gaps = []
if len(stamps) >= 2:
    ss = sorted(datetime.fromisoformat(x) for x in stamps)
    for a2, b2 in zip(ss, ss[1:]):
        g = (b2 - a2).total_seconds() / 60.0
        if g >= GAP_MIN:
            gaps.append({"from": a2.isoformat(sep=" "), "to": b2.isoformat(sep=" "),
                         "minutes": round(g, 1)})
gaps.sort(key=lambda x: -x["minutes"])
max_gap = gaps[0]["minutes"] if gaps else 0.0
gap_total = round(sum(x["minutes"] for x in gaps), 1)

# Interval BETWEEN compactions, measured within each agent and then pooled. A raw count cannot
# distinguish 17 resets inside 30 min from 17 spread over a 6h run, and only the interval says
# whether a goal outlives the context that started it.
_cgaps = []
for _a, _ss in compact_stamps.items():
    try:
        _ds = sorted(datetime.fromisoformat(x) for x in _ss)
    except ValueError:
        continue
    _cgaps += [(y - x).total_seconds() / 60.0 for x, y in zip(_ds, _ds[1:])]
_cgaps.sort()
compact_gap = round(_cgaps[len(_cgaps) // 2], 1) if _cgaps else 0.0

total_calls = sum(cats.values()) or 1
activity = {k: round(100.0 * v / total_calls, 1) for k, v in cats.items()}
# Force the declared categories to exist even at 0, so two runs are always comparable, then
# absorb rounding drift into the largest bucket so the partition still sums to 100.
for k in ("probe_reference", "own_build", "run_tests", "write_code",
          "git_or_gitea", "mattermost", "board", "read_search", "other"):
    activity.setdefault(k, 0.0)
drift = round(100.0 - sum(activity.values()), 1)
if abs(drift) >= 0.1:
    top = max(activity, key=lambda k: activity[k])
    activity[top] = round(activity[top] + drift, 1)

out = {
    "trajectory": os.path.basename(traj.rstrip("/")),
    "agents": len(agent_names),
    "total_turns": turns,
    "elapsed_min": elapsed_min,
    "requests_per_min": round(turns / elapsed_min, 2) if elapsed_min else 0.0,
    "active_min": round(max(0.0, elapsed_min - gap_total), 1),
    "max_gap_min": max_gap,
    "budget_min": BUDGET,
    "shortfall_min": round(max(0.0, BUDGET - elapsed_min), 1),
    "gap_total_min": gap_total,
    "gaps": gaps[:5],
    "api_errors": errs.get("api_error", 0),
    "tool_errors": errs.get("tool_error", 0),
    "compactions": sum(compactions.values()),
    "compactions_by_agent": dict(compactions),
    "compaction_median_gap_min": compact_gap,
    "subissue_opened": issue_opened,
    "goals_authored": goals_authored,
    "cases_authored": cases_authored,
    "cases_per_goal": round(cases_authored / goals_authored, 1) if goals_authored else 0.0,
    "subissue_landed": landed,
    "goal_conversion_pct": round(100.0 * landed / goals_authored, 1) if goals_authored else 0.0,
    "pr_opened": pr_opened,
    "prs_opened": prs_opened_exact,
    "prs_landed": prs_landed,
    "pr_land_pct": round(100.0 * prs_landed / prs_opened_exact, 1) if prs_opened_exact else 0.0,
    "branches_merged": branches_merged,
    "pr_merge_commits": pr_merged,
    "branches": branches,
    "total_tool_calls": total_calls,
    "activity_pct": activity,
    "turns_by_agent": dict(per_agent),
    "proxy_metrics": [
        "subissue_opened -- LOWER BOUND, often badly wrong. Leads frequently write a python "
        "script that loops `curl -X {method} {url}`, so ONE tool call creates N issues and the "
        "literal '-X POST' never appears. "
        "No transcript regex can fix this; the exact source is Gitea's issue table.",
        "pr_opened -- SUPERSEDED by prs_opened/prs_landed, which are exact (refs/pull/*/head "
        "and ancestor-of-main). Kept only so old JSON stays comparable; do not quote it.",
    ],
}

if as_json:
    print(json.dumps(out, indent=2, sort_keys=True))
else:
    print(f"=== {out['trajectory']} ===")
    print(f"  agents                {out['agents']}")
    print(f"  total turns           {out['total_turns']}")
    print(f"  elapsed (min)         {out['elapsed_min']}")
    print(f"  requests/min          {out['requests_per_min']}")
    print(f"  active (min)          {out['active_min']}   (elapsed minus stalls >= 5 min)")
    print(f"  largest stall (min)   {out['max_gap_min']}   total stalled {out['gap_total_min']}")
    print(f"  shortfall vs budget   {out['shortfall_min']} min of {out['budget_min']:.0f} (ended early?)")
    for gg in out['gaps'][:3]:
        print(f"      STALL {gg['minutes']:>6.1f}m  {gg['from'][11:19]} -> {gg['to'][11:19]}")
    print(f"  API errors            {out['api_errors']}   (structurally marked only)")
    print(f"  tool errors           {out['tool_errors']}   (failed commands, not network)")
    print(f"  compactions           {out['compactions']}   (context resets; median {out['compaction_median_gap_min']} min apart)")
    print(f"  sub-issues opened     {out['subissue_opened']}  (LOWER BOUND — unreliable)")
    print(f"  goals authored        {out['goals_authored']}   ({out['cases_authored']} cases, {out['cases_per_goal']}/goal)")
    print(f"  sub-issues landed     {out['subissue_landed']}   (src/ci-list.txt, {out['goal_conversion_pct']}% of authored)")
    print(f"  PRs opened            {out['prs_opened']}   (refs/pull/*/head — exact)")
    print(f"  PRs landed            {out['prs_landed']}   ({out['pr_land_pct']}% — head is an ancestor of main)")
    print(f"  branches merged       {out['branches_merged']}   (best proxy for units merged)")
    print(f"  merge commits         {out['pr_merge_commits']}   (LOWER bound; prs_landed is UPPER)")
    print(f"  branches              {out['branches']}")
    print(f"  tool calls            {out['total_tool_calls']}")
    print("  activity:")
    for k, v in sorted(activity.items(), key=lambda kv: -kv[1]):
        print(f"      {k:<18} {v:5.1f}%")
    print("  NOTE: subissue_opened is a lower bound (one tool call can create many issues).")
    print("        prs_landed is an UPPER bound, merge commits a LOWER one; branches_merged")
    print("        is the best single proxy for units actually merged.")
PY
