# 论文谱系精读笔记（RESEARCH）

> 维护方式：每个论文系列一节；每篇按固定模板记录（问题 / 构造 / 指标 / 发现 / 局限 / membench 吸收）。
> 只写**实际读到并验证过**的内容；摘要级信息与全文级信息分开标注。每轮对照至少 3 篇。

## 系列一：长期记忆 Benchmark 谱系

```
LoCoMo (2024.02)          多轮长对话记忆，QA/事件摘要/多模态
  └─ LongMemEval (2024.10, ICLR'25)   能力分类 + 检索定位指标 + 拒答
      └─ BEAM (2025.10)             规模化生成 + nugget 评分 + 长度分 bin
          └─ AMA-Bench (2026.02)    agentic 轨迹记忆 + judge 可信度自检
Memora (2026.04, ACL'26 Findings)     个性化代理 + 失效记忆惩罚（FAMA）
```

### LongMemEval（arXiv:2410.10813，ICLR 2025）— 全文级（README + 摘要）

- **问题**：商用助手与长上下文 LLM 在持续交互中记忆衰减 ~30%，且缺系统能力分类。
- **构造**（值得学）：needle-in-haystack 式**属性受控编译**——用户属性/背景池 +
  问题与证据 session 标注 + ShareGPT/UltraChat 填充 session + 时间戳分配，
  脚本可复现编译（S=80 session/115k tokens，M=500 session）。
- **数据字段**（直接借鉴）：`question_type`、`question_date`、
  `haystack_sessions`、`answer_session_ids`（session 级证据定位）、
  turn 级 `has_answer` 标签。
- **指标**：QA 正确性（LLM judge）+ **session 级/turn 级记忆检索定位率**
  （不只是答对，还要"从对的 session 取"）。
- **拒答设计**：`_abs` 后缀实例指"不存在的事件"，无标准答案位置；
  检索评测时剔除这 30 例。
- **membench 已吸收**：✅ 拒答用例（any_include 措辞匹配）；
  ✅ `evidence_sessions` / `session.date` 元数据字段；
  ✅ 时序/更新/多 session 维度。
- **membench 待吸收**：检索定位率（需智能体暴露检索过程；subproc 协议可扩展）。

### BEAM（arXiv:2510.27246，2025.10）— 全文级（HTML 正文）

- **问题**：百万 token 级对话中 LLM 记忆退化；需要可规模化的对话生成。
- **构造**（值得学）：四段式全自动流水线——①计划生成（领域/人设/时间线/
  MBTI 用户画像）；②LLaMA-3.3-70B 生成用户发言；③角色扮演生成助手回复
  （带问题检测/追问检测模块）；④GPT-4.1-mini 按能力生成探针问题（带答案
  与源 turn 标识）。**人工校验**：两名标注者剔除无效/不一致探针，每对话
  每能力保留 2 题，共 100 对话 × 10 能力 × 2 = 2000 题。
- **指标**（直接借鉴）：**nugget 评分**——judge 对每个 nugget 打
  0 / 0.5 / 1，能力得分 = nugget 均值；**Event Ordering 用 Kendall τ-b**
  （同时捕捉召回与顺序保真）；按 128K/500K/1M/10M 分 bin 报告。
- **能力清单**（10 种）：Abstention、Contradiction Resolution、Event
  Ordering、Information Extraction、Instruction Following、Knowledge
  Update、Multi-hop Reasoning、Preference Following、Summarization、
  Temporal Reasoning。
- **membench 已吸收**：✅ 分 bin 报告（按 session 数）；✅ nugget 式部分得分
  （must_include 命中比例）。
- **membench 待吸收**：Contradiction Resolution（远距离自相矛盾检测）可并入
  相近区分维度；Instruction Following（记住"以后都这样做"的指令）可并入
  任务复用。

### Memora / From Recall to Forgetting（arXiv:2604.20006，ACL'26 Findings）— 全文级（HTML 正文）

- **问题**：现有评测是"浅层跨 session 检索"；个性化代理会**复用已失效的
  记忆**（如推荐用户已厌倦的导演的电影）。
- **构造**（值得学）：10 个职业人设种子（偏好/活动/目标三类记忆 +
  操作与时序约束）→ session 模拟（带 add/update/delete 记忆状态操作，
  交错记忆无关 session）→ 多智能体对话生成（Intent/Flow/Prompt Manager，
  开场-探索-记忆-收尾四阶段）→ **3 个 LLM 一致通过的记忆接地校验 +
  每人设 5% 人工抽检**。
- **指标**（直接借鉴）：**FAMA = max(0, MPA − λ·(1−FAA))**，MPA=记忆在场
  准确率，FAA=遗忘缺失准确率（该失效的没失效），λ=FAA 判据占比；
  三个 LLM judge 多数投票，人机一致率 88.3%。
- **错误类型学**（75 例人工归因）：recommending 错误 64% 源于"过期记忆
  未遗忘"；remembering 72% 源于部分检索导致结构化输出残缺；reasoning
  100% 因检索不全无法整合。
- **membench 已吸收**：✅ `superseded_values` → improper_reuse（FAMA 风格
  裁决）；✅ 拒答。
- **membench 待吸收**：criteria 级 FAMA 公式（我们是探针级二元+部分分，
  可在未来 judge 里支持"记忆在场判据 + 遗忘缺失判据"双清单）。

### AMA-Bench（arXiv:2602.22769，2026.02）— 全文级（HTML 正文 §任务与评分）

- **四类任务**：A Recall（时序/顺序信息）、B Causal（动作前置条件与状态
  依赖）、C State Updating（显式观察+隐藏状态更新）、D State Abstraction
  （滤冗余取要点）。
- **指标**：Accuracy + F1；Qwen3-32B LLM judge 二元判分，人机一致率
  92.67%/精度 96.45%；跨 judge 鲁棒性（vs GPT-5.4 92.8% 等）；QA 分数与
  端到端任务成功率 Pearson 相关 0.96-0.98；轨迹长度分 5 bin。
- **membench 已吸收**：✅ causal_reasoning 维度；✅ judge 自检接口；
  ✅ 长度分档报告。
- **局限**（他们自认）：轨迹合成+规则 QA，真人轨迹占比小。

## 系列二：记忆系统谱系（用于设计参考智能体与 judge rubric）

> 状态：未开读。候选顺序：MemGPT (2310.08560) → Mem0 (2504.xxxx) →
> A-Mem → MemGym。待下一轮。

## 给 membench 的差异化结论（持续更新）

1. 五分类裁决（尤其 improper_persistence / improper_reuse）在上述所有
   benchmark 中都不存在——它们的 judge 只判"答案对不对"；
2. 多证据源（对话+记忆库+文件系统）无人覆盖——因为它们不评"智能体"只评"LLM"；
3. 确定性优先评分无人做——所有指标都依赖 LLM judge，可复现性靠一致率统计兜底；
4. 我们的数据规模与人工校验深度是真实短板（BEAM 人工双标注校验 2000 题；
   我们 29 例手写无第二标注者）——答辩时应主动承认并强调生成器+确定性
   探针部分弥补。

## 系列三：递归阅读（从已读论文的引文往回追）

> 方法：每读一篇，把其引文里与"记忆评测/记忆系统"直接相关的参考文献追进去读。
> 本轮递归 4 篇。

### RULER（arXiv:2404.06654，COLM 2024）— LongMemEval/BEAM 的合成构造源头 — 全文级（摘要+仓库）

- **13 任务 4 类**：检索（niah 变体）/ 多跳（VT）/ 聚合（CWE、FWE）/ QA。
- **Variable Tracking（VT）**：多条"变量名→变量名"绑定链散布在上下文中，
  模型需逐跳回溯到末端值；`num_chains` × `num_hops` 两个难度旋钮。
- **难度旋钮思想**（值得学）：CWE 用常见词/干扰词频率差控制难度；FWE 用
  Zipf α 控制分布平坦度——**难度是可参数化的，而非靠手写堆数量**。
- **发现**：vanilla NIAH 近满分的模型，随长度/复杂度上升大幅退化——
  "太容易的检索测试没有区分度"。
- **membench 吸收**：✅ `upd_chain` 生成器模板（VT 的代理记忆版：同一槽位
  链式变更 N 次，探针只认终值）；✅ 干扰项难度旋钮列入未来工作。

### MemGPT（arXiv:2310.08560，2023.10）— 记忆系统谱系起点 — 摘要级（正文抓取超时）

- **OS 式虚拟上下文管理**：上下文窗口=内存，外部存储=磁盘，智能体自己
  在层级间搬数据；用"中断"做自我↔用户控制流交接。
- **自编辑记忆**：由智能体自己调用函数完成写入/检索/驱逐，而非用户管理。
- **评测域**：超长文档分析 + 多 session 对话（含反思/演化）。
- **对 membench 的意义**：boundary_refusal 测的正是"自编辑纪律"（什么该
  写进长期层、什么该驱逐）；subproc 协议的 memory_dump 即"外部层可视化"。
  工具名级细节待下轮读正文。

### Zep / Graphiti（arXiv:2501.13956）— Memora 系引用，事实失效的工程化 — 技术博客级

- **时序知识图谱**：事实变更时**旧边标记失效而非删除**，保留知识演化史
  ——与我们 `superseded_values` 的 FAMA 思路同源，但 Zep 是双向时间戳
  的图结构；membench 当前是探针级声明，未来可升级为逐条记忆的
  validity interval。
- **对 DMR 的批评**（警钟）：GPT-4-Turbo 全文塞上下文 98.2% > Zep 94.8% >
  MemGPT 93.4%——**转录太短/太简单的记忆基准，全文窗口即可轻松刷穿**。
  membench 的对策：探针全部设计在"全文窗口可答但记忆系统未必答好"的
  跨 session 场景，并用 bin 报告暴露负担增长下的退化。
- **LongMemEval 实测**：图记忆 vs 全文基线 +18.5%（时延 -90%，token <2%）；
  例外：single-session-assistant 类 -17.7%（图化丢失了"助手原话"细节）。

### LoCoMo（arXiv:2402.17753）— 谱系根节点 — 摘要级（补登记）

- ~300 turn/9K tokens/最多 35 session 的超长对话；QA/事件摘要/多模态
  三类任务。其 QA 含 adversarial 类（答案不在对话中）——拒答设计的
  最早出处之一，LongMemEval 的 abstention 与 BEAM 的 Abstention 均承此。
- **membench 已吸收**：✅ 拒答用例（bnd-05/06 + 模板）。

### 递归阅读后的发散想法（筛选后采纳 1 项，其余挂账）

1. ✅ **记忆演变轨迹（memory evolution trace）**【发散采纳】：现有所有
   benchmark 只测"终态 QA"；赛题明确要求衡量"记忆写入、检索、更新、拒绝"
   ——那就把**过程**也变成证据：每个 session 结束后导出记忆库快照并做
   diff（added/removed/kept），形成逐 case 的"记忆动力学曲线"。价值：
   能区分"从没写入"（写失败）vs"写了但丢失"（保持失败）vs"写了没删"
   （边界失败）——三种病因在终态指标里不可分。
2. ⏳ 检索定位率（LongMemEval session-level recall）：需智能体暴露"取了
   哪些记忆"，subproc 协议可加 retrieve 消息——下轮。
3. ⏳ 干扰项难度旋钮（RULER）：相近区分用例的"相似度参数化"——下轮。
4. ⏳ 逐条记忆 validity interval（Zep 双时间戳）：superseded_values 的
   图结构化——挂账。
