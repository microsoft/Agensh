# Shared helpers for the software-project hooks: run context, project and git.

import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request

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


# The host's gh login for GitHub upstreams; workers never hold these credentials.
GH_CREDENTIAL = ['-c', 'credential.helper=', '-c', 'credential.helper=!gh auth git-credential']
IDENTITY = ['-c', 'user.name=Agensh', '-c', 'user.email=agensh@localhost']
# `git clone` options for the host's clones of the project: Git LFS files stay pointer
# files, since LFS objects may be unavailable and the team's Gitea holds none. Kept in
# the clone's config, so git-lfs never runs there and installs no pre-push hook.
NO_LFS = ['-c', 'filter.lfs.process=', '-c', 'filter.lfs.smudge=', '-c', 'filter.lfs.clean=',
          '-c', 'filter.lfs.required=false']


def upstream_credentials(repo):
    import shutil
    _, github_repo = git_url(repo)
    return GH_CREDENTIAL if github_repo and shutil.which('gh') else []


def gitea_api(values, method, path, body=None):
    # Admin call on the team repository through the edge port; (HTTP status, reply).
    credentials = base64.b64encode(f'{values["GITEA_ADMIN_USER"]}:{values["GITEA_ADMIN_PASSWORD"]}'.encode()).decode()
    request = urllib.request.Request(
        f'http://localhost:{values["EDGE_HTTP_PORT"]}/api/v1/repos/{values["ORG_NAME"]}/main{path}', method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': f'Basic {credentials}'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode()
            return response.status, json.loads(text) if text else None
    except urllib.error.HTTPError as error:
        return error.code, None


def git(*arguments, cwd=None, capture=False, env=None):
    result = subprocess.run(['git', *arguments], cwd=cwd, env=env, text=True,
                            capture_output=capture, check=True)
    return result.stdout.strip() if capture else None


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text()) if path.is_file() else default


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


__all__ = ['GH_CREDENTIAL', 'IDENTITY', 'NO_LFS', 'ROOT', 'context', 'git', 'git_url', 'gitea_api', 'log',
           'read_json', 'upstream_credentials', 'write_json']
