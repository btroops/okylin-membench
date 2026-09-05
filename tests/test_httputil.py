# -*- coding: utf-8 -*-
"""httputil.opener_for：回环地址绕过代理（N+22 回归覆盖）。

行为级验证：即使环境代理指向不可达地址，回环请求也必须直连成功——
这正是 N+21 轮"测试套件 1F+3E"事故的根因场景。
"""
import http.server
import os
import threading
import unittest

from membench.httputil import opener_for

_PROXY_ENV_KEYS = ("http_proxy", "https_proxy", "all_proxy",
                   "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                   "no_proxy", "NO_PROXY")


class _OKHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


class OpenerForTest(unittest.TestCase):
    def setUp(self):
        self.server = http.server.HTTPServer(("127.0.0.1", 0), _OKHandler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self._saved = {k: os.environ.get(k) for k in _PROXY_ENV_KEYS}

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _poison_proxy_env(self):
        # 指向不可达地址（TEST-NET-1），模拟 N+21 事故时"代理不可达"的环境
        os.environ["http_proxy"] = "http://192.0.2.1:7890"
        os.environ["https_proxy"] = "http://192.0.2.1:7890"
        os.environ.pop("no_proxy", None)
        os.environ.pop("NO_PROXY", None)

    def test_loopback_bypasses_env_proxy(self):
        self._poison_proxy_env()
        op = opener_for("http://127.0.0.1:%d/v1" % self.port)
        self.assertIsNotNone(op)
        with op.open("http://127.0.0.1:%d/" % self.port, timeout=3) as resp:
            self.assertEqual(resp.status, 200)

    def test_localhost_and_ipv6_covered(self):
        self.assertIsNotNone(opener_for("http://localhost:%d/v1" % self.port))
        self.assertIsNotNone(opener_for("http://[::1]:%d/v1" % self.port))

    def test_remote_keeps_env_proxy(self):
        self.assertIsNone(opener_for("https://api.example.com/v1"))


if __name__ == "__main__":
    unittest.main()
