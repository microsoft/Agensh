# Characterize note verification, grep query parsing and detail unfolding.
# Run: python3 -m unittest discover -s board-service/tests

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gquery  # noqa: E402
import unfold  # noqa: E402
from shared_lessons import VALID_TYPES  # noqa: E402
from verifier import verify_note  # noqa: E402


class VerifyNoteTest(unittest.TestCase):
    def test_type_is_normalized_and_content_stripped(self):
        note, status = verify_note({"type": " fact ", "content": "  ok  "})
        self.assertEqual(note, {"type": "FACT", "content": "ok"})
        self.assertEqual(status, "ok:1/1")

    def test_unknown_type_or_empty_content_is_rejected(self):
        self.assertEqual(verify_note({"type": "IDEA", "content": "x"}), (None, "ok:0/1"))
        self.assertEqual(verify_note({"type": "FACT", "content": " "}), (None, "ok:0/1"))

    def test_content_is_truncated_to_type_cap(self):
        note, _ = verify_note({"type": "FACT", "content": "x" * 150})
        self.assertEqual(len(note["content"]), 100)
        long_patch = "files=a | idea=b | evidence=passed " + "y" * 400
        note, _ = verify_note({"type": "PATCH_SUMMARY", "content": long_patch})
        self.assertEqual(len(note["content"]), 300)

    def test_patch_summary_needs_real_evidence(self):
        invalid = (
            "files=a | idea=b",
            "files=a | idea=b | evidence=",
            "files=a | idea=b | evidence=TBD",
            "files=a | idea=b | evidence=pending review",
            "files=a | idea=b | evidence=n/a",
            "files=a | idea=b | evidence=should work, I think",
        )
        for content in invalid:
            with self.subTest(content=content):
                self.assertEqual(verify_note({"type": "PATCH_SUMMARY", "content": content}),
                                 (None, "ok:0/1,ps_invalid_ev=1"))

    def test_placeholder_prefix_inside_a_word_is_accepted(self):
        for evidence in ("pendingtests ran clean", "tests pass on 12 inputs"):
            with self.subTest(evidence=evidence):
                note, status = verify_note({"type": "PATCH_SUMMARY",
                                            "content": f"files=a | idea=b | evidence={evidence}"})
                self.assertIsNotNone(note)
                self.assertEqual(status, "ok:1/1")

    def test_evidence_after_truncation_is_checked(self):
        content = "files=" + "a" * 300 + " | idea=b | evidence=passed"
        self.assertEqual(verify_note({"type": "PATCH_SUMMARY", "content": content}),
                         (None, "ok:0/1,ps_invalid_ev=1"))


class QueryParseTest(unittest.TestCase):
    def test_and_binds_tighter_than_or(self):
        self.assertEqual(gquery.parse("a&b|c&d"),
                         ("or", [("and", [("term", "a"), ("term", "b")]),
                                 ("and", [("term", "c"), ("term", "d")])]))

    def test_parentheses_group_and_spaces_stay_literal(self):
        self.assertEqual(gquery.parse(" (exit code | crash) & tab "),
                         ("and", [("or", [("term", "exit code"), ("term", "crash")]),
                                  ("term", "tab")]))

    def test_single_term(self):
        self.assertEqual(gquery.parse("x"), ("term", "x"))
        self.assertEqual(gquery.count_terms(gquery.parse("a|(b&c)")), 3)

    def test_errors_explain_the_problem(self):
        cases = {
            "": "empty expression",
            "()": "empty group",
            "(a": "unbalanced '('",
            "a)": "unexpected ')'",
            "a|": "expected a search term",
            "&a": "'&' needs a term on both sides",
            "a (b)": "missing an operator",
            "(a|)": "expected a term before ')'",
        }
        for expr, message in cases.items():
            with self.subTest(expr=expr):
                with self.assertRaises(gquery.QueryError) as caught:
                    gquery.parse(expr)
                self.assertIn(message, str(caught.exception))

    def test_compile_sql_binds_terms_as_parameters(self):
        sql, params = gquery.compile_sql(gquery.parse("a&(b|c)"), lambda w: f"%{w}%")
        self.assertEqual(sql, "(content LIKE %s ESCAPE '\\\\' AND "
                              "(content LIKE %s ESCAPE '\\\\' OR content LIKE %s ESCAPE '\\\\'))")
        self.assertEqual(params, ["%a%", "%b%", "%c%"])


class TypeListTest(unittest.TestCase):
    def test_flat_list_with_any_separator_is_deduplicated(self):
        self.assertEqual(gquery.parse_type_list("fail|FACT,fail & claim", VALID_TYPES),
                         ["FAIL", "FACT", "CLAIM"])
        self.assertEqual(gquery.parse_type_list("", VALID_TYPES), [])

    def test_brackets_and_unknown_types_are_rejected(self):
        with self.assertRaises(gquery.QueryError):
            gquery.parse_type_list("(FAIL)", VALID_TYPES)
        with self.assertRaises(gquery.QueryError) as caught:
            gquery.parse_type_list("FAIL|IDEA", VALID_TYPES)
        self.assertIn("unknown type 'IDEA'", str(caught.exception))


class UnfoldTest(unittest.TestCase):
    def test_parse_label(self):
        self.assertEqual(unfold.parse_label(" G12 "), 12)
        for label in ("g12", "G", "G1x", "12", ""):
            with self.subTest(label=label):
                self.assertIsNone(unfold.parse_label(label))

    def test_resolves_known_labels_and_reports_unknown(self):
        result = unfold.unfold(["G1", "G2", "bad", " "], {1: "full one", 2: ""})
        self.assertEqual(result["resolved"], ["G1"])
        self.assertEqual(result["unknown"], ["G2", "bad"])
        self.assertTrue(result["rendered"].startswith("==== UNFOLDED DETAIL ===="))
        self.assertIn("[G1] full detail:\nfull one", result["rendered"])

    def test_nothing_resolved(self):
        result = unfold.unfold(["G9"], {})
        self.assertEqual(result["rendered"],
                         "(nothing unfolded: no requested label resolved to stored detail)")

    def test_labels_over_cap_are_dropped(self):
        labels = [f"G{i}" for i in range(unfold.MAX_UNFOLD_LABELS + 2)]
        result = unfold.unfold(labels, {})
        self.assertEqual(result["dropped_over_cap"], labels[-2:])
        self.assertEqual(len(result["unknown"]), unfold.MAX_UNFOLD_LABELS)

    def test_render_index_lists_only_labelled_entries_with_detail(self):
        entries = [
            {"_label": "G1", "_has_detail": True, "type": "FACT", "content": "short"},
            {"_label": "G2", "_has_detail": False, "type": "FACT", "content": "no detail"},
            {"_label": "G3", "_has_detail": True, "type": "FAIL", "content": "word " * 30},
        ]
        lines = unfold.render_index(entries).splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[1], "  G1  FACT  short")
        self.assertTrue(lines[2].startswith("  G3  FAIL  word"))
        self.assertTrue(lines[2].endswith(" ..."))
        self.assertEqual(unfold.render_index([entries[1]]), "")


if __name__ == "__main__":
    unittest.main()
