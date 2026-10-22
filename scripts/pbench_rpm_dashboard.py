#!/usr/bin/env python3
# Observe running profile request rates from egress-proxy logs and cgroup counters.
# Separate client completions from gateway hits including retries, and retain
# completed minute buckets for the dashboard's twelve-hour chart.

import argparse
import json
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOW = 60
POLL = 10
BUCKET_READ = 150
CHART_MINUTES = 720
CEILING_UPSTREAM = ""

STATUS_RE = re.compile(r"->\s+(\d{3}|BAD)\b")
REQ_RE = re.compile(r"\]\s+(POST|GET)\s+(\S+)")
RETRY_RE = re.compile(r"\]\s+upstream\s.*, retry \d+/\d+ in ")

STATE_FILE = Path("/tmp/pbench_rpm_state.json")
_state = {"stacks": {}, "groups": {}, "updated": None, "error": None}
try:
    _saved = json.loads(STATE_FILE.read_text())
    for _key in ("minutes_by_upstream", "gateway_minutes_by_upstream"):
        _state[_key] = {
            u: {int(k): v for k, v in d.items()}
            for u, d in _saved.get(_key, {}).items()}
except Exception:
    _state["minutes_by_upstream"] = {}
    _state["gateway_minutes_by_upstream"] = {}
_lock = threading.Lock()


def sh(args, timeout=25):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.stdout
    except Exception:
        return ""


def profile_of(project):
    return project[len("omcgitea-"):] if project.startswith("omcgitea-pbench-") else None


def stacks_on_host():
    out = sh(["docker", "ps", "--no-trunc", "--format",
              '{{.ID}}\t{{.Names}}\t{{.Label "com.docker.compose.project"}}'])
    by = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        cid, name, project = parts
        prof = profile_of(project)
        if not prof:
            continue
        st = by.setdefault(prof, {"proxy": None, "cids": []})
        st["cids"].append(cid)
        if "egress-proxy" in name:
            st["proxy"] = name
    return by


def env_val(profile, key):
    try:
        for line in (ROOT / f".env.{profile}").read_text().splitlines():
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def upstream_of(profile):
    u = env_val(profile, "PBENCH_LLM_UPSTREAM")
    return re.sub(r"^https?://", "", u).rstrip("/") or "unknown"


def workers_of(profile):
    w = env_val(profile, "PBENCH_WORKERS_PER_TEAM")
    return int(w) if w.isdigit() else 0


SLICE = Path("/sys/fs/cgroup/pbench.slice")


def pids_of(cids):
    total = 0
    for cid in cids:
        try:
            total += int((SLICE / f"docker-{cid}.scope" / "pids.current").read_text())
        except Exception:
            pass
    return total


def slice_pids():
    try:
        cur = int((SLICE / "pids.current").read_text())
        mx = (SLICE / "pids.max").read_text().strip()
        return cur, (int(mx) if mx.isdigit() else 0)
    except Exception:
        return 0, 0


def sample_one(container):
    # These are log-derived rates, not a direct measurement of upstream concurrency.
    raw = sh(["docker", "logs", "--since", f"{BUCKET_READ}s", "--timestamps", container])
    now = datetime.now(timezone.utc)
    n = inflight = retries = 0
    codes, agents, buckets, hits = {}, set(), {}, {}
    for line in raw.splitlines():
        if " POST " not in line and " GET " not in line and " retry " not in line:
            continue
        retry = RETRY_RE.search(line)
        if not retry and not REQ_RE.search(line):
            continue
        try:
            ts = datetime.fromisoformat(line.split(" ", 1)[0].replace("Z", "+00:00"))
        except Exception:
            continue
        age = (now - ts).total_seconds()
        minute = int(ts.timestamp()) // 60
        hits[minute] = hits.get(minute, 0) + 1
        if retry:
            if age <= WINDOW:
                retries += 1
            continue
        buckets[minute] = buckets.get(minute, 0) + 1
        if age > WINDOW:
            continue
        n += 1
        m = STATUS_RE.search(line)
        if m:
            codes[m.group(1)] = codes.get(m.group(1), 0) + 1
        else:
            inflight += 1
        a = re.search(r"\[proxy ([\d.]+):", line)
        if a:
            agents.add(a.group(1))
    return {"rpm": n, "inflight": inflight, "codes": codes,
            "retries": retries, "gateway_rpm": n + retries,
            "active_agents": len(agents), "buckets": buckets, "gateway_buckets": hits}


def _merge_up(stacks, key, first_full, cur_min):
    merged_up = {}
    for d in stacks.values():
        up = d.get("upstream", "unknown")
        tgt = merged_up.setdefault(up, {})
        for mn, c in d.get(key, {}).items():
            if first_full <= mn < cur_min:
                tgt[mn] = tgt.get(mn, 0) + c
    return merged_up


def _store_up(state_key, merged_up):
    # Poll windows overlap; keep the largest complete count rather than adding twice.
    mbu = _state.setdefault(state_key, {})
    for _up, _d in merged_up.items():
        _t = mbu.setdefault(_up, {})
        for _k, _v in _d.items():
            _t[_k] = max(_t.get(_k, 0), _v)
        for _k in sorted(_t)[:-CHART_MINUTES]:
            del _t[_k]
    return mbu


def sampler(only_upstream):
    while True:
        try:
            stacks = {}
            for s, st in stacks_on_host().items():
                if not st["proxy"]:
                    continue
                up = upstream_of(s)
                if only_upstream and only_upstream not in up:
                    continue
                d = sample_one(st["proxy"])
                d["upstream"] = up
                d["workers"] = workers_of(s)
                d["pids"] = pids_of(st["cids"])
                d["containers"] = len(st["cids"])
                stacks[s] = d
            groups = {}
            for s, d in stacks.items():
                g = groups.setdefault(d["upstream"], {"rpm": 0, "gateway_rpm": 0, "stacks": [],
                                                      "errors": 0, "workers": 0})
                g["rpm"] += d["rpm"]
                g["gateway_rpm"] += d["gateway_rpm"]
                g["workers"] += d["workers"]
                g["stacks"].append(s)
                g["errors"] += sum(v for k, v in d["codes"].items() if k != "200")
            with _lock:
                _state["stacks"] = stacks
                _state["groups"] = groups
                now_t = time.time()
                # Exclude partial boundary minutes before persisting chart history.
                first_full = int((now_t - BUCKET_READ) // 60) + 1
                cur_min = int(now_t) // 60
                merged_up = _merge_up(stacks, "buckets", first_full, cur_min)
                mbu = _store_up("minutes_by_upstream", merged_up)
                gmbu = _store_up("gateway_minutes_by_upstream",
                                 _merge_up(stacks, "gateway_buckets", first_full, cur_min))
                try:
                    STATE_FILE.write_text(json.dumps({
                        "minutes_by_upstream": {
                            u: {str(k): v for k, v in d.items()}
                            for u, d in mbu.items()},
                        "gateway_minutes_by_upstream": {
                            u: {str(k): v for k, v in d.items()}
                            for u, d in gmbu.items()},
                    }))
                except Exception:
                    pass
                _state["slice_pids"], _state["slice_max"] = slice_pids()
                _state["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                _state["error"] = None
        except Exception as e:
            with _lock:
                _state["error"] = str(e)
        time.sleep(POLL)


PAGE = """<!DOCTYPE html><meta charset="utf-8"><title>pbench RPM</title>
<meta http-equiv="refresh" content="10">
<style>
 body{background:#fcfcfb;color:#0b0b0b;font:14px/1.45 ui-sans-serif,system-ui,-apple-system,sans-serif;
      margin:0;padding:26px 30px;max-width:1080px}
 @media(prefers-color-scheme:dark){body{background:#1a1a19;color:#fff}
   .card{background:#222221!important;border-color:#333!important}
   th{color:#918f85!important} td{border-color:#2b2b29!important}}
 h1{font-size:17px;margin:0 0 3px;font-weight:600}
 .sub{color:#7a7873;font-size:12.5px;margin:0 0 18px}
 .card{border:1px solid #e9e8e4;border-radius:9px;padding:15px 17px;margin:0 0 14px;background:#fff}
 .big{font-size:30px;font-weight:700;letter-spacing:-.02em}
 .bar{height:11px;border-radius:6px;background:#e9e8e4;overflow:hidden;margin:9px 0 5px}
 .fill{height:100%;border-radius:6px;transition:width .4s}
 table{border-collapse:collapse;width:100%;font-size:13px}
 th{text-align:left;font-weight:600;font-size:11px;text-transform:uppercase;
    letter-spacing:.04em;color:#7a7873;padding:0 10px 6px 0}
 td{padding:5px 10px 5px 0;border-top:1px solid #eee;font-variant-numeric:tabular-nums}
 .warn{color:#cc4125;font-weight:700} .ok{color:#1baf7a;font-weight:600}
 .muted{color:#7a7873;font-size:11.5px}
 .gw{stroke:#eb6834} .sw.gw{background:#eb6834}
 @media(prefers-color-scheme:dark){.gw{stroke:#d95926} .sw.gw{background:#d95926}}
 .sw{display:inline-block;width:14px;height:2px;vertical-align:middle;margin:0 4px 0 6px}
 svg{display:block}
</style>
<body>__BODY__</body>"""


def render():
    with _lock:
        st = json.loads(json.dumps(_state))
    limit = st.get("limit", 600)
    ep = st.get("upstream_filter") or "all gateways"
    parts = [f"<h1>ProgramBench &mdash; requests per minute &middot; {ep}</h1>"]
    parts.append(f'<p class="sub">{WINDOW}s trailing window, sampled every {POLL}s from each '
                 f'stack&rsquo;s egress-proxy. Only stacks pointed at <b>{ep}</b> are counted &mdash; '
                 f'other sweeps run against a different gateway and do not share this ceiling. '
                 f'Updated {st.get("updated") or "never"}.</p>')
    if st.get("error"):
        parts.append(f'<div class="card warn">sampler error: {st["error"]}</div>')
    if not st["stacks"]:
        parts.append(f'<div class="card">No running stack points at <b>{ep}</b>.</div>')

    for up, g in sorted(st["groups"].items(), key=lambda kv: -kv[1]["rpm"]):
        rpm, hits = g["rpm"], g.get("gateway_rpm", g["rpm"])
        pct = 100.0 * hits / limit if limit else 0
        colour = "#cc4125" if pct >= 85 else ("#d1922b" if pct >= 60 else "#1baf7a")
        errs = g["errors"]
        parts.append(f"""<div class="card">
          <div class="muted">{up} &middot; {len(g['stacks'])} stack(s) &middot; {g['workers']} agents</div>
          <div class="big" style="color:{colour}">{rpm} <span style="font-size:15px;font-weight:500;color:#7a7873">req/min &nbsp;/&nbsp; {limit} ceiling</span></div>
          <div class="bar"><div class="fill" style="width:{min(100.0,pct):.1f}%;background:{colour}"></div></div>
          <div class="muted">{pct:.0f}% of ceiling ({hits} gateway hits/min, {hits - rpm} of them proxy retries) &middot; {'<span class="warn">' + str(errs) + ' non-200 in window</span>' if errs else '<span class="ok">no errors</span>'}</div>
        </div>""")

    cur, mx = st.get("slice_pids", 0), st.get("slice_max", 0)
    if mx:
        ppct = 100.0 * cur / mx
        pcol = "#cc4125" if ppct >= 85 else ("#d1922b" if ppct >= 65 else "#1baf7a")
        shown = sum(d.get("pids", 0) for d in st["stacks"].values())
        other = max(0, cur - shown)
        parts.append(f"""<div class="card">
          <div class="muted">pbench.slice TasksMax &mdash; host-wide, NOT scoped to this endpoint
            (other sweeps share it)</div>
          <div class="big" style="color:{pcol}">{cur:,} <span style="font-size:15px;font-weight:500;color:#7a7873">tasks &nbsp;/&nbsp; {mx:,} cap</span></div>
          <div class="bar"><div class="fill" style="width:{min(100.0,ppct):.1f}%;background:{pcol}"></div></div>
          <div class="muted">{ppct:.0f}% of cap &middot; {shown:,} from stacks shown here &middot;
            {other:,} from other sweeps &middot; counts THREADS, ~423/agent</div>
        </div>""")

    rows = ["<tr><th>stack</th><th>agents</th><th>req/min</th><th>gw hits</th><th>per agent</th>"
            "<th>active</th><th>no status</th><th>pids</th><th>per agent</th>"
            "<th>ctrs</th><th>status</th></tr>"]
    for s, d in sorted(st["stacks"].items(), key=lambda kv: -kv[1]["rpm"]):
        per = d["rpm"] / d["workers"] if d["workers"] else 0
        codes = " ".join(f'{k}&times;{v}' for k, v in sorted(d["codes"].items())) or "&mdash;"
        bad = any(k != "200" for k in d["codes"])
        pd = d.get("pids", 0)
        pper = pd / d["workers"] if d["workers"] else 0
        rows.append(f'<tr><td><b>{s}</b></td><td>{d["workers"] or "?"}</td><td>{d["rpm"]}</td>'
                    f'<td>{d.get("gateway_rpm", d["rpm"])}</td>'
                    f'<td>{per:.2f}</td><td>{d["active_agents"]}</td><td>{d["inflight"]}</td>'
                    f'<td>{pd:,}</td><td>{pper:.0f}</td><td>{d.get("containers",0)}</td>'
                    f'<td class="{"warn" if bad else ""}">{codes}</td></tr>')
    parts.append(f'<div class="card"><table>{"".join(rows)}</table></div>')

    mbu = {u: {int(k): v for k, v in d.items()}
           for u, d in st.get("minutes_by_upstream", {}).items()}
    ceil_up = next((u for u in mbu if CEILING_UPSTREAM and CEILING_UPSTREAM in u), None)
    mins = mbu.get(ceil_up, {}) if ceil_up else {}
    gmins = ({int(k): v for k, v in
              st.get("gateway_minutes_by_upstream", {}).get(ceil_up, {}).items()}
             if ceil_up else {})
    chart_label = ceil_up or "(no rate-limited upstream present)"
    now_min = int(time.time()) // 60
    span = CHART_MINUTES
    x0 = now_min - span
    pts = sorted((k, v) for k, v in mins.items() if k > x0)
    vals = [v for _, v in pts]
    peak = max(vals) if vals else 0
    mean = sum(vals) / len(vals) if vals else 0
    gpts = sorted((k, v) for k, v in gmins.items() if k > x0)
    gpeak = max((v for _, v in gpts), default=0)
    top = float(limit)
    w, h = 1020, 190
    ceil_y = 1.0
    yv = lambda v: h - (min(v, top) / top) * h

    def polylines(series, stroke):
        segs, cur = [], []
        prev = None
        for k, v in series:
            if prev is not None and k != prev + 1:
                if len(cur) > 1:
                    segs.append(cur)
                cur = []
            cur.append(((k - x0) / span * w, yv(v)))
            prev = k
        if len(cur) > 1:
            segs.append(cur)
        return "".join(
            f'<polyline fill="none" {stroke} stroke-width="1.8" '
            f'stroke-linejoin="round" points="{" ".join(f"{x:.2f},{y:.2f}" for x, y in sg)}"/>'
            for sg in segs)
    poly = polylines(gpts, 'class="gw"') + polylines(pts, 'stroke="#2b6cb0"')

    yticks = "".join(
        f'<line x1="0" y1="{h-(t/top)*h:.1f}" x2="{w}" y2="{h-(t/top)*h:.1f}" '
        f'stroke="currentColor" opacity=".10"/>'
        f'<text x="2" y="{max(9, h-(t/top)*h-3):.1f}" font-size="9" fill="currentColor" '
        f'opacity=".55">{int(t)}</text>'
        for t in (0, limit * 0.25, limit * 0.5, limit * 0.75))

    grid = "".join(
        f'<line x1="{i/12*w:.1f}" y1="0" x2="{i/12*w:.1f}" y2="{h}" stroke="currentColor" '
        f'opacity=".08"/><text x="{i/12*w+3:.1f}" y="{h-4}" font-size="9" '
        f'fill="currentColor" opacity=".45">-{12-i}h</text>'
        for i in range(12))

    rd, gd = dict(pts), dict(gpts)
    data = json.dumps([[k, rd.get(k), gd.get(k)] for k in sorted(set(rd) | set(gd))])
    parts.append(f"""<div class="card">
      <div class="muted">requests per minute &mdash; <b>{chart_label}</b> only
        (the gateway that advertises the {limit}/min ceiling; other arms run against an
        uncapped gateway and are NOT summed in here) &middot; fixed 12h window
        &middot; peak <b>{peak}</b> &middot; mean {mean:.0f} &middot; {len(vals)} min of data
        &middot; gateway peak <b>{gpeak}</b><br>
        <span class="sw" style="background:#2b6cb0"></span>client requests
        <span class="sw gw"></span>gateway hits, proxy retries included (what the ceiling counts)</div>
      <div style="position:relative">
        <svg id="chart" data-chart-max="{int(top)}" data-gateway-limit="{int(limit)}"
             width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="cursor:crosshair">
          {grid}{yticks}
          <line x1="0" y1="{ceil_y:.1f}" x2="{w}" y2="{ceil_y:.1f}" stroke="#cc4125"
                stroke-width="1" stroke-dasharray="5 4" opacity=".85"/>
          {poly}
          <line id="guide" x1="0" y1="0" x2="0" y2="{h}" stroke="#cc4125"
                stroke-width="1" opacity="0"/>
          <circle id="dot" r="3.5" fill="#cc4125" opacity="0"/>
          <rect id="hit" x="0" y="0" width="{w}" height="{h}" fill="transparent"/>
        </svg>
        <div id="tip" style="position:absolute;pointer-events:none;opacity:0;
             background:var(--surface-1,#fff);border:1px solid #c9c8c3;border-radius:6px;
             padding:5px 9px;font-size:12px;white-space:nowrap;
             box-shadow:0 3px 10px rgba(0,0,0,.16);transition:opacity .08s"></div>
      </div>
    </div>
    <script>
    (function(){{
      const D={data}, W={w}, H={h}, X0={x0}, SPAN={span}, TOP={top:.4f};
      const svg=document.getElementById('chart'), g=document.getElementById('guide'),
            dot=document.getElementById('dot'), tip=document.getElementById('tip'),
            hit=document.getElementById('hit');
      if(!D.length) return;
      const xOf=k=>(k-X0)/SPAN*W, yOf=v=>H-(Math.min(v,TOP)/TOP)*H;
      hit.addEventListener('mousemove',e=>{{
        const r=svg.getBoundingClientRect();
        const mx=(e.clientX-r.left)*(W/r.width);
        let best=D[0], bd=1e9;
        for(const p of D){{ const d=Math.abs(xOf(p[0])-mx); if(d<bd){{bd=d;best=p;}} }}
        const v=best[1]??0, gv=best[2]??v;
        const px=xOf(best[0]), py=yOf(v);
        g.setAttribute('x1',px); g.setAttribute('x2',px); g.setAttribute('opacity','.7');
        dot.setAttribute('cx',px); dot.setAttribute('cy',py); dot.setAttribute('opacity','1');
        const t=new Date(best[0]*60000);
        const hh=String(t.getUTCHours()).padStart(2,'0'),
              mm=String(t.getUTCMinutes()).padStart(2,'0');
        tip.innerHTML='<b>'+v+'</b> req/min &middot; '+gv+' gateway hits &middot; '+hh+':'+mm+' UTC'
                      +(gv>TOP?' <span style="color:#cc4125">over ceiling</span>':'');
        tip.style.opacity='1';
        tip.style.left=Math.min(px*(r.width/W)+12, r.width-150)+'px';
        tip.style.top=Math.max(0, py*(r.height/H)-34)+'px';
      }});
      hit.addEventListener('mouseleave',()=>{{
        g.setAttribute('opacity','0'); dot.setAttribute('opacity','0'); tip.style.opacity='0';
      }});
    }})();
    </script>""")
    return PAGE.replace("__BODY__", "".join(parts))


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/":
            self.send_error(404)
            return
        body = render().encode()
        ctype = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=19500)
    ap.add_argument("--limit", type=int, default=600,
                    help="gateway ceiling, its advertised x-ratelimit-limit-requests")
    ap.add_argument("--ceiling-upstream", default=None,
                    help="which upstream the --limit ceiling applies to (default: "
                         "--upstream); only this one is charted against it")
    ap.add_argument("--upstream", required=True,
                    help="only show stacks whose PBENCH_LLM_UPSTREAM contains this "
                         "(host:port); pass '' for every gateway")
    a = ap.parse_args()
    _state["limit"] = a.limit
    _state["upstream_filter"] = a.upstream
    global CEILING_UPSTREAM
    CEILING_UPSTREAM = a.upstream if a.ceiling_upstream is None else a.ceiling_upstream
    threading.Thread(target=sampler, args=(a.upstream,), daemon=True).start()
    print(f"pbench RPM dashboard -> http://localhost:{a.port}   "
          f"(ceiling {a.limit}/min, endpoint {a.upstream or 'ALL'})")
    ThreadingHTTPServer(("0.0.0.0", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
