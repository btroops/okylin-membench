#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenClaw 真实实例适配器（membench subproc 协议）。

把 membench 的 stdio-JSONL 协议对接到「容器内真实运行的 OpenClaw 实例」：

  harness -> shim:
    {"type": "session_start", "session_id": "..."}
    {"type": "user", "content": "..."}
    {"type": "memory_dump_request"}
    {"type": "retrieval_trace_request", "query": "..."}
    {"type": "session_end"}

  shim -> harness:
    {"type": "assistant", "content": "..."}        # 对每条 user 回复一次
    {"type": "memory", "items": ["..."]}            # memory_dump_request 回复
    {"type": "retrieval_trace", "items": [...]}     # 尽力而为，失败则空列表
    {"type": "error", "message": "..."}             # 可选

证据来源：OpenClaw 的记忆是磁盘上可读的 Markdown 文件（见 docs.openclaw.ai）：
  MEMORY.md  USER.md  DREAMS.md  memory/<date>.md
这些文件随容器启动挂载到宿主机目录（docker-compose 的 openclaw-workspace 卷），
shim 直接读取并作为 memory_dump 交给 membench 评分——这就是「真实实例」的证据。

依赖（宿主机侧，非容器内）：docker + 已 `docker compose up -d openclaw-gateway`。
"""

import json
import os
import shutil
import subprocess
import sys
import uuid

# ---------------------------------------------------------------------------
# 配置（均可通过环境变量覆盖；不设则用合理默认值）
# ---------------------------------------------------------------------------
COMPOSE_FILE = os.environ.get(
    "OPENCLAW_COMPOSE_FILE",
    os.path.join(os.path.dirname(__file__), "..", "docker", "openclaw", "docker-compose.yml"),
)
GATEWAY_TOKEN = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "membench-dev-token")
# 记忆文件所在宿主机目录（与 compose 中 openclaw-workspace 挂载路径一致）
WORKSPACE_DIR = os.environ.get(
    "OPENCLAW_WORKSPACE_DIR",
    os.path.join(os.path.dirname(__file__), "..", "docker", "openclaw", "openclaw-workspace"),
)
# 发送给 OpenClaw 的 agent 名（默认 main）
AGENT_NAME = os.environ.get("OPENCLAW_AGENT", "main")
# 干净记忆快照目录：每个 episode 开始时用它还原，杜绝跨用例污染
PRISTINE_DIR = os.environ.get(
    "OPENCLAW_PRISTINE_DIR",
    os.path.join(os.path.dirname(__file__), "..", "docker", "openclaw", "openclaw-pristine"),
)
# 是否在每个 episode 开始时重置记忆状态（默认开；设为 0 可关闭以做对照实验）
RESET_MEMORY = os.environ.get("OPENCLAW_RESET_MEMORY", "1") != "0"
# 每个 episode 使用独立会话键：`openclaw agent` 默认把全部调用累积进同一滚动
# 会话（agent:<id>:main），历史轮次会跨 episode 泄漏（实测 ret-01 第二轮跑分时
# 模型答"这条信息我早就记住了"）。新会话从零开始，从根源切断该泄漏；
# 可用 OPENCLAW_SESSION_KEY 固定会话键以便调试/对照。
SESSION_KEY = os.environ.get("OPENCLAW_SESSION_KEY") or (
    "agent:%s:mb-%s" % (AGENT_NAME, uuid.uuid4().hex[:12]))

# 已实测可用的调用形式：进入运行中的 gateway 容器执行 `openclaw agent`。
# 消息作为独立 argv 元素追加，不经 shell，无注入风险。
DEFAULT_CMD_PREFIX = [
    "docker", "compose", "-f", COMPOSE_FILE,
    "exec", "-T", "openclaw-gateway",
    "openclaw", "agent",
    "--agent", AGENT_NAME,
    "--session-key", SESSION_KEY,
    "--message",
]


def _reset_memory_state() -> None:
    """把 OpenClaw 的记忆状态还原为干净起点。

    membench 的 subproc 适配器在每个 episode 开始时会重启本进程
    （`new_episode()` → `close()`），因此「进程启动」即「新 episode」。
    隔离由两层共同完成：
      1) 会话层：本进程使用独立 SESSION_KEY（见上），新会话无历史轮次；
      2) 文件层：workspace（USER.md / memory/）按 agent 共享、跨会话持久，
         必须显式还原为干净模板，否则上一用例的事实会被下一用例读到。
    """
    if not RESET_MEMORY:
        return
    ws = os.path.abspath(WORKSPACE_DIR)
    if not os.path.isdir(ws):
        return
    # 1) 删除终态记忆文件（MEMORY.md / DREAMS.md 由 OpenClaw 自行重建）
    for fname in ("MEMORY.md", "DREAMS.md"):
        path = os.path.join(ws, fname)
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    # 2) 清空 memory/ 日记
    diary = os.path.join(ws, "memory")
    if os.path.isdir(diary):
        for fname in os.listdir(diary):
            if fname.endswith(".md"):
                try:
                    os.remove(os.path.join(diary, fname))
                except OSError:
                    pass
    # 3) USER.md 还原为空指令模板
    pristine = os.path.join(PRISTINE_DIR, "USER.md")
    if os.path.isfile(pristine):
        try:
            shutil.copyfile(pristine, os.path.join(ws, "USER.md"))
        except OSError:
            pass


def _run_openclaw(message: str) -> str:
    """把一条 user 消息发给 OpenClaw，返回助手回复文本。"""
    cmd = list(DEFAULT_CMD_PREFIX) + [message]
    proc = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,   # 关键：不得继承协议管道，防止子进程吞掉/阻塞 JSONL
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        timeout=420,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "openclaw 调用失败 (rc=%d): %s" % (proc.returncode, (proc.stderr or "").strip()[:500])
        )
    return (proc.stdout or "").strip()


# 记忆文件名优先级（靠前的更「稳定」，作为 memory_dump 主条目）
MEMORY_FILES = ["MEMORY.md", "USER.md", "DREAMS.md"]


def _read_memory_dump():
    """读取挂载出来的 OpenClaw 记忆文件，拼接为 items 列表。"""
    items = []
    ws = os.path.abspath(WORKSPACE_DIR)
    if not os.path.isdir(ws):
        return items
    for fname in MEMORY_FILES:
        path = os.path.join(ws, fname)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    body = f.read().strip()
                if body:
                    items.append("# %s\n%s" % (fname, body))
            except OSError:
                pass
    # 附带 memory/ 下的日记正文：OpenClaw 会把当日事实写入 memory/<date>.md
    diary_dir = os.path.join(ws, "memory")
    if os.path.isdir(diary_dir):
        try:
            for fname in sorted(os.listdir(diary_dir)):
                if not fname.endswith(".md"):
                    continue
                path = os.path.join(diary_dir, fname)
                if not os.path.isfile(path):
                    continue
                with open(path, "r", encoding="utf-8") as f:
                    body = f.read().strip()
                if body:
                    items.append("# memory/%s\n%s" % (fname, body))
        except OSError:
            pass
    return items


def _retrieval_trace(query: str):
    """尽力而为地返回检索轨迹；失败则空列表（membench 优雅降级）。"""
    # TODO: 若需真实 retrieval_trace，可用 `openclaw memory search "<query>"`
    #       解析其输出为 {"content":..., "score":...} 列表。当前先返空。
    return []


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> None:
    # 新进程 = 新 episode：先还原干净记忆状态，杜绝跨用例污染
    _reset_memory_state()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        mtype = msg.get("type")
        try:
            if mtype == "session_start":
                # OpenClaw 跨调用持久化记忆，session 边界无需额外处理
                continue
            elif mtype == "user":
                content = msg.get("content", "")
                reply = _run_openclaw(content)
                _emit({"type": "assistant", "content": reply})
            elif mtype == "memory_dump_request":
                items = _read_memory_dump()
                _emit({"type": "memory", "items": items})
            elif mtype == "retrieval_trace_request":
                _emit({"type": "retrieval_trace", "items": _retrieval_trace(msg.get("query", ""))})
            elif mtype == "session_end":
                continue
            else:
                # 未知消息类型：忽略（harness 不期待回复）
                continue
        except Exception as e:  # noqa: BLE001
            _emit({"type": "error", "message": str(e)[:500]})


if __name__ == "__main__":
    main()
