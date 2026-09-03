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

    def close(self) -> None:
        pass
