# -*- coding: utf-8 -*-
"""membench 命令行入口。

    membench list                     查看内置用例
    membench validate                 校验数据集
    membench run --agent smart        运行评测（支持多次重复与多智能体）
    membench report <outdir>...       汇总生成对比报告
    membench demo                     三内置智能体全流程演示
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List

from . import __version__
from .loader import load_cases
from .report import write_reports

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CASES = os.path.join(PKG_ROOT, "cases")
DEFAULT_AGENTS_DIR = os.path.join(PKG_ROOT, "agents")


# LLM judge 两种 wire format 的默认端点与 key 环境变量（--judge-base-url /
# --judge-key-env 未显式给出时按格式取默认；N+26 起支持 anthropic）。
JUDGE_LLM_DEFAULTS = {
    "openai": {"base_url": "https://api.openai.com/v1", "key_env": "OPENAI_API_KEY"},
    "anthropic": {"base_url": "https://api.anthropic.com", "key_env": "ANTHROPIC_API_KEY"},
}


def _judge_from_args(args):
    judge_mode = getattr(args, "judge", "heuristic")
    if judge_mode == "heuristic":
        return None
    if judge_mode in JUDGE_LLM_DEFAULTS:
        from .judge import LLMJudge
        d = JUDGE_LLM_DEFAULTS[judge_mode]
        api_key = os.environ.get(getattr(args, "judge_key_env", "") or d["key_env"], "")
        return LLMJudge(base_url=getattr(args, "judge_base_url", "") or d["base_url"],
                        model=args.judge_model, api_key=api_key,
                        votes=args.judge_votes, api=judge_mode)
    raise SystemExit("未知 judge: %s（可选 heuristic/openai/anthropic）" % judge_mode)


def cmd_list(args) -> int:
    cases = load_cases([args.cases])
    print("共 %d 个用例（%s）" % (len(cases), args.cases))
    by_dim = {}
    for c in cases:
        by_dim.setdefault(c.dimension, []).append(c)
    from . import DIMENSIONS, DIMENSION_LABELS
    for dim in DIMENSIONS:
        print("\n[%s] %s" % (DIMENSION_LABELS[dim], dim))
        for c in by_dim.get(dim, []):
            print("  %-22s %-28s probes=%d %s"
                  % (c.case_id, c.title[:28], len(c.probes), c.difficulty))
    missing = [d for d in DIMENSIONS if d not in by_dim]
    if missing:
        print("\n警告：以下维度无用例:", ", ".join(missing))
    return 0


def cmd_validate(args) -> int:
    cases = load_cases([args.cases])
    from . import DIMENSIONS
    dims = {c.dimension for c in cases}
    print("校验通过：%d 个用例，覆盖维度 %d/%d" % (len(cases), len(dims), len(DIMENSIONS)))
    for d in DIMENSIONS:
        if d not in dims:
            print("  警告：维度 %s 无用例" % d)
    probe_types = set()
    for c in cases:
        for p in c.probes:
            probe_types.add(p.type)
    print("探针类型覆盖:", ", ".join(sorted(probe_types)))
    return 0


def cmd_run(args) -> int:
    from .agents import create_agent, create_agent_from_config
    from .runner import _safe_name, run_suite
    cases = load_cases([args.cases])
    if args.filter:
        keys = [k.strip().lower() for k in args.filter.split(",")]
        cases = [c for c in cases
                 if any(k in c.case_id.lower() or k in c.dimension or k in (c.tags or [])
                        for k in keys)]
        if not cases:
            print("过滤器未匹配任何用例", file=sys.stderr)
            return 2
    os.makedirs(args.out, exist_ok=True)
    judge = _judge_from_args(args)
    summaries = []
    agent_dirs = []
    for spec in _expand_agent_specs(args.agent):
        agent = create_agent(spec)
        print("== 运行智能体: %s（%d 用例 × %d 次）" % (agent.name, len(cases), args.runs))
        s = run_suite(agent, cases, out_dir=args.out, runs=args.runs,
                      judge_free=(judge.judge_free if judge is not None else None),
                      keep_workdir=args.keep_workdir,
                      quiet=args.quiet)
        summaries.append(s)
        agent_dirs.append(os.path.join(args.out, _safe_name(agent.name)))
        print("   总分 %.1f | 六维: %s" % (
            100 * s["overall"],
            " ".join("%s=%.0f" % (d, 100 * s["dimensions"][d]["score"])
                     for d in s["dimensions"])))
    paths = write_reports(summaries, args.out, cases=cases, agent_dirs=agent_dirs)
    print("报告: %s" % paths["html"])
    return 0


def _expand_agent_specs(specs: List[str]) -> List[str]:
    """展开 --agent：JSON 文件内容为数组时，展开为批量配置（临时落盘）。"""
    import json
    import tempfile
    expanded: List[str] = []
    for spec in specs:
        if spec.endswith(".json") and os.path.isfile(spec):
            try:
                with open(spec, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                data = None
            if isinstance(data, list):
                cfg_dir = tempfile.mkdtemp(prefix="membench_agents_")
                for i, cfg in enumerate(data):
                    if not isinstance(cfg, dict) or "kind" not in cfg:
                        raise SystemExit("%s: 数组第 %d 项不是合法智能体配置" % (spec, i))
                    path = os.path.join(cfg_dir, "agent_%02d.json" % i)
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, ensure_ascii=False, indent=2)
                    expanded.append(path)
                continue
        expanded.append(spec)
    return expanded


def cmd_gen(args) -> int:
    """按模板批量生成用例：展示"数据生成方式"，expected 与注入变量同源。"""
    from .generator import generate
    cases = generate(variants=args.variants, seed=args.seed)
    os.makedirs(args.out, exist_ok=True)
    try:
        import yaml  # type: ignore
        dump = lambda data, f: yaml.safe_dump(  # noqa: E731
            data, f, allow_unicode=True, sort_keys=False)
        ext = ".yaml"
    except ImportError:
        dump = lambda data, f: json.dump(data, f, ensure_ascii=False, indent=2)  # noqa: E731
        ext = ".json"
    by_dim = {}
    for c in cases:
        by_dim.setdefault(c["dimension"], []).append(c)
    for dim, items in by_dim.items():
        dim_dir = os.path.join(args.out, dim)
        os.makedirs(dim_dir, exist_ok=True)
        for c in items:
            path = os.path.join(dim_dir, c["case_id"] + ext)
            with open(path, "w", encoding="utf-8") as f:
                dump({"schema_version": 1, **c}, f)
    # 自检：生成结果必须能通过静态校验
    loaded = load_cases([args.out])
    print("已生成 %d 个用例到 %s（校验通过，全部可加载）" % (len(loaded), args.out))
    return 0


def cmd_report(args) -> int:
    summaries = []
    for d in args.outdirs:
        sp = os.path.join(d, "summary.json")
        if not os.path.exists(sp):
            print("警告: %s 不存在，跳过" % sp, file=sys.stderr)
            continue
        with open(sp, "r", encoding="utf-8") as f:
            summaries.append(json.load(f))
    if not summaries:
        print("没有可汇总的结果目录", file=sys.stderr)
        return 2
    out = args.out or os.path.dirname(os.path.abspath(summaries and args.outdirs[0]))
    # 复用 bin 报告的 case 上下文：第一个 outdir 上一级目录的 cases/
    cases_dir = os.path.join(os.path.dirname(os.path.abspath(args.outdirs[0])), "..", "cases")
    cases = None
    if os.path.isdir(os.path.normpath(cases_dir)):
        try:
            cases = load_cases([os.path.normpath(cases_dir)])
        except Exception:
            cases = None
    paths = write_reports(summaries, out, cases=cases)
    print("报告: %s\nMarkdown: %s\nJSON: %s" % (paths["html"], paths["markdown"], paths["json"]))
    return 0


def cmd_doctor(args) -> int:
    from .doctor import main as doctor_main
    return doctor_main()


def cmd_demo(args) -> int:
    """全流程演示：三个内置智能体 × 内置用例集 → 对比报告。"""
    from .agents import create_agent
    from .runner import _safe_name, run_suite
    cases = load_cases([args.cases or DEFAULT_CASES])
    os.makedirs(args.out, exist_ok=True)
    summaries = []
    agent_dirs = []
    for spec in ("nomem", "naive", "smart"):
        agent = create_agent(spec)
        print("== demo 智能体: %s（%d 用例 × %d 次）" % (agent.name, len(cases), args.runs))
        s = run_suite(agent, cases, out_dir=args.out, runs=args.runs, quiet=args.quiet)
        summaries.append(s)
        agent_dirs.append(os.path.join(args.out, _safe_name(agent.name)))
        print("   总分 %.1f" % (100 * s["overall"]))
    paths = write_reports(summaries, args.out, cases=cases, agent_dirs=agent_dirs)
    print("\n演示完成。对比报告: %s" % paths["html"])
    return 0


def main(argv: List[str] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="membench",
        description="openKylin 智能体长期记忆自动化评测基准")
    ap.add_argument("--version", action="version", version="membench " + __version__)
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("list", help="列出用例")
    p.add_argument("--cases", default=DEFAULT_CASES)
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("validate", help="校验数据集")
    p.add_argument("--cases", default=DEFAULT_CASES)
    p.set_defaults(fn=cmd_validate)

    p = sub.add_parser("run", help="运行评测")
    p.add_argument("--agent", action="append", required=True,
                   help="内置名(nomem/naive/smart)或智能体配置 JSON；可多次指定")
    p.add_argument("--cases", default=DEFAULT_CASES)
    p.add_argument("--runs", type=int, default=1, help="每用例重复次数（测稳定性）")
    p.add_argument("--filter", default="", help="逗号分隔的关键字过滤 case_id/维度/标签")
    p.add_argument("--judge", choices=["heuristic", "openai", "anthropic"],
                   default="heuristic",
                   help="free 探针判定：heuristic 离线；openai/anthropic 为 LLM judge 的两种 wire format")
    p.add_argument("--judge-base-url", default="",
                   help="LLM 端点；缺省随 --judge：openai=https://api.openai.com/v1（含版本段），anthropic=https://api.anthropic.com（不含）")
    p.add_argument("--judge-model", default="gpt-4o-mini")
    p.add_argument("--judge-key-env", default="",
                   help="API key 的环境变量名；缺省随 --judge：OPENAI_API_KEY / ANTHROPIC_API_KEY")
    p.add_argument("--judge-votes", type=int, default=1)
    p.add_argument("--keep-workdir", action="store_true", help="保留沙箱工作目录用于排查")
    p.add_argument("--quiet", action="store_true", help="不打印逐用例进度")
    p.add_argument("-o", "--out", default="membench_results")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("doctor", help="openKylin 环境自检（复现前先跑一遍）")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("gen", help="按模板批量生成用例（数据生成方式演示）")
    p.add_argument("-o", "--out", default="cases_generated")
    p.add_argument("--variants", type=int, default=3, help="每个模板生成的变体数")
    p.add_argument("--seed", type=int, default=42, help="随机种子（保证可复现）")
    p.set_defaults(fn=cmd_gen)

    p = sub.add_parser("report", help="汇总多个结果目录生成对比报告")
    p.add_argument("outdirs", nargs="+", help="含 summary.json 的智能体结果目录")
    p.add_argument("-o", "--out", default="")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("demo", help="三内置智能体全流程演示")
    p.add_argument("--cases", default=DEFAULT_CASES)
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--quiet", action="store_true")
    p.add_argument("-o", "--out", default="membench_demo")
    p.set_defaults(fn=cmd_demo)

    args = ap.parse_args(argv)
    if not getattr(args, "cmd", None):
        ap.print_help()
        return 1
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
