#!/usr/bin/env python3
# Smoke checks for the CI merge gate on a live software-project stack: required checks
# and protected files on main, CI statuses on merged PRs, a protected-file PR that a
# worker cannot merge, and a broken main that holds ordinary PRs while a fix-main PR
# merges, then recovers. Usage: check_gate.py ENV_FILE TASK_OUT

import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agensh import quality  # noqa: E402

ENV = dict(line.split('=', 1) for line in Path(sys.argv[1]).read_text().splitlines() if '=' in line)
TASK_OUT = Path(sys.argv[2])
ORG, PORT = ENV['ORG_NAME'], ENV['EDGE_HTTP_PORT']
ADMIN = (ENV['GITEA_ADMIN_USER'], ENV['GITEA_ADMIN_PASSWORD'])
BASE = f'http://localhost:{PORT}/api/v1/repos/{ORG}/main'
CLONE = f'http://{ADMIN[0]}:{ADMIN[1]}@localhost:{PORT}/{ORG}/main.git'


def log(message):
    print(f'[gate {time.strftime("%H:%M:%S", time.gmtime())}] {message}', file=sys.stderr, flush=True)


def fail(message):
    log(f'FAIL: {message}')
    sys.exit(1)


def api(method, path, body=None, token=None):
    auth = f'token {token}' if token else 'Basic ' + base64.b64encode(':'.join(ADMIN).encode()).decode()
    request = urllib.request.Request(BASE + path, method=method,
                                     data=None if body is None else json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json', 'Authorization': auth})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode()
            return response.status, json.loads(text) if text else None
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode(errors='replace')


def wait(what, probe, timeout=300, interval=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = probe()
        if value:
            return value
        time.sleep(interval)
    fail(f'timed out after {timeout}s waiting for {what}')


def status_of(sha, context):
    code, combined = api('GET', f'/commits/{sha}/status')
    return quality.check_state(combined.get('statuses'), context) if code == 200 else None


def main_sha():
    return api('GET', '/branches/main')[1]['commit']['id']


def health():
    path = TASK_OUT / 'main-health.json'
    return json.loads(path.read_text()) if path.is_file() else {}


def worker_token():
    path = Path(ENV['DATA_ROOT']) / ENV['PROFILE'] / f'tokens/agent-{ORG}-worker1.token'
    return subprocess.run(['sudo', '-n', 'cat', str(path)], check=True, capture_output=True, text=True).stdout.strip()


def push_branch(work, branch, files, message, base='main'):
    git = lambda *a: subprocess.run(['git', '-C', str(work), '-c', 'user.name=Smoke', '-c',
                                     'user.email=smoke@localhost', *a], check=True, capture_output=True)
    git('fetch', '-q', 'origin', base)
    git('checkout', '-q', '-B', branch, 'FETCH_HEAD')
    for name, text in files.items():
        (work / name).parent.mkdir(parents=True, exist_ok=True)
        (work / name).write_text(text)
        git('add', name)
    git('commit', '-qm', message)
    git('push', '-q', '-f', 'origin', f'HEAD:refs/heads/{branch}')
    return subprocess.run(['git', '-C', str(work), 'rev-parse', 'HEAD'], check=True, capture_output=True,
                          text=True).stdout.strip()


def open_pr(branch, title):
    code, reply = api('POST', '/pulls', {'head': branch, 'base': 'main', 'title': title})
    if code != 201:
        fail(f'cannot open {branch}: {code} {reply}')
    return reply['number']


def merge(number, token):
    code, reply = api('POST', f'/pulls/{number}/merge', {'Do': 'merge'}, token=token)
    return code == 200, f'{code} {str(reply)[:160]}'


def check_protection():
    code, protection = api('GET', '/branch_protections/main')
    if code != 200:
        fail(f'no branch protection on main ({code})')
    if not protection.get('enable_status_check') or set(protection.get('status_check_contexts') or []) != set(
            quality.REQUIRED_CHECKS):
        fail(f'main does not require {quality.REQUIRED_CHECKS}: {protection.get("status_check_contexts")}')
    if '.gitea/workflows/**' not in (protection.get('protected_file_patterns') or ''):
        fail(f'workflow files are not protected: {protection.get("protected_file_patterns")!r}')
    code, labels = api('GET', '/labels')
    if quality.FIX_LABEL not in {label['name'] for label in labels or []}:
        fail(f'the {quality.FIX_LABEL} label is missing')
    log(f'main requires {", ".join(quality.REQUIRED_CHECKS)}; protected: {protection["protected_file_patterns"]}')


def check_merged_prs():
    code, pulls = api('GET', '/pulls?state=closed&limit=50')
    merged = [p for p in pulls if p.get('merged')]
    for pull in merged:
        for context in quality.REQUIRED_CHECKS:
            if status_of(pull['head']['sha'], context) != 'success':
                fail(f'merged PR #{pull["number"]} lacks a successful {context}')
    sha = main_sha()
    state = wait(f'{quality.MAIN_CHECK} on main', lambda: status_of(sha, quality.MAIN_CHECK) in ('success', 'failure')
                 and status_of(sha, quality.MAIN_CHECK))
    if state != 'success':
        fail(f'{quality.MAIN_CHECK} is {state} on main {sha[:12]}')
    log(f'{len(merged)} merged PR(s) passed both required checks; main passes {quality.MAIN_CHECK}')


def check_protected_files(work, token):
    # The PR passes both checks, so only file protection can refuse it.
    head = push_branch(work, 'smoke/protected', {'.agensh/acceptance.txt': 'weaker checks\n'},
                       'Change a protected acceptance file')
    number = open_pr('smoke/protected', 'smoke: change a protected file')
    wait('both checks on the protected-file PR', lambda: all(
        status_of(head, c) == 'success' for c in quality.REQUIRED_CHECKS), timeout=300)
    merged, reply = merge(number, token)
    if merged or api('GET', f'/pulls/{number}')[1].get('merged'):
        fail('a worker merged a change to a protected file')
    if 'protected' not in reply.lower():
        fail(f'the merge was refused for another reason: {reply}')
    api('PATCH', f'/pulls/{number}', {'state': 'closed'})
    log(f'a worker cannot merge a protected-file change, though its checks pass ({reply.split()[0]})')


def check_broken_main(work, token):
    breaking = push_branch(work, 'main', {'widget.py': 'def greet(name):\n    return "broken"\n'},
                           'Break greet on purpose')
    wait('the full suite to fail on the broken main', lambda: status_of(breaking, quality.MAIN_CHECK) == 'failure')
    wait('the driver to mark main red', lambda: health().get('red'), timeout=120)
    ordinary_head = push_branch(work, 'smoke/ordinary', {'smoke/ordinary.txt': 'ordinary\n'}, 'Ordinary change')
    ordinary = open_pr('smoke/ordinary', 'smoke: ordinary change')
    wait('the ordinary PR to be held', lambda: status_of(ordinary_head, quality.HEALTH_CHECK) == 'pending', timeout=120)
    fix_head = push_branch(work, 'smoke/fix', {'widget.py': 'def greet(name):\n    return f"hello {name}"\n'},
                           'Restore greet')
    fix = open_pr('smoke/fix', f'[{quality.FIX_LABEL}] restore greet')
    wait('the fix-main PR to pass both checks', lambda: all(
        status_of(fix_head, c) == 'success' for c in quality.REQUIRED_CHECKS), timeout=300)
    merged, reply = merge(fix, token)
    if not merged:
        fail(f'the fix-main PR did not merge: {reply}')
    wait('the driver to mark main green', lambda: not health().get('red'), timeout=300)
    wait('the ordinary PR to be released', lambda: status_of(ordinary_head, quality.HEALTH_CHECK) == 'success',
         timeout=120)
    api('PATCH', f'/pulls/{ordinary}', {'state': 'closed'})
    actions = [entry['action'] for entry in health().get('history', [])]
    if actions[:2] != ['broken', 'recovered']:
        fail(f'unexpected main-health history: {actions}')
    log('a broken main held an ordinary PR, merged the fix-main PR, then recovered')


def main():
    check_protection()
    check_merged_prs()
    token = worker_token()
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory, 'work')
        subprocess.run(['git', 'clone', '-q', CLONE, str(work)], check=True)
        check_protected_files(work, token)
        check_broken_main(work, token)
    log('PASS')


if __name__ == '__main__':
    main()
