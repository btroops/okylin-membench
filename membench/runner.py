# -*- coding: utf-8 -*-
"""评测执行器：回放记忆剧本、采集运行证据、逐探针评分。

一次 run（对某智能体 × 某用例）的流程：
  1. 准备沙箱工作目录，写入 setup_files，做文件系统快照（前）
  2. 依次回放各 session 的 user 消息，记录智能体回复
  3. 每个 session 结束后，提出该时点的探针（每条探针独占一个新 session）
  4. 结束后导出记忆库 dump（memory 探针在此时评测）、做文件系统快照（后），
     并扫描敏感信息持久化
  5. 逐探针评测（确定性优先），产出 CaseResult
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, List, Optional

from . import (VERDICT_CORRECT, VERDICT_IMPROPER_PERSISTENCE,
               VERDICT_IMPROPER_REUSE, VERDICT_NOT_EVALUABLE)
from .agents.base import AgentAdapter, AgentError
from .schema import Case, Probe, probe_role
from .scoring import (ProbeResult, diff_snapshot, evaluate_probe, normalize_text,
                      scan_sensitive, snapshot_dir)

FreeJudge = Callable[[Probe, Case, str], dict]


def _contains_any(items: List[str], patterns: List[str]) -> bool:
    from .scoring import normalize_text
    joined = "\n".join(normalize_text(x) for x in items)
    return any(normalize_text(x) in joined for x in patterns)


def _snippet2(s: str, width: int) -> str:
    return s if len(s) <= width else s[:width] + "…"


@dataclass
class CaseResult:
    agent: str
    case_id: str
    dimension: str
    run_index: int
    difficulty: str = "medium"
    rows: List[dict] = field(default_factory=list)        # 探针评分行
    findings: List[dict] = field(default_factory=list)    # 敏感持久化扫描结果
    score: Optional[float] = None
    evidence: dict = field(default_factory=dict)
    started_at: float = 0.0
    duration_sec: float = 0.0

    def to_json(self) -> dict:
        return asdict(self)


def run_case(agent: AgentAdapter, case: Case, run_index: int,
             workroot: str, judge_free: Optional[FreeJudge] = None,
             keep_workdir: bool = False) -> CaseResult:
    started = time.time()
    workdir = tempfile.mkdtemp(prefix="membench_%s_" % case.case_id, dir=workroot)
    result = CaseResult(agent=agent.name, case_id=case.case_id,
                        dimension=case.dimension, run_index=run_index,
                        difficulty=case.difficulty, started_at=started)
    try:
        # 1) setup + 快照
        from .schema import _check_sandbox_path
        for rel, content in case.setup_files.items():
            _check_sandbox_path("", case.case_id, "setup_files", rel)
            path = os.path.join(workdir, rel)
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        agent.new_episode(workdir)
        fs_before = snapshot_dir(workdir)
        transcript: List[dict] = []
        asked: set = set()
        memory_evolution: List[dict] = []   # 记忆演变轨迹（赛题"写入/更新/拒绝"的过程证据）
        prev_dump: Optional[List[str]] = None
        stale_reported: set = set()

        # 2/3) 回放 session 与文本/fs 探针
        for session in case.sessions:
            agent.session_start(session.session_id)
            st = {"session_id": session.session_id, "note": session.note,
                  "date": session.date, "turns": []}
            for turn in session.turns:
                if turn.role != "user":
                    continue
                reply = agent.send_user(turn.content)
                st["turns"].append({"role": "user", "content": turn.content})
                st["turns"].append({"role": "assistant", "content": reply})
            transcript.append(st)
            agent.session_end()
            # 记忆演变轨迹：每个 session 结束后导出快照并与上一快照 diff。
            # 三种病因在终态指标里不可分，这里把它们分开：
            #   写失败（added 始终为空）/ 保持失败（写后 removed）/ 边界失败（该删未删）
            try:
                dump_now: Optional[List[str]] = agent.memory_dump()
            except AgentError:
                dump_now = None
            if dump_now is not None:
                prev_set = set(prev_dump or [])
                now_set = set(dump_now)
                memory_evolution.append({
                    "after_session": session.session_id,
                    "n_items": len(now_set),
                    "added": sorted(now_set - prev_set),
                    "removed": sorted(prev_set - now_set),
                })
                prev_dump = list(dump_now)
                # 记忆写入纪律：新增条目是否触发噪声上限（防止"什么都存"的记忆系统）
                for value, maxn in case.noise_max_count.items():
                    now_count = sum(1 for item in dump_now if normalize_text(value) in
                                   normalize_text(item))
                    if now_count > maxn:
                        result.rows.append({
                            "probe_id": "noise_scan", "probe_type": "scan",
                            "dimension": case.dimension, "role": "absence",
                            "verdict": "improper_persistence", "score": 0.0,
                            "reason": "记忆写入纪律：值「%s」在记忆库中出现 %d 次（上限 %d）——"
                                      "记忆系统应避免累积噪声/重复" % (
                                          _snippet2(value, 20), now_count, maxn),
                            "reply": "", "hits": [value], "misses": [],
                            "weight": 1.0, "judge": "deterministic",
                            "evidence_sessions": [], "retrieval_trace": None,
                        })
                # Zep 式过期扫描：此刻已失效的事实若仍留在记忆库中 =>
                # 过程级 staleness 发现（"该遗忘的没遗忘"，Memora FAA 对应物）
                for f in case.fact_lifecycle:
                    if not f.valid_until or f.valid_until != session.session_id:
                        continue
                    if _contains_any(dump_now, [f.value]):
                        stale = {
                            "probe_id": "staleness_scan", "probe_type": "scan",
                            "dimension": case.dimension, "role": "absence",
                            "verdict": VERDICT_IMPROPER_REUSE, "score": 0.0,
                            "reason": "事实「%s」已在 %s 失效，但记忆库仍保留（该遗忘的没遗忘）"
                                      % (_snippet2(f.value, 24), f.valid_until),
                            "reply": "", "hits": [f.value], "misses": [],
                            "weight": 1.0, "judge": "deterministic",
                            "evidence_sessions": [],
                            "retrieval_trace": None,
                        }
                        result.rows.append(stale)
                        stale_reported.add(f.value)
            for probe in case.probes:
                if probe.probe_id in asked or probe.type == "memory":
                    continue
                if probe.after_session and probe.after_session != session.session_id:
                    continue
                row = _ask_probe(agent, probe, case, workdir, judge_free)
                transcript.append({
                    "session_id": "probe:%s" % probe.probe_id, "note": "探针",
                    "turns": [{"role": "user", "content": probe.question},
                              {"role": "assistant", "content": row.get("reply", "")}]})
                result.rows.append(row)
                asked.add(probe.probe_id)

        # 无 after_session 的非 memory 探针放到最后
        for probe in case.probes:
            if probe.probe_id in asked or probe.type == "memory" or probe.after_session:
                continue
            row = _ask_probe(agent, probe, case, workdir, judge_free)
            result.rows.append(row)
            asked.add(probe.probe_id)

        # 4) 记忆库导出 + 文件系统对比 + 敏感扫描
        try:
            memory_items: Optional[List[str]] = agent.memory_dump()
        except AgentError:
            memory_items = None
        # memory 探针在拿到最终 dump 后评测（白盒证据）
        for probe in case.probes:
            if probe.type != "memory" or probe.probe_id in asked:
                continue
            pr = evaluate_probe(probe, case, reply="", memory_items=memory_items,
                                workdir=workdir)
            row = asdict(pr)
            row["judge"] = "deterministic"
            row["role"] = probe_role(probe)
            result.rows.append(row)
            asked.add(probe.probe_id)

        fs_after = snapshot_dir(workdir)
        new_files = diff_snapshot(fs_before, fs_after)

        # 生命周期缺席判据的终局检查（对称可见：通过也要出现在证据里）
        for f in case.fact_lifecycle:
            if not f.valid_until or f.value in stale_reported:
                continue
            clean = not _contains_any(memory_items or [], [f.value]) and \
                not _contains_any(list(new_files.values()), [f.value])
            result.rows.append({
                "probe_id": "staleness_scan", "probe_type": "scan",
                "dimension": case.dimension, "role": "absence",
                "verdict": VERDICT_CORRECT if clean else VERDICT_IMPROPER_REUSE,
                "score": 1.0 if clean else 0.0,
                "reason": ("事实「%s」已按生命周期失效且未驻留（缺席判据通过）"
                           % _snippet2(f.value, 24)) if clean else
                          ("事实「%s」已失效但仍驻留（该遗忘的没遗忘）"
                           % _snippet2(f.value, 24)),
                "reply": "", "hits": [] if clean else [f.value], "misses": [],
                "weight": 1.0, "judge": "deterministic",
                "evidence_sessions": [], "retrieval_trace": None})
        result.findings = scan_sensitive(case.sensitive_patterns,
                                         memory_items or [], new_files)
        for f in result.findings:
            result.rows.append({
                "probe_id": "sensitive_scan", "probe_type": "scan",
                "dimension": "boundary_refusal", "role": "absence",
                "verdict": VERDICT_IMPROPER_PERSISTENCE, "score": 0.0,
                "reason": f["detail"], "reply": "", "hits": [f["pattern"]],
                "misses": [], "weight": 1.0, "judge": "deterministic",
                "evidence_sessions": [], "retrieval_trace": None})
        found = {f["pattern"] for f in result.findings}
        for pat in case.sensitive_patterns:
            if pat not in found:  # 通过的缺席判据也要可见（FAMA 分母对称）
                result.rows.append({
                    "probe_id": "sensitive_scan", "probe_type": "scan",
                    "dimension": "boundary_refusal", "role": "absence",
                    "verdict": VERDICT_CORRECT, "score": 1.0,
                    "reason": "敏感信息「%s」未出现在记忆库与文件系统（缺席判据通过）"
                              % _snippet2(pat, 16), "reply": "", "hits": [],
                    "misses": [], "weight": 1.0, "judge": "deterministic",
                    "evidence_sessions": [], "retrieval_trace": None})

        # 5) 用例得分（None 评分不计入）
        scored = [r for r in result.rows if r.get("score") is not None]
        if scored:
            wsum = sum(r["weight"] for r in scored)
            result.score = (sum(r["score"] * r["weight"] for r in scored) / wsum) if wsum else 0.0
        result.evidence = {
            "transcript": transcript,
            "memory_dump": memory_items,
            "memory_evolution": memory_evolution or None,
            "fs_added_or_modified": {k: v[:500] for k, v in new_files.items()},
        }
    except AgentError as e:
        # 单用例失败不应中断整套评测：记录错误并标记为不可评
        result.evidence["error"] = str(e)
        result.rows.append({
            "probe_id": "agent_error", "probe_type": "error",
            "dimension": case.dimension,
            "verdict": VERDICT_NOT_EVALUABLE, "score": None,
            "reason": "智能体运行出错: %s" % e, "reply": "",
            "hits": [], "misses": [], "weight": 1.0, "judge": "none"})
    finally:
        result.duration_sec = time.time() - started
        if not keep_workdir:
            shutil.rmtree(workdir, ignore_errors=True)
    return result


def _ask_probe(agent: AgentAdapter, probe: Probe, case: Case,
               workdir: str, judge_free: Optional[FreeJudge]) -> dict:
    """发出探针并评分；fs 探针不发消息。"""
    reply = ""
    trace = None
    if probe.type != "fs" and probe.question:
        agent.session_start("probe:%s" % probe.probe_id)
        try:
            reply = agent.send_user(probe.question)
            try:
                trace = agent.retrieval_trace(probe.question)
            except AgentError:
                trace = None
        finally:
            agent.session_end()

    if probe.type == "free" and judge_free is not None:
        jd = judge_free(probe, case, reply)
        return {
            "probe_id": probe.probe_id, "probe_type": probe.type,
            "dimension": probe.dimension or case.dimension,
            "verdict": jd.get("verdict"), "score": jd.get("score"),
            "reason": jd.get("reason", ""), "reply": reply,
            "hits": [], "misses": [], "weight": probe.weight, "judge": "llm",
            "relation": probe.relation,
            "evidence_sessions": probe.evidence_sessions,
            "retrieval_trace": trace, "role": probe_role(probe),
        }
    pr: ProbeResult = evaluate_probe(probe, case, reply=reply,
                                     memory_items=None, workdir=workdir)
    row = asdict(pr)
    row["judge"] = "deterministic"
    row["evidence_sessions"] = probe.evidence_sessions
    # ProbeResult.relation already covers this; nothing to add here
    row["retrieval_trace"] = trace
    row["role"] = probe_role(probe)
    return row


# ---------- 套件编排 ---------------------------------------------------------------

def run_suite(agent: AgentAdapter, cases: List[Case], out_dir: str,
              runs: int = 1, judge_free: Optional[FreeJudge] = None,
              keep_workdir: bool = False, quiet: bool = False,
              judge_health_fn: Optional[Callable[[], dict]] = None) -> dict:
    """对单个智能体运行整套用例 N 次，落盘逐用例证据与汇总，返回 summary dict。

    judge_health_fn（可选）：落盘前调用一次，返回值并入 summary["_judge"]——
    judge 计数在评测期间递增，调用方用闭包快照差值给出"本智能体"的增量。
    """
    agent_dir = os.path.join(out_dir, _safe_name(agent.name))
    runs_dir = os.path.join(agent_dir, "runs")
    os.makedirs(runs_dir, exist_ok=True)
    all_case_results: List[CaseResult] = []
    for r in range(1, runs + 1):
        run_dir = os.path.join(runs_dir, "run%02d" % r)
        os.makedirs(run_dir, exist_ok=True)
        for case in cases:
            cr = run_case(agent, case, run_index=r, workroot=run_dir,
                          judge_free=judge_free, keep_workdir=keep_workdir)
            with open(os.path.join(run_dir, cr.case_id + ".json"), "w",
                      encoding="utf-8") as f:
                json.dump(cr.to_json(), f, ensure_ascii=False, indent=2)
            all_case_results.append(cr)
            if not quiet:
                _log("  [%s] run%d %s (%s) score=%s"
                     % (agent.name, r, case.case_id, case.dimension,
                        "n/a" if cr.score is None else "%.2f" % cr.score))

    from .aggregate import summarize_agent
    summary = summarize_agent(agent.name, all_case_results, runs=runs)
    if judge_health_fn is not None:
        summary["_judge"] = judge_health_fn()
    with open(os.path.join(agent_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name) or "agent"


def _log(msg: str) -> None:
    print(msg, flush=True)
