#!/usr/bin/env python3
# Projects for packs that work on real repositories: load a project file
# (.agensh/project.toml), generate its team profile, build its worker image and
# run its team: profile, build, run, then pause, resume, finalize and status.

import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import secrets
import string
import subprocess
import sys
import tomllib

from agensh import allocate
from agensh.pack import PackError, load_pack, parse_duration, protected_path_list

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agent'))
from harness_config import load_config  # noqa: E402

PROJECT_PACKS = ('software-project',)
# Debian/Ubuntu images with python3, which the worker image needs for its runtime.
BASE_IMAGES = {'default-python': 'python:3.12-bookworm'}
NAME = re.compile(r'[a-z0-9][a-z0-9-]*')
DOMAIN = re.compile(r'(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}')
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
    allow_domains: tuple = ()
    max_model_tokens: int = 0
    # [human]: an optional product owner with Gitea and Mattermost accounts.
    human: str = ''
    digest_seconds: int = 0
    # [coordination]: one worker plans before the others wake.
    planning: bool = False
    planning_timeout: int = 2700
    review_paths: tuple = ()
    # [budget] fixed_length: the run uses its whole wall-clock budget; a worker
    # closing issue #1 does not end it (comparisons across team sizes need this).
    fixed_length: bool = False
    # [workspace] history = "snapshot": import the (sanitized) tree as one commit, no history.
    history: str = 'full'
    sanitize: str = ''
    # [acceptance] final: the evaluate hook's commands; private_dir is mounted only there.
    acceptance_final: tuple = ()
    private_dir: str = ''
    # [team.models]: worker number -> model id, for per-role models.
    models: dict = field(default_factory=dict)
    protected_paths: tuple = ()
    ci_timeout_minutes: int = 15
    extra: dict = field(default_factory=dict)

    @property
    def profile(self):
        return f'{self.pack}-{self.name}'

    @property
    def final_commands(self):
        return self.acceptance_final or self.acceptance_main

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
                  'budget', 'environment', 'human', 'coordination'), path.name)
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
    _known(workspace, ('seed', 'history', 'sanitize'), '[workspace]')
    seed = workspace.get('seed', 'git')
    if seed not in ('git', 'empty'):
        raise ProjectError(f'[workspace] seed must be "git" or "empty"; got {seed!r}')
    history = workspace.get('history', 'full')
    if history not in ('full', 'snapshot'):
        raise ProjectError(f'[workspace] history must be "full" or "snapshot"; got {history!r}')
    sanitize = _outside_path(workspace.get('sanitize', ''), path, '[workspace] sanitize', want='file')
    if sanitize and (history != 'snapshot' or seed != 'git'):
        raise ProjectError('[workspace] sanitize needs seed = "git" and history = "snapshot", '
                           'or the removed files would stay in the imported history')
    upstream = data.get('upstream', {})
    _known(upstream, ('repo', 'base_branch', 'delivery_branch'), '[upstream]')
    repo = str(upstream.get('repo', '')).strip()
    if seed == 'git' and not repo:
        raise ProjectError('[upstream] repo is required when [workspace] seed = "git"')
    delivery = str(upstream.get('delivery_branch', 'agensh/{run_id}'))
    if '{run_id}' not in delivery:
        raise ProjectError('[upstream] delivery_branch must contain {run_id}, so runs never share a branch')

    acceptance = data.get('acceptance', {})
    _known(acceptance, ('pr', 'main', 'final', 'private_dir', 'protected_paths', 'timeout_minutes'), '[acceptance]')
    private_dir = _outside_path(acceptance.get('private_dir', ''), path, '[acceptance] private_dir', want='dir')
    try:
        protected = protected_path_list(acceptance.get('protected_paths', []), '[acceptance] protected_paths')
    except PackError as error:
        raise ProjectError(str(error)) from None
    timeout = acceptance.get('timeout_minutes', 15)
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 180:
        raise ProjectError('[acceptance] timeout_minutes must be an integer from 1 to 180')
    team = data.get('team', {})
    _known(team, ('workers', 'models'), '[team]')
    workers = team.get('workers', 4)
    if not isinstance(workers, int) or isinstance(workers, bool) or not 1 <= workers <= 128:
        raise ProjectError('[team] workers must be an integer from 1 to 128')
    models = team.get('models', {})
    if not isinstance(models, dict) or not all(
            str(k).isdigit() and 1 <= int(k) <= workers and isinstance(v, str) and re.fullmatch(r'[A-Za-z0-9._:/-]+', v)
            for k, v in models.items()):
        raise ProjectError('[team.models] maps worker numbers to model ids, e.g. "3" = "gpt-5.6-mini"')
    budget = data.get('budget', {})
    _known(budget, ('hours', 'max_model_tokens', 'fixed_length'), '[budget]')
    fixed_length = budget.get('fixed_length', False)
    if not isinstance(fixed_length, bool):
        raise ProjectError('[budget] fixed_length must be true or false')
    max_tokens = budget.get('max_model_tokens', 0)
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 0:
        raise ProjectError('[budget] max_model_tokens must be a non-negative integer (0: no limit)')
    hours = budget.get('hours', 2)
    if isinstance(hours, bool) or not isinstance(hours, (int, float)) or hours <= 0:
        raise ProjectError('[budget] hours must be a positive number')
    environment = data.get('environment', {})
    _known(environment, ('base_image', 'network', 'allow_domains'), '[environment]')
    base_image = str(environment.get('base_image', 'default-python'))
    if base_image.startswith('default-') and base_image not in BASE_IMAGES:
        raise ProjectError(f'unknown default base image {base_image!r}; available: {", ".join(BASE_IMAGES)}')
    network = str(environment.get('network', ''))
    if network and network not in ('open', 'offline', 'allowlist', 'auto'):
        raise ProjectError(f'[environment] network must be open, allowlist, offline or auto; got {network!r}')
    domains = environment.get('allow_domains', [])
    if not isinstance(domains, list) or not all(isinstance(d, str) and DOMAIN.fullmatch(d.lower()) for d in domains):
        raise ProjectError('[environment] allow_domains must be a list of domain names, e.g. ["pypi.internal.example"]')
    human_table = data.get('human', {})
    _known(human_table, ('mode', 'username', 'digest'), '[human]')
    mode = human_table.get('mode', 'none')
    if mode not in ('none', 'optional'):
        raise ProjectError(f'[human] mode must be "none" or "optional"; got {mode!r}')
    username = str(human_table.get('username', 'owner'))
    if not NAME.fullmatch(username) or username in ('chairman', 'mmadmin', 'harness') or username.startswith('team-'):
        raise ProjectError(f'[human] username {username!r} must be a lowercase name not used by the team')
    try:
        digest = parse_duration(human_table.get('digest', '1h'))
        coordination = data.get('coordination', {})
        _known(coordination, ('planning', 'planning_timeout', 'review_paths'), '[coordination]')
        review_paths = protected_path_list(coordination.get('review_paths', []), '[coordination] review_paths')
        planning_timeout = parse_duration(coordination.get('planning_timeout', '45m'))
    except PackError as error:
        raise ProjectError(str(error)) from None
    if review_paths and workers < 2:
        raise ProjectError('[coordination] review_paths needs at least two workers: a peer must approve')
    planning = coordination.get('planning', False)
    if not isinstance(planning, bool):
        raise ProjectError('[coordination] planning must be true or false')
    return Project(path=path, pack=pack, name=name, goal=goal.strip() + '\n', seed=seed, upstream=repo,
                   base_branch=str(upstream.get('base_branch', 'main')), delivery_branch=delivery,
                   acceptance_pr=_commands(acceptance.get('pr', []), '[acceptance] pr'),
                   acceptance_main=_commands(acceptance.get('main', acceptance.get('pr', [])), '[acceptance] main'),
                   workers=workers, hours=float(hours), base_image=base_image, network=network,
                   allow_domains=tuple(d.lower() for d in domains), max_model_tokens=max_tokens,
                   human=username if mode == 'optional' else '', digest_seconds=digest if mode == 'optional' else 0,
                   planning=planning, planning_timeout=planning_timeout, review_paths=review_paths,
                   models={int(k): v for k, v in models.items()}, history=history, sanitize=sanitize,
                   fixed_length=fixed_length,
                   acceptance_final=_commands(acceptance['final'], '[acceptance] final') if 'final' in acceptance else (),
                   private_dir=private_dir,
                   protected_paths=protected, ci_timeout_minutes=timeout)


def _outside_path(value, project_file, where, want):
    # Files that must stay away from the team (a sanitize script, held-out data):
    # absolute or relative to the project file, and existing.
    if not value:
        return ''
    if not isinstance(value, str):
        raise ProjectError(f'{where} must be a path')
    resolved = (project_file.parent / value).resolve()
    if not (resolved.is_file() if want == 'file' else resolved.is_dir()):
        raise ProjectError(f'{where} {value!r} is not an existing {"file" if want == "file" else "directory"}')
    return str(resolved)


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
    if project.max_model_tokens:
        keys.append(('AGENSH_MAX_MODEL_TOKENS', project.max_model_tokens))
    if project.fixed_length:
        keys.append(('AGENSH_FIXED_LENGTH', 1))
    if project.human:
        keys += [('AGENSH_HUMAN', project.human), ('AGENSH_DIGEST_S', project.digest_seconds)]
    if project.planning:
        keys += [('AGENSH_PLANNING', 1), ('AGENSH_PLANNING_TIMEOUT_S', project.planning_timeout)]
    if project.review_paths:
        keys.append(('AGENSH_REVIEW_PATHS', ';'.join(project.review_paths)))
    if project.models:
        # The egress proxy sends these workers' requests to their own model.
        keys.append(('AGENSH_AGENT_MODELS', ','.join(f'team-worker{n}={m}' for n, m in sorted(project.models.items()))))
    pack = load_pack(project.pack)
    if pack.ci_gate:
        paths = dict.fromkeys(pack.protected_paths + project.protected_paths)
        keys += [('AGENSH_PROTECTED_FILES', ';'.join(paths)),
                 ('ACT_JOB_TIMEOUT', f'{project.ci_timeout_minutes}m')]
    for key in ('MINI_ROUTER_IMAGE', 'BOARD_IMAGE', 'BOOTSTRAP_IMAGE', 'SECRET_SERVICE_IMAGE', 'WORKER_CPUS', 'WORKER_MEMORY'):
        if os.environ.get(key):
            keys.append((key, os.environ[key]))
    temporary = out.with_name(out.name + f'.tmp.{os.getpid()}')
    temporary.write_text(''.join(f'{k}={v}\n' for k, v in keys))
    temporary.chmod(0o600)
    temporary.replace(out)
    return out


# Images the team stack needs besides the worker image; Compose builds bootstrap and
# secret-service itself. The environment names another tag for each (as in the profile).
SHARED_IMAGES = (('AGENT_BASE_IMAGE', 'omcgitea-agent-base:pbench', 'agent/Dockerfile.base', 'agent'),
                 ('MINI_ROUTER_IMAGE', 'omcgitea-mini-router:local', 'mini-router/Dockerfile', 'mini-router'),
                 ('BOARD_IMAGE', 'omcgitea-board:local', 'board-service/Dockerfile', 'board-service'))


def build_shared_images(docker):
    # A fresh host has none of them; existing ones are reused, as Docker's cache would.
    for variable, default, dockerfile, context in SHARED_IMAGES:
        tag = os.environ.get(variable) or default
        if subprocess.run([*docker, 'image', 'inspect', tag], capture_output=True).returncode == 0:
            continue
        print(f'agensh.project: building {tag} from {dockerfile}', file=sys.stderr)
        if subprocess.run([*docker, 'build', '-q', '-f', dockerfile, '-t', tag, context], cwd=ROOT,
                          stdout=subprocess.DEVNULL).returncode != 0:
            raise ProjectError(f'building {tag} failed')


def build_image(project, args):
    config = harness_settings(args)
    image = f'omcgitea-agent-{project.image_slug}-{config.harness}:{os.environ.get("AGENT_IMAGE_TAG") or "agensh"}'
    docker = os.environ.get('DOCKER', 'sudo -n docker').split()
    build_shared_images(docker)
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


def out_dir():
    return Path(os.environ.get('OUT_DIR') or ROOT / 'out/projects')


def run_state(project):
    path = out_dir() / project.name / 'run_state.json'
    return json.loads(path.read_text()) if path.is_file() else {}


def driver_alive(state):
    pid = state.get('pid')
    if state.get('state') != 'running' or not pid:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def start_driver(project, mode):
    env = dict(os.environ, TASK=project.name, PROFILE=project.profile, OUT_DIR=str(out_dir()), AGENSH_MODE=mode,
               HOURS=os.environ.get('HOURS') or f'{project.hours:g}')
    os.execvpe('bash', ['bash', str(ROOT / 'scripts/team_run.sh')], env)


def control(project, command):
    # pause and finalize reach a running driver through its control file.
    state = run_state(project)
    if driver_alive(state):
        (out_dir() / project.name / 'control').write_text(command + '\n')
        print(f'{command} requested; the driver acts within a few seconds (see run_state.json)')
        return
    if command == 'finalize' and state.get('state') == 'paused':
        start_driver(project, 'finalize')
    raise ProjectError(f'{project.name} is {state.get("state") or "not started"}; {command} needs a running driver'
                       + (' or a paused run' if command == 'finalize' else ''))


def main():
    parser = argparse.ArgumentParser(description='Generate profiles, build images and run project teams.')
    commands = parser.add_subparsers(dest='command', required=True)
    for name, text in (('profile', 'write the .env.<pack>-<name> profile'),
                       ('build', 'build the worker image for the project'),
                       ('run', 'run one team for the project with scripts/team_run.sh'),
                       ('pause', 'pause a running team, keeping its state for resume'),
                       ('resume', 'continue a paused team with fresh sessions'),
                       ('finalize', 'deliver a running or paused team: sync upstream, export, evaluate'),
                       ('status', 'print the run state')):
        command = commands.add_parser(name, help=text)
        command.add_argument('project', type=Path, help='project file, e.g. path/to/repo/.agensh/project.toml')
        if name in ('profile', 'build'):
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
        elif args.command == 'run':
            start_driver(project, 'run')
        elif args.command == 'resume':
            state = run_state(project)
            if state.get('state') != 'paused':
                raise ProjectError(f'{project.name} is {state.get("state") or "not started"}; resume needs a paused run')
            start_driver(project, 'resume')
        elif args.command in ('pause', 'finalize'):
            control(project, args.command)
        else:
            state = run_state(project)
            if state and state.get('state') == 'running' and not driver_alive(state):
                state['state'] = 'running (driver not alive)'
            print(json.dumps(state or {'state': 'not started'}, indent=2))
    except (ProjectError, PackError, ValueError) as error:
        sys.exit(f'agensh.project: {error}')


if __name__ == '__main__':
    main()
