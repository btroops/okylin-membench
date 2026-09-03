# -*- coding: utf-8 -*-
"""智能体适配器基类与协议定义。

评测只依赖该接口，任何智能体（内置/外部进程/LLM API）实现它即可被测：
    new_episode(workdir)   开始一次独立评测（新记忆、新沙箱）
    session_start(sid)     开始一个 session
    send_user(content)     发送一条 user 消息，返回 assistant 回复
    session_end()          结束当前 session（记忆应当"落库"的时机）
    memory_dump()          返回智能体持久化记忆条目列表；不支持则返回 None
    close()                释放资源
"""
from __future__ import annotations

from typing import List, Optional


class AgentError(RuntimeError):
    pass


class AgentAdapter:
    name = "agent"

    def new_episode(self, workdir: str) -> None:
        raise NotImplementedError

    def session_start(self, session_id: str) -> None:
        raise NotImplementedError

    def send_user(self, content: str) -> str:
        raise NotImplementedError

    def session_end(self) -> None:
        raise NotImplementedError

    def memory_dump(self) -> Optional[List[str]]:
        return None

    def retrieval_trace(self, query: str) -> Optional[List[dict]]:
        """可选：返回本次回答检索使用了哪些记忆及其来源 session。

        [{"content": "...", "session_origin": "s1"}, ...]
        返回 None 表示不支持检索追踪；返回 [] 表示检索为空。
        用于 LongMemEval 式"检索定位率"指标（从正确的 session 取记忆）。
        """
        return None

    def close(self) -> None:
        pass
