# -*- coding: utf-8 -*-
"""LLM HTTP 统一适配：OpenAI 与 Anthropic 两种 wire format（N+26）。

judge（membench/judge.py）与被测智能体（membench/agents/openai_compat.py）
原先各写一份 POST 且只支持 OpenAI 格式；本模块把请求构造、鉴权头、响应
解析收敛到一处，格式由调用方以 api 字段指定。零第三方依赖（urllib）。

  api = "openai"     Chat Completions 格式。base_url 含版本段
                     （如 https://api.openai.com/v1、Ollama 的
                     http://127.0.0.1:11434/v1），请求 POST {base}/chat/completions。
  api = "anthropic"  Messages 格式。base_url 不含版本段
                     （如 https://api.anthropic.com、DeepSeek 的
                     https://api.deepseek.com/anthropic），请求 POST {base}/v1/messages。
                     鉴权同时发送 x-api-key 与 Authorization: Bearer——
                     官方认 x-api-key，DeepSeek 等 anthropic 兼容网关认
                     Bearer，双发无害。

格式差异全部在此层消化，调用方无感：
- anthropic 的 system 是顶层字段而非 messages 角色；协议要求 user 开头且
  user/assistant 交替，连续同角色消息自动合并；
- anthropic 的 max_tokens 必填（默认 1024）；响应正文在 content[].text。
"""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 1024
APIS = ("openai", "anthropic")


class LLMHTTPError(Exception):
    """LLM HTTP 调用失败（网络/HTTP 状态/响应结构异常），message 带摘要。"""


def _post(url: str, headers: Dict[str, str], payload: dict,
          timeout: float, opener) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers}, method="POST")
    open_fn = opener.open if opener else urllib.request.urlopen
    try:
        with open_fn(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:200]
        except Exception:  # noqa: BLE001 —— 摘要读取失败不影响原错误上报
            pass
        raise LLMHTTPError("HTTP %s: %s" % (e.code, body)) from e
    except urllib.error.URLError as e:
        raise LLMHTTPError("请求失败: %s" % e.reason) from e
    except socket.timeout as e:
        raise LLMHTTPError("请求超时（%ss）" % timeout) from e
    except json.JSONDecodeError as e:
        raise LLMHTTPError("响应非 JSON: %s" % e) from e


def _split_system(messages: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, str]]]:
    """anthropic 化：拆出 system 顶层字段；合并连续同角色（协议要求交替）。"""
    system_parts = [m.get("content", "") for m in messages if m.get("role") == "system"]
    msgs: List[Dict[str, str]] = []
    for m in messages:
        if m.get("role") == "system":
            continue
        if msgs and msgs[-1]["role"] == m.get("role"):
            msgs[-1]["content"] += "\n\n" + m.get("content", "")
        else:
            msgs.append({"role": m.get("role"), "content": m.get("content", "")})
    return "\n\n".join(system_parts), msgs


def _anthropic_text(data: dict) -> str:
    if data.get("type") == "error":
        err = data.get("error") or {}
        raise LLMHTTPError("anthropic 错误响应: %s" % (err.get("message") or data))
    text = "".join(b.get("text", "") for b in (data.get("content") or [])
                   if isinstance(b, dict) and b.get("type") == "text")
    if not text:
        raise LLMHTTPError("响应无文本内容: %r" % str(data)[:200])
    return text


def chat(base_url: str, api: str = "openai", model: str = "",
         messages: Optional[List[Dict[str, str]]] = None, api_key: str = "",
         temperature: float = 0.0, timeout: float = 120.0, opener=None,
         max_tokens: Optional[int] = None) -> str:
    """按 api 指定的 wire format 发起一次对话，返回助手文本回复。

    opener 由调用方传入（通常来自 httputil.opener_for，回环地址绕过环境
    代理）；传 None 时沿用 urllib 默认（含环境代理）。
    """
    if api not in APIS:
        raise LLMHTTPError("未知 api 格式: %r（可选 %s）" % (api, APIS))
    base = base_url.rstrip("/")
    messages = messages or []
    if api == "anthropic":
        system, msgs = _split_system(messages)
        payload = {"model": model, "max_tokens": int(max_tokens or DEFAULT_MAX_TOKENS),
                   "temperature": temperature, "messages": msgs}
        if system:
            payload["system"] = system
        headers = {"anthropic-version": ANTHROPIC_VERSION}
        if api_key:
            headers["x-api-key"] = api_key
            headers["Authorization"] = "Bearer " + api_key
        return _anthropic_text(_post(base + "/v1/messages", headers,
                                     payload, timeout, opener))
    payload = {"model": model, "messages": messages, "temperature": temperature}
    headers = {"Authorization": "Bearer " + api_key} if api_key else {}
    data = _post(base + "/chat/completions", headers, payload, timeout, opener)
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as e:
        raise LLMHTTPError("响应格式异常: %r" % str(data)[:200]) from e
