#!/usr/bin/env python3
# Run one task for a team: prepare, bring up services, seed Gitea, wake workers,
# enforce the budget, export, shut down and evaluate. Task-specific steps are the
# pack's hooks. Graceful worker shutdown seals archives that must verify before
# profile teardown. Configuration is read from the environment, as the former shell runner
# accepted it; scripts/team_run.sh is the entry point.

import argparse
import base64
import errno
import fcntl
import glob
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

from agensh import schedule
from agensh.pack import PackError, load_pack

ROOT = Path(__file__).resolve().parents[1]
DOCKER = ['sudo', 'docker']
UP_LOCK = '/tmp/agensh-make-up.lock'
SESSION_DIRS = {'copilot': 'home/.copilot/session-state', 'codex': 'home/.codex/sessions',
                'claude': 'home/.claude/projects'}
DEFAULT_SESSION_DIR = 'home/.pi/agent/sessions'


def log(message):
    print(f'[agensh] {message}', file=sys.stderr, flush=True)


class Fatal(Exception):
    pass


def env_int(name, default):
    return int(os.environ.get(name, '') or default)


def read_profile(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        key, sep, value = line.partition('=')
        if sep and not key.startswith('#'):
            values[key] = value
    return values


def run(command, check=False, quiet=False, **kwargs):
    if quiet:
        kwargs.setdefault('stdout', subprocess.DEVNULL)
        kwargs.setdefault('stderr', subprocess.DEVNULL)
    result = subprocess.run(command, **kwargs)
    if check and result.returncode != 0:
        raise Fatal(f'{" ".join(map(str, command[:3]))} failed with exit {result.returncode}')
    return result


def output(command, **kwargs):
    result = subprocess.run(command, capture_output=True, text=True, **kwargs)
    return result.returncode, result.stdout


def render_prompt(path, **variables):
    # Shared render_prompt, captured as the shell runner did with $(...).
    script = 'source "$1"; shift; out="$(render_prompt "$@")"; printf %s "$out"'
    code, text = output(['bash', '-c', script, 'render', str(ROOT / 'scripts/lib_prompts.sh'), str(path),
                         *[f'{key}={value}' for key, value in variables.items()]])
    if code != 0:
        raise Fatal(f'cannot render {path}')
    return text


class Mattermost:
    """Admin-side Mattermost calls; failures are reported and never stop the run."""

    def __init__(self, port, user, password, team_name, channel):
        self.channel = channel
        self.base = f'http://localhost:{port}' if port else None
        self.user, self.password, self.team_name = user, password, team_name
        self.token = None
        self.team_id = self.channel_id = None

    def request(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        request = urllib.request.Request(self.base + '/api/v4' + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                text = response.read().decode()
                return response.status, (json.loads(text) if text else None), response.headers
        except urllib.error.HTTPError as error:
            return error.code, None, error.headers
        except (OSError, ValueError):
            return 0, None, {}

    def login(self):
        if self.token:
            return True
        if not self.base:
            log('WARN: EDGE_MM_PORT unset; MM drive disabled')
            return False
        status, _, headers = self.request('POST', '/users/login',
                                          {'login_id': self.user, 'password': self.password})
        self.token = headers.get('Token') if status == 200 else None
        if not self.token:
            log('WARN: mattermost admin login failed; MM drive disabled')
            return False
        return True

    def user_id(self, username):
        if not self.login():
            return None
        status, reply, _ = self.request('GET', f'/users/username/{username}')
        return reply.get('id') if status == 200 and isinstance(reply, dict) else None

    def post(self, channel_id, message):
        if not channel_id or not self.login():
            return False
        status, _, _ = self.request('POST', '/posts', {'channel_id': channel_id, 'message': message})
        return 200 <= status < 300

    def dm_channel(self, username):
        if not self.login():
            return None
        me, other = self.user_id(self.user), self.user_id(username)
        if not me or not other:
            return None
        status, reply, _ = self.request('POST', '/channels/direct', [me, other])
        return reply.get('id') if 200 <= status < 300 and isinstance(reply, dict) else None

    def ensure_task_channel(self, workers):
        if not self.login():
            return None, None
        status, reply, _ = self.request('GET', f'/teams/name/{self.team_name}')
        team_id = reply.get('id') if status == 200 and isinstance(reply, dict) else None
        if not team_id:
            log(f'MM team {self.team_name} missing; creating it')
            status, reply, _ = self.request('POST', '/teams', {'name': self.team_name,
                                                                'display_name': self.team_name, 'type': 'O'})
            team_id = reply.get('id') if 200 <= status < 300 and isinstance(reply, dict) else None
            if not team_id:
                log('WARN: could not create MM team')
                return None, None
        for member in [self.user_id(self.user), *[self.user_id(w) for w in workers]]:
            if member:
                self.request('POST', f'/teams/{team_id}/members', {'team_id': team_id, 'user_id': member})
        status, reply, _ = self.request('GET', f'/teams/{team_id}/channels/name/{self.channel}')
        channel = reply.get('id') if status == 200 and isinstance(reply, dict) else None
        if not channel:
            status, reply, _ = self.request('POST', '/channels', {'team_id': team_id, 'name': self.channel,
                                                                  'display_name': self.channel.replace('-', ' '), 'type': 'P'})
            channel = reply.get('id') if 200 <= status < 300 and isinstance(reply, dict) else None
            if not channel:
                log('WARN: could not create MM task channel')
                return None, None
        for worker in workers:
            user = self.user_id(worker)
            if not user:
                log(f'WARN: no MM user id for {worker}')
                continue
            status, _, _ = self.request('POST', f'/channels/{channel}/members', {'user_id': user})
            if not 200 <= status < 300:
                log(f'WARN: MM channel join failed for {worker} (http={status:03d})')
        self.team_id, self.channel_id = team_id, channel
        return team_id, channel


class TeamRun:
    def __init__(self, pack):
        self.pack = pack
        self.task = os.environ.get('TASK') or self.fail_usage('TASK=<instance_id> required (e.g. abishekvashok__cmatrix.5c082c6)')
        self.hours = os.environ.get('HOURS', '2')
        self.out_dir = Path(os.environ.get('OUT_DIR') or ROOT / 'out/pbench')
        self.profile = os.environ.get('PROFILE') or self.fail_usage('PROFILE=<profile> required (e.g. programbench-pandoc)')
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', self.profile):
            raise Fatal(f'PROFILE={self.profile!r} must be lowercase letters, digits and hyphens')
        self.env_file = ROOT / f'.env.{self.profile}'
        self.task_out = self.out_dir / self.task
        self.stop = threading.Event()
        self.threads = []
        self.run_t0 = None

    @staticmethod
    def fail_usage(message):
        raise Fatal(message)

    # Environment shared by make, Compose and hooks.
    def setup_environment(self):
        os.environ.setdefault('AGENSH_RUN_START_MS', str(int(time.time() * 1000)))
        os.environ.setdefault('PBENCH_DOCKER', 'sudo docker')
        if shutil.which('envsubst') is None:
            raise Fatal('envsubst not found (apt install gettext-base); it renders the prompts under prompts/ and the task pack')
        orchestrator = os.environ.get('AGENSH_ORCHESTRATOR')
        if not self.env_file.is_file():
            raise Fatal(f'{self.env_file} missing (task #1 should have created it)')
        self.values = read_profile(self.env_file)
        orchestrator = orchestrator or self.values.get('AGENSH_ORCHESTRATOR', '').strip() or 'compose'
        if orchestrator != 'compose':
            raise Fatal(f"AGENSH_ORCHESTRATOR='{orchestrator}'; this release supports single-node Compose only")
        if self.task_out.exists():
            raise Fatal(f'{self.task_out} already exists — leftover output from a prior run would be mixed in. '
                        f'Remove it (`rm -rf {self.task_out}`) before re-running.')
        self.task_out.mkdir(parents=True)
        data_root = self.values.get('DATA_ROOT') or '../.claude-team-data'
        self.profile_data = Path(data_root) / self.profile
        if self.profile_data.exists():
            raise Fatal(f'{self.profile_data} already exists — leftover state from a prior run would leak into this '
                        f'one (acp_session_id, gitea repo, mattermost history). Run `make clean PROFILE={self.profile}` first.')
        v = self.values
        self.org = v.get('ORG_NAME', '')
        self.repo = os.environ.get('AGENSH_REPO', 'main')
        self.edge_port = v.get('EDGE_HTTP_PORT', '')
        self.gitea_user, self.gitea_password = v.get('GITEA_ADMIN_USER', ''), v.get('GITEA_ADMIN_PASSWORD', '')
        self.workers = int(v.get('AGENSH_WORKERS', '') or 4)
        self.mm = Mattermost(v.get('EDGE_MM_PORT', ''), v.get('MATTERMOST_ADMIN_USER', ''),
                             v.get('MATTERMOST_ADMIN_PASSWORD', ''),
                             v.get('MATTERMOST_TEAM_NAME', '') or self.org, self.pack.channel)

    def gitea_url(self, with_credentials=True):
        credentials = f'{self.gitea_user}:{self.gitea_password}@' if with_credentials else ''
        return f'http://{credentials}localhost:{self.edge_port}/{self.org}/{self.repo}.git'

    def hook_env(self):
        return dict(os.environ, AGENSH_ROOT=str(ROOT), AGENSH_PACK_DIR=str(self.pack.root),
                    AGENSH_TASK=self.task, AGENSH_PROFILE=self.profile, AGENSH_ENV_FILE=str(self.env_file),
                    AGENSH_OUT_DIR=str(self.out_dir), AGENSH_TASK_OUT=str(self.task_out),
                    AGENSH_GITEA_URL=self.gitea_url(), AGENSH_GITEA_REPO=f'{self.org}/{self.repo}',
                    AGENSH_GITEA_PUBLIC_URL=f'localhost:{self.edge_port}/{self.org}/{self.repo}.git')

    def run_hook(self, name):
        hook = self.pack.hook(name)
        if hook is None:
            return True
        interpreter = [sys.executable] if hook.suffix == '.py' else ['bash']
        return run([*interpreter, str(hook)], cwd=ROOT, env=self.hook_env()).returncode == 0

    def make(self, *arguments, quiet=False, check=False):
        return run(['make', *arguments, f'PROFILE={self.profile}'], cwd=ROOT, quiet=quiet, check=check)

    def docker_ps(self, *filters, all_containers=False, fmt=None):
        command = [*DOCKER, 'ps', *(['-a'] if all_containers else []), *(['--format', fmt] if fmt else ['-q'])]
        for item in filters:
            command += ['--filter', item]
        code, text = output(command)
        return text.split('\n') if code == 0 else []

    def project(self):
        return f'label=com.docker.compose.project=omcgitea-{self.profile}'

    # Preparation and bring-up.
    def prepare(self):
        if not self.run_hook('prepare'):
            raise Fatal('prepare hook failed')
        compose_env = self.task_out / 'compose.env'
        if compose_env.is_file():
            os.environ.update(read_profile(compose_env))

    def bring_up(self):
        image = os.environ.get('AGENT_IMAGE') or self.values.get('AGENT_IMAGE', '').strip()
        if not image:
            raise Fatal(f'AGENT_IMAGE is not set in .env.{self.profile}')
        log(f'agent image: {image}')
        if run([*DOCKER, 'image', 'inspect', image], quiet=True).returncode != 0:
            raise Fatal(f"agent image missing: {image} (build it with the pack's image builder, "
                        "e.g. tasks/programbench/scripts/build_images.sh)")
        log(f'bringing up {self.profile} stack')
        if self.make('-s', 'render-base', quiet=True).returncode != 0:
            raise Fatal(f'render-base failed for {self.profile}')
        wanted = self.values.get('AGENSH_WORKERS', '').strip()
        if wanted:
            base = ROOT / f'docker/_gen_prod.{self.profile}.yml'
            if not base.is_file():
                raise Fatal(f'compose base not rendered: {base}')
            got = len(re.findall(r'^  agent-worker[0-9]+:', base.read_text(), flags=re.M))
            if str(got) != wanted:
                raise Fatal(f'compose base {base} has {got} workers, .env asks for {wanted}')
            log(f'compose base rendered: {wanted} workers/team')
        # Serialize infrastructure bring-up across experiments sharing this host.
        with open(UP_LOCK, 'w') as lock:
            deadline = time.monotonic() + 900
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError as error:
                    if error.errno not in (errno.EAGAIN, errno.EACCES) or time.monotonic() > deadline:
                        raise Fatal(f'could not acquire {UP_LOCK} in 15min')
                    time.sleep(1)
            log(f'acquired make-up lock (pid {os.getpid()})')
            if os.environ.get('AGENSH_STAGGERED_BRINGUP', '1') == '1':
                code, text = output(['make', '-s', 'compose-services', f'PROFILE={self.profile}'], cwd=ROOT)
                infra = [s for s in text.split() if not re.fullmatch(r'(agent|mini-router)-worker[0-9]+', s)]
                if code != 0 or not infra:
                    raise Fatal(f'could not enumerate infra services for {self.profile}')
                self.clear_stale_containers()
                log(f'bringing up INFRA only ({len(infra)} services); agents start on the stagger')
                if self.make('up', f'SERVICES={" ".join(infra)}').returncode != 0:
                    raise Fatal('make up (infra) failed')
            elif self.make('up').returncode != 0:
                raise Fatal('make up failed')

    def clear_stale_containers(self):
        stale = [c for c in self.docker_ps(self.project(), all_containers=True) if c]
        if stale:
            log(f'clearing {len(stale)} stale container record(s) for {self.profile}')
            run([*DOCKER, 'rm', '-f', *stale], quiet=True)

    def push_history(self, clone):
        # main does not exist yet (no initial commit), so this is an ordinary push.
        log(f'pushing the imported history from {clone} as main')
        for attempt in range(1, 6):
            if run(['git', '-C', str(clone), 'push', '-q', self.gitea_url(), 'HEAD:refs/heads/main']).returncode == 0:
                log('imported history is main')
                return
            log(f'WARN: history push attempt {attempt}/5 failed; retrying in {attempt * 5}s')
            time.sleep(attempt * 5)
        raise Fatal('could not push the imported history to the team repository')

    def push_seed(self):
        history = self.task_out / '.seed_git'
        if history.is_file():
            self.push_history(Path(history.read_text().strip()))
            return
        seed_path = self.task_out / '.seed_path'
        seed_dir = Path(seed_path.read_text().strip()) if seed_path.is_file() else None
        push_tmp = self.task_out / '_push'
        log('cloning team repo to seed initial commit')
        seeded = False
        for attempt in range(1, 6):
            shutil.rmtree(push_tmp, ignore_errors=True)
            if run(['git', 'clone', '--quiet', self.gitea_url(), str(push_tmp)], quiet=True).returncode == 0:
                seeded = True
                break
            log(f'WARN: clone attempt {attempt}/5 failed; retrying in {attempt * 5}s')
            time.sleep(attempt * 5)
        if not seeded:
            log('WARN: clone failed after 5 attempts; skipping seed push (agents are still woken below)')
            return
        if seed_dir and seed_dir.is_dir():
            run(['cp', '-a', f'{seed_dir}/.', f'{push_tmp}/'], quiet=True)
        message = self.pack.seed_message.format(task=self.task)
        steps = [['git', 'config', 'user.email', f'chairman@{self.org}.local'],
                 ['git', 'config', 'user.name', self.gitea_user],
                 ['git', 'add', '-A'], ['git', 'commit', '-qm', message], ['git', 'push', '-q', 'origin', 'HEAD']]
        for step in steps:
            if run(step, cwd=push_tmp).returncode != 0:
                log('WARN: seed push failed (repo may already be seeded)')
                return

    def open_issue(self, brief):
        log('opening task issue (no assignee; peers self-select)')
        credentials = base64.b64encode(f'{self.gitea_user}:{self.gitea_password}'.encode()).decode()
        request = urllib.request.Request(
            f'http://localhost:{self.edge_port}/api/v1/repos/{self.org}/{self.repo}/issues', method='POST',
            data=json.dumps({'title': self.pack.issue_title.format(task=self.task), 'body': brief}).encode(),
            headers={'Content-Type': 'application/json', 'Authorization': f'Basic {credentials}'})
        try:
            with urllib.request.urlopen(request, timeout=30):
                log('task issue opened')
        except (OSError, ValueError):
            log('WARN: could not open task issue')

    def start_agent_containers(self, index, name):
        attempt = 1
        while True:
            result = subprocess.run(['make', 'up', f'PROFILE={self.profile}', 'UP_FLAGS=--no-deps',
                                     f'SERVICES=agent-worker{index} mini-router-worker{index}'],
                                    cwd=ROOT, capture_output=True, text=True)
            if result.returncode == 0:
                break
            retry = env_int('AGENSH_START_RETRY_S', 30)
            log(f'WARN: container start failed for {name} (try {attempt}); retrying in {retry}s')
            for line in (result.stdout + result.stderr).splitlines()[-5:]:
                log(f'    {line}')
            attempt += 1
            time.sleep(retry)
        log(f'started containers for {name}')

    def drive(self):
        self.push_seed()
        team_id, channel = self.mm.ensure_task_channel([f'{self.org}-worker{i}' for i in range(1, self.workers + 1)])
        # The prepare hook may add project variables (goal, checks) for the brief.
        extra = {}
        brief_vars = self.task_out / 'brief_vars.json'
        if brief_vars.is_file():
            extra = {k: str(v) for k, v in json.loads(brief_vars.read_text()).items()
                     if re.fullmatch(r'[A-Z][A-Z0-9_]*', k)}
        brief = render_prompt(self.pack.task_brief, **extra, TASK=self.task, REPO=self.repo,
                              MM_TEAM_ID=team_id or '', TASK_CHANNEL_ID=channel or '')
        kickoff = render_prompt(ROOT / 'prompts/kickoff.txt', TASK_BRIEF=brief)
        self.open_issue(brief)

        base = env_int('AGENSH_WAKE_STAGGER_S', 30)
        fast = env_int('AGENSH_WAKE_FAST_STAGGER_S', 3)
        ramp = env_int('AGENSH_WAKE_RAMP_SUBJ_S', 3600)
        switch_at = ramp // base
        if self.workers > switch_at:
            log(f'waking {self.workers} agents by DM: {base}s apart for the first {switch_at} (one hour), then {fast}s')
        else:
            log(f'waking {self.workers} agents by DM, {base}s apart')
        # Charge activation time to the shared wall-clock budget, starting before ramp-up.
        self.run_t0 = time.time()
        if os.environ.get('AGENSH_WATCHDOG_EARLY', '1') == '1':
            total = schedule.budget_seconds(self.hours or 6)
            self.start_thread(self.watchdog, total)
            log(f'idle watchdog started BEFORE the ramp ({total}s)')
        woke = 0
        for index in range(1, self.workers + 1):
            name = f'{self.org}-worker{index}'
            started = time.time()
            if os.environ.get('AGENSH_STAGGERED_BRINGUP', '1') == '1':
                self.start_agent_containers(index, name)
                time.sleep(env_int('AGENSH_BRINGUP_SETTLE_S', 20))
            dm = self.mm.dm_channel(name) or self.mm.dm_channel(name)
            if dm:
                if self.mm.post(dm, kickoff):
                    woke += 1
                    log(f'woke {name} ({woke}/{self.workers})')
                else:
                    log(f'WARN: DM wake failed for {name}')
            else:
                log(f'WARN: no DM channel for {name}')
            if index < self.workers:
                remain = schedule.wake_stagger(index, base, fast, ramp) - int(time.time() - started)
                if remain > 0:
                    time.sleep(remain)
        log(f'wake complete: {woke}/{self.workers} agents')
        if channel:
            if self.mm.post(channel, kickoff):
                log(f'task posted to MM channel {self.pack.channel} (record; agents already woken)')
            else:
                log('WARN: MM channel post failed')
        else:
            log('WARN: no MM channel for the task record (agents were woken by DM)')

    # Background loops.
    def start_thread(self, target, *arguments):
        thread = threading.Thread(target=target, args=arguments, daemon=True)
        thread.start()
        self.threads.append(thread)

    def stop_background_loops(self):
        self.stop.set()

    def mysql_pending(self, container, password, agent):
        if not container or not password:
            return None
        sql = (f"SELECT COUNT(*) FROM events WHERE agent='{agent}' "
               "AND state IN ('pending','sending','retrying','failed');")
        code, text = output([*DOCKER, 'exec', container, 'mysql', '-N', '-B', '-uroot', f'-p{password}',
                             '-D', 'omcgitea', '-e', sql])
        return text.strip() if code == 0 else None

    def watchdog(self, total_seconds):
        agents_root = Path(self.values.get('DATA_ROOT') or '../.claude-team-data') / self.profile / 'agents'
        dedup = self.task_out / '_watchdog'
        dedup.mkdir(parents=True, exist_ok=True)
        session_subdir = SESSION_DIRS.get(self.values.get('AGENT_HARNESS', ''), DEFAULT_SESSION_DIR)
        threshold = env_int('WORKER_IDLE_THRESHOLD', 600)
        repeat = env_int('WORKER_IDLE_REPEAT', 600)
        interval = env_int('WORKER_CHECK_INTERVAL', 60)
        start = time.time()
        if run(['sudo', '-n', 'true'], quiet=True).returncode != 0:
            log('WARN: watchdog cannot sudo -n; private native journals cannot be scanned, so idle nudges will be skipped')
        mysql = next((n for n in self.docker_ps(f'name=omcgitea-{self.profile}-mysql', fmt='{{.Names}}') if n), '')
        password = self.values.get('MYSQL_ROOT_PASSWORD', '')
        if not mysql or not password:
            log(f"WARN: watchdog cannot read the UEM queue (container='{mysql or 'none'}'); it will nudge on idle alone")
        while not self.stop.is_set():
            now = time.time()
            elapsed = now - start
            if elapsed >= total_seconds:
                break
            phase = schedule.idle_phase(total_seconds, total_seconds - int(elapsed))
            for agent_dir in sorted(glob.glob(str(agents_root / f'{self.org}-*worker*'))):
                if not os.path.isdir(agent_dir):
                    continue
                # Native session-log modification times are the liveness signal.
                code, text = output(['sudo', '-n', 'find', os.path.join(agent_dir, session_subdir),
                                     '-type', 'f', '-name', '*.jsonl', '-printf', '%T@\n'])
                times = [float(t) for t in text.split()] if text else []
                if not times:
                    continue
                worker = os.path.basename(agent_dir)
                self.consider_nudge(worker, int(now) - int(max(times)), int(now), dedup, phase,
                                    threshold, repeat, mysql, password)
            self.stop.wait(interval)

    def consider_nudge(self, worker, idle, now, dedup, phase, threshold, repeat, mysql, password):
        marker = dedup / worker
        try:
            last = int(marker.read_text().strip())
        except (OSError, ValueError):
            last = 0
        if idle < 0 or not schedule.should_nudge(idle, now, last, threshold, repeat):
            return
        pending = self.mysql_pending(mysql, password, worker)
        if pending and pending != '0':
            log(f'watchdog: {worker} idle={idle}s but {pending} UEM row(s) pending; letting the queue wake it')
            marker.write_text(f'{now}\n')
            return
        message = render_prompt(self.pack.idle_delivery if phase == 'delivery' else self.pack.idle)
        pinged = False
        dm = self.mm.dm_channel(worker)
        if dm:
            if self.mm.post(dm, message):
                log(f'watchdog: DM {worker} (idle={idle}s, UEM queue empty)')
                pinged = True
            else:
                log(f'WARN: watchdog DM to {worker} failed')
        if not pinged and self.mm.channel_id:
            if self.mm.post(self.mm.channel_id, f'@{worker} {message}'):
                log(f'watchdog: channel-fallback ping for {worker} (idle {idle}s)')
            else:
                log(f'WARN: watchdog channel fallback failed for {worker}')
        marker.write_text(f'{now}\n')

    def reminders(self, total_seconds):
        # Reminders are channel messages timed against the remaining run budget.
        start = time.time()
        for offset, reminder in schedule.reminder_times(total_seconds, self.pack.reminders):
            if self.stop.wait(max(0, start + offset - time.time())):
                return
            label = f"T-{reminder['before_end_seconds'] // 60}m"
            if not self.mm.post(self.mm.channel_id, render_prompt(reminder['message'])):
                log(f'WARN: {label} reminder failed')
            log(f'posted {label} reminder')

    # Shutdown.
    def dump_board_lifecycle(self):
        board = next((n for n in self.docker_ps(f'name=omcgitea-{self.profile}-board-service',
                                                fmt='{{.Names}}') if n), '')
        if not board:
            return
        log(f'dumping board lifecycle from {board}')
        script = '''import json, urllib.request
try:
    boards = json.load(urllib.request.urlopen('http://127.0.0.1:8660/healthz', timeout=5))['boards']
except Exception as e:
    print('healthz failed:', e); raise SystemExit(0)
for b in boards:
    try:
        req = urllib.request.Request(
            f'http://127.0.0.1:8660/board/{b}/lifecycle?viewer=harness', method='POST')
        print(b, json.load(urllib.request.urlopen(req, timeout=15)).get('path'))
    except Exception as e:
        print(b, 'FAILED', e)
'''
        with open(self.task_out / 'board-lifecycle.log', 'a') as stream:
            run([*DOCKER, 'exec', board, 'python3', '-c', script], stdout=stream, stderr=stream)

    def quiesce(self):
        # Stop routers/CI first, then let workers archive while Gitea/MySQL stay up.
        project = f'omcgitea-{self.profile}'
        routers = sorted({c for c in self.docker_ps(self.project(), 'name=mini-router', 'name=act-runner') if c})
        if routers:
            log(f'quiesce: stopping routers/runners for {project} before worker snapshots')
            if run([*DOCKER, 'stop', '-t', '10', *routers], quiet=True).returncode != 0:
                log(f'WARN: some routers/runners did not stop cleanly for {project}')
        agents = sorted({c for c in self.docker_ps(self.project(), 'name=agent-worker') if c})
        if agents:
            log(f'quiesce: saving worker sessions for {project} (up to 600s; gitea/mysql stay up)')
            if run([*DOCKER, 'stop', '-t', '600', *agents], quiet=True).returncode != 0:
                log(f'WARN: some workers did not stop cleanly for {project}')
        return run(['sudo', '-n', 'python3', str(ROOT / 'agent/archive.py'), 'check',
                    str(self.profile_data)]).returncode == 0

    def save_service_logs(self):
        # Preserve router/proxy stdout before Compose removes the container records.
        directory = self.task_out / 'service-logs'
        directory.mkdir(parents=True, exist_ok=True)
        for line in self.docker_ps(self.project(), all_containers=True,
                                   fmt='{{.ID}} {{.Label "com.docker.compose.service"}}'):
            container, _, service = line.partition(' ')
            if not container or not service:
                continue
            with open(directory / f'{service}.log', 'w') as stream:
                if run([*DOCKER, 'logs', '--timestamps', container], stdout=stream, stderr=stream).returncode != 0:
                    log(f'WARN: could not save {service} logs for {self.profile}')
        (directory / 'captured-at.txt').write_text(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) + '\n')
        log(f'saved service stdout/stderr to {directory}')

    def export(self):
        return self.run_hook('export')

    def teardown(self, code):
        # The failure path also preserves recoverable state when the run fails early.
        log(f'teardown (rc={code}): quiescing agents, exporting submission, stopping profile')
        self.stop_background_loops()
        try:
            self.dump_board_lifecycle()
        except Exception:
            pass
        archives_ok = self.quiesce()
        self.export()
        try:
            self.save_service_logs()
        except Exception:
            pass
        if archives_ok:
            self.make('down', quiet=True)
        else:
            log('ERROR: incomplete shutdown archives; preserving containers and DATA_ROOT for recovery')

    def main(self):
        log(f'TASK={self.task} HOURS={self.hours} OUT_DIR={self.out_dir} PROFILE={self.profile}')
        self.setup_environment()
        try:
            self.prepare()
            self.bring_up()
            self.drive()
            total = schedule.budget_seconds(self.hours)
            elapsed = max(0, int(time.time() - self.run_t0))
            remaining = schedule.remaining_after(total, elapsed)
            log(f'agents working for {self.hours}h ({total}s); {elapsed}s spent waking, sleeping {remaining}s')
            if self.threads:
                log('reusing pre-ramp idle watchdog')
            else:
                self.start_thread(self.watchdog, remaining)
            self.start_thread(self.reminders, remaining)
            self.stop.wait(remaining)
            self.stop_background_loops()
            log('wall-clock budget elapsed; exporting + evaluating')
        except BaseException as error:
            if isinstance(error, Fatal):
                log(f'FATAL: {error}')
            self.teardown(1)
            raise SystemExit(1)

        self.export()
        if not self.quiesce():
            self.save_service_logs()
            raise Fatal('incomplete shutdown archives; preserving containers and DATA_ROOT for recovery')
        self.save_service_logs()
        self.make('down', quiet=True)
        if os.environ.get('SKIP_EVAL', '0') == '1':
            log(f'SKIP_EVAL=1 → deferring programbench eval (submission left at {self.task_out}/submission.tar.gz)')
            return
        if not self.run_hook('evaluate'):
            raise Fatal('evaluate hook failed')


def terminate(signum, _frame):
    raise KeyboardInterrupt(f'signal {signum}')


def main():
    parser = argparse.ArgumentParser(description='Run one task for a team; settings come from the environment.')
    parser.add_argument('--pack', default=os.environ.get('AGENSH_PACK') or None,
                        help="task pack under tasks/ (default: the profile's AGENSH_PACK, else programbench)")
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, terminate)
    try:
        pack = args.pack
        profile_file = ROOT / f".env.{os.environ.get('PROFILE', '')}"
        if not pack and profile_file.is_file():
            # Match the Makefile, which renders Compose for the profile's pack.
            pack = read_profile(profile_file).get('AGENSH_PACK', '').strip()
        TeamRun(load_pack(pack or 'programbench')).main()
    except (Fatal, PackError) as error:
        log(f'FATAL: {error}')
        sys.exit(1)


if __name__ == '__main__':
    main()
