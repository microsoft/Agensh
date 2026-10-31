# The CI merge gate: the generated workflow, the main-health timing rules and the
# per-PR statuses. Run: python3 -m unittest discover -s tests/unit

from pathlib import Path
import sys
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agensh import quality  # noqa: E402
from agensh.pack import PackError, load_pack  # noqa: E402


class WorkflowTest(unittest.TestCase):
    def test_jobs_and_checks(self):
        text = quality.render_workflow(['python3 -m unittest -q', 'ruff check "src"'], ['make test'], 20)
        workflow = yaml.safe_load(text)
        self.assertEqual(workflow['name'], 'agensh')
        # PyYAML reads the bare `on` key as True.
        self.assertEqual(workflow[True], {'pull_request': None, 'push': {'branches': ['main']}})
        pr, main = workflow['jobs']['pr'], workflow['jobs']['main']
        self.assertEqual((pr['if'], main['if']), ("gitea.event_name == 'pull_request'", "gitea.event_name == 'push'"))
        self.assertEqual(pr['timeout-minutes'], 20)
        self.assertEqual([s['run'] for s in pr['steps'][1:]], ['python3 -m unittest -q', 'ruff check "src"'])
        self.assertEqual([s['run'] for s in main['steps'][1:]], ['make test'])
        # Only run: steps, so offline teams fetch no actions.
        for job in (pr, main):
            self.assertTrue(all('uses' not in step for step in job['steps']))
            self.assertIn('http://gitea:3000/${{ gitea.repository }}.git', job['steps'][0]['run'])

    def test_no_commands(self):
        workflow = yaml.safe_load(quality.render_workflow([], []))
        self.assertEqual(len(workflow['jobs']['pr']['steps']), 2)


class HealthGateTest(unittest.TestCase):
    ordinary = {'title': 'Add a flag', 'labels': []}
    labeled = {'title': 'Fix tests', 'labels': [{'name': 'fix-main'}]}
    titled = {'title': '[fix-main] restore greet', 'labels': []}

    def test_green_main_passes_every_pr(self):
        gate = quality.HealthGate()
        self.assertEqual(gate.observe('success', 'a', 0), [])
        self.assertEqual(gate.observe(None, 'b', 5), [])
        self.assertEqual(gate.pr_status(self.ordinary)[0], 'success')

    def test_broken_main_timeline(self):
        gate = quality.HealthGate()
        self.assertEqual(gate.observe('failure', 'bad', 100), ['broken'])
        self.assertEqual((gate.broken_sha, gate.red_since), ('bad', 100))
        self.assertEqual(gate.pr_status(self.ordinary)[0], 'pending')
        self.assertEqual(gate.pr_status(self.labeled)[0], 'success')
        self.assertEqual(gate.pr_status(self.titled)[0], 'success')
        # A pending run on a newer head keeps main red; later failures do not re-alert.
        self.assertEqual(gate.observe('pending', 'newer', 200), [])
        self.assertEqual(gate.observe('failure', 'newer', 300), [])
        self.assertEqual(gate.observe('error', 'newer', 100 + quality.TEAM_ALERT_AFTER), ['alert_team'])
        self.assertEqual(gate.observe('failure', 'newer', 100 + quality.TEAM_ALERT_AFTER + 60), [])
        self.assertEqual(gate.observe('failure', 'newer', 100 + quality.LIFT_AFTER), ['lift'])
        self.assertEqual(gate.pr_status(self.ordinary)[0], 'success')
        self.assertEqual(gate.observe('failure', 'newer', 100 + quality.LIFT_AFTER + 60), [])
        self.assertEqual(gate.observe('success', 'good', 100 + quality.LIFT_AFTER + 120), ['recovered'])
        self.assertFalse(gate.red or gate.lifted or gate.team_alerted)
        self.assertEqual([h['action'] for h in gate.history], ['broken', 'alert_team', 'lift', 'recovered'])
        # A new failure starts the timeline again.
        self.assertEqual(gate.observe('failure', 'bad2', 10_000), ['broken'])
        self.assertEqual(gate.pr_status(self.ordinary)[0], 'pending')

    def test_check_state_uses_the_latest_status(self):
        statuses = [
            {'id': 1, 'context': quality.MAIN_CHECK, 'status': 'failure', 'updated_at': '2026-10-31T01:00:00Z'},
            {'id': 2, 'context': quality.MAIN_CHECK, 'status': 'success', 'updated_at': '2026-10-31T02:00:00Z'},
            {'id': 3, 'context': quality.HEALTH_CHECK, 'status': 'pending', 'updated_at': '2026-10-31T03:00:00Z'},
        ]
        self.assertEqual(quality.check_state(statuses, quality.MAIN_CHECK), 'success')
        self.assertIsNone(quality.check_state(statuses, quality.PR_CHECK))
        self.assertIsNone(quality.check_state(None, quality.PR_CHECK))


class PackGateTest(unittest.TestCase):
    def test_packs(self):
        software = load_pack('software-project')
        self.assertTrue(software.ci_gate)
        self.assertEqual(software.protected_paths, ('.gitea/workflows/**', '.agensh/**'))
        self.assertFalse(load_pack('programbench').ci_gate)

    def test_rejections(self):
        import tempfile
        cases = {'ci_gate = "yes"\n': 'ci_gate must be', 'protected_paths = ["a"]\n': 'needs ci_gate',
                 'ci_gate = true\nprotected_paths = "a"\n': 'list of path globs'}
        for body, message in cases.items():
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                pack = Path(directory, 'tasks/demo')
                (pack / 'prompts').mkdir(parents=True)
                for name in ('brief', 'idle'):
                    (pack / f'prompts/{name}.txt').write_text('x\n')
                (pack / 'pack.toml').write_text(
                    'name = "demo"\n[messages]\ntask_brief = "prompts/brief.txt"\nidle = "prompts/idle.txt"\n'
                    'idle_delivery = "prompts/idle.txt"\n[acceptance]\n' + body)
                with self.assertRaises(PackError) as caught:
                    load_pack('demo', root=directory)
                self.assertIn(message, str(caught.exception))


if __name__ == '__main__':
    unittest.main()


class LifecycleSettingsTest(unittest.TestCase):
    def test_packs(self):
        software, programbench = load_pack('software-project'), load_pack('programbench')
        self.assertEqual((software.resumable, software.stop_when, software.finalize_notice, software.wake_stagger),
                         (True, ('budget', 'tokens', 'issue_closed'), 900, 5))
        self.assertEqual((programbench.resumable, programbench.stop_when, programbench.finalize_notice,
                          programbench.wake_stagger), (False, ('budget',), 0, 30))

    def test_rejections(self):
        import tempfile
        cases = {'[lifecycle]\nresumable = "yes"\n': 'resumable must be',
                 '[lifecycle]\nstop_when = ["tokens"]\n': 'including budget',
                 '[lifecycle]\nstop_when = ["budget", "moon"]\n': 'stop_when must list',
                 '[lifecycle]\nsync_before_end = "10m"\n': 'needs a sync hook'}
        for body, message in cases.items():
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                pack = Path(directory, 'tasks/demo')
                (pack / 'prompts').mkdir(parents=True)
                (pack / 'prompts/x.txt').write_text('x\n')
                (pack / 'pack.toml').write_text(
                    'name = "demo"\n[messages]\ntask_brief = "prompts/x.txt"\nidle = "prompts/x.txt"\n'
                    'idle_delivery = "prompts/x.txt"\n' + body)
                with self.assertRaises(PackError) as caught:
                    load_pack('demo', root=directory)
                self.assertIn(message, str(caught.exception))


class ProtectedPathTest(unittest.TestCase):
    def test_globs(self):
        self.assertTrue(quality.matches_any('.gitea/workflows/agensh.yml', ['.gitea/workflows/**']))
        self.assertTrue(quality.matches_any('.agensh/a/b.toml', ['.agensh/**']))
        self.assertFalse(quality.matches_any('src/.agensh/x', ['.agensh/**']))
        self.assertTrue(quality.matches_any('tests/acceptance/test_x.py', ['tests/acceptance/*.py']))
        self.assertFalse(quality.matches_any('tests/acceptance/sub/test_x.py', ['tests/acceptance/*.py']))
        self.assertFalse(quality.matches_any('agensh/x', ['.agensh/**']))

    def test_codeowners(self):
        text = quality.render_codeowners(['.gitea/workflows/**', '.gitea/CODEOWNERS'], 'owner')
        self.assertIn('^\\.gitea/workflows/.*$ @owner\n', text)
        self.assertIn('^\\.gitea/CODEOWNERS$ @owner\n', text)


class ReviewTest(unittest.TestCase):
    paths = ['src/core/**']

    def review(self, user, state, at, **extra):
        return {'user': {'login': user}, 'state': state, 'submitted_at': at, **extra}

    def test_paths_decide(self):
        self.assertEqual(quality.review_status(['README.md'], [], 'team-worker1', self.paths)[0], 'success')
        state, text = quality.review_status(['src/core/a.py', 'README.md'], [], 'team-worker1', self.paths)
        self.assertEqual((state, text), ('pending', 'needs one peer approval: touches src/core/a.py'))

    def test_peer_approval(self):
        files = ['src/core/a.py']
        own = [self.review('team-worker1', 'APPROVED', '1')]
        self.assertEqual(quality.review_status(files, own, 'team-worker1', self.paths)[0], 'pending')
        peer = [self.review('team-worker2', 'APPROVED', '1')]
        self.assertEqual(quality.review_status(files, peer, 'team-worker1', self.paths),
                         ('success', 'approved by team-worker2'))
        withdrawn = peer + [self.review('team-worker2', 'REQUEST_CHANGES', '2')]
        self.assertEqual(quality.review_status(files, withdrawn, 'team-worker1', self.paths)[0], 'pending')
        stale = [self.review('team-worker2', 'APPROVED', '1', stale=True)]
        self.assertEqual(quality.review_status(files, stale, 'team-worker1', self.paths)[0], 'pending')
        comment = [self.review('team-worker3', 'COMMENT', '3')]
        self.assertEqual(quality.review_status(files, peer + comment, 'team-worker1', self.paths)[0], 'success')
