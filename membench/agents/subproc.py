# -*- coding: utf-8 -*-
"""外部智能体适配器：以子进程方式驱动任意实现了 stdio-JSONL 协议的程序。

协议（每行一个 JSON 对象）：
  harness -> agent:
    {"type": "session_start", "session_id": "..."}
    {"type": "user", "content": "..."}
    {"type": "memory_dump_request"}
    {"type": "session_end"}
  agent -> harness:
    {"type": "assistant", "content": "..."}          （对每条 user 恰好回复一次）
    {"type": "memory", "items": ["..."]}             （对 memory_dump_request 回复一次）
    {"type": "error", "message": "..."}              （可选，报告内部错误）

环境变量：子进程的 cwd 与 MEMBENCH_WORKDIR 均为本次评测沙箱目录。
参考实现见 examples/echo-agent.py。
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
from typing import List, Optional

from .base import AgentAdapter, AgentError


class SubprocAgent(AgentAdapter):
    def __init__(self, name: str, cmd: List[str], timeout: float = 60.0) -> None:
        self.name = name
        self.cmd = cmd
        self.timeout = timeout
        self._proc: Optional[subprocess.Popen] = None
        self._workdir = "."

    # ---- 进程管理 --------------------------------------------------------
    def _ensure_started(self) -> None:
        if self._proc is None or self._proc.poll() is not None:
            env = dict(os.environ)
            env["MEMBENCH_WORKDIR"] = os.path.abspath(self._workdir)
            self._proc = subprocess.Popen(
                self.cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, cwd=self._workdir, env=env,
                text=True, encoding="utf-8", bufsize=1)

    def _send(self, obj: dict) -> None:
        self._ensure_started()
        assert self._proc is not None and self._proc.stdin is not None
        try:
            self._proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
            self._proc.stdin.flush()
        except BrokenPipeError as e:
            raise AgentError("[%s] 智能体进程已退出: %s" % (self.name, _stderr_tail(self._proc))) from e

    def _recv(self) -> dict:
        assert self._proc is not None and self._proc.stdout is not None
        result = {}

        def reader():
            assert self._proc is not None and self._proc.stdout is not None
            line = self._proc.stdout.readline()
            result["line"] = line

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        t.join(self.timeout)
        if t.is_alive():
            raise AgentError("[%s] 等待回复超时（>%ss）" % (self.name, self.timeout))
        line = result.get("line")
        if not line:
            raise AgentError("[%s] 智能体提前退出: %s" % (self.name, _stderr_tail(self._proc)))
        try:
            return json.loads(line)
        except json.JSONDecodeError as e:
            raise AgentError("[%s] 回复不是合法 JSON: %r" % (self.name, line[:200])) from e

    # ---- AgentAdapter 接口 ------------------------------------------------
    def new_episode(self, workdir: str) -> None:
        self.close()
        self._workdir = workdir

    def session_start(self, session_id: str) -> None:
        self._send({"type": "session_start", "session_id": session_id})

    def send_user(self, content: str) -> str:
        self._send({"type": "user", "content": content})
        msg = self._recv()
        if msg.get("type") == "assistant":
            return str(msg.get("content", ""))
        if msg.get("type") == "error":
            raise AgentError("[%s] %s" % (self.name, msg.get("message", "")))
        raise AgentError("[%s] 意外的协议消息: %r" % (self.name, msg))

    def session_end(self) -> None:
        self._send({"type": "session_end"})

    def memory_dump(self) -> Optional[List[str]]:
        try:
            self._send({"type": "memory_dump_request"})
            msg = self._recv()
        except AgentError:
            return None
        if msg.get("type") == "memory":
            return [str(x) for x in (msg.get("items") or [])]
        return None

    def close(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()
        self._proc = None


def _stderr_tail(proc: subprocess.Popen) -> str:
    try:
        if proc.stderr is not None:
            err = proc.stderr.read() if hasattr(proc.stderr, "read") else ""
            return (err or "")[-300:]
    except Exception:
        pass
    return "(无 stderr)"
