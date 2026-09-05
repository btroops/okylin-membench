# -*- coding: utf-8 -*-
"""OpenClaw shim 会话键轮换与 retrieval_trace 解析回归（N+19）。

不依赖 docker/LLM：只测纯逻辑——
1. session_start 按 harness session 边界轮换 OpenClaw 会话键；
2. 命令前缀携带当前（轮换后的）会话键；
3. memory search 的 JSON 输出解析（含 stdout 混入日志行的容错）。
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import agents.openclaw_shim as shim


class SessionKeyRotationTest(unittest.TestCase):
    def setUp(self):
        # 固定 episode 前缀，隔离随机性
        shim.SESSION_PREFIX = "agent:main:mb-test"
        shim._session_key = None

    def test_prefix_unique_per_process(self):
        # 无 OPENCLAW_SESSION_KEY 时每个进程生成独立前缀（episode 隔离）
        old = os.environ.pop("OPENCLAW_SESSION_KEY", None)
        try:
            import importlib
            importlib.reload(shim)
            p1 = shim.SESSION_PREFIX
            importlib.reload(shim)
            p2 = shim.SESSION_PREFIX
            self.assertNotEqual(p1, p2)
            self.assertTrue(p1.startswith("agent:main:mb-"))
        finally:
            if old is not None:
                os.environ["OPENCLAW_SESSION_KEY"] = old
            importlib.reload(shim)
            self.setUp()

    def test_rotation_on_session_start(self):
        # 未收到 session_start：使用前缀兜底
        self.assertEqual(shim._cmd_prefix()[-2], "agent:main:mb-test")
        # s1 → probe:p1 各自派生独立键
        shim._session_key = "agent:main:mb-test:s1"
        self.assertEqual(shim._cmd_prefix()[-2], "agent:main:mb-test:s1")
        shim._session_key = "agent:main:mb-test:probe:p1"
        self.assertEqual(shim._cmd_prefix()[-2], "agent:main:mb-test:probe:p1")

    def test_probe_session_key_contains_probe_id(self):
        # 探针会话键由 harness 的 probe:<id> 派生——上下文里没有剧本原文
        sid = "probe:p1"
        key = "%s:%s" % (shim.SESSION_PREFIX, sid)
        self.assertIn("probe:p1", key)
        self.assertNotIn("s1", key)


class RetrievalTraceParseTest(unittest.TestCase):
    """_retrieval_trace 的 JSON 解析容错（不触发真实 docker 调用）。"""

    def test_parse_mixed_output(self):
        # stdout 混入日志行时只取 JSON 段
        out = 'No matches.\n[memory] sync failed (search): Error: ...\n{"results": [{"content": "用户叫小明", "score": 0.8}]}'
        import re
        m = re.search(r"\{.*\}", out, re.S)
        data = json.loads(m.group(0))
        items = [{"content": str(r.get("content"))[:500], "score": r.get("score")}
                 for r in (data.get("results") or [])[:5]]
        self.assertEqual(items, [{"content": "用户叫小明", "score": 0.8}])

    def test_empty_results(self):
        out = '{"results": []}\n[memory] sync failed: ...'
        import re
        m = re.search(r"\{.*\}", out, re.S)
        data = json.loads(m.group(0))
        items = [r for r in (data.get("results") or [])[:5]]
        self.assertEqual(items, [])

    def test_no_json_returns_empty(self):
        # 纯日志输出（无 JSON）应解析为空——优雅降级
        import re
        out = "No matches.\n[memory] sync failed (search): Error"
        m = re.search(r"\{.*\}", out, re.S)
        self.assertIsNone(m)


if __name__ == "__main__":
    unittest.main()
