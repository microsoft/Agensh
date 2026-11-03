# Compose generation from the task pack and resource settings, and the open
# network overlay. Run: python3 -m unittest discover -s tests/unit

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
BASE_ENV = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': tempfile.gettempdir(),
            'AGENSH_WORKERS': '2', 'AGENT_HARNESS': 'pi', 'HARNESS_VERSION': '1.4.0'}


def generate(**extra):
    result = subprocess.run([sys.executable, str(ROOT / 'tools/gen_compose_prod.py')], cwd=ROOT,
                            env=dict(BASE_ENV, **extra), capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return result.stdout


class GeneratedComposeTest(unittest.TestCase):
    def test_programbench_defaults(self):
        text = generate()
        self.assertIn('  mem_limit: 64g\n  memswap_limit: 64g\n', text)
        self.assertNotIn('\n  cpus:', text)
        self.assertEqual(text.count('BOARD_IDS: "pbench-top"'), 2)
        self.assertIn('{"pbench-top":[', text)
        self.assertEqual(text.count('      - ${PBENCH_BIN:-/dev/null}:/opt/pbench/executable:ro\n'), 2)
        self.assertEqual(text.count('../tasks/programbench/prompts:/opt/omcgitea/task-prompts:ro'), 2)
        # ProgramBench has no CI gate: no required checks, protected files or job timeout.
        for key in ('AGENSH_REQUIRED_CHECKS', 'AGENSH_PROTECTED_FILES', 'AGENSH_LABELS', '      ACT_JOB_TIMEOUT:'):
            self.assertNotIn(key, text)

    def test_worker_resources(self):
        self.assertIn('  mem_limit: 32g\n  memswap_limit: 32g\n  cpus: 2.5\n',
                      generate(WORKER_MEMORY='32g', WORKER_CPUS='2.5'))
        self.assertRegex(generate(WORKER_CPUS='auto'), r'\n  cpus: [0-9.]+\n')
        with self.assertRaises(AssertionError):
            generate(WORKER_CPUS='-1')

    def test_auto_share(self):
        import gen_compose_prod  # noqa: E402 - imported for its helper only
        self.assertEqual(gen_compose_prod.worker_cpus('auto', 4, host_cpus=10), 2.0)
        self.assertEqual(gen_compose_prod.worker_cpus('auto', 64, host_cpus=8), 0.5)
        self.assertIsNone(gen_compose_prod.worker_cpus('', 4))
        self.assertEqual(gen_compose_prod.worker_cpus('3', 4), 3.0)


@unittest.skipUnless(shutil.which('docker'), 'needs the Docker Compose CLI')
class NetworkOverlayTest(unittest.TestCase):
    def config(self, *files):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory, 'base.yml')
            # The overlay extends these services, so the base must define them.
            base.write_text('services:\n' + ''.join(f'  {name}:\n    image: busybox\n'
                            for name in ('app', 'nginx-edge', 'mysql')))
            command = ['docker', 'compose', '-f', str(base)]
            for name in files:
                command += ['-f', str(ROOT / 'docker' / name)]
            env = dict(os.environ, AGENSH_LLM_UPSTREAM='http://upstream.invalid', AGENSH_PUBLIC_PORT='18080',
                       DATA_ROOT=directory, PROFILE='p')
            result = subprocess.run(command + ['--profile', 'p', 'config', '--format', 'json'],
                                    capture_output=True, text=True, env=env)
        # Docker is present, so a failing config is a real failure, not a skip.
        self.assertEqual(result.returncode, 0, result.stderr.strip()[:300])
        import json
        return json.loads(result.stdout)

    def test_offline_is_internal_and_open_is_not(self):
        offline = self.config('docker_compose.team.yml')
        self.assertTrue(offline['networks']['default'].get('internal'))
        opened = self.config('docker_compose.team.yml', 'network_open.yml')
        self.assertFalse(opened['networks']['default'].get('internal', False))
        self.assertEqual(opened['networks']['default']['ipam'], offline['networks']['default']['ipam'])


if __name__ == '__main__':
    unittest.main()
