# Shared helpers for the software-project hooks: run context, project and git.

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(os.environ['AGENSH_ROOT'])
sys.path.insert(0, str(ROOT))

from agensh.pack import load_pack  # noqa: E402
from agensh.project import git_url, load_project  # noqa: E402


def log(message):
    print(f'[software-project] {message}', file=sys.stderr, flush=True)


def profile_values():
    values = {}
    for line in Path(os.environ['AGENSH_ENV_FILE']).read_text().splitlines():
        key, sep, value = line.partition('=')
        if sep and not key.startswith('#'):
            values[key] = value
    return values


def context():
    values = profile_values()
    project = load_project(values['AGENSH_PROJECT_FILE'])
    return Path(os.environ['AGENSH_TASK_OUT']), values, project, load_pack(project.pack)


def git(*arguments, cwd=None, capture=False, env=None):
    result = subprocess.run(['git', *arguments], cwd=cwd, env=env, text=True,
                            capture_output=capture, check=True)
    return result.stdout.strip() if capture else None


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text()) if path.is_file() else default


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


__all__ = ['ROOT', 'context', 'git', 'git_url', 'log', 'read_json', 'write_json']
