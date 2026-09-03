# -*- coding: utf-8 -*-
"""用例加载：递归扫描目录，支持 .yaml / .yml / .json，做静态校验与去重。"""
from __future__ import annotations

import json
import os
from typing import Dict, List

from .schema import Case, SchemaError, parse_case

try:
    import yaml  # type: ignore
    _HAS_YAML = True
except ImportError:  # pragma: no cover
    _HAS_YAML = False


def _parse_text(text: str, path: str) -> dict:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        return json.loads(text)
    if ext in (".yaml", ".yml"):
        if not _HAS_YAML:
            raise SchemaError(
                f"{path}: 需要 PyYAML 才能读取 YAML 用例；请改用 .json 或安装 python3-yaml")
        return yaml.safe_load(text)
    raise SchemaError(f"{path}: 不支持的用例格式 {ext}（支持 .yaml/.yml/.json）")


def load_cases(paths: List[str]) -> List[Case]:
    """从若干文件或目录加载用例；目录会递归扫描。返回按 case_id 去重后的列表。"""
    files: List[str] = []
    for p in paths:
        if os.path.isfile(p):
            files.append(p)
        elif os.path.isdir(p):
            for root, _dirs, names in os.walk(p):
                for n in sorted(names):
                    if os.path.splitext(n)[1].lower() in (".yaml", ".yml", ".json"):
                        fp = os.path.join(root, n)
                        # agent 配置也是 json，按字段区分
                        if n.endswith(".json") and _looks_like_agent_config(fp):
                            continue
                        files.append(fp)
        else:
            raise SchemaError(f"路径不存在: {p}")

    cases: Dict[str, Case] = {}
    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            text = f.read()
        if not text.strip():
            continue
        data = _parse_text(text, fp)
        if not isinstance(data, list):
            data = [data]
        for item in data:
            case = parse_case(item, source_file=fp)
            if case.case_id in cases:
                raise SchemaError(
                    f"case_id 重复: {case.case_id}（{fp} 与 {cases[case.case_id].source_file}）")
            cases[case.case_id] = case
    return list(cases.values())


def _looks_like_agent_config(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return isinstance(data, dict) and "kind" in data and "name" in data \
            and "sessions" not in data and "probes" not in data
    except Exception:
        return False
