#!/usr/bin/env bash
# pbench_traj_metrics.sh — static metrics for one archived ProgramBench trajectory.
#
# Usage:
#   scripts/pbench_traj_metrics.sh <traj-dir> [--json]
#   scripts/pbench_traj_metrics.sh ~/agensteam_traj_eng_sweep_6.11_1_team/universal-ctags__*
#
# Compare two sweeps:
#   for d in ~/agensteam_traj_eng_sweep_6.1{0,1}_1_team/universal-ctags__*; do
#       scripts/pbench_traj_metrics.sh "$d"; done
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
#     "unbalanced", and fabricated an entire error cascade the first time it was tried.
#   PROXY (declared in `proxy_metrics`):
#     subissue_opened, pr_opened -- issues and PRs live in Gitea's MySQL, which is NOT in the
#     archive as queryable data. These are counted from create-shaped calls in the transcripts
#     (POST to /issues or /pulls, or the matching MCP write tools). Agents also read and comment
#     through the same endpoints, so treat these as upper-ish bounds, not counts.
#
# TRANSCRIPTS ARE ROOT-OWNED. Everything below reads them through sudo. A plain read returns
# nothing and silently reports zeros -- which is why the test asserts total_turns > 100.
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
if sudo test -d "$REPO"; then
    PR_MERGED=$(sudo git --git-dir="$REPO" log main --oneline 2>/dev/null | grep -c 'Merge pull request' || echo 0)
    LANDED=$(sudo git --git-dir="$REPO" show main:src/ci-list.txt 2>/dev/null | grep -c . || echo 0)
    BRANCHES=$(sudo git --git-dir="$REPO" branch -a 2>/dev/null | grep -c . || echo 0)
fi

# --- everything else, from the transcripts -----------------------------------
sudo python3 - "$TRAJ" "$PR_MERGED" "$LANDED" "$BRANCHES" "$JSON" <<'PY'
import json, sys, glob, os, re, collections
from datetime import datetime

traj, pr_merged, landed, branches, as_json = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5] == "1"

files = glob.glob(os.path.join(traj, "data-root/hermes/*/home/.claude/projects/-work/*.jsonl"))

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
# Counting API/network failures by searching transcript text is WRONG and was removed.
# A substring scan for "429"/"529"/"balance" matches digits inside `—` escapes ("—29"
# contains "429") and ordinary prose ("unbalanced" contains "balance"). Measured that way,
# ctags 6.11 appeared to show a 429 cascade in the minutes before its agents stopped -- pure
# artifact. Structured markers give the real answer: ZERO API errors in both 6.10 and 6.11.
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
per_agent = collections.Counter()
cats = collections.Counter()
tools = collections.Counter()
errs = collections.Counter()
stamps = []
issue_opened = 0
pr_opened = 0

for f in files:
    agent = f.split("/hermes/")[1].split("/")[0] if "/hermes/" in f else "?"
    try:
        fh = open(f, errors="replace")
    except OSError:
        continue
    for line in fh:
        try:
            d = json.loads(line)
        except Exception:
            continue
        ts = d.get("timestamp")
        if ts:
            stamps.append(ts[:19])
        if d.get("type") == "assistant":
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

# FREEZE DETECTION. A whole-stack outage is invisible in (last - first): on 2026-08-12 all
# four stacks froze 43 min and still reported a 329-360 min span. Measure the HOLES: sort every
# timestamp in the trajectory and find gaps where NO agent produced anything. active_min is the
# span minus those holes -- the time actually worked.
GAP_MIN = 5.0
# A freeze at the END of a run leaves no gap -- the span simply stops short of the budget.
# ctags/pandoc/gromacs on 2026-08-12 look exactly like that (max_gap 0, but 31-41 min missing),
# while ffmpeg shows the same outage as a 43-minute hole. Report BOTH or half the cases hide.
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
    "agents": len(files),
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
    "subissue_opened": issue_opened,
    "subissue_landed": landed,
    "pr_opened": pr_opened,
    "pr_merged": pr_merged,
    "branches": branches,
    "total_tool_calls": total_calls,
    "activity_pct": activity,
    "turns_by_agent": dict(per_agent),
    "proxy_metrics": [
        "subissue_opened -- LOWER BOUND, often badly wrong. Leads frequently write a python "
        "script that loops `curl -X {method} {url}`, so ONE tool call creates N issues and the "
        "literal '-X POST' never appears. ctags 6.11 reports 2 against ~34 real sub-issues. "
        "No transcript regex can fix this; the exact source is Gitea's issue table.",
        "pr_opened -- same defect, same cause. `branches` and `pr_merged` are the exact figures "
        "and should be preferred for any comparison.",
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
    print(f"  sub-issues opened     {out['subissue_opened']}  (LOWER BOUND — unreliable)")
    print(f"  sub-issues landed     {out['subissue_landed']}   (src/ci-list.txt)")
    print(f"  PRs opened            {out['pr_opened']}  (LOWER BOUND — unreliable)")
    print(f"  PRs merged            {out['pr_merged']}")
    print(f"  branches              {out['branches']}")
    print(f"  tool calls            {out['total_tool_calls']}")
    print("  activity:")
    for k, v in sorted(activity.items(), key=lambda kv: -kv[1]):
        print(f"      {k:<18} {v:5.1f}%")
    print("  NOTE: opened counts are lower bounds — one tool call can create many issues via a")
    print("        loop script. Use `landed`, `merged` and `branches` for comparisons.")
PY
