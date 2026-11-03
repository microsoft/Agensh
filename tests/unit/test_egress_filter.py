# The allowlist network's filtering proxy: domain rules, and CONNECT and plain HTTP
# through a live proxy to a local server. Run: python3 -m unittest discover -s tests/unit

import asyncio
import http.server
import importlib.util
from pathlib import Path
import socket
import threading
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('egress_filter', ROOT / 'scripts/egress_filter.py')
egress_filter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(egress_filter)


class RuleTest(unittest.TestCase):
    def test_domains(self):
        domains = egress_filter.allowed_domains(' pypi.internal.example ,,')
        allowed = egress_filter.is_allowed
        self.assertTrue(allowed('pypi.org', 443, domains))
        self.assertTrue(allowed('FILES.pythonhosted.org.', 443, domains))
        self.assertTrue(allowed('deb.debian.org', 80, domains))
        self.assertTrue(allowed('mirror.pypi.internal.example', 443, domains))
        self.assertFalse(allowed('example.com', 443, domains))
        self.assertFalse(allowed('evilpypi.org', 443, domains))
        self.assertFalse(allowed('pypi.org', 22, domains))
        self.assertFalse(allowed('140.82.112.3', 443, domains))
        self.assertFalse(allowed('github.com', 443, domains))

    def test_targets(self):
        self.assertEqual(egress_filter.target('CONNECT', 'pypi.org:443', {}), ('pypi.org', 443, None))
        self.assertEqual(egress_filter.target('GET', 'http://deb.debian.org/debian/dists', {}),
                         ('deb.debian.org', 80, '/debian/dists'))
        self.assertEqual(egress_filter.target('GET', 'http://h.example:8080', {}), ('h.example', 8080, '/'))


class Origin(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = f'origin saw {self.path}'.encode()
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


class ProxyTest(unittest.TestCase):
    def setUp(self):
        self.origin = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Origin)
        threading.Thread(target=self.origin.serve_forever, daemon=True).start()
        self.addCleanup(self.origin.shutdown)
        # The local origin stands in for an allowed registry on port 80.
        self.loop = asyncio.new_event_loop()
        original = egress_filter.is_allowed
        egress_filter.is_allowed = lambda host, port, domains=None: host == 'localhost' or original(host, port)
        self.addCleanup(setattr, egress_filter, 'is_allowed', original)
        self.server = self.loop.run_until_complete(asyncio.start_server(egress_filter.handle, '127.0.0.1', 0))
        self.port = self.server.sockets[0].getsockname()[1]
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        self.addCleanup(self.stop_loop)

    def stop_loop(self):
        self.loop.call_soon_threadsafe(self.server.close)
        self.loop.call_soon_threadsafe(self.loop.stop)
        while self.loop.is_running():
            pass
        self.loop.close()

    def exchange(self, request):
        with socket.create_connection(('127.0.0.1', self.port), timeout=10) as conn:
            conn.sendall(request)
            data = b''
            while chunk := conn.recv(65536):
                data += chunk
                if b'origin saw' in data or b'403' in data.split(b'\r\n', 1)[0]:
                    break
            return data

    def test_plain_http_and_denial(self):
        origin_port = self.origin.server_address[1]
        reply = self.exchange(f'GET http://localhost:{origin_port}/simple/x HTTP/1.1\r\n'
                              f'Host: localhost:{origin_port}\r\n\r\n'.encode())
        self.assertIn(b'origin saw /simple/x', reply)
        denied = self.exchange(b'CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n')
        self.assertTrue(denied.startswith(b'HTTP/1.1 403'))
        self.assertIn(b'allow_domains', denied)

    def test_connect_tunnel(self):
        origin_port = self.origin.server_address[1]
        with socket.create_connection(('127.0.0.1', self.port), timeout=10) as conn:
            conn.sendall(f'CONNECT localhost:{origin_port} HTTP/1.1\r\n\r\n'.encode())
            self.assertTrue(conn.recv(4096).startswith(b'HTTP/1.1 200'))
            conn.sendall(b'GET /tunnel HTTP/1.1\r\nHost: localhost\r\n\r\n')
            data = b''
            while b'origin saw' not in data and (chunk := conn.recv(65536)):
                data += chunk
        self.assertIn(b'origin saw /tunnel', data)


if __name__ == '__main__':
    unittest.main()
