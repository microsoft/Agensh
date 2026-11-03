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

from agensh import backlog, quality, schedule
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
        # run: a new run; resume: continue a paused run; finalize: deliver a paused run.
        self.mode = os.environ.get('AGENSH_MODE', 'run')
        if self.mode not in ('run', 'resume', 'finalize'):
            raise Fatal(f'AGENSH_MODE={self.mode!r} must be run, resume or finalize')
        if self.mode != 'run' and not pack.resumable:
            raise Fatal(f'the {pack.name} pack is not resumable; only AGENSH_MODE=run applies')
        self.stop_reason = None
        self.watchdog_started = False

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
        data_root = self.values.get('DATA_ROOT') or '../.claude-team-data'
        self.profile_data = Path(data_root) / self.profile
        if self.mode == 'run':
            if self.task_out.exists():
                raise Fatal(f'{self.task_out} already exists — leftover output from a prior run would be mixed in. '
                            f'Remove it (`rm -rf {self.task_out}`) before re-running.')
            self.task_out.mkdir(parents=True)
            if self.profile_data.exists():
                raise Fatal(f'{self.profile_data} already exists — leftover state from a prior run would leak into '
                            f'this one (acp_session_id, gitea repo, mattermost history). '
                            f'Run `make clean PROFILE={self.profile}` first.')
        else:
            state = self.read_state().get('state')
            if state != 'paused' or not self.profile_data.is_dir():
                raise Fatal(f'{self.mode} needs a paused run in {self.task_out} with its state in '
                            f'{self.profile_data}; the run is {state or "missing"}')
            compose_env = self.task_out / 'compose.env'
            if compose_env.is_file():
                os.environ.update(read_profile(compose_env))
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

    def run_hook(self, name, **extra):
        hook = self.pack.hook(name)
        if hook is None:
            return True
        interpreter = [sys.executable] if hook.suffix == '.py' else ['bash']
        return run([*interpreter, str(hook)], cwd=ROOT, env=dict(self.hook_env(), **extra)).returncode == 0

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

    def gitea_api(self, method, path, body=None):
        # Admin calls on the team repository; returns (HTTP status, decoded reply or None).
        credentials = base64.b64encode(f'{self.gitea_user}:{self.gitea_password}'.encode()).decode()
        request = urllib.request.Request(
            f'http://localhost:{self.edge_port}/api/v1/repos/{self.org}/{self.repo}{path}', method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type': 'application/json', 'Authorization': f'Basic {credentials}'})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                text = response.read().decode()
                return response.status, (json.loads(text) if text else None)
        except urllib.error.HTTPError as error:
            return error.code, None
        except (OSError, ValueError):
            return 0, None

    def open_issue(self, brief):
        log('opening task issue (no assignee; peers self-select)')
        status, _ = self.gitea_api('POST', '/issues', {'title': self.pack.issue_title.format(task=self.task),
                                                       'body': brief})
        log('task issue opened' if 200 <= status < 300 else 'WARN: could not open task issue')

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

    def render_brief(self, team_id, channel):
        # The prepare hook may add project variables (goal, checks) for the brief.
        extra = {}
        brief_vars = self.task_out / 'brief_vars.json'
        if brief_vars.is_file():
            extra = {k: str(v) for k, v in json.loads(brief_vars.read_text()).items()
                     if re.fullmatch(r'[A-Z][A-Z0-9_]*', k)}
        return render_prompt(self.pack.task_brief, **extra, TASK=self.task, REPO=self.repo,
                             MM_TEAM_ID=team_id or '', TASK_CHANNEL_ID=channel or '')

    def start_quality_loops(self):
        if self.pack.ci_gate:
            self.start_thread(self.main_health)
        if self.pack.backlog == 'issues':
            self.start_thread(self.backlog_sync)

    def drive(self):
        self.push_seed()
        if self.pack.ci_gate:
            self.protect_files()
            self.require_review()
        self.start_quality_loops()
        team_id, channel = self.mm.ensure_task_channel(self.channel_members())
        brief = self.render_brief(team_id, channel)
        kickoff = render_prompt(ROOT / 'prompts/kickoff.txt', TASK_BRIEF=brief)
        self.open_issue(brief)
        if self.values.get('AGENSH_PLANNING') == '1' and self.workers > 1:
            self.planning_phase(kickoff)
        else:
            self.wake(kickoff)
        if channel:
            if self.mm.post(channel, kickoff):
                log(f'task posted to MM channel {self.pack.channel} (record; agents already woken)')
            else:
                log('WARN: MM channel post failed')
        else:
            log('WARN: no MM channel for the task record (agents were woken by DM)')

    def resume_drive(self):
        # Fresh native sessions; workers continue from the repository, issues and board.
        self.sync('resume')
        self.fresh_sessions()
        self.start_quality_loops()
        team_id, channel = self.mm.ensure_task_channel(self.channel_members())
        message = render_prompt(ROOT / 'prompts/lifecycle/resume.txt',
                                TASK_BRIEF=self.render_brief(team_id, channel), STATE_SUMMARY=self.state_summary())
        self.wake(message)

    def human(self):
        return self.values.get('AGENSH_HUMAN', '').strip() if self.pack.product_owner else ''

    def channel_members(self):
        return self.worker_names() + ([self.human()] if self.human() else [])

    def planning_phase(self, kickoff):
        # Worker 1 writes the architecture and the issue breakdown; the others wake
        # when its `[plan]` PR is merged, or after the planning timeout.
        timeout = env_int('AGENSH_PLANNING_TIMEOUT_S', 2700)
        plan = render_prompt(ROOT / 'prompts/planning.txt', KICKOFF=kickoff, MINUTES=str(timeout // 60),
                             PEERS=str(self.workers - 1))
        log(f'planning phase: {self.org}-worker1 plans; the others wake when a [plan] PR merges (at most {timeout}s)')
        self.wake(plan, indices=[1])
        deadline = time.time() + timeout
        while time.time() < deadline and not self.stop.is_set():
            status, pulls = self.gitea_api('GET', '/pulls?state=closed&sort=recentupdate&limit=50')
            merged = [p for p in pulls or [] if status == 200 and p.get('merged')
                      and str(p.get('title', '')).lower().startswith('[plan]')]
            if merged:
                log(f'plan merged (PR #{merged[0]["number"]}); waking the rest of the team')
                break
            self.stop.wait(15)
        else:
            log('planning timed out; waking the rest of the team')
        self.wake(kickoff, indices=range(2, self.workers + 1))

    def digest_text(self, since):
        # Progress since the last digest, from Gitea, CI, the board and usage metering.
        import datetime
        def after(stamp):
            try:
                return datetime.datetime.fromisoformat(str(stamp).replace('Z', '+00:00')).timestamp() > since
            except ValueError:
                return False
        lines = [f'**Progress digest** ({time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())})']
        status, closed = self.gitea_api('GET', '/pulls?state=closed&sort=recentupdate&limit=50')
        merged = [p for p in closed or [] if status == 200 and p.get('merged') and after(p.get('merged_at'))]
        lines.append(f'- Merged since the last digest: {len(merged)} PR(s)'
                     + ''.join(f'\n  - #{p["number"]} {p["title"]} ({p["user"]["login"]})' for p in merged[:15]))
        _, issues = self.gitea_api('GET', '/issues?state=open&type=issues&limit=50')
        _, pulls = self.gitea_api('GET', '/pulls?state=open&limit=50')
        lines.append(f'- Open: {len(issues or [])} issue(s), {len(pulls or [])} PR(s)')
        if self.pack.ci_gate:
            code, branch = self.gitea_api('GET', '/branches/main')
            if code == 200:
                sha = branch['commit']['id']
                code, combined = self.gitea_api('GET', f'/commits/{sha}/status')
                state = quality.check_state((combined or {}).get('statuses'), quality.MAIN_CHECK) if code == 200 else None
                lines.append(f'- `main` {sha[:12]}: full suite {state or "not run yet"}')
        entries = self.board_entries() or []
        recent = [e for e in entries if float(e.get('ts') or 0) > since]
        counts = {kind: sum(1 for e in recent if e.get('type') == kind) for kind in ('PATCH_SUMMARY', 'FAIL', 'FACT')}
        lines.append('- Board: ' + ', '.join(f'{n} {kind}' for kind, n in counts.items()))
        used, limit = self.team_tokens(), int(self.values.get('AGENSH_MAX_MODEL_TOKENS', '') or 0)
        if used is not None:
            lines.append(f'- Model tokens used: {used}' + (f' of {limit} ({100 * used // limit}%)' if limit else ''))
        return '\n'.join(lines)

    def digest_loop(self, interval):
        directory = self.task_out / 'digests'
        directory.mkdir(exist_ok=True)
        since = time.time()
        while not self.stop.wait(interval):
            try:
                text = self.digest_text(since)
            except Exception as error:  # A failed digest never stops the run.
                log(f'WARN: progress digest failed: {error}')
                continue
            since = time.time()
            (directory / f'digest-{time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())}.md').write_text(text + '\n')
            if not self.mm.post(self.mm.channel_id, f'@{self.human()} {text}'):
                log('WARN: could not post the progress digest')
            log('posted a progress digest')

    def latest_digest(self):
        digests = sorted((self.task_out / 'digests').glob('digest-*.md')) if (self.task_out / 'digests').is_dir() else []
        return digests[-1].read_text().strip() if digests else ''

    def fresh_sessions(self):
        mysql = next((n for n in self.docker_ps(f'name=omcgitea-{self.profile}-mysql', fmt='{{.Names}}') if n), '')
        sql = "DELETE FROM agent_kv WHERE k LIKE 'acp_session_id:%';"
        if not mysql or run([*DOCKER, 'exec', mysql, 'mysql', '-N', '-B', '-uroot',
                             f'-p{self.values.get("MYSQL_ROOT_PASSWORD", "")}', '-D', 'omcgitea', '-e', sql],
                            quiet=True).returncode != 0:
            raise Fatal('could not clear the stored ACP sessions for a fresh resume')
        log('cleared stored ACP sessions: workers resume with fresh native sessions')

    def state_summary(self):
        # What a fresh session needs: open work, recent merges, CI and upstream state.
        lines = []
        status, issues = self.gitea_api('GET', '/issues?state=open&type=issues&limit=30')
        if status == 200 and issues:
            lines.append('Open issues:')
            for issue in issues:
                who = ', '.join(a['login'] for a in issue.get('assignees') or []) or 'unassigned'
                lines.append(f'- #{issue["number"]} {issue["title"]} ({who})')
        status, pulls = self.gitea_api('GET', '/pulls?state=open&limit=30')
        if status == 200 and pulls:
            lines.append('Open PRs:')
            lines += [f'- #{p["number"]} {p["title"]} by {p["user"]["login"]}' for p in pulls]
        status, closed = self.gitea_api('GET', '/pulls?state=closed&sort=recentupdate&limit=15')
        merged = [p for p in closed or [] if p.get('merged')] if status == 200 else []
        if merged:
            lines.append('Recently merged:')
            lines += [f'- #{p["number"]} {p["title"]} by {p["user"]["login"]}' for p in merged[:10]]
        if self.pack.ci_gate:
            status, branch = self.gitea_api('GET', '/branches/main')
            if status == 200:
                sha = branch['commit']['id']
                code, combined = self.gitea_api('GET', f'/commits/{sha}/status')
                state = quality.check_state((combined or {}).get('statuses'), quality.MAIN_CHECK) if code == 200 else None
                lines.append(f'`main` is at {sha[:12]}; full suite: {state or "not run yet"}.')
        sync = (json.loads((self.task_out / 'sync.json').read_text()).get('last')
                if (self.task_out / 'sync.json').is_file() else None)
        if sync:
            lines.append(f'Upstream sync on resume: {sync["result"]} at {sync["upstream_sha"][:12]}'
                         + (f' (issue #{sync["issue"]})' if sync.get('issue') else '') + '.')
        digest = self.latest_digest()
        if digest:
            lines += ['', 'Latest progress digest:', digest]
        return '\n'.join(lines) or 'No open issues or PRs.'

    def wake(self, message, indices=None):
        # The planning phase wakes worker 1 first and the rest later.
        indices = list(indices or range(1, self.workers + 1))
        base = env_int('AGENSH_WAKE_STAGGER_S', self.pack.wake_stagger)
        fast = env_int('AGENSH_WAKE_FAST_STAGGER_S', 3)
        ramp = env_int('AGENSH_WAKE_RAMP_SUBJ_S', 3600)
        switch_at = ramp // base
        if self.workers > switch_at:
            log(f'waking {self.workers} agents by DM: {base}s apart for the first {switch_at} (one hour), then {fast}s')
        else:
            log(f'waking {self.workers} agents by DM, {base}s apart')
        # Charge activation time to the shared wall-clock budget, starting before ramp-up.
        if self.run_t0 is None:
            self.run_t0 = time.time()
        if os.environ.get('AGENSH_WATCHDOG_EARLY', '1') == '1' and not self.watchdog_started:
            total = schedule.budget_seconds(self.hours or 6)
            self.start_thread(self.watchdog, total)
            self.watchdog_started = True
            log(f'idle watchdog started BEFORE the ramp ({total}s)')
        woke = 0
        for position, index in enumerate(indices, 1):
            name = f'{self.org}-worker{index}'
            started = time.time()
            if os.environ.get('AGENSH_STAGGERED_BRINGUP', '1') == '1':
                self.start_agent_containers(index, name)
                time.sleep(env_int('AGENSH_BRINGUP_SETTLE_S', 20))
            dm = self.mm.dm_channel(name) or self.mm.dm_channel(name)
            if dm:
                if self.mm.post(dm, message):
                    woke += 1
                    log(f'woke {name} ({woke}/{len(indices)})')
                else:
                    log(f'WARN: DM wake failed for {name}')
            else:
                log(f'WARN: no DM channel for {name}')
            if position < len(indices):
                remain = schedule.wake_stagger(index, base, fast, ramp) - int(time.time() - started)
                if remain > 0:
                    time.sleep(remain)
        log(f'wake complete: {woke}/{len(indices)} agents')

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

    # Main-health gate: while main fails its full suite, only fix-main PRs may merge.
    def worker_names(self):
        return [f'{self.org}-worker{i}' for i in range(1, self.workers + 1)]

    def require_review(self):
        # Peer review by path joins the required checks on main.
        if not self.review_paths():
            return
        status, _ = self.gitea_api('PATCH', '/branch_protections/main', {
            'enable_status_check': True,
            'status_check_contexts': [*quality.REQUIRED_CHECKS, quality.REVIEW_CHECK]})
        if status != 200:
            raise Fatal(f'could not require {quality.REVIEW_CHECK} on main (HTTP {status})')
        log(f'PRs touching {", ".join(self.review_paths())} need one peer approval ({quality.REVIEW_CHECK})')

    def protect_files(self):
        # With a product owner, PRs touching protected paths need their approval:
        # CODEOWNERS (from the prepare hook) requests their review, which is official
        # because they are the only approver, and pending official requests block
        # the merge. Gitea 1.22 has no separate code-owner requirement. Otherwise only the administrator may
        # change them; set once main exists, because Gitea 1.22 cannot check protected
        # files on the push that creates the branch.
        if self.human():
            status, _ = self.gitea_api('PATCH', '/branch_protections/main', {
                'block_on_official_review_requests': True, 'enable_approvals_whitelist': True,
                'approvals_whitelist_username': [self.human()]})
            if status != 200:
                raise Fatal(f'could not require the product owner\'s review on main (HTTP {status})')
            log(f'protected paths on main need the approval of {self.human()} (CODEOWNERS)')
            return
        patterns = self.values.get('AGENSH_PROTECTED_FILES', '').strip() or ';'.join(self.pack.protected_paths)
        if not patterns:
            return
        status, _ = self.gitea_api('PATCH', '/branch_protections/main', {'protected_file_patterns': patterns})
        if status != 200:
            raise Fatal(f'could not protect {patterns} on main (HTTP {status})')
        log(f'protected files on main: {patterns}')

    def board_container(self):
        return next((n for n in self.docker_ps(f'name=omcgitea-{self.profile}-board-service',
                                               fmt='{{.Names}}') if n), '')

    def board_note(self, kind, content):
        script = '''import json, sys, urllib.request
body = json.dumps({'thread_id': 'harness', 'type': sys.argv[2], 'content': sys.argv[3]}).encode()
request = urllib.request.Request(f'http://127.0.0.1:8660/board/{sys.argv[1]}/note', data=body,
                                 method='POST', headers={'Content-Type': 'application/json'})
sys.exit(json.load(urllib.request.urlopen(request, timeout=15)).get('status') != 'admitted')
'''
        board = self.board_container()
        if not board or run([*DOCKER, 'exec', board, 'python3', '-c', script, self.pack.board_id, kind,
                             content[:100]], quiet=True).returncode != 0:
            log(f'WARN: could not post the {kind} board entry')

    def board_entries(self):
        board = self.board_container()
        if not board:
            return None
        code, text = output([*DOCKER, 'exec', board, 'python3', '-c',
                             'import sys, urllib.request; sys.stdout.write(urllib.request.urlopen('
                             'f"http://127.0.0.1:8660/board/{sys.argv[1]}/read_all?viewer=harness", '
                             'timeout=15).read().decode())', self.pack.board_id])
        return json.loads(text).get('entries', []) if code == 0 else None

    # Backlog: a live CLAIM citing #<n> assigns issue n to its author (agensh/backlog.py).
    def backlog_tick(self, assignments):
        entries = self.board_entries()
        if entries is None:
            return
        claims = backlog.live_claims(entries, set(self.worker_names()), time.time())
        for number in assignments.issues(claims):
            status, issue = self.gitea_api('GET', f'/issues/{number}')
            if status != 200 or not isinstance(issue, dict):
                assignments.managed.pop(number, None)
                continue
            current = [user['login'] for user in issue.get('assignees') or []]
            desired = assignments.update(number, claims, current, issue.get('state'))
            if desired is None:
                continue
            status, _ = self.gitea_api('PATCH', f'/issues/{number}', {'assignees': desired})
            if 200 <= status < 300:
                log(f'backlog: #{number} assignees {current or "none"} -> {desired or "none"}')
            else:
                log(f'WARN: backlog: could not assign #{number} (HTTP {status})')

    def backlog_sync(self):
        assignments = backlog.Assignments()
        interval = env_int('AGENSH_BACKLOG_INTERVAL_S', 30)
        log(f'backlog sync: board claims citing #<issue> assign issues every {interval}s')
        while not self.stop.is_set():
            try:
                self.backlog_tick(assignments)
            except Exception as error:  # A failed sync never stops the run.
                log(f'WARN: backlog sync failed: {error}')
            self.stop.wait(interval)

    def direct_message(self, worker, message):
        dm = self.mm.dm_channel(worker)
        if not dm or not self.mm.post(dm, message):
            log(f'WARN: main-health DM to {worker} failed')

    def breaking_change(self, sha):
        # The merged PR whose merge commit is the failing head, if a PR made it.
        for page in range(1, 4):
            status, pulls = self.gitea_api('GET', f'/pulls?state=closed&sort=recentupdate&limit=50&page={page}')
            if status != 200 or not pulls:
                break
            for pull in pulls:
                if pull.get('merged') and pull.get('merge_commit_sha') == sha:
                    author = (pull.get('merged_by') or pull.get('user') or {}).get('login', '')
                    return f'PR #{pull["number"]}', author
        return 'a direct push', ''

    def health_action(self, action, gate, sha, now):
        minutes = int((now - gate.red_since) / 60) if gate.red else 0
        variables = {'SHA': sha[:12], 'CHANGE': self.health_change, 'MINUTES': str(minutes)}
        prompts = ROOT / 'prompts/main_health'
        if action == 'broken':
            self.health_change, author = self.breaking_change(sha)
            variables['CHANGE'] = self.health_change
            log(f'main-health: main fails at {sha[:12]} after {self.health_change}; only fix-main PRs merge')
            self.board_note('FAIL', f'main fails its full suite at {sha[:8]} ({self.health_change}); '
                                    'only fix-main PRs merge')
            # The author alone is alerted first, so the team does not converge on one failure.
            recipients = [author] if author in self.worker_names() else self.worker_names()
            for worker in recipients:
                self.direct_message(worker, render_prompt(prompts / 'broken.txt', **variables))
        elif action == 'alert_team':
            log(f'main-health: main still failing after {minutes}m; alerting every worker')
            for worker in self.worker_names():
                self.direct_message(worker, render_prompt(prompts / 'team.txt', **variables))
        elif action == 'lift':
            # A human notice: the gate stopped protecting main (see main-health.json).
            log(f'NOTICE: main has failed for {minutes}m since {gate.broken_sha[:12]}; fix-main restriction lifted')
            self.mm.post(self.mm.channel_id, render_prompt(prompts / 'lifted.txt', **variables))
        elif action == 'recovered':
            log(f'main-health: main passes again at {sha[:12]}')
            self.board_note('FACT', f'main passes its full suite again at {sha[:8]}')
            self.mm.post(self.mm.channel_id, render_prompt(prompts / 'recovered.txt', **variables))

    def review_paths(self):
        return [p for p in self.values.get('AGENSH_REVIEW_PATHS', '').split(';') if p]

    def review_state(self, pull):
        # Peer review by path (quality.review_status); files are cached per head.
        number, head = pull['number'], pull['head']['sha']
        files = self.pr_files.get(head)
        if files is None:
            files = []
            for page in range(1, 11):
                status, batch = self.gitea_api('GET', f'/pulls/{number}/files?limit=100&page={page}')
                if status != 200 or not batch:
                    break
                files += [f['filename'] for f in batch]
            self.pr_files[head] = files
        status, reviews = self.gitea_api('GET', f'/pulls/{number}/reviews')
        return quality.review_status(files, reviews if status == 200 else [], pull['user']['login'], self.review_paths())

    def post_status(self, posted, head, context, wanted):
        if posted.get((head, context)) == wanted:
            return
        code, _ = self.gitea_api('POST', f'/statuses/{head}', {
            'state': wanted[0], 'context': context, 'description': wanted[1][:250]})
        if 200 <= code < 300:
            posted[(head, context)] = wanted

    def health_tick(self, gate, posted):
        status, branch = self.gitea_api('GET', '/branches/main')
        if status != 200 or not isinstance(branch, dict):
            return
        sha = branch['commit']['id']
        status, combined = self.gitea_api('GET', f'/commits/{sha}/status')
        state = quality.check_state((combined or {}).get('statuses'), quality.MAIN_CHECK) if status == 200 else None
        now = time.time()
        for action in gate.observe(state, sha, now):
            self.health_action(action, gate, sha, now)
        for page in range(1, 6):
            status, pulls = self.gitea_api('GET', f'/pulls?state=open&limit=50&page={page}')
            if status != 200 or not pulls:
                break
            for pull in pulls:
                head = pull['head']['sha']
                self.post_status(posted, head, quality.HEALTH_CHECK, gate.pr_status(pull))
                if self.review_paths():
                    self.post_status(posted, head, quality.REVIEW_CHECK, self.review_state(pull))

    def main_health(self):
        gate, posted = quality.HealthGate(), {}
        self.pr_files = {}
        self.health_change = ''
        interval = env_int('AGENSH_HEALTH_INTERVAL_S', 15)
        record = self.task_out / 'main-health.json'
        log(f'main-health gate: checking main and open PRs every {interval}s')
        while not self.stop.is_set():
            try:
                self.health_tick(gate, posted)
            except Exception as error:  # A failed check never stops the run.
                log(f'WARN: main-health check failed: {error}')
            record.write_text(json.dumps({'red': gate.red, 'broken_sha': gate.broken_sha,
                                          'lifted': gate.lifted, 'history': gate.history}, indent=2) + '\n')
            self.stop.wait(interval)

    # Run state and stop conditions (docs/task_pack_design.md, run lifecycle).
    def read_state(self):
        path = self.task_out / 'run_state.json'
        return json.loads(path.read_text()) if path.is_file() else {}

    def write_state(self, state, **details):
        record = self.read_state()
        segments = record.setdefault('segments', [])
        now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        if state == 'running':
            segments.append({'mode': self.mode, 'started': now})
        elif segments:
            segments[-1].update(ended=now, **details)
        record.update(state=state, pid=os.getpid() if state == 'running' else None)
        (self.task_out / 'run_state.json').write_text(json.dumps(record, indent=2) + '\n')

    def request_stop(self, reason):
        if self.stop_reason is None:
            self.stop_reason = reason
            log(f'stop requested: {reason}')
        self.stop.set()

    def control_watch(self):
        # `python3 -m agensh.project pause|finalize` writes its request here.
        control = self.task_out / 'control'
        while not self.stop.wait(5):
            if control.is_file():
                request = control.read_text().strip()
                control.unlink(missing_ok=True)
                if request in ('pause', 'finalize'):
                    self.request_stop(request)
                else:
                    log(f'WARN: ignoring control request {request!r}')

    def team_tokens(self):
        proxy = next((n for n in self.docker_ps(f'name=omcgitea-{self.profile}-egress-proxy', fmt='{{.Names}}')
                      if n), '')
        if not proxy:
            return None
        code, text = output([*DOCKER, 'exec', proxy, 'python3', '-c',
                             'import sys, urllib.request; sys.stdout.write(urllib.request.urlopen('
                             '"http://127.0.0.1:4180/usage", timeout=10).read().decode())'])
        if code != 0:
            return None
        agents = json.loads(text).get('agents', {})
        return sum(a.get('input_tokens', 0) + a.get('output_tokens', 0) for a in agents.values())

    def token_watch(self, limit):
        # Warn at 90% of the budget; at 100% the proxy refuses requests and the run stops.
        interval, warned = env_int('AGENSH_TOKEN_CHECK_S', 30), False
        while not self.stop.wait(interval):
            used = self.team_tokens()
            if used is None:
                continue
            if used >= limit:
                log(f'token budget spent: {used} of {limit}')
                self.request_stop('tokens')
                return
            if not warned and used >= 0.9 * limit:
                warned = True
                percent = str(100 * used // limit)
                log(f'token budget at {percent}%: {used} of {limit}; warning every worker')
                message = render_prompt(ROOT / 'prompts/lifecycle/budget_warning.txt', PERCENT=percent,
                                        USED=str(used), LIMIT=str(limit))
                for worker in self.worker_names():
                    self.direct_message(worker, message)

    def issue_closer(self):
        status, timeline = self.gitea_api('GET', '/issues/1/timeline?limit=50')
        closes = [e for e in timeline or [] if status == 200 and e.get('type') == 'close']
        return (closes[-1].get('user') or {}).get('login', '') if closes else ''

    def reopen_issue(self, note):
        self.gitea_api('PATCH', '/issues/1', {'state': 'open'})
        self.gitea_api('POST', '/issues/1/comments', {'body': note})
        self.mm.post(self.mm.channel_id, note)

    def issue_watch(self):
        # With a product owner only they end the run by closing issue #1 (a worker's
        # close is reopened); without one, the team's own close ends it, unless the
        # profile asks for a fixed-length run (AGENSH_FIXED_LENGTH).
        fixed = self.values.get('AGENSH_FIXED_LENGTH', '').strip() == '1'
        while not self.stop.wait(env_int('AGENSH_ISSUE_CHECK_S', 15 if fixed else 60)):
            status, issue = self.gitea_api('GET', '/issues/1')
            if status != 200 or not isinstance(issue, dict) or issue.get('state') != 'closed':
                continue
            closer = self.issue_closer()
            if self.human() and closer != self.human():
                log(f'issue #1 closed by {closer or "unknown"}, not {self.human()}; reopening it')
                self.reopen_issue(f'Reopened: only @{self.human()}, the product owner, ends the run by closing '
                                  'this issue.')
                continue
            if fixed and not self.human():
                log(f'issue #1 closed by {closer or "unknown"} in a fixed-length run; reopening it')
                self.reopen_issue('Reopened: this run has a fixed length and does not end when this issue is '
                                  'closed. Keep improving toward the goal until the run ends.')
                continue
            log(f'issue #1 closed by {closer or "unknown"}')
            self.request_stop('issue_closed')
            return

    def finalize_notice(self, remaining):
        # A segment shorter than the notice gets none: the brief already gives its length.
        notice = self.pack.finalize_notice
        if remaining > notice and not self.stop.wait(remaining - notice):
            message = render_prompt(ROOT / 'prompts/lifecycle/before_finalize.txt',
                                    MINUTES=str(max(1, min(notice, remaining) // 60)))
            log('telling workers the run is about to finalize')
            for worker in self.worker_names():
                self.direct_message(worker, message)

    def start_stop_watchers(self, remaining):
        self.start_thread(self.control_watch)
        digest = int(self.values.get('AGENSH_DIGEST_S', '') or 0)
        if self.human() and digest > 0:
            self.start_thread(self.digest_loop, digest)
        limit = int(self.values.get('AGENSH_MAX_MODEL_TOKENS', '') or 0)
        if 'tokens' in self.pack.stop_when and limit > 0:
            self.start_thread(self.token_watch, limit)
        if 'issue_closed' in self.pack.stop_when:
            self.start_thread(self.issue_watch)
        if self.pack.finalize_notice:
            self.start_thread(self.finalize_notice, remaining)

    def announce_stop(self, template, grace, **variables):
        # Workers get the grace period to push and record their work.
        if grace <= 0:
            return
        message = render_prompt(ROOT / f'prompts/lifecycle/{template}', **variables)
        for worker in self.worker_names():
            self.direct_message(worker, message)
        log(f'waiting {grace}s for workers to push and record their work')
        time.sleep(grace)

    def pause(self, reason):
        # A spent token budget leaves workers unable to act on a message.
        grace = 0 if reason == 'tokens' else env_int('AGENSH_PAUSE_GRACE_S', 120)
        self.announce_stop('before_pause.txt', grace, GRACE=str(grace), REASON='requested')
        archives_ok = self.quiesce()
        self.save_service_logs()
        if not archives_ok:
            raise Fatal('incomplete shutdown archives; preserving containers and DATA_ROOT for recovery')
        self.make('down', quiet=True)
        self.write_state('paused', reason=reason)
        log(f'paused ({reason}); state kept in {self.profile_data}. Resume with '
            '`python3 -m agensh.project resume <project file>` (raise [budget] max_model_tokens first if it is spent)')

    def finalize(self, reason, workers_running=True):
        if workers_running and reason in ('finalize', 'issue_closed'):
            grace = env_int('AGENSH_PAUSE_GRACE_S', 120)
            self.announce_stop('before_finalize.txt', grace, MINUTES=str(max(1, grace // 60)))
        self.sync('final')
        self.export()
        if not self.quiesce():
            self.save_service_logs()
            raise Fatal('incomplete shutdown archives; preserving containers and DATA_ROOT for recovery')
        skip_eval = os.environ.get('SKIP_EVAL', '0') == '1'
        # Workers are stopped; the model proxy still runs for an evaluation that calls models,
        # and its final-evaluation route is opened outside the team's token budget.
        evaluated = False
        if self.pack.evaluate_with_services and not skip_eval:
            gate = self.profile_data / 'usage' / 'final-evaluation.open'
            run(['sudo', '-n', 'touch', str(gate)], quiet=True)
            try:
                evaluated = self.run_hook('evaluate')
            finally:
                run(['sudo', '-n', 'rm', '-f', str(gate)], quiet=True)
        self.save_service_logs()
        self.make('down', quiet=True)
        if self.pack.resumable:
            self.write_state('finalized', reason=reason)
        if skip_eval:
            log(f'SKIP_EVAL=1 → deferring programbench eval (submission left at {self.task_out}/submission.tar.gz)')
            return
        if self.pack.evaluate_with_services:
            if not evaluated:
                raise Fatal('evaluate hook failed')
            return
        if not self.run_hook('evaluate'):
            raise Fatal('evaluate hook failed')

    # Upstream sync: the pack's sync hook, before the end and again before export.
    def sync(self, phase):
        if self.pack.hook('sync') is None:
            return
        if not self.run_hook('sync', AGENSH_SYNC_PHASE=phase):
            log(f'WARN: {phase} upstream sync failed; delivering main as it is')

    def scheduled_sync(self, total_seconds):
        # Early enough for the team to resolve a conflict in a normal PR.
        if not self.stop.wait(max(0, total_seconds - self.pack.sync_before_end)):
            self.sync('scheduled')

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
        # A resumed run keeps each segment's logs: service-logs, service-logs-2, ...
        directory, segment = self.task_out / 'service-logs', 1
        while (directory / 'captured-at.txt').is_file():
            segment += 1
            directory = self.task_out / f'service-logs-{segment}'
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
        if self.pack.resumable and self.task_out.is_dir():
            self.write_state('failed', reason=f'teardown (rc={code})')

    def main(self):
        log(f'TASK={self.task} HOURS={self.hours} OUT_DIR={self.out_dir} PROFILE={self.profile} MODE={self.mode}')
        self.setup_environment()
        if self.mode == 'finalize':
            # Deliver a paused run: services only, no workers.
            try:
                self.bring_up()
            except BaseException:
                self.make('down', quiet=True)
                raise
            self.finalize('finalize', workers_running=False)
            return
        try:
            if self.mode == 'run':
                self.prepare()
            self.bring_up()
            if self.pack.resumable:
                self.write_state('running')
            if self.mode == 'run':
                self.drive()
            else:
                self.resume_drive()
            total = schedule.budget_seconds(self.hours)
            elapsed = max(0, int(time.time() - self.run_t0))
            remaining = schedule.remaining_after(total, elapsed)
            log(f'agents working for {self.hours}h ({total}s); {elapsed}s spent waking, sleeping {remaining}s')
            if self.watchdog_started:
                log('reusing pre-ramp idle watchdog')
            else:
                self.start_thread(self.watchdog, remaining)
            self.start_thread(self.reminders, remaining)
            if self.pack.hook('sync'):
                self.start_thread(self.scheduled_sync, remaining)
            self.start_stop_watchers(remaining)
            self.stop.wait(remaining)
            reason = self.stop_reason or 'budget'
            self.stop_background_loops()
            log('wall-clock budget elapsed; exporting + evaluating' if reason == 'budget' else f'stopping: {reason}')
        except BaseException as error:
            if isinstance(error, Fatal):
                log(f'FATAL: {error}')
            self.teardown(1)
            raise SystemExit(1)

        if self.pack.resumable and reason in ('pause', 'tokens'):
            self.pause(reason)
        else:
            self.finalize(reason)

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
