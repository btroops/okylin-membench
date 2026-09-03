# -*- coding: utf-8 -*-
"""深入回归：--judge openai 完整链路（CLI）、路径逃逸拦截、重复 ID 拒绝、
report 单目录、按维度过滤、fs 探针运行时防线。"""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from membench.loader import load_cases
from membench.schema import SchemaError, parse_case
from membench.scoring import evaluate_probe

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(PKG, "cases")


def _case_dict(probes, case_id="x-1", dimension="recall", **extra):
    d = {
        "case_id": case_id, "dimension": dimension, "title": "t",
        "sessions": [{"session_id": "s1", "turns": ["a"]}],
        "probes": probes,
    }
    d.update(extra)
    return d


class _VerdictHandler(BaseHTTPRequestHandler):
    """返回固定 LLM judge 裁决的假 OpenAI 兼容服务。"""

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(n)
        payload = json.dumps({
            "choices": [{"message": {"content":
                '{"verdict": "miss", "score": 0.3, "reason": "LLM裁决：回答不完整"}'}}]
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *a):
        pass


class TestJudgeWiring(unittest.TestCase):
    """回归：--judge openai 必须真实生效（曾经被静默忽略）。"""

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _VerdictHandler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_judge_flag_takes_effect(self):
        import subprocess
        # ret-02 含 free 探针吗？——构造一个只含 free 探针的临时用例集
        tmp = tempfile.mkdtemp()
        case = _case_dict([{
            "probe_id": "p1", "type": "free", "after_session": "s1",
            "question": "我叫什么？",
            "expected": {"must_include": ["小明"]},
        }])
        with open(os.path.join(tmp, "c.yaml"), "w", encoding="utf-8") as f:
            import yaml
            yaml.safe_dump(case, f, allow_unicode=True)
        out = os.path.join(tmp, "res")
        r = subprocess.run(
            [sys.executable, "-m", "membench.cli", "run",
             "--agent", "nomem", "--cases", tmp, "--runs", "1", "-o", out,
             "--judge", "openai",
             "--judge-base-url", "http://127.0.0.1:%d/v1" % self.port,
             "--judge-model", "fake", "--quiet"],
            cwd=PKG, capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr)
        result = json.load(open(os.path.join(out, "nomem", "runs", "run01", "x-1.json")))
        row = result["rows"][0]
        self.assertEqual(row["judge"], "llm", "--judge openai 未生效，仍为确定性评分")
        self.assertEqual(row["verdict"], "miss")
        self.assertAlmostEqual(row["score"], 0.3)
        shutil.rmtree(tmp, ignore_errors=True)


class TestSandboxPathGuard(unittest.TestCase):
    def test_reject_absolute_fs_path(self):
        with self.assertRaises(SchemaError):
            parse_case(_case_dict([{
                "probe_id": "p1", "type": "fs",
                "expected": {"file_exists": ["/etc/passwd"]},
            }]))

    def test_reject_parent_escape(self):
        with self.assertRaises(SchemaError):
            parse_case(_case_dict([{
                "probe_id": "p1", "type": "fs",
                "expected": {"file_exists": ["../../etc/passwd"]},
            }], dimension="task_reuse"))

    def test_reject_setup_file_escape(self):
        with self.assertRaises(SchemaError):
            parse_case(_case_dict([{
                "probe_id": "p1", "type": "slot",
                "expected": {"must_include": ["x"]},
            }], setup_files={"/root/.bashrc": "evil"}))

    def test_fs_runtime_guard(self):
        """绕过 parse_case 直接构造 Case 时，运行时也要拦截。"""
        from membench.schema import Case, Expected, Probe, Session, Turn
        case = Case(case_id="evil", dimension="retention", title="t",
                    sessions=[Session(session_id="s1", turns=[Turn("user", "a")])],
                    probes=[Probe(probe_id="p1", type="fs",
                                  expected=Expected(file_exists=["/etc/passwd"]))])
        row = evaluate_probe(case.probes[0], case, reply="",
                             memory_items=None, workdir="/tmp")
        self.assertEqual(row.verdict, "not_evaluable")
        self.assertIn("拦截", row.reason)


class TestDuplicateIds(unittest.TestCase):
    def test_duplicate_probe_id_rejected(self):
        probes = [{"probe_id": "p1", "type": "slot", "expected": {"must_include": ["x"]}},
                  {"probe_id": "p1", "type": "slot", "expected": {"must_include": ["y"]}}]
        with self.assertRaises(SchemaError):
            parse_case(_case_dict(probes))

    def test_duplicate_session_id_rejected(self):
        d = _case_dict([{"probe_id": "p1", "type": "slot",
                         "expected": {"must_include": ["x"]}}])
        d["sessions"] = [{"session_id": "s1", "turns": ["a"]},
                         {"session_id": "s1", "turns": ["b"]}]
        with self.assertRaises(SchemaError):
            parse_case(d)


class TestCliMatrix(unittest.TestCase):
    """上次未覆盖的 CLI 分支。"""

    def _cli(self, *args):
        import subprocess
        return subprocess.run([sys.executable, "-m", "membench.cli", *args],
                              cwd=PKG, capture_output=True, text=True, timeout=300)

    def test_report_single_dir(self):
        out = tempfile.mkdtemp()
        r = self._cli("run", "--agent", "smart", "--filter", "ret-01",
                      "--runs", "1", "-o", out, "--quiet")
        self.assertEqual(r.returncode, 0, r.stderr)
        r2 = self._cli("report", os.path.join(out, "smart"), "-o", out)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertTrue(os.path.exists(os.path.join(out, "comparison", "report.html")))

    def test_filter_by_dimension_and_tag(self):
        out = tempfile.mkdtemp()
        r = self._cli("run", "--agent", "smart", "--filter", "boundary_refusal",
                      "--runs", "1", "-o", out, "--quiet")
        self.assertEqual(r.returncode, 0, r.stderr)
        run_dir = os.path.join(out, "smart", "runs", "run01")
        files = os.listdir(run_dir)
        self.assertTrue(files)
        self.assertTrue(all(f.startswith("bnd-") for f in files),
                        "维度过滤失效: %s" % files)

    def test_keep_workdir(self):
        out = tempfile.mkdtemp()
        r = self._cli("run", "--agent", "smart", "--filter", "ret-01",
                      "--runs", "1", "-o", out, "--keep-workdir", "--quiet")
        self.assertEqual(r.returncode, 0, r.stderr)
        # 保留的工作目录位于 runs/run01 下
        found = any(d.startswith("membench_") for _r, ds, _f in
                    os.walk(os.path.join(out, "smart", "runs")) for d in ds)
        self.assertTrue(found, "--keep-workdir 未保留沙箱目录")

    def test_builtin_suite_still_valid(self):
        r = self._cli("validate")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("31 个用例", r.stdout)


if __name__ == "__main__":
    unittest.main()
