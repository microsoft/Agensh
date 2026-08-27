#!/usr/bin/env python3
"""omcgitea secret-service (R7-a, DESIGN_R7_SIDECAR §4.2 / §7).

Tiny stdlib HTTP server that serves per-agent Gitea tokens to mini-router
sidecars. Reads/writes /data/tokens/agent-<name>.token (mode 0600). Auth
is a shared header secret; only reachable on the docker network.
"""
from __future__ import annotations

import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AUTH = os.environ.get("SECRET_SERVICE_INTERNAL_AUTH", "")
TOKENS_DIR = os.environ.get("SECRET_SERVICE_TOKENS_DIR", "/data/tokens")
PORT = int(os.environ.get("SECRET_SERVICE_PORT", "8650"))
NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _token_path(name: str) -> str:
    return os.path.join(TOKENS_DIR, f"agent-{name}.token")


class Handler(BaseHTTPRequestHandler):
    # Speak HTTP/1.1 so modern fetch clients (undici) can keep-alive and
    # parse the response cleanly. Requires Content-Length on every reply,
    # which _send always sets.
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[secret-service] " + (fmt % args) + "\n")

    def _send(self, code: int, body: bytes = b"", ctype: str = "text/plain") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _check_auth(self) -> bool:
        if not AUTH:
            self._send(500, b"server misconfigured: no auth secret\n")
            return False
        if self.headers.get("X-Internal-Auth", "") != AUTH:
            self._send(401, b"unauthorized\n")
            return False
        return True

    def _parse_agent(self, prefix: str) -> str | None:
        if not self.path.startswith(prefix):
            self._send(404, b"not found\n")
            return None
        name = self.path[len(prefix):].split("?", 1)[0]
        if not NAME_RE.match(name):
            self._send(400, b"bad agent name\n")
            return None
        return name

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._send(200, b"ok\n")
            return
        if not self._check_auth():
            return
        name = self._parse_agent("/tokens/")
        if name is None:
            return
        path = _token_path(name)
        if not os.path.isfile(path):
            self._send(404, b"no such token\n")
            return
        with open(path, "rb") as f:
            self._send(200, f.read())

    def do_POST(self) -> None:  # noqa: N802
        if not self._check_auth():
            return
        name = self._parse_agent("/tokens/")
        if name is None:
            return
        n = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(n) if n > 0 else b""
        os.makedirs(TOKENS_DIR, exist_ok=True)
        path = _token_path(name)
        tmp = path + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, body)
        finally:
            os.close(fd)
        os.replace(tmp, path)
        self._send(204)


def main() -> None:
    if not AUTH:
        sys.stderr.write("FATAL: SECRET_SERVICE_INTERNAL_AUTH unset\n")
        sys.exit(2)
    os.makedirs(TOKENS_DIR, exist_ok=True)
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    sys.stderr.write(f"[secret-service] listening on :{PORT} dir={TOKENS_DIR}\n")
    srv.serve_forever()


if __name__ == "__main__":
    main()
