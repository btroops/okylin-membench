# -*- coding: utf-8 -*-
"""雷达图 / LLM judge 单元测试。"""
import os
import sys
import unittest
from xml.etree import ElementTree

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from membench import DIMENSIONS
from membench.judge import LLMJudge
from membench.radar import bars_svg, radar_svg
from membench.schema import parse_case


class TestRadar(unittest.TestCase):
    def test_wellformed_svg(self):
        series = {
            "甲": {d: 0.5 for d in DIMENSIONS},
            "乙": {d: 0.9 for d in DIMENSIONS},
        }
        svg = radar_svg(series, title="对比")
        root = ElementTree.fromstring(svg)  # 语法必须合法
        self.assertEqual(root.tag.endswith("svg"), True)
        self.assertEqual(svg.count("<polygon"), 7)  # 5 网格环 + 2 数据多边形

    def test_bars_svg(self):
        svg = bars_svg({"a": 1.0, "b": 0.4, "c": 0.0})
        ElementTree.fromstring(svg)


def _make_case():
    return parse_case({
        "case_id": "j-1", "dimension": "recall", "title": "t",
        "sessions": [{"session_id": "s1", "turns": ["我叫小明。"]}],
        "probes": [{"probe_id": "p1", "type": "free", "question": "我叫什么？",
                    "expected": {"must_include": ["小明"]}}],
    })


class TestLLMJudge(unittest.TestCase):
    def test_parse_and_verdict(self):
        from membench import VERDICT_CORRECT
        from unittest import mock

        j = LLMJudge(base_url="http://127.0.0.1:1/v1", model="m")
        case = _make_case()
        probe = case.probes[0]
        with mock.patch.object(LLMJudge, "_post",
                               return_value={"verdict": "correct", "score": 1.0,
                                             "reason": "回答包含小明"}):
            out = j.judge_free(probe, case, "你叫小明")
        self.assertEqual(out["verdict"], VERDICT_CORRECT)
        self.assertEqual(out["score"], 1.0)

    def test_no_fallback_returns_not_evaluable(self):
        from membench import VERDICT_NOT_EVALUABLE
        j = LLMJudge(base_url="http://127.0.0.1:1/v1", model="m")  # 端口必失败
        case = _make_case()
        probe = case.probes[0]
        out = j.judge_free(probe, case, "不知道")
        self.assertEqual(out["verdict"], VERDICT_NOT_EVALUABLE)

    def test_fallback_used_on_error(self):
        from membench import VERDICT_CORRECT

        def fallback(probe, case, reply):
            return {"verdict": VERDICT_CORRECT, "score": 1.0, "reason": "启发式兜底"}
        j = LLMJudge(base_url="http://127.0.0.1:1/v1", model="m", fallback=fallback)
        case = _make_case()
        out = j.judge_free(case.probes[0], case, "你叫小明")
        self.assertEqual(out["verdict"], VERDICT_CORRECT)

    def test_invalid_verdict_rejected(self):
        from membench import VERDICT_NOT_EVALUABLE
        j = LLMJudge(base_url="http://127.0.0.1:1/v1", model="m")
        case = _make_case()
        probe = case.probes[0]
        from unittest import mock
        with mock.patch.object(LLMJudge, "_post",
                               return_value={"verdict": "神级正确", "score": 5}):
            out = j.judge_free(probe, case, "随便")
        self.assertEqual(out["verdict"], VERDICT_NOT_EVALUABLE)


if __name__ == "__main__":
    unittest.main()
