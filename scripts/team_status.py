#!/usr/bin/env python3
# Summarize a running team: per-worker containers, native activity, event queue,
# token usage and board entries, plus the team repository's pull requests.
# Read-only; uses `sudo -n docker` (override with DOCKER) and the profile file.

import argparse
import base64
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agensh.pack import PackError, load_pack  # noqa: E402
DOCKER = shlex.split(os.environ.get('DOCKER', 'sudo -n docker'))
# Native session journals, as scanned by the runner's idle watchdog.
SESSION_DIRS = {'copilot': 'home/.copilot/session-state', 'codex': 'home/.codex/sessions',
                'claude': 'home/.claude/projects', 'pi': 'home/.pi/agent/sessions'}
EVENT_STATES = ('pending', 'sending', 'retrying', 'failed', 'sent')


def read_profile(profile):
    path = ROOT / f'.env.{profile}'
    if not path.is_file():
        sys.exit(f'team_status: {path} not found')
    values = {}
    for line in path.read_text().splitlines():
        key, sep, value = line.partition('=')
        if sep and not key.startswith('#'):
            values[key.strip()] = value.strip()
    return values


def run(command, timeout=30):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, str(error)
    if result.returncode != 0:
        return None, (result.stderr or result.stdout).strip()[:300]
    return result.stdout, None


def containers(project):
    out, error = run([*DOCKER, 'ps', '-a', '--filter', f'label=com.docker.compose.project={project}',
                      '--format', '{{.Label "com.docker.compose.service"}}\t{{.Names}}\t{{.State}}\t{{.Status}}'])
    services = {}
    for line in (out or '').splitlines():
        service, name, state, status = (line.split('\t') + ['', '', '', ''])[:4]
        services[service] = {'name': name, 'state': state, 'status': status}
    return services, error


def exec_python(container, code, *arguments):
    out, error = run([*DOCKER, 'exec', container, 'python3', '-c', code, *arguments])
    if out is None:
        return None, error
    try:
        return json.loads(out), None
    except ValueError:
        return None, 'unparseable output'


def proxy_usage(services):
    proxy = services.get('egress-proxy', {}).get('name')
    if not proxy:
        return None, 'egress-proxy not found'
    return exec_python(proxy, 'import json,urllib.request;print(urllib.request.urlopen('
                              '"http://127.0.0.1:4180/usage",timeout=10).read().decode())')


def board_counts(services, board_id):
    board = services.get('board-service', {}).get('name')
    if not board:
        return None, 'board-service not found'
    code = ('import json,sys,urllib.request,collections\n'
            'u="http://127.0.0.1:8660/board/%s/read_all?viewer=harness"%sys.argv[1]\n'
            'e=json.load(urllib.request.urlopen(u,timeout=10))["entries"]\n'
            'c=collections.defaultdict(lambda: collections.Counter())\n'
            'last={}\n'
            'for x in e:\n'
            '    c[x["thread_id"]][x["type"]]+=1; last[x["thread_id"]]=max(last.get(x["thread_id"],0),x["ts"])\n'
            'print(json.dumps({k:{"types":dict(v),"last_ts":last[k]} for k,v in c.items()}))')
    return exec_python(board, code, board_id)


def event_counts(services, root_password):
    mysql = services.get('mysql', {}).get('name')
    if not mysql:
        return None, 'mysql not found'
    out, error = run([*DOCKER, 'exec', '-e', f'MYSQL_PWD={root_password}', mysql, 'mysql', '-N', '-B',
                      '-uroot', '-D', 'omcgitea', '-e',
                      'SELECT agent, state, COUNT(*) FROM events GROUP BY agent, state'])
    if out is None:
        return None, error
    counts = {}
    for line in out.splitlines():
        agent, state, count = line.split('\t')
        counts.setdefault(agent, {})[state] = int(count)
    return counts, None


def last_activity(agent_dir, harness):
    # Journals are private to the worker UID, so they are scanned with sudo.
    directory = Path(agent_dir) / SESSION_DIRS.get(harness, SESSION_DIRS['pi'])
    out, _ = run(['sudo', '-n', 'find', str(directory), '-type', 'f', '-name', '*.jsonl', '-printf', '%T@\n'])
    times = [float(value) for value in (out or '').split()]
    return max(times) if times else None


def pull_requests(values):
    url = (f"http://localhost:{values['EDGE_HTTP_PORT']}/api/v1/repos/{values['ORG_NAME']}/"
           f"{values.get('REPOS', 'main').split(',')[0]}/pulls?state=all&limit=50")
    credentials = f"{values['GITEA_ADMIN_USER']}:{values['GITEA_ADMIN_PASSWORD']}".encode()
    request = urllib.request.Request(url, headers={'Authorization': 'Basic ' + base64.b64encode(credentials).decode()})
    try:
        pulls = json.load(urllib.request.urlopen(request, timeout=10))
    except (OSError, ValueError) as error:
        return None, str(error)
    summary = {'open': 0, 'merged': 0, 'closed': 0, 'by_author': {}}
    for pull in pulls:
        state = 'merged' if pull.get('merged') else pull.get('state', 'open')
        summary[state] = summary.get(state, 0) + 1
        author = (pull.get('user') or {}).get('login', '?')
        summary['by_author'].setdefault(author, {}).setdefault(state, 0)
        summary['by_author'][author][state] += 1
    return summary, None


def collect(profile):
    values = read_profile(profile)
    org = values['ORG_NAME']
    workers = int(values.get('AGENSH_WORKERS', '0') or 0)
    harness = values.get('AGENT_HARNESS', 'copilot')
    project = f'omcgitea-{profile}'
    data_root = values.get('DATA_ROOT') or str(ROOT / '.claude-team-data')
    services, container_error = containers(project)
    usage, usage_error = proxy_usage(services)
    # The board belongs to the profile's pack, as in Compose generation.
    try:
        board_id = load_pack(values.get('AGENSH_PACK') or 'programbench').board_id
    except PackError as error:
        board_id, board_error = None, str(error)
    board, board_error = board_counts(services, board_id) if board_id else (None, board_error)
    events, event_error = event_counts(services, values.get('MYSQL_ROOT_PASSWORD', ''))
    pulls, pull_error = pull_requests(values)
    now = time.time()
    rows = []
    for index in range(1, workers + 1):
        agent = f'{org}-worker{index}'
        activity = last_activity(Path(data_root) / profile / 'agents' / agent, harness)
        agent_usage = ((usage or {}).get('agents') or {}).get(agent, {})
        agent_board = (board or {}).get(agent, {})
        rows.append({
            'agent': agent,
            'worker': services.get(f'agent-worker{index}', {}).get('state', 'missing'),
            'router': services.get(f'mini-router-worker{index}', {}).get('state', 'missing'),
            'idle_seconds': round(now - activity) if activity else None,
            'events': {state: (events or {}).get(agent, {}).get(state, 0) for state in EVENT_STATES},
            'usage': {key: agent_usage.get(key, 0) for key in
                      ('requests', 'errors', 'input_tokens', 'cached_input_tokens', 'output_tokens')},
            'board': agent_board.get('types', {}),
            'pulls': ((pulls or {}).get('by_author') or {}).get(agent, {}),
        })
    errors = {name: error for name, error in (('containers', container_error), ('usage', usage_error),
              ('board', board_error), ('events', event_error), ('pulls', pull_error)) if error}
    return {'profile': profile, 'project': project, 'harness': harness, 'checked_at': round(now),
            'services_running': sum(1 for s in services.values() if s['state'] == 'running'),
            'services_total': len(services), 'workers': rows,
            'team_usage': (usage or {}).get('team'),
            'pulls': {k: v for k, v in (pulls or {}).items() if k != 'by_author'},
            'errors': errors}


def human(seconds):
    if seconds is None:
        return '-'
    return f'{seconds}s' if seconds < 120 else f'{seconds // 60}m'


def print_table(status):
    print(f"{status['project']}  harness={status['harness']}  "
          f"services {status['services_running']}/{status['services_total']} running")
    header = ('agent', 'worker', 'router', 'idle', 'pending', 'sent', 'failed', 'requests',
              'in_tokens', 'out_tokens', 'gists', 'merged')
    lines = [header]
    for row in status['workers']:
        events = row['events']
        lines.append((row['agent'], row['worker'], row['router'], human(row['idle_seconds']),
                      str(events['pending'] + events['sending'] + events['retrying']), str(events['sent']),
                      str(events['failed']), str(row['usage']['requests']), str(row['usage']['input_tokens']),
                      str(row['usage']['output_tokens']), str(sum(row['board'].values())),
                      str(row['pulls'].get('merged', 0))))
    widths = [max(len(line[i]) for line in lines) for i in range(len(header))]
    for line in lines:
        print('  '.join(value.ljust(width) for value, width in zip(line, widths)).rstrip())
    team = status['team_usage'] or {}
    pulls = status['pulls'] or {}
    print(f"team: requests={team.get('requests', 0)} errors={team.get('errors', 0)} "
          f"input_tokens={team.get('input_tokens', 0)} output_tokens={team.get('output_tokens', 0)}  "
          f"PRs open={pulls.get('open', 0)} merged={pulls.get('merged', 0)} closed={pulls.get('closed', 0)}")
    for name, error in status['errors'].items():
        print(f'warning: {name}: {error}', file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description='Summarize a running team profile.')
    parser.add_argument('profile', help='profile name, e.g. programbench-pandoc')
    parser.add_argument('--json', action='store_true', help='print machine-readable JSON')
    args = parser.parse_args()
    status = collect(args.profile)
    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print_table(status)


if __name__ == '__main__':
    main()
