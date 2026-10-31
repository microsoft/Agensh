#!/usr/bin/env python3
# software-project export hook: deliver the team's main. With an upstream, push it to
# the delivery branch and, for GitHub repositories, open a pull request (never merge).
# Without one, write a git bundle. AGENSH_DELIVERY=off keeps everything local.
# Records $AGENSH_TASK_OUT/delivery.json.

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from common import GH_CREDENTIAL, IDENTITY, context, git, git_url, log, read_json, write_json

WORKFLOW_COMMITS = '^(Add|Remove) the Agensh team workflow$'


def remove_workflow(checkout, path):
    # The team workflow ran Agensh's CI only; upstream should not receive it.
    if not path or not (checkout / path).exists():
        return False
    git('rm', '--quiet', path, cwd=checkout)
    git(*IDENTITY, 'commit', '--quiet', '-m', 'Remove the Agensh team workflow', cwd=checkout)
    return True


def summary(checkout, base_sha, upstream_sha=None):
    # Against the latest upstream merged into main, as the GitHub PR shows it.
    upstream_sha = upstream_sha or base_sha
    known = all(subprocess.run(['git', 'cat-file', '-e', f'{sha}^{{commit}}'], cwd=checkout).returncode == 0
                for sha in (base_sha, upstream_sha))
    if not known:
        return None, ''
    # The team's commits, without upstream's or the workflow bookkeeping that cancels out.
    commits = int(git('rev-list', '--count', '--invert-grep', '-E', f'--grep={WORKFLOW_COMMITS}',
                      '--grep=^Merge upstream ', 'HEAD', '--not', base_sha, upstream_sha,
                      cwd=checkout, capture=True))
    stat = git('diff', '--stat', f'{upstream_sha}..HEAD', cwd=checkout, capture=True)
    return commits, stat


def synced_upstream(task_out, checkout):
    # The newest upstream head that main contains, from the sync hook's record.
    for entry in reversed((read_json(task_out / 'sync.json') or {}).get('history', [])):
        sha = entry.get('upstream_sha')
        if sha and subprocess.run(['git', 'merge-base', '--is-ancestor', sha, 'HEAD'], cwd=checkout,
                                  capture_output=True).returncode == 0:
            return sha
    return None


def sync_summary(task_out):
    last = (read_json(task_out / 'sync.json') or {}).get('last')
    if not last:
        return 'Upstream was not synced during the run.'
    if last['result'] == 'conflict':
        files = ', '.join(f'`{f}`' for f in last.get('files', []))
        return (f'**Upstream `{last["upstream_sha"][:12]}` conflicts with this branch** in {files}; the team '
                'did not resolve it before the end. Resolve it when reviewing.')
    return f'Upstream `{last["upstream_sha"][:12]}`: {last["result"]}.'


def network_summary(prepare):
    # Reviewers see what the team could reach while it wrote this change.
    network = prepare.get('network', 'unknown')
    text = f'The team worked with network mode `{network}` ({prepare.get("network_reason", "")}).'
    if network == 'allowlist':
        domains = prepare.get('allow_domains') or []
        added = ', '.join(f'`{d}`' for d in domains) if domains else 'none'
        text += f' Package registries plus project domains: {added}.'
    return text


def pr_body(project, prepare, commits, stat, run_id, task_out):
    checks = '\n'.join(f'- `{c}`' for c in project.acceptance_main) or '- (none declared)'
    return (f'Delivered by an Agensh team run (`{run_id}`) for **{project.name}**. Review it like any '
            f'other contribution before merging.\n\n## Goal\n\n{project.goal}\n'
            f'## Changes\n\n{commits} team commit(s) on top of `{prepare["base_branch"]}` at '
            f'`{prepare["base_sha"][:12]}`.\n\n```\n{stat or "(no file changes)"}\n```\n\n'
            f'## Acceptance on main\n\n{checks}\n\nResults are recorded in the run\'s `acceptance.json`.\n'
            f'\n## Upstream\n\n{sync_summary(task_out)}\n'
            f'\n## Network\n\n{network_summary(prepare)}\n')


def main():
    task_out, _values, project, _pack = context()
    prepare = read_json(task_out / 'prepare.json')
    if prepare is None:
        raise RuntimeError('prepare.json is missing; the prepare hook did not complete')
    checkout = task_out / '_deliver'
    shutil.rmtree(checkout, ignore_errors=True)
    git('clone', '--quiet', '--branch', 'main', os.environ['AGENSH_GITEA_URL'], str(checkout))
    team_head = git('rev-parse', 'HEAD', cwd=checkout, capture=True)
    remove_workflow(checkout, prepare.get('workflow'))
    head = git('rev-parse', 'HEAD', cwd=checkout, capture=True)
    upstream_sha = synced_upstream(task_out, checkout)
    commits, stat = summary(checkout, prepare['base_sha'], upstream_sha)
    run_id = prepare['run_id']
    delivery = {'head': head, 'team_head': team_head, 'base_sha': prepare['base_sha'], 'commits': commits,
                'run_id': run_id, 'upstream_sha': upstream_sha or prepare['base_sha'],
                'sync': ((read_json(task_out / 'sync.json') or {}).get('last') or {}).get('result')}
    if os.environ.get('AGENSH_DELIVERY', 'on') == 'off':
        delivery['mode'] = 'local (AGENSH_DELIVERY=off)'
    elif project.upstream:
        url, github_repo = git_url(project.upstream)
        branch = project.delivery_branch.format(run_id=run_id)
        credentials = GH_CREDENTIAL if github_repo and shutil.which('gh') else []  # host gh login
        log(f'pushing main ({head[:12]}) to {project.upstream} as {branch}')
        git(*credentials, 'push', '--quiet', url, f'HEAD:refs/heads/{branch}', cwd=checkout)
        delivery.update(mode='branch', upstream=project.upstream, branch=branch)
        if github_repo and shutil.which('gh') and commits:
            with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False) as body:
                body.write(pr_body(project, prepare, commits, stat, run_id, task_out))
            created = subprocess.run(['gh', 'pr', 'create', '--repo', github_repo, '--base', prepare['base_branch'],
                                      '--head', branch, '--title', f'Agensh: {project.name} ({run_id})',
                                      '--body-file', body.name], capture_output=True, text=True)
            Path(body.name).unlink(missing_ok=True)
            if created.returncode != 0:
                raise RuntimeError(f'gh pr create failed: {created.stderr.strip()[:300]}')
            delivery.update(mode='pull_request', pull_request=created.stdout.strip())
            log(f'opened {created.stdout.strip()}')
        elif github_repo and not commits:
            log('no new commits on main; pushed the branch without opening a pull request')
    else:
        bundle = task_out / 'delivery.bundle'
        git('bundle', 'create', '--quiet', str(bundle), 'HEAD', 'main', cwd=checkout)
        delivery.update(mode='bundle', bundle=str(bundle))
        log(f'no upstream configured; wrote {bundle}')
    write_json(task_out / 'delivery.json', delivery)
    log(f'delivery: {delivery["mode"]}, {commits} new commit(s)')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:  # Report any failure as the hook's exit status.
        log(f'ERROR: delivery failed: {error}')
        sys.exit(1)
