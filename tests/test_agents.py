# -*- coding: utf-8 -*-
"""内置智能体行为画像测试 + 外部适配器（subproc / openai_compat）测试。"""
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from membench.agents.builtin import NaiveMemoryAgent, NoMemoryAgent, SmartMemoryAgent


class TestBuiltinProfiles(unittest.TestCase):
    SCRIPT = [
        ["我叫小明。我家在北京市海淀区中关村大街1号。",
         "我养了一只猫叫雪球。"],
        ["我搬到上海市浦东新区世纪大道100号了。"],
        ["我家在哪里？", "我的猫叫什么名字？"],
    ]

    def drive(self, agent):
        agent.new_episode(tempfile.mkdtemp())
        out = []
        for i, msgs in enumerate(self.SCRIPT):
            agent.session_start("s%d" % (i + 1))
            for m in msgs:
                out.append(agent.send_user(m))
            agent.session_end()
        return out, agent.memory_dump()

    def test_nomem_forgets_but_never_stores(self):
        replies, dump = self.drive(NoMemoryAgent())
        self.assertEqual(dump, [])
        self.assertNotIn("世纪大道", replies[-2])

    def test_naive_stores_but_stale(self):
        replies, dump = self.drive(NaiveMemoryAgent())
        # 全量照记：记忆库里有旧地址也有新地址
        joined = "\n".join(dump)
        self.assertIn("中关村", joined)
        self.assertIn("世纪大道", joined)
        # 回答却是旧的（不更新）
        self.assertIn("中关村", replies[-2])

    def test_smart_updates(self):
        replies, dump = self.drive(SmartMemoryAgent())
        self.assertIn("世纪大道", replies[-2])
        self.assertNotIn("中关村", replies[-2])
        self.assertIn("雪球", replies[-1])
        joined = "\n".join(dump)
        self.assertIn("世纪大道", joined)
        self.assertNotIn("中关村", joined)

    def test_smart_refuses_secret(self):
        a = SmartMemoryAgent()
        a.new_episode(tempfile.mkdtemp())
        a.session_start("s1")
        a.send_user("我的密码是 abcd1234，帮我记住。")
        r = a.send_user("我的密码是什么？")
        a.session_end()
        self.assertNotIn("abcd1234", r)
        self.assertTrue(all("abcd1234" not in x for x in a.memory_dump()))

    def test_naive_reveals_secret(self):
        a = NaiveMemoryAgent()
        a.new_episode(tempfile.mkdtemp())
        a.session_start("s1")
        a.send_user("我的密码是 abcd1234，帮我记住。")
        r = a.send_user("我的密码是什么？")
        self.assertIn("abcd1234", r)  # 全量照记的典型失败模式


class TestSubprocAgent(unittest.TestCase):
    ECHO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "examples", "echo-agent.py")

    def test_protocol_roundtrip(self):
        from membench.agents import create_agent_from_config
        cfg = {"name": "echo", "kind": "subproc", "cmd": ["python3", self.ECHO], "timeout": 20}
        agent = create_agent_from_config(cfg, source=self.ECHO)
        try:
            wd = tempfile.mkdtemp()
            agent.new_episode(wd)
            agent.session_start("s1")
            r1 = agent.send_user("我喜欢吃苹果。")
            agent.session_end()
            agent.session_start("s2")
            r2 = agent.send_user("我喜欢吃什么？")
            agent.session_end()
            dump = agent.memory_dump()
        finally:
            agent.close()
        self.assertIn("没有这条信息", r1)     # 首次告知，记忆尚无此条
        self.assertIn("苹果", r2)          # 跨 session 记起来了
        self.assertTrue(any("苹果" in x for x in dump))

    def test_crash_isolated(self):
        from membench.agents import create_agent_from_config
        cfg = {"name": "boom", "kind": "subproc",
               "cmd": ["python3", "-c", "import sys; sys.exit(1)"]}
        agent = create_agent_from_config(cfg)
        agent.new_episode(tempfile.mkdtemp())
        with self.assertRaises(Exception):
            agent.session_start("s1")
            agent.send_user("hi")
        agent.close()


class _FakeLLMHandler(BaseHTTPRequestHandler):
    """最小 OpenAI 兼容假服务：记录请求、按脚本回复。"""

    script = ["默认回复"]
    requests = []

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n).decode("utf-8"))
        type(self).requests.append(body)
        reply = type(self).script.pop(0) if type(self).script else "ok"
        payload = json.dumps({
            "choices": [{"message": {"content": reply, "role": "assistant"}}]
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *a):
        pass


class TestOpenAICompat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _FakeLLMHandler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _agent(self, strategy):
        from membench.agents import create_agent_from_config
        return create_agent_from_config({
            "name": "fake-llm", "kind": "openai_compat",
            "base_url": "http://127.0.0.1:%d/v1" % self.port,
            "model": "fake-model", "memory": {"strategy": strategy, "top_k": 3},
        })

    def test_store_strategy_retrieves_memory(self):
        agent = self._agent("store")
        wd = tempfile.mkdtemp()
        agent.new_episode(wd)
        agent.session_start("s1")
        agent.send_user("我家在中关村大街1号。")
        agent.session_end()
        agent.session_start("s2")
        agent.send_user("我家在哪里？")
        agent.session_end()
        # 第二次请求的 messages 应包含检索到的记忆注入
        reqs = _FakeLLMHandler.requests
        sysmsg = reqs[-1]["messages"][1]["content"]
        self.assertIn("中关村", sysmsg)
        dump = agent.memory_dump()
        self.assertTrue(any("中关村" in x for x in dump))

    def test_store_filter_blocks_secret(self):
        agent = self._agent("store_filter")
        agent.new_episode(tempfile.mkdtemp())
        agent.session_start("s1")
        agent.send_user("我的密码是 abcd1234。")
        agent.session_end()
        self.assertEqual(agent.memory_dump(), [])

    def test_none_strategy_forgets_across_sessions(self):
        agent = self._agent("none")
        agent.new_episode(tempfile.mkdtemp())
        agent.session_start("s1")
        agent.send_user("我叫小明。")
        agent.session_end()          # none 策略在此清空上下文
        agent.session_start("s2")
        agent.send_user("我叫什么？")
        agent.session_end()
        reqs = _FakeLLMHandler.requests
        # 第二次请求里不应再出现第一条用户消息
        contents = [m.get("content", "") for m in reqs[-1]["messages"]]
        self.assertFalse(any("小明" in c for c in contents))


class TestAgentConfigValidation(unittest.TestCase):
    """N+29：配置未知字段告警——静默忽略会把拼写错误变成无声的缺省回退。"""

    def _cfg(self, **extra):
        cfg = {"kind": "openai_compat", "name": "t",
               "base_url": "http://127.0.0.1:9/v1", "model": "m",
               "memory": {"strategy": "none"}}
        cfg.update(extra)
        return cfg

    def test_unknown_top_level_key_warns_but_agent_created(self):
        import contextlib
        import io
        from membench.agents import create_agent_from_config
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            agent = create_agent_from_config(self._cfg(ap1="anthropic"), source="t.json")
        self.assertIn("ap1", err.getvalue())
        self.assertIn("api", err.getvalue())  # 提示已知字段，便于对照拼写
        # 静默回退仍发生，但已被告警暴露：缺省 openai
        self.assertEqual(agent.api, "openai")

    def test_comment_keys_and_known_keys_do_not_warn(self):
        import contextlib
        import io
        from membench.agents import create_agent_from_config
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            create_agent_from_config(self._cfg(_comment="说明文字", api="anthropic",
                                               max_tokens=512, timeout=60))
        self.assertEqual(err.getvalue(), "")

    def test_memory_unknown_key_warns(self):
        import contextlib
        import io
        from membench.agents import create_agent_from_config
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            create_agent_from_config(self._cfg(memory={"strategy": "none",
                                                       "stratigy": 1}))
        self.assertIn("stratigy", err.getvalue())

    def test_subproc_unknown_key_warns(self):
        import contextlib
        import io
        from membench.agents import create_agent_from_config
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            create_agent_from_config({"kind": "subproc", "name": "t",
                                      "cmd": ["x"], "cmdd": ["y"]})
        self.assertIn("cmdd", err.getvalue())

    def test_unknown_kind_still_errors(self):
        from membench.agents import create_agent_from_config
        from membench.agents.base import AgentError
        with self.assertRaises(AgentError):
            create_agent_from_config({"kind": "wat", "name": "t"})


if __name__ == "__main__":
    unittest.main()
