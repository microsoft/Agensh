# Load a task pack: tasks/<name>/pack.toml with its prompts and hook executables.
# Only the fields the team driver uses today are accepted; unknown fields fail.

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]
DURATION = re.compile(r'^(\d+)([smh])$')
HOOKS = ('prepare', 'export', 'evaluate')
# `allowlist` and `auto` arrive with the software-project pack (docs/task_pack_design.md).
NETWORK_MODES = ('offline', 'open')
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

    def hook(self, name):
        return self.hooks.get(name)


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
    _known(data, ('name', 'description', 'hooks', 'messages', 'team', 'environment'), path.name)
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
    _known(team, ('issue_title', 'seed_message', 'board_id'), '[team]')
    board_id = team.get('board_id', 'team')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', str(board_id)):
        raise PackError(f'invalid board_id {board_id!r}')

    environment = data.get('environment', {})
    _known(environment, ('network', 'mounts'), '[environment]')
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
    )
