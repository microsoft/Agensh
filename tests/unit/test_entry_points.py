# Every command-line entry point must at least import and print its usage.
# Run: python3 -m unittest discover -s tests/unit

from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
COMMANDS = [
    [sys.executable, '-m', 'agensh.team_run', '--help'],
    [sys.executable, 'scripts/team_status.py', '--help'],
    [sys.executable, 'tools/render_snapshot.py', '--help'],
    [sys.executable, 'tasks/programbench/tools/submission.py', '--help'],
    [sys.executable, 'tasks/programbench/scripts/acp_driver.py', '--help'],
    [sys.executable, 'tasks/programbench/scripts/launch_single_agent.py', '--help'],
]


class EntryPointTest(unittest.TestCase):
    def test_usage(self):
        for command in COMMANDS:
            with self.subTest(command=command[1:3]):
                result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr[-500:])
                self.assertIn('usage', result.stdout.lower())


if __name__ == '__main__':
    unittest.main()
