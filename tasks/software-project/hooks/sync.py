#!/usr/bin/env python3
# software-project sync hook: bring the upstream base branch into the team's main.
# The driver runs it before the end of the budget (AGENSH_SYNC_PHASE=scheduled) and
# again before export (final). The upstream head is always pushed to the team as
# upstream/<base_branch>. A clean merge is pushed to main as the administrator; a
# conflict is never forced: an issue asks the team to resolve it in a normal PR.
# Records $AGENSH_TASK_OUT/sync.json.

import os
import shutil
import subprocess
import sys
import time

from common import IDENTITY, NO_LFS, context, git, gitea_api, log, read_json, upstream_credentials, write_json
from common import git_url


def push_main(checkout, values):
    # Upstream may change protected files; the administrator lifts the protection
    # for this one push and restores it.
    pushed = subprocess.run(['git', 'push', '--quiet', 'origin', 'HEAD:refs/heads/main'], cwd=checkout,
                            capture_output=True, text=True)
    if pushed.returncode == 0:
        return True
    if 'protected' not in pushed.stderr.lower():
        log(f'push to main refused: {pushed.stderr.strip()[-300:]}')
        return False
    status, protection = gitea_api(values, 'GET', '/branch_protections/main')
    patterns = (protection or {}).get('protected_file_patterns', '') if status == 200 else ''
    gitea_api(values, 'PATCH', '/branch_protections/main', {'protected_file_patterns': ''})
    try:
        return subprocess.run(['git', 'push', '--quiet', 'origin', 'HEAD:refs/heads/main'],
                              cwd=checkout).returncode == 0
    finally:
        restored, _ = gitea_api(values, 'PATCH', '/branch_protections/main', {'protected_file_patterns': patterns})
        if restored != 200:
            log(f'ERROR: could not restore protected files on main ({patterns}); HTTP {restored}')


def open_conflict_issue(values, project, upstream_sha, files):
    branch = f'upstream/{project.base_branch}'
    listing = '\n'.join(f'- `{f}`' for f in files) or '- (git reported no file names)'
    body = (f'`{project.base_branch}` on {project.upstream} moved to `{upstream_sha[:12]}`, and merging it '
            f'into `main` conflicts in:\n\n{listing}\n\nThe upstream head is on the branch `{branch}`. Merge it '
            f'into a branch from the latest `main`, resolve the conflicts, run the checks, and merge the PR '
            f'as usual. Delivery includes upstream only once this is merged.\n')
    status, reply = gitea_api(values, 'POST', '/issues', {'title': f'Merge upstream {project.base_branch} '
                                                                   f'({upstream_sha[:12]}): conflicts', 'body': body})
    return reply.get('number') if 200 <= status < 300 and isinstance(reply, dict) else None


def sync_once(task_out, values, project, record):
    url, _ = git_url(project.upstream)
    checkout = task_out / '_sync'
    shutil.rmtree(checkout, ignore_errors=True)
    git('clone', *NO_LFS, '--quiet', '--branch', 'main', os.environ['AGENSH_GITEA_URL'], str(checkout))
    git(*upstream_credentials(project.upstream), 'fetch', '--quiet', url, project.base_branch, cwd=checkout)
    upstream_sha = git('rev-parse', 'FETCH_HEAD', cwd=checkout, capture=True)
    git('push', '--quiet', '--force', 'origin', f'{upstream_sha}:refs/heads/upstream/{project.base_branch}',
        cwd=checkout)
    entry = {'upstream_sha': upstream_sha}
    if subprocess.run(['git', 'merge-base', '--is-ancestor', upstream_sha, 'HEAD'], cwd=checkout).returncode == 0:
        return dict(entry, result='up-to-date')
    merged = subprocess.run(['git', *IDENTITY, 'merge', '--no-ff', '--quiet', '-m',
                             f'Merge upstream {project.base_branch} at {upstream_sha[:12]}', upstream_sha],
                            cwd=checkout, capture_output=True, text=True)
    if merged.returncode != 0:
        files = git('diff', '--name-only', '--diff-filter=U', cwd=checkout, capture=True).split()
        subprocess.run(['git', 'merge', '--abort'], cwd=checkout)
        known = [h for h in record['history'] if h.get('upstream_sha') == upstream_sha and h.get('issue')]
        issue = known[0]['issue'] if known else open_conflict_issue(values, project, upstream_sha, files)
        return dict(entry, result='conflict', files=files, issue=issue)
    if not push_main(checkout, values):
        return dict(entry, result='push-refused')
    return dict(entry, result='merged', main=git('rev-parse', 'HEAD', cwd=checkout, capture=True))


def main():
    task_out, values, project, _pack = context()
    phase = os.environ.get('AGENSH_SYNC_PHASE', 'manual')
    if not project.upstream:
        log('no upstream repository; nothing to sync')
        return
    if project.history == 'snapshot':
        # Upstream commits could bring back what the sanitize script removed.
        log('snapshot import: upstream is not synced into the team repository')
        return
    path = task_out / 'sync.json'
    record = read_json(path, {'history': []})
    for attempt in range(1, 4):
        # main may move between the clone and the push; merge again on a refused push.
        entry = sync_once(task_out, values, project, record)
        if entry['result'] != 'push-refused':
            break
        log(f'main moved during the sync (attempt {attempt}/3); merging again')
        time.sleep(5)
    entry.update(at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), phase=phase)
    record['history'].append(entry)
    record['last'] = entry
    write_json(path, record)
    issue = f' (issue #{entry["issue"]})' if entry.get('issue') else ''
    log(f'sync ({phase}): upstream {entry["upstream_sha"][:12]} {entry["result"]}{issue}')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:  # Report any failure as the hook's exit status.
        log(f'ERROR: upstream sync failed: {error}')
        sys.exit(1)
