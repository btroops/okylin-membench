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

### MemGPT 正文核实（补，arXiv:2310.08560 HTML §正文）

- **主上下文三段**（逐字核实）：系统指令（只读）+ **working context**
  （"定长读写文本块，仅能通过 MemGPT 函数调用写入"，存关键事实/偏好/人设）
  + FIFO 消息队列（首槽为被逐出消息的**递归摘要**）。
- **外部上下文两库**：recall storage（消息数据库，被逐出消息永久留存）+
  archival storage（任意长度文本对象的读写库，pgvector/HNSW 检索）。
- **函数名**：正文仅逐字出现 `conversation_search`；其余函数 schema 在
  站点外部，维持"待核实"。
- **membench 吸收**：working context 的"写操作留痕"思想 → 我们的记忆
  演变轨迹即其评测对应物。

### Mem0 正文核实（补，arXiv:2504.19413 HTML §2.1 + 附录）

- **操作分类学逐字核实**：ADD（无语义等价记忆时新建）/ UPDATE（用互补
  信息增强既有记忆）/ DELETE（被新信息矛盾的记忆移除）/ NOOP——经工具
  调用机制对 top-s 相似既有记忆做决策。
- **J 指标**：judge 对"事实正确/相关/完整/语境合适"做 CORRECT/WRONG
  二元判定，J=判对比例；**每个方法独立跑 10 次报均值±标准差**（与我们
  的跨 run std + judge votes 同一稳定性哲学）。
- **membench 印证**：我们的演变轨迹 added/removed 与其 ADD/DELETE 操作
  一一对应——过程证据度量的正是工业系统真实执行的操作。

### HippoRAG（arXiv:2405.14831，NeurIPS 2024）— 摘要级

- **设计**：海马体索引理论——LLM 当新皮层、KG+个性化 PageRank 当海马
  索引，实现单步多跳检索；多跳 QA 最高超 SOTA 20%，比迭代检索便宜
  10-30 倍、快 6-13 倍。
- **对 membench**：多跳检索是我们的 multi_session_reasoning 所测能力；
  检索定位率（上轮落地）正是检验"单步多跳"是否取对证据的探针。
- **局限**：依赖 LLM 抽取质量与 KG 构建成本（摘要未展开，待正文）。

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

### MemGPT / Letta（arXiv:2310.08560）— 摘要级 + 产品文档级（正文抓取超时）

- **设计**：OS 式虚拟上下文管理——上下文窗口=内存、外部存储=磁盘，
  智能体自己搬数据；用"中断"做自我↔用户控制流交接。
- **产品化演进（Letta 文档核实）**：原始 core/recall/archival 三层已演进为
  **MemFS——git 支撑的记忆文件系统**：/remember 显式教学、后台"Dreaming"
  子代理整理记忆（对话压缩后触发）、/doctor 审计记忆摆放/重复度。
- **对 membench 的印证**：①工业界记忆系统正在"文件化"——我们的 fs 证据
  与 memory_dump 双通道押对了方向；②"重复度审计"与我们的相近区分维度
  呼应；③Dreaming 式后台整理是未来可测的"记忆维护能力"（挂账）。
- **工具名级细节**（core_memory_append 等）仍未逐字核实，下轮补。

### Mem0（arXiv:2504.19413，2025.04）— 摘要级

- **架构**：动态"抽取→整合→检索"记忆层；增量更新走与既有记忆的比对
  （ADD/UPDATE/DELETE/NOOP——操作名细节待正文核实）。
- **评测**：LOCOMO 上 vs 6 类基线（记忆系统/RAG/全文/开源方案/专有模型/
  记忆平台），四类问题（单跳/时序/多跳/开放域），LLM-as-Judge 打分；
  **比全文基线 p95 时延 -91%、token 成本 -90%**，judge 分 +26% vs OpenAI。
- **对 membench 的印证**：①它们报告"时延/成本"，我们不报告（赛题不要
  性能指标，但可作扩展位）；②它们的四类问题已全部被我们九维覆盖。

### A-MEM（arXiv:2502.12110，NeurIPS 2025）— 摘要级

- **设计**：Zettelkasten 卡片盒——新记忆生成结构化笔记（上下文描述/关键词/
  标签），自动建立链接；**新记忆会触发既有笔记的演进**（更新其表示与
  属性），非 append-only。
- **对 membench 的印证**：①"记忆演化"正是我们 memory_evolution 轨迹所
  评测的对象——他们做系统、我们做该系统的"考卷"，命名撞车反而是好的
  叙事连接点；②"链接生成"提示了未来的多跳检索定位扩展。
- **局限**：摘要未给 LOCOMO 具体数字；正文待读。

### Zep / Graphiti 补充核实（arXiv:2501.13956）

- **已核实（文档级）**：Graphiti 的标准 `add_episode` 路径执行**边失效
  （edge invalidation）**，批量导入路径明确声明"不执行失效操作"——说明
  失效是图构建的核心步骤而非可选优化。
- **t_valid/t_invalid 属性名**：未能从一手来源逐字核实（HTML 超时），
  诚实降级为"二手来源引用"。
- **落地**：membench 新增 `fact_lifecycle`（value + valid_from/valid_until
  ——session 级时间轴），评分器自动推导失效值（无需手工 superseded_values），
  runner 在每个 session 边界对记忆库快照做**过期扫描**：失效事实仍在 =>
  improper_reuse 发现（"该遗忘的没遗忘"，Memora FAA 对应物）。

### A-MEM 正文核实（补，arXiv:2502.12110 HTML）

- **笔记七元组**：原始内容/时间戳/关键词(≥3)/标签/上下文描述/嵌入向量/
  链接集合（all-minilm-l6-v2）。
- **演化机制**：新笔记到达 → 与全部既有笔记算余弦相似取 top-k → LLM 分析
  共同属性决定建链 → 对每个邻居评估可执行 "strengthen"（加固连接）或
  "update_neighbor"（修订上下文/标签）——历史笔记的表示随新记忆**被改写**。
- **LOCOMO 多跳 QA 实测**：GPT-4o-mini 45.85 F1 vs LoCoMo 基线 18.41
  （≥2 倍优势）；token 成本 ~1.2-2.5k vs ~16.9k。
- **消融**：去掉链接生成+记忆演化，多跳 F1 45.85 → 24.55——两个模块互补，
  链接是组织基础、演化是精炼。
- **对 membench**：我们的 memory_evolution 轨迹 + staleness 扫描评测的
  正是 "update_neighbor" 类操作是否做对——演化式记忆系统现在有了
  过程级考卷。

### MemoryAgentBench（arXiv:2507.05257）— 摘要级

- **四能力**：accurate retrieval / test-time learning / long-range
  understanding / **selective forgetting**——最后者与我们的 staleness
  扫描 + FAA 直接对应（独立工作再次确认"选择性遗忘"是一等评测能力）。
- **构造**：把既有长上下文数据集改造为**增量多轮**格式（批评静态
  book-QA 式评测），覆盖四能力的人工校验集。
- **发现**：现有方法（含外部记忆模块与工具集成）无一掌握全部四能力。

### MemGym（arXiv:2605.20833，2026.05）— 摘要级

- **定位**：既有记忆基准是"聊天式保留"，忽略**执行过程中的动态记忆形成**
  ——统一多个 agent gym（tau2-bench/SWE-Gym/WebArena-Infinity 等）于
  单一记忆-推理接口。
- **指标思想（值得学）**：**memory-isolated scores**——把记忆表现与推理/
  检索/工具使用能力解耦，避免混淆变量；MemRM 轻量奖励模型替代昂贵的
  Docker 全程回放。
- **membench 对照**：我们的确定性探针（slot/choice/fs/memory）天然把
  "记忆"与"推理"部分解耦（答错原因可归因到没记住而非不会推）；跨 session
  分档（bin）是他们的长度分轴的 session 版。

### 系列二小结（对 membench 的三点强化）

1. **操作分类学对齐**：Mem0 的记忆操作（增/改/删）与我们的演变轨迹
   added/removed/kept 一致——我们的"过程证据"度量的是工业界真实在做的
   事，不是自造概念；
2. **记忆系统在文件化**：fs 探针 + memory_dump 双通道设计方向正确；
3. **检索定位率落地**：本轮实现（见 DEVLOG），对标 LongMemEval 的
   session-level recall——从"答对没"进化到"从对的 session 取没"。

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
5. ✅ 干扰项难度旋钮（RULER）：dis 系列模板新增 hard 变体（最小对兄弟值，
   同长一字符差、互不为子串防"超串陷阱"），种子可复现。
6. ✅ 检索定位率协议扩展：subproc 新增 retrieval_trace_request 消息，
   不支持的智能体优雅降级为 None（每 episode 只探测一次）。

## 系列四：OS 集成与生态（扣"与 openKylin 架构集成"15% 评分项）

### AIOS（arXiv:2403.16971，COLM 2025）— 摘要级

- **设计**：AIOS 内核把"调度、上下文管理、内存管理、存储管理、访问控制"
  五类服务从智能体应用中隔离出来，作为智能体与底层资源间的仲裁层；
  SDK 暴露 API。多框架智能体并发共享 LLM/工具容量，最高 2.1x 提速。
- **对 membench**：与 openKylin 智能体操作系统的对接位 = 我们的证据接口
  （stdio-JSONL / OpenAI 兼容 / 文件快照）即"内核服务旁路采集"——
  评测器不需要侵入内核，只需读智能体落盘产物。

### 记忆综述（arXiv:2603.07670，2026.03）— 摘要级

- **分类学**：记忆 = write–manage–read 循环；机制五家族（上下文压缩/
  检索增强/反思自改进/分级虚拟上下文/策略学习管理）。
- **领域趋势**：从静态召回基准转向"记忆与决策交织的多 session 智能体
  测试"——与我们的定位一致。
- **开放挑战五项**：持续整合、因果接地检索、可信反思、**learned
  forgetting**、多模态具身记忆。membench 已覆盖 learned forgetting 的
  评测面（staleness 扫描 + FAA）。
- **用法**：答辩时用该综述的分类学给我们的九维"上坐标系"。

### OpenClaw（赛题点名生态智能体）— 官方文档级

- **记忆模型（逐字核实）**：工作区纯 Markdown 文件——USER.md（稳定偏好）、
  MEMORY.md（持久事实，每 session 注入）、memory/日期.md（日记，索引不
  注入）、DREAMS.md（Dreaming 整理摘要）；检索 = memory_search（向量+关键词
  混合，可插拔 SQLite/Honcho/LanceDB）；**Dreaming 为默认后台整理**，
  压缩前先做 memory-flush。
- **重大落地结论**：OpenClaw 的记忆就是**磁盘上可读的文件**——membench 的
  fs 快照通道无需任何侵入即可捕获其记忆写入/更新；写一个 50 行的协议
  shim（读 MEMORY.md 作为 memory_dump）即可把它接入白盒评测。这直接
  回应赛题"面向 openKylin 生态已支持的主流智能体框架"。
- **行业收敛**：Letta MemFS 与 OpenClaw 文件化不谋而合——文件化记忆 +
  后台整理 + 混合检索是 2026 年的收敛形态，membench 的证据设计押中。

### Mem0 研究页补充核实（mem0.ai/research）

- **LOCOMO 分类别**（1,540 题，5 类）：多跳 95.4 / 时序 92.5 / 单跳 94.6 /
  开放域 82.3，总分 92.5，均 token ~6,956（全文 25,000+）。
- **增益归因**：时序重排"偏向当前事实" + **ADD-only 抽取**（只增不改——
  与我们测的覆盖式更新形成有趣的对照：Mem0 靠时序重排规避旧值，
  我们直接考"旧值还在不在"）。
- **检索三信号融合**：语义/关键词/实体并行打分再融合——检索定位率的
  工程对应物。

### MemOS（arXiv:2507.03724）— 摘要级

- **MemCube**：记忆的基本单元，封装内容 + 元数据（来源/版本），可组合/
  迁移/融合；三类记忆统一调度：明文（RAG）、激活态（内部状态）、参数级
  （权重）。
- **对 membench**：记忆作为"可调度系统资源"的观念与 AIOS 同路；
  MemCube 的 versioning 元数据正是我们 fact_lifecycle 的通用化方向。

### Generative Agents（arXiv:2304.03442）— 摘要级（谱系根补登记）

- **记忆流** + 检索（recency/importance/relevance 三分量——细节在正文）
  + **反思**（把记忆合成为更高层洞见）+ 规划；消融证明观察/规划/反思
  各自关键。
- **地位**：后续一切智能体记忆架构（MemGPT/A-Mem/Mem0）的引用源头；
  我们的九维中的 multi_session_reasoning 对应其"反思"能力面。

### HippoRAG 2 数字核实（补，arXiv:2502.14802v1 §6/Table 2-7）

- **基线澄清**：无 IRCoT 直接对比（结构化 RAG 基线 = RAPTOR/GraphRAG/
  LightRAG/HippoRAG），§6.3 实为"稠密检索器可换性实验"，非持续学习。
- **Table 2（F1, Llama-3.3-70B-Instruct reader）**：NQ 63.3 vs 61.9 / PopQA
  56.2 vs 55.7 / NarrativeQA 25.9 vs 25.7 / MuSiQue 48.6 vs 45.7 / 2Wiki
  71.0 vs 61.5 / HotpotQA 75.5 vs 75.3 / LV-Eval 12.9 vs 9.8——全面领先
  NV-Embed-v2。
- **Table 3/9（检索 recall@5/2）**：MuSiQue +5.0、2Wiki +13.9。
- **§6.1 消融**：linking / graph 构建 / triple 过滤三组件各自关键。
- **MEMORA LOCOMO 评测页 / blog 链接**：未能从一手来源核实（404 / 索引无），
  诚实降级为待核实。

### Mem0 LOCOMO 评测页（blog）— 一手 404

- mem0.ai/blog、/locomo-evaluation、/llms-as-operating-systems 等均 404；
  mem0.ai/research 仅给出 1,540 题 5 类分数（已上轮核实）。结论：mem0
  博客层 LOCOMO 分类别详细数字与 token/时延对比——无法从一手源核实，
  后续访问需直接索取代码复现。

## 系列五：记忆系统产品化与软件工程现场（2025-2026）

### OpenAI Memory（ChatGPT Memory 产品）— 一手源 403/404

- 多次尝试 openai.com、help.openai.com、platform.openai.com 文档站、
  cookbook 均 403 Forbidden 或 404 Not Found；无法从一手源核实“何时记
  忆、何时遗忘、用户控制”的实现细节。**业内常被引用的描述**（ChatGPT
  记忆分为 ephemeral chat history 与 long-term user facts、用户可查看/
  编辑/删除）来自二手评测和媒体报道，本轮不收录。
- **诚实降级**：OpenAI Memory 的工程化实现细节待一手源公开后补读。

### SIABench（arXiv:2603.06422，2026）— 全文级

- **数据集**：Part I SIA 25 场景 229 题（4 类：Memory Forensics/Malware/
  Network/Misc，三档难度）；Part II 告警分诊 135（55 TP / 80 FP，Snort
  + Suricata，从 TII-SRC-23 + CIC-IDS2017 生成）。
- **公平性预处**理（值得借鉴）：Gemini-1.5 Flash 改写 + 标识符中性化 +
  文件标准化 + 4 类去偏（开放改写/假设剔除/数字中性/外网知识搜索剔除）。
- **多状态 ReAct 工作流**：Init→Plan/Execute/Summarize→Solved；消融
  证明多状态显著优于单状态、摘要器降低上下文限制错误（Claude-3.5
  -12~32%）、ReAct vs Act-Only（老模型更明显）。
- **结果**：11 LLM；Claude-4.5-Sonnet 81.7% / GPT-5 80.7% 领先；
  Defense Evasion < 55% / Execution < 65% 普遍；Llama 8B 无限循环
  62.9% / o3-mini 错答率 58.1%；temperature=0 下输出仍不稳定。
- **membench 借鉴**：抽象化预处（标识符/文件名中性化）可作为数据
  生成管线的增强项（避免“中文用例被 LLM 偏见影响”类评审质疑）。

### Git-Context-Controller（arXiv:2508.00031，2026 v3）— 摘要级

- **设计**：把智能体上下文管理为版本化文件系统——`COMMIT`（任务
  边界里程碑）/ `BRANCH`（隔离探索）/ `MERGE`（路径回并）/ `CONTEXT`
  （分级检索），把“聊天日志”变成“仓库历史”。
- **结果**：SWE-Bench Verified 80%+，超 13% 相对长上下文基线，**击败
  26 个开源/商业系统**；BrowseComp SOTA（数字未给）。
- **membench 借鉴**：思路与 Letta MemFS、MemCube versioning 同源；
  我们的 fact_lifecycle + staleness 扫描评测的正是“commit 时点后过
  期事实处理是否正确”——而 GCC 的 BRANCH 行为与我们的“该删未删”
  病理正相反（可作未来扩展）。

## 系列六：MEASURING HALLUCINATION IN AI CODES 之类的相关...（不展开）

## 系列七：2026 年新一批 long-term memory benchmark（用户给的清单）

### ATM-Bench (arXiv:2603.01990, 2026.03) — 全文级

- **任务**：multimodal 多源个人 referential memory QA（4 年隐私保护数据：6,741 邮件 + 3,759 图片 + 533 视频，12k 记忆项，1,038 QA）。
- **5 能力**：PR（个性化指代）/ LA（位置感知）/ MUT（时序更新）/ ME（多证据组合）/ ABS（拒答）。
- **SGM**（schema-guided memory）：键值结构化 vs DM，6 baseline + RAG 上全胜。
- **关键发现**：**Hard 集所有系统 < 20%**；Piled Memory 等同 Linked Memory（编码 1/10 时间）。
- **membench 借鉴**：5 能力与 9 维大体正交；**缺 LA 与多模态**——后者是 openKylin 桌面评测的自然外延。
- **诚实承认**：纯文本，未覆盖多模态。

### SubtleMemory (arXiv:2606.05761, 2026.06)

- **任务**：fine-grained relational memory discrimination（complementary / nuanced / contradictory 三类关系记忆辨别）。
- **规模**：1,522 instances / 10 long histories / 1,090 relation-controlled memory-variant sets。
- **被测系统**：6 standalone + 2 Claw-style 原生 + 3 Claw-style 插件。
- **关键发现**：**standalone 系统对 nuanced/complementary 弱**。
- **membench 借鉴（本轮实现）**：
  - `probe.relation` 字段（5 取 1）+ schema 校验 + Probe 构造透传
  - 3 个手写用例（rel-01 contradictory / rel-02 nuanced / rel-03 complementary）
  - runner 三处 row 构造点注入 relation
  - aggregate.relation_breakdown 维度 × 难度 矩阵
  - 报告（HTML+MD）加"关系型专项（SubtleMemory 风格）"表
  - **实测复现论文发现**：smart 50/0/0、naive 0/100/33、nomem 0/0/0
  - 论文的"standalone 系统弱"被规则记忆智能体（smart）实证

### PAST-Bench（Princeton）— 摘要级

- **任务**：4 能力自进化（memory / procedural / information-gathering / update）。
- **方法**：**对照实验**——同一 agent 在"开/关保留"两个条件下做相同任务，diff = 真实收益。
- **结果**：7 base models × 4 frameworks；**update 类任务提升最显著**。
- **membench 借鉴**：① "开/关保留"对照可作下轮智能体配对评估范式；② update 是我们强项。

### 共同启示

- 多模态 + 关系辨别 + 自进化是 2026 趋势；我们的"系统级证据 + 确定性优先 + FAMA"仍具差异点。
- 2026 行业数据基线 1k–1.5k 实例——我们 35 手写 + 24 模板仍偏小，但**证据包丰富度（多源 + 过程级）是行业均无的**。
