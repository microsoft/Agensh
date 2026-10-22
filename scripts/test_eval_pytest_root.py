#!/usr/bin/env python3
# Run one official test from each Pandoc branch against a supplied submission.
# Assert JUnit identities with the evaluator's pytest-root option appended by
# the Docker shim. Requires real cached test blobs and the v6 cleanroom image.

import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[1]
PARSER = argparse.ArgumentParser(description='Check real ProgramBench test identities when a submission has pyproject.toml.')
PARSER.add_argument('--submission', type=Path, required=True)
PARSER.add_argument('--blob-dir', type=Path, required=True)
PARSER.add_argument('--image', default='programbench/jgm_1776_pandoc.5caad90:task_cleanroom_v6')
OPTIONS = PARSER.parse_args()


class PytestRootIntegration(unittest.TestCase):
    def test_real_tests_keep_registry_names_in_both_branches(self):
        root = REPO / 'out' / ('eval-pytest-root-test-' + str(time.time_ns()))
        root.mkdir(parents=True)
        cases = [
            # Branches invoke pytest from different working directories.
            ('08afe9ff1778', '/workspace', 'eval/tests/test_pandoc.py::test_version_output',
             'eval.tests.test_pandoc.test_version_output'),
            ('ea7a9f0674dc', '/workspace/eval', 'tests/test_cli_options.py::test_list_highlight_styles',
             'tests.test_cli_options.test_list_highlight_styles'),
        ]
        observed = {}
        for branch, cwd, selection, expected in cases:
            report = root / branch
            report.mkdir()
            script = ('set -eu\ncd /workspace\n'
                      'tar -xzf /input/submission.tar.gz\n./compile.sh\n'
                      'tar -xzf /input/tests.tar.gz\n'
                      'python3 -m pip install -q beautifulsoup4\n'
                      f'cd {cwd}\n'
                      f'python3 -m pytest -q {selection} --junitxml=/report/results.xml\n')
            command = [str(REPO / 'scripts/pbench-docker-sudo.sh'), 'run', '--rm',
                       '--name', 'omcgitea-eval-root-' + branch + '-' + str(time.time_ns()),
                       '--network', 'bridge', '--cgroup-parent', 'pbench.slice',
                       '--env', 'PYTEST_ADDOPTS=--max-worker-restart=4',
                       '--mount', f'type=bind,src={OPTIONS.submission.resolve()},dst=/input/submission.tar.gz,readonly',
                       '--mount', f'type=bind,src={(OPTIONS.blob_dir / "tests" / (branch + ".tar.gz")).resolve()},dst=/input/tests.tar.gz,readonly',
                       '--mount', f'type=bind,src={report},dst=/report',
                       '--entrypoint', 'bash', OPTIONS.image, '-lc', script]
            env = os.environ | {'PBENCH_EVAL_PYTEST_ADDOPTS': '--rootdir=.'}
            with (report / 'pytest.log').open('w') as output:
                result = subprocess.run(command, env=env, stdout=output, stderr=subprocess.STDOUT, timeout=120)
            self.assertEqual(result.returncode, 0, (report / 'pytest.log').read_text()[-5000:])
            cases_xml = list(ET.parse(report / 'results.xml').getroot().iter('testcase'))
            self.assertEqual(len(cases_xml), 1)
            actual = cases_xml[0].get('classname') + '.' + cases_xml[0].get('name')
            self.assertEqual(actual, expected, 'Submission metadata changed the official test identity')
            observed[branch] = actual
        (root / 'result.json').write_text(json.dumps(observed, indent=2) + '\n')
        print(json.dumps({'real_pytest': True, 'real_test_blobs': True, 'identities': observed, 'reports': str(root)}, indent=2))


if __name__ == '__main__':
    unittest.main(argv=[__file__])
