# Load a task pack: tasks/<name>/pack.toml with its prompts and hook executables.
# Only the fields the team driver uses today are accepted; unknown fields fail.

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]
DURATION = re.compile(r'^(\d+)([smh])$')
HOOKS = ('prepare', 'sync', 'export', 'evaluate')
# Why a run segment ends: the wall-clock budget, the token budget, or issue #1 closed.
STOP_CONDITIONS = ('budget', 'tokens', 'issue_closed')
# `auto` is resolved by the pack's prepare hook into AGENSH_RUN_NETWORK (open or allowlist).
NETWORK_MODES = ('offline', 'open', 'allowlist', 'auto')
MOUNT_TARGET = re.compile(r'^/[A-Za-z0-9._/-]+$')


class PackError(ValueError):
    pass


def parse_duration(value):
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    match = DURATION.match(str(value))
    if not match:
        raise PackError(f'invalid duration {value!r}; use seconds or forms like "45m"')
    return int(match.group(1)) * {'s': 1, 'm': 60, 'h': 3600}[match.group(2)]


@dataclass(frozen=True)
class Pack:
    name: str
    root: Path
    prompts: Path
    hooks: dict
    task_brief: Path
    idle: Path
    idle_delivery: Path
    reminders: tuple
    issue_title: str
    seed_message: str
    network: str = 'offline'
    mounts: tuple = ()
    board_id: str = 'team'
    channel: str = 'team-task'
    # `run`: the prepare hook renders the prompt fragments into $AGENSH_TASK_PROMPTS.
    task_prompts: str = 'pack'
    # The prepare hook supplies a git history that becomes the team's main branch.
    import_history: bool = False
    # Work merges only after the generated CI workflow passes (agensh/quality.py).
    ci_gate: bool = False
    protected_paths: tuple = ()
    # `issues`: claims citing #<n> assign Gitea issues (agensh/backlog.py); `board`: claims only.
    backlog: str = 'board'
    # The sync hook also runs this long before the end of the budget (and before export).
    sync_before_end: int = 1800
    # Resumable packs pause (keeping state) on the token budget or a pause request;
    # others always finalize. finalize_notice warns workers before a timed finalize.
    resumable: bool = False
    stop_when: tuple = ('budget',)
    finalize_notice: int = 0
    # Run the evaluate hook while the services still run (for model calls), before stopping them.
    evaluate_with_services: bool = False
    wake_stagger: int = 30
    # A project may name a human product owner (AGENSH_HUMAN in its profile).
    product_owner: bool = False
    # `inline`: the router adds the latest comment or thread start to each event.
    event_context: str = 'summary'
    # Workers and CI get AGENSH_MODEL_BASE, the egress proxy's unmodified /raw route,
    # for a project's own model calls (metered and budgeted with the team's).
    model_route: bool = False

    def hook(self, name):
        return self.hooks.get(name)


def protected_path_list(value, where):
    # Gitea protected-file globs, joined with ';' for branch protection.
    if not isinstance(value, list) or not all(
            isinstance(p, str) and p.strip() and not any(c in p for c in ';\n"') for p in value):
        raise PackError(f'{where} must be a list of path globs without ";" or quotes')
    return tuple(p.strip() for p in value)


def _known(table, allowed, where):
    unknown = set(table) - set(allowed)
    if unknown:
        raise PackError(f'unknown field(s) in {where}: {", ".join(sorted(unknown))}')


def load_pack(name, root=ROOT):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', name or ''):
        raise PackError(f'invalid pack name {name!r}')
    directory = Path(root) / 'tasks' / name
    path = directory / 'pack.toml'
    if not path.is_file():
        raise PackError(f'{path} not found')
    with path.open('rb') as stream:
        data = tomllib.load(stream)
    _known(data, ('name', 'description', 'hooks', 'messages', 'team', 'environment', 'workspace', 'acceptance',
                  'coordination', 'lifecycle', 'human'),
           path.name)
    if data.get('name') != name:
        raise PackError(f'{path} declares name {data.get("name")!r}, expected {name!r}')

    def inside(relative, kind):
        resolved = (directory / relative).resolve()
        if directory.resolve() not in resolved.parents:
            raise PackError(f'{kind} {relative!r} must stay inside {directory}')
        if not resolved.is_file():
            raise PackError(f'{kind} {relative!r} not found in {directory}')
        return resolved

    hooks_table = data.get('hooks', {})
    _known(hooks_table, HOOKS, '[hooks]')
    hooks = {hook: inside(value, f'hook {hook}') for hook, value in hooks_table.items()}

    messages = data.get('messages', {})
    _known(messages, ('task_brief', 'idle', 'idle_delivery', 'reminders'), '[messages]')
    for key in ('task_brief', 'idle', 'idle_delivery'):
        if key not in messages:
            raise PackError(f'[messages] needs {key}')
    reminders = []
    for index, reminder in enumerate(messages.get('reminders', [])):
        _known(reminder, ('before_end', 'message'), f'[[messages.reminders]] #{index + 1}')
        reminders.append({'before_end_seconds': parse_duration(reminder['before_end']),
                          'message': inside(reminder['message'], 'reminder message')})

    team = data.get('team', {})
    _known(team, ('issue_title', 'seed_message', 'board_id', 'channel', 'wake_stagger', 'event_context'), '[team]')
    event_context = team.get('event_context', 'summary')
    if event_context not in ('summary', 'inline'):
        raise PackError(f'[team] event_context must be "summary" or "inline"; got {event_context!r}')
    wake_stagger = parse_duration(team.get('wake_stagger', 30))
    board_id = team.get('board_id', 'team')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', str(board_id)):
        raise PackError(f'invalid board_id {board_id!r}')
    channel = team.get('channel', 'team-task')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', str(channel)):
        raise PackError(f'invalid channel {channel!r}')

    environment = data.get('environment', {})
    _known(environment, ('network', 'mounts', 'task_prompts', 'model_route'), '[environment]')
    model_route = environment.get('model_route', False)
    if not isinstance(model_route, bool):
        raise PackError('[environment] model_route must be true or false')
    task_prompts = environment.get('task_prompts', 'pack')
    if task_prompts not in ('pack', 'run'):
        raise PackError(f'task_prompts must be "pack" or "run"; got {task_prompts!r}')
    workspace = data.get('workspace', {})
    _known(workspace, ('import_history',), '[workspace]')
    import_history = workspace.get('import_history', False)
    if not isinstance(import_history, bool):
        raise PackError('[workspace] import_history must be true or false')
    acceptance = data.get('acceptance', {})
    _known(acceptance, ('ci_gate', 'protected_paths'), '[acceptance]')
    ci_gate = acceptance.get('ci_gate', False)
    if not isinstance(ci_gate, bool):
        raise PackError('[acceptance] ci_gate must be true or false')
    protected_paths = protected_path_list(acceptance.get('protected_paths', []), '[acceptance] protected_paths')
    if protected_paths and not ci_gate:
        raise PackError('[acceptance] protected_paths needs ci_gate = true')
    human = data.get('human', {})
    _known(human, ('product_owner',), '[human]')
    product_owner = human.get('product_owner', False)
    if not isinstance(product_owner, bool):
        raise PackError('[human] product_owner must be true or false')
    lifecycle = data.get('lifecycle', {})
    _known(lifecycle, ('sync_before_end', 'resumable', 'stop_when', 'finalize_notice', 'evaluate_with_services'),
           '[lifecycle]')
    evaluate_with_services = lifecycle.get('evaluate_with_services', False)
    if not isinstance(evaluate_with_services, bool):
        raise PackError('[lifecycle] evaluate_with_services must be true or false')
    sync_before_end = parse_duration(lifecycle.get('sync_before_end', '30m'))
    resumable = lifecycle.get('resumable', False)
    if not isinstance(resumable, bool):
        raise PackError('[lifecycle] resumable must be true or false')
    stop_when = lifecycle.get('stop_when', ['budget'])
    if not isinstance(stop_when, list) or not set(stop_when) <= set(STOP_CONDITIONS) or 'budget' not in stop_when:
        raise PackError(f'[lifecycle] stop_when must list some of {", ".join(STOP_CONDITIONS)}, including budget')
    finalize_notice = parse_duration(lifecycle.get('finalize_notice', 0))
    if 'sync_before_end' in lifecycle and 'sync' not in hooks:
        raise PackError('[lifecycle] sync_before_end needs a sync hook')
    coordination = data.get('coordination', {})
    _known(coordination, ('backlog',), '[coordination]')
    backlog = coordination.get('backlog', 'board')
    if backlog not in ('board', 'issues'):
        raise PackError(f'[coordination] backlog must be "board" or "issues"; got {backlog!r}')
    network = environment.get('network', 'offline')
    if network not in NETWORK_MODES:
        raise PackError(f'network must be one of {", ".join(NETWORK_MODES)}; got {network!r}')
    mounts = []
    for index, mount in enumerate(environment.get('mounts', [])):
        _known(mount, ('source', 'target', 'read_only'), f'[[environment.mounts]] #{index + 1}')
        source, target = str(mount.get('source', '')), str(mount.get('target', ''))
        if not source or any(c in source for c in '\n\r"'):
            raise PackError(f'mount #{index + 1} needs a single-line source')
        if not MOUNT_TARGET.match(target) or '..' in target.split('/'):
            raise PackError(f'mount #{index + 1} needs an absolute target path; got {target!r}')
        mounts.append({'source': source, 'target': target, 'read_only': bool(mount.get('read_only', True))})
    return Pack(
        name=name, root=directory, prompts=directory / 'prompts', hooks=hooks,
        task_brief=inside(messages['task_brief'], 'message'),
        idle=inside(messages['idle'], 'message'),
        idle_delivery=inside(messages['idle_delivery'], 'message'),
        reminders=tuple(sorted(reminders, key=lambda r: -r['before_end_seconds'])),
        issue_title=team.get('issue_title', '{task}'),
        seed_message=team.get('seed_message', 'Seed workspace ({task})'),
        network=network, mounts=tuple(mounts), board_id=board_id,
        task_prompts=task_prompts, import_history=import_history, channel=channel,
        ci_gate=ci_gate, protected_paths=protected_paths, backlog=backlog, sync_before_end=sync_before_end,
        resumable=resumable, stop_when=tuple(stop_when), finalize_notice=finalize_notice, wake_stagger=wake_stagger,
        evaluate_with_services=evaluate_with_services,
        product_owner=product_owner, event_context=event_context, model_route=model_route,
    )
