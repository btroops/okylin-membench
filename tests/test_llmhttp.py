# -*- coding: utf-8 -*-
"""llmhttp 双 wire format 单测（N+26）。

用 stdlib http.server 在 127.0.0.1 随机端口起 fake LLM 端点，行为级断言
openai / anthropic 两种格式各自的请求路径、鉴权头、请求体与响应解析。
回环目标经 httputil.opener_for 绕过环境代理，测试不受宿主代理影响。
"""
import http.server
import json
import os
import threading
import unittest

from membench import llmhttp
from membench.httputil import opener_for

FAKE_REPLY = "好的，已记住。"
_PROXY_ENV_KEYS = ("http_proxy", "https_proxy", "all_proxy",
                   "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                   "no_proxy", "NO_PROXY")


class _FakeLLM(http.server.BaseHTTPRequestHandler):
    """记录最近一次请求（头名转小写），按路径返回对应格式的固定响应。"""

    last = None

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        _FakeLLM.last = {"path": self.path,
                         "headers": {k.lower(): v for k, v in self.headers.items()},
                         "body": body}
        if self.path.endswith("/chat/completions"):
            resp = {"choices": [{"message": {"content": FAKE_REPLY}}]}
        elif self.path.endswith("/v1/messages"):
            resp = {"content": [{"type": "text", "text": FAKE_REPLY}]}
        else:
            resp = {"unexpected": True}
        data = json.dumps(resp).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class _ErrorLLM(http.server.BaseHTTPRequestHandler):
    """始终返回 HTTP 500 + JSON 错误体。"""

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        data = json.dumps({"error": {"message": "boom"}}).encode("utf-8")
        self.send_response(500)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class LLMHTTPFormatTest(unittest.TestCase):
    def setUp(self):
        self.server = http.server.HTTPServer(("127.0.0.1", 0), _FakeLLM)
        self.port = self.server.server_address[1]
        self.base = "http://127.0.0.1:%d" % self.port
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self._saved = {k: os.environ.get(k) for k in _PROXY_ENV_KEYS}
        _FakeLLM.last = None

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _msgs(self):
        return [{"role": "system", "content": "你是助手。"},
                {"role": "user", "content": "你好"}]

    # ---- openai 格式 -------------------------------------------------------
    def test_openai_request_shape(self):
        out = llmhttp.chat(self.base + "/v1", "openai", "m1", self._msgs(),
                           api_key="sk-1", temperature=0.3, timeout=5,
                           opener=opener_for(self.base))
        self.assertEqual(out, FAKE_REPLY)
        req = _FakeLLM.last
        self.assertEqual(req["path"], "/v1/chat/completions")
        self.assertEqual(req["headers"]["authorization"], "Bearer sk-1")
        self.assertNotIn("x-api-key", req["headers"])
        self.assertEqual(req["body"], {"model": "m1",
                                       "messages": self._msgs(),
                                       "temperature": 0.3})

    def test_openai_without_key_has_no_auth_header(self):
        llmhttp.chat(self.base + "/v1", "openai", "m1", self._msgs(),
                     timeout=5, opener=opener_for(self.base))
        self.assertNotIn("authorization", _FakeLLM.last["headers"])

    # ---- anthropic 格式 ----------------------------------------------------
    def test_anthropic_request_shape(self):
        out = llmhttp.chat(self.base, "anthropic", "m2", self._msgs(),
                           api_key="ak-2", temperature=0.1, timeout=5,
                           opener=opener_for(self.base))
        self.assertEqual(out, FAKE_REPLY)
        req = _FakeLLM.last
        self.assertEqual(req["path"], "/v1/messages")
        h = req["headers"]
        self.assertEqual(h["x-api-key"], "ak-2")
        self.assertEqual(h["authorization"], "Bearer ak-2")
        self.assertEqual(h["anthropic-version"], llmhttp.ANTHROPIC_VERSION)
        body = req["body"]
        # system 拆为顶层字段，messages 中不再有 system 角色
        self.assertEqual(body["system"], "你是助手。")
        self.assertEqual(body["messages"], [{"role": "user", "content": "你好"}])
        self.assertEqual(body["max_tokens"], llmhttp.DEFAULT_MAX_TOKENS)

    def test_anthropic_merges_consecutive_same_roles(self):
        msgs = [{"role": "system", "content": "s1"},
                {"role": "user", "content": "a"},
                {"role": "user", "content": "b"},
                {"role": "assistant", "content": "c"},
                {"role": "user", "content": "d"}]
        llmhttp.chat(self.base, "anthropic", "m2", msgs, max_tokens=64,
                     timeout=5, opener=opener_for(self.base))
        body = _FakeLLM.last["body"]
        self.assertEqual(body["system"], "s1")
        self.assertEqual(body["messages"], [
            {"role": "user", "content": "a\n\nb"},
            {"role": "assistant", "content": "c"},
            {"role": "user", "content": "d"},
        ])
        self.assertEqual(body["max_tokens"], 64)

    def test_anthropic_without_key_has_no_auth_headers(self):
        llmhttp.chat(self.base, "anthropic", "m2", self._msgs(),
                     timeout=5, opener=opener_for(self.base))
        h = _FakeLLM.last["headers"]
        self.assertNotIn("x-api-key", h)
        self.assertNotIn("authorization", h)
        self.assertIn("anthropic-version", h)

    # ---- 错误处理 ----------------------------------------------------------
    def test_unknown_api_rejected(self):
        with self.assertRaises(llmhttp.LLMHTTPError):
            llmhttp.chat(self.base, "gemini", "m", self._msgs())

    def test_http_error_wrapped_with_body(self):
        es = http.server.HTTPServer(("127.0.0.1", 0), _ErrorLLM)
        threading.Thread(target=es.serve_forever, daemon=True).start()
        try:
            with self.assertRaises(llmhttp.LLMHTTPError) as ctx:
                llmhttp.chat("http://127.0.0.1:%d/v1" % es.server_address[1],
                             "openai", "m", self._msgs(), timeout=5,
                             opener=opener_for(self.base))
            self.assertIn("HTTP 500", str(ctx.exception))
        finally:
            es.shutdown()
            es.server_close()

    def test_openai_bad_structure_wrapped(self):
        class _Bad(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                data = b'{"unexpected": 1}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        bs = http.server.HTTPServer(("127.0.0.1", 0), _Bad)
        threading.Thread(target=bs.serve_forever, daemon=True).start()
        try:
            with self.assertRaises(llmhttp.LLMHTTPError):
                llmhttp.chat("http://127.0.0.1:%d/v1" % bs.server_address[1],
                             "openai", "m", self._msgs(), timeout=5,
                             opener=opener_for(self.base))
        finally:
            bs.shutdown()
            bs.server_close()


class FactoryAnthropicRouteTest(unittest.TestCase):
    """工厂按 api 字段路由：anthropic 配置全链路走通到 /v1/messages。"""

    KEY_ENV = "_MEMBENCH_TEST_ANTHROPIC_KEY"

    def setUp(self):
        self.server = http.server.HTTPServer(("127.0.0.1", 0), _FakeLLM)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self._saved = {k: os.environ.get(k) for k in _PROXY_ENV_KEYS + (self.KEY_ENV,)}
        os.environ[self.KEY_ENV] = "ak-test"
        _FakeLLM.last = None

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_anthropic_config_end_to_end(self):
        from membench.agents import create_agent_from_config
        cfg = {"kind": "openai_compat", "name": "t-anthropic",
               "api": "anthropic",
               "base_url": "http://127.0.0.1:%d" % self.port,
               "model": "m2", "api_key_env": self.KEY_ENV,
               "memory": {"strategy": "none"}}
        agent = create_agent_from_config(cfg)
        agent.new_episode("/tmp")
        self.assertEqual(agent.send_user("你好"), FAKE_REPLY)
        self.assertEqual(_FakeLLM.last["path"], "/v1/messages")

    def test_legacy_config_defaults_to_openai(self):
        from membench.agents import create_agent_from_config
        cfg = {"kind": "openai_compat", "name": "t-openai",
               "base_url": "http://127.0.0.1:%d/v1" % self.port,
               "model": "m1", "memory": {"strategy": "none"}}
        agent = create_agent_from_config(cfg)
        agent.new_episode("/tmp")
        self.assertEqual(agent.send_user("你好"), FAKE_REPLY)
        self.assertEqual(_FakeLLM.last["path"], "/v1/chat/completions")


if __name__ == "__main__":
    unittest.main()
