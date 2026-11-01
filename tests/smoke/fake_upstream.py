#!/usr/bin/env python3
# Minimal model upstream for tests: answers Responses, Chat Completions and
# Anthropic Messages requests, as JSON or SSE, with fixed token usage.

import json
import os
import http.server

# Fixed counts let tests check the proxy's per-agent accounting exactly.
RESPONSES_USAGE = {'input_tokens': 120, 'input_tokens_details': {'cached_tokens': 20},
                   'output_tokens': 30, 'output_tokens_details': {'reasoning_tokens': 10}}
CHAT_USAGE = {'prompt_tokens': 50, 'prompt_tokens_details': {'cached_tokens': 5},
              'completion_tokens': 7, 'completion_tokens_details': {'reasoning_tokens': 2}}
MESSAGES_USAGE = {'input_tokens': 40, 'cache_read_input_tokens': 60,
                  'cache_creation_input_tokens': 8, 'output_tokens': 25}


def sse(events):
    return ''.join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events).encode()


def responses(stream):
    response = {'id': 'resp_1', 'object': 'response', 'status': 'completed', 'model': 'fake',
                'output': [{'type': 'message', 'role': 'assistant',
                            'content': [{'type': 'output_text', 'text': 'ok'}]}],
                'usage': RESPONSES_USAGE}
    if not stream:
        return 'application/json', json.dumps(response).encode()
    return 'text/event-stream', sse([
        ('response.created', {'type': 'response.created', 'response': {**response, 'usage': None}}),
        ('response.output_text.delta', {'type': 'response.output_text.delta', 'delta': 'ok'}),
        ('response.completed', {'type': 'response.completed', 'response': response})])


def chat(stream):
    if not stream:
        return 'application/json', json.dumps({
            'id': 'chat_1', 'object': 'chat.completion', 'model': 'fake',
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'ok'}}],
            'usage': CHAT_USAGE}).encode()
    chunks = [{'choices': [{'index': 0, 'delta': {'content': 'ok'}}], 'usage': None},
              {'choices': [], 'usage': CHAT_USAGE}]
    return 'text/event-stream', (''.join(f'data: {json.dumps(c)}\n\n' for c in chunks) + 'data: [DONE]\n\n').encode()


def messages(stream):
    if not stream:
        return 'application/json', json.dumps({
            'id': 'msg_1', 'type': 'message', 'role': 'assistant', 'model': 'fake',
            'content': [{'type': 'text', 'text': 'ok'}], 'usage': MESSAGES_USAGE}).encode()
    start_usage = {**MESSAGES_USAGE, 'output_tokens': 1}
    return 'text/event-stream', sse([
        ('message_start', {'type': 'message_start', 'message': {'id': 'msg_1', 'usage': start_usage}}),
        ('content_block_delta', {'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': 'ok'}}),
        ('message_delta', {'type': 'message_delta', 'usage': {'output_tokens': MESSAGES_USAGE['output_tokens']}}),
        ('message_stop', {'type': 'message_stop'})])


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        self.reply(200, 'text/plain', b'ok\n')

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', '0') or 0))
        try:
            request = json.loads(body or b'{}')
        except ValueError:
            request = {}
        # Tests read what the proxy actually forwarded.
        RECEIVED.append({'path': self.path, 'request': request, 'authorization': self.headers.get('Authorization')})
        stream = bool(request.get('stream'))
        path = self.path.split('?', 1)[0].rstrip('/')
        if request.get('fail'):
            self.reply(400, 'application/json', b'{"error":{"message":"bad request"}}')
        elif path.endswith('/messages'):
            self.reply(200, *messages(stream))
        elif path.endswith('/chat/completions'):
            self.reply(200, *chat(stream))
        elif path.endswith('/responses'):
            self.reply(200, *responses(stream))
        else:
            self.reply(404, 'application/json', b'{"error":"not found"}')

    def reply(self, status, content_type, payload):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


RECEIVED = []


def serve(host='0.0.0.0', port=None):
    server = http.server.ThreadingHTTPServer((host, int(port or os.environ.get('PORT', '8080'))), Handler)
    return server


if __name__ == '__main__':
    server = serve()
    print(f'fake upstream listening on {server.server_address}', flush=True)
    server.serve_forever()
