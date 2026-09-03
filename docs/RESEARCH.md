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
