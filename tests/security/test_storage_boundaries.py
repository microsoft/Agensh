"""Security regressions using real service handlers and filesystem operations."""
from __future__ import annotations

import contextlib
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load_service(name: str, directory: str, environment: dict[str, str]):
    previous = {key: os.environ.get(key) for key in environment}
    os.environ.update(environment)
    search_path = str(ROOT / directory)
    sys.path.insert(0, search_path)
    try:
        spec = importlib.util.spec_from_file_location(name, ROOT / directory / "main.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(search_path)
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


secret = load_service(
    "security_test_secret_service",
    "secret-service",
    {"SECRET_SERVICE_INTERNAL_AUTH": "local-regression-auth"},
)
board = load_service(
    "security_test_board_service",
    "board-service",
    {
        "MYSQL_DSN": "mysql://test:test@127.0.0.1:1/test",
        "BOARD_MEMBERS_JSON": "{}",
        "BOARD_OPERATOR": "harness",
    },
)


class SecretFixture(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(prefix="magens-secret-security-")
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        self.tokens = self.root / "tokens"
        self.tokens.mkdir()
        secret.TOKENS_DIR = str(self.tokens)


class TokenPathTests(SecretFixture):
    def test_valid_identifiers_keep_their_existing_filenames(self):
        for name in ("agent1", "team1-worker_2.v3", ".", "..", "a" * 64):
            with self.subTest(name=name):
                self.assertEqual(
                    Path(secret._token_path(name)),
                    self.tokens / f"agent-{name}.token",
                )

    def test_invalid_names_are_rejected_at_the_file_boundary(self):
        for name in ("", "../outside", "x/../../outside", "/absolute", "x\n", "a" * 65):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    secret._token_path(name)

    def test_symlink_outside_token_directory_is_rejected(self):
        outside = self.root / "outside.token"
        outside.write_text("outside sentinel")
        (self.tokens / "agent-agent1.token").symlink_to(outside)
        with self.assertRaises(ValueError):
            secret._token_path("agent1")


class TokenHttpTests(SecretFixture):
    def setUp(self):
        super().setUp()
        self.server = secret.ThreadingHTTPServer(("127.0.0.1", 0), secret.Handler)
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": 0.01},
            daemon=True,
        )
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.assertFalse(self.thread.is_alive())

    def request(self, method: str, path: str, body: bytes | None = None, auth=True):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=5
        )
        headers = {"X-Internal-Auth": secret.AUTH} if auth else {}
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def test_authenticated_tokens_round_trip_with_private_permissions(self):
        value = b"owned-regression-token\n"
        self.assertEqual(self.request("POST", "/tokens/agent1", value)[0], 204)
        self.assertEqual(self.request("GET", "/tokens/agent1"), (200, value))
        self.assertEqual(
            (self.tokens / "agent-agent1.token").stat().st_mode & 0o777, 0o600
        )
        self.assertEqual(self.request("GET", "/tokens/agent1", auth=False)[0], 401)

    def test_get_does_not_read_a_symlink_target_outside_token_directory(self):
        outside = self.root / "outside.token"
        outside.write_bytes(b"outside read sentinel")
        (self.tokens / "agent-agent1.token").symlink_to(outside)
        status, body = self.request("GET", "/tokens/agent1")
        self.assertEqual(status, 400)
        self.assertNotIn(b"outside read sentinel", body)

    def test_post_rejects_an_outside_destination_without_modifying_it(self):
        outside = self.root / "outside.token"
        outside.write_bytes(b"outside write sentinel")
        (self.tokens / "agent-agent1.token").symlink_to(outside)
        self.assertEqual(self.request("POST", "/tokens/agent1", b"replacement")[0], 400)
        self.assertEqual(outside.read_bytes(), b"outside write sentinel")

    def test_existing_temporary_symlink_cannot_redirect_a_write(self):
        outside = self.root / "outside.token"
        outside.write_bytes(b"outside temporary sentinel")
        temporary_link = self.tokens / "agent-agent2.token.tmp"
        temporary_link.symlink_to(outside)
        value = b"new token"
        self.assertEqual(self.request("POST", "/tokens/agent2", value)[0], 204)
        self.assertEqual(self.request("GET", "/tokens/agent2"), (200, value))
        self.assertEqual(outside.read_bytes(), b"outside temporary sentinel")
        self.assertTrue(temporary_link.is_symlink())

    def test_replacing_an_internal_symlink_keeps_the_other_token_unchanged(self):
        peer = self.tokens / "agent-peer.token"
        peer.write_bytes(b"peer token")
        link = self.tokens / "agent-linked.token"
        link.symlink_to(peer)
        self.assertEqual(self.request("GET", "/tokens/linked"), (200, b"peer token"))
        self.assertEqual(self.request("POST", "/tokens/linked", b"new token")[0], 204)
        self.assertFalse(link.is_symlink())
        self.assertEqual(link.read_bytes(), b"new token")
        self.assertEqual(peer.read_bytes(), b"peer token")

    def test_traversal_request_is_rejected_over_http(self):
        self.assertEqual(self.request("GET", "/tokens/../../outside")[0], 400)
        self.assertEqual(
            self.request("POST", "/tokens/../../outside", b"replacement")[0], 400
        )

    def test_rejected_post_body_is_not_parsed_and_logged_as_another_request(self):
        token = b"rejected-body-token-sentinel\n"
        request = (
            "POST /tokens/../../outside HTTP/1.1\r\n"
            "Host: localhost\r\n"
            f"X-Internal-Auth: {secret.AUTH}\r\n"
            f"Content-Length: {len(token)}\r\n"
            "Connection: keep-alive\r\n\r\n"
        ).encode() + token
        log = io.StringIO()
        with contextlib.redirect_stderr(log):
            with socket.create_connection(
                ("127.0.0.1", self.server.server_port), timeout=5
            ) as connection:
                connection.sendall(request)
                connection.shutdown(socket.SHUT_WR)
                response = b""
                while chunk := connection.recv(4096):
                    response += chunk
        self.assertIn(b"400", response)
        self.assertNotIn(token.decode().strip(), log.getvalue())


class TokenStartupTests(unittest.TestCase):
    def test_startup_log_does_not_disclose_token_storage_directory(self):
        with tempfile.TemporaryDirectory(prefix="magens-private-token-dir-") as directory:
            environment = {
                **os.environ,
                "SECRET_SERVICE_INTERNAL_AUTH": "local-startup-regression-auth",
                "SECRET_SERVICE_TOKENS_DIR": directory,
                "SECRET_SERVICE_PORT": "0",
            }
            process = subprocess.Popen(
                [sys.executable, "-u", str(ROOT / "secret-service" / "main.py")],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                line = process.stderr.readline()
                self.assertIn("listening", line)
                self.assertNotIn(directory, line)
                self.assertNotIn(environment["SECRET_SERVICE_INTERNAL_AUTH"], line)
            finally:
                process.terminate()
                process.communicate(timeout=5)


class BoardLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.workspace = tempfile.TemporaryDirectory(prefix="magens-board-security-")
        self.root = Path(self.workspace.name)
        self.output = self.root / "lifecycle"
        self.output.mkdir()
        self.previous_directory = os.environ.get("BOARD_LIFECYCLE_DIR")
        os.environ["BOARD_LIFECYCLE_DIR"] = str(self.output)
        board.STATE = board.State()

    async def asyncTearDown(self):
        if self.previous_directory is None:
            os.environ.pop("BOARD_LIFECYCLE_DIR", None)
        else:
            os.environ["BOARD_LIFECYCLE_DIR"] = self.previous_directory
        self.workspace.cleanup()

    async def test_valid_board_identifiers_are_not_rewritten(self):
        for board_id in ("pbench-top", "repo.1", "board with spaces", "项目-1"):
            with self.subTest(board_id=board_id):
                result = await board.post_lifecycle(board_id, viewer="harness")
                path = self.output / f"{board_id}.jsonl"
                self.assertEqual(Path(result["path"]), path)
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                self.assertEqual(rows[-1]["task_id"], board_id)
                self.assertEqual(rows[-1]["kind"], "summary")

    async def test_traversal_and_absolute_destinations_are_rejected(self):
        names = (
            "../outside/escape",
            "../lifecycle-sibling/escape",
            str(self.root / "absolute"),
        )
        for board_id in names:
            with self.subTest(board_id=board_id):
                with self.assertRaises(board.HTTPException) as raised:
                    await board.post_lifecycle(board_id, viewer="harness")
                self.assertEqual(raised.exception.status_code, 400)
                self.assertFalse((self.output / f"{board_id}.jsonl").exists())

    async def test_symlink_escape_does_not_overwrite_an_outside_file(self):
        outside = self.root / "outside.jsonl"
        outside.write_text("outside lifecycle sentinel")
        (self.output / "pbench-top.jsonl").symlink_to(outside)
        with self.assertRaises(board.HTTPException) as raised:
            await board.post_lifecycle("pbench-top", viewer="harness")
        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(outside.read_text(), "outside lifecycle sentinel")


if __name__ == "__main__":
    unittest.main()
