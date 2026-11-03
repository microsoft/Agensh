#!/usr/bin/env python3
# Render prompts, profiles and Compose files for a checkout into a directory tree.
# Compare trees from two revisions to see exactly what a refactor changes.

from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Fixed inputs keep snapshots deterministic; none of these values are credentials.
TASK = 'jgm__pandoc.5caad90'
HOURS = 6
DEFAULT_WORKERS = range(1, 17)
# Exact releases avoid resolving `latest` from the npm registry.
DEFAULT_HARNESS_VERSIONS = {'copilot': '1.0.70', 'pi': '1.4.0', 'codex': '0.164.0',
                            'claude': '2.1.312'}
FIXED_PASSWORDS = {
    'GITEA_ADMIN_PASSWORD': 'FixtureGiteaAdmin000000',
    'MYSQL_ROOT_PASSWORD': 'FixtureMysqlRoot0000000000',
    'MYSQL_PASSWORD': 'FixtureMysqlUser0000000000',
    'SECRET_SERVICE_INTERNAL_AUTH': 'FixtureSecretAuth000000000',
    'MATTERMOST_ADMIN_PASSWORD': 'FixtureMattermost000000',
}
FIXTURE_ENV = {
    'LLM_UPSTREAM': 'https://gateway.invalid',
    'LLM_UPSTREAM_TOKEN': 'fixture-upstream-credential',
}
# Values the runner obtains from Mattermost at launch time.
MM_TEAM_ID = 'fixture-team-id'
TASK_CHANNEL_ID = 'fixture-channel-id'
REPO = 'main'


def run(command, *, env=None, cwd=None, stdin=None):
    result = subprocess.run(command, env=env, cwd=cwd, input=stdin, text=True,
                            capture_output=True)
    if result.returncode != 0:
        raise SystemExit(f'render_snapshot: {command[0]} failed ({result.returncode}):\n'
                         f'{result.stderr.strip()}')
    return result.stdout


def clean_env(home, **extra):
    env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': str(home), 'LANG': 'C.UTF-8'}
    env.update(extra)
    return env


def envsubst(text, variables, names=None):
    # names=None mirrors unrestricted envsubst; a string mirrors the SHELL-FORMAT argument.
    command = ['envsubst'] if names is None else ['envsubst', names]
    return run(command, env={'PATH': os.environ.get('PATH', '/usr/bin:/bin'), **variables},
               stdin=text)


def render_prompt(root, path, **variables):
    # The runner captures render_prompt with $(...), which drops trailing newlines.
    library = root / 'scripts/lib_prompts.sh'
    pairs = [f'{k}={v}' for k, v in variables.items()]
    if library.is_file():
        script = 'source "$1"; shift; out="$(render_prompt "$@")"; printf %s "$out"'
        return run(['bash', '-c', script, 'render', str(library), str(path), *pairs],
                   env=clean_env(root))
    # Revisions before scripts/lib_prompts.sh defined render_prompt inside the runner.
    names = ''.join('${%s}' % name for name in variables)
    text = envsubst(path.read_text(), {k: str(v) for k, v in variables.items()}, names)
    return text.rstrip('\n')


def worker_counts(value):
    # Accept comma-separated counts and inclusive ranges, e.g. "1-4,8,16".
    counts = set()
    for part in value.split(','):
        low, _, high = part.strip().partition('-')
        try:
            low, high = int(low), int(high or low)
        except ValueError:
            raise argparse.ArgumentTypeError(f'invalid worker count list: {value!r}')
        if not 1 <= low <= high:
            raise argparse.ArgumentTypeError(f'invalid worker count range: {part!r}')
        counts.update(range(low, high + 1))
    return sorted(counts)


def harness_version(value):
    name, sep, version = value.partition('=')
    if not sep or name not in DEFAULT_HARNESS_VERSIONS or not version:
        raise argparse.ArgumentTypeError(
            f'expected HARNESS=VERSION with HARNESS in {", ".join(DEFAULT_HARNESS_VERSIONS)}')
    return name, version


# Revisions before the naming migration used scripts/ for ProgramBench tooling,
# pbench-single-node-<task> profiles and PBENCH_* names for core settings.
LAYOUTS = {
    'current': {'gen_env': 'tasks/programbench/scripts/gen_env.sh', 'profile': 'programbench-pandoc',
                'overlay': 'docker/docker_compose.team.yml', 'workers_key': 'AGENSH_WORKERS',
                'acp_driver': 'tasks/programbench/scripts/acp_driver.py'},
    'legacy': {'gen_env': 'scripts/pbench_gen_env.sh', 'profile': 'pbench-single-node-pandoc',
               'overlay': 'docker/docker_compose.pbench.yml', 'workers_key': 'PBENCH_WORKERS_PER_TEAM',
               'acp_driver': 'scripts/acp_driver.py'},
}


class Snapshot:
    def __init__(self, root: Path, out: Path, harnesses, versions, workers, jobs):
        self.root = root.resolve()
        self.layout = LAYOUTS['current' if (self.root / LAYOUTS['current']['gen_env']).is_file() else 'legacy']
        self.out = out
        self.harnesses = harnesses
        self.versions = versions
        self.workers = workers
        self.jobs = jobs
        self.scratch = Path(tempfile.mkdtemp(prefix='render-snapshot-'))

    def normalize(self, text):
        text = text.replace(str(self.scratch), '<SCRATCH>')
        return text.replace(str(self.root), '<ROOT>')

    def write(self, relative, text):
        path = self.out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.normalize(text))

    def fixtures(self):
        # Recording the inputs makes a diff caused by changed options self-explanatory.
        self.write('fixtures.json', json.dumps({
            'task': TASK, 'profile': self.layout['profile'], 'hours': HOURS, 'workers': self.workers,
            'harness_versions': {name: self.versions[name] for name in self.harnesses},
        }, indent=2) + '\n')

    def task_prompts(self):
        # Task messages moved from prompts/ into the ProgramBench pack.
        pack = self.root / 'tasks/programbench/prompts'
        return pack if pack.is_dir() else self.root / 'prompts'

    def prompts(self):
        core, task = self.root / 'prompts', self.task_prompts()
        brief = render_prompt(self.root, task / 'task_brief.txt', TASK=TASK, REPO=REPO,
                              MM_TEAM_ID=MM_TEAM_ID, TASK_CHANNEL_ID=TASK_CHANNEL_ID)
        self.write('team/task_brief.txt', brief)
        self.write('team/task_issue.json', json.dumps(
            {'title': f'[pbench] {TASK}', 'body': brief}, indent=2) + '\n')
        self.write('team/kickoff.txt', render_prompt(self.root, core / 'kickoff.txt', TASK_BRIEF=brief))
        for name in ('idle', 'idle_delivery', 'deadline_45m', 'deadline_5m'):
            self.write(f'team/{name}.txt', render_prompt(self.root, task / f'{name}.txt'))

    def agents_md(self, variables):
        # Render as agent/entrypoint.sh does, with the worker's environment.
        prompts = self.root / 'prompts'
        renderer = self.root / 'agent/render_agents.sh'
        if renderer.is_file():
            return run(['bash', str(renderer), str(prompts / 'agents.txt'), str(self.task_prompts())],
                       env={'PATH': os.environ.get('PATH', '/usr/bin:/bin'), **variables})
        # Earlier revisions exported the brief as PBENCH_BRIEF; $(cat) drops trailing newlines.
        legacy = dict(variables, PBENCH_BRIEF=(prompts / 'pbench_brief.txt').read_text().rstrip('\n'))
        return envsubst((prompts / 'agents.txt').read_text(), legacy)

    def worker_files(self, org, workers):
        variables = {
            'AGENT_NAME': f'{org}-worker1',
            'GITEA_ORG': org,
            # The core template names the team size AGENSH_WORKERS (PBENCH_WORKERS before).
            'AGENSH_WORKERS': str(workers),
            'PBENCH_WORKERS': str(workers),
            'GITEA_HOST': 'http://gitea:3000',
            'GITEA_TOKEN': '<GITEA_TOKEN>',
            'MATTERMOST_HOST': 'http://mattermost:8065',
            'MATTERMOST_TOKEN': '<MATTERMOST_TOKEN>',
            'BOARD_SERVICE_URL': 'http://board-service:8660',
            'BOARD_IDS': 'pbench-top',
            # Compose passes the pack's task channel; ProgramBench keeps pbench-task.
            'TASK_CHANNEL': 'pbench-task',
            'MCP_TOOL_TIMEOUT_MS': '180000',
            'AGENT_NODE': '/opt/agentrt/bin/node',
        }
        self.write(f'worker/w{workers:02d}/AGENTS.md', self.agents_md(variables))
        mcp = json.loads(envsubst((self.root / 'agent/config/mcp.json.tmpl').read_text(), variables))
        for server in mcp.get('mcpServers', {}).values():
            if 'timeout' in server:
                server['timeout'] = int(server['timeout'])
        self.write(f'worker/w{workers:02d}/mcp.json', json.dumps(mcp, indent=2) + '\n')

    def single_agent(self):
        prompts = self.task_prompts() / 'single-agent'
        rendered = {}
        for name in ('brief', 'rules', 'resume'):
            text = (prompts / f'{name}.txt').read_text()
            text = text.replace('${TASK}', TASK).replace('${HOURS}', str(HOURS))
            rendered[name] = text.rstrip('\n') if name == 'resume' else text
        spec = importlib.util.spec_from_file_location('acp_driver', self.root / self.layout['acp_driver'])
        driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(driver)
        self.write('single-agent/initial.txt',
                   driver.build_initial_prompt(rendered['brief'], rendered['rules']))
        self.write('single-agent/resume.txt', driver._resume_text(rendered['resume'], 0, 600))
        self.write('single-agent/resume_after_watchdog.txt',
                   driver._resume_text(rendered['resume'], 600, 600))
        self.write('single-agent/resume_near_deadline.txt',
                   driver._deadline_text(rendered['resume'], 60))

    def profile(self, harness, workers, directory):
        # Pre-seeded passwords are preserved by the generator, keeping output stable.
        env_file = directory / f".env.{self.layout['profile']}"
        env_file.write_text(''.join(f'{k}={v}\n' for k, v in FIXED_PASSWORDS.items()))
        env = clean_env(directory, ENV_DIR=str(directory), TASKS=TASK, WORKERS=str(workers),
                        **FIXTURE_ENV)
        run(['bash', str(self.root / self.layout['gen_env']),
             '--agent-harness', harness, '--harness-version', self.versions[harness]],
            env=env, cwd=self.root)
        text = env_file.read_text()
        values = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
        return env_file, values, re.sub(r'^(UPSTREAM_AUTH_TOKEN)=.*$', r'\1=<REDACTED>',
                                        text, flags=re.M)

    def compose(self, harness, workers, directory, env_file, values):
        # Mirror the Makefile's render-base and COMPOSE invocation. The profile's
        # version is exported so the generator never resolves `latest` from npm.
        workers_key = self.layout['workers_key']
        env = clean_env(directory, **{workers_key: values[workers_key]},
                        AGENT_HARNESS=values['AGENT_HARNESS'],
                        HARNESS_VERSION=values['HARNESS_VERSION'])
        base = run([sys.executable, str(self.root / 'tools/gen_compose_prod.py')],
                   env=env, cwd=self.root)
        # Compose resolves relative paths against the first file's directory.
        docker_dir = self.root / 'docker'
        staged = docker_dir / f'_gen_prod.render-snapshot-{os.getpid()}-{harness}-{workers}.yml'
        staged.write_text(base)
        try:
            resolved = run(['docker', 'compose', '-f', str(staged),
                            '-f', str(self.root / self.layout['overlay']),
                            '--project-name', f"omcgitea-{self.layout['profile']}", '--env-file', str(env_file),
                            '--profile', self.layout['profile'], 'config'],
                           env=clean_env(directory))
        finally:
            staged.unlink()
        return base, re.sub(r'(UPSTREAM_AUTH_TOKEN: ).*', r'\1<REDACTED>', resolved)

    def team(self, harness, workers):
        directory = self.scratch / f'{harness}-w{workers}'
        directory.mkdir()
        env_file, values, profile = self.profile(harness, workers, directory)
        base, resolved = self.compose(harness, workers, directory, env_file, values)
        prefix = f'compose/{harness}/w{workers:02d}'
        self.write(f'{prefix}/profile.env', profile)
        self.write(f'{prefix}/gen_prod.yml', base)
        self.write(f'{prefix}/resolved.yml', resolved)
        return values['ORG_NAME']

    def build(self):
        if self.out.exists():
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        try:
            self.fixtures()
            self.prompts()
            self.single_agent()
            # Rendering is subprocess-bound, so threads overlap the generators and Compose.
            with concurrent.futures.ThreadPoolExecutor(self.jobs) as pool:
                jobs = [pool.submit(self.team, harness, workers)
                        for harness in self.harnesses for workers in self.workers]
                orgs = {job.result() for job in jobs}
            (org,) = orgs
            for workers in self.workers:
                self.worker_files(org, workers)
        finally:
            shutil.rmtree(self.scratch, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        description='Render prompts, profiles and Compose files with fixed fixtures.')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1],
                        help='checkout to render (default: this checkout)')
    parser.add_argument('--out', type=Path, required=True, help='output directory (replaced)')
    parser.add_argument('--harness', action='append', choices=sorted(DEFAULT_HARNESS_VERSIONS),
                        help='harness to render (repeatable; default: all)')
    parser.add_argument('--harness-version', action='append', type=harness_version, default=[],
                        metavar='HARNESS=VERSION',
                        help='override a harness release (repeatable; defaults: '
                             + ', '.join(f'{k}={v}' for k, v in DEFAULT_HARNESS_VERSIONS.items())
                             + ')')
    parser.add_argument('--workers', type=worker_counts, default=list(DEFAULT_WORKERS),
                        help='worker counts, e.g. "1-4,8,16" (default: 1-16)')
    parser.add_argument('--jobs', type=int, default=os.cpu_count() or 4,
                        help='parallel renders (default: CPU count)')
    args = parser.parse_args()
    for tool in ('envsubst', 'docker'):
        if shutil.which(tool) is None:
            raise SystemExit(f'render_snapshot: {tool} is required')
    versions = dict(DEFAULT_HARNESS_VERSIONS, **dict(args.harness_version))
    Snapshot(args.root, args.out, args.harness or list(DEFAULT_HARNESS_VERSIONS), versions,
             args.workers, max(1, args.jobs)).build()


if __name__ == '__main__':
    main()
