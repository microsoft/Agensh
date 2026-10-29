#!/usr/bin/env python3
"""Expose the selected Pi release's native RPC runtime through Agensh's ACP subset.

The existing root bridge still owns the Unix socket, worker UID, process cleanup
and archives. Pi owns tools, model requests, compaction, retries and JSONL sessions.
"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading

from config import agent_dir
from harness_config import load_config


class PiProcess:
    def __init__(self, cwd, session_file, on_event, on_exit):
        config = load_config()
        command = [os.environ.get('PI_BIN', '/usr/local/bin/pi-wrapped'), '--mode', 'rpc',
                   '--offline', '--no-approve', '--no-extensions', '--extension', 'builtin:mcp',
                   '--no-prompt-templates', '--no-themes',
                   '--provider', 'agensh', '--model', config.model,
                   '--thinking', 'off' if config.reasoning_effort == 'none' else config.reasoning_effort,
                   '--session-dir', str(agent_dir() / 'sessions')]
        # Explicitly admit workspace skill instructions while unattended project
        # trust continues to protect the generated MCP/runtime configuration.
        workspace = Path(cwd).resolve()
        skill_directories = [workspace / '.pi' / 'skills']
        for parent in (workspace, *workspace.parents):
            skill_directories.append(parent / '.agents' / 'skills')
            if (parent / '.git').exists():
                break
        for directory in skill_directories:
            if directory.is_dir():
                command.extend(['--skill', str(directory)])
        if session_file is not None:
            command.extend(['--session', str(session_file)])
        self.process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=sys.stderr)
        self.condition = threading.Condition()
        self.writer = threading.Lock()
        self.pending = {}
        self.sequence = 0
        self.exited = False
        self.on_event, self.on_exit = on_event, on_exit
        self.reader = threading.Thread(target=self.read, daemon=True)
        self.reader.start()

    def read(self):
        try:
            for line in self.process.stdout:
                record = json.loads(line)
                if record.get('type') == 'response':
                    with self.condition:
                        future = self.pending.pop(record.get('id'), None)
                        if future is not None:
                            future['record'] = record
                            self.condition.notify_all()
                else:
                    self.on_event(record)
        except (OSError, ValueError) as error:
            print('[pi-acp] RPC reader failed: ' + str(error), file=sys.stderr, flush=True)
        finally:
            with self.condition:
                self.exited = True
                self.condition.notify_all()
            self.on_exit()

    def request(self, kind, timeout=60, **parameters):
        with self.condition:
            if self.exited:
                raise RuntimeError('Pi closed stdout')
            self.sequence += 1
            identifier = str(self.sequence)
            future = {}
            self.pending[identifier] = future
        try:
            with self.writer:
                self.process.stdin.write((json.dumps({'id': identifier, 'type': kind, **parameters}) + '\n').encode())
                self.process.stdin.flush()
            with self.condition:
                ready = self.condition.wait_for(lambda: 'record' in future or self.exited, timeout=timeout)
                if not ready:
                    raise TimeoutError('Pi RPC timed out: ' + kind)
                if 'record' not in future:
                    raise RuntimeError('Pi closed stdout during ' + kind)
            response = future['record']
            if not response.get('success'):
                raise RuntimeError(response.get('error', 'Pi RPC failed: ' + kind))
            return response.get('data') or {}
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
        self.pi = None
        self.session_id = None
        self.writer = threading.Lock()
        self.operation = threading.Lock()
        self.submission = threading.Lock()
        self.finished = threading.Event()
        self.cancelled = threading.Event()
        self.prompt_thread = None
        self.prompt_active = False
        self.last_error = None

    def send(self, record):
        with self.writer:
            sys.stdout.write(json.dumps({'jsonrpc': '2.0', **record}) + '\n')
            sys.stdout.flush()

    def result(self, identifier, result):
        self.send({'id': identifier, 'result': result})

    def error(self, identifier, message, code=-32603):
        self.send({'id': identifier, 'error': {'code': code, 'message': message}})

    def on_exit(self):
        if self.prompt_active:
            self.last_error = 'Pi exited before the prompt settled'
            self.finished.set()

    def on_event(self, event):
        if not self.prompt_active:
            return
        kind = event.get('type')
        update = {'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': ''}}
        if kind == 'message_update':
            delta = event.get('assistantMessageEvent', {})
            if delta.get('type') in ('text_delta', 'thinking_delta'):
                update['sessionUpdate'] = ('agent_thought_chunk' if delta['type'] == 'thinking_delta'
                                           else 'agent_message_chunk')
                update['content']['text'] = delta.get('delta', '')
        elif kind == 'message_end' and event.get('message', {}).get('role') == 'assistant':
            message = event['message']
            self.last_error = (message.get('errorMessage', 'Pi model request failed')
                               if message.get('stopReason') == 'error' else None)
        elif kind == 'tool_execution_start':
            update = {'sessionUpdate': 'tool_call', 'toolCallId': event['toolCallId'],
                      'title': event['toolName'], 'kind': 'other', 'status': 'in_progress',
                      'rawInput': event.get('args')}
        elif kind in ('tool_execution_update', 'tool_execution_end'):
            update = {'sessionUpdate': 'tool_call_update', 'toolCallId': event['toolCallId'],
                      'status': ('failed' if event.get('isError') else 'completed')
                      if kind == 'tool_execution_end' else 'in_progress',
                      'rawOutput': event.get('result', event.get('partialResult'))}
        self.send({'method': 'session/update', 'params': {'sessionId': self.session_id, 'update': update}})
        # agent_end can be followed by native retry or compaction. Only settled ends ACP's prompt.
        if kind == 'agent_settled':
            if event.get('aborted'):
                self.cancelled.set()
            self.finished.set()

    def open_session(self, parameters, load=False):
        cwd = Path(parameters['cwd']).resolve()
        if cwd != Path.cwd().resolve():
            raise ValueError('ACP cwd must match the worker workspace')
        if parameters.get('mcpServers'):
            raise ValueError('MCP servers are supplied by the worker configuration')
        session_file = None
        if load:
            identifier = parameters['sessionId']
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', identifier):
                raise ValueError('Invalid Pi session ID')
            for candidate in (agent_dir() / 'sessions').glob('*_' + identifier + '.jsonl'):
                with candidate.open() as source:
                    header = json.loads(source.readline())
                if header.get('id') == identifier and Path(header['cwd']).resolve() == cwd:
                    session_file = candidate
                    break
            if session_file is None:
                raise ValueError('Pi session is missing from this workspace: ' + identifier)
        if self.pi is not None:
            self.pi.close()
        self.pi = PiProcess(str(cwd), session_file, self.on_event, self.on_exit)
        state = self.pi.request('get_state')
        if load and state.get('sessionId') != parameters['sessionId']:
            raise RuntimeError('Pi did not restore the requested session')
        self.session_id = state['sessionId']
        return {} if load else {'sessionId': self.session_id}

    def prompt(self, identifier, parameters):
        error_message = None
        stop_reason = 'end_turn'
        try:
            if self.pi is None or parameters.get('sessionId') != self.session_id:
                raise ValueError('Unknown Pi session')
            blocks = parameters['prompt']
            if any(block.get('type') != 'text' for block in blocks):
                raise ValueError('This ACP adapter accepts text prompts only')
            with self.submission:
                response = ({'disposition': 'handled'} if self.cancelled.is_set() else
                            self.pi.request('prompt', message='\n\n'.join(block['text'] for block in blocks)))
            if response.get('disposition') != 'handled':
                self.finished.wait()
            if self.last_error and not self.cancelled.is_set():
                raise RuntimeError(self.last_error)
            stop_reason = 'cancelled' if self.cancelled.is_set() else 'end_turn'
        except (OSError, ValueError, TypeError, KeyError, RuntimeError, TimeoutError) as error:
            error_message = str(error)
        finally:
            self.prompt_active = False
            self.operation.release()
        if error_message is not None:
            self.error(identifier, error_message)
        else:
            self.result(identifier, {'stopReason': stop_reason})

    def cancel(self, parameters):
        if self.pi is not None and parameters.get('sessionId') == self.session_id and self.prompt_active:
            self.cancelled.set()
            try:
                # Serialize with acceptance so an early cancel cannot precede its prompt.
                with self.submission:
                    if self.prompt_active:
                        self.pi.request('abort', timeout=8)
            except (OSError, RuntimeError, TimeoutError) as error:
                print('[pi-acp] cancellation failed: ' + str(error), file=sys.stderr, flush=True)

    def dispatch(self, message):
        identifier, method = message.get('id'), message.get('method')
        parameters = message.get('params') or {}
        if method == 'session/cancel':
            self.cancel(parameters)
            return
        if 'id' not in message:
            return
        if method == 'initialize':
            self.result(identifier, {'protocolVersion': 1, 'agentCapabilities': {'loadSession': True},
                                     'agentInfo': {'name': 'pi', 'version': load_config().version}})
            return
        if not self.operation.acquire(blocking=False):
            self.error(identifier, 'A Pi operation is already in progress', -32600)
            return
        if method == 'session/prompt':
            self.finished.clear()
            self.cancelled.clear()
            self.last_error = None
            self.prompt_active = True
            self.prompt_thread = threading.Thread(target=self.prompt, args=(identifier, parameters), daemon=True)
            self.prompt_thread.start()
            return
        try:
            if method in ('session/new', 'session/load'):
                self.result(identifier, self.open_session(parameters, load=method == 'session/load'))
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
            if self.pi is not None:
                self.pi.close()


if __name__ == '__main__':
    Adapter().run()
