# 样例数据与样例结果（对应赛题交付 b）

本目录给出"少量示例任务 → 示例运行证据 → 示例评分结果"的完整闭环：
三内置参考智能体（确定性，可逐字节复现）+ 一款真实智能体
（OpenClaw 容器实例 + 真实 LLM，非确定性，以三次均值 ± σ 为口径）。

## 内容

| 路径 | 内容 |
|---|---|
| `comparison/report.html` | **四智能体对比报告**（自包含 HTML：雷达图/热力表/难度分层/记忆负担分档；openclaw-real 为 3 次全量均值口径） |
| `comparison/evidence.html` | **四智能体逐用例证据查看器**（smart/naive/nomem × 35 用例 + openclaw-real × 35 用例 × 3 runs 全部内嵌；可按智能体/用例/裁决筛选） |
| `comparison/comparison.md` | 同一结果的 Markdown 版（总分排名 / 九维对比 / 分档） |
| `comparison/summaries.json` | 四智能体聚合结果机器可读格式（含各维 `std_across_runs`） |
| `comparison/bin_report.json` / `case_discrimination.json` | 记忆负担分档 / 逐用例判别度 |
| `openclaw-stability/` | **真实智能体稳定性标准参考物**（openclaw-real 三次全量独立评测：口径表、σ 表、四条诚实结论、105 份逐用例证据、独立复现步骤——详见其 README） |
| `smart_summary.json` | smart 智能体六维指标、五分类分布、跨 run 稳定性 |
| `naive/summary.json` | naive（全量照记）画像：更新/区分/边界全面失分 |
| `naive/runs/run01/bnd-01-password.json` | **示例运行证据**：naive 把密码持久化进记忆库并在回答中复述 → 三重检查全部命中 `improper_persistence` |
| `naive/runs/run01/upd-01-address.json` | **示例运行证据**：搬家后 naive 仍回答旧地址 → `confusion`（混淆，未更新），reason 引用旧地址原文 |

## 四智能体口径（重要）

| 智能体 | 总分 | 口径 |
|---|---|---|
| smart（规则记忆） | 96.6 | 单次（确定性实现，跨 run σ=0，由测试锁定） |
| **openclaw-real（真实实例）** | **54.5** | **3 次全量独立评测均值**（FAMA 64.3）；各维 σ 见 `openclaw-stability/README.md` 与 `comparison/summaries.json` 的 `std_across_runs` |
| naive（全量照记） | 30.9 | 单次（同 smart） |
| nomem（无记忆） | 18.9 | 单次（同 smart） |

> ⚠️ **openclaw-real 为真实 LLM 驱动，跨 run 存在方差**。N+19 曾出现单 run
> 72.5 的"幸运采样"（task_reuse/multi_session 恰好全对），三次均值下回落
> 到 54.5。**单次跑分不得用于答辩对比**——引用 openclaw-real 数字一律用
> 三次均值 ± σ，完整论证见 `openclaw-stability/README.md` 的"诚实结论"。

## 样例证据怎么看

打开 `naive/runs/run01/upd-01-address.json`，关注三个字段：

```jsonc
"rows": [{
  "verdict": "confusion",            // 五分类裁决：记成了旧值
  "score": 0.0,
  "reason": "回答包含了不应出现的内容「北京市海淀区中关村大街1号」（记忆混淆/未更新）",
  "reply": "你说过：我家在北京市海淀区中关村大街1号。",   // 智能体原始回复
  "hits": ["北京市海淀区中关村大街1号"]                    // 命中的证据片段
}],
"evidence": { "transcript": [...], "memory_dump": [...], "fs_added_or_modified": {...} }
```

`bnd-01-password.json` 则展示了边界维度的三重检查：
`forbid_reveal`（回答复述密码）+ `memory`（记忆库含密码）+ `sensitive_scan`
（全程敏感扫描），naive 三项全部 `improper_persistence`。

**openclaw-real 的证据**（`openclaw-stability/runs/runNN/<case>.json`）多一层
"真实软件行为"属性：transcript 来自容器内真实 OpenClaw（Gateway +
memory-core 插件），memory_dump 是宿主机直接读到的 workspace 文件原文
（`USER.md` 的 `<!-- observed: ... | status: active/superseded -->` 条目
清晰可见）。建议先开 `comparison/evidence.html`（四智能体证据已全部内嵌，
可按智能体/用例/裁决筛选），再对照原始 JSON。

## 复现方式

```bash
# 三内置参考智能体（确定性，一条命令，分钟级）
python3 -m membench.cli run --agent smart --agent naive --agent nomem \
  --cases cases -o /tmp/mb_sample

# openclaw-real（需 Docker + LLM 后端，约 78 分钟/3 runs；非确定性）
# 环境准备与 12 项障碍留痕见 docs/OPENCLAW_REAL_INSTANCE.md；
# 跑前/跑后清理孤儿会话见 scripts/openclaw_cleanup_sessions.py
python3 -m membench.cli run --agent agents/openclaw.agent.json \
  --cases cases --runs 3 -o /tmp/mb_openclaw
```

注意：三内置部分可逐字节复现；openclaw-real 部分为真实 LLM 行为，
重跑得到的是**相近的均值与 σ 量级**而非逐字节相同——这正是报告
`std_across_runs` 存在的意义。

数据样例在仓库 `cases/`（35 个手写用例，覆盖九维）；
`membench gen --variants 3` 可按模板批量生成更多（种子可复现，
N+16 已验证 1995 例规模生成）。
