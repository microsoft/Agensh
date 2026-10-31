# The software-project pack: project files, profiles, the prepare and export hooks
# against local git repositories, and its Compose and worker-instruction rendering.
# Run: python3 -m unittest discover -s tests/unit

import json
import os
from pathlib import Path
import re
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
                '[team]', 'protected_paths = ["tests/acceptance/**", ".agensh/**"]\ntimeout_minutes = 20\n[team]'))
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
        for key in ('EDGE_HTTP_PORT', 'AGENSH_SUBNET_DEFAULT', 'GITEA_ADMIN_PASSWORD', 'MYSQL_PASSWORD'):
            self.assertEqual(values[key], second[key], key)


class HookTest(unittest.TestCase):
    """Run the prepare and export hooks against local repositories."""

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
        self.assertIn('The network is open', objective)
        self.assertIn('no PR can change them: `.gitea/workflows/**`, `.agensh/**`.',
                      (prompts / 'delivery.txt').read_text())
        for name in ('objective', 'focus', 'work_cycle', 'delivery'):
            self.assertNotRegex((prompts / f'{name}.txt').read_text(), r'\$\{[A-Z_]+\}', name)
        self.assertEqual((self.task_out / 'compose.env').read_text(), f'AGENSH_TASK_PROMPTS={prompts}\n')
        brief = json.loads((self.task_out / 'brief_vars.json').read_text())
        self.assertEqual(brief['UPSTREAM'], str(self.upstream))
        prepare = json.loads((self.task_out / 'prepare.json').read_text())
        self.assertEqual((prepare['base_sha'], prepare['run_id']), (self.base_sha, 'unit'))

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
