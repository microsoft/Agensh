#!/usr/bin/env python3
# Scripted ACP harness for the smoke test. It replaces the Pi adapter inside a
# worker and performs one fixed contribution through the real team services:
# claim on the board, push a branch, open and merge a PR, publish a patch summary.

import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

AGENT = os.environ['AGENT_NAME']
ORG = os.environ['GITEA_ORG']
GITEA = os.environ.get('GITEA_HOST', 'http://gitea:3000').rstrip('/')
TOKEN = os.environ['GITEA_TOKEN']
BOARD = os.environ.get('BOARD_SERVICE_URL', 'http://board-service:8660').rstrip('/')
BOARD_ID = os.environ.get('BOARD_IDS', 'pbench-top').split(',')[0].strip()
REPO = 'main'
# The worker's idle watchdog reads native session-file times from the Pi location.
SESSIONS = Path(os.environ.get('PI_CODING_AGENT_DIR', str(Path.home() / '.pi/agent'))) / 'sessions'
DONE = Path.home() / '.stub' / 'contribution.json'


def log(message):
    print(f'[stub-acp {AGENT}] {message}', file=sys.stderr, flush=True)


def http(method, url, body=None, headers=None, timeout=30):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method=method, headers={
        'Content-Type': 'application/json', 'Accept': 'application/json', **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode()
            try:
                return response.status, json.loads(text) if text else None
            except ValueError:  # Streamed model replies are SSE text.
                return response.status, text
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode(errors='replace')


def gitea(method, path, body=None):
    return http(method, f'{GITEA}/api/v1{path}', body, {'Authorization': f'token {TOKEN}'})


def board_note(kind, content, delegation_id=None):
    status, reply = http('POST', f'{BOARD}/board/{BOARD_ID}/note', {
        'thread_id': AGENT, 'type': kind, 'content': content, 'delegation_id': delegation_id})
    if status != 200 or not isinstance(reply, dict) or reply.get('status') != 'admitted':
        raise RuntimeError(f'board {kind} not admitted: {status} {reply}')
    return reply['label']


def git(*arguments, cwd):
    subprocess.run(['git', *arguments], cwd=cwd, check=True, stdout=sys.stderr, stderr=sys.stderr)


def retry(action, attempts=12, delay=5):
    for attempt in range(1, attempts + 1):
        try:
            return action()
        except Exception as error:  # Retry transient service and Git errors alike.
            if attempt == attempts:
                raise
            log(f'retry {attempt}/{attempts}: {error}')
            time.sleep(delay)


def model_requests():
    # Call the model route the way Pi would, with the key Pi's config was given.
    models = json.loads((SESSIONS.parent / 'models.json').read_text())
    provider = models['providers']['agensh']
    for stream in (True, False):
        status, reply = http('POST', provider['baseUrl'].rstrip('/') + '/responses',
                             {'model': provider['models'][0]['id'], 'input': 'smoke', 'stream': stream},
                             {'Authorization': f"Bearer {provider['apiKey']}"}, timeout=60)
        if status != 200:
            raise RuntimeError(f'model request failed: {status} {str(reply)[:200]}')


def contribute(plan=False):
    # One fixed change per worker; repeated prompts after success do nothing.
    if DONE.exists():
        return json.loads(DONE.read_text())
    model_marker = DONE.parent / 'model-requests.done'
    if not model_marker.exists():
        model_requests()
        model_marker.parent.mkdir(parents=True, exist_ok=True)
        model_marker.write_text('2\n')
    path = f'smoke/{AGENT}.txt'
    work = Path('/work/smoke-checkout')
    branch = f'smoke/{AGENT}'
    board_note('CLAIM', f'smoke: adding {path} for #1', delegation_id='smoke')

    def push():
        if work.exists():
            subprocess.run(['rm', '-rf', str(work)], check=True)
        git('clone', '--quiet', f'{GITEA}/{ORG}/{REPO}.git', str(work), cwd='/work')
        git('checkout', '-q', '-b', branch, cwd=work)
        (work / path).parent.mkdir(parents=True, exist_ok=True)
        (work / path).write_text(f'written by {AGENT}\n')
        git('add', path, cwd=work)
        git('commit', '-q', '-m', f'smoke: add {path}', cwd=work)
        git('push', '-q', '--force', 'origin', branch, cwd=work)
    retry(push)

    def open_pr():
        status, reply = gitea('POST', f'/repos/{ORG}/{REPO}/pulls',
                              {'head': branch, 'base': 'main',
                               'title': f'{"[plan] " if plan else ""}smoke: add {path}'})
        if status == 409:  # An earlier attempt already opened it.
            status, pulls = gitea('GET', f'/repos/{ORG}/{REPO}/pulls?state=open&limit=50')
            matches = [p for p in pulls or [] if p['head']['ref'] == branch] if status == 200 else []
            if matches:
                return matches[0]['number']
        if status != 201:
            raise RuntimeError(f'open PR failed: {status} {reply}')
        return reply['number']
    number = retry(open_pr)

    def merge():
        # Gitea computes mergeability asynchronously after a PR is opened.
        status, reply = gitea('POST', f'/repos/{ORG}/{REPO}/pulls/{number}/merge', {'Do': 'merge'})
        if status == 200:
            return
        status_after, pull = gitea('GET', f'/repos/{ORG}/{REPO}/pulls/{number}')
        if status_after == 200 and pull.get('merged'):
            return
        raise RuntimeError(f'merge PR #{number} failed: {status} {reply}')
    # Packs with a CI gate refuse the merge until the PR's checks pass.
    retry(merge, attempts=72)

    def on_main():
        status, _ = gitea('GET', f'/repos/{ORG}/{REPO}/contents/{path}?ref=main')
        if status != 200:
            raise RuntimeError(f'{path} is not on main yet ({status})')
    retry(on_main, attempts=6, delay=2)

    label = board_note('PATCH_SUMMARY',
                       f'files={path} | idea=smoke contribution | evidence=PR #{number} merged; '
                       f'{path} confirmed on main', delegation_id='smoke')
    result = {'agent': AGENT, 'path': path, 'pr': number, 'patch_label': label}
    DONE.parent.mkdir(parents=True, exist_ok=True)
    DONE.write_text(json.dumps(result) + '\n')
    log(f'contribution complete: {result}')
    return result


class Adapter:
    def __init__(self):
        self.writer = threading.Lock()
        self.session_id = None
        self.journal = None

    def send(self, record):
        with self.writer:
            sys.stdout.write(json.dumps({'jsonrpc': '2.0', **record}) + '\n')
            sys.stdout.flush()

    def record(self, entry):
        with self.journal.open('a') as stream:
            stream.write(json.dumps({'ts': time.time(), **entry}) + '\n')

    def open_session(self, parameters, load):
        if Path(parameters['cwd']).resolve() != Path.cwd().resolve():
            raise ValueError('ACP cwd must match the worker workspace')
        SESSIONS.mkdir(parents=True, exist_ok=True)
        identifier = parameters['sessionId'] if load else uuid.uuid4().hex
        journal = SESSIONS / f'stub_{identifier}.jsonl'
        if load and not journal.exists():
            raise ValueError('stub session is missing: ' + identifier)
        self.session_id, self.journal = identifier, journal
        self.record({'event': 'load' if load else 'new'})
        return {} if load else {'sessionId': identifier}

    def prompt(self, identifier, parameters):
        if parameters.get('sessionId') != self.session_id:
            self.send({'id': identifier, 'error': {'code': -32602, 'message': 'Unknown stub session'}})
            return
        text = '\n\n'.join(block.get('text', '') for block in parameters.get('prompt', []))
        self.record({'event': 'prompt', 'chars': len(text), 'head': text[:200]})
        try:
            # A planner's PR is titled `[plan] ...` so the driver wakes the rest of the team.
            result = contribute(plan='`[plan] <summary>`' in text)
        except Exception as error:
            self.record({'event': 'error', 'message': str(error)})
            log(f'contribution failed: {error}')
            self.send({'id': identifier, 'error': {'code': -32603, 'message': str(error)}})
            return
        self.send({'method': 'session/update', 'params': {'sessionId': self.session_id, 'update': {
            'sessionUpdate': 'agent_message_chunk',
            'content': {'type': 'text', 'text': f'smoke contribution: PR #{result["pr"]}'}}}})
        self.record({'event': 'end_turn'})
        self.send({'id': identifier, 'result': {'stopReason': 'end_turn'}})

    def dispatch(self, message):
        identifier, method = message.get('id'), message.get('method')
        parameters = message.get('params') or {}
        if method == 'session/cancel' or 'id' not in message:
            return
        try:
            if method == 'initialize':
                self.send({'id': identifier, 'result': {'protocolVersion': 1,
                           'agentCapabilities': {'loadSession': True},
                           'agentInfo': {'name': 'stub', 'version': '0'}}})
            elif method in ('session/new', 'session/load'):
                self.send({'id': identifier, 'result': self.open_session(parameters, method == 'session/load')})
            elif method == 'session/prompt':
                self.prompt(identifier, parameters)
            else:
                self.send({'id': identifier, 'error': {'code': -32601, 'message': f'Method not implemented: {method}'}})
        except (OSError, ValueError, KeyError) as error:
            self.send({'id': identifier, 'error': {'code': -32603, 'message': str(error)}})

    def run(self):
        for line in sys.stdin.buffer:
            try:
                message = json.loads(line)
            except ValueError as error:
                self.send({'id': None, 'error': {'code': -32700, 'message': str(error)}})
                continue
            if isinstance(message, dict):
                self.dispatch(message)


if __name__ == '__main__':
    Adapter().run()
