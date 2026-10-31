#!/usr/bin/env python3
# Projects for packs that work on real repositories: load a project file
# (.agensh/project.toml), generate its team profile, build its worker image and
# start a run. Subcommands: profile, build, run.

import argparse
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import secrets
import string
import subprocess
import sys
import tomllib

from agensh import allocate
from agensh.pack import PackError, load_pack

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agent'))
from harness_config import load_config  # noqa: E402

PROJECT_PACKS = ('software-project',)
# Debian/Ubuntu images with python3, which the worker image needs for its runtime.
BASE_IMAGES = {'default-python': 'python:3.12-bookworm'}
NAME = re.compile(r'[a-z0-9][a-z0-9-]*')
# Projects allocate from their own range, clear of the ProgramBench task table.
PORT_BASE, SUBNET_OCTET = 23000, 217
SLOT_KEYS = ('EDGE_HTTP_PORT', 'EDGE_MM_PORT', 'AGENSH_SUBNET_DEFAULT', 'AGENSH_SUBNET_EGRESS', 'AGENSH_SUBNET_EDGE')


class ProjectError(ValueError):
    pass


@dataclass(frozen=True)
class Project:
    path: Path
    pack: str
    name: str
    goal: str
    seed: str
    upstream: str
    base_branch: str
    delivery_branch: str
    acceptance_pr: tuple
    acceptance_main: tuple
    workers: int
    hours: float
    base_image: str
    network: str = ''
    extra: dict = field(default_factory=dict)

    @property
    def profile(self):
        return f'{self.pack}-{self.name}'

    @property
    def image_slug(self):
        if self.base_image in BASE_IMAGES:
            return self.base_image
        return re.sub(r'[^a-z0-9]+', '-', self.base_image.lower()).strip('-')[:40]

    @property
    def base_image_ref(self):
        return BASE_IMAGES.get(self.base_image, self.base_image)


def _known(table, allowed, where):
    unknown = set(table) - set(allowed)
    if unknown:
        raise ProjectError(f'unknown field(s) in {where}: {", ".join(sorted(unknown))}')


def _commands(value, where):
    if not isinstance(value, list) or not all(isinstance(c, str) and c.strip() and '\n' not in c for c in value):
        raise ProjectError(f'{where} must be a list of single-line commands')
    return tuple(c.strip() for c in value)


def load_project(path):
    path = Path(path).resolve()
    if not path.is_file():
        raise ProjectError(f'{path} not found')
    with path.open('rb') as stream:
        data = tomllib.load(stream)
    _known(data, ('pack', 'name', 'goal', 'goal_file', 'workspace', 'upstream', 'acceptance', 'team',
                  'budget', 'environment'), path.name)
    pack = data.get('pack', '')
    if pack not in PROJECT_PACKS:
        raise ProjectError(f'pack must be one of {", ".join(PROJECT_PACKS)}; got {pack!r}')
    name = data.get('name', '')
    if not NAME.fullmatch(str(name)) or len(name) > 40:
        raise ProjectError(f'name must be lowercase letters, digits and hyphens (at most 40); got {name!r}')
    if ('goal' in data) == ('goal_file' in data):
        raise ProjectError('set exactly one of goal or goal_file')
    if 'goal_file' in data:
        goal_path = (path.parent / data['goal_file']).resolve()
        if not goal_path.is_file():
            raise ProjectError(f'goal_file {data["goal_file"]!r} not found next to {path.name}')
        goal = goal_path.read_text()
    else:
        goal = str(data['goal'])
    if not goal.strip():
        raise ProjectError('the goal is empty')

    workspace = data.get('workspace', {})
    _known(workspace, ('seed',), '[workspace]')
    seed = workspace.get('seed', 'git')
    if seed not in ('git', 'empty'):
        raise ProjectError(f'[workspace] seed must be "git" or "empty"; got {seed!r}')
    upstream = data.get('upstream', {})
    _known(upstream, ('repo', 'base_branch', 'delivery_branch'), '[upstream]')
    repo = str(upstream.get('repo', '')).strip()
    if seed == 'git' and not repo:
        raise ProjectError('[upstream] repo is required when [workspace] seed = "git"')
    delivery = str(upstream.get('delivery_branch', 'agensh/{run_id}'))
    if '{run_id}' not in delivery:
        raise ProjectError('[upstream] delivery_branch must contain {run_id}, so runs never share a branch')

    acceptance = data.get('acceptance', {})
    _known(acceptance, ('pr', 'main'), '[acceptance]')
    team = data.get('team', {})
    _known(team, ('workers',), '[team]')
    workers = team.get('workers', 4)
    if not isinstance(workers, int) or isinstance(workers, bool) or not 1 <= workers <= 128:
        raise ProjectError('[team] workers must be an integer from 1 to 128')
    budget = data.get('budget', {})
    _known(budget, ('hours',), '[budget]')
    hours = budget.get('hours', 2)
    if isinstance(hours, bool) or not isinstance(hours, (int, float)) or hours <= 0:
        raise ProjectError('[budget] hours must be a positive number')
    environment = data.get('environment', {})
    _known(environment, ('base_image', 'network'), '[environment]')
    base_image = str(environment.get('base_image', 'default-python'))
    if base_image.startswith('default-') and base_image not in BASE_IMAGES:
        raise ProjectError(f'unknown default base image {base_image!r}; available: {", ".join(BASE_IMAGES)}')
    network = str(environment.get('network', ''))
    if network and network not in ('open', 'offline'):
        raise ProjectError(f'[environment] network must be "open" or "offline"; got {network!r}')
    return Project(path=path, pack=pack, name=name, goal=goal.strip() + '\n', seed=seed, upstream=repo,
                   base_branch=str(upstream.get('base_branch', 'main')), delivery_branch=delivery,
                   acceptance_pr=_commands(acceptance.get('pr', []), '[acceptance] pr'),
                   acceptance_main=_commands(acceptance.get('main', acceptance.get('pr', [])), '[acceptance] main'),
                   workers=workers, hours=float(hours), base_image=base_image, network=network)


def git_url(repo):
    """github.com/<owner>/<name> becomes an HTTPS clone URL; anything else is used as given."""
    match = re.fullmatch(r'(?:https://)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?', repo)
    if match:
        return f'https://github.com/{match.group(1)}/{match.group(2)}.git', f'{match.group(1)}/{match.group(2)}'
    return repo, None


def _upstream_credentials():
    path = Path.home() / '.agensh/upstream.env'
    values = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            key, sep, value = line.partition('=')
            if sep:
                values[key.strip()] = value.strip()
    upstream = os.environ.get('LLM_UPSTREAM') or values.get('LLM_UPSTREAM', '')
    token = os.environ.get('LLM_UPSTREAM_TOKEN') or values.get('LLM_UPSTREAM_TOKEN', '')
    if not upstream or not token:
        raise ProjectError(f'LLM_UPSTREAM and LLM_UPSTREAM_TOKEN must be set in {path} or the environment')
    return upstream, token


def harness_settings(args):
    return load_config(args.harness_config, {'harness': args.agent_harness, 'version': args.harness_version})


def write_profile(project, args, env_dir=ROOT):
    config = harness_settings(args)
    out = Path(env_dir) / f'.env.{project.profile}'
    old = {}
    if out.is_file():
        for line in out.read_text().splitlines():
            key, sep, value = line.partition('=')
            if sep and not key.startswith('#'):
                old[key] = value
    alphabet = string.ascii_letters + string.digits

    def password(key, length):
        if re.fullmatch(r'[A-Za-z0-9]{20,}', old.get(key, '')):
            return old[key]
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    workers = args.workers or project.workers
    prefix = allocate.subnet_layout(workers)[0]
    if all(old.get(k) for k in SLOT_KEYS) and old['AGENSH_SUBNET_DEFAULT'].endswith(f'/{prefix}'):
        slot = {k: old[k] for k in SLOT_KEYS}
    else:
        ports, networks = allocate.profile_claims(str(env_dir), str(out))
        _, chosen = allocate.choose_slot(PORT_BASE, SUBNET_OCTET, workers, ports,
                                         networks + allocate.host_networks(), allocate.port_is_free)
        slot = chosen
    llm_upstream, llm_token = _upstream_credentials()
    harness = config.harness
    settings = config.environment()
    tag = os.environ.get('AGENT_IMAGE_TAG') or 'agensh'
    mm = int(slot['EDGE_MM_PORT'])
    keys = [
        ('ORG_NAME', 'team'), ('PROFILE', project.profile),
        ('AGENSH_PACK', project.pack), ('AGENSH_PROJECT_FILE', str(project.path)),
        ('EDGE_HTTP_PORT', slot['EDGE_HTTP_PORT']), ('EDGE_MM_PORT', mm), ('EDGE_DOMAIN', 'localhost'),
        ('MATTERMOST_SITE_URL', f'http://localhost:{mm}'), ('DATA_ROOT', f'{ROOT}/.claude-team-data'),
        ('GITEA_ADMIN_USER', 'chairman'), ('GITEA_ADMIN_PASSWORD', password('GITEA_ADMIN_PASSWORD', 22)),
        ('MYSQL_ROOT_PASSWORD', password('MYSQL_ROOT_PASSWORD', 64)), ('MYSQL_PASSWORD', password('MYSQL_PASSWORD', 64)),
        ('SECRET_SERVICE_INTERNAL_AUTH', password('SECRET_SERVICE_INTERNAL_AUTH', 64)),
        ('MATTERMOST_ADMIN_USER', 'mmadmin'), ('MATTERMOST_ADMIN_PASSWORD', password('MATTERMOST_ADMIN_PASSWORD', 23)),
        ('ANTHROPIC_BASE_URL', 'http://egress-proxy:4180'), ('AGENSH_LLM_UPSTREAM', llm_upstream),
        *[(k, v) for k, v in settings.items()],
        ('HARNESS_CONFIG', str(Path(args.harness_config or os.environ.get('HARNESS_CONFIG')
                                    or ROOT / 'agent/config/harness.json').expanduser().resolve())),
        ('ANTHROPIC_MODEL', config.model), ('ANTHROPIC_API_KEY', 'local-proxy-no-auth'),
        ('UPSTREAM_AUTH_TOKEN', llm_token), ('AGENSH_WORKERS', workers), ('REPOS', 'main'),
        ('MINI_ROUTER_STUCK_MS', 1200000),
        ('AGENT_IMAGE', f'omcgitea-agent-{project.image_slug}-{harness}:{tag}'),
        ('AGENSH_SUBNET_DEFAULT', slot['AGENSH_SUBNET_DEFAULT']),
        ('AGENSH_SUBNET_EGRESS', slot['AGENSH_SUBNET_EGRESS']),
        ('AGENSH_SUBNET_EDGE', slot['AGENSH_SUBNET_EDGE']), ('UPSTREAM_AUTH_STYLE', 'bearer'),
        (f'{harness.upper()}_CLI_VERSION', config.version),
        (f'{harness.upper()}_PROVIDER_WIRE_API', 'messages' if harness == 'claude' else 'responses'),
    ]
    if harness == 'copilot':
        keys.append(('COPILOT_PROVIDER_TYPE', 'openai'))
    if project.network:
        keys.append(('AGENSH_NETWORK', project.network))
    for key in ('MINI_ROUTER_IMAGE', 'BOARD_IMAGE', 'BOOTSTRAP_IMAGE', 'SECRET_SERVICE_IMAGE', 'WORKER_CPUS', 'WORKER_MEMORY'):
        if os.environ.get(key):
            keys.append((key, os.environ[key]))
    temporary = out.with_name(out.name + f'.tmp.{os.getpid()}')
    temporary.write_text(''.join(f'{k}={v}\n' for k, v in keys))
    temporary.chmod(0o600)
    temporary.replace(out)
    return out


def build_image(project, args):
    config = harness_settings(args)
    image = f'omcgitea-agent-{project.image_slug}-{config.harness}:{os.environ.get("AGENT_IMAGE_TAG") or "agensh"}'
    docker = os.environ.get('DOCKER', 'sudo -n docker').split()
    command = [*docker, 'build', '-f', 'agent/Dockerfile', '--build-arg', f'TASK_IMAGE={project.base_image_ref}',
               '--build-arg', f'AGENT_HARNESS={config.harness}',
               '--build-arg', f'{config.harness.upper()}_CLI_VERSION={config.version}', '-t', image, '.']
    if os.environ.get('AGENT_BASE_IMAGE'):
        at = len(docker) + 1  # right after `build`
        command[at:at] = ['--build-arg', f'AGENT_BASE_IMAGE={os.environ["AGENT_BASE_IMAGE"]}']
    if subprocess.run(command, cwd=ROOT).returncode != 0:
        raise ProjectError(f'building {image} failed')
    check = [*docker, 'run', '--rm', '--network', 'none', '--entrypoint', 'python3', image,
             '/opt/omcgitea/check_harness.py', config.harness, config.version]
    if subprocess.run(check, cwd=ROOT).returncode != 0:
        raise ProjectError(f'{image} failed the harness check')
    return image


def main():
    parser = argparse.ArgumentParser(description='Generate profiles, build images and run project teams.')
    commands = parser.add_subparsers(dest='command', required=True)
    for name, text in (('profile', 'write the .env.<pack>-<name> profile'),
                       ('build', 'build the worker image for the project'),
                       ('run', 'run one team for the project with scripts/team_run.sh')):
        command = commands.add_parser(name, help=text)
        command.add_argument('project', type=Path, help='project file, e.g. path/to/repo/.agensh/project.toml')
        if name != 'run':
            command.add_argument('--agent-harness')
            command.add_argument('--harness-version')
            command.add_argument('--harness-config', type=Path)
        if name == 'profile':
            command.add_argument('--workers', type=int, help='override [team] workers')
            command.add_argument('--env-dir', type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        project = load_project(args.project)
        load_pack(project.pack)
        if args.command == 'profile':
            print(write_profile(project, args, args.env_dir))
        elif args.command == 'build':
            print(build_image(project, args))
        else:
            env = dict(os.environ, TASK=project.name, PROFILE=project.profile,
                       HOURS=os.environ.get('HOURS') or f'{project.hours:g}')
            os.execvpe('bash', ['bash', str(ROOT / 'scripts/team_run.sh')], env)
    except (ProjectError, PackError, ValueError) as error:
        sys.exit(f'agensh.project: {error}')


if __name__ == '__main__':
    main()
