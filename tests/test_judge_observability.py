# -*- coding: utf-8 -*-
"""N+29 回归：judge 默认模型随 wire format 切换（P1）、失败计数入 summary 与
报告健康度可见（P2）。"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from membench import DIMENSIONS, cli
from membench.judge import LLMJudge
from membench.report import build_html, build_markdown
from membench.runner import run_suite
from membench.schema import parse_case


def _free_case():
    return parse_case({
        "case_id": "j-1", "dimension": "recall", "title": "t",
        "sessions": [{"session_id": "s1", "turns": ["我叫小明。"]}],
        "probes": [{"probe_id": "p1", "type": "free", "question": "我叫什么？",
                    "expected": {"must_include": ["小明"]}}],
    })


class TestJudgeModelDefaults(unittest.TestCase):
    """P1：--judge-model 缺省值必须随 wire format 切换，防跨格式错配
    （此前固定 gpt-4o-mini，--judge anthropic 会静默失败回退）。"""

    def _ns(self, judge, model=""):
        return argparse.Namespace(judge=judge, judge_base_url="", judge_key_env="",
                                  judge_model=model, judge_votes=1)

    def test_anthropic_default_model(self):
        j = cli._judge_from_args(self._ns("anthropic"))
        self.assertEqual(j.api, "anthropic")
        self.assertEqual(j.model, "claude-sonnet-4-5")
        self.assertEqual(j.base_url, "https://api.anthropic.com")

    def test_openai_default_model(self):
        j = cli._judge_from_args(self._ns("openai"))
        self.assertEqual(j.api, "openai")
        self.assertEqual(j.model, "gpt-4o-mini")

    def test_explicit_model_wins(self):
        j = cli._judge_from_args(self._ns("anthropic", model="deepseek-r1"))
        self.assertEqual(j.model, "deepseek-r1")


class TestJudgeHealthInSummary(unittest.TestCase):
    """P2：judge 计数按智能体增量汇入 summary["_judge"] 并落盘 summary.json。"""

    def setUp(self):
        self.out = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.out, ignore_errors=True)

    def test_run_suite_persists_judge_delta(self):
        from membench.agents import create_agent
        judge = LLMJudge(base_url="http://127.0.0.1:1/v1", model="m")  # 端口必失败
        s = run_suite(create_agent("naive"), [_free_case()], out_dir=self.out,
                      runs=2, quiet=True, judge_free=judge.judge_free,
                      judge_health_fn=cli._judge_delta_fn(judge, judge.health()))
        self.assertEqual(s["_judge"]["calls"], 2)    # 2 次 run × 1 个 free 探针
        self.assertEqual(s["_judge"]["failures"], 2)
        self.assertTrue(s["_judge"]["last_error"])
        on_disk = json.load(open(os.path.join(self.out, "naive", "summary.json"),
                                 encoding="utf-8"))
        self.assertEqual(on_disk["_judge"]["failures"], 2)

    def test_heuristic_run_has_no_judge_key(self):
        from membench.agents import create_agent
        s = run_suite(create_agent("naive"), [_free_case()], out_dir=self.out,
                      runs=1, quiet=True)
        self.assertNotIn("_judge", s)

    def test_delta_blank_between_agents(self):
        """共享 judge 依次跑两个智能体：无失败的智能体不得串到上一个的报错。"""
        from membench.agents import create_agent
        judge = LLMJudge(base_url="http://127.0.0.1:1/v1", model="m")
        first = run_suite(create_agent("naive"), [_free_case()], out_dir=self.out,
                          runs=1, quiet=True, judge_free=judge.judge_free,
                          judge_health_fn=cli._judge_delta_fn(judge, judge.health()))
        self.assertEqual(first["_judge"]["failures"], 1)
        second = run_suite(create_agent("smart"), [_free_case()], out_dir=self.out,
                           runs=1, quiet=True, judge_free=judge.judge_free,
                           judge_health_fn=cli._judge_delta_fn(judge, judge.health()))
        self.assertEqual((second["_judge"]["calls"], second["_judge"]["failures"]),
                         (1, 1))
        self.assertTrue(second["_judge"]["last_error"])  # 本智能体确有失败


class TestJudgeHealthInReports(unittest.TestCase):
    """summary["_judge"] 在 markdown / HTML 报告中可见，失败态用警示样式。"""

    @staticmethod
    def _summary(failures):
        return {"agent": "a", "runs": 1, "n_cases": 1, "overall": 0.5,
                "total_findings_sensitive": 0,
                "dimensions": {d: {"score": 0.5, "n_probes": 1, "n_scored": 1,
                                   "n_not_evaluable": 0,
                                   "verdicts": {"correct": 1},
                                   "std_across_runs": 0.0}
                               for d in DIMENSIONS},
                "_judge": {"api": "anthropic", "model": "claude-sonnet-4-5",
                           "votes": 1, "calls": 4, "failures": failures,
                           "last_error": "HTTP 401: bad key" if failures else ""}}

    def test_markdown_shows_judge_health(self):
        md = build_markdown([self._summary(failures=2)])
        self.assertIn("失败 2/4 次", md)
        self.assertIn("HTTP 401", md)
        ok = build_markdown([self._summary(failures=0)])
        self.assertIn("4 次调用全部成功", ok)

    def test_html_shows_judge_health(self):
        html = build_html([self._summary(failures=2)],
                          os.path.join(tempfile.mkdtemp(), "r.html"))
        self.assertIn("失败 2/4 次", html)
        self.assertIn("class='bad'", html)


if __name__ == "__main__":
    unittest.main()
