# -*- coding: utf-8 -*-
"""数据集 schema：Case / Session / Probe / Expected 的数据类与校验。

设计原则（对应赛题"数据集设计"交付）：
- 每个用例（case）= 一段"记忆剧本"：多 session 对话 + 探针（probe）+ 期望（expected）。
- 探针类型覆盖确定性可判的（choice/slot/fs/memory）与需要语义判定的（free）。
- expected 的字段全部可扩展，新增检查项不影响旧用例。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

from . import DIMENSIONS

PROBE_TYPES = ("choice", "slot", "free", "fs", "memory")

SCHEMA_VERSION = 1


class SchemaError(ValueError):
    """数据集格式错误。"""


def _require(cond: bool, msg: str):
    if not cond:
        raise SchemaError(msg)


def _check_sandbox_path(src: str, case_id: str, where: str, path: str) -> None:
    """沙箱内相对路径检查：拒绝绝对路径与向上逃逸，防止误触评测机文件系统。"""
    norm = os.path.normpath(path)
    if os.path.isabs(path) or norm.startswith("..") or norm.startswith("/"):
        raise SchemaError(
            f"{src}: {case_id} {where} 必须是沙箱内相对路径，收到: {path!r}")


@dataclass
class Turn:
    role: str            # "user" / "assistant"（剧本里一般只写 user 侧）
    content: str


@dataclass
class Session:
    session_id: str
    turns: List[Turn] = field(default_factory=list)
    note: str = ""       # 人类可读的场景说明，例如 "一周后"
    date: str = ""       # 可选：模拟时间戳（如 2026-03-15），对标 LongMemEval 的 timestamped sessions


@dataclass
class Expected:
    """探针期望。字段按 probe_type 选用，全部可选以保持向后兼容。"""
    # choice
    choices: List[str] = field(default_factory=list)
    answer: str = ""                       # 正确选项文本
    distractor_labels: List[int] = field(default_factory=list)  # 易混淆选项下标(0-based)
    # slot / free
    must_include: List[str] = field(default_factory=list)
    must_not_include: List[str] = field(default_factory=list)
    # OR 语义：任一命中即算通过（用于拒答类探针："不知道/没说过/..."任一即可）
    any_include: List[str] = field(default_factory=list)
    # FAMA（Forgetting-Aware Memory Accuracy）风格：must_not_include 里的串若
    # 已被剧本中后续 session 显式覆盖/失效（如"原电话 138… 改为 139…"），
    # 命中时统一按 improper_reuse 而非 confusion 裁决。
    superseded_values: List[str] = field(default_factory=list)
    # free：语义断言（每条都应被回答满足），支持部分得分
    assertions: List[str] = field(default_factory=list)
    # fs
    file_exists: List[str] = field(default_factory=list)
    file_absent: List[str] = field(default_factory=list)
    file_contains: Dict[str, str] = field(default_factory=dict)  # path -> 正则
    # memory（对智能体记忆库 dump 的确定性检查）
    memory_includes: List[str] = field(default_factory=list)
    memory_excludes: List[str] = field(default_factory=list)
    # 记忆卫生：value 在记忆库中的出现次数不得超过上限（重复声明应去重）
    memory_max_count: Dict[str, int] = field(default_factory=dict)
    # 边界：禁止在回答中出现的敏感内容（出现即 improper_persistence）
    forbid_reveal: List[str] = field(default_factory=list)


@dataclass
class Probe:
    probe_id: str
    type: str                          # choice / slot / free / fs / memory
    question: str = ""                 # 作为 user 消息发给智能体
    after_session: str = ""            # 在哪个 session 结束后提出
    expected: Expected = field(default_factory=Expected)
    weight: float = 1.0
    note: str = ""
    dimension: str = ""                # 可选：覆盖所属 case 的维度
    evidence_sessions: List[str] = field(default_factory=list)  # 可选：证据所在 session（对标 answer_session_ids）


@dataclass
class FactSpan:
    """事实有效期声明（Zep/Graphiti 式"失效不删除"的 session 级时间轴版）。

    value 在 valid_from session 进入记忆，在 valid_until session 被覆盖/失效；
    valid_until 之后仍出现在记忆或回答中 => improper_reuse（FAMA 风格）。
    """
    value: str
    valid_from: str = ""
    valid_until: str = ""


@dataclass
class Case:
    case_id: str
    dimension: str                     # 六维之一
    title: str
    sessions: List[Session] = field(default_factory=list)
    probes: List[Probe] = field(default_factory=list)
    description: str = ""
    difficulty: str = "medium"         # easy / medium / hard
    tags: List[str] = field(default_factory=list)
    # 敏感内容标记：runner 会在记忆库与文件系统新增内容中扫描这些串
    sensitive_patterns: List[str] = field(default_factory=list)
    # 事实生命周期：失效值在后续 session 的记忆快照中仍出现 => 过程级 staleness 发现
    fact_lifecycle: List[FactSpan] = field(default_factory=list)
    # 初始文件（写入沙箱工作目录）：path -> content
    setup_files: Dict[str, str] = field(default_factory=dict)
    source_file: str = ""


def parse_case(data: Dict[str, Any], source_file: str = "") -> Case:
    """从 dict（YAML/JSON 已解析）构建并校验 Case。"""
    _require(isinstance(data, dict), "用例必须是映射对象")
    case_id = str(data.get("case_id", "")).strip()
    _require(case_id, f"{source_file}: 缺少 case_id")
    dimension = str(data.get("dimension", "")).strip()
    _require(dimension in DIMENSIONS,
             f"{source_file}: dimension 非法: {dimension!r}（应为 {DIMENSIONS}）")
    title = str(data.get("title", case_id))
    version = int(data.get("schema_version", 1))
    _require(version == SCHEMA_VERSION,
             f"{source_file}: 不支持的 schema_version={version}")

    sessions: List[Session] = []
    seen_sessions = set()
    for i, s in enumerate(data.get("sessions") or []):
        _require(isinstance(s, dict), f"{source_file}: sessions[{i}] 不是映射")
        sid = str(s.get("session_id", "")).strip()
        _require(sid, f"{source_file}: sessions[{i}] 缺少 session_id")
        turns = []
        for t in s.get("turns") or []:
            if isinstance(t, str):            # 简写：直接给 user 文本
                t = {"role": "user", "content": t}
            role = str(t.get("role", "user"))
            content = str(t.get("content", ""))
            _require(content != "" or role == "assistant",
                     f"{source_file}: session {sid} 存在空 turn")
            turns.append(Turn(role=role, content=content))
        _require(sid not in seen_sessions,
                 f"{source_file}: {case_id} session_id 重复: {sid!r}")
        seen_sessions.add(sid)
        sessions.append(Session(session_id=sid, turns=turns,
                                note=str(s.get("note", "")),
                                date=str(s.get("date", ""))))
    _require(sessions, f"{source_file}: {case_id} 至少需要一个 session")

    probes: List[Probe] = []
    seen_probes = set()
    for i, p in enumerate(data.get("probes") or []):
        _require(isinstance(p, dict), f"{source_file}: probes[{i}] 不是映射")
        pid = str(p.get("probe_id", "")).strip() or f"p{i+1}"
        _require(pid not in seen_probes,
                 f"{source_file}: {case_id} probe_id 重复: {pid!r}")
        seen_probes.add(pid)
        ptype = str(p.get("type", "")).strip()
        _require(ptype in PROBE_TYPES,
                 f"{source_file}: {case_id} probe {pid} 类型非法: {ptype!r}（应为 {PROBE_TYPES}）")
        exp_data = p.get("expected") or {}
        _require(isinstance(exp_data, dict), f"{source_file}: {case_id}/{pid} expected 不是映射")
        exp = Expected(
            choices=[str(c) for c in (exp_data.get("choices") or [])],
            answer=str(exp_data.get("answer", "")),
            distractor_labels=[int(x) for x in (exp_data.get("distractor_labels") or [])],
            must_include=[str(x) for x in (exp_data.get("must_include") or [])],
            must_not_include=[str(x) for x in (exp_data.get("must_not_include") or [])],
            any_include=[str(x) for x in (exp_data.get("any_include") or [])],
            superseded_values=[str(x) for x in (exp_data.get("superseded_values") or [])],
            assertions=[str(x) for x in (exp_data.get("assertions") or [])],
            file_exists=[str(x) for x in (exp_data.get("file_exists") or [])],
            file_absent=[str(x) for x in (exp_data.get("file_absent") or [])],
            file_contains={str(k): str(v) for k, v in (exp_data.get("file_contains") or {}).items()},
            memory_includes=[str(x) for x in (exp_data.get("memory_includes") or [])],
            memory_excludes=[str(x) for x in (exp_data.get("memory_excludes") or [])],
            memory_max_count={str(k): int(v) for k, v in (exp_data.get("memory_max_count") or {}).items()},
            forbid_reveal=[str(x) for x in (exp_data.get("forbid_reveal") or [])],
        )
        # 静态校验：expected 与 probe 类型至少有一项匹配的检查字段
        _check_probe_expectation(case_id, pid, ptype, exp, source_file)
        after = str(p.get("after_session", "")).strip()
        if after:
            _require(any(s.session_id == after for s in sessions),
                     f"{source_file}: {case_id}/{pid} after_session={after!r} 不存在")
        pdim = str(p.get("dimension", "")).strip()
        if pdim:
            _require(pdim in DIMENSIONS,
                     f"{source_file}: {case_id}/{pid} dimension 非法: {pdim!r}")
        ev_sessions = [str(x) for x in (p.get("evidence_sessions") or [])]
        for es in ev_sessions:
            _require(any(x.session_id == es for x in sessions),
                     f"{source_file}: {case_id}/{pid} evidence_sessions 引用不存在的 session: {es!r}")
        probes.append(Probe(
            probe_id=pid, type=ptype,
            question=str(p.get("question", "")),
            after_session=after, expected=exp,
            weight=float(p.get("weight", 1.0)),
            note=str(p.get("note", "")),
            dimension=pdim,
            evidence_sessions=ev_sessions,
        ))
    _require(probes, f"{source_file}: {case_id} 至少需要一个 probe")

    return Case(
        case_id=case_id, dimension=dimension, title=title,
        sessions=sessions, probes=probes,
        description=str(data.get("description", "")),
        difficulty=str(data.get("difficulty", "medium")),
        tags=[str(t) for t in (data.get("tags") or [])],
        sensitive_patterns=[str(x) for x in (data.get("sensitive_patterns") or [])],
        fact_lifecycle=_build_lifecycle(data, case_id, sessions, source_file),
        setup_files=_build_setup_files(data, case_id, source_file),
        source_file=source_file,
    )


def _build_lifecycle(data: dict, case_id: str, sessions: List[Session],
                     src: str) -> List[FactSpan]:
    order = {x.session_id: i for i, x in enumerate(sessions)}
    out: List[FactSpan] = []
    for i, f in enumerate(data.get("fact_lifecycle") or []):
        _require(isinstance(f, dict), f"{src}: {case_id} fact_lifecycle[{i}] 不是映射")
        value = str(f.get("value", "")).strip()
        _require(value, f"{src}: {case_id} fact_lifecycle[{i}] 缺少 value")
        vf = str(f.get("valid_from", "")).strip()
        vu = str(f.get("valid_until", "")).strip()
        for ref in (vf, vu):
            _require(not ref or ref in order,
                     f"{src}: {case_id} fact_lifecycle[{i}] 引用不存在的 session: {ref!r}")
        if vf and vu:
            _require(order[vf] <= order[vu],
                     f"{src}: {case_id} fact_lifecycle[{i}] valid_from 在 valid_until 之后")
        out.append(FactSpan(value=value, valid_from=vf, valid_until=vu))
    return out


def probe_role(probe: "Probe") -> str:
    """判据角色：absence = 检验"该遗忘/不该泄露"的信息；presence = 检验应记信息。

    对应 Memora FAMA 的双清单：memory-presence criteria 与 forgetting-absence
    criteria。探针可按 expected 字段自动推断。
    """
    exp = probe.expected
    if exp.forbid_reveal or exp.memory_excludes:
        return "absence"
    return "presence"


def invalid_values_at(case: Case, after_session: str) -> set:
    """在 after_session 时点已失效的值集合（供评分归类 improper_reuse）。"""
    order = {x.session_id: i for i, x in enumerate(case.sessions)}
    probe_idx = order.get(after_session, len(order))
    out = set()
    for f in case.fact_lifecycle:
        if f.valid_until and order.get(f.valid_until, len(order)) <= probe_idx:
            out.add(f.value)
    return out


def _build_setup_files(data: dict, case_id: str, src: str) -> Dict[str, str]:
    files = {str(k): str(v) for k, v in (data.get("setup_files") or {}).items()}
    for rel in files:
        _check_sandbox_path(src, case_id, "setup_files", rel)
    return files


def _check_probe_expectation(case_id: str, pid: str, ptype: str, exp: Expected, src: str):
    """确保每类探针声明了可判定的期望，避免'空探针'流入评测。"""
    def has_any(*vals) -> bool:
        return any(bool(v) for v in vals)

    if ptype == "choice":
        _require(len(exp.choices) >= 2 and exp.answer,
                 f"{src}: {case_id}/{pid} choice 探针需要 choices(>=2) 与 answer")
        _require(exp.answer in exp.choices,
                 f"{src}: {case_id}/{pid} answer 不在 choices 中")
        for idx in exp.distractor_labels:
            _require(0 <= idx < len(exp.choices),
                     f"{src}: {case_id}/{pid} distractor_labels 越界: {idx}")
    elif ptype == "slot":
        _require(has_any(exp.must_include, exp.must_not_include, exp.any_include),
                 f"{src}: {case_id}/{pid} slot 探针需要 must_include/must_not_include/any_include")
    elif ptype == "free":
        _require(has_any(exp.must_include, exp.must_not_include, exp.assertions,
                         exp.forbid_reveal, exp.any_include),
                 f"{src}: {case_id}/{pid} free 探针需要 must_include/must_not_include/assertions/forbid_reveal/any_include")
    elif ptype == "fs":
        _require(has_any(exp.file_exists, exp.file_absent, exp.file_contains),
                 f"{src}: {case_id}/{pid} fs 探针需要 file_exists/file_absent/file_contains")
        for rel in exp.file_exists + exp.file_absent + list(exp.file_contains):
            _check_sandbox_path(src, case_id, "%s/%s 的文件路径" % (pid, ptype), rel)
    elif ptype == "memory":
        _require(has_any(exp.memory_includes, exp.memory_excludes, exp.memory_max_count),
                 f"{src}: {case_id}/{pid} memory 探针需要 memory_includes/memory_excludes/memory_max_count")
