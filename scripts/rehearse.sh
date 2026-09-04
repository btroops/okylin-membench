#!/usr/bin/env bash
# openKylin 演示彩排脚本：按 docs/DEMO_SCRIPT.md 的镜头顺序执行并自检。
# 用法: bash scripts/rehearse.sh [输出目录，默认 rehearse_out]
set -euo pipefail
OUT="${1:-rehearse_out}"

echo "=== [1/6] 环境自检（doctor） ==="
python3 -m membench.cli doctor

echo "=== [2/6] 数据集校验 ==="
python3 -m membench.cli validate

echo "=== [3/6] 生成器彩排（种子可复现） ==="
python3 -m membench.cli gen -o "$OUT/gen" --variants 1 --seed 42
python3 -m membench.cli gen -o "$OUT/gen2" --variants 1 --seed 42
diff -r "$OUT/gen" "$OUT/gen2" && echo "生成器逐字节一致"

echo "=== [4/6] 三内置智能体评测（镜头 3-4 的替代彩排） ==="
python3 -m membench.cli run --agent nomem --agent naive --agent smart \
  --runs 2 -o "$OUT/results" --quiet

echo "=== [5/6] 对比报告（含雷达图/热力表/FAMA） ==="
python3 -m membench.cli report "$OUT/results/nomem" "$OUT/results/naive" "$OUT/results/smart"

echo "=== [6/6] 产物清单 ==="
ls -la "$OUT/results/comparison/"
echo "彩排完成。录制时按 docs/DEMO_SCRIPT.md 的分镜替换真实智能体配置。"
