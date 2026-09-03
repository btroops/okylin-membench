# -*- coding: utf-8 -*-
"""报告生成：JSON → Markdown / 自包含 HTML（内嵌 SVG 雷达图）。"""
from __future__ import annotations

import json
import os
from typing import Dict, List

from . import DIMENSIONS, DIMENSION_LABELS
from .aggregate import bin_report_by_load, compare_summaries
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
             "## 总分排名", "", "| 排名 | 智能体 | 总分 |", "|---|---|---|"]
    for i, r in enumerate(cmp_data["ranking"], 1):
        lines.append("| %d | %s | %.1f |" % (i, r["agent"], 100 * r["overall"]))
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
            "<h1>openKylin 智能体长期记忆自动化评测报告</h1>",
            "<div class='note'>由 membench 自动生成 · 五分类裁决：correct/miss/confusion/"
            "improper_persistence/improper_reuse</div>",
            radar,
            "<h2>总分排名</h2><table><tr><th>排名</th><th>智能体</th><th>总分</th></tr>"]
    for i, r in enumerate(cmp_data["ranking"], 1):
        html.append("<tr><td>%d</td><td>%s</td><td class='%s'>%.1f</td></tr>"
                    % (i, r["agent"], _cls(r["overall"]), 100 * r["overall"]))
    html.append("</table>")
    if cases is not None:
        bins = bin_report_by_load(cases, summaries)
        html.append("<h2>记忆负担分档对比</h2><p class='note'>沿用 BEAM 思路：按用例 session 数分档，观察随记忆负担增长的退化曲线。</p>")
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


def write_reports(summaries: List[dict], out_dir: str, cases=None) -> Dict[str, str]:
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
    if cases is not None:
        bin_path = os.path.join(cmp_dir, "bin_report.json")
        with open(bin_path, "w", encoding="utf-8") as f:
            json.dump(bin_report_by_load(cases, summaries), f,
                      ensure_ascii=False, indent=2)
        paths["bin_report"] = bin_path
    return paths
