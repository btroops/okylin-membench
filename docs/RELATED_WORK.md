# 相关工作与差异化（答辩版 · Evidence-Driven 叙事）

> 完整精读依据：RESEARCH.md（31 项，4 系列）。
> 叙事主文档：EVIDENCE_CHAIN.md（范式主张 + 三层架构 + 实验数据）。
> 本页是"评委三问"的直接答案。

## 评委问题 1：你和 LoCoMo / LongMemEval / MemoryAgentBench 有什么区别？

**一句话**：它们评"最终回答"，我们评"证据链"。

|  | 终态 QA 范式（现有工作） | 证据链范式（本方案） |
|---|---|---|
| 评测对象 | 最终回答 vs 标准答案 | 对话轨迹 + 记忆状态演变 + 检索来源 + 文件产物 |
| 失败归因 | 对/错（最多 FAMA 式惩罚） | 五分类：没记住 / 记住没用 / 记错 / 该忘未忘 / 不该记却记 |
| 不可见失败 | 该忘未忘、不该记却记（答题可满分） | 过程级捕获（staleness / sensitive 扫描） |
| 评分 | LLM judge（一致率 88-93%） | 确定性优先（4/5 探针零 LLM，跨 run 方差 0） |
| 被评对象 | LLM | 智能体（内置 / stdio 协议 / OpenAI 兼容 / 文件化记忆生态） |

**杀手级例子**：一个把用户密码写进长期记忆的智能体，在终态 QA 范式下
可以满分；在本方案的 sensitive_scan + memory 探针下当场违规。
（实测：naive 智能体 8 次敏感持久化事件，证据包可逐条查看。）

## 评委问题 2：你的自动评分为什么可信？

**用数据回答，不用形容词**（实验数据见 `tests/labels/`）：

1. **盲评一致性实验**：185 条探针裁决，独立盲评器（另行实现、不经
   scoring.py）raw agreement **83.8%**（κ=0.75，六分类）；30 条分歧
   逐条仲裁：21 条为盲评器无记忆库/文件访问权（权限制约），9 条为
   类间语义近似，**1 条真实改进点当场转化为引擎修复**（any_include
   回退定类，回归测试锁定）；
2. **零方差**：同一输入跨 run 逐字节一致（test_stability_deterministic）；
   对照：AMA-Bench 的 LLM judge 人机一致率 92.7%、Memora 三 judge
   投票 88.3%——我们的确定性路径免 judge、免投票、免温度；
3. **每条裁决可人工复核**：verdict + reason 引用命中的证据片段，
   `evidence.html` 逐条点开即可验证（对/错一目了然，不依赖黑盒）；
4. **诚实口径**：LLM judge 在 free 探针上仍可选（带自检接口与失败回退），
   我们主张的不是"不用 LLM"而是"能用确定性就不用"。

## 评委问题 3：为什么这不是把几个 benchmark 拼起来？

**因为核心对象不同，不是题型相加。**

- 拼题型 = 继续在 Question→Answer→Judge 路径上加任务类型（这正是
  LoCoMo→LongMemEval→BEAM 的演进方式，我们没有重复它）；
- 我们新增的评测对象是**记忆系统的内部行为**：逐 session 的记忆库
  快照 diff（写没写、删没删）、检索来源（从哪个 session 取）、文件
  产物（写了什么）——这些在任何上述 benchmark 里都不存在；
- 组合的证据见六项可声称原创（演变轨迹/文件证据/五分类裁决/记忆
  卫生/staleness 扫描/确定性立场），以及三项明确标注"继承并工程化"
  的能力（跨 session QA/拒答/时序多跳）——我们公开说清楚了哪些是
  站在 LongMemEval 等工作的肩膀上。

## 与六项工作的逐项对比表

| 能力 | LoCoMo | LongMemEval | BEAM | Memora | AMA-Bench | MemGym | **membench** | 原创性 |
|---|---|---|---|---|---|---|---|---|
| 跨 session QA | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 继承 |
| 拒答 | ✅ | ✅ | ✅ | △ | ❌ | ❌ | ✅ | 继承+工程化 |
| 选择性遗忘 | ❌ | △ | ✅ | ✅FAMA | ✅ | ❌ | ✅ | 语义继承，**扫描机制原创** |
| 时序/多跳/因果 | △ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 继承 |
| 记忆状态过程评测 | ❌ | ❌ | ❌ | ❌ | ❌ | △记录非评测 | ✅ | **原创** |
| 检索证据定位 | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | 继承思想，扩展到智能体协议 |
| 文件/行动产物证据 | ❌ | ❌ | ❌ | ❌ | ❌ | △ | ✅ | **原创** |
| 五分类失败裁决 | ❌ | ❌ | ❌ | △ | ❌ | ❌ | ✅ | **原创** |
| 记忆卫生（去重/噪声） | ❌ | ❌ | ❌ | ❌ | △ | ❌ | ✅ | **原创** |
| 确定性优先评分 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | **立场原创**（IFEval 归属） |
| OS 集成 .deb/doctor | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | **工程原创**（AIOS/OpenClaw 归属） |

## 四层引用骨架（PPT 引用页）

1. **Benchmark foundation**：LoCoMo (2024.02) → LongMemEval (ICLR'25) →
   MemoryAgentBench (2025.07)——"长期记忆评测必须跨 session、含拒答
   与选择性遗忘"；
2. **Memory mechanism**：MemGPT (2023.10) → Mem0 (2025.04) → A-MEM
   (NeurIPS'25) → Zep/Graphiti (2025.01)——"真实记忆系统是
   add/update/delete/evolve，不是 KV cache"（演变轨迹 added/removed
   正对应 Mem0 的 ADD/DELETE，逐字核实）；
3. **Agentic benchmark**：BEAM (2025.10) → AMA-Bench (2026.02) →
   MemGym (2026.05)——"评测正从 QA 走向轨迹/状态更新/因果行动/
   记忆隔离打分"（MemGym 的 memory-isolated scores 与我们同向）；
4. **OS / system integration**：AIOS (COLM'25) + Letta MemFS +
   OpenClaw 官方文档——"为什么适配 openKylin：生态智能体的记忆就是
   磁盘文件，fs 证据通道无需侵入"。

## 一句话定位（收尾用）

> 开源基准在给 LLM 出长上下文考卷；我们在给 openKylin 上的智能体做
> **记忆体检**——不只看答对没，还看写没写、删没删、从哪取的、
> 该忘的忘没忘、不该记的记没记。
