#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第三方智能体接入示例：实现 membench stdio-JSONL 协议的最小智能体。

该脚本演示外部智能体如何被 membench 评测：
每行一个 JSON 对象，处理 harness 发来的消息并对 user 消息回复一次。

用下面的 agent 配置（agents/echo.agent.json）即可评测本脚本：
  {"name": "echo", "kind": "subproc", "cmd": ["python3", "examples/echo-agent.py"]}

运行:  membench run --agent agents/echo.agent.json --cases cases --filter ret-01
"""
import json
import re
import sys

# 简单演示记忆：session 结束时把本 session 的用户消息存档（带来源 session）
memory = []          # [(session_id, content)]
session_buffer = []  # 当前 session 的未落库消息
last_trace = []      # 最近一次回答使用的记忆（供 retrieval_trace_request 查询）
current_session = ""


def answer(content: str):
    """极简策略：回放与问题字符重合度最高的历史消息。

    返回 (回复, 检索追踪)：追踪记录被回放消息及其来源 session。"""
    if content.startswith("/write"):
        return "已写入。", []
    best, best_score, best_sid = None, 0.0, None
    stop = set(" ，。？！.,?!我的请帮\n")
    q = set(content) - stop
    for sid, item in memory:
        score = len(q & set(item)) / max(len(q), 1)
        if score > best_score:
            best, best_score, best_sid = item, score, sid
    if best is not None and best_score > 0.3:
        return ("根据你之前说的：" + best,
                [{"content": best, "session_origin": best_sid}])
    return "抱歉，我的记忆里没有这条信息。", []


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue
    mtype = msg.get("type")
    if mtype == "session_start":
        session_buffer = []
        current_session = msg.get("session_id", "")
    elif mtype == "user":
        content = msg.get("content", "")
        reply, last_trace = answer(content)
        session_buffer.append((current_session, content))
        print(json.dumps({"type": "assistant", "content": reply}, ensure_ascii=False), flush=True)
    elif mtype == "session_end":
        memory.extend(session_buffer)
        session_buffer = []
    elif mtype == "memory_dump_request":
        print(json.dumps({"type": "memory", "items": [c for _s, c in memory]},
                         ensure_ascii=False), flush=True)
    elif mtype == "retrieval_trace_request":
        print(json.dumps({"type": "retrieval_trace", "items": last_trace},
                         ensure_ascii=False), flush=True)
