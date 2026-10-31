# Profile generation for listed and unlisted tasks.
# Run: python3 -m unittest discover -s tests/unit

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def generate(env_dir, task, **extra):
    env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': env_dir, 'ENV_DIR': env_dir,
           'TASKS': task, 'WORKERS': '2', 'LLM_UPSTREAM': 'https://gateway.invalid',
           'LLM_UPSTREAM_TOKEN': 'unit-test', **extra}
    result = subprocess.run(['bash', str(ROOT / 'tasks/programbench/scripts/gen_env.sh'), '--agent-harness', 'pi',
                             '--harness-version', '1.4.0'], cwd=ROOT, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return result.stderr


def read(path):
    return dict(line.split('=', 1) for line in Path(path).read_text().splitlines() if '=' in line)


class ProfileGenerationTest(unittest.TestCase):
    def test_listed_task_keeps_its_fixed_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            generate(directory, 'jgm__pandoc.5caad90')
            values = read(Path(directory, '.env.programbench-pandoc'))
        self.assertEqual(values['EDGE_HTTP_PORT'], '22050')
        self.assertEqual(values['AGENSH_SUBNET_DEFAULT'], '10.216.15.0/24')
        self.assertNotIn('AGENSH_PACK', values)

    def test_unlisted_task_is_allocated_and_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            stderr = generate(directory, 'acme__widget.0000000', PORT_BASE='31000', SUBNET_OCTET='233',
                              AGENSH_PACK='programbench', WORKER_CPUS='auto')
            self.assertIn('not in TASK_TABLE', stderr)
            path = Path(directory, '.env.programbench-widget')
            first = read(path)
            self.assertGreaterEqual(int(first['EDGE_HTTP_PORT']), 31000 + 20 * 10)
            self.assertEqual(int(first['EDGE_MM_PORT']), int(first['EDGE_HTTP_PORT']) + 2)
            self.assertTrue(first['AGENSH_SUBNET_DEFAULT'].startswith('10.233.'))
            self.assertEqual(first['WORKER_CPUS'], 'auto')
            self.assertNotIn('AGENSH_PACK', first)
            generate(directory, 'acme__widget.0000000', PORT_BASE='31000', SUBNET_OCTET='233')
            second = read(path)
        for key in ('EDGE_HTTP_PORT', 'EDGE_MM_PORT', 'AGENSH_SUBNET_DEFAULT', 'AGENSH_SUBNET_EGRESS',
                    'AGENSH_SUBNET_EDGE', 'GITEA_ADMIN_PASSWORD'):
            self.assertEqual(first[key], second[key], key)

    def test_unlisted_tasks_do_not_collide(self):
        with tempfile.TemporaryDirectory() as directory:
            generate(directory, 'acme__one.0000000', PORT_BASE='31000', SUBNET_OCTET='233')
            generate(directory, 'acme__two.0000000', PORT_BASE='31000', SUBNET_OCTET='233')
            one = read(Path(directory, '.env.programbench-one'))
            two = read(Path(directory, '.env.programbench-two'))
        self.assertNotEqual(one['EDGE_HTTP_PORT'], two['EDGE_HTTP_PORT'])
        self.assertNotEqual(one['AGENSH_SUBNET_DEFAULT'], two['AGENSH_SUBNET_DEFAULT'])


if __name__ == '__main__':
    unittest.main()
