# The driver's timing rules must match the shell runner they replaced.
# Run: python3 -m unittest discover -s tests/unit

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agensh import schedule  # noqa: E402

REMINDERS = [{'before_end_seconds': 2700, 'message': '45m'}, {'before_end_seconds': 300, 'message': '5m'}]


def shell_reminders(secs):
    """Transcription of deadline_reminder_loop in the former scripts/pbench_run.sh."""
    posted = []
    t45, t5 = secs - 45 * 60, secs - 5 * 60
    if t45 > 0:
        posted.append((t45, '45m'))
    rest = t5 - (t45 if t45 > 0 else 0)
    if rest > 0:
        posted.append((t5, '5m'))
    return posted


def shell_idle_phase(total, remaining):
    delivery = 2700 if total > 2700 else 300
    return 'delivery' if remaining <= delivery else 'development'


def shell_stagger(index, base=30, fast=3, ramp=3600):
    return base if index <= ramp // base else fast


class ScheduleTest(unittest.TestCase):
    def test_budget_and_minimum_remaining(self):
        self.assertEqual(schedule.budget_seconds('6'), 21600)
        self.assertEqual(schedule.budget_seconds(5 / 60), 300)
        self.assertEqual(schedule.budget_seconds('0.08333333333333333'), 300)
        self.assertEqual(schedule.remaining_after(21600, 600), 21000)
        self.assertEqual(schedule.remaining_after(300, 290), 60)
        self.assertEqual(schedule.remaining_after(300, 900), 60)

    def test_reminders_match_shell_runner(self):
        for secs in [0, 1, 299, 300, 301, 600, 2699, 2700, 2701, 3000, 3600, 21600, 21000]:
            with self.subTest(secs=secs):
                ours = [(offset, r['message']) for offset, r in schedule.reminder_times(secs, REMINDERS)]
                self.assertEqual(ours, shell_reminders(secs))

    def test_reminders_are_ordered_whatever_the_input_order(self):
        reversed_input = list(reversed(REMINDERS))
        self.assertEqual([r['message'] for _, r in schedule.reminder_times(21600, reversed_input)], ['45m', '5m'])

    def test_idle_phase_matches_shell_runner(self):
        for total in (300, 2700, 2701, 21600):
            for remaining in (0, 299, 300, 301, 2699, 2700, 2701, total):
                with self.subTest(total=total, remaining=remaining):
                    self.assertEqual(schedule.idle_phase(total, remaining), shell_idle_phase(total, remaining))

    def test_wake_stagger_matches_shell_runner(self):
        for index in (1, 2, 119, 120, 121, 1024):
            self.assertEqual(schedule.wake_stagger(index), shell_stagger(index))
        self.assertEqual(schedule.wake_stagger(3, base_seconds=5, fast_seconds=1, ramp_seconds=10), 1)
        self.assertEqual(schedule.wake_stagger(2, base_seconds=5, fast_seconds=1, ramp_seconds=10), 5)

    def test_nudge_threshold_and_repeat(self):
        self.assertFalse(schedule.should_nudge(599, 10_000, 0))
        self.assertTrue(schedule.should_nudge(600, 10_000, 0))
        self.assertFalse(schedule.should_nudge(900, 10_000, 9_500))
        self.assertTrue(schedule.should_nudge(900, 10_100, 9_500))


if __name__ == '__main__':
    unittest.main()
