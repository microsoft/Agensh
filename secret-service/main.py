#!/usr/bin/env python3
# Serve bootstrap-issued worker tokens to routers on the private service network.
# Token reads require X-Internal-Auth; the health endpoint is unauthenticated.

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
    # Check the entire identifier and resolved path, including existing symlinks.
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
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[secret-service] " + (fmt % args) + "\n")

    def _send(self, code: int, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        if code >= 400:
            # Rejected requests must not leave unread bytes on a reusable connection.
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

    def _parse_token_path(self) -> str | None:
        prefix = "/tokens/"
        if not self.path.startswith(prefix):
            self._send(404, b"not found\n")
            return None
        name = self.path[len(prefix):].split("?", 1)[0]
        try:
            return _token_path(name)
        except ValueError:
            self._send(400, b"bad agent name\n")
            return None

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send(200, b"ok\n")
            return
        if not self._check_auth():
            return
        path = self._parse_token_path()
        if path is None:
            return
        if not os.path.isfile(path):
            self._send(404, b"no such token\n")
            return
        with open(path, "rb") as f:
            self._send(200, f.read())


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
