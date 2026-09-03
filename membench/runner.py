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

from . import VERDICT_IMPROPER_PERSISTENCE, VERDICT_NOT_EVALUABLE
from .agents.base import AgentAdapter, AgentError
from .schema import Case, Probe
from .scoring import (ProbeResult, diff_snapshot, evaluate_probe, scan_sensitive,
                      snapshot_dir)

FreeJudge = Callable[[Probe, Case, str], dict]


@dataclass
class CaseResult:
    agent: str
    case_id: str
    dimension: str
    run_index: int
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
                        started_at=started)
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
            result.rows.append(row)
            asked.add(probe.probe_id)

        fs_after = snapshot_dir(workdir)
        new_files = diff_snapshot(fs_before, fs_after)
        result.findings = scan_sensitive(case.sensitive_patterns,
                                         memory_items or [], new_files)
        for f in result.findings:
            result.rows.append({
                "probe_id": "sensitive_scan", "probe_type": "scan",
                "dimension": "boundary_refusal",
                "verdict": VERDICT_IMPROPER_PERSISTENCE, "score": 0.0,
                "reason": f["detail"], "reply": "", "hits": [f["pattern"]],
                "misses": [], "weight": 1.0, "judge": "deterministic"})

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
            "evidence_sessions": probe.evidence_sessions,
            "retrieval_trace": trace,
        }
    pr: ProbeResult = evaluate_probe(probe, case, reply=reply,
                                     memory_items=None, workdir=workdir)
    row = asdict(pr)
    row["judge"] = "deterministic"
    row["evidence_sessions"] = probe.evidence_sessions
    row["retrieval_trace"] = trace
    return row


# ---------- 套件编排 ---------------------------------------------------------------

def run_suite(agent: AgentAdapter, cases: List[Case], out_dir: str,
              runs: int = 1, judge_free: Optional[FreeJudge] = None,
              keep_workdir: bool = False, quiet: bool = False) -> dict:
    """对单个智能体运行整套用例 N 次，落盘逐用例证据与汇总，返回 summary dict。"""
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
    with open(os.path.join(agent_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name) or "agent"


def _log(msg: str) -> None:
    print(msg, flush=True)
