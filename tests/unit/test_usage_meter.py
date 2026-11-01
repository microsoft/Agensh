# Usage parsing, ledger accounting and the proxy's per-agent metering end to end.
# Run: python3 -m unittest discover -s tests/unit

import gzip
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests' / 'smoke'))

import fake_upstream  # noqa: E402
from usage_meter import UsageLedger, agent_identity, is_model_path, parse_usage  # noqa: E402

RESPONSES = {'input_tokens': 120, 'cached_input_tokens': 20, 'cache_creation_input_tokens': 0,
             'output_tokens': 30, 'reasoning_tokens': 10}
CHAT = {'input_tokens': 50, 'cached_input_tokens': 5, 'cache_creation_input_tokens': 0,
        'output_tokens': 7, 'reasoning_tokens': 2}
MESSAGES = {'input_tokens': 40, 'cached_input_tokens': 60, 'cache_creation_input_tokens': 8,
            'output_tokens': 25, 'reasoning_tokens': 0}


class ParseUsageTest(unittest.TestCase):
    def check(self, path, builder, expected):
        for stream in (False, True):
            with self.subTest(path=path, stream=stream):
                content_type, body = builder(stream)
                self.assertEqual(parse_usage(path, content_type, body), expected)

    def test_responses(self):
        self.check('/v1/responses', fake_upstream.responses, RESPONSES)

    def test_chat_completions(self):
        self.check('/v1/chat/completions', fake_upstream.chat, CHAT)

    def test_messages_take_final_output_count(self):
        self.check('/v1/messages', fake_upstream.messages, MESSAGES)

    def test_gzip_and_sse_without_content_type(self):
        _, body = fake_upstream.responses(True)
        self.assertEqual(parse_usage('/responses', '', body), RESPONSES)
        _, body = fake_upstream.responses(False)
        self.assertEqual(parse_usage('/responses', 'application/json', gzip.compress(body), 'gzip'), RESPONSES)

    def test_no_usage_or_malformed_body(self):
        self.assertIsNone(parse_usage('/v1/responses', 'application/json', b'{"id":"x"}'))
        self.assertIsNone(parse_usage('/v1/responses', 'application/json', b'not json'))
        self.assertIsNone(parse_usage('/v1/responses', 'application/json', b'\x1f\x8bbad', 'gzip'))
        self.assertIsNone(parse_usage('/v1/messages', 'text/event-stream', b'data: [DONE]\n\n'))

    def test_negative_or_non_integer_counts_become_zero(self):
        body = json.dumps({'usage': {'input_tokens': -3, 'output_tokens': True}}).encode()
        usage = parse_usage('/v1/responses', 'application/json', body)
        self.assertEqual((usage['input_tokens'], usage['output_tokens']), (0, 0))


class IdentityTest(unittest.TestCase):
    def test_labels_from_any_key_header(self):
        self.assertEqual(agent_identity({'authorization': 'Bearer local-proxy-org-worker2'}), 'org-worker2')
        self.assertEqual(agent_identity({'x-api-key': 'local-proxy-org-worker3'}), 'org-worker3')
        self.assertEqual(agent_identity({'api-key': 'local-proxy-a'}), 'a')

    def test_unlabelled_requests(self):
        for headers in ({}, {'authorization': 'Bearer local-proxy-no-auth'},
                        {'authorization': 'Bearer sk-real'}, {'x-api-key': 'local-proxy-'}):
            with self.subTest(headers=headers):
                self.assertEqual(agent_identity(headers), 'unlabelled')

    def test_model_paths(self):
        for path in ('/v1/responses', '/responses/compact', '/v1/chat/completions', '/v1/messages?beta=true'):
            self.assertTrue(is_model_path(path), path)
        for path in ('/healthz', '/v1/models', '/v1/messages/count_tokens'):
            self.assertFalse(is_model_path(path), path)


class LedgerTest(unittest.TestCase):
    def test_totals_persist_and_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'nested', 'usage.jsonl')
            ledger = UsageLedger(path)
            ledger.record('a', '/v1/responses', 200, 'm', RESPONSES)
            ledger.record('a', '/v1/responses', 200, 'm', None)
            ledger.record('a', '/v1/responses', 429, 'm', None)
            ledger.record('b', '/v1/messages', 200, 'm', MESSAGES)
            snapshot = UsageLedger(path).snapshot()
        a = snapshot['agents']['a']
        self.assertEqual((a['requests'], a['errors'], a['without_usage'], a['input_tokens']), (3, 1, 1, 120))
        self.assertEqual(snapshot['team']['output_tokens'], 55)
        self.assertEqual(snapshot['team']['requests'], 4)

    def test_unwritable_log_keeps_counting(self):
        with tempfile.TemporaryDirectory() as directory:
            blocker = Path(directory) / 'file'
            blocker.write_text('')
            ledger = UsageLedger(str(blocker / 'usage.jsonl'))
            ledger.record('a', '/v1/responses', 200, 'm', RESPONSES)
        self.assertEqual(ledger.snapshot()['agents']['a']['output_tokens'], 30)


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class ProxyBase(unittest.TestCase):
    """The real proxy in front of the fake upstream."""
    EXTRA_ENV = {}

    @classmethod
    def setUpClass(cls):
        cls.upstream = fake_upstream.serve('127.0.0.1', 0)
        threading.Thread(target=cls.upstream.serve_forever, daemon=True).start()
        cls.directory = tempfile.TemporaryDirectory()
        cls.log = os.path.join(cls.directory.name, 'usage.jsonl')
        cls.port = free_port()
        env = dict(os.environ, UPSTREAM=f'http://127.0.0.1:{cls.upstream.server_address[1]}',
                   LISTEN_HOST='127.0.0.1', LISTEN_PORT=str(cls.port), UPSTREAM_USAGE_LOG=cls.log,
                   UPSTREAM_AUTH_TOKEN='upstream-secret', UPSTREAM_RETRY_ATTEMPTS='1', **cls.EXTRA_ENV)
        cls.proxy = subprocess.Popen([sys.executable, str(ROOT / 'scripts' / 'strip_metadata_proxy.py')],
                                     env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for _ in range(100):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{cls.port}/healthz', timeout=1)
                break
            except OSError:
                time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        cls.proxy.terminate()
        cls.proxy.wait(timeout=5)
        cls.proxy.stdout.close()
        cls.upstream.shutdown()
        cls.upstream.server_close()
        cls.directory.cleanup()

    def post(self, path, headers, stream, fail=False):
        request = urllib.request.Request(f'http://127.0.0.1:{self.port}{path}', method='POST',
                                         data=json.dumps({'model': 'fake', 'stream': stream, 'fail': fail}).encode(),
                                         headers={'Content-Type': 'application/json', **headers})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()



class ProxyMeteringTest(ProxyBase):
    """Run the real proxy against the fake upstream and check per-agent totals."""

    def test_requests_are_metered_per_agent(self):
        worker1 = {'Authorization': 'Bearer local-proxy-org-worker1'}
        worker2 = {'x-api-key': 'local-proxy-org-worker2'}
        status, body = self.post('/v1/responses', worker1, True)
        self.assertEqual(status, 200)
        self.assertIn(b'response.completed', body)
        self.assertEqual(self.post('/v1/responses', worker1, False)[0], 200)
        self.assertEqual(self.post('/v1/messages', worker2, True)[0], 200)
        self.assertEqual(self.post('/v1/messages', worker2, False, fail=True)[0], 400)
        self.assertEqual(self.post('/v1/models', worker2, False)[0], 404)
        self.assertEqual(self.post('/v1/chat/completions', {}, False)[0], 200)

        snapshot = json.load(urllib.request.urlopen(f'http://127.0.0.1:{self.port}/usage', timeout=5))
        agents = snapshot['agents']
        self.assertEqual(agents['org-worker1']['requests'], 2)
        self.assertEqual(agents['org-worker1']['input_tokens'], 240)
        self.assertEqual(agents['org-worker1']['output_tokens'], 60)
        self.assertEqual(agents['org-worker2']['output_tokens'], 25)
        self.assertEqual((agents['org-worker2']['requests'], agents['org-worker2']['errors']), (2, 1))
        self.assertEqual(agents['org-worker2']['cached_input_tokens'], 60)
        self.assertEqual(agents['unlabelled']['input_tokens'], 50)
        records = [json.loads(line) for line in Path(self.log).read_text().splitlines()]
        self.assertEqual(len(records), 5)
        self.assertTrue(all('upstream-secret' not in json.dumps(r) for r in records))
        self.assertEqual({r['model'] for r in records}, {'fake'})



class TokenBudgetTest(ProxyBase):
    # Each fake Responses reply reports 120 input and 30 output tokens.
    OPEN_FILE = os.path.join(tempfile.gettempdir(), f'final-evaluation-{os.getpid()}.open')
    EXTRA_ENV = {'UPSTREAM_MAX_MODEL_TOKENS': '300', 'UPSTREAM_FINAL_OPEN_FILE': OPEN_FILE}

    def test_requests_stop_at_the_budget(self):
        worker = {'Authorization': 'Bearer local-proxy-org-worker1'}
        self.assertEqual(self.post('/v1/responses', worker, False)[0], 200)
        self.assertEqual(self.post('/v1/responses', worker, False)[0], 200)
        status, body = self.post('/v1/responses', worker, False)
        self.assertEqual(status, 429)
        self.assertEqual(json.loads(body)['error']['type'], 'budget_exhausted')
        snapshot = json.load(urllib.request.urlopen(f'http://127.0.0.1:{self.port}/usage', timeout=5))
        self.assertEqual(snapshot['agents']['org-worker1']['requests'], 2)
        # The final evaluation's route is held to the budget until the driver opens it ...
        self.assertEqual(self.post('/raw-final/v1/responses', {}, False)[0], 429)
        Path(self.OPEN_FILE).touch()
        self.addCleanup(Path(self.OPEN_FILE).unlink, missing_ok=True)
        self.assertEqual(self.post('/raw-final/v1/responses', {}, False)[0], 200)
        self.assertEqual(self.post('/raw-final/v1/responses', {}, False)[0], 200)
        # ... and its tokens do not count against the team's.
        self.assertEqual(self.post('/raw/v1/responses', {}, False)[0], 429)
        Path(self.OPEN_FILE).unlink()
        self.assertEqual(self.post('/raw-final/v1/responses', {}, False)[0], 429)
        snapshot = json.load(urllib.request.urlopen(f'http://127.0.0.1:{self.port}/usage', timeout=5))
        self.assertEqual(snapshot['agents']['final-evaluation']['requests'], 2)



class AgentModelTest(ProxyBase):
    # Per-role models: worker2's requests go to its own model.
    EXTRA_ENV = {'UPSTREAM_AGENT_MODELS': 'org-worker2=small-model,org-worker9=other'}

    def test_model_per_agent(self):
        self.assertEqual(self.post('/v1/responses', {'Authorization': 'Bearer local-proxy-org-worker1'}, False)[0], 200)
        self.assertEqual(self.post('/v1/responses', {'Authorization': 'Bearer local-proxy-org-worker2'}, False)[0], 200)
        records = [json.loads(line) for line in Path(self.log).read_text().splitlines()]
        self.assertEqual({r['agent']: r['model'] for r in records}, {'org-worker1': 'fake', 'org-worker2': 'small-model'})



class RawRouteTest(ProxyBase):
    # /raw forwards a project's own requests unchanged apart from the credential.
    EXTRA_ENV = {'UPSTREAM_RESPONSE_VERBOSITY': 'low', 'UPSTREAM_MAX_OUTPUT_TOKENS': '100',
                 'UPSTREAM_AGENT_MODELS': 'org-worker1=other-model'}

    def test_raw_requests_are_not_rewritten(self):
        fake_upstream.RECEIVED.clear()
        self.assertEqual(self.post('/v1/responses', {'Authorization': 'Bearer local-proxy-org-worker1'}, False)[0], 200)
        harness = fake_upstream.RECEIVED[-1]
        self.assertEqual((harness['path'], harness['request']['text'], harness['request']['model']),
                         ('/v1/responses', {'verbosity': 'low'}, 'other-model'))
        self.assertEqual(self.post('/raw/v1/responses', {}, False)[0], 200)
        raw = fake_upstream.RECEIVED[-1]
        self.assertEqual(raw['path'], '/v1/responses')
        self.assertEqual(raw['request'], {'model': 'fake', 'stream': False, 'fail': False})
        self.assertEqual(raw['authorization'], 'Bearer upstream-secret')
        self.assertEqual(self.post('/raw/v1/responses', {'Authorization': 'Bearer local-proxy-org-worker1'}, False)[0], 200)
        self.assertEqual(fake_upstream.RECEIVED[-1]['request']['model'], 'fake')
        records = [json.loads(line) for line in Path(self.log).read_text().splitlines()]
        self.assertEqual([(r['agent'], r['model']) for r in records[-2:]], [('project', 'fake'), ('org-worker1', 'fake')])


if __name__ == '__main__':
    unittest.main()
