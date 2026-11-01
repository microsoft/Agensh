# Account model token usage per agent from buffered proxy responses.
# Parses Responses, Chat Completions and Anthropic Messages bodies, both JSON and
# SSE, and appends one JSONL record per model request without prompt content.

import gzip
import json
import os
import threading
import time

IDENTITY_PREFIX = 'local-proxy-'
USAGE_FIELDS = ('input_tokens', 'cached_input_tokens', 'cache_creation_input_tokens',
                'output_tokens', 'reasoning_tokens')
MODEL_PATH_SUFFIXES = ('/responses', '/responses/compact', '/chat/completions', '/messages')


def is_model_path(path):
    return path.split('?', 1)[0].rstrip('/').endswith(MODEL_PATH_SUFFIXES)


def agent_identity(headers):
    """Workers send `local-proxy-<agent>` as their proxy key; it labels, not authenticates."""
    candidates = [headers.get('x-api-key', '') or '', headers.get('api-key', '') or '']
    authorization = headers.get('authorization', '') or ''
    if authorization.lower().startswith('bearer '):
        candidates.insert(0, authorization[7:])
    for key in candidates:
        key = key.strip()
        if key.startswith(IDENTITY_PREFIX) and len(key) > len(IDENTITY_PREFIX):
            name = key[len(IDENTITY_PREFIX):]
            return 'unlabelled' if name == 'no-auth' else name
    return 'unlabelled'


def _number(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _from_usage(usage, api):
    if not isinstance(usage, dict):
        return None
    if api == 'messages':
        record = {'input_tokens': _number(usage.get('input_tokens')),
                  'cached_input_tokens': _number(usage.get('cache_read_input_tokens')),
                  'cache_creation_input_tokens': _number(usage.get('cache_creation_input_tokens')),
                  'output_tokens': _number(usage.get('output_tokens')),
                  'reasoning_tokens': 0}
    elif api == 'chat':
        record = {'input_tokens': _number(usage.get('prompt_tokens')),
                  'cached_input_tokens': _number((usage.get('prompt_tokens_details') or {}).get('cached_tokens')),
                  'cache_creation_input_tokens': 0,
                  'output_tokens': _number(usage.get('completion_tokens')),
                  'reasoning_tokens': _number((usage.get('completion_tokens_details') or {}).get('reasoning_tokens'))}
    else:
        record = {'input_tokens': _number(usage.get('input_tokens')),
                  'cached_input_tokens': _number((usage.get('input_tokens_details') or {}).get('cached_tokens')),
                  'cache_creation_input_tokens': 0,
                  'output_tokens': _number(usage.get('output_tokens')),
                  'reasoning_tokens': _number((usage.get('output_tokens_details') or {}).get('reasoning_tokens'))}
    return record


def api_family(path):
    path = path.split('?', 1)[0].rstrip('/')
    if path.endswith('/messages'):
        return 'messages'
    if path.endswith('/chat/completions'):
        return 'chat'
    return 'responses'


def _sse_events(text):
    for line in text.splitlines():
        if line.startswith('data:'):
            data = line[5:].strip()
            if data and data != '[DONE]':
                try:
                    yield json.loads(data)
                except ValueError:
                    continue


def parse_usage(path, content_type, body, content_encoding=''):
    """Return normalized token counts, or None when the body reports no usage.

    Messages report `input_tokens` without cache reads and writes, which are kept
    in their own fields; Responses and Chat Completions include cached tokens in
    `input_tokens`.
    """
    api = api_family(path)
    try:
        if content_encoding.lower() == 'gzip':
            body = gzip.decompress(body)
        text = body.decode('utf-8', errors='replace')
    except (OSError, EOFError):
        return None
    if 'event-stream' in content_type.lower() or text.lstrip().startswith(('event:', 'data:')):
        usage = None
        for event in _sse_events(text):
            if not isinstance(event, dict):
                continue
            if api == 'messages':
                if event.get('type') == 'message_start':
                    usage = _from_usage((event.get('message') or {}).get('usage'), api)
                elif event.get('type') == 'message_delta' and isinstance(event.get('usage'), dict):
                    # Deltas carry cumulative output and, on some gateways, input counts.
                    delta = _from_usage(event['usage'], api)
                    usage = usage or {field: 0 for field in USAGE_FIELDS}
                    for field in USAGE_FIELDS:
                        if delta[field]:
                            usage[field] = delta[field]
            elif api == 'chat':
                if isinstance(event.get('usage'), dict):
                    usage = _from_usage(event['usage'], api)
            elif isinstance(event.get('response'), dict) and event['response'].get('usage'):
                usage = _from_usage(event['response']['usage'], api)
        return usage
    try:
        document = json.loads(text)
    except ValueError:
        return None
    if not isinstance(document, dict):
        return None
    if api == 'responses' and isinstance(document.get('response'), dict):
        document = document['response']
    return _from_usage(document.get('usage'), api)


class UsageLedger:
    """Thread-safe per-agent totals, persisted as an append-only JSONL log."""

    def __init__(self, path=None):
        self.path = path or None
        self.lock = threading.Lock()
        self.totals = {}
        if self.path and os.path.exists(self.path):
            with open(self.path, encoding='utf-8') as stream:
                for line in stream:
                    try:
                        self._add(json.loads(line))
                    except (ValueError, KeyError, TypeError):
                        continue

    def _add(self, record):
        agent = self.totals.setdefault(record['agent'], dict(
            {'requests': 0, 'errors': 0, 'without_usage': 0, 'last_request_at': None},
            **{field: 0 for field in USAGE_FIELDS}))
        agent['requests'] += 1
        if record.get('status', 0) >= 400:
            agent['errors'] += 1
        usage = record.get('usage')
        if usage:
            for field in USAGE_FIELDS:
                agent[field] += _number(usage.get(field))
        elif record.get('status', 0) < 400:
            agent['without_usage'] += 1
        agent['last_request_at'] = record.get('ts')

    def record(self, agent, path, status, model, usage):
        entry = {'ts': round(time.time(), 3), 'agent': agent, 'path': path.split('?', 1)[0],
                 'status': status, 'model': model, 'usage': usage}
        with self.lock:
            self._add(entry)
            if self.path:
                # Accounting must never break forwarding; totals stay in memory.
                try:
                    os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
                    with open(self.path, 'a', encoding='utf-8') as stream:
                        stream.write(json.dumps(entry, separators=(',', ':')) + '\n')
                except OSError as error:
                    print(f'[usage] could not append to {self.path}: {error}', flush=True)
        return entry

    def budget_tokens(self):
        # The token budget counts the team's input and output tokens, not the final evaluation's.
        with self.lock:
            return sum(v['input_tokens'] + v['output_tokens'] for name, v in self.totals.items()
                       if name != 'final-evaluation')

    def snapshot(self):
        with self.lock:
            agents = {name: dict(values) for name, values in self.totals.items()}
        team = {field: sum(values[field] for values in agents.values())
                for field in ('requests', 'errors', 'without_usage', *USAGE_FIELDS)}
        return {'agents': agents, 'team': team}
