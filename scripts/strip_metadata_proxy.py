#!/usr/bin/env python3
"""Strip-metadata proxy for upstream Claude-API compatible backends that
reject requests carrying Claude Code's metadata.user_id (e.g. some
GitHub Copilot wrappers return 403 + GitHub ToS message).

Listens on 127.0.0.1:4180 by default. Forwards any /v1/* request to
UPSTREAM with the JSON body's `metadata` field removed.

Run: python3 strip_metadata_proxy.py
"""
import json, os, http.server, urllib.request, urllib.error

UPSTREAM = os.environ.get("UPSTREAM", "http://20.9.234.247")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "4180"))
# Bind host. Default 127.0.0.1 keeps the dev/prod same-container sidecar
# behavior unchanged. The pbench profile runs this as a SEPARATE container that
# agents reach via egress-proxy:4180, so it sets LISTEN_HOST=0.0.0.0.
LISTEN_HOST = os.environ.get("LISTEN_HOST", "127.0.0.1")
# Optional auth-header injection: if set, replaces any inbound Authorization /
# x-api-key header on the outgoing request. Purpose: different upstreams need
# different auth styles (Azure FrontDoor: Bearer; Azure AI Foundry: api-key;
# etc.), and the Anthropic SDK inside agents is configured with a fixed
# ANTHROPIC_API_KEY (x-api-key). Injecting here is a single-point rewrite that
# keeps the frozen prod template and per-agent env unchanged.
# UPSTREAM_AUTH_STYLE: "bearer" (default) → `Authorization: Bearer <token>`;
#                     "api-key"          → `api-key: <token>` (Azure AI Foundry).
# When UPSTREAM_AUTH_TOKEN is unset, the proxy is header-transparent.
UPSTREAM_AUTH_TOKEN = os.environ.get("UPSTREAM_AUTH_TOKEN", "").strip()
UPSTREAM_AUTH_STYLE = os.environ.get("UPSTREAM_AUTH_STYLE", "bearer").strip().lower()
# Optional path override: when set, the proxy uses this literal path (query
# string included) for every proxied request, ignoring the inbound self.path.
# Purpose: Azure AI Foundry's OpenAI-compatible endpoint lives at
# `/models/chat/completions?api-version=2024-05-01-preview` while Copilot CLI
# sends `/chat/completions`. This lets a single env var reshape the target URL
# without touching Copilot or the SDK. When unset, self.path is used verbatim.
UPSTREAM_PATH_OVERRIDE = os.environ.get("UPSTREAM_PATH_OVERRIDE", "").strip()

class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):    self._proxy()
    def do_GET(self):     self._proxy()
    def do_PUT(self):     self._proxy()
    def do_DELETE(self):  self._proxy()
    def log_message(self, fmt, *args):
        # Silence stdlib per-request access log — the default writes partial
        # lines that interleave badly under ThreadingHTTPServer. _proxy emits
        # a single atomic summary line per request instead.
        pass

    def _proxy(self):
        # rid tags every log line for one request so concurrent threads
        # (5+ agents pounding /chat/completions) don't produce ambiguous logs.
        src_ip = self.client_address[0] if self.client_address else "?"
        src_port = self.client_address[1] if self.client_address else 0
        rid = f"{src_ip}:{src_port}#{id(self) & 0xffff:04x}"
        # Short-circuit the container healthcheck. compose fires
        # GET /healthz every 10s from 127.0.0.1; forwarding it upstream burns
        # a FrontDoor round-trip AND floods the log with unrelated 404s that
        # look like chat traffic under casual inspection. Answer locally.
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
            # BaseHTTPRequestHandler doesn't decode chunked bodies. Read the
            # chunked stream manually: <hex-size>\r\n<data>\r\n ... 0\r\n\r\n
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
                self.rfile.readline()  # trailing CRLF after chunk
            body = b"".join(chunks)
        else:
            body = self.rfile.read(length) if length else b""
        ct = self.headers.get("Content-Type", "")
        # Normalise JSON body:
        #   1. Drop `metadata` at the top level (original purpose — some
        #      Copilot-wrapping upstreams 403 on Claude Code's metadata.user_id).
        #   2. Drop `refusal` inside every `messages[*]` — OpenAI JS SDK emits
        #      `refusal: null` on assistant turns, but Fireworks-hosted GLM
        #      (Azure AI Foundry `services.ai.azure.com/models`) rejects it as
        #      `Extra inputs are not permitted, field: 'messages[N].refusal'`.
        #      That single 400 poisons multi-turn history, so strip surgically
        #      at the proxy rather than teach Copilot / the OpenAI SDK about
        #      Fireworks's stricter schema.
        if body and "json" in ct.lower():
            try:
                d = json.loads(body)
                mutated = False
                if isinstance(d, dict):
                    if "metadata" in d:
                        d.pop("metadata", None)
                        mutated = True
                    msgs = d.get("messages")
                    if isinstance(msgs, list):
                        for m in msgs:
                            if isinstance(m, dict) and "refusal" in m:
                                m.pop("refusal", None)
                                mutated = True
                if mutated:
                    body = json.dumps(d).encode()
                    self.headers.replace_header("Content-Length", str(len(body))) \
                        if "Content-Length" in self.headers else self.headers.add_header("Content-Length", str(len(body)))
            except Exception as e:
                print(f"[proxy {rid}] json parse skip: {e}", flush=True)

        url = UPSTREAM.rstrip("/") + (UPSTREAM_PATH_OVERRIDE or self.path)
        hop_by_hop = {"host", "connection", "content-length"}
        out_headers = {k: v for k, v in self.headers.items() if k.lower() not in hop_by_hop}
        out_headers["Content-Length"] = str(len(body))
        # If UPSTREAM_AUTH_TOKEN is set, replace inbound auth headers with the
        # configured style. Case-insensitive removal since header casing from
        # urllib clients varies.
        if UPSTREAM_AUTH_TOKEN:
            out_headers = {k: v for k, v in out_headers.items()
                           if k.lower() not in ("authorization", "x-api-key", "api-key")}
            if UPSTREAM_AUTH_STYLE == "api-key":
                out_headers["api-key"] = UPSTREAM_AUTH_TOKEN
            else:
                out_headers["Authorization"] = f"Bearer {UPSTREAM_AUTH_TOKEN}"

        req = urllib.request.Request(url, data=body, headers=out_headers, method=self.command)
        try:
            resp = urllib.request.urlopen(req, timeout=600)
            status = resp.status
            resp_body = resp.read()
            resp_headers = resp.getheaders()
        except urllib.error.HTTPError as e:
            status = e.code
            resp_body = e.read() or b""
            resp_headers = e.headers.items()
        except Exception as e:
            self.send_error(502, f"proxy error: {e}")
            print(f"[proxy {rid}] {self.command} {self.path} in={len(body)}b({length}CL,{'chunked' if 'chunked' in te else 'plain'}) UA={ua!r} -> BAD: {e}", flush=True)
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
            if k.lower() in ("transfer-encoding", "content-length", "connection"): continue
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(resp_body)))
        self.end_headers()
        self.wfile.write(resp_body)


class ThreadingServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    addr = (LISTEN_HOST, LISTEN_PORT)
    auth_note = f" +auth-inject({UPSTREAM_AUTH_STYLE})" if UPSTREAM_AUTH_TOKEN else ""
    path_note = f" path-override={UPSTREAM_PATH_OVERRIDE}" if UPSTREAM_PATH_OVERRIDE else ""
    print(f"strip-metadata proxy: listening on http://{addr[0]}:{addr[1]} -> {UPSTREAM}{auth_note}{path_note}")
    ThreadingServer(addr, Handler).serve_forever()
