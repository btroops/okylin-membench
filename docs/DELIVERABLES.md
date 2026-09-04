# 赛题交付自查矩阵（终版）

> 逐条对照《openKylin 赛题》交付要求 a–e 与评审六维度。每项给出证据物与
> 验证方式。状态：✅ 完成并验证 / 🔶 框架就绪、需真实资源 / ⏳ 未做（含理由）。

## 一、交付要求对照

| 交付 | 要求 | 证据物 | 验证方式 | 状态 |
|---|---|---|---|---|
| a 方案说明 | 测试目标/前提/数据生成/用例设计/结果收集/自动评分全流程 | `docs/DESIGN.md`（11 节）、`docs/SCHEMA.md`、`docs/RESEARCH.md`（4 系列 25 项）、`docs/DEVLOG.md`（11 轮）、`docs/RELATED_WORK.md`（相关工作一页） | 文档间数字与代码输出一致性经三轮复查 | ✅ |
| a 数据集设计 | 可扩展结构，覆盖记忆样本与验证项 | `membench/schema.py`（9 维度、5 探针类型、fact_lifecycle、memory_max_count、superseded_values、evidence_sessions）；`cases/` 31 手写用例；`membench gen` 21 模板 | `membench validate` 静态校验；生成器种子可复现（diff 为空）；测试锁定 | ✅ |
| a 自动评测方案 | 少人工介入、按证据评分、可解释 | `membench/scoring.py` + `judge.py`：确定性优先（choice/slot/fs/memory 零 LLM）、五分类裁决、criteria 级 FAMA、LLM judge 自检 | `tests/test_scoring.py` 等；同一输入跨 run std=0（测试锁定） | ✅ |
| b 样例数据与结果 | 示例任务/运行证据/评分结果 | `cases/` 31 例；`examples/sample_results/`（对比报告 HTML/MD/JSON、bin 报告、证据查看器、2 个证据包 + README 解读） | 样例与当前代码输出逐字节一致（自查脚本） | ✅ |
| c 可复现材料 | 脚本/配置/README/代码在 openKylin 直接运行 | 全仓库；零第三方依赖（python3≥3.8 + python3-yaml）；`membench doctor` 8 项环境自检；tests/ 90 个测试随 deb 分发 | 干净副本 tar 解开从零跑全绿；.deb 解包后包内测试全绿 | 🔶 本机（Ubuntu22.04/py3.8）验证；openKylin 真机各跑一次由参赛者完成 |
| d 工具化封装 | CLI 一键运行、批量对比、.deb | `membench/cli.py` 7 子命令（doctor/list/validate/gen/run/report/demo）；`--agent` 支持批量配置数组；`packaging/build_deb.sh` | deb 构建+解包实测（CLI/批量配置/包内测试）；多智能体批量对比实测 | ✅ |
| e 演示视频 | openKylin 桌面、≥2 款智能体、3~5 分钟、雷达图 | `docs/DEMO_SCRIPT.md`（5 分镜+口播稿+防翻车清单）、`scripts/rehearse.sh`（彩排脚本）、`agents/*.json` 模板 | 框架侧全链路彩排通过；录制需真实桌面 | 🔶 需参赛者在 openKylin 真机录制（约 15 分钟） |

## 二、评审六维度对照

| 维度 | 权重 | membench 对应能力 | 实测/证据 |
|---|---|---|---|
| 任务定义与通用性 | 15% | 三种接入面（builtin/subproc JSONL/OpenAI 兼容）；批量导入；多证据源（对话+记忆库+文件）；AIOS 式"内核旁路采集"架构论证；OpenClaw 记忆文件可直读 | `agents/` 配置样例；`examples/echo-agent.py` 协议参考实现实测；RESEARCH 系列四 |
| 数据设计质量 | 25% | 9 维度 × 5 探针类型 × 31 手写 + 21 模板（种子可复现）；干扰项难度旋钮（最小对变体）；fact_lifecycle 生命周期 | `membench gen` 一致性测试；难度旋钮测试（字符差收窄且无子串陷阱） |
| 自动评分能力 | 25% | 五分类裁决（correct/miss/confusion/improper_persistence/improper_reuse）+ 理由引用证据片段；criteria 级 FAMA = max(0, MPA−λ(1−FAA))；确定性优先 + LLM judge 限权（JSON 强制/多数投票/失败回退） | `tests/test_scoring.py`、`test_fama_bin_judge.py`；实测理由文案含原文引用 |
| 稳定性与可复现性 | 15% | 同输入跨 run 逐字节一致；`std_across_runs` 报告；批量运行与结果追踪（每 run 独立目录 + 时间戳）；doctor 自检 | `test_e2e::test_stability_deterministic`；两次 demo diff 为空实测 |
| 指标完整性 | 10% | 九维得分 + 总分 + **FAMA** + 检索定位率 + 记忆演变轨迹（writes/deletes）+ staleness_violations + 五分类分布 + 难度分层 + 难度×维度热力表 + 记忆负担分档 | `summary.json` 字段与 HTML/MD 报告实测 |
| 创新性与工程落地 | 10% | 过程级证据（演变轨迹/staleness/定位率——开源基准均无）；零依赖 .deb；doctor；21 模板生成器 | 与 LoCoMo/LongMemEval/BEAM/Memora/AMA-Bench/MemGym 逐列对照（RELATED_WORK.md） |

## 三、实测区分度（内置参考智能体，9 维）

```
smart(规则记忆) 100.0 | 八维全 100
naive(全量照记)  32.7 | 保持86 调用50 更新0 区分0 边界7 复用50 时序0 多session33 因果75
nomem(无记忆)    11.1 | 仅边界 100（什么都不存，天然不越界）
```

每项失分在证据包中有五分类裁决 + 引用原文的理由；过程级指标
（writes/deletes、staleness、定位率）与终态裁决互相印证。

## 四、参赛者剩余待办（3 项）

1. **openKylin 真机验证**：`sudo dpkg -i dist/membench_0.1.0-1_all.deb && membench doctor && membench demo`（约 10 分钟，留档输出）；
2. **接两款真实智能体**：本地 LLM 改 `agents/openai-compat.example.json` 的 base_url/model；OpenClaw 类文件化记忆智能体写 50 行协议 shim；`membench run --agent 批量.json` 对比；
3. **录制演示视频**：按 `docs/DEMO_SCRIPT.md` 五分镜 + `scripts/rehearse.sh` 彩排后正式录（约 15 分钟）。
