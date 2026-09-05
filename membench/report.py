# -*- coding: utf-8 -*-
"""报告生成：JSON → Markdown / 自包含 HTML（内嵌 SVG 雷达图）。"""
from __future__ import annotations

import json
import os
from typing import Dict, List

from . import DIMENSIONS, DIMENSION_LABELS
from .aggregate import bin_report_by_load, compare_summaries, fama_for_rows
from .scoring import _snippet
from .radar import bars_svg, radar_svg

CSS = """
body{font-family:sans-serif;margin:24px auto;max-width:1080px;color:#222;line-height:1.5}
h1,h2,h3{color:#1a3a6b} table{border-collapse:collapse;margin:12px 0;width:100%}
th,td{border:1px solid #ddd;padding:6px 10px;text-align:center;font-size:13px}
th{background:#f1f3f5} .good{color:#0ca678;font-weight:bold}
.mid{color:#f59f00;font-weight:bold} .bad{color:#c92a2a;font-weight:bold}
.note{color:#666;font-size:12px} pre{background:#f8f9fa;padding:8px;overflow-x:auto}
"""


def _cls(v: float) -> str:
    return "good" if v >= 0.6 else ("mid" if v >= 0.3 else "bad")


def build_markdown(summaries: List[dict], cases=None) -> str:
    cmp_data = compare_summaries(summaries)
    lines = ["# openKylin 智能体长期记忆评测报告", "",
             "## 总分排名", "", "| 排名 | 智能体 | 总分 | FAMA |", "|---|---|---|---|"]
    for i, r in enumerate(cmp_data["ranking"], 1):
        fa = next((x.get("fama_mean") for x in summaries if x["agent"] == r["agent"]), None)
        lines.append("| %d | %s | %.1f | %s |" % (i, r["agent"], 100 * r["overall"],
                                                  "%.1f" % (100 * fa) if fa is not None else "-"))
    lines += ["", "## 六维对比", "",
              "| 维度 | " + " | ".join(cmp_data["agents"]) + " |",
              "|---|" + "---|" * len(cmp_data["agents"])]
    for row in cmp_data["dimensions"]:
        cells = ["%.0f" % (100 * row["scores"][a]) for a in cmp_data["agents"]]
        lines.append("| %s（%s） | %s |" % (DIMENSION_LABELS[row["dimension"]],
                                            row["dimension"], " | ".join(cells)))
    if cases is not None:
        bins = bin_report_by_load(cases, summaries)
        lines += ["", "## 记忆负担分档对比（沿用 BEAM 思路）", ""]
        header = "| 智能体 | " + " | ".join(bins["bins"]) + " |"
        sep = "|---|" + "---|" * len(bins["bins"])
        lines.append(header); lines.append(sep)
        for a, per_bin in bins["by_agent"].items():
            cells = [("%.0f" % v) if v is not None else "-" for v in
                     (per_bin.get(lab) for lab in bins["bins"])]
            lines.append("| %s | %s |" % (a, " | ".join(cells)))
    diff_rows = {s["agent"]: s.get("difficulty_breakdown", {}) for s in summaries}
    diff_keys = ["easy", "medium", "hard"]
    if any(diff_rows.values()):
        lines += ["", "## 难度分层得分", "",
                  "| 智能体 | easy | medium | hard |", "|---|---|---|---|"]
        for a, per in diff_rows.items():
            lines.append("| %s | %s |" % (a, " | ".join(
                ("%.0f" % per[k]) if k in per else "-" for k in diff_keys)))
    diff_keys = ["easy", "medium", "hard"]
    dim_cols = DIMENSIONS
    mat = {s["agent"]: s.get("difficulty_dimension", {}) for s in summaries}
    rel_by = {s["agent"]: s.get("relation_breakdown", {}) for s in summaries}
    if any(rel_by.values()):
        lines += ["", "## 关系型专项（SubtleMemory 风格）", "",
                  "| 智能体 | 难度 | complementary | nuanced | contradictory | abstain |",
                  "|---|---|---|---|---|---|"]
        for a, m in rel_by.items():
            if not m:
                continue
            for dk in ("easy", "medium", "hard"):
                if dk not in m:
                    continue
                cells = [("%.0f" % m[dk][col]) if m[dk].get(col) is not None else "-"
                         for col in ("complementary", "nuanced", "contradictory", "abstain")]
                lines.append("| %s | %s | %s |" % (a, dk, " | ".join(cells)))
    if any(mat.values()):
        lines += ["", "## 难度 × 维度热力表", "",
                  "| 智能体 | 难度 | " + " | ".join(DIMENSION_LABELS[d_] for d_ in dim_cols) + " |",
                  "|---|---|" + "---|" * len(dim_cols)]
        for a, m in mat.items():
            if not m:
                continue
            for dk in diff_keys:
                if dk not in m:
                    continue
                cells = [("%.0f" % m[dk][dim]) if m[dk].get(dim) is not None else "-" for dim in dim_cols]
                lines.append("| %s | %s | %s |" % (a, dk, " | ".join(cells)))
    if any(s.get("case_discrimination_top") for s in summaries):
        top = summaries[0].get("case_discrimination_top") or []
        if top:
            lines += ["", "## 高判别力用例（BEAM 风格：跨智能体极差最大）", "",
                      "| 用例 | 难度 | 判别度 |", "|---|---|---|"]
            for t in top:
                lines.append("| %s | %s | %.0f |" % (t["case_id"], t.get("difficulty", "?"),
                                                 t["discrimination"]))
    lines += ["", "## 五分类裁决分布", ""]
    for s in summaries:
        lines.append("### %s" % s["agent"])
        lines += ["", "| 维度 | correct | miss | confusion | improper_persistence | improper_reuse | 不可评 |",
                  "|---|---|---|---|---|---|---|"]
        for dim in DIMENSIONS:
            d = s["dimensions"][dim]
            v = d["verdicts"]
            lines.append("| %s | %d | %d | %d | %d | %d | %d |" % (
                DIMENSION_LABELS[dim], v.get("correct", 0), v.get("miss", 0),
                v.get("confusion", 0), v.get("improper_persistence", 0),
                v.get("improper_reuse", 0), d["n_not_evaluable"]))
        lines.append("")
    lines.append("## 稳定性（各维度跨 run 标准差）")
    lines.append("")
    lines.append("| 智能体 | " + " | ".join(DIMENSION_LABELS[d] for d in DIMENSIONS) + " |")
    lines.append("|---|" + "---|" * len(DIMENSIONS))
    for s in summaries:
        stds = ["%.3f" % s["dimensions"][d]["std_across_runs"] for d in DIMENSIONS]
        lines.append("| %s | %s |" % (s["agent"], " | ".join(stds)))
    return "\n".join(lines)


def build_html(summaries: List[dict], out_path: str, cases=None) -> str:
    cmp_data = compare_summaries(summaries)
    series = {s["agent"]: {d: s["dimensions"][d]["score"] for d in DIMENSIONS}
              for s in summaries}
    radar = radar_svg(series, title="六维长期记忆能力对比")
    html = ["<!DOCTYPE html><html><head><meta charset='utf-8'>",
            "<title>openKylin 智能体长期记忆评测报告</title>",
            "<style>%s</style></head><body>" % CSS,
            '<nav style="background:#1a3a6b;color:#fff;padding:8px 16px;font-size:13px">'
            '<a href="#rank" style="color:#fff;margin-right:14px">排名</a>'
            '<a href="#heat" style="color:#fff;margin-right:14px">难度×维度</a>'
            '<a href="#top-disc" style="color:#fff;margin-right:14px">高判别用例</a>'
            '<a href="evidence.html" style="color:#fff;margin-right:14px">证据查看器</a>'
            '</nav>',
            "<h1>openKylin 智能体长期记忆自动化评测报告</h1>",
            "<div class='note'>由 membench 自动生成 · 五分类裁决：correct/miss/confusion/"
            "improper_persistence/improper_reuse · "
            "<a href='evidence.html'>逐用例证据查看器（为什么扣分）</a></div>",
            radar,
            "<h2 id='rank'>总分排名</h2><table><tr><th>排名</th><th>智能体</th><th>总分</th>"
            "<th>FAMA</th></tr>"]
    for i, r in enumerate(cmp_data["ranking"], 1):
        fa = next((x.get("fama_mean") for x in summaries if x["agent"] == r["agent"]), None)
        html.append("<tr><td>%d</td><td>%s</td><td class='%s'>%.1f</td><td>%s</td></tr>"
                    % (i, r["agent"], _cls(r["overall"]), 100 * r["overall"],
                       ("%.1f" % (100 * fa)) if fa is not None else "-"))
    html.append("</table>")
    diff_rows = {s["agent"]: s.get("difficulty_breakdown", {}) for s in summaries}
    if any(diff_rows.values()):
        html.append("<h2>难度分层得分</h2><table><tr><th>智能体</th>"
                    "<th>easy</th><th>medium</th><th>hard</th></tr>")
        for a, per in diff_rows.items():
            html.append("<tr><td>%s</td>" % a)
            for k in ("easy", "medium", "hard"):
                html.append("<td>%s</td>" % (("%.0f" % per[k]) if k in per else "-"))
            html.append("</tr>")
        html.append("</table>")
    diff_keys = ["easy", "medium", "hard"]
    mat = {s["agent"]: s.get("difficulty_dimension", {}) for s in summaries}
    if any(mat.values()):
        html.append("<h2 id='heat'>难度 × 维度热力表</h2><table><tr><th>智能体</th><th>难度</th>")
        html.extend("<th>%s</th>" % DIMENSION_LABELS[d_] for d_ in DIMENSIONS)
        html.append("</tr>")
        for a, m in mat.items():
            if not m:
                continue
            for dk in diff_keys:
                if dk not in m:
                    continue
                html.append("<tr><td>%s</td><td>%s</td>" % (a, dk))
                for dim in DIMENSIONS:
                    v = m[dk].get(dim)
                    html.append("<td class='%s'>%s</td>" % (
                        _cls((v or 0) / 100), ("%.0f" % v) if v is not None else "-"))
                html.append("</tr>")
        html.append("</table>")
    if any(s.get("case_discrimination_top") for s in summaries):
        top = summaries[0].get("case_discrimination_top") or []
        if top:
            html.append("<h2 id='top-disc'>高判别力用例（跨智能体极差最大）</h2>"
                        "<table><tr><th>用例</th><th>难度</th><th>判别度</th></tr>")
            for t in top:
                html.append("<tr><td>%s</td><td>%s</td><td>%.0f</td></tr>"
                            % (t["case_id"], t.get("difficulty", "?"), t["discrimination"]))
            html.append("</table>")
    if cases is not None:
        bins = bin_report_by_load(cases, summaries)
        html.append("<h2 id='bins'>记忆负担分档对比</h2><p class='note'>沿用 BEAM 思路：按用例 session 数分档，观察随记忆负担增长的退化曲线。</p>")
        html.append("<table><tr><th>智能体</th>")
        html.extend("<th>%s</th>" % b for b in bins["bins"])
        html.append("</tr>")
        for a, per_bin in bins["by_agent"].items():
            html.append("<tr><td>%s</td>" % a)
            for lab in bins["bins"]:
                v = per_bin.get(lab)
                html.append("<td class='%s'>%s</td>" % (
                    _cls((v or 0) / 100), (("%.0f" % v) if v is not None else "-")))
            html.append("</tr>")
        html.append("</table>")
    html.append("<h2>六维对比</h2><table><tr><th>维度</th>")
    html.extend("<th>%s</th>" % a for a in cmp_data["agents"])
    html.append("</tr>")
    for row in cmp_data["dimensions"]:
        html.append("<tr><td>%s<br><span class='note'>%s</span></td>" % (
            DIMENSION_LABELS[row["dimension"]], row["dimension"]))
        for a in cmp_data["agents"]:
            v = row["scores"][a]
            html.append("<td class='%s'>%.0f</td>" % (_cls(v), 100 * v))
        html.append("</tr>")
    html.append("</table>")

    html.append("<h2>各智能体维度明细</h2>")
    for s in summaries:
        scores = {DIMENSION_LABELS[d] + " " + d: s["dimensions"][d]["score"] for d in DIMENSIONS}
        html.append("<h3>%s（总分 %.1f）</h3>" % (s["agent"], 100 * s["overall"]))
        html.append(bars_svg(scores, title=""))
        html.append("<table><tr><th>维度</th><th>得分</th><th>探针数</th>"
                    "<th>不可评</th><th>correct</th><th>miss</th><th>confusion</th>"
                    "<th>improper_persist</th><th>improper_reuse</th><th>std</th></tr>")
        for dim in DIMENSIONS:
            d = s["dimensions"][dim]
            v = d["verdicts"]
            html.append("<tr><td>%s</td><td class='%s'>%.0f</td><td>%d</td><td>%d</td>"
                        "<td>%d</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td><td>%.3f</td></tr>"
                        % (DIMENSION_LABELS[dim], _cls(d["score"]), 100 * d["score"],
                           d["n_probes"], d["n_not_evaluable"],
                           v.get("correct", 0), v.get("miss", 0), v.get("confusion", 0),
                           v.get("improper_persistence", 0), v.get("improper_reuse", 0),
                           d["std_across_runs"]))
        html.append("</table>")
        if s.get("total_findings_sensitive"):
            html.append("<p class='bad'>敏感信息持久化事件：%d 次</p>"
                        % s["total_findings_sensitive"])
    html.append("</body></html>")

    doc = "\n".join(html)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return doc


def write_reports(summaries: List[dict], out_dir: str, cases=None,
                  agent_dirs: Optional[List[str]] = None) -> Dict[str, str]:
    # 先算 case_discrimination_top，确保 build_markdown/build_html 拿到
    from .aggregate import case_discrimination_top
    disc = case_discrimination_top(summaries)
    for s_ in summaries:
        s_["case_discrimination_top"] = disc
    """写出 comparison/{report.html, comparison.md, summary.json}，返回文件路径表。"""
    cmp_dir = os.path.join(out_dir, "comparison")
    os.makedirs(cmp_dir, exist_ok=True)
    paths = {}
    html_path = os.path.join(cmp_dir, "report.html")
    build_html(summaries, html_path, cases=cases)
    paths["html"] = html_path
    md_path = os.path.join(cmp_dir, "comparison.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_markdown(summaries, cases=cases))
    paths["markdown"] = md_path
    js_path = os.path.join(cmp_dir, "summaries.json")
    with open(js_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)
    paths["json"] = js_path
    # 单独落盘（disc 已在函数顶部计算）
    with open(os.path.join(cmp_dir, "case_discrimination.json"), "w",
              encoding="utf-8") as f:
        json.dump(disc, f, ensure_ascii=False, indent=2)
    paths["discrimination"] = os.path.join(cmp_dir, "case_discrimination.json")
    if agent_dirs:
        ev_path = os.path.join(cmp_dir, "evidence.html")
        build_evidence_viewer(agent_dirs, ev_path)
        paths["evidence"] = ev_path
    if cases is not None:
        bin_path = os.path.join(cmp_dir, "bin_report.json")
        with open(bin_path, "w", encoding="utf-8") as f:
            json.dump(bin_report_by_load(cases, summaries), f,
                      ensure_ascii=False, indent=2)
        paths["bin_report"] = bin_path
    return paths


def build_evidence_viewer(agent_dirs: List[str], out_path: str) -> str:
    """单用例证据查看器：评审可逐条点开"为什么扣分"。

    数据源：各智能体结果目录下的 runs/run*/<case_id>.json。
    输出：自包含 HTML（含裁决徽章、对话轨迹、记忆演变、扫描发现）。
    """
    import glob as _glob

    parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'>",
             "<title>membench 逐用例证据查看器</title>",
             "<style>%s</style>" % CSS + """
.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;color:#fff}
.correct{background:#0ca678}.miss{background:#f59f00}.confusion{background:#e8590c}
.improper_persistence{background:#c92a2a}.improper_reuse{background:#9c36b5}
.not_evaluable{background:#adb5bd}
details{margin:6px 0}summary{cursor:pointer;color:#1a3a6b}
.case{border:1px solid #e0e0e0;border-radius:8px;padding:10px;margin:14px 0}
.evoblock{font-size:12px;color:#555;margin:4px 0}
""", "</head><body>",
             "<h1>membench 逐用例证据查看器</h1>",
             "<div class='note'>每条探针裁决均含可解释理由与命中片段；"
             "对话轨迹/记忆演变/记忆库终态可展开。</div>"]
    agent_names = []
    for adir in agent_dirs:
        name = os.path.basename(os.path.normpath(adir))
        files = sorted(_glob.glob(os.path.join(adir, "runs", "run*", "*.json")))
        if not files:
            continue
        agent_names.append(name)
        parts.append("<h2 id='agent-%s'>智能体：%s（%d 份证据）</h2>"
                     % (name, name, len(files)))
        parts.append("<p>")
        for fp in files:
            cid = os.path.splitext(os.path.basename(fp))[0]
            parts.append("<a href='#ev-%s-%s'>%s</a> · " % (name, cid, cid))
        parts.append("</p>")
        for fp in files:
            try:
                with open(fp, encoding="utf-8") as f:
                    d = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            cid = d.get("case_id", os.path.basename(fp))
            anchor = "ev-%s-%s" % (name, cid)
            parts.append("<div class='case' id='%s'>" % anchor)
            parts.append("<h3>%s · %s <span class='note'>(%s, 难度 %s, run %d)</span></h3>"
                         % (name, cid, d.get("dimension", "?"),
                            d.get("difficulty", "?"), d.get("run_index", 1)))
            score = d.get("score")
            fama = fama_for_rows(d.get("rows", []))
            parts.append("<div>用例得分：<b>%s</b> · FAMA：<b>%.0f</b></div>"
                         % ("%.0f" % (100 * score) if score is not None else "不可评",
                            100 * fama))
            parts.append("<table><tr><th>探针</th><th>角色</th><th>裁决</th><th>分</th>"
                         "<th>理由（含证据片段）</th><th>回复</th><th>检索来源</th></tr>")
            for row in d.get("rows", []):
                origins = sorted({t.get("session_origin") for t in (row.get("retrieval_trace") or [])
                                  if t.get("session_origin")})
                parts.append("<tr><td>%s</td><td>%s</td>"
                             "<td><span class='badge %s'>%s</span></td><td>%s</td>"
                             "<td>%s</td><td>%s</td><td>%s</td></tr>"
                             % (row.get("probe_id"), row.get("role", "-"),
                                row.get("verdict"), row.get("verdict"),
                                "—" if row.get("score") is None else "%.1f" % row["score"],
                                row.get("reason", ""), _snippet(row.get("reply", ""), 60) or "—",
                                ",".join(origins) or "—"))
            parts.append("</table>")
            evo = (d.get("evidence") or {}).get("memory_evolution")
            if evo:
                parts.append("<details><summary>记忆演变轨迹（%d 步）</summary>" % len(evo))
                for st in evo:
                    parts.append("<div class='evoblock'>%s 后：+%d / -%d（存量 %d）"
                                 "&nbsp;新增: %s&nbsp;删除: %s</div>"
                                 % (st.get("after_session"), len(st.get("added", [])),
                                    len(st.get("removed", [])), st.get("n_items", 0),
                                    (", ".join(st.get("added", []))[:120] or "—"),
                                    (", ".join(st.get("removed", []))[:120] or "—")))
                parts.append("</details>")
            mdump = (d.get("evidence") or {}).get("memory_dump")
            if mdump is not None:
                parts.append("<details><summary>记忆库终态（%d 条）</summary>" % len(mdump))
                for item in mdump:
                    parts.append("<div class='evoblock'>- %s</div>" % item)
                parts.append("</details>")
            transcript = (d.get("evidence") or {}).get("transcript") or []
            parts.append("<details><summary>对话轨迹（%d 段）</summary>" % len(transcript))
            for st in transcript:
                date = "（%s）" % st["date"] if st.get("date") else ""
                parts.append("<div class='evoblock'>[%s]%s %s</div>"
                             % (st.get("session_id"), date, st.get("note") or ""))
                for t in st.get("turns", []):
                    who = "用户" if t.get("role") == "user" else "智能体"
                    parts.append("<div class='evoblock'>&nbsp;&nbsp;%s：%s</div>"
                                 % (who, t.get("content", "")))
                if not st.get("turns"):
                    parts.append("<div class='evoblock'>&nbsp;&nbsp;（无消息）</div>")
            parts.append("</details></div>")
    parts.append("</body></html>")
    doc = "\n".join(parts)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return doc
