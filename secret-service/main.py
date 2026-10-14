#!/usr/bin/env python3
"""omcgitea secret-service.

Tiny stdlib HTTP server that serves per-agent Gitea tokens to mini-router
sidecars. Reads/writes /data/tokens/agent-<name>.token (mode 0600). Auth
is a shared header secret; only reachable on the docker network.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AUTH = os.environ.get("SECRET_SERVICE_INTERNAL_AUTH", "")
TOKENS_DIR = os.environ.get("SECRET_SERVICE_TOKENS_DIR", "/data/tokens")
PORT = int(os.environ.get("SECRET_SERVICE_PORT", "8650"))
NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _token_path(name: str) -> str:
    if not NAME_RE.fullmatch(name):
        raise ValueError("bad agent name")
    root = os.path.realpath(TOKENS_DIR)
    path = os.path.abspath(os.path.join(root, f"agent-{name}.token"))
    if (
        not path.startswith(os.path.join(root, ""))
        or os.path.commonpath((root, os.path.realpath(path))) != root
    ):
        raise ValueError("token path outside storage directory")
    return path


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
        if code >= 400:
            # Rejected POST bodies may still be unread. Do not parse their
            # token bytes as a second request and include them in error logs.
            self.close_connection = True
            self.send_header("Connection", "close")
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

    def _parse_token_path(self, prefix: str) -> str | None:
        if not self.path.startswith(prefix):
            self._send(404, b"not found\n")
            return None
        name = self.path[len(prefix):].split("?", 1)[0]
        try:
            return _token_path(name)
        except ValueError:
            self._send(400, b"bad agent name\n")
            return None

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._send(200, b"ok\n")
            return
        if not self._check_auth():
            return
        path = self._parse_token_path("/tokens/")
        if path is None:
            return
        if not os.path.isfile(path):
            self._send(404, b"no such token\n")
            return
        with open(path, "rb") as f:
            self._send(200, f.read())

    def do_POST(self) -> None:  # noqa: N802
        if not self._check_auth():
            return
        path = self._parse_token_path("/tokens/")
        if path is None:
            return
        n = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(n) if n > 0 else b""
        os.makedirs(TOKENS_DIR, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".token-", dir=TOKENS_DIR)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(body)
            os.replace(tmp, path)
        finally:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
        self._send(204)


def main() -> None:
    if not AUTH:
        sys.stderr.write("FATAL: SECRET_SERVICE_INTERNAL_AUTH unset\n")
        sys.exit(2)
    os.makedirs(TOKENS_DIR, exist_ok=True)
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    sys.stderr.write(f"[secret-service] listening on :{PORT}\n")
    srv.serve_forever()


if __name__ == "__main__":
    main()
