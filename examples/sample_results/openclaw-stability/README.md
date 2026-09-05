# openclaw-real 三次全量稳定性参考物（标准口径）

真实智能体（OpenClaw 容器实例 + 真实 LLM 后端）在 35 个手写用例上
`--runs 3` 全量评测的**完整落盘证据**。这是答辩引用 openclaw 分数时的
唯一标准口径——单次跑分不得用于对比（原因见下"诚实结论"）。

## 来源与口径

| 项 | 值 |
|---|---|
| 评测日期 | 2026-09-05（研发轮次 N+20） |
| 被测智能体 | `openclaw-real`（`agents/openclaw.agent.json`，OpenClaw 官方镜像，Gateway:18789，Anthropic 兼容端点 DeepSeek） |
| 用例 | `cases/` 全量 35 个手写用例（九维） |
| 重复次数 | 3（`--runs 3`，同配置独立重跑） |
| 总耗时 | 4664 秒 ≈ 78 分钟 |
| 跑前/跑后清理 | `scripts/openclaw_cleanup_sessions.py` 两轮（148 / 308 个 mb-* 孤儿会话），均回到基线 20 会话 |
| 敏感扫描 | `total_findings_sensitive = 0` |

## 核心数字（三次均值 ± 跨 run σ，摘自 summary.json）

| 维度 | 均值 | σ | 探针数 |
|---|---|---|---|
| 长期保持 retention | 94.9 | 7.3 | 39 |
| 记忆调用 recall | 75.0 | 0.0 | 12 |
| 动态更新 dynamic_update | 61.5 | 6.3 | 39 |
| 相近区分 distractor_discrimination | 25.0 | **20.4** | 24 |
| 边界识别 boundary_refusal | 83.9 | 5.5 | 40 |
| 任务复用 task_reuse | 33.3 | 11.8 | 12 |
| 时序推理 temporal_reasoning | 50.0 | **40.8** | 6 |
| 多 session 推理 multi_session_reasoning | 66.7 | 0.0 | 3 |
| 因果推理 causal_reasoning | 0.0 | 0.0 | 6 |

**总分 54.5，FAMA 64.3**。单 run 用例级均分 61.4 / 63.2 / 67.1
（口径：每用例 `score` 字段均值 ×100；run02 为 34/35 —— bnd-01-password
因 Docker daemon 与网关偶发连接错误未产生得分，非模型能力问题）。

## 诚实结论（答辩时必须主动说明）

1. **单次跑分会被幸运/不幸采样放大**。N+19 轮的单 run 画像（总分 72.5，
   task_reuse=100、multi_session=100）在三次均值下回落到总分 54.5、
   reuse 33.3 / multi_session 66.7。具体到用例：
   `runs/run02/upd-04-memory-store.json` 得 0.00，同用例 run01/run03 均
   1.00——σ 列就是为抵御"跑一次挑好结果"质疑而设。
2. **causal_reasoning = 0 是三次一致失败**（3 runs × 6 探针全 miss），
   不是网络抖动；openclaw 对"前置条件→行动适配"类探针稳定失分。
3. **σ 与探针样本量强相关**：temporal σ=40.8 但仅 6 探针、
   multi_session σ=0.0 也仅 3 探针——探针少的维度方差估计本身不可信。
   压低 σ 的正路是扩大数据集（N+16 已验证 1995 例生成能力），不是调 judge。
4. **检索定位率 0.0 是环境局限而非被测能力**：memory-core 语义检索依赖
   OpenAI embedding key，本环境无该 key，`retrieval_trace` 恒空
   （详见 `docs/OPENCLAW_REAL_INSTANCE.md` 第五节）。

## 文件导览

| 路径 | 内容 |
|---|---|
| `summary.json` | 三 run 聚合：九维 `score`/`std_across_runs`/裁决分布、总分、FAMA、逐用例 `per_case`、难度分层、记忆操作计数 |
| `runs/run01..03/*.json` | 105 个逐用例证据文件：每探针 `verdict`/`score`/`reason`/`reply`/`hits` + `evidence`（transcript、memory_dump、fs diff）。σ 可由此逐条复算 |
| `comparison/comparison.md` | 单智能体报告的 Markdown 版（六维/分档/难度分层） |
| `comparison/report.html` | 自包含 HTML 报告（双击可看） |
| `comparison/summaries.json` | 聚合结果机器可读格式 |
| `comparison/evidence.html` | 逐用例证据查看器 |
| `comparison/bin_report.json` | 记忆负担分档 |
| `comparison/case_discrimination.json` | 逐用例判别度 |

## 复现方式

环境前置（LLM key、容器、docker 组权限）见 `docs/OPENCLAW_REAL_INSTANCE.md`；
跑前建议 `python3 -m membench.cli doctor` 自检。核心命令：

```bash
docker compose -f docker/openclaw/docker-compose.yml up -d openclaw-gateway
python3 -m membench.cli run --agent agents/openclaw.agent.json \
  --cases cases --runs 3 -o results/openclaw-stability
python3 -m membench.cli report results/openclaw-stability
# 跑完清理评测产生的 mb-* 孤儿会话（幂等，脚本须在容器内执行）：
docker compose -f docker/openclaw/docker-compose.yml stop openclaw-gateway
docker compose run --rm --no-deps openclaw-gateway \
  python3 /home/node/.openclaw/cleanup_sessions.py
```

注意：真实 LLM 后端逐次采样有随机性，复现得到的应是**相近的均值与 σ
量级**，而非逐字节相同；内置参考智能体（nomem/naive/smart）才是确定性的
（见本目录上层 README 的稳定性自测）。
