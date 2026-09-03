# 相关工作与差异化（答辩一页）

> 依据：RESEARCH.md 中 19 项精读记录（截至轮次 N+9）。每条结论均可在
> 该文件找到原文级依据；标注"摘要级"的为 abstract/文档级核实。

## 一、评测基准谱系（谁在测、怎么测）

| 工作 | 能力分类 | 评分方式 | 关键局限 |
|---|---|---|---|
| LoCoMo (2024.02) | 5 类 QA（含 **adversarial** 24.9%）+ 事件摘要 | F1 + FactScore 式原子事实 | 只评 LLM；无过程证据 |
| LongMemEval (ICLR'25) | 5 能力；`answer_session_ids` 证据定位 | LLM judge + 检索定位率 | judge 随机性靠 10 次均值兜底 |
| BEAM (2025.10) | **10 能力**；nugget 0/0.5/1；长度分 bin | nugget 均值；Event Ordering 用 Kendall τ-b | 生成依赖 GPT-4.1，人工双标注成本高 |
| Memora (ACL'26) | 记住/推理/推荐；**FAMA = max(0, MPA − λ(1−FAA))** | 3 judge 投票，人机一致 88.3% | 合成对话；仅偏好/活动/目标记忆 |
| AMA-Bench (2026.02) | Recall/Causal/StateUpdate/Abstraction | judge 人机一致 92.7%；QA-轨迹相关 0.96 | 合成轨迹为主 |
| MemoryAgentBench (2507) | 检索/测试时学习/长程理解/**选择性遗忘** | 多轮增量格式 | — |
| MemGym (2605) | 执行中动态记忆形成 | **memory gain（配对运行差值）** | — |

**共同缺口**（上表逐列核对）：全部只评"答案对不对"；全部依赖 LLM judge；
全部不评"智能体"只评"LLM"；无文件系统/行动产物证据。

## 二、记忆系统谱系（被评的对象长什么样）

- **MemGPT**：OS 式分级（working context 仅可函数写入 + recall/archival）；
  产品化 Letta 已演进为 **git 支撑的 MemFS + Dreaming 后台整理 + /doctor 审计**。
- **Mem0**：增量比对操作分类学 **ADD/UPDATE/DELETE/NOOP**（逐字核实）；
  LOCOMO 上比全文基线时延 -91%。
- **A-MEM**：Zettelkasten 笔记演化（strengthen/update_neighbor）——
  多跳 QA 比 LoCoMo 基线高 ≥2 倍。
- **Zep/Graphiti**：时序知识图谱，事实**失效不删除**、保留演化史。
- **OpenClaw**（赛题点名生态智能体，官方文档核实）：记忆 = 工作区
  **纯 Markdown 文件**（MEMORY.md / memory/日期.md / DREAMS.md）+
  混合检索 + **Dreaming 后台整理**。
- **行业收敛**：文件化存储 + 后台整理 + 混合检索——三条主线全部落在
  membench 的证据通道上（文件快照、记忆演变轨迹、检索定位率）。

## 三、membench 的六项差异化（每项都有出处）

1. **过程级证据**（唯一）：记忆演变轨迹区分"写失败/该删未删/健康覆盖"，
   终态 QA 指标对此不可分（MemGym 的 condensation 记录最接近，但不做评测）；
2. **五分类裁决 + criteria 级 FAMA**（唯一）：correct/miss/confusion/
   improper_persistence/improper_reuse；FAMA = max(0, MPA − λ(1−FAA))
   按判据角色分解——所有基准的 judge 只判对错；
3. **全轨迹 staleness 扫描**（唯一）：事实生命周期（Zep 式失效不删除的
   session 级版）+ 每 session 边界扫描，"该遗忘的没遗忘"被过程级捕获
   （呼应 MemoryAgentBench 的 selective forgetting 与综述的 learned
   forgetting 开放挑战）；
4. **确定性优先**：4/5 探针类型零 LLM，跨 run std=0（对照 IFEval 的
   可验证指令思想）；LLM judge 可选且有自检接口；
5. **智能体可插拔**：builtin / stdio-JSONL / OpenAI 兼容三种接入——
   对 OpenClaw 这类文件化记忆智能体，fs 证据通道**天然可直读其记忆**
   （无需侵入），对接成本约 50 行协议 shim；
6. **openKylin 落地面**：.deb 分发、`membench doctor` 环境自检 8 项
   （python/yaml/用例/智能体/协议/沙箱/UTF-8/CJK 字体）、零第三方依赖
   （python3 + python3-yaml 均为系统预装）。

## 四、主动承认的差距（答辩防身）

- 数据规模：27 手写 + 模板生成 << BEAM 2000 题（人工校验深度不及）；
- 无 leaderboard（赛题未要求）；
- 时序推理深度不及 LongMemEval（无"事件+持续时长"组合题）；
- 检索定位率目前覆盖内置/实现该协议的智能体，外部智能体需实现协议 shim；
- 我们的 judge 在 free 探针上仍可用 LLM（启发式为默认），与全 LLM judge
  的基准相比，语义覆盖面窄但可复现性换来了稳定性——这是明确的设计取舍。

## 五、一句话定位

> 开源基准在"给 LLM 出长上下文考卷"，membench 在"给 openKylin 上的
> 智能体做记忆体检"——不只看答对没，还看记忆写没写、删没删、从哪取的、
> 该忘的忘没忘。
