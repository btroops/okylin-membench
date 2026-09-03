# -*- coding: utf-8 -*-
"""本轮新增能力回归：FAMA 复用旧值裁决、judge 自检接口、bin 报告。"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from membench.aggregate import bin_report_by_load
from membench.judge import LLMJudge
from membench.loader import load_cases
from membench.schema import parse_case
from membench.scoring import _fama_verdict

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestFamaVerdict(unittest.TestCase):
    def test_superseded_value_is_improper_reuse(self):
        from membench.schema import Expected
        from membench import VERDICT_IMPROPER_REUSE
        case = parse_case({
            "case_id": "x", "dimension": "retention", "title": "t",
            "sessions": [{"session_id": "s1", "turns": ["a"]}],
            "probes": [{"probe_id": "p1", "type": "slot",
                        "expected": {"must_not_include": ["旧号"],
                                     "superseded_values": ["旧号"]}}],
        })
        exp = Expected(must_not_include=["旧号"], superseded_values=["旧号"])
        self.assertEqual(_fama_verdict(exp, "retention", case, "旧号"),
                         VERDICT_IMPROPER_REUSE)

    def test_non_superseded_still_confusion(self):
        from membench.schema import Expected
        from membench import VERDICT_CONFUSION
        case = parse_case({
            "case_id": "x", "dimension": "retention", "title": "t",
            "sessions": [{"session_id": "s1", "turns": ["a"]}],
            "probes": [{"probe_id": "p1", "type": "slot",
                        "expected": {"must_not_include": ["干扰"]}}],
        })
        exp = Expected(must_not_include=["干扰"])
        self.assertEqual(_fama_verdict(exp, "retention", case, "干扰"),
                         VERDICT_CONFUSION)

    def test_superseded_in_dynamic_update_keeps_improper_reuse(self):
        """即使维度是 dynamic_update，被覆盖值仍按 improper_reuse。"""
        from membench.schema import Expected
        from membench import VERDICT_IMPROPER_REUSE
        case = parse_case({
            "case_id": "x", "dimension": "dynamic_update", "title": "t",
            "sessions": [{"session_id": "s1", "turns": ["a"]}],
            "probes": [{"probe_id": "p1", "type": "slot",
                        "expected": {"must_not_include": ["旧"],
                                     "superseded_values": ["旧"]}}],
        })
        exp = Expected(must_not_include=["旧"], superseded_values=["旧"])
        self.assertEqual(_fama_verdict(exp, "dynamic_update", case, "旧"),
                         VERDICT_IMPROPER_REUSE)


class TestJudgeSelfConsistencyHook(unittest.TestCase):
    def test_hook_returns_ama_bench_ref(self):
        j = LLMJudge(base_url="http://x", model="m", votes=3)
        h = j.self_consistency_hook()
        self.assertIn("AMA-Bench", h["_ref"])
        self.assertEqual(h["current_votes"], 3)
        self.assertGreaterEqual(h["expected_min_consistency"], 0.8)


class TestBinReport(unittest.TestCase):
    def test_bins_by_session_count(self):
        cases = [
            parse_case({"case_id": "c1", "dimension": "retention", "title": "t",
                        "sessions": [{"session_id": "s1", "turns": ["a"]}],
                        "probes": [{"probe_id": "p1", "type": "slot",
                                    "expected": {"must_include": ["x"]}}]}),
            parse_case({"case_id": "c2", "dimension": "retention", "title": "t",
                        "sessions": [{"session_id": "s1", "turns": ["a"]},
                                     {"session_id": "s2", "turns": ["b"]},
                                     {"session_id": "s3", "turns": ["c"]},
                                     {"session_id": "s4", "turns": ["d"]},
                                     {"session_id": "s5", "turns": ["e"]}],
                        "probes": [{"probe_id": "p1", "type": "slot",
                                    "expected": {"must_include": ["x"]}}]}),
        ]
        summaries = [
            {"agent": "a", "per_case": [{"case_id": "c1", "score": 100},
                                        {"case_id": "c2", "score": 50}]},
            {"agent": "b", "per_case": [{"case_id": "c1", "score": 80},
                                        {"case_id": "c2", "score": 30}]},
        ]
        r = bin_report_by_load(cases, summaries, bins=(1, 2, 4))
        self.assertIn("1-1 sessions", r["bins"])
        self.assertEqual(r["by_agent"]["a"]["1-1 sessions"], 100.0)
        self.assertEqual(r["by_agent"]["b"]["1-1 sessions"], 80.0)
        # 最后一档必须开放（N+），5 个 session 的用例有归属而不是被丢弃
        last = r["bins"][-1]
        self.assertTrue(last.endswith("+ sessions"), r["bins"])
        self.assertEqual(r["by_agent"]["a"][last], 50.0)
        self.assertEqual(r["by_agent"]["b"][last], 30.0)


if __name__ == "__main__":
    unittest.main()


class TestMemoryEvolution(unittest.TestCase):
    """记忆演变轨迹（发散点）：把'写入/更新/拒绝'变成过程级证据。"""

    def _run(self, name, case):
        from membench.agents import create_agent
        from membench.runner import run_case
        return run_case(create_agent(name), case, run_index=1,
                        workroot=tempfile.mkdtemp())

    def setUp(self):
        self.case = load_cases([os.path.join(PKG, "cases")])[0]
        for c in load_cases([os.path.join(PKG, "cases")]):
            if c.case_id == "upd-01-address":
                self.case = c

    def test_evolution_separates_failure_modes(self):
        nomem = self._run("nomem", self.case)
        naive = self._run("naive", self.case)
        smart = self._run("smart", self.case)
        evo_n = nomem.evidence["memory_evolution"]
        evo_v = naive.evidence["memory_evolution"]
        evo_s = smart.evidence["memory_evolution"]
        # nomem：从未写入 → 写失败
        self.assertTrue(all(e["added"] == [] and e["removed"] == [] for e in evo_n))
        # naive：写入但从不删除 → 该删未删（边界/遗忘失败）
        self.assertTrue(all(e["removed"] == [] for e in evo_v))
        self.assertGreater(sum(len(e["added"]) for e in evo_v), 0)
        # smart：更新时新值写入 + 旧值删除
        self.assertTrue(any(e["added"] and e["removed"] for e in evo_s))
        # 演变轨迹的 removed 应恰为旧地址（FAMA 语义闭环）
        removed_all = {x for e in evo_s for x in e["removed"]}
        self.assertIn("北京市海淀区中关村大街1号", "".join(removed_all))

    def test_summary_counts_memory_ops(self):
        from membench.agents import create_agent
        from membench.runner import run_suite
        out = tempfile.mkdtemp()
        cases = [self.case]
        s = run_suite(create_agent("naive"), cases, out_dir=out, runs=1, quiet=True)
        self.assertGreater(s["memory_ops"]["writes"], 0)
        self.assertEqual(s["memory_ops"]["deletes"], 0)  # naive 从不删除
        shutil.rmtree(out, ignore_errors=True)

    def test_chain_update_discriminates(self):
        """RULER-VT 风格链式换号：终值才对，中间值按 FAMA 判 improper_reuse。"""
        from membench.generator import generate
        from membench.schema import parse_case
        chain = [c for c in generate(variants=1, seed=3)
                 if c["case_id"].startswith("gen-upd-chain")][0]
        case = parse_case({"schema_version": 1, **chain})
        smart = self._run("smart", case)
        naive = self._run("naive", case)
        self.assertEqual(smart.score, 1.0)
        self.assertEqual(naive.rows[0]["verdict"], "improper_reuse")
