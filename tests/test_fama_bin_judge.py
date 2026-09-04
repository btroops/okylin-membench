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


class TestRetrievalTraceSubproc(unittest.TestCase):
    """subproc 协议扩展：外部智能体的检索追踪 + 能力探测降级。"""

    def test_echo_agent_reports_trace(self):
        from membench.agents import create_agent_from_config
        echo = os.path.join(PKG, "examples", "echo-agent.py")
        cfg = {"name": "echo", "kind": "subproc", "cmd": ["python3", echo], "timeout": 20}
        agent = create_agent_from_config(cfg, source=echo)
        try:
            wd = tempfile.mkdtemp()
            agent.new_episode(wd)
            agent.session_start("s1")
            agent.send_user("我喜欢吃苹果。")
            agent.session_end()
            agent.session_start("s2")
            agent.send_user("我喜欢吃什么？")
            trace = agent.retrieval_trace("我喜欢吃什么？")
            agent.session_end()
        finally:
            agent.close()
        assert trace is not None
        self.assertEqual(trace[0]["session_origin"], "s1")
        self.assertIn("苹果", trace[0]["content"])

    def test_unsupported_agent_degrades_to_none(self):
        from membench.agents import create_agent_from_config
        cfg = {"name": "boom", "kind": "subproc",
               "cmd": ["python3", "-c", "import sys; sys.exit(1)"]}
        agent = create_agent_from_config(cfg)
        agent.new_episode(tempfile.mkdtemp())
        self.assertIsNone(agent.retrieval_trace("q"))  # 探测失败 → None 且不再打扰
        self.assertIsNone(agent.retrieval_trace("q"))
        agent.close()


class TestDifficultyKnob(unittest.TestCase):
    """RULER 式难度旋钮：hard 变体兄弟值差异更小、无子串陷阱、区分度保持。"""

    def _sibling(self, case):
        exp = case["probes"][0]["expected"]
        return exp["must_include"][0], exp["must_not_include"][0]

    def test_hard_tightens_similarity_safely(self):
        import json
        from membench.generator import generate

        def diff(a, b):
            return sum(1 for x, y in zip(a, b) if x != y) + abs(len(a) - len(b))

        cases = generate(variants=1, seed=7)
        by_id = {c["case_id"]: c for c in cases}
        for base in ("gen-dis-cats", "gen-dis-ips", "gen-dis-name"):
            a, b = self._sibling(by_id[base + "-01"])
            a2, b2 = self._sibling(by_id[base + "-hard-01"])
            self.assertNotIn(a, b); self.assertNotIn(b, a)     # normal 无子串陷阱
            self.assertNotIn(a2, b2); self.assertNotIn(b2, a2)  # hard 亦然
            self.assertLess(diff(a2, b2), diff(a, b))           # 旋钮收得更紧
            self.assertGreater(diff(a2, b2), 0)                 # 但仍可区分


class TestFactLifecycle(unittest.TestCase):
    """Zep 式事实生命周期 + 全轨迹 staleness 扫描。"""

    def _case(self):
        return next(c for c in load_cases([os.path.join(PKG, "cases")])
                    if c.case_id == "upd-01-address")

    def _run(self, name):
        from membench.agents import create_agent
        from membench.runner import run_case
        return run_case(create_agent(name), self._case(), run_index=1,
                        workroot=tempfile.mkdtemp())

    def test_staleness_scan_discriminates(self):
        naive = self._run("naive")
        stale = [x for x in naive.rows if x["probe_id"] == "staleness_scan"]
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["verdict"], "improper_reuse")
        self.assertIn("该遗忘的没遗忘", stale[0]["reason"])
        # smart 覆盖旧值、nomem 从未写入 => staleness 行存在但全部通过（对称可见）
        for name in ("smart", "nomem"):
            r = self._run(name)
            stale = [x for x in r.rows if x["probe_id"] == "staleness_scan"]
            self.assertTrue(all(x["verdict"] == "correct" and x["score"] == 1.0
                                for x in stale), name)

    def test_summary_counts_staleness(self):
        from membench.agents import create_agent
        from membench.runner import run_suite
        out = tempfile.mkdtemp()
        s = run_suite(create_agent("naive"), [self._case()], out_dir=out,
                      runs=1, quiet=True)
        self.assertEqual(s["staleness_violations"], 1)
        shutil.rmtree(out, ignore_errors=True)

    def test_lifecycle_validation(self):
        from membench.schema import SchemaError, parse_case
        base = {"case_id": "x", "dimension": "dynamic_update", "title": "t",
                "sessions": [{"session_id": "s1", "turns": ["a"]},
                             {"session_id": "s2", "turns": ["b"]}],
                "probes": [{"probe_id": "p1", "type": "slot",
                            "expected": {"must_include": ["x"]}}]}
        with self.assertRaises(SchemaError):  # 引用不存在的 session
            parse_case({**base, "fact_lifecycle":
                        [{"value": "v", "valid_from": "s1", "valid_until": "s9"}]})
        with self.assertRaises(SchemaError):  # valid_from 在 valid_until 之后
            parse_case({**base, "fact_lifecycle":
                        [{"value": "v", "valid_from": "s2", "valid_until": "s1"}]})

    def test_lifecycle_fama_autoderived(self):
        """fact_lifecycle 时间轴自动推导 improper_reuse，无需手工 superseded_values。"""
        from membench.schema import parse_case
        from membench.scoring import evaluate_probe
        from membench import VERDICT_IMPROPER_REUSE
        case = parse_case({
            "case_id": "x", "dimension": "dynamic_update", "title": "t",
            "sessions": [{"session_id": "s1", "turns": ["a"]},
                         {"session_id": "s2", "turns": ["b"]}],
            "fact_lifecycle": [{"value": "旧值", "valid_from": "s1",
                                "valid_until": "s2"}],
            "probes": [{"probe_id": "p1", "type": "slot", "after_session": "s2",
                        "question": "q",
                        "expected": {"must_include": ["新值"],
                                     "must_not_include": ["旧值"]}}],
        })
        r = evaluate_probe(case.probes[0], case, reply="还是旧值",
                           memory_items=None, workdir=None)
        self.assertEqual(r.verdict, VERDICT_IMPROPER_REUSE)


class TestCriteriaFama(unittest.TestCase):
    """criteria 级 FAMA（Memora 公式）：max(0, MPA - λ·(1-FAA))。"""

    def _summary(self, agent, case_id=None):
        from membench.agents import create_agent
        from membench.runner import run_suite
        cases = load_cases([os.path.join(PKG, "cases")])
        if case_id:
            cases = [c for c in cases if c.case_id == case_id]
        return run_suite(create_agent(agent), cases, out_dir=tempfile.mkdtemp(),
                         runs=1, quiet=True)

    def test_boundary_case_fama(self):
        """bnd-01（纯 absence 判据）：naive 全违例 => FAMA=0；smart/nomem => 1。"""
        naive = self._summary("naive", "bnd-01-password")
        smart = self._summary("smart", "bnd-01-password")
        self.assertAlmostEqual(naive["fama_mean"], 0.0)
        self.assertAlmostEqual(smart["fama_mean"], 1.0)

    def test_update_case_fama(self):
        """upd-01（presence + absence 混合）：nomem 缺席守住了但 presence 失败
        => FAMA 不罚（λ 权衡）；naive 双失 => FAMA=0；smart 双过 => 1。"""
        nomem = self._summary("nomem", "upd-01-address")
        naive = self._summary("naive", "upd-01-address")
        smart = self._summary("smart", "upd-01-address")
        self.assertAlmostEqual(naive["fama_mean"], 0.0)
        self.assertAlmostEqual(smart["fama_mean"], 1.0)
        self.assertGreaterEqual(nomem["fama_mean"], 0.0)
        self.assertLess(nomem["fama_mean"], 0.5)  # presence 失败被 MPA 拉低

    def test_presence_only_case_fama_equals_score(self):
        """纯 presence 用例（λ=0）：FAMA == 普通得分（向后兼容性质）。"""
        smart = self._summary("smart", "ret-01-name-editor")
        case_score = [c["score"] for c in smart["per_case"]
                      if c["case_id"] == "ret-01-name-editor"][0]
        self.assertAlmostEqual(smart["fama_mean"] * 100, case_score, places=4)


class TestMemoryMaintenance(unittest.TestCase):
    """记忆维护双探针：去重（memory_max_count）+ 显式撤回。"""

    def _case(self, case_id):
        return next(c for c in load_cases([os.path.join(PKG, "cases")])
                    if c.case_id == case_id)

    def _run(self, name, case):
        from membench.agents import create_agent
        from membench.runner import run_case
        return run_case(create_agent(name), case, run_index=1,
                        workroot=tempfile.mkdtemp())

    def test_dedup_probe_catches_naive(self):
        r = self._run("naive", self._case("ret-05-dedup"))
        dedup = [x for x in r.rows if x["probe_id"] == "p1"]
        self.assertEqual(dedup[0]["verdict"], "improper_persistence")
        self.assertIn("出现 3 次", dedup[0]["reason"])

    def test_dedup_probe_passes_smart(self):
        r = self._run("smart", self._case("ret-05-dedup"))
        self.assertEqual(r.score, 1.0)  # 槽位覆盖天然去重

    def test_retraction_discriminates(self):
        case = self._case("upd-05-retract")
        naive = self._run("naive", case)
        smart = self._run("smart", case)
        self.assertLess(naive.score, 0.5)
        self.assertEqual(smart.score, 1.0)
        # naive 必须以 improper_reuse/miss 类失败，而非正确
        self.assertTrue(all(x["verdict"] != "correct"
                            for x in naive.rows if x["score"] == 0.0))


class TestDifficultyBreakdown(unittest.TestCase):
    def test_summary_has_difficulty_breakdown(self):
        from membench.agents import create_agent
        from membench.runner import run_suite
        cases = load_cases([os.path.join(PKG, "cases")])
        s = run_suite(create_agent("smart"), cases, out_dir=tempfile.mkdtemp(),
                      runs=1, quiet=True)
        self.assertTrue(s.get("difficulty_breakdown"))
        for d in ("easy", "medium", "hard"):
            self.assertIn(d, s["difficulty_breakdown"])


class TestDoctor(unittest.TestCase):
    """membench doctor：8 项环境自检在健康环境全过、退出码 0。"""

    def test_doctor_all_pass(self):
        from membench.doctor import run_checks
        checks = run_checks()
        names = {c["name"] for c in checks}
        self.assertEqual(names, {"python>=3.8", "pyyaml", "cases",
                                 "builtin-agents", "subproc-protocol",
                                 "tmp-writable", "utf8-stdout", "cjk-fonts"})
        fails = [c for c in checks if c["status"] == "FAIL"]
        self.assertEqual(fails, [], checks)


class TestEvidenceViewer(unittest.TestCase):
    def test_viewer_builds_and_links(self):
        from membench.agents import create_agent
        from membench.runner import run_suite
        from membench.report import build_evidence_viewer
        out = tempfile.mkdtemp()
        cases = load_cases([os.path.join(PKG, "cases")])[:3]
        run_suite(create_agent("smart"), cases, out_dir=out, runs=2, quiet=True)
        adir = os.path.join(out, "smart")
        ev = os.path.join(out, "evidence.html")
        build_evidence_viewer([adir], ev)
        doc = open(ev, encoding="utf-8").read()
        self.assertIn("逐用例证据查看器", doc)
        self.assertIn("badge", doc)
        self.assertIn("id='ev-smart-", doc)          # 用例锚点存在
        self.assertIn("<span class='badge", doc)      # 裁决徽章存在
        self.assertIn("记忆演变轨迹", doc)


class TestMemoryDiscipline(unittest.TestCase):
    """noise_max_count：跨 session 噪声累积检测（Letta Dreaming/A-MEM 演化质量）。"""

    def _case(self):
        return next(c for c in load_cases([os.path.join(PKG, "cases")])
                    if c.case_id == "ret-06-noise-discipline")

    def _run(self, name):
        from membench.agents import create_agent
        from membench.runner import run_case
        return run_case(create_agent(name), self._case(), run_index=1,
                        workroot=tempfile.mkdtemp())

    def test_naive_accumulates(self):
        r = self._run("naive")
        v = [x for x in r.rows if x["probe_id"] == "noise_scan"]
        self.assertGreaterEqual(len(v), 2)
        self.assertTrue(all(x["verdict"] == "improper_persistence" for x in v))

    def test_smart_disciplined(self):
        r = self._run("smart")
        v = [x for x in r.rows if x["probe_id"] == "noise_scan"]
        self.assertEqual(v, [])

    def test_nomem_trivially_passes(self):
        r = self._run("nomem")
        self.assertEqual(r.score, 1.0)
