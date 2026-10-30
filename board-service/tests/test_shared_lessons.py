# Characterize the recent shared-context view: admission, claims, patch status,
# deduplication and rendering. Run: python3 -m unittest discover -s board-service/tests

import asyncio
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import shared_lessons  # noqa: E402
from shared_lessons import SharedLessons, SharedLessonsError, parse_patch_summary_field  # noqa: E402


def run(coro):
    return asyncio.run(coro)


class NoteAdmissionTest(unittest.TestCase):
    def setUp(self):
        self.board = SharedLessons("task")

    def test_rejects_unknown_type(self):
        with self.assertRaises(SharedLessonsError):
            run(self.board.note(1, "IDEA", "x"))

    def test_rejects_empty_content(self):
        with self.assertRaises(SharedLessonsError):
            run(self.board.note(1, "FACT", "   "))

    def test_none_tokens_are_dropped_silently(self):
        for token in ("(none)", "None", "-", "—"):
            self.assertIsNone(run(self.board.note(1, "FACT", token)))
        self.assertEqual(run(self.board.read_all()), [])

    def test_content_caps_depend_on_type(self):
        run(self.board.note(1, "FACT", "x" * 100))
        with self.assertRaises(SharedLessonsError):
            run(self.board.note(1, "FACT", "x" * 101))
        run(self.board.note(1, "PATCH_SUMMARY", "y" * 300))
        with self.assertRaises(SharedLessonsError):
            run(self.board.note(1, "PATCH_SUMMARY", "y" * 301))

    def test_content_is_stripped(self):
        entry = run(self.board.note(1, "FACT", "  spaced  "))
        self.assertEqual(entry["content"], "spaced")

    def test_retained_window_is_capped(self):
        original = shared_lessons.MAX_BOARD_ENTRIES
        shared_lessons.MAX_BOARD_ENTRIES = 3
        try:
            for i in range(5):
                run(self.board.note(1, "FACT", f"fact {i}"))
        finally:
            shared_lessons.MAX_BOARD_ENTRIES = original
        contents = [e["content"] for e in run(self.board.read_all())]
        self.assertEqual(contents, ["fact 2", "fact 3", "fact 4"])


class ClaimTest(unittest.TestCase):
    def setUp(self):
        self.board = SharedLessons("task")

    def test_default_ttl_is_one_hour(self):
        before = time.time()
        entry = run(self.board.note(1, "CLAIM", "parser"))
        self.assertAlmostEqual(entry["_expires_at"] - before, 3600, delta=5)

    def test_negative_ttl_is_clamped_to_now(self):
        entry = run(self.board.note(1, "CLAIM", "parser", ttl_seconds=-50))
        self.assertAlmostEqual(entry["_expires_at"], entry["ts"], delta=0.01)

    def test_only_claims_expire(self):
        self.assertFalse(SharedLessons._is_expired_claim({"type": "FACT", "_expires_at": 0}, 10))
        self.assertFalse(SharedLessons._is_expired_claim({"type": "CLAIM", "_expires_at": None}, 10))
        self.assertTrue(SharedLessons._is_expired_claim({"type": "CLAIM", "_expires_at": 5}, 10))
        self.assertFalse(SharedLessons._is_expired_claim({"type": "CLAIM", "_expires_at": 10}, 10))

    def test_expired_claims_are_hidden_from_read_but_retained(self):
        run(self.board.note(1, "CLAIM", "old", ttl_seconds=0))
        run(self.board.note(2, "CLAIM", "live"))
        time.sleep(0.01)
        self.assertEqual([e["content"] for e in run(self.board.read())], ["live"])
        self.assertEqual(len(run(self.board.read_all())), 2)

    def test_identical_claims_are_not_merged(self):
        run(self.board.note(1, "CLAIM", "same"))
        run(self.board.note(2, "CLAIM", "same"))
        self.assertEqual(len(run(self.board.read())), 2)


class PatchSummaryTest(unittest.TestCase):
    def setUp(self):
        self.board = SharedLessons("task")

    def test_parse_patch_summary_field(self):
        content = "files=a.py | IDEA=fix x | evidence= tests pass "
        self.assertEqual(parse_patch_summary_field(content, "idea"), "fix x")
        self.assertEqual(parse_patch_summary_field(content, "evidence"), "tests pass")
        self.assertIsNone(parse_patch_summary_field(content, "missing"))

    def test_verified_checkpoint_needs_solid_evidence(self):
        verified = run(self.board.note(1, "PATCH_SUMMARY", "files=a | idea=b | evidence=tests passed"))
        weak = run(self.board.note(2, "PATCH_SUMMARY", "files=a | idea=b | evidence=should pass"))
        vague = run(self.board.note(3, "PATCH_SUMMARY", "files=a | idea=b | evidence=ran it"))
        self.assertTrue(verified.get("_verified_checkpoint"))
        self.assertNotIn("_verified_checkpoint", weak)
        self.assertNotIn("_verified_checkpoint", vague)

    def test_same_author_and_label_replaces_and_keeps_first_timestamp(self):
        first = run(self.board.note(1, "PATCH_SUMMARY", "files=a | idea=v1 | evidence=x", delegation_id=7))
        run(self.board.note(1, "PATCH_SUMMARY", "files=a | idea=v2 | evidence=x", delegation_id=7))
        entries = run(self.board.read_all())
        self.assertEqual(len(entries), 1)
        self.assertIn("v2", entries[0]["content"])
        self.assertEqual(entries[0]["_first_ts"], first["ts"])

    def test_different_label_or_author_is_kept(self):
        run(self.board.note(1, "PATCH_SUMMARY", "files=a | idea=one | evidence=x", delegation_id=7))
        run(self.board.note(1, "PATCH_SUMMARY", "files=a | idea=two | evidence=x", delegation_id=8))
        run(self.board.note(2, "PATCH_SUMMARY", "files=a | idea=three | evidence=x", delegation_id=7))
        self.assertEqual(len(run(self.board.read_all())), 3)

    def test_fail_invalidates_authors_latest_matching_patch(self):
        run(self.board.note(1, "PATCH_SUMMARY", "files=a | idea=b | evidence=tests passed", delegation_id=7))
        run(self.board.note(2, "PATCH_SUMMARY", "files=a | idea=c | evidence=tests passed", delegation_id=7))
        run(self.board.note(1, "FAIL", "breaks on empty input", delegation_id=7))
        mine, theirs = [e for e in run(self.board.read_all()) if e["type"] == "PATCH_SUMMARY"]
        self.assertNotIn("_verified_checkpoint", mine)
        self.assertEqual(mine["_invalidated_by_fail"], "breaks on empty input")
        self.assertEqual(mine["_local_fail_count"], 1)
        self.assertTrue(theirs["_verified_checkpoint"])
        line = self.board.format_entry_line(mine)
        self.assertTrue(line.endswith("[status=invalidated,local_failures=1]"), line)

    def test_new_revision_carries_prior_failures(self):
        run(self.board.note(1, "FAIL", "first try failed", delegation_id=3))
        entry = run(self.board.note(1, "PATCH_SUMMARY", "files=a | idea=b | evidence=x", delegation_id=3))
        self.assertEqual(entry["_local_fail_count"], 1)


class DedupeTest(unittest.TestCase):
    def setUp(self):
        self.board = SharedLessons("task")

    def test_exact_duplicates_merge_with_count_and_authors(self):
        run(self.board.note(1, "FACT", "flag -x  is ignored"))
        run(self.board.note(2, "FACT", "flag -x is ignored"))
        run(self.board.note(3, "FAIL", "flag -x is ignored"))
        entries = run(self.board.read())
        facts = [e for e in entries if e["type"] == "FACT"]
        self.assertEqual(len(entries), 2)
        self.assertEqual(facts[0]["_dup"], 2)
        self.assertEqual(facts[0]["_thread_ids"], [1, 2])
        self.assertTrue(self.board.format_entry_line(facts[0]).endswith("(x2)"))

    def test_semantic_duplicates_need_strong_code_anchors(self):
        run(self.board.note(1, "FACT", "parser.py def tokenize drops tabs"))
        run(self.board.note(2, "FACT", "in parser.py, def tokenize loses tab characters"))
        run(self.board.note(3, "FACT", "tabs are dropped somewhere"))
        run(self.board.note(4, "FACT", "tab characters get lost"))
        self.assertEqual(len(run(self.board.read())), 3)

    def test_semantic_key_cases(self):
        key = self.board._semantic_key
        self.assertIsNone(key({"type": "FACT", "content": "parser.py is slow"}))
        self.assertIsNotNone(key({"type": "FACT", "content": "parser.py line 12 crashes"}))
        self.assertIsNotNone(key({"type": "FACT", "content": "test_render fails"}))
        self.assertIsNotNone(key({"type": "FACT", "content": "KeyError at line 4"}))


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.board = SharedLessons("task")

    def test_empty_board(self):
        self.assertEqual(self.board.format_for_prompt([]), "(no shared lessons yet)")

    def test_sections_are_ordered_patches_claims_lessons(self):
        run(self.board.note(1, "FACT", "a fact"))
        run(self.board.note(2, "CLAIM", "a claim"))
        run(self.board.note(3, "PATCH_SUMMARY", "files=a | idea=b | evidence=x"))
        text = self.board.format_for_prompt(run(self.board.read()))
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith("[Patch summaries"))
        self.assertTrue(lines[1].startswith("[t3/PATCH_SUMMARY +"))
        self.assertEqual(lines[2], "")
        self.assertTrue(lines[3].startswith("[Active claims"))
        self.assertRegex(lines[4], r"^\[t2/CLAIM \+\d+\.\dm, \+\d+\.\dm left\] a claim$")
        self.assertEqual(lines[5:7], ["", "[Shared lessons]"])
        self.assertRegex(lines[7], r"^\[t1/FACT \+\d+\.\dm\] a fact$")

    def test_lessons_only_has_no_header(self):
        run(self.board.note(1, "FACT", "a fact"))
        text = self.board.format_for_prompt(run(self.board.read()))
        self.assertRegex(text, r"^\[t1/FACT \+\d+\.\dm\] a fact$")

    def test_lifecycle_summary_counts_renders(self):
        run(self.board.note(1, "FACT", "seen twice"))
        run(self.board.note(2, "FACT", "seen twice"))
        run(self.board.note(1, "PATCH_SUMMARY", "files=a | idea=b | evidence=tests passed"))
        run(self.board.read())
        run(self.board.read())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "board.jsonl"
            run(self.board.write_lifecycle_summary(path))
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        entries = {row["content"]: row for row in rows if row["kind"] == "entry"}
        summary = rows[-1]
        self.assertEqual(entries["seen twice"]["written_count"], 2)
        self.assertEqual(entries["seen twice"]["render_count"], 2)
        patch = entries["files=a | idea=b | evidence=tests passed"]
        self.assertTrue(patch["is_verified_checkpoint"])
        self.assertEqual(patch["patch_status"], "verified")
        self.assertEqual(summary["kind"], "summary")
        self.assertEqual(summary["stored_total"], 3)
        self.assertEqual(summary["unique_total"], 2)
        self.assertEqual(summary["stored_by_type"]["FACT"], 2)


if __name__ == "__main__":
    unittest.main()
