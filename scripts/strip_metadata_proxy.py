#!/usr/bin/env python3
"""Strip-metadata proxy for upstream Claude-API compatible backends that
reject requests carrying Claude Code's metadata.user_id (e.g. some
GitHub Copilot wrappers return 403 + GitHub ToS message).

Listens on 127.0.0.1:4180 by default. Forwards any /v1/* request to
UPSTREAM with the JSON body's `metadata` field removed.

Run: python3 strip_metadata_proxy.py
"""
import json, os, sys, time, http.server, urllib.request, urllib.error

# The LLM endpoint to forward to. Required: compose and gen-k8s always set it.
UPSTREAM = os.environ.get("UPSTREAM", "").strip()
if not UPSTREAM:
    sys.exit("FATAL: UPSTREAM is not set (the LLM endpoint to forward to)")
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
# Hop-by-hop headers describe one connection, not the message, so they stop here
# in both directions. The body is re-framed with a fresh Content-Length each way:
# a Transfer-Encoding: chunked forwarded next to it makes the receiver parse the
# already de-chunked body as chunks.
HOP_BY_HOP = {"connection", "keep-alive", "proxy-connection", "te", "trailer",
              "transfer-encoding", "upgrade", "content-length"}


def _timed_out(e):
    # urlopen wraps a timeout in the connect/send phase in URLError; one while
    # waiting for the status line or reading the body arrives bare.
    r = e.reason if isinstance(e, urllib.error.URLError) else e
    return isinstance(r, TimeoutError)


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
                    #   3. Responses API: drop encrypted reasoning items.
                    #      Copilot runs the conversation client-side (store:false) but asks
                    #      for include:["reasoning.encrypted_content"] and replays those
                    #      blobs on the next turn. They are encrypted BY THE DEPLOYMENT
                    #      THAT PRODUCED THEM, and a load-balanced gateway sends the next
                    #      request elsewhere, where most of them fail with
                    #        400 The encrypted content for item rs_... could not be verified
                    #      Stripping both the request for them and any replayed items makes
                    #      every turn self-contained.
                    #      Cost: the model cannot reuse prior reasoning; the message history
                    #      still carries the conversation.
                    if "/responses" in self.path and isinstance(d, dict):
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
                    self.headers.replace_header("Content-Length", str(len(body))) \
                        if "Content-Length" in self.headers else self.headers.add_header("Content-Length", str(len(body)))
            except Exception as e:
                print(f"[proxy {rid}] json parse skip: {e}", flush=True)

        url = UPSTREAM.rstrip("/") + (UPSTREAM_PATH_OVERRIDE or self.path)
        out_headers = {k: v for k, v in self.headers.items()
                       if k.lower() not in HOP_BY_HOP and k.lower() != "host"}
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

        # RETRY TRANSIENT UPSTREAM FAILURES HERE, not in the agent.
        #
        # A gateway returns intermittent 500/504 when its own upstream drops,
        # and the agent SDK's entire retry budget is SIX SECONDS ("Failed to get
        # response from the AI model; retried 5 times (total retry wait time:
        # 6.00 seconds)"), after which the TURN DIES. A dead turn leaves an
        # event-driven agent idle until something else wakes it, and at fleet
        # scale most agents hit it.
        #
        # The proxy is ours and sits in the right place, so it absorbs the blip
        # instead. Backoff is bounded well under the 600s upstream timeout.
        # Only idempotent-by-nature 5xx and 429 are retried, plus failures before
        # the upstream answered at all (refused, DNS, a reset before the status
        # line); 4xx (a real client or auth error) is passed straight through --
        # retrying those would just multiply load against a request that can
        # never succeed. A timeout is final wherever it fires (nearly always a
        # generation that outran it), and so is a failure after the upstream
        # started answering (IncompleteRead, a reset mid-body): the generation
        # ran and was billed, the agent has stopped waiting for it, and a resend
        # pays for it again.
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
                    # The upstream already returned a status line, so this is a
                    # post-response failure just like resp.read() below. Do not
                    # resend a generation that may already have run and billed.
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
        # The `-> <status>` line above records only that the GATEWAY answered.
        # A write failure here means the agent gave up before receiving it, and
        # that has to be loud: a silently dropped response looks like a slow turn.
        try:
            self.end_headers()
            self.wfile.write(resp_body)
            self.wfile.flush()
        except Exception as e:
            print(f"[proxy {rid}] CLIENT GONE before the response was written: {e}",
                  flush=True)

class ThreadingServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    addr = (LISTEN_HOST, LISTEN_PORT)
    auth_note = f" +auth-inject({UPSTREAM_AUTH_STYLE})" if UPSTREAM_AUTH_TOKEN else ""
    path_note = f" path-override={UPSTREAM_PATH_OVERRIDE}" if UPSTREAM_PATH_OVERRIDE else ""
    print(f"strip-metadata proxy: listening on http://{addr[0]}:{addr[1]} -> {UPSTREAM}{auth_note}{path_note}")
    ThreadingServer(addr, Handler).serve_forever()
