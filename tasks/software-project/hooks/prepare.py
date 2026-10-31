#!/usr/bin/env python3
# software-project prepare hook: import the upstream base branch with its history,
# or start an empty repository, then render the project's prompt fragments.
# Writes .seed_git (history pushed as main), prompts/, compose.env, brief_vars.json
# and prepare.json under $AGENSH_TASK_OUT.

import os
import shutil
import sys
import time

from common import context, git, git_url, log, write_json

PLACEHOLDER = '${%s}'


def bullets(commands):
    if not commands:
        return "  - (none declared: use the repository's own test command)"
    return '\n'.join(f'  - `{command}`' for command in commands)


def render(text, values):
    # Only the named placeholders are replaced; other `$` text in templates stays literal.
    for key, value in values.items():
        text = text.replace(PLACEHOLDER % key, value)
    return text


def main():
    task_out, values, project, pack = context()
    clone = task_out / 'upstream'
    shutil.rmtree(clone, ignore_errors=True)
    if project.seed == 'git':
        url, _ = git_url(project.upstream)
        log(f'importing {project.upstream} ({project.base_branch}) with its history')
        git('clone', '--quiet', '--branch', project.base_branch, '--single-branch', url, str(clone))
        source = project.upstream
    else:
        log(f'starting {project.name} as a new, empty repository')
        clone.mkdir(parents=True)
        git('init', '--quiet', '--initial-branch=main', str(clone))
        (clone / 'README.md').write_text(f'# {project.name}\n\n{project.goal}')
        identity = ['-c', 'user.name=Agensh', '-c', 'user.email=agensh@localhost']
        git(*identity, 'add', 'README.md', cwd=clone)
        git(*identity, 'commit', '--quiet', '-m', f'Start {project.name}', cwd=clone)
        source = 'a new, empty repository'
    base_sha = git('rev-parse', 'HEAD', cwd=clone, capture=True)
    (task_out / '.seed_git').write_text(f'{clone}\n')

    network = project.network or pack.network
    template_values = {
        'PROJECT': project.name,
        'GOAL': project.goal,
        'ACCEPTANCE_PR': bullets(project.acceptance_pr),
        'ACCEPTANCE_MAIN': bullets(project.acceptance_main),
        'LANGUAGE': ('Use the language, frameworks and tooling the repository already uses.'
                     if project.seed == 'git' else
                     'This is a new project: use Python unless the goal says otherwise.'),
        'NETWORK': ('The network is open: install dependencies with the project\'s own package '
                    'manager, and pin what you add.' if network == 'open' else
                    'There is no internet access: use only the toolchain already installed in the container.'),
    }
    prompts = task_out / 'prompts'
    prompts.mkdir(mode=0o755, exist_ok=True)
    for name in ('objective', 'focus', 'work_cycle', 'delivery'):
        rendered = render((pack.root / 'templates' / f'{name}.txt').read_text(), template_values)
        (prompts / f'{name}.txt').write_text(rendered)
        (prompts / f'{name}.txt').chmod(0o644)
    (task_out / 'compose.env').write_text(f'AGENSH_TASK_PROMPTS={prompts}\n')
    write_json(task_out / 'brief_vars.json', {'GOAL': project.goal, 'UPSTREAM': source})
    write_json(task_out / 'prepare.json', {
        'run_id': os.environ.get('RUN_ID') or time.strftime('%Y%m%dt%H%M%Sz', time.gmtime()),
        'seed': project.seed, 'upstream': project.upstream, 'base_branch': project.base_branch,
        'base_sha': base_sha, 'network': network,
    })
    log(f'seed ready at {base_sha[:12]}; prompts rendered in {prompts}')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:  # Report any failure as the hook's exit status.
        log(f'FATAL: {error}')
        sys.exit(1)
