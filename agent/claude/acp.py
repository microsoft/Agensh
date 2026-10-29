#!/usr/bin/env python3
"""Expose native Claude Code stream-json sessions through Agensh's ACP interface."""

import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import uuid

from config import TOOLS, config_dir, native_environment
from harness_config import load_config


class Adapter:
    def __init__(self):
        self.process = None
        self.session_id = None
        self.writer = threading.Lock()
        self.native_writer = threading.Lock()
        self.operation = threading.Lock()
        self.submission = threading.Lock()
        self.finished = threading.Event()
        self.cancelled = threading.Event()
        self.active = False
        self.last_error = None
        self.prompt_thread = None
        self.reader = None

    def send(self, message):
        with self.writer:
            sys.stdout.write(json.dumps({'jsonrpc': '2.0', **message}) + '\n')
            sys.stdout.flush()

    def result(self, identifier, data):
        self.send({'id': identifier, 'result': data})

    def error(self, identifier, text, code=-32603):
        self.send({'id': identifier, 'error': {'code': code, 'message': text}})

    def update(self, update):
        self.send({'method': 'session/update', 'params': {'sessionId': self.session_id, 'update': update}})

    def write_native(self, value):
        with self.native_writer:
            if self.process is None or self.process.poll() is not None:
                raise RuntimeError('Claude Code has exited')
            self.process.stdin.write((json.dumps(value) + '\n').encode())
            self.process.stdin.flush()

    def start_native(self, resume=False):
        settings = load_config()
        env = os.environ | native_environment(settings)
        for name in ('CLAUDE_CODE_OAUTH_TOKEN', 'CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR',
                     'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY'):
            env.pop(name, None)
        command = [os.environ.get('CLAUDE_BIN', '/usr/local/bin/claude-wrapped'), '--print',
            '--input-format', 'stream-json', '--output-format', 'stream-json', '--verbose',
            '--include-partial-messages', '--permission-mode', 'bypassPermissions',
            '--model', settings.model, '--effort', settings.reasoning_effort,
            '--tools', ','.join(TOOLS), '--strict-mcp-config',
            '--mcp-config', str(config_dir() / 'mcp.json'), '--settings', str(config_dir() / 'settings.json'),
            '--resume' if resume else '--session-id', self.session_id]
        self.process = subprocess.Popen(command, cwd=Path.cwd(), env=env, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=sys.stderr)
        self.reader = threading.Thread(target=self.read_native, daemon=True)
        self.reader.start()

    def read_native(self):
        try:
            for line in self.process.stdout:
                if not line.strip():
                    continue
                event = json.loads(line)
                kind = event.get('type')
                if kind == 'system' and event.get('subtype') == 'init':
                    if event.get('session_id') != self.session_id:
                        raise RuntimeError('Claude Code did not restore the requested session')
                if not self.active:
                    continue
                if kind == 'assistant':
                    for block in event.get('message', {}).get('content', []):
                        if block.get('type') == 'text':
                            self.update({'sessionUpdate': 'agent_message_chunk',
                                         'content': {'type': 'text', 'text': block.get('text', '')}})
                        elif block.get('type') == 'tool_use':
                            self.update({'sessionUpdate': 'tool_call', 'toolCallId': block['id'],
                                'title': block['name'], 'kind': 'other', 'status': 'in_progress',
                                'rawInput': block.get('input', {})})
                elif kind == 'user':
                    blocks = event.get('message', {}).get('content', [])
                    if isinstance(blocks, list):
                        for block in blocks:
                            if isinstance(block, dict) and block.get('type') == 'tool_result':
                                self.update({'sessionUpdate': 'tool_call_update',
                                    'toolCallId': block['tool_use_id'],
                                    'status': 'failed' if block.get('is_error') else 'completed',
                                    'rawOutput': block.get('content')})
                else:
                    # Native streaming and retry events keep the ACP silence watchdog informed.
                    self.update({'sessionUpdate': 'agent_thought_chunk', 'content': {'type': 'text', 'text': ''}})
                if kind == 'result':
                    if event.get('is_error') or event.get('subtype') != 'success':
                        self.last_error = '; '.join(str(error) for error in event.get('errors') or []) or event.get('result') or 'Claude Code turn failed'
                    metrics = {model: {key: value for key, value in usage.items()
                               if key in ('contextWindow', 'maxOutputTokens', 'inputTokens', 'outputTokens')}
                               for model, usage in event.get('modelUsage', {}).items() if isinstance(usage, dict)}
                    print('[claude-acp] model usage ' + json.dumps(metrics), file=sys.stderr, flush=True)
                    self.finished.set()
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
            self.last_error = str(error)
            self.finished.set()
        finally:
            if self.active and not self.finished.is_set():
                self.last_error = 'Claude Code exited before the prompt completed'
                self.finished.set()

    def close_native(self):
        if self.process is None:
            return
        try:
            self.process.stdin.close()
            self.process.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.reader:
            self.reader.join(timeout=2)
        self.process.stdout.close()
        self.process = None

    def open_session(self, params, resume=False):
        if Path(params['cwd']).resolve() != Path.cwd().resolve():
            raise ValueError('ACP cwd must match the worker workspace')
        if params.get('mcpServers'):
            raise ValueError('MCP servers are supplied by the worker configuration')
        identifier = str(uuid.UUID(params['sessionId'])) if resume else str(uuid.uuid4())
        if resume and not list((config_dir() / 'projects').rglob(identifier + '.jsonl')):
            raise ValueError('Claude Code session is missing: ' + identifier)
        self.close_native()
        self.session_id = identifier
        self.start_native(resume)
        return {} if resume else {'sessionId': identifier}

    def prompt(self, identifier, params):
        try:
            if params.get('sessionId') != self.session_id or self.process is None:
                raise ValueError('Unknown Claude Code session')
            blocks = params['prompt']
            if any(block.get('type') != 'text' for block in blocks):
                raise ValueError('This ACP adapter accepts text prompts only')
            with self.submission:
                if self.cancelled.is_set():
                    self.finished.set()
                else:
                    self.write_native({'type': 'user', 'session_id': self.session_id,
                        'parent_tool_use_id': None, 'message': {'role': 'user', 'content': blocks}})
            self.finished.wait()
            if self.last_error and not self.cancelled.is_set():
                raise RuntimeError(self.last_error)
            self.result(identifier, {'stopReason': 'cancelled' if self.cancelled.is_set() else 'end_turn'})
        except (OSError, ValueError, KeyError, RuntimeError) as error:
            self.error(identifier, str(error))
        finally:
            self.active = False
            self.operation.release()

    def dispatch(self, message):
        identifier, method, params = message.get('id'), message.get('method'), message.get('params') or {}
        if method == 'session/cancel':
            if self.active and params.get('sessionId') == self.session_id:
                self.cancelled.set()
                try:
                    with self.submission:
                        self.write_native({'type': 'control_request', 'request_id': str(uuid.uuid4()),
                                           'request': {'subtype': 'interrupt'}})
                except (OSError, RuntimeError):
                    self.finished.set()
            return
        if not self.operation.acquire(blocking=False):
            self.error(identifier, 'Another ACP operation is active')
            return
        try:
            if method == 'initialize':
                self.result(identifier, {'protocolVersion': 1, 'agentCapabilities': {'loadSession': True},
                    'agentInfo': {'name': 'agensh-claude', 'version': '1.0'}})
            elif method in ('session/new', 'session/load'):
                self.result(identifier, self.open_session(params, method == 'session/load'))
            elif method == 'session/prompt':
                self.finished.clear();self.cancelled.clear();self.last_error = None;self.active = True
                self.prompt_thread = threading.Thread(target=self.prompt, args=(identifier, params), daemon=True)
                self.prompt_thread.start()
                return
            else:
                self.error(identifier, 'Method not implemented: ' + str(method), -32601)
        except (OSError, ValueError, KeyError, RuntimeError) as error:
            self.error(identifier, str(error))
        self.operation.release()

    def run(self):
        try:
            for line in sys.stdin.buffer:
                try:
                    self.dispatch(json.loads(line))
                except (ValueError, AttributeError) as error:
                    self.error(None, str(error), -32700)
        finally:
            self.dispatch({'method': 'session/cancel', 'params': {'sessionId': self.session_id}})
            if self.prompt_thread:
                self.prompt_thread.join(timeout=8)
            self.close_native()


if __name__ == '__main__':
    Adapter().run()
