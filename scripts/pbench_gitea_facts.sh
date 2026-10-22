#!/usr/bin/env bash
# Read issue/PR counts and integration timings from an archived Gitea SQLite DB.
# Accept a trajectory directory and optional --json; the database is opened read-only.
set -u

TRAJ="${1:-}"
JSON=0
[ "${2:-}" = "--json" ] && JSON=1
[ "${1:-}" = "--json" ] && { echo "usage: $0 <traj-dir> [--json]" >&2; exit 2; }
if [ -z "$TRAJ" ] || [ ! -d "$TRAJ" ]; then
    echo "FATAL: no such trajectory directory: '${TRAJ:-<none>}'" >&2
    exit 2
fi
DB="$TRAJ/data-root/gitea/gitea/gitea.db"
if ! sudo test -f "$DB"; then
    echo "FATAL: no gitea.db at $DB" >&2
    exit 2
fi

sudo python3 - "$TRAJ" "$DB" "$JSON" <<'PY'
import json, os, sqlite3, statistics, sys

traj, db, as_json = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
q = lambda s, *a: con.execute(s, a).fetchall()
one = lambda s, *a: (q(s, *a) or [[0]])[0][0]

sub_open   = one("select count(*) from issue where is_pull=0")
sub_closed = one("select count(*) from issue where is_pull=0 and is_closed=1")
prs        = one("select count(*) from pull_request")
merged     = one("select count(*) from pull_request where has_merged=1")
closed_unmerged = one("""select count(*) from pull_request p join issue i on i.id=p.issue_id
                         where p.has_merged!=1 and i.is_closed=1""")
still_open      = one("""select count(*) from pull_request p join issue i on i.id=p.issue_id
                         where p.has_merged!=1 and i.is_closed=0""")

lat = [(m - c) / 60.0 for m, c in q("""select p.merged_unix, i.created_unix
                                       from pull_request p join issue i on i.id=p.issue_id
                                       where p.has_merged=1 and p.merged_unix>0""")]
lat.sort()
life = [(cl - cr) / 60.0 for cl, cr in q("""select closed_unix, created_unix from issue
                                            where is_pull=0 and is_closed=1 and closed_unix>0""")]
life.sort()
comments = one("select coalesce(sum(num_comments),0) from issue")

out = {
    "trajectory": os.path.basename(traj.rstrip("/")),
    "subissues_opened": sub_open,
    "subissues_closed": sub_closed,
    "subissue_close_pct": round(100.0 * sub_closed / sub_open, 1) if sub_open else 0.0,
    "subissue_median_lifetime_min": round(statistics.median(life), 1) if life else 0.0,
    "prs_opened": prs,
    "prs_merged": merged,
    "prs_closed_unmerged": closed_unmerged,
    "prs_open_at_end": still_open,
    "pr_merge_pct": round(100.0 * merged / prs, 1) if prs else 0.0,
    "pr_median_open_to_merge_min": round(statistics.median(lat), 1) if lat else 0.0,
    "pr_p90_open_to_merge_min": round(lat[int(0.9 * (len(lat) - 1))], 1) if lat else 0.0,
    "total_comments": comments,
    "source": "gitea.db (issue, pull_request) — exact, read-only",
}

if as_json:
    print(json.dumps(out, indent=2, sort_keys=True))
else:
    print(f"=== {out['trajectory']} ===")
    print(f"  sub-issues opened     {out['subissues_opened']}")
    print(f"  sub-issues closed     {out['subissues_closed']}  ({out['subissue_close_pct']}%)")
    print(f"  median sub-issue life {out['subissue_median_lifetime_min']} min")
    print(f"  PRs opened            {out['prs_opened']}")
    print(f"  PRs merged            {out['prs_merged']}  ({out['pr_merge_pct']}%)")
    print(f"  PRs closed unmerged   {out['prs_closed_unmerged']}")
    print(f"  PRs still open at end {out['prs_open_at_end']}")
    print(f"  open->merge median    {out['pr_median_open_to_merge_min']} min   p90 {out['pr_p90_open_to_merge_min']} min")
    print(f"  comments              {out['total_comments']}")
PY
