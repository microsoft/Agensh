#!/usr/bin/env python3
"""Adapt native Codex app-server threads and turns to Agensh's ACP clients."""

import json
import os
from pathlib import Path
import subprocess
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_config import load_config

class CodexProcess:
    def __init__(self, on_event, on_exit):
        self.process = subprocess.Popen([os.environ.get('CODEX_BIN', '/usr/local/bin/codex-wrapped'),
            'app-server', '--listen', 'stdio://', '--strict-config'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr)
        self.writer = threading.Lock()
        self.condition = threading.Condition()
        self.pending = {}
        self.sequence = 0
        self.exited = False
        self.on_event, self.on_exit = on_event, on_exit
        self.reader = threading.Thread(target=self.read, daemon=True)
        self.reader.start()

    def send(self, message):
        with self.writer:
            self.process.stdin.write((json.dumps(message) + '\n').encode())
            self.process.stdin.flush()

    def read(self):
        try:
            for line in self.process.stdout:
                message = json.loads(line)
                if 'id' in message and 'method' not in message:
                    with self.condition:
                        future = self.pending.pop(message['id'], None)
                        if future is not None:
                            future['response'] = message
                            self.condition.notify_all()
                elif 'id' in message:
                    method = message.get('method')
                    if method in ('item/commandExecution/requestApproval', 'item/fileChange/requestApproval'):
                        self.send({'id': message['id'], 'result': {'decision': 'accept'}})
                    elif method == 'mcpServer/elicitation/request':
                        self.send({'id': message['id'], 'result': {'action': 'cancel', 'content': None}})
                    else:
                        self.send({'id': message['id'], 'error': {'code': -32601,
                                  'message': 'Unsupported autonomous client request: ' + str(method)}})
                else:
                    self.on_event(message.get('method'), message.get('params') or {})
        except (ValueError, OSError) as error:
            print('[codex-acp] reader failed: ' + str(error), file=sys.stderr, flush=True)
        finally:
            with self.condition:
                self.exited = True
                self.condition.notify_all()
            self.on_exit()

    def request(self, method, parameters, timeout=60):
        with self.condition:
            if self.exited:
                raise RuntimeError('Codex closed stdout')
            self.sequence += 1
            identifier = self.sequence
            future = {}
            self.pending[identifier] = future
        try:
            self.send({'id': identifier, 'method': method, 'params': parameters})
            with self.condition:
                ready = self.condition.wait_for(lambda: 'response' in future or self.exited, timeout=timeout)
                if not ready:
                    raise TimeoutError('Codex request timed out: ' + method)
                if 'response' not in future:
                    raise RuntimeError('Codex closed stdout during ' + method)
            response = future['response']
            if 'error' in response:
                raise RuntimeError(response['error'].get('message', 'Codex request failed: ' + method))
            return response.get('result') or {}
        finally:
            with self.condition:
                self.pending.pop(identifier, None)

    def close(self):
        try:
            self.process.stdin.close()
        except OSError:
            pass
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.reader.join(timeout=2)
        self.process.stdout.close()


class Adapter:
    def __init__(self):
        self.codex = None
        self.session_id = None
        self.turn_id = None
        self.writer = threading.Lock()
        self.operation = threading.Lock()
        self.submission = threading.Lock()
        self.finished = threading.Event()
        self.cancelled = threading.Event()
        self.prompt_active = False
        self.prompt_thread = None
        self.last_error = None

    def send(self, message):
        with self.writer:
            print(json.dumps({'jsonrpc': '2.0', **message}), flush=True)

    def error(self, identifier, message, code=-32603):
        self.send({'id': identifier, 'error': {'code': code, 'message': message}})

    def on_exit(self):
        if self.prompt_active:
            self.last_error = 'Codex exited before the turn completed'
            self.finished.set()

    def on_event(self, method, parameters):
        if not self.prompt_active or parameters.get('threadId', self.session_id) != self.session_id:
            return
        update = {'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': ''}}
        if method in ('item/agentMessage/delta', 'item/reasoning/textDelta', 'item/reasoning/summaryTextDelta'):
            update['sessionUpdate'] = ('agent_message_chunk' if method == 'item/agentMessage/delta'
                                       else 'agent_thought_chunk')
            update['content']['text'] = parameters.get('delta', '')
        elif method in ('item/started', 'item/completed'):
            item = parameters.get('item', {})
            if item.get('type') in ('commandExecution', 'fileChange', 'mcpToolCall', 'dynamicToolCall'):
                update = {'sessionUpdate': 'tool_call' if method == 'item/started' else 'tool_call_update',
                          'toolCallId': item['id'], 'status': 'in_progress' if method == 'item/started' else
                          ('failed' if item.get('status') in ('failed', 'declined') else 'completed')}
                if method == 'item/started':
                    update.update(title=item.get('tool') or item.get('command') or item['type'],
                                  kind='other', rawInput=item)
                else:
                    update['rawOutput'] = item
        elif method == 'turn/started':
            self.turn_id = parameters['turn']['id']
        elif method == 'turn/completed':
            turn = parameters['turn']
            status = turn.get('status')
            if status == 'interrupted':
                self.cancelled.set()
            elif status != 'completed':
                self.last_error = (turn.get('error') or {}).get('message') or 'Codex turn failed: ' + str(status)
        self.send({'method': 'session/update', 'params': {'sessionId': self.session_id, 'update': update}})
        # A model message/tool completion can be followed by more work or retries.
        if method == 'turn/completed':
            self.finished.set()

    def open_session(self, parameters, load=False):
        cwd = str(Path(parameters['cwd']).resolve())
        if Path(cwd) != Path.cwd().resolve():
            raise ValueError('ACP cwd must match the worker workspace')
        if parameters.get('mcpServers'):
            raise ValueError('MCP servers are supplied by the worker configuration')
        if self.codex is not None:
            self.codex.close()
        self.codex = CodexProcess(self.on_event, self.on_exit)
        self.codex.request('initialize', {'clientInfo': {'name': 'agensh', 'title': 'Agensh', 'version': '1.0'}})
        self.codex.send({'method': 'initialized', 'params': {}})
        options = {'cwd': cwd, 'model': load_config().model, 'modelProvider': 'agensh',
                   'approvalPolicy': 'never', 'sandbox': 'danger-full-access'}
        if load:
            options.update(threadId=parameters['sessionId'], excludeTurns=True)
        result = self.codex.request('thread/resume' if load else 'thread/start', options)
        identifier = result['thread']['id']
        if load and identifier != parameters['sessionId']:
            raise RuntimeError('Codex did not restore the requested thread')
        self.session_id = identifier
        return {} if load else {'sessionId': identifier}

    def prompt(self, identifier, parameters):
        failure = None
        try:
            if self.codex is None or parameters.get('sessionId') != self.session_id:
                raise ValueError('Unknown Codex session')
            blocks = parameters['prompt']
            if any(block.get('type') != 'text' for block in blocks):
                raise ValueError('This ACP adapter accepts text prompts only')
            with self.submission:
                if not self.cancelled.is_set():
                    result = self.codex.request('turn/start', {'threadId': self.session_id,
                        'input': [{'type': 'text', 'text': '\n\n'.join(block['text'] for block in blocks)}],
                        'effort': load_config().reasoning_effort})
                    self.turn_id = result['turn']['id']
                else:
                    self.finished.set()
            self.finished.wait()
            if self.last_error:
                raise RuntimeError(self.last_error)
            stop_reason = 'cancelled' if self.cancelled.is_set() else 'end_turn'
        except (OSError, ValueError, TypeError, KeyError, RuntimeError, TimeoutError) as error:
            failure = str(error)
        finally:
            self.prompt_active = False
            self.operation.release()
        if failure is not None:
            self.error(identifier, failure)
        else:
            self.send({'id': identifier, 'result': {'stopReason': stop_reason}})

    def cancel(self, parameters):
        if self.prompt_active and parameters.get('sessionId') == self.session_id:
            self.cancelled.set()
            try:
                with self.submission:
                    if self.prompt_active and self.turn_id is not None:
                        self.codex.request('turn/interrupt', {'threadId': self.session_id,
                                                            'turnId': self.turn_id}, timeout=8)
            except (OSError, RuntimeError, TimeoutError) as error:
                print('[codex-acp] cancellation failed: ' + str(error), file=sys.stderr, flush=True)

    def dispatch(self, message):
        identifier, method, parameters = message.get('id'), message.get('method'), message.get('params') or {}
        if method == 'session/cancel':
            self.cancel(parameters)
            return
        if 'id' not in message:
            return
        if method == 'initialize':
            self.send({'id': identifier, 'result': {'protocolVersion': 1, 'agentCapabilities': {'loadSession': True},
                       'agentInfo': {'name': 'codex', 'version': '0.164.0'}}})
            return
        if not self.operation.acquire(blocking=False):
            self.error(identifier, 'A Codex operation is already in progress', -32600)
            return
        if method == 'session/prompt':
            self.finished.clear()
            self.cancelled.clear()
            self.turn_id, self.last_error, self.prompt_active = None, None, True
            self.prompt_thread = threading.Thread(target=self.prompt, args=(identifier, parameters), daemon=True)
            self.prompt_thread.start()
            return
        try:
            if method in ('session/new', 'session/load'):
                self.send({'id': identifier, 'result': self.open_session(parameters, load=method == 'session/load')})
            else:
                self.error(identifier, 'Method not implemented: ' + str(method), -32601)
        except (OSError, ValueError, TypeError, KeyError, RuntimeError, TimeoutError) as error:
            self.error(identifier, str(error))
        finally:
            self.operation.release()

    def run(self):
        try:
            for line in sys.stdin.buffer:
                try:
                    message = json.loads(line)
                    if not isinstance(message, dict):
                        raise ValueError('Expected a JSON object')
                    self.dispatch(message)
                except ValueError as error:
                    self.error(None, str(error), -32700)
        finally:
            self.cancel({'sessionId': self.session_id})
            if self.prompt_thread is not None:
                self.prompt_thread.join(timeout=8)
            if self.codex is not None:
                self.codex.close()


if __name__ == '__main__':
    Adapter().run()
