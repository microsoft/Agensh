#!/usr/bin/env python3
"""Exercise shared-context portability boundaries without services or a model."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "board-service"))

from shared_lessons import SharedLessons
from verifier import verify_note


class CoordinationProbe(unittest.IsolatedAsyncioTestCase):
    async def test_given_two_workers_when_claiming_same_work_then_both_claims_are_visible(self):
        board = SharedLessons("synthetic-task")
        await asyncio.gather(
            board.note(1, "CLAIM", "Implement parser", delegation_id="parser"),
            board.note(2, "CLAIM", "Implement parser", delegation_id="parser"),
        )
        claims = [entry for entry in await board.read() if entry["type"] == "CLAIM"]
        self.assertEqual({entry["thread_id"] for entry in claims}, {1, 2})
        self.assertEqual(len(claims), 2)

    async def test_given_expired_claim_when_reading_then_live_view_hides_it_and_history_retains_it(self):
        with patch("shared_lessons.time.time", return_value=1000):
            board = SharedLessons("synthetic-task")
            await board.note(1, "CLAIM", "Implement parser", ttl_seconds=30)
        with patch("shared_lessons.time.time", return_value=1031):
            self.assertEqual(await board.read(), [])
            retained = await board.read_all()
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0]["content"], "Implement parser")

    async def test_given_repeated_finding_when_reading_then_one_gist_retains_all_authors(self):
        board = SharedLessons("synthetic-task")
        for author in [1, 2, 3]:
            await board.note(author, "FACT", "Parser accepts UTF-8", delegation_id="parser")
        visible = await board.read()
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]["_dup"], 3)
        self.assertEqual(set(visible[0]["_thread_ids"]), {1, 2, 3})
        self.assertEqual(len(await board.read_all()), 3)

    async def test_given_patch_revision_when_publishing_then_latest_candidate_replaces_same_author_work(self):
        board = SharedLessons("synthetic-task")
        await board.note(1, "PATCH_SUMMARY", "files=parser.py | idea=v1 | evidence=passed",
                         delegation_id="parser")
        await board.note(2, "PATCH_SUMMARY", "files=lexer.py | idea=lexer | evidence=passed",
                         delegation_id="lexer")
        await board.note(1, "PATCH_SUMMARY", "files=parser.py | idea=v2 | evidence=passed",
                         delegation_id="parser")
        visible = await board.read()
        self.assertEqual(len(visible), 2)
        parser = next(entry for entry in visible if entry["thread_id"] == 1)
        self.assertIn("idea=v2", parser["content"])
        self.assertNotIn("idea=v1", parser["content"])

    async def test_given_author_counterexample_when_publishing_fail_then_candidate_is_invalidated(self):
        board = SharedLessons("synthetic-task")
        await board.note(1, "PATCH_SUMMARY", "files=parser.py | idea=v1 | evidence=passed",
                         delegation_id="parser")
        await board.note(1, "FAIL", "Parser rejects an empty string", delegation_id="parser")
        candidate = next(entry for entry in await board.read() if entry["type"] == "PATCH_SUMMARY")
        self.assertNotIn("_verified_checkpoint", candidate)
        self.assertEqual(candidate["_invalidated_by_fail"], "Parser rejects an empty string")
        self.assertIn("invalidated", board.format_for_prompt([candidate]))

    async def test_given_peer_counterexample_when_publishing_fail_then_other_author_candidate_needs_reconciliation(self):
        board = SharedLessons("synthetic-task")
        await board.note(1, "PATCH_SUMMARY", "files=parser.py | idea=v1 | evidence=passed",
                         delegation_id="parser")
        await board.note(2, "FAIL", "Parser rejects an empty string", delegation_id="parser")
        visible = await board.read()
        candidate = next(entry for entry in visible if entry["type"] == "PATCH_SUMMARY")
        self.assertTrue(candidate["_verified_checkpoint"])
        self.assertNotIn("_invalidated_by_fail", candidate)
        self.assertEqual(len([entry for entry in visible if entry["type"] == "FAIL"]), 1)

    async def test_given_claimed_pass_when_admitting_then_text_status_does_not_establish_execution(self):
        note, reason = verify_note({
            "type": "PATCH_SUMMARY",
            "content": "files=parser.py | idea=synthetic | evidence=passed nonexistent-command",
        })
        self.assertEqual(reason, "ok:1/1")
        self.assertIsNotNone(note)
        board = SharedLessons("synthetic-task")
        await board.note(1, note["type"], note["content"], delegation_id="parser")
        candidate = (await board.read())[0]
        self.assertTrue(candidate["_verified_checkpoint"])

    async def test_given_missing_placeholder_or_truncated_evidence_when_admitting_then_note_is_refused(self):
        for content in [
            "files=parser.py | idea=synthetic",
            "files=parser.py | idea=synthetic | evidence=pending",
            "files=parser.py | idea=" + "x" * 300 + " | evidence=passed",
        ]:
            with self.subTest(content=content):
                note, reason = verify_note({"type": "PATCH_SUMMARY", "content": content})
                self.assertIsNone(note)
                self.assertIn("ps_invalid_ev=1", reason)

    async def test_given_reused_context_when_exporting_then_lifecycle_records_compression_and_use(self):
        board = SharedLessons("synthetic-task")
        for author in [1, 2, 3]:
            await board.note(author, "FACT", "Parser accepts UTF-8")
        await board.read()
        await board.read()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "lifecycle.jsonl"
            await board.write_lifecycle_summary(output)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
        entry = next(row for row in rows if row["kind"] == "entry")
        summary = next(row for row in rows if row["kind"] == "summary")
        self.assertEqual(entry["written_count"], 3)
        self.assertEqual(entry["render_count"], 2)
        self.assertEqual(set(entry["thread_ids"]), {1, 2, 3})
        self.assertEqual(summary["stored_total"], 3)
        self.assertEqual(summary["unique_total"], 1)
        self.assertEqual(summary["ever_rendered"], 1)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(CoordinationProbe)
    )
    print(json.dumps({
        "probe": "shared-context-portability",
        "cases": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "boundary": "in-process shared context; synthetic inputs; no model or service execution",
    }, sort_keys=True))
    complete = result.testsRun == 9 and not result.skipped
    raise SystemExit(0 if result.wasSuccessful() and complete else 1)
