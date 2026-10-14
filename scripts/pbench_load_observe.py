#!/usr/bin/env python3
"""pbench_load_observe.py — sample gitea, mattermost and board under load.

WHY A SEPARATE PROBE
The agents' own success rate cannot tell you which service is the wall. A slow
turn shows up identically whether gitea is serialising writes, mattermost is out
of file descriptors, or the board's pool is queueing -- and at 1000 agents all
three are plausible. This samples each service directly, on a fixed cadence,
independent of what the fleet happens to be doing, so the three curves can be
compared against one another and against the agent count.

WHY IT RUNS IN-CLUSTER
A `kubectl port-forward` is a single TCP connection through the API server. Under
a 1000-agent stack it becomes the slowest hop in the path, and every latency
number would be measuring the tunnel. This is meant to be deployed as a pod in
the same namespace, reaching gitea:3000 / mattermost:8065 / board-service:8660
exactly as an agent does.

WHAT IT SAMPLES, AND WHY EACH ONE
  gitea   read   GET  /api/v1/repos/{org}/{repo}/issues     -- the common query
  gitea   write  POST /api/v1/repos/{org}/{repo}/issues/{n}/comments
                 Reads and writes are reported SEPARATELY because that is the
                 whole question: sqlite serialises writers while readers proceed,
                 so a read-only probe would show a healthy service right up to
                 the point the fleet stalls.
  mm      read   GET  /api/v4/users/me
  board   read   POST /board/{id}/read     -- what every agent turn renders
  board   write  POST /board/{id}/write    -- the append path, which is where
                 the 2k-entry cap and the pool contend

Output is one JSON object per sample per target, appended to --out, so a run can
be cut at any point and still be analysed.

Usage (in-cluster):
  python3 pbench_load_observe.py --org pbench --repo main --seconds 900 \
      --interval 5 --out /data/observe.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request

GITEA = os.environ.get("GITEA_HOST", "http://gitea:3000")
MM = os.environ.get("MATTERMOST_HOST", "http://mattermost:8065")
BOARD = os.environ.get("BOARD_SERVICE_URL", "http://board-service:8660")
BOARD_ID = os.environ.get("BOARD_QUEUE_ID", "pbench-top")
TOKEN = os.environ.get("GITEA_TOKEN", "")
MM_TOKEN = os.environ.get("MATTERMOST_TOKEN", "")


def call(method: str, url: str, headers: dict, body: bytes | None, timeout: float):
    """-> (ok, http_status, elapsed_ms). Never raises: a timeout IS the datum."""
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read(2048)
            return True, r.status, (time.monotonic() - t0) * 1000
    except urllib.error.HTTPError as e:
        # A 4xx/5xx is a real answer and its latency counts; it is not an outage.
        return False, e.code, (time.monotonic() - t0) * 1000
    except Exception:
        return False, 0, (time.monotonic() - t0) * 1000


def targets(org: str, repo: str, issue: int, agent: str):
    """Every URL and payload here must be verified against a live stack before it
    is written down. A guessed endpoint returns 405/404/401/500 for an entire run
    -- and when the one that happens to be right (gitea read) needs no auth, the
    output looks like a working probe reporting a healthy service. A probe that
    cannot fail visibly is worse than no probe.

    The board identifies its caller and authorises against board membership, so
    the probe borrows a REAL agent name: "observer" gets 403. That also makes
    these calls traverse exactly the path an agent's calls do.
    """
    j = {"Content-Type": "application/json"}
    gh = dict(j, **({"Authorization": f"token {TOKEN}"} if TOKEN else {}))
    mh = dict(j, **({"Authorization": f"Bearer {MM_TOKEN}"} if MM_TOKEN else {}))
    stamp = str(int(time.time() * 1000))
    return [
        ("gitea.read", "GET", f"{GITEA}/api/v1/repos/{org}/{repo}/issues?limit=20", gh, None),
        ("gitea.write", "POST", f"{GITEA}/api/v1/repos/{org}/{repo}/issues/{issue}/comments", gh,
         json.dumps({"body": f"observe probe {stamp}"}).encode()),
        ("mm.read", "GET", f"{MM}/api/v4/users/me", mh, None),
        ("board.read", "GET", f"{BOARD}/board/{BOARD_ID}/read_all?viewer={agent}", j, None),
        ("board.write", "POST", f"{BOARD}/board/{BOARD_ID}/note", j,
         json.dumps({"thread_id": agent, "type": "OBSERVED",
                     "content": f"probe {stamp}"}).encode()),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", default=os.environ.get("ORG_NAME", "pbench"))
    ap.add_argument("--repo", default="main")
    ap.add_argument("--issue", type=int, default=1, help="issue to comment on for the write probe")
    ap.add_argument("--seconds", type=int, default=600)
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--agents", type=int, default=0, help="recorded with each sample")
    ap.add_argument("--agent", default=os.environ.get("OBS_AGENT", "pbench-worker1"),
                help="board identity; must be a board member (see targets())")
    ap.add_argument("--out", default="-")
    a = ap.parse_args()

    out = sys.stdout if a.out == "-" else open(a.out, "a", buffering=1)
    hist: dict[str, list[float]] = {}
    errs: dict[str, int] = {}
    n: dict[str, int] = {}
    end = time.monotonic() + a.seconds

    while time.monotonic() < end:
        cycle = time.monotonic()
        for name, method, url, headers, body in targets(a.org, a.repo, a.issue, a.agent):
            ok, status, ms = call(method, url, headers, body, a.timeout)
            hist.setdefault(name, []).append(ms)
            n[name] = n.get(name, 0) + 1
            if not ok:
                errs[name] = errs.get(name, 0) + 1
            print(json.dumps({
                "t": round(time.time(), 3), "target": name, "agents": a.agents,
                "ok": ok, "status": status, "ms": round(ms, 1),
            }), file=out)
        # Sleep the REMAINDER: a fixed sleep would stretch the cadence by however
        # long the probes took, which is exactly when the service is slowest --
        # so the sampling rate would fall off precisely where resolution matters.
        rest = a.interval - (time.monotonic() - cycle)
        if rest > 0:
            time.sleep(rest)

    for name in sorted(hist):
        v = sorted(hist[name])
        p = lambda q: v[min(len(v) - 1, int(len(v) * q))]
        print(json.dumps({
            "summary": name, "agents": a.agents, "n": n[name],
            "err": errs.get(name, 0),
            "err_rate": round(errs.get(name, 0) / max(1, n[name]), 4),
            "p50": round(statistics.median(v), 1), "p90": round(p(0.90), 1),
            "p99": round(p(0.99), 1), "max": round(v[-1], 1),
        }), file=out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
