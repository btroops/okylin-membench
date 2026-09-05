# -*- coding: utf-8 -*-
"""OpenAI 兼容接口适配器（stdlib urllib 实现，便于离线单测）。

可对接任何 OpenAI Chat Completions 兼容端点（vLLM / Ollama / FastChat 等），
并支持可插拔的"记忆策略"，用于对比同一 LLM 在不同记忆策略下的表现：

  strategy = none       不做长期记忆（每次会话仅保留当前 session 上下文）
  strategy = full_log   全量历史拼进上下文（对照：窗口越大越贵）
  strategy = store      持久化用户消息到本地记忆库，按关键词重合度检索注入
  strategy = store_filter 同 store，但先过滤敏感信息（密码/验证码等）再入库

配置示例（agents/llm.agent.json）：
{
  "name": "qwen-store",
  "kind": "openai_compat",
  "base_url": "http://127.0.0.1:11434/v1",
  "model": "qwen2.5:7b",
  "api_key_env": "OPENAI_API_KEY",
  "memory": {"strategy": "store", "top_k": 5},
  "system_prompt": "你是 openKylin 桌面助手。",
  "temperature": 0.2
}
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Dict, List, Optional

from ..httputil import opener_for
from .base import AgentAdapter, AgentError
from .builtin import SECRET_RE

MEMORY_STRATEGIES = ("none", "full_log", "store", "store_filter")


class _MemoryStore:
    """极简长期记忆库：条目为字符串，检索按字符重合度取 top_k。"""

    def __init__(self, strategy: str, top_k: int = 5) -> None:
        self.strategy = strategy
        self.top_k = top_k
        self.items: List[str] = []

    def observe_user(self, content: str, session_open: bool) -> None:
        if not session_open and self.strategy == "none":
            return
        if self.strategy in ("none",):
            return
        if self.strategy == "store_filter" and SECRET_RE.search(content):
            return  # 敏感信息不入库
        self.items.append(content)

    def retrieve(self, query: str) -> List[str]:
        if not self.items:
            return []

        def score(item: str) -> float:
            qs = set(query) - set(" ，。？！.,?!我的请帮\n")
            return len(qs & set(item)) / max(len(qs), 1)

        ranked = sorted(range(len(self.items)), key=lambda i: -score(self.items[i]))
        picked = [self.items[i] for i in ranked[: self.top_k]
                  if score(self.items[i]) > 0.1]
        return picked

    def dump(self) -> List[str]:
        return list(self.items)


class OpenAICompatAgent(AgentAdapter):
    def __init__(self, name: str, base_url: str, model: str,
                 api_key: str = "", memory: Optional[dict] = None,
                 system_prompt: str = "你是 openKylin 桌面智能助手。",
                 temperature: float = 0.2, timeout: float = 120.0) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self._opener = opener_for(self.base_url)
        self.model = model
        self.api_key = api_key
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.timeout = timeout
        mem_cfg = memory or {}
        strategy = str(mem_cfg.get("strategy", "store"))
        if strategy not in MEMORY_STRATEGIES:
            raise AgentError("未知记忆策略: %s（可选 %s）" % (strategy, MEMORY_STRATEGIES))
        self.memory = _MemoryStore(strategy, top_k=int(mem_cfg.get("top_k", 5)))
        self._session_open = False
        self._history: List[Dict[str, str]] = []
        self._workdir = "."

    # ---- AgentAdapter -----------------------------------------------------
    def new_episode(self, workdir: str) -> None:
        self._history = []
        self.memory = _MemoryStore(self.memory.strategy, self.memory.top_k)
        self._session_open = False
        self._workdir = workdir

    def session_start(self, session_id: str) -> None:
        self._session_open = True

    def send_user(self, content: str) -> str:
        self.memory.observe_user(content, self._session_open)
        messages = self._build_messages(content)
        reply = self._chat(messages)
        self._history.append({"role": "user", "content": content})
        self._history.append({"role": "assistant", "content": reply})
        return reply

    def session_end(self) -> None:
        self._session_open = False
        if self.memory.strategy == "none":
            self._history = []  # 无记忆：清空上下文

    def memory_dump(self) -> Optional[List[str]]:
        if self.memory.strategy in ("none", "full_log"):
            return None
        return self.memory.dump()

    # ---- 内部 -------------------------------------------------------------
    def _build_messages(self, user_msg: str) -> List[Dict[str, str]]:
        msgs: List[Dict[str, str]] = [{"role": "system", "content": self.system_prompt}]
        if self.memory.strategy in ("store", "store_filter"):
            hits = self.memory.retrieve(user_msg)
            if hits:
                msgs.append({"role": "system",
                             "content": "以下是你在过去对话中记住的用户信息（可能不完全可靠，冲突时以最新为准）:\n- "
                                        + "\n- ".join(hits)})
        if self.memory.strategy == "full_log":
            msgs.extend(self._history)
        elif self.memory.strategy != "none":
            msgs.extend(self._history[-6:])   # 近期上下文窗口
        else:
            msgs.extend(self._history)        # none: history 在 session_end 清空，即当前 session 内可见
        msgs.append({"role": "user", "content": user_msg})
        return msgs

    def _chat(self, messages: List[Dict[str, str]]) -> str:
        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/chat/completions", data=payload,
            headers={"Content-Type": "application/json",
                     **({"Authorization": "Bearer " + self.api_key} if self.api_key else {})})
        try:
            open_fn = self._opener.open if self._opener else urllib.request.urlopen
            with open_fn(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise AgentError("[%s] 请求失败: %s" % (self.name, e)) from e
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise AgentError("[%s] 响应格式异常: %r" % (self.name, data)) from e
