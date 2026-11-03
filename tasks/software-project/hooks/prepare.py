#!/usr/bin/env python3
# software-project prepare hook: import the upstream base branch with its history,
# or start an empty repository, then render the project's prompt fragments.
# Writes .seed_git (history pushed as main), prompts/, compose.env, brief_vars.json
# and prepare.json under $AGENSH_TASK_OUT.

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

from common import NO_LFS, ROOT, context, git, git_url, log, write_json

sys.path.insert(0, str(ROOT))
from agensh import quality  # noqa: E402

PLACEHOLDER = '${%s}'
IDENTITY = ['-c', 'user.name=Agensh', '-c', 'user.email=agensh@localhost']
NETWORK_RULES = {
    'open': "The network is open: install dependencies with the project's own package manager, "
            'and pin what you add.',
    'allowlist': 'The network reaches only package registries (PyPI, npm, crates.io, the Go proxy, '
                 'Debian and Ubuntu mirrors) and these project domains: {domains}. Install dependencies '
                 "with the project's own package manager and pin what you add; other sites are refused, "
                 'so do not depend on them.',
    'offline': 'There is no internet access: use only the toolchain already installed in the container.',
}


def bullets(commands):
    if not commands:
        return "  - (none declared: use the repository's own test command)"
    return '\n'.join(f'  - `{command}`' for command in commands)


def render(text, values):
    # Only the named placeholders are replaced; other `$` text in templates stays literal.
    for key, value in values.items():
        text = text.replace(PLACEHOLDER % key, value)
    return text


def github_visibility(repo):
    # True for private, False for public, None when it cannot be told.
    if shutil.which('gh'):
        result = subprocess.run(['gh', 'api', f'repos/{repo}', '--jq', '.private'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip() in ('true', 'false'):
            return result.stdout.strip() == 'true'
    try:
        with urllib.request.urlopen(f'https://api.github.com/repos/{repo}', timeout=20) as response:
            return bool(json.load(response).get('private'))
    except (OSError, ValueError):
        return None  # Private repositories answer 404 without credentials.


def resolve_network(project, pack):
    mode = project.network or pack.network
    if mode != 'auto':
        return mode, f'{mode} (set in the {"project file" if project.network else "pack"})'
    if not project.upstream:
        return 'open', 'auto: a new project without an upstream repository'
    _, github_repo = git_url(project.upstream)
    private = github_visibility(github_repo) if github_repo else None
    if private is False:
        return 'open', f'auto: {github_repo} is public'
    reason = (f'{github_repo} is private' if private else
              f'the visibility of {project.upstream} is unknown, so it is treated as private')
    return 'allowlist', f'auto: {reason}'


def add_workflow(clone, project, pack, network):
    # The team's CI (and, with a product owner, CODEOWNERS for the protected paths)
    # runs from this commit on; export removes these files again before delivery.
    files = {quality.WORKFLOW_PATH: quality.render_workflow(
        project.acceptance_pr, project.acceptance_main, project.ci_timeout_minutes,
        proxy=quality.ALLOWLIST_PROXY if network == 'allowlist' else None, model_route=pack.model_route)}
    if project.human:
        # CODEOWNERS covers itself, so no PR can drop the owner's review.
        files[quality.CODEOWNERS_PATH] = quality.render_codeowners(
            list(dict.fromkeys(pack.protected_paths + project.protected_paths + (quality.CODEOWNERS_PATH,))),
            project.human)
    for name, text in files.items():
        path = clone / name
        if path.exists():
            raise RuntimeError(f'{name} already exists upstream; Agensh adds its own for the run')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        git(*IDENTITY, 'add', name, cwd=clone)
    git(*IDENTITY, 'commit', '--quiet', '-m', 'Add the Agensh team workflow', cwd=clone)
    return list(files)


def snapshot(clone, project, base_sha):
    # The team starts from the (sanitized) tree alone: its history could bring back
    # whatever the sanitize script removed, such as held-out evaluation data.
    if project.sanitize:
        log(f'sanitizing the imported tree with {project.sanitize}')
        subprocess.run([project.sanitize, str(clone)], cwd=clone, check=True)
    git('checkout', '--quiet', '--orphan', 'agensh-snapshot', cwd=clone)
    git('add', '--all', cwd=clone)
    git(*IDENTITY, 'commit', '--quiet', '--allow-empty', '-m',
        f'Snapshot of {project.upstream} {project.base_branch} at {base_sha[:12]} (history not imported)', cwd=clone)
    return git('rev-parse', 'HEAD', cwd=clone, capture=True)


def protected_paths(pack, project):
    paths = list(dict.fromkeys(pack.protected_paths + project.protected_paths))
    return ', '.join(f'`{p}`' for p in paths) if paths else '(none)'


def main():
    task_out, values, project, pack = context()
    clone = task_out / 'upstream'
    shutil.rmtree(clone, ignore_errors=True)
    if project.seed == 'git':
        url, _ = git_url(project.upstream)
        log(f'importing {project.upstream} ({project.base_branch})'
            + (' as a snapshot without history' if project.history == 'snapshot' else ' with its history'))
        git('clone', *NO_LFS, '--quiet', '--branch', project.base_branch, '--single-branch', url, str(clone))
        source = project.upstream
    else:
        log(f'starting {project.name} as a new, empty repository')
        clone.mkdir(parents=True)
        git('init', '--quiet', '--initial-branch=main', str(clone))
        (clone / 'README.md').write_text(f'# {project.name}\n\n{project.goal}')
        git(*IDENTITY, 'add', 'README.md', cwd=clone)
        git(*IDENTITY, 'commit', '--quiet', '-m', f'Start {project.name}', cwd=clone)
        source = 'a new, empty repository'
    base_sha = git('rev-parse', 'HEAD', cwd=clone, capture=True)
    team_base = snapshot(clone, project, base_sha) if project.history == 'snapshot' and project.seed == 'git' else base_sha
    network, network_reason = resolve_network(project, pack)
    log(f'network: {network_reason}')
    agensh_files = add_workflow(clone, project, pack, network) if pack.ci_gate else []
    (task_out / '.seed_git').write_text(f'{clone}\n')

    template_values = {
        'PROJECT': project.name,
        'GOAL': project.goal,
        'ACCEPTANCE_PR': bullets(project.acceptance_pr),
        'ACCEPTANCE_MAIN': bullets(project.acceptance_main),
        'LANGUAGE': ('Use the language, frameworks and tooling the repository already uses.'
                     if project.seed == 'git' else
                     'This is a new project: use Python unless the goal says otherwise.'),
        'NETWORK': NETWORK_RULES[network].format(domains=', '.join(project.allow_domains) or 'none'),
        'HUMAN_RULE': (
            f'**Product owner**: `{project.human}` owns the goal. When a requirement is ambiguous, ask in '
            f'the task channel and mention `@{project.human}`, then continue with other work instead of '
            "waiting; their answers, comments and issues reach you as urgent events. Do not ask about "
            'things the goal, the repository or your peers can settle.' if project.human else
            '**Fully autonomous**: there is no human to ask during this run. Settle open\n'
            '   questions yourselves from the goal and the repository, decide, and ship.'),
        'MODEL_RULE': (
            '\n7. Model calls made by the project\'s own code (experiments, evaluation scripts) go to '
            '`$AGENSH_MODEL_BASE`, which forwards them unchanged with the credential added; use it as the '
            'API base URL and send no key. These calls count against the team\'s token budget.'
            if pack.model_route else ''),
        'REVIEW_RULE': (
            ' PRs that touch ' + ', '.join(f'`{p}`' for p in project.review_paths) + ' merge only after a peer '
            'approves them (`agensh/review`): ask one by direct message, and review peers\' PRs promptly when asked.'
            if project.review_paths else ''),
        'PROTECTED_RULE': (
            f'Changes to these protected paths need the approval of `{project.human}`: '
            f'{protected_paths(pack, project)}. Avoid them; when one must change, open the PR, say why '
            f'in it, mention `@{project.human}` in the channel, and keep working on something else.'
            if project.human else
            f'These paths are protected and no PR can change them: {protected_paths(pack, project)}. '
            'If one needs to change, open an issue that\nexplains why instead.'),
    }
    prompts = task_out / 'prompts'
    prompts.mkdir(mode=0o755, exist_ok=True)
    for name in ('objective', 'focus', 'work_cycle', 'delivery'):
        rendered = render((pack.root / 'templates' / f'{name}.txt').read_text(), template_values)
        (prompts / f'{name}.txt').write_text(rendered)
        (prompts / f'{name}.txt').chmod(0o644)
    (task_out / 'compose.env').write_text(f'AGENSH_TASK_PROMPTS={prompts}\nAGENSH_RUN_NETWORK={network}\n'
                                          f'AGENSH_ALLOW_DOMAINS={",".join(project.allow_domains)}\n')
    write_json(task_out / 'brief_vars.json', {'GOAL': project.goal, 'UPSTREAM': source})
    write_json(task_out / 'prepare.json', {
        'run_id': os.environ.get('RUN_ID') or time.strftime('%Y%m%dt%H%M%Sz', time.gmtime()),
        'seed': project.seed, 'upstream': project.upstream, 'base_branch': project.base_branch,
        'base_sha': base_sha, 'history': project.history, 'team_base': team_base,
        'network': network, 'network_reason': network_reason,
        'allow_domains': list(project.allow_domains), 'agensh_files': agensh_files, 'human': project.human,
    })
    log(f'seed ready at {base_sha[:12]}; prompts rendered in {prompts}')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:  # Report any failure as the hook's exit status.
        log(f'FATAL: {error}')
        sys.exit(1)
