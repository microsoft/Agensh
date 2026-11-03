# Backlog synchronization: live claims citing issues, and assignee changes that
# never remove people the driver did not add. Run: python3 -m unittest discover -s tests/unit

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agensh import backlog  # noqa: E402

WORKERS = {'team-worker1', 'team-worker2'}


def claim(worker, content, expires=1000.0, kind='CLAIM'):
    return {'type': kind, 'thread_id': worker, 'content': content, '_expires_at': expires}


class LiveClaimsTest(unittest.TestCase):
    def test_references(self):
        entries = [claim('team-worker1', 'CLAIM #7: add --json; also #9'),
                   claim('team-worker2', 'working on #7 tests'),
                   claim('team-worker2', '#3 expired', expires=10.0),
                   claim('team-worker1', 'PATCH for #4', kind='PATCH_SUMMARY'),
                   claim('chairman', '#5 not a worker'),
                   claim('team-worker1', 'see a/b#6 and issue#8'),
                   {'type': 'CLAIM', 'thread_id': 'team-worker2', 'content': '#11', '_expires_at': None}]
        self.assertEqual(backlog.live_claims(entries, WORKERS, now=100.0),
                         {7: {'team-worker1', 'team-worker2'}, 9: {'team-worker1'}, 11: {'team-worker2'}})


class AssignmentsTest(unittest.TestCase):
    def test_claim_then_expiry(self):
        assignments = backlog.Assignments()
        claims = {7: {'team-worker1'}}
        self.assertEqual(assignments.update(7, claims, ['human'], 'open'), ['human', 'team-worker1'])
        self.assertIsNone(assignments.update(7, claims, ['human', 'team-worker1'], 'open'))
        self.assertEqual(assignments.issues({}), [7])
        # The claim expired: remove only the assignment the driver made.
        self.assertEqual(assignments.update(7, {}, ['human', 'team-worker1'], 'open'), ['human'])
        self.assertEqual(assignments.issues({}), [])

    def test_hand_over_and_close(self):
        assignments = backlog.Assignments()
        assignments.update(7, {7: {'team-worker1'}}, [], 'open')
        self.assertEqual(assignments.update(7, {7: {'team-worker2'}}, ['team-worker1'], 'open'), ['team-worker2'])
        # Closed issues keep their assignees as the record of who did the work.
        self.assertIsNone(assignments.update(7, {}, ['team-worker2'], 'closed'))
        self.assertEqual(assignments.issues({}), [])

    def test_never_removes_other_assignees(self):
        assignments = backlog.Assignments()
        self.assertIsNone(assignments.update(7, {}, ['team-worker1'], 'open'))


if __name__ == '__main__':
    unittest.main()
