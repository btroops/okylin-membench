# 评分可信度实验产物（185 探针）

本目录所有文件均由 N+15 轮次生成器与盲评器一次性跑出，**不依赖 LLM**：

| 文件 | 用途 |
|---|---|
| `engine_verdicts.json` | 185 条探针 × 三内置智能体的引擎裁决 + reply + reason |
| `blind_payload.json` | 同上但剥掉 reason/engine_verdict（盲评载荷） |
| `human_labels.json` | 按规则文本独立实现的盲评器对每条给的裁决（第二标注者模拟） |
| `blind_disagreements.json` | 30 条不一致清单（按盲评器与引擎） |
| `arbitration.json` | 仲裁笔记（21 权限制约 + 9 类间近似 + 1 真实改进点） |
| `agreement_report.json` | 总结指标：raw agreement 83.8% / κ=0.75（六分类）/ 跨运行 σ=0 |

## 盲评器 / 算分脚本

- `scripts/labels/blind_relabel.py`：独立实现的"第二标注者"，与 scoring.py 无共享代码
- `scripts/labels/compute_agreement.py`：从 engine_verdicts + human_labels 算 agreement/κ/每类 P/R/F1

## 复现

```bash
python3 scripts/labels/blind_relabel.py
python3 scripts/labels/compute_agreement.py
# 期望输出: n=185, agreement=0.8378, kappa=0.7485
```
