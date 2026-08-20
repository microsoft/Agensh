#!/usr/bin/env python3
"""board_dump.py <trajectory-dir> [--full] [--reads] [--injections]

Replay the shared-context board from a saved trajectory.

The board itself lived in MySQL inside each profile's DATA_ROOT, which is wiped
between tasks. The .ibd tablespaces survive inside the trajectory but need a
MySQL instance to read; the agents' tool calls are plain JSON, so this
reconstructs from those.

By default prints every board_write with its admission label. Options:
  --full        do not truncate gist content, and print the `detail` body — the
                layer held outside the board and reachable only via unfold
  --reads       also print board_read / board_unfold calls and what came back
  --injections  also print the router's forced-read blocks (the rendered board
                spliced into each prompt). This is the channel agents actually
                consume and it is NOT a tool call, so it is invisible otherwise.

What this still cannot show: server-side dedupe collapsing (the `(xN)`
markers), CLAIM TTL expiry, PATCH_SUMMARY latest-wins replacement, and eviction
when the render window overflows — on the sweep_6 boards roughly 40% of stored
gists never reached anyone's window. "admitted" is not "seen". For that, read
board_gists from the .ibd files with a real MySQL.
"""
import sys, json, os, datetime

args = [a for a in sys.argv[1:] if not a.startswith("--")]
opts = {a for a in sys.argv[1:] if a.startswith("--")}
if not args:
    sys.exit(__doc__.strip())
FULL, READS, INJ = "--full" in opts, "--reads" in opts, "--injections" in opts

root = os.path.expanduser(args[0])
hermes = next((p for p in (os.path.join(root, "data-root", "hermes"),
                           os.path.join(root, "hermes")) if os.path.isdir(p)), None)
if not hermes:
    sys.exit(f"no hermes/ under {root}")

files = []
for dirpath, _, names in os.walk(hermes):
    if "events.jsonl" in names and os.sep + "session-state" + os.sep in dirpath + os.sep:
        files.append(os.path.join(dirpath, "events.jsonl"))

events, outcomes = [], {}
for f in files:
    agent = os.path.relpath(f, hermes).split(os.sep)[0]
    for line in open(f, errors="replace"):
        try:
            e = json.loads(line)
        except Exception:
            continue
        d, ts, t = e.get("data") or {}, e.get("timestamp", ""), e.get("type")
        if t == "tool.execution_complete":
            outcomes[d.get("toolCallId")] = ((d.get("result") or {}).get("content")) or ""
        elif t == "tool.execution_start":
            n = str(d.get("toolName", ""))
            if n.startswith("board-"):
                events.append((ts, n, agent, d.get("arguments") or {}, d.get("toolCallId")))
        elif t == "user.message" and INJ and "SHARED CONTEXT" in json.dumps(d):
            events.append((ts, "_injection", agent, d, None))

events.sort(key=lambda r: r[0])
if not events:
    sys.exit("  (nothing recorded)")
t0 = datetime.datetime.fromisoformat(events[0][0].replace("Z", "+00:00"))

writes = [e for e in events if e[1] == "board-board_write"]
adm = sum('"admitted"' in outcomes.get(e[4], "") for e in writes)
rej = sum('"rejected"' in outcomes.get(e[4], "") for e in writes)
print(f"  {len(writes)} board writes — {os.path.basename(root)}")
print(f"  admitted={adm}  rejected={rej}  unknown={len(writes)-adm-rej}\n")

for ts, kind, agent, a, cid in events:
    m = (datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")) - t0).total_seconds() / 60
    if kind == "_injection":
        txt = json.dumps(a)
        i = txt.find("SHARED CONTEXT")
        print(f"\n  +{m:6.1f}m [{agent}] FORCED-READ block injected into prompt:")
        print("    " + txt[max(0, i - 20): i + (99999 if FULL else 1200)].replace("\\n", "\n    "))
        continue
    res = outcomes.get(cid, "")
    if kind == "board-board_write":
        try:
            r = json.loads(res)
            mark = r.get("label") or f"REJECTED:{r.get('reason')}"
        except Exception:
            mark = "?"
        content = str(a.get("content", ""))
        if not FULL:
            content = " ".join(content.split())[:96]
        dg = f" ({a.get('delegation_id')})" if a.get("delegation_id") else ""
        print(f"  +{m:6.1f}m {mark:20s} {a.get('type','?'):14s} [{agent}]{dg}  {content}")
        if a.get("detail"):
            det = str(a["detail"])
            if FULL:
                print(f"           detail ({len(det)} chars):")
                for ln in det.splitlines():
                    print(f"             {ln}")
            else:
                print(f"           [+detail: {len(det)} chars — use --full to print]")
    elif READS:
        print(f"  +{m:6.1f}m {kind:20s} [{agent}]  args={json.dumps(a)[:140]}")
        if res:
            print(f"           -> {res if FULL else res[:400]}")
