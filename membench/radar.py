# -*- coding: utf-8 -*-
"""纯标准库 SVG 雷达图（零依赖，openKylin 任意看图器/浏览器可打开）。"""
from __future__ import annotations

import math
from typing import Dict
from xml.sax.saxutils import escape

from . import DIMENSIONS, DIMENSION_LABELS

PALETTE = ["#2f6fed", "#e8590c", "#0ca678", "#9c36b5", "#f59f00", "#c92a2a"]


def _polar(cx: float, cy: float, r: float, angle_deg: float):
    rad = math.radians(angle_deg)
    return cx + r * math.cos(rad), cy + r * math.sin(rad)


def radar_svg(series: Dict[str, Dict[str, float]], title: str = "",
              size: int = 460) -> str:
    """series: {agent_name: {dimension: score(0..1)}}，渲染为多边形叠加雷达图。"""
    cx = cy = size / 2
    r_max = size * 0.34
    n = len(DIMENSIONS)
    start_angle = -90.0
    step = 360.0 / n

    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
             'viewBox="0 0 %d %d" font-family="sans-serif">' % (size, size + 40, size, size + 40)]
    if title:
        parts.append('<text x="%d" y="24" text-anchor="middle" font-size="16" '
                     'font-weight="bold" fill="#222">%s</text>'
                     % (size / 2, escape(title)))

    # 网格环（20% 步长）
    for k in range(1, 6):
        r = r_max * k / 5.0
        pts = " ".join("%.1f,%.1f" % _polar(cx, cy, r, start_angle + i * step)
                       for i in range(n))
        fill = '#f8f9fa' if k % 2 == 0 else '#ffffff'
        parts.append('<polygon points="%s" fill="%s" stroke="#dee2e6" stroke-width="1"/>'
                     % (pts, fill))
        parts.append('<text x="%.1f" y="%.1f" font-size="9" fill="#999">%d%%</text>'
                     % (cx + 3, cy - r + 3, k * 20))

    # 轴与标签
    for i, dim in enumerate(DIMENSIONS):
        x, y = _polar(cx, cy, r_max, start_angle + i * step)
        parts.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#ced4da"/>'
                     % (cx, cy, x, y))
        lx, ly = _polar(cx, cy, r_max + 26, start_angle + i * step)
        label = "%s %s" % (DIMENSION_LABELS[dim], dim)
        anchor = "middle"
        parts.append('<text x="%.1f" y="%.1f" text-anchor="%s" font-size="11" fill="#444">%s</text>'
                     % (lx, ly + 4, anchor, escape(label)))

    # 数据多边形
    for idx, (name, scores) in enumerate(series.items()):
        color = PALETTE[idx % len(PALETTE)]
        pts = []
        for i, dim in enumerate(DIMENSIONS):
            v = max(0.0, min(1.0, float(scores.get(dim, 0.0))))
            pts.append(_polar(cx, cy, r_max * v, start_angle + i * step))
        pt_str = " ".join("%.1f,%.1f" % p for p in pts)
        parts.append('<polygon points="%s" fill="%s" fill-opacity="0.18" '
                     'stroke="%s" stroke-width="2"/>' % (pt_str, color, color))
        for (x, y) in pts:
            parts.append('<circle cx="%.1f" cy="%.1f" r="3" fill="%s"/>' % (x, y, color))

    # 图例
    legend_y = size + 14
    lx0 = 20
    for idx, name in enumerate(series.keys()):
        color = PALETTE[idx % len(PALETTE)]
        parts.append('<rect x="%d" y="%d" width="12" height="12" fill="%s"/>'
                     % (lx0, legend_y, color))
        parts.append('<text x="%d" y="%d" font-size="12" fill="#333">%s（总分 %.0f）</text>'
                     % (lx0 + 16, legend_y + 10, escape(name),
                        100 * sum(series[name].get(d, 0.0) for d in DIMENSIONS) / len(DIMENSIONS)))
        lx0 += 16 + 12 * (len(name) * 2 + 14)
    parts.append("</svg>")
    return "\n".join(parts)


def bars_svg(scores: Dict[str, float], title: str = "", width: int = 460) -> str:
    """横向条形图：维度得分明细。scores: {label: 0..1}"""
    bar_h = 22
    label_w = 150
    height = 40 + bar_h * len(scores) + 10
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
             'font-family="sans-serif">' % (width, height)]
    if title:
        parts.append('<text x="10" y="18" font-size="14" font-weight="bold" fill="#222">%s</text>'
                     % escape(title))
    for i, (label, v) in enumerate(scores.items()):
        y = 34 + i * bar_h
        w = (width - label_w - 60) * max(0.0, min(1.0, v))
        color = PALETTE[0] if v >= 0.6 else (PALETTE[4] if v >= 0.3 else PALETTE[5])
        parts.append('<text x="%d" y="%d" font-size="11" fill="#444" text-anchor="end">%s</text>'
                     % (label_w - 8, y + 15, escape(label)))
        parts.append('<rect x="%d" y="%d" width="%d" height="16" fill="#e9ecef" rx="2"/>'
                     % (label_w, y, width - label_w - 60))
        parts.append('<rect x="%d" y="%d" width="%.1f" height="16" fill="%s" rx="2"/>'
                     % (label_w, y, w, color))
        parts.append('<text x="%d" y="%d" font-size="11" fill="#333">%d</text>'
                     % (width - 44, y + 13, round(100 * v)))
    parts.append("</svg>")
    return "\n".join(parts)
