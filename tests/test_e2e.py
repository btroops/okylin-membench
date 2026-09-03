# -*- coding: utf-8 -*-
"""端到端测试：runner / 聚合 / 报告 / 区分度 / 稳定性 / LLM judge 接入。"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from membench.agents import create_agent
from membench.loader import load_cases
from membench.report import build_markdown, write_reports
from membench.runner import run_suite
from membench.aggregate import compare_summaries

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(PKG, "cases")


class TestRunnerE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_cases([CASES])
        cls.tmp = tempfile.mkdtemp()
        cls.summaries = []
        for name in ("nomem", "naive", "smart"):
            agent = create_agent(name)
            cls.summaries.append(run_suite(agent, cls.cases, out_dir=cls.tmp,
                                           runs=2, quiet=True))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_all_probes_evaluated(self):
        for s in self.summaries:
            for dim, d in s["dimensions"].items():
                self.assertEqual(d["n_probes"], d["n_scored"] + d["n_not_evaluable"],
                                 "%s/%s 探针计数不一致" % (s["agent"], dim))

    def test_discrimination(self):
        """三种记忆策略的画像必须显著不同——这是 benchmark 区分度的底线。"""
        by = {s["agent"]: {d: v["score"] for d, v in s["dimensions"].items()}
              for s in self.summaries}
        # nomem：什么都没记住但什么都没存 → 边界满分，其余接近 0
        self.assertEqual(by["nomem"]["boundary_refusal"], 1.0)
        self.assertLessEqual(by["nomem"]["retention"], 0.2)
        # naive：记得住但全记错重点 → 更新/区分/边界都应差
        self.assertGreater(by["naive"]["retention"], 0.7)
        self.assertLessEqual(by["naive"]["dynamic_update"], 0.3)
        self.assertLessEqual(by["naive"]["boundary_refusal"], 0.3)
        # smart：全部维度良好
        for d, v in by["smart"].items():
            self.assertGreaterEqual(v, 0.7, "smart 在 %s 失分" % d)
        # 总分排序
        overall = {s["agent"]: s["overall"] for s in self.summaries}
        self.assertGreater(overall["smart"], overall["naive"])
        self.assertGreater(overall["naive"], overall["nomem"])

    def test_stability_deterministic(self):
        """确定性智能体两次 run 的各维度得分应完全一致（std=0）。"""
        for s in self.summaries:
            for dim, d in s["dimensions"].items():
                self.assertEqual(d["std_across_runs"], 0.0,
                                 "%s/%s 跨 run 不稳定" % (s["agent"], dim))

    def test_boundary_sensitive_scan(self):
        """naive 全量照记 → 必须产生敏感持久化事件；nomem/smart 不应有。"""
        by = {s["agent"]: s["total_findings_sensitive"] for s in self.summaries}
        self.assertGreater(by["naive"], 0)
        self.assertEqual(by["nomem"], 0)
        self.assertEqual(by["smart"], 0)

    def test_reports_generated(self):
        paths = write_reports(self.summaries, self.tmp)
        for key in ("html", "markdown", "json"):
            self.assertTrue(os.path.exists(paths[key]))
        html = open(paths["html"], encoding="utf-8").read()
        self.assertIn("<svg", html)
        self.assertIn("六维长期记忆能力对比", html)  # 雷达图已内嵌
        md = open(paths["markdown"], encoding="utf-8").read()
        self.assertIn("六维对比", md)
        cmp_data = compare_summaries(self.summaries)
        self.assertEqual(cmp_data["ranking"][0]["agent"], "smart")


class TestBrokenAgentIsolated(unittest.TestCase):
    def test_agent_error_does_not_stop_suite(self):
        """智能体崩溃应被隔离为 not_evaluable，而不是中断评测。"""
        broken = os.path.join(tempfile.mkdtemp(), "boom.json")
        with open(broken, "w", encoding="utf-8") as f:
            json.dump({"name": "boom", "kind": "subproc",
                       "cmd": ["python3", "-c", "import sys; sys.exit(1)"]}, f)
        agent = create_agent(broken)
        cases = load_cases([CASES])[:3]
        s = run_suite(agent, cases, out_dir=tempfile.mkdtemp(), runs=1, quiet=True)
        # 每个用例都有 error 行且全部不可评
        self.assertEqual(s["dimensions"]["retention"]["n_not_evaluable"] +
                         s["dimensions"]["recall"]["n_not_evaluable"] +
                         s["dimensions"]["dynamic_update"]["n_not_evaluable"], 3)


if __name__ == "__main__":
    unittest.main()
