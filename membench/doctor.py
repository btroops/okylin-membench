# -*- coding: utf-8 -*-
"""环境自检（doctor）：面向 openKylin 标准环境的适配性检查。

用法：membench doctor
检查项全部围绕"评审方在 openKylin 上复现"可能踩的坑：
python 版本、PyYAML、用例可加载、内置智能体可运行、subproc 协议回环、
临时目录可写、UTF-8 输出、CJK 字体提示。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from typing import List

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_checks() -> List[dict]:
    checks: List[dict] = []

    def add(name: str, ok: bool, detail: str, warn: bool = False):
        checks.append({"name": name, "status": "PASS" if ok else
                       ("WARN" if warn else "FAIL"), "detail": detail})

    # 1) Python 版本
    v = sys.version_info
    add("python>=3.8", v >= (3, 8), "当前 %s.%s.%s" % (v.major, v.minor, v.micro))

    # 2) PyYAML（JSON 用例不需要，故缺失只告警）
    try:
        import yaml  # noqa: F401
        add("pyyaml", True, "可用（YAML 用例可读）")
    except ImportError:
        add("pyyaml", False, "缺失：YAML 用例不可读；请安装 python3-yaml 或改用 .json 用例",
            warn=True)

    # 3) 用例可加载
    try:
        from .loader import load_cases
        cases = load_cases([os.path.join(PKG_ROOT, "cases")])
        add("cases", len(cases) >= 29, "加载 %d 个内置用例" % len(cases))
    except Exception as e:  # noqa: BLE001
        add("cases", False, "加载失败: %s" % e)

    # 4) 内置智能体可运行
    try:
        from .agents import create_agent
        agent = create_agent("nomem")
        agent.new_episode(tempfile.mkdtemp())
        agent.session_start("s1")
        agent.send_user("你好")
        agent.session_end()
        agent.close()
        add("builtin-agents", True, "nomem 冒烟通过")
    except Exception as e:  # noqa: BLE001
        add("builtin-agents", False, "内置智能体冒烟失败: %s" % e)

    # 5) subproc 协议回环（echo-agent）
    try:
        from .agents import create_agent_from_config
        echo = os.path.join(PKG_ROOT, "examples", "echo-agent.py")
        cfg = {"name": "doctor-echo", "kind": "subproc",
               "cmd": [sys.executable, echo], "timeout": 30}
        agent = create_agent_from_config(cfg, source=echo)
        agent.new_episode(tempfile.mkdtemp())
        agent.session_start("s1")
        agent.send_user("我喜欢吃苹果。")
        agent.session_end()
        agent.session_start("s2")
        r = agent.send_user("我喜欢吃什么？")
        agent.session_end()
        agent.close()
        add("subproc-protocol", "苹果" in r, "stdio-JSONL 回环通过")
    except Exception as e:  # noqa: BLE001
        add("subproc-protocol", False, "回环失败: %s" % e)

    # 6) 临时目录可写（评测沙箱依赖）
    try:
        d = tempfile.mkdtemp(prefix="membench_doctor_")
        os.remove(os.path.join(d, ".keep")) if False else None
        probe = os.path.join(d, "w.txt")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        os.rmdir(d)
        add("tmp-writable", True, "沙箱临时目录可写")
    except OSError as e:
        add("tmp-writable", False, "临时目录不可写: %s" % e)

    # 7) UTF-8 输出（中文报告/理由依赖）
    enc = (sys.stdout.encoding or "").lower()
    add("utf8-stdout", "utf" in enc, "stdout 编码 %s" % (enc or "未知"),
        warn=not ("utf" in enc))

    # 8) CJK 字体提示（雷达图 SVG 在浏览器渲染时需要系统中文字体）
    if shutil.which("fc-list"):
        try:
            import subprocess
            out = subprocess.run(["fc-list", ":lang=zh"], capture_output=True,
                                 text=True, timeout=20)
            add("cjk-fonts", bool(out.stdout.strip()),
                "系统中文字体 %d 个（雷达图标签渲染）" % len(out.stdout.splitlines()),
                warn=not out.stdout.strip())
        except Exception as e:  # noqa: BLE001
            add("cjk-fonts", True, "fc-list 检查失败（不影响功能）: %s" % e, warn=True)
    else:
        add("cjk-fonts", True, "无 fc-list（非 Linux 或极简环境；浏览器渲染依赖系统中文字体）",
            warn=True)

    return checks


def main() -> int:
    checks = run_checks()
    print("membench doctor — openKylin 环境自检")
    fails = 0
    for c in checks:
        mark = {"PASS": "✓", "WARN": "!", "FAIL": "✗"}[c["status"]]
        print(" [%s] %-18s %s" % (mark, c["name"], c["detail"]))
        if c["status"] == "FAIL":
            fails += 1
    print("\n结论: %s（%d 项失败，%d 项告警）"
          % ("可复现" if fails == 0 else "存在阻塞项", fails,
             sum(1 for c in checks if c["status"] == "WARN")))
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
