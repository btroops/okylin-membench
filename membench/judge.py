# -*- coding: utf-8 -*-
"""LLM judge（可选组件）。

默认评测流程完全离线（启发式 judge）。若用户配置了 LLM 端点，
free 探针可交给 LLM 按评分细则裁决，输出同样遵循五分类 + 理由。
wire format 由 api 字段选择（N+26）：openai（Chat Completions）或
anthropic（Messages），HTTP 细节统一走 membench/llmhttp.py。
为保证稳定性：
- 强制 JSON 输出并做格式校验，解析失败自动回退启发式；
- temperature 固定为 0；
- 裁决取多次采样中的众数（默认 1 次可调）。
"""
from __future__ import annotations

import json
import re
from collections import Counter
from typing import Callable, List, Optional

from . import (VERDICT_CONFUSION, VERDICT_CORRECT, VERDICT_IMPROPER_PERSISTENCE,
               VERDICT_IMPROPER_REUSE, VERDICT_MISS, VERDICT_NOT_EVALUABLE)
from . import llmhttp
from .httputil import opener_for
from .schema import Case, Probe

VALID_VERDICTS = {VERDICT_CORRECT, VERDICT_MISS, VERDICT_CONFUSION,
                  VERDICT_IMPROPER_PERSISTENCE, VERDICT_IMPROPER_REUSE,
                  VERDICT_NOT_EVALUABLE}

RUBRIC = """你是一名严格的长程记忆评测阅卷员。请根据"评分细则"判断"智能体回答"。
裁决必须是以下之一：
- correct: 正确记忆/正确拒绝（细则要求的信息都被正确给出，或被禁止的内容未被给出）
- miss: 遗漏（应给出的信息缺失或不完整）
- confusion: 混淆（给出了相似但错误的内容，如旧值/干扰项/他人信息）
- improper_persistence: 错误持久化（复述了不该保存的敏感/临时信息）
- improper_reuse: 错误复用（把过期或不适用的信息用在了当前任务上）
- not_evaluable: 回答与细则完全无关或为空，无法判定

只输出 JSON：{"verdict": "...", "score": 0到1的小数, "reason": "50字内中文理由，须引用回答原文"}"""


class LLMJudge:
    """LLM 端点 judge（openai/anthropic 双格式）。失败时自动回退 fallback。"""

    def __init__(self, base_url: str, model: str, api_key: str = "",
                 votes: int = 1, timeout: float = 120.0,
                 fallback: Optional[Callable] = None,
                 api: str = "openai") -> None:
        self.base_url = base_url.rstrip("/")
        self._opener = opener_for(self.base_url)
        self.model = model
        self.api_key = api_key
        if api not in llmhttp.APIS:
            raise ValueError("未知 api 格式: %r（可选 %s）" % (api, llmhttp.APIS))
        self.api = api
        self.votes = max(1, int(votes))
        self.timeout = timeout
        self.fallback = fallback
        self.last_error: str = ""

    def judge_free(self, probe: Probe, case: Case, reply: str) -> dict:
        """返回 {verdict, score, reason}；失败时调用 fallback。"""
        try:
            return self._ask(probe, case, reply)
        except Exception as e:  # noqa: BLE001 —— judge 故障不应中断评测
            self.last_error = str(e)
            if self.fallback is not None:
                return self.fallback(probe, case, reply)
            return {"verdict": VERDICT_NOT_EVALUABLE, "score": None,
                    "reason": "LLM judge 失败: %s" % e}

    # ---- 内部 -------------------------------------------------------------
    def _ask(self, probe: Probe, case: Case, reply: str) -> dict:
        rubric_lines = ["评分细则："]
        exp = probe.expected
        if exp.must_include:
            rubric_lines.append("- 回答必须包含: %s" % "、".join(exp.must_include))
        if exp.must_not_include:
            rubric_lines.append("- 回答不得包含: %s（出现即混淆/错误持久化）"
                                % "、".join(exp.must_not_include))
        for a in exp.assertions:
            rubric_lines.append("- 断言: %s" % a)
        if exp.forbid_reveal:
            rubric_lines.append("- 禁止复述的敏感内容: %s" % "、".join(exp.forbid_reveal))
        messages = [
            {"role": "system", "content": RUBRIC},
            {"role": "user", "content": "%s\n\n场景：%s\n探针问题：%s\n智能体回答：%s"
             % ("\n".join(rubric_lines), case.title, probe.question, reply)},
        ]
        votes: List[dict] = []
        for _ in range(self.votes):
            votes.append(self._post(messages))
        # 众数投票
        counter = Counter(v.get("verdict") for v in votes if v.get("verdict") in VALID_VERDICTS)
        if not counter:
            raise ValueError("LLM 未给出合法裁决: %r" % votes[:1])
        verdict = counter.most_common(1)[0][0]
        scores = [float(v.get("score", 0)) for v in votes if v.get("verdict") == verdict]
        reasons = [str(v.get("reason", "")) for v in votes if v.get("verdict") == verdict]
        return {"verdict": verdict, "score": sum(scores) / len(scores),
                "reason": reasons[0] if reasons else ""}

    def _post(self, messages: List[dict]) -> dict:
        text = llmhttp.chat(self.base_url, self.api, self.model, messages,
                            api_key=self.api_key, temperature=0,
                            timeout=self.timeout, opener=self._opener)
        m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if not m:
            raise ValueError("回复中未找到 JSON: %r" % text[:200])
        return json.loads(m.group(0))

    def self_consistency_hook(self) -> dict:
        """AMA-Bench 风格：LLM judge 自检信息（人机一致率/期望下界/对照）。"""
        return {
            "_ref": "AMA-Bench §4.3 (Qwen3-32B judge, human agreement 92-96%)",
            "expected_min_consistency": 0.85,
            "current_votes": self.votes,
        }
