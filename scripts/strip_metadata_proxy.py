#!/usr/bin/env python3
# Relay model HTTP requests, removing unsupported metadata/Responses reasoning data.
# Optionally inject the upstream credential; buffer complete responses and retry
# selected transient failures before returning the upstream status and body.

import json, os, sys, time, http.server, urllib.request, urllib.error

UPSTREAM = os.environ.get("UPSTREAM", "").strip()
if not UPSTREAM:
    sys.exit("FATAL: UPSTREAM is not set (the LLM endpoint to forward to)")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "4180"))
LISTEN_HOST = os.environ.get("LISTEN_HOST", "127.0.0.1")
UPSTREAM_AUTH_TOKEN = os.environ.get("UPSTREAM_AUTH_TOKEN", "").strip()
UPSTREAM_AUTH_STYLE = os.environ.get("UPSTREAM_AUTH_STYLE", "bearer").strip().lower()
HOP_BY_HOP = {"connection", "keep-alive", "proxy-connection", "te", "trailer",
              "transfer-encoding", "upgrade", "content-length"}


def _timed_out(e):
    r = e.reason if isinstance(e, urllib.error.URLError) else e
    return isinstance(r, TimeoutError)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):    self._proxy()
    def do_GET(self):     self._proxy()
    def log_message(self, fmt, *args):
        pass

    def _proxy(self):
        src_ip = self.client_address[0] if self.client_address else "?"
        src_port = self.client_address[1] if self.client_address else 0
        rid = f"{src_ip}:{src_port}#{id(self) & 0xffff:04x}"
        if self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "3")
            self.end_headers()
            self.wfile.write(b"ok\n")
            return
        te = self.headers.get("Transfer-Encoding", "").lower()
        length = int(self.headers.get("Content-Length", "0"))
        ua = self.headers.get("User-Agent", "")[:60]
        if "chunked" in te:
            # Decode incoming chunks before forwarding a fixed Content-Length body.
            chunks = []
            while True:
                line = self.rfile.readline().strip()
                if not line: break
                try:
                    n = int(line.split(b";",1)[0], 16)
                except Exception:
                    break
                if n == 0:
                    while self.rfile.readline().strip():
                        pass
                    break
                chunks.append(self.rfile.read(n))
                self.rfile.readline()
            body = b"".join(chunks)
        else:
            body = self.rfile.read(length) if length else b""
        ct = self.headers.get("Content-Type", "")
        if body and "json" in ct.lower():
            try:
                d = json.loads(body)
                mutated = False
                if isinstance(d, dict):
                    if "metadata" in d:
                        d.pop("metadata", None)
                        mutated = True
                    if "/responses" in self.path:
                        # Drop reasoning replay items and encrypted-content includes.
                        inc = d.get("include")
                        if isinstance(inc, list):
                            keep = [x for x in inc if "encrypted_content" not in str(x)]
                            if len(keep) != len(inc):
                                if keep:
                                    d["include"] = keep
                                else:
                                    d.pop("include", None)
                                mutated = True
                        items = d.get("input")
                        if isinstance(items, list):
                            keep = [it for it in items
                                    if not (isinstance(it, dict) and it.get("type") == "reasoning")]
                            if len(keep) != len(items):
                                d["input"] = keep
                                mutated = True
                if mutated:
                    body = json.dumps(d).encode()
            except Exception as e:
                print(f"[proxy {rid}] json parse skip: {e}", flush=True)

        url = UPSTREAM.rstrip("/") + self.path
        out_headers = {k: v for k, v in self.headers.items()
                       if k.lower() not in HOP_BY_HOP and k.lower() != "host"}
        out_headers["Content-Length"] = str(len(body))
        if UPSTREAM_AUTH_TOKEN:
            # Replace the worker's local credential only when injection is configured.
            out_headers = {k: v for k, v in out_headers.items()
                           if k.lower() not in ("authorization", "x-api-key", "api-key")}
            if UPSTREAM_AUTH_STYLE == "api-key":
                out_headers["api-key"] = UPSTREAM_AUTH_TOKEN
            else:
                out_headers["Authorization"] = f"Bearer {UPSTREAM_AUTH_TOKEN}"

        req = urllib.request.Request(url, data=body, headers=out_headers, method=self.command)

        _attempts = int(os.environ.get("UPSTREAM_RETRY_ATTEMPTS", "4"))
        _backoff = [0, 2, 5, 12]
        resp_headers = []
        err = None
        for _try in range(_attempts):
            try:
                resp = urllib.request.urlopen(req, timeout=600)
            except urllib.error.HTTPError as e:
                status = e.code
                try:
                    resp_body = e.read() or b""
                    resp_headers = e.headers.items()
                except Exception as read_err:
                    try:
                        e.close()
                    except Exception:
                        pass
                    err = read_err
                    break
                if status in (429, 500, 502, 503, 504) and _try < _attempts - 1:
                    _d = _backoff[min(_try, len(_backoff) - 1)] or 1
                    print(f"[proxy {rid}] upstream {status}, retry {_try+1}/{_attempts-1} in {_d}s", flush=True)
                    time.sleep(_d)
                    req = urllib.request.Request(url, data=body, headers=out_headers, method=self.command)
                    continue
                break
            except Exception as e:
                # Do not retry timeouts: the upstream may still be running inference.
                if not _timed_out(e) and _try < _attempts - 1:
                    _d = _backoff[min(_try, len(_backoff) - 1)] or 1
                    print(f"[proxy {rid}] upstream error {e}, retry {_try+1}/{_attempts-1} in {_d}s", flush=True)
                    time.sleep(_d)
                    req = urllib.request.Request(url, data=body, headers=out_headers, method=self.command)
                    continue
                err = e
                break
            try:
                status = resp.status
                resp_body = resp.read()
                resp_headers = resp.getheaders()
            except Exception as e:
                resp.close()
                err = e
            break
        if err is not None:
            self.send_error(502, f"proxy error: {err}")
            print(f"[proxy {rid}] {self.command} {self.path} in={len(body)}b({length}CL,{'chunked' if 'chunked' in te else 'plain'}) UA={ua!r} -> BAD: {err}", flush=True)
            return

        print(f"[proxy {rid}] {self.command} {self.path} in={len(body)}b({length}CL,{'chunked' if 'chunked' in te else 'plain'}) UA={ua!r} -> {status} out={len(resp_body)}b", flush=True)
        if status >= 400:
            try:
                _rb = body.decode('utf-8', 'replace')[:400]
                _resp = resp_body[:400].decode('utf-8','replace')
                print(f"[proxy {rid}]   REQ({len(body)}b): {_rb}", flush=True)
                print(f"[proxy {rid}]   RESP({len(resp_body)}b): {_resp}", flush=True)
            except Exception:
                pass
        self.send_response(status)
        for k, v in resp_headers:
            if k.lower() in HOP_BY_HOP: continue
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(resp_body)))
        try:
            self.end_headers()
            self.wfile.write(resp_body)
            self.wfile.flush()
        except Exception as e:
            print(f"[proxy {rid}] CLIENT GONE before the response was written: {e}",
                  flush=True)

if __name__ == "__main__":
    addr = (LISTEN_HOST, LISTEN_PORT)
    auth_note = f" +auth-inject({UPSTREAM_AUTH_STYLE})" if UPSTREAM_AUTH_TOKEN else ""
    print(f"strip-metadata proxy: listening on http://{addr[0]}:{addr[1]} -> {UPSTREAM}{auth_note}")
    http.server.ThreadingHTTPServer(addr, Handler).serve_forever()
