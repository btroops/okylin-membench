# -*- coding: utf-8 -*-
"""生成器与 CLI 扩展（gen / 批量 agent 配置）回归测试。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from membench.generator import generate, templates
from membench.loader import load_cases
from membench.schema import parse_case

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N_TEMPLATES = sum(len(fns) for fns in templates().values())


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "membench.cli", *args],
        cwd=PKG, capture_output=True, text=True, timeout=300)


class TestGenerator(unittest.TestCase):
    def test_generates_valid_cases(self):
        for variant in (1, 3):
            cases = generate(variants=variant, seed=42)
            self.assertEqual(len(cases), variant * N_TEMPLATES)
            for c in cases:
                parse_case({"schema_version": 1, **c})  # 必须通过静态校验

    def test_expected_consistent_with_injected_values(self):
        """生成的 expected 必须与剧本里注入的值同源（抓标注漂移）。"""
        for c in generate(variants=3, seed=7):
            text = json.dumps(c, ensure_ascii=False)
            for p in c["probes"]:
                for v in p["expected"].get("must_include", []):
                    self.assertIn(v, text,
                                  "%s: expected 值 %r 不在剧本中" % (c["case_id"], v))

    def test_seed_reproducible(self):
        a = json.dumps(generate(variants=2, seed=123), ensure_ascii=False, sort_keys=True)
        b = json.dumps(generate(variants=2, seed=123), ensure_ascii=False, sort_keys=True)
        c = json.dumps(generate(variants=2, seed=124), ensure_ascii=False, sort_keys=True)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_generated_suite_discriminates(self):
        """生成用例跑两个内置智能体同样要有区分度。"""
        from membench.agents import create_agent
        from membench.runner import run_suite
        tmp = tempfile.mkdtemp()
        try:
            out = os.path.join(tmp, "cases")
            r = run_cli("gen", "-o", out, "--variants", "1", "--seed", "5")
            self.assertEqual(r.returncode, 0, r.stderr)
            cases = load_cases([out])
            self.assertGreaterEqual(len(cases), 9)
            summaries = []
            for name in ("smart", "nomem"):
                summaries.append(run_suite(create_agent(name), cases,
                                           out_dir=os.path.join(tmp, "res"),
                                           runs=1, quiet=True))
            by = {s["agent"]: s["overall"] for s in summaries}
            self.assertGreater(by["smart"], by["nomem"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestCliExtensions(unittest.TestCase):
    def test_gen_command(self):
        out = tempfile.mkdtemp()
        r = run_cli("gen", "-o", out, "--variants", "2", "--seed", "9")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("校验通过", r.stdout)
        n = sum(len(fs) for _d, _s, fs in os.walk(out))
        self.assertEqual(n, 2 * N_TEMPLATES)

    def test_batch_agent_file(self):
        out = tempfile.mkdtemp()
        batch = os.path.join(out, "batch.json")
        with open(batch, "w", encoding="utf-8") as f:
            json.dump([{"name": "b1", "kind": "builtin", "impl": "nomem"},
                       {"name": "b2", "kind": "builtin", "impl": "smart"}], f)
        r = run_cli("run", "--agent", batch, "--filter", "bnd-01",
                      "--runs", "1", "-o", os.path.join(out, "res"), "--quiet")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(os.path.join(out, "res", "b1", "summary.json")))
        self.assertTrue(os.path.exists(os.path.join(out, "res", "b2", "summary.json")))


if __name__ == "__main__":
    unittest.main()
