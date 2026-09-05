# -*- coding: utf-8 -*-
"""HTTP 小工具：回环地址绕过环境代理。

urllib 默认读取 HTTP_PROXY/ALL_PROXY 等环境变量，会把发往 127.0.0.1 的
请求也交给代理；代理无法回连本机临时端口，表现为连接超时（本地 fake
LLM server、本机 gateway 探活均属此场景）。回环目标永远不该走代理。
"""
import urllib.parse
import urllib.request

_LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")


def opener_for(base_url: str):
    """回环 base_url 返回无代理 opener；远端返回 None（沿用环境代理）。"""
    host = (urllib.parse.urlparse(base_url).hostname or "").lower()
    if host in _LOOPBACK_HOSTS:
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return None
