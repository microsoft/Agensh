# Task pack loading: the ProgramBench pack and malformed pack files.
# Run: python3 -m unittest discover -s tests/unit

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agensh.pack import PackError, load_pack, parse_duration  # noqa: E402

MINIMAL = '''name = "demo"
[messages]
task_brief = "prompts/brief.txt"
idle = "prompts/idle.txt"
idle_delivery = "prompts/idle.txt"
'''


class ProgramBenchPackTest(unittest.TestCase):
    def test_loads_hooks_messages_and_team_text(self):
        pack = load_pack('programbench')
        self.assertEqual(set(pack.hooks), {'prepare', 'export', 'evaluate'})
        for hook in pack.hooks.values():
            self.assertTrue(hook.is_file(), hook)
        self.assertEqual(pack.task_brief, ROOT / 'tasks/programbench/prompts/task_brief.txt')
        self.assertEqual([r['before_end_seconds'] for r in pack.reminders], [2700, 300])
        self.assertEqual(pack.issue_title.format(task='t'), '[pbench] t')
        self.assertEqual(pack.seed_message.format(task='t'), 'pbench: seed cleanroom workspace (t)')
        self.assertEqual(pack.prompts, ROOT / 'tasks/programbench/prompts')


class MalformedPackTest(unittest.TestCase):
    def make(self, text, files=('prompts/brief.txt', 'prompts/idle.txt')):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        pack = Path(self.directory.name) / 'tasks' / 'demo'
        for name in files:
            (pack / name).parent.mkdir(parents=True, exist_ok=True)
            (pack / name).write_text('x\n')
        (pack / 'pack.toml').write_text(text)
        return Path(self.directory.name)

    def assert_rejected(self, text, message, **kwargs):
        root = self.make(text, **kwargs)
        with self.assertRaises(PackError) as caught:
            load_pack('demo', root)
        self.assertIn(message, str(caught.exception))

    def test_minimal_pack_uses_defaults(self):
        pack = load_pack('demo', self.make(MINIMAL))
        self.assertEqual(pack.hooks, {})
        self.assertEqual(pack.reminders, ())
        self.assertEqual(pack.issue_title.format(task='t'), 't')

    def test_rejections(self):
        self.assert_rejected('extra = 1\n' + MINIMAL, 'unknown field(s) in pack.toml: extra')
        self.assert_rejected(MINIMAL + 'extra = 1\n', 'unknown field(s) in [messages]: extra')
        self.assert_rejected(MINIMAL.replace('"demo"', '"other"'), "declares name 'other'")
        self.assert_rejected(MINIMAL + '[hooks]\nprepare = "hooks/missing.sh"\n', 'hook prepare')
        self.assert_rejected(MINIMAL + '[hooks]\nbuild = "prompts/brief.txt"\n', 'unknown field(s) in [hooks]')
        self.assert_rejected(MINIMAL.replace('prompts/brief.txt', '../../../etc/passwd'), 'must stay inside')
        self.assert_rejected(MINIMAL.replace('idle = "prompts/idle.txt"\n', ''), '[messages] needs idle')
        self.assert_rejected(MINIMAL + '[[messages.reminders]]\nbefore_end = "soon"\nmessage = "prompts/idle.txt"\n',
                             'invalid duration')

    def test_invalid_names(self):
        for name in ('', 'Demo', '../demo', 'demo/x'):
            with self.subTest(name=name), self.assertRaises(PackError):
                load_pack(name, ROOT)

    def test_durations(self):
        self.assertEqual(parse_duration('45m'), 2700)
        self.assertEqual(parse_duration('2h'), 7200)
        self.assertEqual(parse_duration('30s'), 30)
        self.assertEqual(parse_duration(90), 90)
        for bad in ('-5m', '5 m', True, -1, '1d'):
            with self.subTest(bad=bad), self.assertRaises(PackError):
                parse_duration(bad)


if __name__ == '__main__':
    unittest.main()
