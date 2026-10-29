#!/usr/bin/env python3
# Relay model HTTP requests, removing unsupported metadata/Responses reasoning data.
# Optionally inject the upstream credential; buffer complete responses and retry
# selected transient failures before returning the upstream status and body.

import json, os, sys, time, http.server, urllib.request, urllib.error
import gzip

from code_mode_limits import advertise_defaults, limit_tool_outputs, response_defaults

UPSTREAM = os.environ.get("UPSTREAM", "").strip()
if not UPSTREAM:
    sys.exit("FATAL: UPSTREAM is not set (the LLM endpoint to forward to)")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "4180"))
LISTEN_HOST = os.environ.get("LISTEN_HOST", "127.0.0.1")
UPSTREAM_AUTH_TOKEN = os.environ.get("UPSTREAM_AUTH_TOKEN", "").strip()
UPSTREAM_AUTH_STYLE = os.environ.get("UPSTREAM_AUTH_STYLE", "bearer").strip().lower()
UPSTREAM_DISABLED_TOOLS = frozenset(name.strip() for name in os.environ.get("UPSTREAM_DISABLED_TOOLS", "").split(",") if name.strip())
CODE_MODE_OUTPUT_TOKENS = int(os.environ.get('UPSTREAM_CODE_MODE_OUTPUT_TOKENS', '0'))
MAX_OUTPUT_TOKENS = int(os.environ.get('UPSTREAM_MAX_OUTPUT_TOKENS', '0') or '0')
ANTHROPIC_MODEL = os.environ.get('UPSTREAM_ANTHROPIC_MODEL', '')
ANTHROPIC_EFFORT = os.environ.get('UPSTREAM_ANTHROPIC_EFFORT', '')
TOOL_OUTPUT_BYTES = int(os.environ.get('UPSTREAM_TOOL_OUTPUT_BYTES', '0') or '0')
AGENT_HARNESS = os.environ.get('UPSTREAM_AGENT_HARNESS', '')
RESPONSE_VERBOSITY = os.environ.get('UPSTREAM_RESPONSE_VERBOSITY', '')
REQUEST_TIMEOUT_SECONDS = float(os.environ.get('UPSTREAM_REQUEST_TIMEOUT_SECONDS', '600'))
HOP_BY_HOP = {"connection", "keep-alive", "proxy-connection", "te", "trailer",
              "transfer-encoding", "upgrade", "content-length"}


def limit_anthropic_tool_outputs(payload, budget):
    """Bound UTF-8 text per tool result while preserving image and error fields."""
    changed = False
    notice = "\n[Tool output truncated to the configured byte budget.]"
    def bounded(text, allowance):
        raw = text.encode('utf-8')
        if len(raw) <= allowance:
            return text
        if allowance <= 0:
            return ''
        marker = notice if allowance >= len(notice.encode()) else '.'
        prefix = raw[:max(0, allowance - len(marker.encode()))].decode('utf-8', errors='ignore')
        return prefix + marker
    for message in payload.get('messages', []):
        if not isinstance(message, dict) or not isinstance(message.get('content'), list):
            continue
        for block in message['content']:
            if not isinstance(block, dict) or block.get('type') != 'tool_result':
                continue
            result = block.get('content')
            if isinstance(result, str):
                limited = bounded(result, budget)
                if limited != result:
                    block['content'] = limited
                    changed = True
            elif isinstance(result, list):
                remaining = budget
                limited = []
                for part in result:
                    if isinstance(part, dict) and part.get('type') == 'text':
                        if remaining == 0 and part.get('text'):
                            changed = True
                            continue
                        text = part.get('text', '')
                        value = bounded(text, remaining)
                        remaining = max(0, remaining - len(value.encode()))
                        if value != text:
                            part = {**part, 'text': value}
                            changed = True
                    limited.append(part)
                block['content'] = limited
    return changed


def model_request_metadata(payload):
    """Record effective request settings without prompts, tool data or credentials."""
    reasoning = payload.get('reasoning') or payload.get('output_config')
    text_options = payload.get('text')
    inputs = payload.get('input', payload.get('messages'))
    tools = payload.get('tools')
    tool_count = len(tools) if isinstance(tools, list) else 0
    if isinstance(inputs, list):
        tool_count += sum(len(item['tools']) for item in inputs if isinstance(item, dict)
                          and item.get('type') == 'additional_tools' and isinstance(item.get('tools'), list))
    return {'model': payload.get('model'),
            'reasoning_effort': reasoning.get('effort') if isinstance(reasoning, dict)
                                else payload.get('reasoning_effort'),
            'max_output_tokens': payload.get('max_output_tokens', payload.get('max_tokens')),
            'verbosity': text_options.get('verbosity') if isinstance(text_options, dict) else None,
            'tool_count': tool_count,
            'input_items': len(inputs) if isinstance(inputs, list) else None}


def filter_tool_declarations(payload, disabled):
    """Hide unsupported frontend tools in standard and Responses Lite declarations."""
    if not disabled:
        return False

    def filtered(tools, namespace=""):
        output = []
        changed = False
        for tool in tools:
            if not isinstance(tool, dict):
                output.append(tool)
                continue
            name = tool.get("name") or (tool.get("function") or {}).get("name", "")
            qualified = namespace + "." + name if namespace else name
            if qualified in disabled:
                changed = True
                continue
            if tool.get("type") == "namespace" and isinstance(tool.get("tools"), list):
                nested, nested_changed = filtered(tool["tools"], qualified)
                if nested_changed:
                    changed = True
                    if not nested:
                        continue
                    tool = dict(tool, tools=nested)
            output.append(tool)
        return output, changed

    changed = False
    if isinstance(payload.get("tools"), list):
        tools, modified = filtered(payload["tools"])
        if modified:
            payload["tools"] = tools
            changed = True
    if isinstance(payload.get("input"), list):
        for item in payload["input"]:
            if isinstance(item, dict) and item.get("type") == "additional_tools" and isinstance(item.get("tools"), list):
                tools, modified = filtered(item["tools"])
                if modified:
                    item["tools"] = tools
                    changed = True
    return changed


def filter_disabled_tool_guidance(payload, disabled):
    """Clean pinned harness guidance for question tools hidden by this proxy.

    Only recognized harness text in system/developer instructions is changed.
    User messages, assistant messages and tool results are preserved.
    """
    if not disabled:
        return False

    def hidden(name):
        return name in disabled or "functions." + name in disabled

    def clean(text):
        if hidden("request_user_input_async"):
            paragraphs = text.split("\n\n")
            for index, paragraph in enumerate(paragraphs):
                if paragraph.startswith("When available, you can use the `functions.request_user_input_async` tool"):
                    paragraphs[index] = (
                        "This worker runs unattended. Continue using the task instructions and available tools; "
                        "resolve optional preferences with reasonable assumptions within the task scope."
                    )
            text = "\n\n".join(paragraphs)
        if hidden("request_user_input"):
            start = text.find("## request_user_input availability")
            end = text.find("</collaboration_mode>", start) if start >= 0 else -1
            if start >= 0 and end >= 0 and "<collaboration_mode>" in text[:start]:
                text = text[:start].rstrip() + "\n" + text[end:]
        return text

    changed = False
    if isinstance(payload.get("instructions"), str):
        previous = payload["instructions"]
        payload["instructions"] = clean(previous)
        changed |= payload["instructions"] != previous
    for field in ("input", "messages"):
        items = payload.get(field)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or item.get("role") not in ("system", "developer"):
                continue
            content = item.get("content")
            if isinstance(content, str):
                updated = clean(content)
                if updated != content:
                    item["content"] = updated
                    changed = True
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        previous = part["text"]
                        part["text"] = clean(previous)
                        changed |= part["text"] != previous
    return changed


def _timed_out(e):
    r = e.reason if isinstance(e, urllib.error.URLError) else e
    return isinstance(r, TimeoutError)


def read_upstream_response(response, deadline):
    """A progressing SSE stream must still respect the common request deadline."""
    chunks = []
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('model request deadline exceeded')
        stream = getattr(response, 'fp', None)
        for _ in range(3):
            sock = getattr(getattr(stream, 'raw', None), '_sock', None)
            if sock is not None:
                sock.settimeout(remaining)
                break
            stream = getattr(stream, 'fp', None)
        chunk = response.read1(65536)
        if not chunk:
            return b''.join(chunks)
        chunks.append(chunk)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):    self._proxy()
    def do_GET(self):     self._proxy()
    def log_message(self, fmt, *args):
        pass

    def _proxy(self):
        deadline = time.monotonic() + REQUEST_TIMEOUT_SECONDS
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
                    mutated = filter_tool_declarations(d, UPSTREAM_DISABLED_TOOLS)
                    mutated = filter_disabled_tool_guidance(d, UPSTREAM_DISABLED_TOOLS) or mutated
                    mutated = advertise_defaults(d, CODE_MODE_OUTPUT_TOKENS) or mutated
                    message_path = self.path.split('?', 1)[0].rstrip('/')
                    if message_path.endswith('/messages') or message_path.endswith('/messages/count_tokens'):
                        if ANTHROPIC_MODEL and d.get('model') != ANTHROPIC_MODEL:
                            d['model'] = ANTHROPIC_MODEL
                            mutated = True
                        if message_path.endswith('/messages'):
                            if ANTHROPIC_EFFORT:
                                output_config = d.setdefault('output_config', {})
                                if isinstance(output_config, dict) and output_config.get('effort') != ANTHROPIC_EFFORT:
                                    output_config['effort'] = ANTHROPIC_EFFORT
                                    mutated = True
                            cap = d.get('max_tokens')
                            if MAX_OUTPUT_TOKENS > 0 and (cap is None or isinstance(cap, int) and cap > MAX_OUTPUT_TOKENS):
                                d['max_tokens'] = MAX_OUTPUT_TOKENS
                                mutated = True
                        if TOOL_OUTPUT_BYTES > 0:
                            mutated = limit_anthropic_tool_outputs(d, TOOL_OUTPUT_BYTES) or mutated
                    if "metadata" in d:
                        d.pop("metadata", None)
                        mutated = True
                    if "/responses" in self.path:
                        if AGENT_HARNESS == 'codex' and message_path.endswith(('/responses', '/responses/compact')):
                            mutated = limit_tool_outputs(d, TOOL_OUTPUT_BYTES) or mutated
                        current_cap = d.get('max_output_tokens')
                        if (MAX_OUTPUT_TOKENS > 0 and self.path.split('?', 1)[0].rstrip('/').endswith('/responses')
                                and (current_cap is None or
                                isinstance(current_cap, int) and not isinstance(current_cap, bool)
                                and current_cap > MAX_OUTPUT_TOKENS)):
                            d['max_output_tokens'] = MAX_OUTPUT_TOKENS
                            mutated = True
                        if RESPONSE_VERBOSITY:
                            text_options = d.setdefault('text', {})
                            if isinstance(text_options, dict) and 'verbosity' not in text_options:
                                text_options['verbosity'] = RESPONSE_VERBOSITY
                                mutated = True
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
                if isinstance(d, dict) and ('/responses' in self.path or self.path.split('?', 1)[0].rstrip('/').endswith('/messages')):
                    print(f"[proxy {rid}] REQUEST " + json.dumps(model_request_metadata(d), separators=(',', ':')), flush=True)
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
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('model request deadline exceeded')
                resp = urllib.request.urlopen(req, timeout=remaining)
            except urllib.error.HTTPError as e:
                status = e.code
                try:
                    resp_body = read_upstream_response(e, deadline)
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
                    time.sleep(min(_d, max(0, deadline - time.monotonic())))
                    req = urllib.request.Request(url, data=body, headers=out_headers, method=self.command)
                    continue
                break
            except Exception as e:
                # Do not retry timeouts: the upstream may still be running inference.
                if not _timed_out(e) and _try < _attempts - 1:
                    _d = _backoff[min(_try, len(_backoff) - 1)] or 1
                    print(f"[proxy {rid}] upstream error {e}, retry {_try+1}/{_attempts-1} in {_d}s", flush=True)
                    time.sleep(min(_d, max(0, deadline - time.monotonic())))
                    req = urllib.request.Request(url, data=body, headers=out_headers, method=self.command)
                    continue
                err = e
                break
            try:
                status = resp.status
                resp_body = read_upstream_response(resp, deadline)
                resp_headers = resp.getheaders()
                resp.close()
            except Exception as e:
                resp.close()
                err = e
            break
        if err is not None:
            print(f"[proxy {rid}] {self.command} {self.path} in={len(body)}b({length}CL,{'chunked' if 'chunked' in te else 'plain'}) UA={ua!r} -> BAD: {err}", flush=True)
            try:
                self.send_error(502, f"proxy error: {err}")
            except (BrokenPipeError, ConnectionResetError) as disconnected:
                print(f"[proxy {rid}] CLIENT GONE before the error was written: {disconnected}", flush=True)
            return

        if status < 400 and CODE_MODE_OUTPUT_TOKENS and '/responses' in self.path:
            headers = dict((key.lower(), value) for key, value in resp_headers)
            encoded = headers.get('content-encoding', '').lower() == 'gzip'
            try:
                plain = gzip.decompress(resp_body) if encoded else resp_body
                updated = response_defaults(plain, headers.get('content-type', ''), CODE_MODE_OUTPUT_TOKENS)
                if updated != plain or encoded:
                    # Code Mode's native SSE decoder consumes UTF-8 bytes. Emit
                    # an ordinary uncompressed response after inspecting gzip.
                    resp_body = updated
                    resp_headers = [(key, value) for key, value in resp_headers
                                    if key.lower() not in ('content-encoding', 'content-md5', 'digest', 'etag')]
            except (OSError, EOFError):
                # Preserve an invalid upstream encoding for the native error path.
                pass
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
