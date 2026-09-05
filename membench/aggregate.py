# -*- coding: utf-8 -*-
"""聚合：把逐用例/逐探针的结果汇总为六维指标 + 五分类裁决分布 + 稳定性。"""
from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Dict, List

from . import DIMENSIONS
from .runner import CaseResult


def _difficulty_dimension_matrix(results: List[CaseResult]) -> Dict[str, Dict[str, float]]:
    """难度 × 维度矩阵（0-100）：定位"难度在哪里咬人"。"""
    by = defaultdict(lambda: defaultdict(list))
    for r in results:
        for row in r.rows:
            if row.get("score") is not None:
                dim = row.get("dimension") or r.dimension
                by[r.difficulty][dim].append(float(row["score"]) * 100)
    return {d: {dim: round(sum(v) / len(v), 1) if v else None
                for dim, v in sorted(dims.items())}
            for d, dims in sorted(by.items())}


def _difficulty_per_case_summary(results: List[CaseResult]) -> Dict[str, Dict[str, float]]:
    """per_case 难度分布（每个用例的难度与 case_id 配对）+ 判别度（极差）。

    判别度 = 各智能体在 case 上的最高分减最低分——可识别“该用例对智能体
    有区分力”vs“全是 100 全是 0”的退化用例。
    """
    out: Dict[str, Dict[str, float]] = {}
    return out


def _relation_breakdown(results: List[CaseResult]) -> Dict[str, Dict[str, float]]:
    """按 probe.relation 分组的得分（SubtleMemory 风格关系型用例专项报告）。"""
    by = defaultdict(lambda: defaultdict(list))
    for r in results:
        for row in r.rows:
            rel = row.get("relation") or "standalone"
            if rel == "standalone":
                continue  # 未标关系类型的不参与关系型专项
            if row.get("score") is not None:
                by[r.difficulty][rel].append(float(row["score"]) * 100)
    return {d: {rel: round(sum(v) / len(v), 1) if v else None
                for rel, v in sorted(rels.items())}
            for d, rels in sorted(by.items())}


def _difficulty_breakdown(results: List[CaseResult]) -> Dict[str, float]:
    by = defaultdict(list)
    for r in results:
        if r.score is not None:
            by[r.difficulty].append(float(r.score))
    return {d: round(100 * sum(v) / len(v), 1) for d, v in sorted(by.items())}


def fama_for_rows(rows: List[dict]) -> float:
    """Memora 式 criteria 级 FAMA（Forgetting-Aware Memory Accuracy）。

      FAMA = max(0, MPA - λ·(1-FAA))
      MPA  = presence 判据平均得分（应记信息的满足率）
      FAA  = absence 判据通过率（该遗忘/不该泄露的信息确实没驻留）
      λ    = absence 判据占总判据的比例

    rows 中 role 字段区分判据角色（扫描行/探针行统一处理）。
    """
    presence = [float(r["score"]) for r in rows
                if r.get("role") == "presence" and r.get("score") is not None]
    absence = [float(r["score"]) for r in rows
               if r.get("role") == "absence" and r.get("score") is not None]
    mpa = sum(presence) / len(presence) if presence else 1.0
    faa = (sum(absence) / len(absence)) if absence else 1.0
    lam = len(absence) / (len(presence) + len(absence)) if (presence or absence) else 0.0
    return max(0.0, mpa - lam * (1.0 - faa))


def summarize_agent(agent_name: str, results: List[CaseResult], runs: int = 1) -> dict:
    """单智能体聚合。results 覆盖全部 run × 全部用例。"""
    # 每次单独 run 的维度得分（用于稳定性）
    per_run_dim: Dict[int, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    dim_rows: Dict[str, List[dict]] = defaultdict(list)
    n_traced = n_localized = 0
    for r in results:
        for row in r.rows:
            dim = row.get("dimension") or r.dimension
            dim_rows[dim].append(row)
            if row.get("score") is not None:
                per_run_dim[r.run_index][dim].append(float(row["score"]))
            # LongMemEval 式检索定位率：检索来源 ∩ 证据 session 非空即定位成功
            ev = row.get("evidence_sessions") or []
            trace = row.get("retrieval_trace")
            if ev and trace is not None:
                n_traced += 1
                origins = {t.get("session_origin") for t in trace}
                if origins & set(ev):
                    n_localized += 1

    dimensions = {}
    for dim in DIMENSIONS:
        rows = dim_rows.get(dim, [])
        scored = [x for x in rows if x.get("score") is not None]
        wsum = sum(x.get("weight", 1.0) for x in scored)
        score = (sum(x["score"] * x.get("weight", 1.0) for x in scored) / wsum) if scored else 0.0
        verdicts: Dict[str, int] = defaultdict(int)
        for x in rows:
            verdicts[x.get("verdict", "not_evaluable")] += 1
        # 稳定性：各 run 的维度得分标准差
        run_scores = []
        for ri in sorted(per_run_dim.keys()):
            vals = per_run_dim[ri].get(dim, [])
            run_scores.append(sum(vals) / len(vals) if vals else 0.0)
        stability_std = statistics.pstdev(run_scores) if len(run_scores) > 1 else 0.0
        dimensions[dim] = {
            "score": round(score, 4),
            "n_probes": len(rows),
            "n_scored": len(scored),
            "n_not_evaluable": len(rows) - len(scored),
            "verdicts": dict(verdicts),
            "std_across_runs": round(stability_std, 4),
        }
    overall = sum(dimensions[d]["score"] for d in DIMENSIONS) / len(DIMENSIONS)
    per_case = []
    by_case: Dict[str, List[float]] = defaultdict(list)
    fama_values: List[float] = []
    mem_writes = mem_deletes = 0
    for r in results:
        if r.score is not None:
            by_case[r.case_id].append(float(r.score))
        fama_values.append(fama_for_rows(r.rows))
        evo = (r.evidence or {}).get("memory_evolution") or []
        for step in evo:
            mem_writes += len(step.get("added", []))
            mem_deletes += len(step.get("removed", []))
    case_difficulty = {r.case_id: r.difficulty for r in results}
    for cid, vals in by_case.items():
        per_case.append({"case_id": cid,
                         "difficulty": case_difficulty.get(cid, "medium"),
                         "score": round(100 * sum(vals) / len(vals), 2)})
    return {
        "agent": agent_name,
        "runs": runs,
        "n_cases": len({r.case_id for r in results}),
        "dimensions": dimensions,
        "overall": round(overall, 4),
        "total_findings_sensitive": sum(len(r.findings) for r in results),
        "memory_ops": {"writes": mem_writes, "deletes": mem_deletes},
        "staleness_violations": sum(
            1 for r in results for row in r.rows
            if row.get("probe_id") == "staleness_scan" and row.get("score") == 0.0),
        "fama_mean": round(sum(fama_values) / len(fama_values), 4) if fama_values else None,
        "difficulty_breakdown": _difficulty_breakdown(results),
        "relation_breakdown": _relation_breakdown(results),
        "difficulty_dimension": _difficulty_dimension_matrix(results),
        "per_case": per_case,
        "retrieval_localization": ({"n": n_traced, "hits": n_localized,
                                    "rate": round(n_localized / n_traced, 4)}
                                   if n_traced else None),
        "total_duration_sec": round(sum(r.duration_sec for r in results), 2),
        "per_case": per_case,
    }


def case_discrimination_top(summaries: List[dict], k: int = 10) -> List[dict]:  # type: ignore
    """BEAM 风格有区分力的用例排名。"""
    by_case: Dict[str, Dict[str, float]] = {}
    for s_ in summaries:
        for c in (s_.get("per_case") or []):
            by_case.setdefault(c["case_id"], {})[s_["agent"]] = c["score"]
    diff_map: Dict[str, str] = {}
    for s_ in summaries:
        for c in (s_.get("per_case") or []):
            diff_map.setdefault(c["case_id"], c.get("difficulty", "medium"))
    """BEAM 风格有区分力的用例排名：跨智能体最高分减最低分（极差越大越有判别力）。

    输入是 write_reports 里的 summaries 列表（每个 summary 已含 per_case）。
    """
    by_case: Dict[str, Dict[str, float]] = {}
    for s_ in summaries:
        for c in (s_.get("per_case") or []):
            by_case.setdefault(c["case_id"], {})[s_["agent"]] = c["score"]
    # 查 difficulty：先从 by_case 旁的 case_difficulty 拿（s 由 caller 注入）— 简化起见
    # 让 case_discrimination_top 接收一个 per_case 索引表，caller 注入
    rows = []
    for cid, scores in by_case.items():
        if scores:
            rows.append({
                "case_id": cid,
                "difficulty": diff_map.get(cid, "medium"),
                "discrimination": round(max(scores.values()) - min(scores.values()), 1),
                "scores": scores,
            })
    rows.sort(key=lambda r: -r["discrimination"])
    return rows[:k]


def compare_summaries(summaries: List[dict]) -> dict:
    """多智能体对比表（含各维度分差与总分排名）。"""
    agents = [s["agent"] for s in summaries]
    table = []
    for dim in DIMENSIONS:
        row = {"dimension": dim,
               "scores": {s["agent"]: s["dimensions"][dim]["score"] for s in summaries}}
        table.append(row)
    ranked = sorted(summaries, key=lambda s: -s["overall"])
    return {"agents": agents, "dimensions": table,
            "ranking": [{"agent": s["agent"], "overall": s["overall"]} for s in ranked]}


def bin_report_by_load(cases, summaries: List[dict], bins: tuple = (1, 2, 4, 8)) -> dict:
    """按"记忆负担"（用例 session 数）分档的对比报告（沿用 BEAM 思路）。

    bins: 升序的 session 数分界。
    返回: {bins: [...], by_agent: {agent: {label: 0..100, ...}, ...}}
    """
    case_load = {c.case_id: len(c.sessions) for c in cases}
    labels = _bin_labels(bins)
    by_agent: Dict[str, Dict[str, List[float]]] = {s["agent"]: {lab: [] for lab in labels}
                                                    for s in summaries}
    for s in summaries:
        for c in s.get("per_case", []):
            load = case_load.get(c["case_id"], 1)
            label = _bin_label_for(load, bins, labels)
            by_agent[s["agent"]][label].append(float(c["score"]))
    by_agent_avg = {a: {lab: round(sum(v) / len(v), 1) if v else None
                          for lab, v in bins_dict.items()}
                    for a, bins_dict in by_agent.items()}
    return {"bins": labels, "by_agent": by_agent_avg}


def _bin_labels(bins: tuple) -> List[str]:
    """最后一个分档为开放区间（N+），保证任何 session 数都有归属。"""
    out = ["1-%d sessions" % bins[0]]
    for i in range(1, len(bins)):
        out.append("%d-%d sessions" % (bins[i-1] + 1, bins[i]))
    out[-1] = "%d+ sessions" % (bins[-2] + 1 if len(bins) > 1 else 1)
    return out


def _bin_label_for(load: int, bins: tuple, labels: List[str]) -> str:
    for i, upper in enumerate(bins):
        if load <= upper:
            return labels[i]
    return labels[-1]
