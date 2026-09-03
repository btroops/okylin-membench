# -*- coding: utf-8 -*-
"""schema / loader 单元测试。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from membench.loader import load_cases
from membench.schema import SchemaError, parse_case

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestLoader(unittest.TestCase):
    def test_builtin_suite_loads(self):
        cases = load_cases([os.path.join(PKG, "cases")])
        self.assertGreaterEqual(len(cases), 26)
        dims = {c.dimension for c in cases}
        self.assertEqual(len(dims), 9)

    def test_duplicate_case_id_rejected(self):
        import tempfile
        d = tempfile.mkdtemp()
        body = {
            "case_id": "dup-1", "dimension": "retention", "title": "t",
            "sessions": [{"session_id": "s1", "turns": ["你好"]}],
            "probes": [{"probe_id": "p1", "type": "slot", "question": "q",
                        "expected": {"must_include": ["x"]}}],
        }
        import json
        for name in ("a.json", "b.json"):
            with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                json.dump(body, f)
        with self.assertRaises(SchemaError):
            load_cases([d])

    def test_bad_dimension_rejected(self):
        with self.assertRaises(SchemaError):
            parse_case({"case_id": "x", "dimension": "nope", "title": "t",
                        "sessions": [{"session_id": "s1", "turns": ["a"]}],
                        "probes": [{"probe_id": "p1", "type": "slot",
                                    "expected": {"must_include": ["x"]}}]})

    def test_choice_answer_must_be_in_choices(self):
        with self.assertRaises(SchemaError):
            parse_case({
                "case_id": "x", "dimension": "recall", "title": "t",
                "sessions": [{"session_id": "s1", "turns": ["a"]}],
                "probes": [{"probe_id": "p1", "type": "choice", "question": "q",
                            "expected": {"choices": ["A", "B"], "answer": "C"}}]})

    def test_empty_probe_rejected(self):
        with self.assertRaises(SchemaError):
            parse_case({
                "case_id": "x", "dimension": "recall", "title": "t",
                "sessions": [{"session_id": "s1", "turns": ["a"]}],
                "probes": [{"probe_id": "p1", "type": "free", "question": "q",
                            "expected": {}}]})

    def test_after_session_must_exist(self):
        with self.assertRaises(SchemaError):
            parse_case({
                "case_id": "x", "dimension": "recall", "title": "t",
                "sessions": [{"session_id": "s1", "turns": ["a"]}],
                "probes": [{"probe_id": "p1", "type": "slot", "after_session": "s9",
                            "expected": {"must_include": ["x"]}}]})


if __name__ == "__main__":
    unittest.main()
