# 方案说明：智能体长期记忆自动化评测（对应赛题交付 a）

## 1. 测试目标

量化比较智能体在 openKylin 环境下的长期记忆能力，覆盖**九维**：

| 维度 | 定义 | 数据集前缀 | 对标 |
|---|---|---|---|
| 长期保持 retention | 应保留的稳定信息（偏好/事实/路径/模板）是否被持久记住 | `ret-*` | 赛题基础 |
| 记忆调用 recall | 记住的信息能否在后续实际请求中正确取用 | `rec-*` | 赛题基础 |
| 动态更新 dynamic_update | 新信息出现后能否覆盖旧信息（回答与记忆库两个层面） | `upd-*` | 赛题基础 |
| 相近区分 distractor_discrimination | 同类相近信息（两只猫/两个地址/内外网 IP）能否按限定词分清 | `dis-*` | 赛题基础 |
| 边界识别 boundary_refusal | 敏感（密码/验证码/身份证）与临时信息是否被拒绝持久化与复述 | `bnd-*` | 赛题基础 |
| 任务复用 task_reuse | 历史教过的命令/模板/规范能否迁移到新任务与实际产物 | `reuse-*` | 赛题基础 |
| 时序推理 temporal_reasoning | 分散在多 session 的事件能否被正确排序/时间间隔推理 | `tem-*` | LongMemEval (ICLR'25) |
| 多 session 推理 multi_session_reasoning | 跨 session 分散的信息能否被组合/聚合用于回答 | `ms-*` | LongMemEval multi-session |
| 因果推理 causal_reasoning | 基于已记住的前置条件（"我不会 Python"）调整后续行动建议 | `cau-*` | AMA-Bench Type B (arXiv:2602.22769) |

## 2. 基本前提

1. **被测智能体可被驱动**：能按 session 顺序接收文本消息并返回回复
   （内置智能体、stdio 子进程、OpenAI 兼容 API 三种接入方式）。
2. **证据可采集**：对话轨迹必得；记忆库 dump 与文件系统产物为可选增强
   （智能体不支持时相应探针记为 `not_evaluable`，不影响其余探针）。
3. **评测可重复**：每次 run 使用独立沙箱工作目录；用例剧本与评分规则
   全部声明式存储；评分以确定性逻辑为主。

## 3. 数据生成与用例设计

### 3.1 两种数据生成方式

1. **手写精编用例**（`cases/`，24 个）：覆盖六个维度的典型失败模式，
   每例带 difficulty 与 tags，作为基准核心集；
2. **模板化批量生成**（`membench gen`）：每个模板是带 `{变量}` 的剧本骨架，
   生成器从值库（城市/名字/验证码/包名/IP 等）按种子随机抽取变量值，
   **expected 与注入的变量同源计算**，因此生成用例的标注成本为零且
   天然自洽。`--variants 3 --seed 42` 即可把核心集扩充到 30+ 个变体，
   且同种子输出逐字节一致（数据生成过程本身可复现）。

### 3.2 用例结构

- 用例 = 剧本（多 session 的 user 消息）+ 探针（在指定 session 后提问）+
  期望（结构化检查项）+ 可选的敏感标记与初始文件。
- 探针类型按"确定性从高到低"分五类：
  `choice`（选择题）> `slot`（要点包含/排除）> `free`（语义断言）>
  `fs`（文件产物）> `memory`（记忆库白盒）。
- `must_not_include` 命中时按维度归类裁决：泄露敏感串→`improper_persistence`；
  `task_reuse` 维度→`improper_reuse`；其余→`confusion`（旧值/干扰项）。
- 扩展方式：新增维度 = 新增 `dimension` 枚举与用例目录；新增检查字段 =
  `expected` 追加可选键，旧用例不受影响；新增生成模板 =
  在 `membench/generator.py` 注册一个 `(rng) -> 用例 dict` 函数。

## 4. 结果收集

每个 run × 每用例落盘一份证据包（`runs/runNN/<case_id>.json`）：

- `evidence.transcript`：完整对话轨迹（含探针轮）；
- `evidence.memory_dump`：智能体记忆库导出（白盒证据）；
- `evidence.memory_evolution`：**记忆演变轨迹**——每个 session 结束后的记忆库
  快照 diff（added/removed/n_items）。终态指标无法区分的三种病因在此可分：
  从未写入（写失败）、写了未删（边界/遗忘失败）、写了且覆盖（健康）；
  汇总层的 `memory_ops.writes/deletes` 进入 summary；
- `fact_lifecycle`（事实生命周期）：声明事实的有效 session 区间后，runner
  在每个 session 边界对记忆库做 **staleness 扫描**——已失效事实仍驻留即记
  improper_reuse 过程级发现（"该遗忘的没遗忘"，对标 Memora FAA 与 Zep
  边失效机制），汇总层 `staleness_violations` 进入 summary；
- `evidence.fs_added_or_modified`：评测期间新增/修改的文件（行动轨迹）；
- `rows[]`：逐探针 `{verdict, score, reason, hits, misses}`；
- `findings[]`：敏感信息落库/落盘扫描结果。

## 5. 自动评分流程

```
剧本回放 → 探针回答 → 逐探针裁决（确定性优先，LLM 兜底）
        → 敏感扫描（记忆库 + 文件 diff）
        → 用例得分 = Σ(score×weight)/Σ(weight)
        → 维度得分 / 五分类分布 / 跨 run 稳定性(std)
        → 总分 = 六维等权平均（可配置）
```

对抗"自动评分语义偏移"的三个手段：

1. **确定性优先**：choice/slot/fs/memory 全部字符串级/正则级判定，零 LLM 依赖；
2. **LLM judge 限权**：仅用于 free 探针语义断言；强制 JSON 输出、temperature=0、
   多数投票、裁决白名单校验、失败自动回退启发式；
3. **五分类裁决 + 理由**：每条结果必须引用命中的证据片段（`reason`/`hits`），
   使"记住了/误记了/不该记却记了"可被人工抽检验证。

## 6. 与 openKylin 生态的集成

- **接入面**：所有智能体通过统一的 stdio-JSONL 协议或 OpenAI 兼容端点接入，
  与 openKylin 智能体框架（KylinBot / kylin-agent / OpenClaw / HermesAgent）
  解耦——框架侧只需实现一个消息循环（参考 `examples/echo-agent.py`，
  约 50 行）或暴露一个 chat 端点；批量导入多款智能体用
  `membench run --agent 批量配置.json`（配置文件为配置数组）。
- **证据面**：除对话外，通过目录快照捕获智能体在 `$HOME/.config` 等
  桌面路径之外的文件落盘行为（行动轨迹证据），白盒检查记忆库导出，
  与 openKylin 智能体操作系统中"记忆记录、行动轨迹、运行产物"的
  证据形态一一对应。
- **分发面**：以 `.deb` 分发（`packaging/build_deb.sh`），依赖仅
  `python3 (>=3.8)` 与 `python3-yaml`（openKylin 预装），安装后
  即可在桌面终端运行 `membench`，可进入 openKylin 软件源。
- **验证面**：智能体评测在临时沙箱目录进行（`MEMBENCH_WORKDIR`），
  不污染系统；结果 JSON 含时间戳与运行参数，便于在 openKylin
  标准环境下做版本间对比回归。

## 6b. 样例结果

`examples/sample_results/` 内置一条命令（`membench demo`）产出的完整
样例：三内置智能体对比报告（HTML 雷达图 + Markdown + JSON）、
单智能体六维汇总、以及两个示例证据包（"搬家后仍答旧地址→confusion"、
"密码被持久化并复述→三重检查命中 improper_persistence"），
README 说明了每个字段怎么看。

## 7. 已验证的区分度（内置三个参考智能体）

| 智能体 | 记忆策略 | 保持 | 调用 | 更新 | 区分 | 边界 | 复用 | 总分 |
|---|---|---|---|---|---|---|---|---|
| smart | 规则记忆（覆盖更新/拒敏感/模板复用） | 100 | 100 | 100 | 100 | 100 | 100 | 100.0 |
| naive | 全量照记（回放最相似旧消息） | 86 | 50 | 0 | 0 | 0 | 50 | 30.9 |
| nomem | 无记忆 | 0 | 0 | 0 | 0 | 100 | 0 | 16.7 |

三种策略产出三个显著不同的六维雷达——证明基准具备区分度，
且每个维度的失分都能在证据包里找到对应的裁决理由。

## 8. 稳定性与可复现性

- 同一智能体重复 run，八维得分逐字节一致（内置智能体 std=0，见
  `tests/test_e2e.py::test_stability_deterministic`）；
- LLM judge 存在固有随机性时，通过 votes 多数投票与确定性探针占比
  控制波动范围；
- 结果目录含全部证据，事后可离线复算任意探针的裁决；
- **检索定位率**（对标 LongMemEval session-level recall）：智能体可选实现
  `retrieval_trace`（本次回答所用记忆及来源 session），聚合层计算
  "检索来源 ∩ 证据 session ≠ ∅"的比例——把"答对没"深化为"从对的
  session 取没"，能单独量化"取错来源"型失败。

## 9. 与开源主流长期记忆评测的对比与差异化

| 能力 | LongMemEval (ICLR'25, 500 题) | LoCoMo (arXiv'24) | **membench** |
|---|---|---|---|
| 信息抽取 | ✅ | ✅ | ✅（slot/choice） |
| 多 session 推理 | ✅ | ✅（多跳 QA） | ✅（ms-* 跨 session 组合 + 聚合） |
| **因果/前置条件推理** | ❌ | ❌ | ✅ causal_reasoning（前置条件 → 行动适配，对标 AMA-Bench Type B） |
| 时序推理 | ✅ temporal-reasoning | △ 弱 | ✅（tem-* 事件排序 + 时间间隔） |
| 知识更新 | ✅ knowledge-update | ❌ | ✅ dynamic_update（回答+记忆库双层） |
| 拒答 / 边界识别 | ✅ abstention | ❌ | ✅ boundary_refusal（回答+记忆库+落盘三重检查） |
| **任务复用 / 行动轨迹** | ❌ | ❌ | ✅ task_reuse（命令迁移 + fs 行动产物） |
| **相近区分** | ❌ | ❌ | ✅ distractor_discrimination（两只猫/双 IP/双地址） |
| **多证据源** | 仅 LLM judge | 仅 LLM judge | ✅ 对话 + 记忆库 dump + fs diff + sensitive 扫描 |
| **五分类裁决** | ❌ 仅 QA 对错 | ❌ | ✅ correct/miss/confusion/improper_persistence/improper_reuse |
| **智能体可插拔** | ❌（仅 LLM） | ❌（仅 LLM） | ✅ builtin / subproc JSONL / OpenAI 兼容 |
| **确定性可复现** | ❌（依赖 LLM judge） | ❌ | ✅ 4/5 探针零 LLM，跨 run std=0 |
| 数据规模 | 500 | 35 session | 27 手写 + 模板生成（可达数千） |

**membench 的差异化**（评审重点）：
1. **任务复用 + 行动轨迹证据**：开源工作均不覆盖；membench 通过 `fs`
   探针直接检查智能体真实生成的文件内容；
2. **边界识别三重防线**：对话 / 记忆库 / 文件系统三个层面同时检查；
3. **相近区分**：填补 LongMemEval/LoCoMo 都未单独成维度的能力；
4. **多证据源 + 确定性优先评分**：直接对应赛题"稳定性与可复现性 15%"
   与"自动评分能力 25%"；
5. **智能体可插拔**：不绑定 LLM，可直接评测 KylinBot/kylin-agent 等
   任意 openKylin 智能体框架；
6. **可扩展数据集**：`membench gen` 模板生成 + 26 个手写用例两路并行，
   新增维度无需改 schema（`dimension` 枚举扩展即可）。

**仍存在的差距**（与开源工作对比，评审方可能关注）：
- 数据规模小于 LongMemEval（500 vs 26），但生成器可补足；
- LongMemEval 提供公开 leaderboard；membench 不建榜（赛题也未要求）；
- 时序推理深度不及 LongMemEval（如"事件+持续时长"组合），可作
  下一轮增强点。

## 10. 内置参考智能体的画像（八维实测）

| 智能体 | 记忆策略 | 保持 | 调用 | 更新 | 区分 | 边界 | 复用 | 时序 | 多 session | 因果 | 总分 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| smart | 规则记忆 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | **100.0** |
| naive | 全量照记 | 86 | 50 | 0 | 0 | 0 | 50 | 0 | 33 | 75 | **32.7** |
| nomem | 无记忆 | 0 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | **11.1** |

三种策略的画像显著不同，且每项失分都能在证据包里看到对应的五分类
裁决与原因引用（如 naive 在时序上挂掉是因为它只回放最相似的旧消息，
不会按时间排序事件）。

## 11. 本轮对照的最新工作与吸收点（BEAM / AMA-Bench / Memora）

| 最新工作 | 其方法 | membench 吸收后的落地 |
|---|---|---|
| **BEAM**（arXiv:2510.27246，100 对话 2000 题，按对话长度分 bin 评测） | 观察"随记忆负担增长的能力退化曲线" | `membench report` 内置**记忆负担分档对比**（bin_report.json）：按用例 session 数分 1 / 2 / 3-4 / 5+ 档，逐档给出各智能体得分（HTML/Markdown/JSON 三格式） |
| **AMA-Bench**（arXiv:2602.22769，四类 agentic 记忆任务 + judge 人机一致率 92-96%） | ① causal 任务类型；② LLM judge 可信度自检 | ① 新增 **causal_reasoning** 维度（前置条件→行动适配）；② `LLMJudge.self_consistency_hook()` 输出 judge 自检信息（投票数/一致率下界/对照文献），报告可引用 |
| **Memora / FAMA**（arXiv:2604.20006，ACL'26 Findings，Forgetting-Aware Memory Accuracy） | 显式惩罚"复用已被覆盖/失效的记忆" | 评分 schema 新增 `superseded_values` 字段：被覆盖值在后续回答/记忆库中再次出现时，裁决从 `confusion` 升级为 **`improper_reuse`（FAMA 风格）**，理由文案明确标注——使"错误复用"这一五分类真正可用而非摆设 |

吸收后的额外亮点（对应赛题评分项）：
- **数据设计 25%**：9 维覆盖 + 分 bin 报告展示"覆盖随负担变化的刻画能力"；
- **自动评分 25%**：五分类全部具备独立语义（FAMA 让 improper_reuse 有真实触发路径）；
- **任务定义 15%**：与最新 agentic 记忆评测（AMA-Bench）能力分类对齐；
- **创新性 10%**：确定性优先 + FAMA 显式失效追踪是开源工作均未提供的组合。
