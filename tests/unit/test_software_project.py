# The software-project pack: project files, profiles, the prepare and export hooks
# against local git repositories, and its Compose and worker-instruction rendering.
# Run: python3 -m unittest discover -s tests/unit

import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agensh.project import ProjectError, git_url, load_project, write_profile  # noqa: E402

PROJECT = '''pack = "software-project"
name = "widget"
goal = "Add a --json flag to the widget CLI."
[upstream]
repo = "{upstream}"
[acceptance]
pr = ["python3 -m unittest -q"]
main = ["python3 -m unittest"]
[team]
workers = 2
'''
IDENTITY = ['-c', 'user.name=Test', '-c', 'user.email=test@localhost']


def git(*arguments, cwd=None):
    return subprocess.run(['git', *IDENTITY, *arguments], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout.strip()


def make_upstream(directory):
    work = Path(directory, 'work')
    git('init', '-q', '--initial-branch=main', str(work))
    (work / 'widget.py').write_text('print("widget")\n')
    git('add', '.', cwd=work)
    git('commit', '-qm', 'Initial widget', cwd=work)
    bare = Path(directory, 'upstream.git')
    git('clone', '-q', '--bare', str(work), str(bare))
    return bare, git('rev-parse', 'HEAD', cwd=work)


class Args:
    agent_harness, harness_version, harness_config, workers = 'pi', '1.4.0', None, None


class ProjectFileTest(unittest.TestCase):
    def write(self, text):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        path = Path(self.directory.name, 'project.toml')
        path.write_text(text)
        return path

    def test_loads_defaults(self):
        project = load_project(self.write(PROJECT.format(upstream='github.com/acme/widget')))
        self.assertEqual(project.profile, 'software-project-widget')
        self.assertEqual(project.seed, 'git')
        self.assertEqual(project.base_branch, 'main')
        self.assertEqual(project.delivery_branch, 'agensh/{run_id}')
        self.assertEqual(project.acceptance_main, ('python3 -m unittest',))
        self.assertEqual(project.base_image_ref, 'python:3.12-bookworm')
        self.assertEqual(project.goal, 'Add a --json flag to the widget CLI.\n')

    def test_human_and_planning(self):
        project = load_project(self.write(PROJECT.format(upstream='u') + '[human]\nmode = "optional"\n'
                                          'digest = "30m"\n[coordination]\nplanning = true\n'))
        self.assertEqual((project.human, project.digest_seconds, project.planning, project.planning_timeout),
                         ('owner', 1800, True, 2700))
        fixed = load_project(self.write(PROJECT.format(upstream='u') + '[budget]\nfixed_length = true\n'))
        self.assertTrue(fixed.fixed_length)
        self.assertEqual(load_project(self.write(PROJECT.format(upstream='u'))).human, '')
        project = load_project(self.write(PROJECT.format(upstream='u').replace('workers = 2', 'workers = 2\nmodels = { "2" = "mini" }')
                                          + '[coordination]\nreview_paths = ["src/core/**"]\n'))
        self.assertEqual((project.models, project.review_paths), ({2: 'mini'}, ('src/core/**',)))

    def test_goal_file_and_main_default_to_pr_checks(self):
        path = self.write('pack = "software-project"\nname = "n"\ngoal_file = "goal.md"\n'
                          '[workspace]\nseed = "empty"\n[acceptance]\npr = ["make test"]\n')
        Path(path.parent, 'goal.md').write_text('Build it.\n')
        project = load_project(path)
        self.assertEqual((project.goal, project.acceptance_main, project.upstream), ('Build it.\n', ('make test',), ''))

    def test_rejections(self):
        cases = {
            PROJECT.replace('software-project"', 'programbench"', 1): 'pack must be one of',
            PROJECT.replace('name = "widget"', 'name = "Widget"'): 'name must be',
            PROJECT.replace('repo = "{upstream}"', ''): 'repo is required',
            PROJECT + 'goal_file = "x"\n': 'unknown field(s) in [team]',
            'goal_file = "x"\n' + PROJECT: 'exactly one of goal or goal_file',
            PROJECT.replace('workers = 2', 'workers = 0'): 'workers must be',
            PROJECT.replace('pr = ["python3 -m unittest -q"]', 'pr = "make"'): 'list of single-line commands',
            PROJECT + '[budget]\nhours = -1\n': 'hours must be',
            PROJECT.replace('[upstream]', '[upstream]\ndelivery_branch = "agensh"'): 'must contain {run_id}',
            PROJECT + '[environment]\nbase_image = "default-cobol"\n': 'unknown default base image',
            PROJECT.replace('[team]', 'protected_paths = ["a;b"]\n[team]'): 'list of path globs',
            PROJECT.replace('[team]', 'timeout_minutes = 0\n[team]'): 'timeout_minutes must be',
            PROJECT + '[budget]\nmax_model_tokens = -5\n': 'max_model_tokens must be',
            PROJECT + '[human]\nmode = "always"\n': 'mode must be',
            PROJECT + '[human]\nmode = "optional"\nusername = "team-worker1"\n': 'not used by the team',
            PROJECT + '[coordination]\nplanning = "yes"\n': 'planning must be',
            PROJECT + '[budget]\nfixed_length = "yes"\n': 'fixed_length must be',
            PROJECT.replace('workers = 2', 'workers = 2\nmodels = { "3" = "m" }'): '[team.models]',
            PROJECT + '[coordination]\nreview_paths = ["a;b"]\n': 'list of path globs',
            PROJECT.replace('workers = 2', 'workers = 1') + '[coordination]\nreview_paths = ["src/**"]\n': 'at least two workers',
        }
        for text, message in cases.items():
            with self.subTest(message=message):
                with self.assertRaises(ProjectError) as caught:
                    load_project(self.write(text.replace('{upstream}', 'u')))
                self.assertIn(message, str(caught.exception))

    def test_git_url(self):
        self.assertEqual(git_url('github.com/acme/widget'), ('https://github.com/acme/widget.git', 'acme/widget'))
        self.assertEqual(git_url('https://github.com/acme/widget.git'), ('https://github.com/acme/widget.git', 'acme/widget'))
        self.assertEqual(git_url('/srv/repos/widget.git'), ('/srv/repos/widget.git', None))
        self.assertEqual(git_url('git@example.com:acme/w.git'), ('git@example.com:acme/w.git', None))


class ProfileTest(unittest.TestCase):
    def test_profile_keys_and_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            project_file = Path(directory, 'project.toml')
            project_file.write_text(PROJECT.format(upstream='/nowhere').replace(
                '[team]', 'protected_paths = ["tests/acceptance/**", ".agensh/**"]\ntimeout_minutes = 20\n[team]')
                + '[budget]\nmax_model_tokens = 5000\n')
            env = {'LLM_UPSTREAM': 'https://gateway.invalid', 'LLM_UPSTREAM_TOKEN': 'unit-test'}
            with unittest.mock.patch.dict(os.environ, env):
                first = write_profile(load_project(project_file), Args(), directory)
                values = dict(line.split('=', 1) for line in first.read_text().splitlines())
                again = write_profile(load_project(project_file), Args(), directory)
                second = dict(line.split('=', 1) for line in again.read_text().splitlines())
        self.assertEqual(first.name, '.env.software-project-widget')
        self.assertEqual(values['AGENSH_PACK'], 'software-project')
        self.assertEqual(values['AGENSH_PROJECT_FILE'], str(project_file.resolve()))
        self.assertEqual(values['AGENSH_WORKERS'], '2')
        self.assertEqual(values['ORG_NAME'], 'team')
        self.assertEqual(values['AGENT_IMAGE'], 'omcgitea-agent-default-python-pi:agensh')
        self.assertTrue(values['AGENSH_SUBNET_DEFAULT'].startswith('10.217.'))
        self.assertNotIn('PBENCH_CLEANROOM_TAG', values)
        self.assertEqual(values['AGENSH_PROTECTED_FILES'], '.gitea/workflows/**;.agensh/**;tests/acceptance/**')
        self.assertEqual(values['ACT_JOB_TIMEOUT'], '20m')
        self.assertEqual(values['AGENSH_MAX_MODEL_TOKENS'], '5000')
        self.assertNotIn('AGENSH_FIXED_LENGTH', values)
        for key in ('EDGE_HTTP_PORT', 'AGENSH_SUBNET_DEFAULT', 'GITEA_ADMIN_PASSWORD', 'MYSQL_PASSWORD'):
            self.assertEqual(values[key], second[key], key)


class HookBase(unittest.TestCase):
    """Local upstream and team repositories for running the pack's hooks."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        base = Path(self.directory.name)
        self.upstream, self.base_sha = make_upstream(base)
        self.project_file = base / 'project.toml'
        self.project_file.write_text(PROJECT.format(upstream=self.upstream))
        self.env_file = base / '.env.software-project-widget'
        self.env_file.write_text(f'AGENSH_PROJECT_FILE={self.project_file}\nAGENT_IMAGE=unused\n')
        self.task_out = base / 'out' / 'widget'
        self.task_out.mkdir(parents=True)

    def hook(self, name, **extra):
        env = dict(os.environ, AGENSH_ROOT=str(ROOT), AGENSH_ENV_FILE=str(self.env_file),
                   AGENSH_TASK_OUT=str(self.task_out), RUN_ID='unit', **extra)
        return subprocess.run([sys.executable, str(ROOT / f'tasks/software-project/hooks/{name}.py')],
                              env=env, capture_output=True, text=True)


    def team_main(self):
        # Stand in for the team's Gitea repository: the imported history plus one merge.
        clone = Path((self.task_out / '.seed_git').read_text().strip())
        gitea = Path(self.directory.name, 'gitea.git')
        git('clone', '-q', '--bare', str(clone), str(gitea))
        work = Path(self.directory.name, 'team')
        git('clone', '-q', str(gitea), str(work))
        (work / 'json_flag.py').write_text('FLAG = "--json"\n')
        git('add', '.', cwd=work)
        git('commit', '-qm', 'Add --json flag', cwd=work)
        git('push', '-q', 'origin', 'HEAD:main', cwd=work)
        return gitea

    def upstream_commit(self, name, text):
        work = Path(self.directory.name, 'upstream-work')
        if not work.exists():
            git('clone', '-q', str(self.upstream), str(work))
        (work / name).write_text(text)
        git('add', '.', cwd=work)
        git('commit', '-qm', f'Upstream changes {name}', cwd=work)
        git('push', '-q', 'origin', 'HEAD:main', cwd=work)
        return git('rev-parse', 'HEAD', cwd=work)


class HookTest(HookBase):
    """Run the prepare and export hooks against local repositories."""

    def test_prepare_imports_history_and_renders_prompts(self):
        result = self.hook('prepare')
        self.assertEqual(result.returncode, 0, result.stderr)
        clone = Path((self.task_out / '.seed_git').read_text().strip())
        # The team workflow is one commit on top of the imported base.
        self.assertEqual(git('rev-parse', 'HEAD~1', cwd=clone), self.base_sha)
        self.assertEqual(git('show', '--name-only', '--format=%s', 'HEAD', cwd=clone).splitlines(),
                         ['Add the Agensh team workflow', '', '.gitea/workflows/agensh.yml'])
        self.assertIn('python3 -m unittest -q', (clone / '.gitea/workflows/agensh.yml').read_text())
        prompts = self.task_out / 'prompts'
        objective = (prompts / 'objective.txt').read_text()
        self.assertIn('Add a --json flag to the widget CLI.', objective)
        self.assertIn('  - `python3 -m unittest -q`', objective)
        self.assertIn('Use the language, frameworks and tooling the repository already uses.', objective)
        # A local upstream's visibility is unknown, so `auto` keeps it on the allowlist.
        self.assertIn('The network reaches only package registries', objective)
        self.assertIn('no PR can change them: `.gitea/workflows/**`, `.agensh/**`.',
                      (prompts / 'delivery.txt').read_text())
        for name in ('objective', 'focus', 'work_cycle', 'delivery'):
            self.assertNotRegex((prompts / f'{name}.txt').read_text(), r'\$\{[A-Z_]+\}', name)
        self.assertEqual((self.task_out / 'compose.env').read_text(),
                         f'AGENSH_TASK_PROMPTS={prompts}\nAGENSH_RUN_NETWORK=allowlist\nAGENSH_ALLOW_DOMAINS=\n')
        self.assertIn('HTTPS_PROXY: http://egress-filter:3128', (clone / '.gitea/workflows/agensh.yml').read_text())
        brief = json.loads((self.task_out / 'brief_vars.json').read_text())
        self.assertEqual(brief['UPSTREAM'], str(self.upstream))
        prepare = json.loads((self.task_out / 'prepare.json').read_text())
        self.assertEqual((prepare['base_sha'], prepare['run_id']), (self.base_sha, 'unit'))

    def test_prepare_with_a_product_owner(self):
        self.project_file.write_text(PROJECT.format(upstream=self.upstream) + '[human]\nmode = "optional"\n')
        self.assertEqual(self.hook('prepare').returncode, 0)
        prepare = json.loads((self.task_out / 'prepare.json').read_text())
        self.assertEqual((prepare['human'], prepare['agensh_files']),
                         ('owner', ['.gitea/workflows/agensh.yml', '.gitea/CODEOWNERS']))
        clone = Path((self.task_out / '.seed_git').read_text().strip())
        self.assertIn('^\\.agensh/.*$ @owner', (clone / '.gitea/CODEOWNERS').read_text())
        prompts = self.task_out / 'prompts'
        self.assertIn('**Product owner**: `owner` owns the goal.', (prompts / 'objective.txt').read_text())
        self.assertIn('need the approval of `owner`', (prompts / 'delivery.txt').read_text())

    def test_export_pushes_delivery_branch(self):
        self.assertEqual(self.hook('prepare').returncode, 0)
        gitea = self.team_main()
        result = self.hook('export', AGENSH_GITEA_URL=str(gitea))
        self.assertEqual(result.returncode, 0, result.stderr)
        delivery = json.loads((self.task_out / 'delivery.json').read_text())
        self.assertEqual((delivery['mode'], delivery['branch'], delivery['commits']), ('branch', 'agensh/unit', 1))
        log = git('log', '--format=%s', 'agensh/unit', cwd=self.upstream).splitlines()
        self.assertEqual(log, ['Remove the Agensh team workflow', 'Add --json flag', 'Add the Agensh team workflow',
                               'Initial widget'])
        # Upstream receives the team's change without the workflow.
        self.assertEqual(git('diff', '--name-only', self.base_sha, 'agensh/unit', cwd=self.upstream), 'json_flag.py')
        self.assertNotEqual(delivery['team_head'], delivery['head'])

    def test_export_without_upstream_writes_bundle_and_can_stay_local(self):
        self.project_file.write_text(PROJECT.replace('repo = "{upstream}"\n', '') + '[workspace]\nseed = "empty"\n')
        self.assertEqual(self.hook('prepare').returncode, 0)
        gitea = self.team_main()
        self.assertEqual(self.hook('export', AGENSH_GITEA_URL=str(gitea)).returncode, 0)
        delivery = json.loads((self.task_out / 'delivery.json').read_text())
        self.assertEqual(delivery['mode'], 'bundle')
        self.assertTrue(Path(delivery['bundle']).is_file())
        self.project_file.write_text(PROJECT.format(upstream=self.upstream))
        self.assertEqual(self.hook('export', AGENSH_GITEA_URL=str(gitea), AGENSH_DELIVERY='off').returncode, 0)
        self.assertEqual(json.loads((self.task_out / 'delivery.json').read_text())['mode'], 'local (AGENSH_DELIVERY=off)')
        self.assertNotIn('agensh/unit', git('branch', '--list', cwd=self.upstream))


class NetworkTest(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault('AGENSH_ROOT', str(ROOT))
        sys.path.insert(0, str(ROOT / 'tasks/software-project/hooks'))
        import prepare
        self.prepare = prepare
        self.pack = __import__('agensh.pack', fromlist=['load_pack']).load_pack('software-project')
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def project(self, text):
        path = Path(self.directory.name, 'project.toml')
        path.write_text(text)
        return load_project(path)

    def resolve(self, text, private=None):
        with unittest.mock.patch.object(self.prepare, 'github_visibility', return_value=private) as visibility:
            result = self.prepare.resolve_network(self.project(text), self.pack)
        return result[0], visibility.call_args

    def test_auto(self):
        github = PROJECT.format(upstream='github.com/acme/widget')
        self.assertEqual(self.resolve(github, private=False)[0], 'open')
        self.assertEqual(self.resolve(github, private=True)[0], 'allowlist')
        self.assertEqual(self.resolve(github, private=None)[0], 'allowlist')
        self.assertEqual(self.resolve(github)[1], unittest.mock.call('acme/widget'))
        local, call = self.resolve(PROJECT.format(upstream='/srv/repos/widget.git'))
        self.assertEqual((local, call), ('allowlist', None))
        empty = 'pack = "software-project"\nname = "n"\ngoal = "g"\n[workspace]\nseed = "empty"\n'
        self.assertEqual(self.resolve(empty)[0], 'open')

    def test_project_choice_wins(self):
        text = PROJECT.format(upstream='github.com/acme/widget') + '[environment]\nnetwork = "offline"\n'
        self.assertEqual(self.resolve(text, private=False)[0], 'offline')

    def test_allow_domains(self):
        text = PROJECT.format(upstream='u') + '[environment]\nallow_domains = ["PyPI.Internal.example"]\n'
        self.assertEqual(self.project(text).allow_domains, ('pypi.internal.example',))
        for bad in ('["*.example.com"]', '["http://x.example"]', '"x.example"'):
            with self.subTest(bad=bad), self.assertRaises(ProjectError):
                self.project(PROJECT.format(upstream='u') + f'[environment]\nallow_domains = {bad}\n')


class SnapshotTest(HookBase):
    """history = "snapshot": a sanitized tree without history, replayed onto upstream at delivery."""

    def setUp(self):
        super().setUp()
        work = Path(self.directory.name, 'work')
        (work / 'holdout.json').write_text('{"secret": true}\n')
        git('add', '.', cwd=work)
        git('commit', '-qm', 'Add held-out data', cwd=work)
        git('push', '-q', str(self.upstream), 'HEAD:main', cwd=work)
        self.base_sha = git('rev-parse', 'HEAD', cwd=work)
        sanitize = Path(self.directory.name, 'private', 'sanitize.sh')
        sanitize.parent.mkdir()
        sanitize.write_text('#!/bin/sh\nrm -f "$1/holdout.json"\n')
        sanitize.chmod(0o755)
        self.project_file.write_text(PROJECT.format(upstream=self.upstream)
                                     + f'[workspace]\nhistory = "snapshot"\nsanitize = "{sanitize}"\n')

    def test_snapshot_hides_history_and_delivery_replays(self):
        result = self.hook('prepare')
        self.assertEqual(result.returncode, 0, result.stderr)
        clone = Path((self.task_out / '.seed_git').read_text().strip())
        prepare = json.loads((self.task_out / 'prepare.json').read_text())
        # What the team gets: the snapshot and the workflow commit, without the held-out file.
        self.assertEqual(git('log', '--format=%s', 'HEAD', cwd=clone).splitlines(),
                         ['Add the Agensh team workflow', f'Snapshot of {self.upstream} main at {self.base_sha[:12]} '
                          '(history not imported)'])
        self.assertFalse((clone / 'holdout.json').exists())
        self.assertEqual((prepare['history'], prepare['base_sha']), ('snapshot', self.base_sha))
        # Stand in for push_history, which pushes only HEAD.
        gitea = Path(self.directory.name, 'gitea.git')
        git('init', '-q', '--bare', '--initial-branch=main', str(gitea))
        git('push', '-q', str(gitea), 'HEAD:refs/heads/main', cwd=clone)
        self.assertEqual(git('rev-list', '--count', 'main', cwd=gitea), '2')
        team = Path(self.directory.name, 'team')
        git('clone', '-q', str(gitea), str(team))
        (team / 'json_flag.py').write_text('FLAG = "--json"\n')
        git('add', '.', cwd=team)
        git('commit', '-qm', 'Add --json flag', cwd=team)
        git('push', '-q', 'origin', 'HEAD:main', cwd=team)
        result = self.hook('export', AGENSH_GITEA_URL=str(gitea))
        self.assertEqual(result.returncode, 0, result.stderr)
        delivery = json.loads((self.task_out / 'delivery.json').read_text())
        self.assertEqual((delivery['mode'], delivery['commits']), ('branch', 1))
        # Upstream gets its own history plus one commit with the team's change and nothing else.
        self.assertEqual(git('rev-parse', 'agensh/unit~1', cwd=self.upstream), self.base_sha)
        self.assertEqual(git('diff', '--name-only', self.base_sha, 'agensh/unit', cwd=self.upstream), 'json_flag.py')
        message = git('log', '-1', '--format=%B', 'agensh/unit', cwd=self.upstream)
        self.assertIn('Agensh team changes (unit)', message)
        self.assertIn('- Add --json flag', message)
        self.assertNotIn('workflow', message)
        # Upstream would reintroduce held-out data, so the sync hook leaves snapshots alone.
        result = self.hook('sync', AGENSH_GITEA_URL=str(gitea))
        self.assertIn('snapshot import', result.stderr)
        self.assertFalse((self.task_out / 'sync.json').exists())

    def test_sanitize_needs_a_snapshot(self):
        text = self.project_file.read_text().replace('history = "snapshot"\n', '')
        self.project_file.write_text(text)
        with self.assertRaises(ProjectError) as caught:
            load_project(self.project_file)
        self.assertIn('stay in the imported history', str(caught.exception))
        self.project_file.write_text(PROJECT.format(upstream=self.upstream).replace(
            '[acceptance]', '[acceptance]\nprivate_dir = "nowhere"'))
        with self.assertRaises(ProjectError):
            load_project(self.project_file)


class FakeGitea:
    """Records issues the sync hook opens; answers like Gitea's issue API."""

    def __init__(self):
        import http.server
        import threading
        self.issues = []
        fake = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                fake.issues.append((self.path, body))
                reply = json.dumps({'number': 40 + len(fake.issues)}).encode()
                self.send_response(201)
                self.send_header('Content-Length', str(len(reply)))
                self.end_headers()
                self.wfile.write(reply)

            def log_message(self, *_):
                pass

        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.port = self.server.server_address[1]


class SyncTest(HookBase):
    """The sync hook against local upstream and team repositories."""

    def setUp(self):
        super().setUp()
        self.gitea = FakeGitea()
        self.addCleanup(self.gitea.server.shutdown)
        self.env_file.write_text(self.env_file.read_text() + f'GITEA_ADMIN_USER=chairman\nGITEA_ADMIN_PASSWORD=x\n'
                                 f'EDGE_HTTP_PORT={self.gitea.port}\nORG_NAME=team\n')
        self.assertEqual(self.hook('prepare').returncode, 0)
        self.team = self.team_main()

    def sync(self):
        result = self.hook('sync', AGENSH_GITEA_URL=str(self.team), AGENSH_SYNC_PHASE='final')
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads((self.task_out / 'sync.json').read_text())

    def test_clean_merge_then_delivery(self):
        self.assertEqual(self.sync()['last']['result'], 'up-to-date')
        upstream_sha = self.upstream_commit('upstream_note.txt', 'from upstream\n')
        record = self.sync()
        self.assertEqual((record['last']['result'], record['last']['phase']), ('merged', 'final'))
        self.assertEqual(git('rev-parse', 'upstream/main', cwd=self.team), upstream_sha)
        git('merge-base', '--is-ancestor', upstream_sha, 'main', cwd=self.team)
        self.assertEqual(self.hook('export', AGENSH_GITEA_URL=str(self.team)).returncode, 0)
        delivery = json.loads((self.task_out / 'delivery.json').read_text())
        # Only the team's commit counts; upstream's and the bookkeeping commits do not.
        self.assertEqual((delivery['commits'], delivery['upstream_sha'], delivery['sync']), (1, upstream_sha, 'merged'))
        self.assertEqual(git('diff', '--name-only', upstream_sha, 'agensh/unit', cwd=self.upstream), 'json_flag.py')

    def test_conflict_opens_one_issue(self):
        work = Path(self.directory.name, 'team')
        (work / 'widget.py').write_text('print("team widget")\n')
        git('commit', '-qam', 'Team changes widget', cwd=work)
        git('push', '-q', 'origin', 'HEAD:main', cwd=work)
        upstream_sha = self.upstream_commit('widget.py', 'print("upstream widget")\n')
        record = self.sync()
        self.assertEqual((record['last']['result'], record['last']['files'], record['last']['issue']),
                         ('conflict', ['widget.py'], 41))
        path, body = self.gitea.issues[0]
        self.assertEqual(path, '/api/v1/repos/team/main/issues')
        self.assertIn('`upstream/main`', body['body'])
        self.assertEqual(git('rev-parse', 'upstream/main', cwd=self.team), upstream_sha)
        # main is untouched, and the same conflict does not open a second issue.
        self.assertEqual(git('log', '-1', '--format=%s', 'main', cwd=self.team), 'Team changes widget')
        self.assertEqual(self.sync()['last']['issue'], 41)
        self.assertEqual(len(self.gitea.issues), 1)


LFS_POINTER = 'version https://git-lfs.github.com/spec/v1\noid sha256:{}\nsize 1048576\n'
# A host's git-lfs that cannot fetch the objects: the filter fails on every LFS file.
FAILING_LFS = '[filter "lfs"]\n\tprocess = false\n\tsmudge = false\n\tclean = false\n\trequired = true\n'


class LfsTest(HookBase):
    """The hooks pass Git LFS pointers through when their objects exist nowhere."""

    def setUp(self):
        super().setUp()
        # Test repositories are written without LFS; the hooks run with the failing filter.
        isolated = unittest.mock.patch.dict(os.environ, {'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull})
        isolated.start()
        self.addCleanup(isolated.stop)
        config = Path(self.directory.name, 'lfs.gitconfig')
        config.write_text(FAILING_LFS)
        self.lfs = {'GIT_CONFIG_GLOBAL': str(config)}

    def test_pointers_pass_through_prepare_sync_and_export(self):
        self.upstream_commit('.gitattributes', '*.bin filter=lfs diff=lfs merge=lfs -text\n')
        self.upstream_commit('model.bin', LFS_POINTER.format('a' * 64))
        result = self.hook('prepare', **self.lfs)
        self.assertEqual(result.returncode, 0, result.stderr)
        clone = Path((self.task_out / '.seed_git').read_text().strip())
        self.assertEqual((clone / 'model.bin').read_text(), LFS_POINTER.format('a' * 64))
        team = self.team_main()
        # The sync's merge checks out a new LFS file in the clone it made.
        self.upstream_commit('weights.bin', LFS_POINTER.format('b' * 64))
        result = self.hook('sync', AGENSH_GITEA_URL=str(team), AGENSH_SYNC_PHASE='final', **self.lfs)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.task_out / 'sync.json').read_text())['last']['result'], 'merged')
        result = self.hook('export', AGENSH_GITEA_URL=str(team), **self.lfs)
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ('model.bin', 'weights.bin'):
            self.assertEqual(git('rev-parse', f'agensh/unit:{name}', cwd=self.upstream),
                             git('rev-parse', f'main:{name}', cwd=self.upstream), name)


# `docker run ... -v CHECKOUT:/work -w /work IMAGE -lc ...` as a host process in the
# checkout, as a container user with its own HOME who does not own the checkout.
FAKE_DOCKER = '''import os, subprocess, sys, tempfile
arguments = sys.argv[1:]
checkout = arguments[arguments.index('-v') + 1].rsplit(':', 1)[0]
command = arguments[arguments.index('-w') + 3:]
with tempfile.TemporaryDirectory() as home:
    env = {'PATH': os.environ['PATH'], 'HOME': home, 'GIT_TEST_ASSUME_DIFFERENT_OWNER': '1'}
    sys.exit(subprocess.run(['bash', *command], cwd=checkout, env=env).returncode)
'''


class EvaluateTest(HookBase):
    """The evaluate hook runs acceptance.main in the worker image on the delivered checkout."""

    def test_git_works_on_a_checkout_the_container_does_not_own(self):
        self.project_file.write_text(PROJECT.format(upstream=self.upstream).replace(
            'main = ["python3 -m unittest"]', 'main = ["git log -1 --format=%H"]'))
        self.assertEqual(self.hook('prepare').returncode, 0)
        self.assertEqual(self.hook('export', AGENSH_GITEA_URL=str(self.team_main())).returncode, 0)
        docker = Path(self.directory.name, 'fake_docker.py')
        docker.write_text(FAKE_DOCKER)
        result = self.hook('evaluate', DOCKER=shlex.join([sys.executable, str(docker)]))
        self.assertEqual(result.returncode, 0, result.stderr)
        acceptance = json.loads((self.task_out / 'acceptance.json').read_text())
        self.assertTrue(acceptance['all_passed'], acceptance['results'])
        self.assertEqual(acceptance['results'][0]['output_tail'].strip(),
                         json.loads((self.task_out / 'delivery.json').read_text())['head'])


class RenderingTest(unittest.TestCase):
    def test_compose_and_agents_md(self):
        env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': tempfile.gettempdir(),
               'AGENSH_WORKERS': '2', 'AGENT_HARNESS': 'pi', 'HARNESS_VERSION': '1.4.0',
               'AGENSH_PACK': 'software-project'}
        text = subprocess.run([sys.executable, str(ROOT / 'tools/gen_compose_prod.py')], cwd=ROOT, env=env,
                              capture_output=True, text=True, check=True).stdout
        self.assertIn('${AGENSH_TASK_PROMPTS:?AGENSH_TASK_PROMPTS is set by the prepare hook}:/opt/omcgitea/task-prompts:ro', text)
        self.assertIn('REPO_AUTO_INIT: "false"', text)
        self.assertIn('BOOTSTRAP_CODEOWNERS: "false"', text)
        self.assertIn('BOARD_IDS: "team"', text)
        self.assertIn('TASK_CHANNEL: "team-task"', text)
        self.assertIn('AGENSH_REQUIRED_CHECKS: "agensh / pr (pull_request);agensh/main-health"', text)
        self.assertIn('ACT_JOB_TIMEOUT: "${ACT_JOB_TIMEOUT:-15m}"', text)
        self.assertNotIn('/opt/pbench/executable', text)

        with tempfile.TemporaryDirectory() as directory:
            hook_test = HookTest('test_prepare_imports_history_and_renders_prompts')
            hook_test.setUp()
            self.addCleanup(hook_test.directory.cleanup)
            self.assertEqual(hook_test.hook('prepare').returncode, 0)
            rendered = subprocess.run(['bash', str(ROOT / 'agent/render_agents.sh'), str(ROOT / 'prompts/agents.txt'),
                                       str(hook_test.task_out / 'prompts')], capture_output=True, text=True, check=True,
                                      env={'PATH': env['PATH'], 'AGENT_NAME': 'team-worker1', 'GITEA_ORG': 'team',
                                           'AGENSH_WORKERS': '2', 'TASK_CHANNEL': 'team-task'}).stdout
        self.assertIn('channel `team-task`', rendered)
        self.assertIn('Always focus on the goal in issue #1;', rendered)
        self.assertIn('# ⚙️ Current task: widget', rendered)
        self.assertNotIn('/opt/pbench', rendered)
        self.assertEqual(re.findall(r'\$\{[A-Z_]+\}', rendered), [])


if __name__ == '__main__':
    import unittest.mock  # noqa: F401
    unittest.main()
