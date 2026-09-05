# -*- coding: utf-8 -*-
"""智能体工厂：从内置名或 JSON 配置创建适配器。"""
from __future__ import annotations

import json
import os
from typing import List

from .base import AgentAdapter, AgentError
from .builtin import NaiveMemoryAgent, NoMemoryAgent, SmartMemoryAgent

BUILTIN_AGENTS = {
    "nomem": NoMemoryAgent,
    "naive": NaiveMemoryAgent,
    "smart": SmartMemoryAgent,
}


def create_agent(spec: str) -> AgentAdapter:
    """spec 可以是内置名（nomem/naive/smart）或智能体配置 JSON 文件路径。"""
    if spec in BUILTIN_AGENTS:
        return BUILTIN_AGENTS[spec]()
    if os.path.isfile(spec):
        with open(spec, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return create_agent_from_config(cfg, source=spec)
    raise AgentError("找不到智能体: %s（内置: %s，或提供配置文件路径）"
                     % (spec, sorted(BUILTIN_AGENTS)))


def _resolve_cmd(cmd: List[str], source: str) -> List[str]:
    """把 cmd 中的相对路径解析为绝对路径。

    评测时子进程 cwd 会切到沙箱目录，因此必须在创建适配器时（cwd 仍为
    调用方目录）就解析好脚本路径，优先按调用方 cwd，其次按配置文件所在目录。
    """
    out: List[str] = []
    cfg_dir = os.path.dirname(os.path.abspath(source)) if source else ""
    for arg in cmd:
        if os.path.isfile(arg):
            out.append(os.path.abspath(arg))
        elif cfg_dir and os.path.isfile(os.path.join(cfg_dir, arg)):
            out.append(os.path.abspath(os.path.join(cfg_dir, arg)))
        else:
            out.append(arg)
    return out


def create_agent_from_config(cfg: dict, source: str = "") -> AgentAdapter:
    kind = str(cfg.get("kind", "")).strip()
    name = str(cfg.get("name", "agent"))
    if kind == "builtin":
        impl = str(cfg.get("impl", ""))
        cls = BUILTIN_AGENTS.get(impl)
        if cls is None:
            raise AgentError("%s: 未知内置智能体 %r（可选 %s）" % (source, impl, sorted(BUILTIN_AGENTS)))
        agent = cls()
        agent.name = name or agent.name
        return agent
    if kind == "subproc":
        cmd = [str(x) for x in (cfg.get("cmd") or [])]
        if not cmd:
            raise AgentError("%s: subproc 智能体需要 cmd 字段" % source)
        cmd = _resolve_cmd(cmd, source)
        from .subproc import SubprocAgent
        return SubprocAgent(name=name, cmd=cmd, timeout=float(cfg.get("timeout", 60)))
    if kind == "openai_compat":
        # api 选择 wire format（N+26）：openai=Chat Completions（base_url 含版本段），
        # anthropic=Messages（base_url 不含版本段）；缺省 openai，旧配置零改动。
        api = str(cfg.get("api", "") or "openai").strip()
        if api not in ("openai", "anthropic"):
            raise AgentError("%s: 未知 api 格式 %r（可选 openai/anthropic）" % (source, api))
        default_key_env = "ANTHROPIC_API_KEY" if api == "anthropic" else "OPENAI_API_KEY"
        api_key = ""
        key_env = str(cfg.get("api_key_env", "") or default_key_env)
        if key_env:
            api_key = os.environ.get(key_env, "")
        from .openai_compat import OpenAICompatAgent
        max_tokens = cfg.get("max_tokens")
        return OpenAICompatAgent(
            name=name,
            base_url=str(cfg.get("base_url", "http://127.0.0.1:11434/v1")),
            model=str(cfg.get("model", "")),
            api_key=api_key,
            memory=cfg.get("memory") or {},
            system_prompt=str(cfg.get("system_prompt", "你是 openKylin 桌面智能助手。")),
            temperature=float(cfg.get("temperature", 0.2)),
            timeout=float(cfg.get("timeout", 120)),
            api=api,
            max_tokens=(int(max_tokens) if max_tokens else None),
        )
    raise AgentError("%s: 未知智能体类型 %r（可选 builtin/subproc/openai_compat）" % (source, kind))
