# 研发日志（DEVLOG）

> 按时间倒序追加。每轮记录：做了什么 / 为什么 / 证据（测试与数据）/ 下一步。
> 论文细节见 RESEARCH.md，此处只记决策。

## 2026-09-04 · 轮次 N+2：接入 git + 论文谱系精读 + 拒答能力

- **git 管理**：init、.gitignore（忽略 dist/结果目录等可再生文件）、
  按逻辑分块提交；此后所有变更走提交。
- **论文谱系精读**（RESEARCH.md 建档）：LongMemEval / BEAM / Memora 三篇
  读到构造流水线与指标定义级别。关键收获：
  - LongMemEval 的 `answer_session_ids`/`has_answer` 证据定位元数据 →
    membench schema 新增 `evidence_sessions`（probe）与 `date`（session）；
  - BEAM 的 nugget 0/0.5/1 评分 → 印证我们 must_include 部分得分设计；
  - LongMemEval abstention（"不存在的信息应拒答"）→ membench 缺失 → 本轮补上。
- **实现**：
  - schema：`any_include`（OR 语义，拒答探针必需）、`evidence_sessions`、
    `session.date`，均带静态校验；
  - scoring：any_include 分支（命中拒答措辞=correct；无任何拒答措辞=miss，
    理由注明"疑似编造"）；
  - 数据：bnd-05/bnd-06 手写拒答用例 + `bnd_abstain` 生成器模板（共 29 例）；
  - runner：证据 JSON 记录 evidence_sessions 与 session date。
- **实测**：拒答探针暴露 naive 的"鹦鹉学舌"失败（把上一个探针问题复述出来），
  boundary 维度从 0 → 7 分（第一次拒答成功、第二次复述失败）——与 Memora
  报告的"部分检索/编造"错误形态吻合，说明用例有判别力。
- **测试**：71 通过（新增 any_include/拒答/元数据校验用例）。
- **下一步**：系列二（MemGPT→Mem0→A-Mem→MemGym）精读；检索定位率指标
  （subproc 协议扩展）；criteria 级 FAMA。

## 2026-09-03 · 轮次 N+1：对照最新论文（BEAM / AMA-Bench / Memora）

- 新增 causal_reasoning 维度（AMA-Bench Type B）：前置条件→行动适配；
- schema 新增 `superseded_values`，被覆盖值复现时裁决升级 improper_reuse
  （FAMA 风格），naive 在 upd-01 上 reason 文案可见；
- 报告新增记忆负担分档（bin_report.json + HTML/MD 表），最后一档开放区间；
- LLMJudge.self_consistency_hook()（AMA-Bench §4.3 对标）；
- 修复：causal 用例判别力弱（naive 复述原句即得分）→ 期望改为要求
  "改用 <会语言>"行动适配；bin 标签开放区间防丢用例。

## 2026-09-03 · 轮次 N：对照 LongMemEval 后补两维

- 新增 temporal_reasoning（事件排序/时间间隔）与 multi_session_reasoning
  （跨 session 组合/聚合）；Smart 参考智能体补日期事件抽取、列表累积、
  自我介绍合成；DESIGN.md 加开源对照表（差异+短板都写明）。

## 2026-09-03 · 轮次 N-1：深度复检

- 修复 --judge openai 静默失效（CLI 参数未接线）；
- 修复沙箱路径逃逸（fs 探针/setup_files 绝对路径与 ..）；
- schema 拒绝重复 probe_id/session_id；
- 生成器补 recall 模板（六维全覆盖）。

## 2026-09-03 · 轮次 N-2：初版框架

- 9 项能力维度的 schema/runner/scorer/report/CLI/.deb 全链路；
- 三个内置参考智能体（nomem/naive/smart）验证区分度；
- 生成器（种子可复现）；样例结果入库；docs 三件套。

## 2026-09-04 · 轮次 N+3：引文递归阅读 + 记忆演变轨迹

- **递归阅读**（RESEARCH.md 系列三）：RULER（VT 链式绑定 + 难度旋钮）、
  MemGPT（OS 式分级记忆 + 自编辑纪律，摘要级）、Zep/Graphiti（事实失效
  边不删除 + "DMR 太简单被全文窗口刷穿"的警钟）、LoCoMo（adversarial
  类目为拒答设计源头）。
- **发散采纳——记忆演变轨迹**：所有开源 benchmark 只测终态 QA；赛题
  要求衡量"写入/更新/拒绝"，因此把过程也变成证据：每 session 结束后
  导出记忆库快照并 diff。实测三种病因清晰可分：
  nomem 全程 +0-0（写失败）/ naive +1-0→+1-0（该删未删）/ smart +1-0→+1-1（健康覆盖）。
  summary 新增 memory_ops.writes/deletes 计数。
- **RULER-VT 吸收**：gen-upd-chain 链式换号模板（同槽位改两次只认终值，
  中间值按 FAMA 判 improper_reuse）；smart 全对、naive improper_reuse。
- **测试**：75 通过；样例结果、README/DESIGN 同步；.deb 重建。
- **挂账**：检索定位率协议扩展、干扰项难度旋钮、逐条记忆 validity interval。

## 2026-09-04 · 轮次 N+4：系列二精读 + 检索定位率

- **系列二精读**（RESEARCH.md）：MemGPT/Letta（MemFS git 化 + Dreaming
  后台整理——工业记忆系统在"文件化"，印证 fs 证据设计）、Mem0（LOCOMO
  上 vs 全文基线 -91% 时延；四类问题已被我们九维覆盖）、A-MEM
  （Zettelkasten 演化式笔记——我们 memory_evolution 的评测对象）。
- **检索定位率落地**（LongMemEval session-level recall 对标）：
  - 适配层新增可选 `retrieval_trace(query)`：返回本次回答所用记忆条目
    及其来源 session（naive 记录被回放消息的 session；smart 记录槽位/
    安装模板/运维命令的写入 session；nomem 恒空；subproc 协议可扩展）；
  - 聚合层：evidence_sessions × retrieval_trace 求交集，summary 输出
    `retrieval_localization: {n, hits, rate}`；
  - 12 个手写用例标注 evidence_sessions（memory 探针不标注——不发消息）；
  - 实测：nomem 0%（什么都不取）/ naive 69%（常从旧 session 取——与其
    confusion 裁决一致）/ smart 100%（修掉了 op 分支不填 trace 的缺口）。
- **意义**：评分从"答对没"进化到"从对的 session 取没"——终态指标对、
  但过程取错来源的失败（如 naive 在 upd-01 上答旧地址）首次被单独量化。
- **测试**：75 通过；样例/文档同步；.deb 重建。

## 2026-09-04 · 轮次 N+5：难度旋钮 + subproc 检索追踪 + 三篇正文核实

- **论文**：MemGPT 正文（working context=仅函数可写的定长块、FIFO 带
  递归摘要、recall/archival 两库）；Mem0 正文（ADD/UPDATE/DELETE/NOOP
  逐字核实——与演变轨迹的 added/removed 对应；judge 跑 10 次报均值±std
  与我们同哲学）；HippoRAG（海马索引理论、单步多跳，摘要级）。
- **干扰项难度旋钮**（RULER）：dis 三模板各配 hard 变体（最小对兄弟值：
  同长、一字符差、互不为子串防超串陷阱），种子可复现。实测 hard 变体
  区分度保持：smart 1.0 / naive 0（confusion）/ nomem 0（miss）。
- **subproc 协议扩展**：retrieval_trace_request 消息；echo-agent 支持
  （记录消息来源 session）；不支持的智能体优雅降级 None（每 episode
  探测一次）。
- **事故与修复**：dis 模板加 hard 参数时丢了 dimension 字段（校验器当场
  拦截——静态校验的价值实证）；NAMES_HARD 初版含超串陷阱，自查修正。
- **测试**：75→77 通过。

## 2026-09-04 · 轮次 N+6：Zep 式事实生命周期 + 全轨迹 staleness 扫描

- **论文**：LoCoMo 全文级精读（adversarial 占 24.9%，长上下文模型仅 2.1%
  ——拒答设计源头坐实；断言式存储优于 session 摘要；FactScore 式事件
  摘要指标）；HippoRAG 2（ICML'25，修正结构化 RAG 在事实任务上的退化；
  factual/sense-making/associative 三类）；Zep（Graphiti 文档证实边失效
  为标准程序；t_valid/t_invalid 属性名诚实标注为二手来源）。
- **实现**：
  - schema：`fact_lifecycle`（value/valid_from/valid_until，session 级
    时间轴；校验引用存在性与顺序）；
  - scoring：失效值自动推导（invalid_values_at），与手工 superseded_values
    并行生效；
  - runner：每个 session 边界对记忆库快照做 **staleness 扫描**——失效事实
    仍在 => improper_reuse 过程级发现；summary 新增 staleness_violations；
  - 生成器：upd 模板带 lifecycle；hard 变体补 difficulty 元数据。
- **实测**：naive 在 upd-01 上产生 1 条 staleness 发现（"事实…已在 s2 失效，
  但记忆库仍保留"）；smart/nomem 为 0——三种病因的过程级判别补全。
- **测试**：77→81 通过；样例/文档同步；.deb 重建。

## 2026-09-04 · 轮次 N+7：criteria 级 FAMA + 对称缺席判据

- **论文**：A-Mem 正文（笔记七元组、strengthen/update_neighbor 演化、
  LOCOMO 多跳 2 倍优势与消融数据——演化式记忆系统从此有过程级考卷）；
  MemoryAgentBench（四能力含 selective forgetting，独立确认我们 staleness
  方向）；MemGym（memory-isolated scores 解耦思想，长度可控管线）。
- **实现（Memora 公式忠实落地）**：
  - `FAMA = max(0, MPA − λ·(1−FAA))`：探针按 expected 字段自动推断
    判据角色（absence=forbid_reveal/memory_excludes；其余 presence）；
  - **对称缺席判据**：敏感扫描与 staleness 的"通过"也产出可见行
    （此前只记失败——修复了 FAA 分母缺失的度量偏差，nomem 总分从 11.1
    修正为 15.9，其"什么都不存"的边界纪律首次获得应得分）；
  - 聚合 `fama_mean` 入 summary；HTML/Markdown 排名表加 FAMA 列；
- **性质测试**：纯 presence 用例 FAMA == 普通分（λ=0 向后兼容）；
  bnd-01 naive FAMA=0 / smart=1；upd-01 nomem FAMA 被压到 <0.5
  （presence 失败由 MPA 拉低，absence 守住不再加罚——公式语义正确）。
- **测试**：81→85 通过；样例/文档同步；.deb 重建。

## 2026-09-04 · 轮次 N+8：记忆维护探针 + 难度分层报告

- **论文**：IFEval（25 类可验证指令、~500 prompts——确定性评分的先声，
  我们 4/5 探针类型的哲学同源）；MemGym 正文（memory gain=配对运行差值、
  逐事件 condensation 记录≈我们的演变轨迹、**虚构实体阻断参数化记忆**、
  A-Mem 在 500k token 高压下夺冠）；MemGPT DMR 细节（MSC 人设一致会话 +
  self-instruct 出题 + ROUGE-L 与 judge 复合评分）。
- **实现**：
  - 记忆卫生探针 `memory_max_count`：重复声明去重检查——naive 记忆堆积
    3 份被 improper_persistence 捕获，smart 槽位覆盖天然通过；
  - 显式撤回用例 upd-05（"把我家地址忘掉吧"）：smart 实现撤回命令
    （槽位删除），naive 复述旧地址被 FAMA/improper_reuse 捕获，nomem
    无记忆自然通过；
  - 评分顺序修复：must_not_include 先于 any_include（防"泄露+拒答措辞
    并存"漏判）；
  - 难度分层报告：per_case 带 difficulty，summary 输出
    difficulty_breakdown，HTML/Markdown 加 easy/medium/hard 表。
- **事故**：撤回正则的跳过字符类误排除全角逗号导致跨不过"作废了，把"
  ——冒烟测试当场抓住。
- **测试**：85→88 通过。

## 2026-09-04 · 轮次 N+9：openKylin 适配自检 + 答辩相关工作页

- **论文**：AIOS（内核五服务，COLM'25——OS 集成评分项的理论锚）；记忆
  综述 2603.07670（write–manage–read 循环 + learned forgetting 开放挑战
  ——我们已覆盖其评测面）；OpenClaw 官方文档（记忆=工作区 Markdown 文件
  + Dreaming 整理——fs 证据通道天然直读，50 行 shim 可接入白盒评测）。
- **实现**：`membench doctor` 8 项环境自检（python/yaml/用例/内置智能体/
  subproc 回环/沙箱可写/UTF-8/CJK 字体），面向"评审在 openKylin 复现"
  的每个坑位，健康环境全过退出码 0；
- **答辩材料**：docs/RELATED_WORK.md——相关工作两表 + 六项差异化
  （每项标注出处）+ 主动承认的差距 + 一句话定位。
- **测试**：88→89。

## 2026-09-04 · 轮次 N+10：难度×维度热力表 + 三篇补读

- **论文**：Mem0 研究页（LOCOMO 分类别数字 + ADD-only 抽取 vs 我们的
  覆盖式更新对照 + 三信号检索融合）；MemOS（MemCube 版本化元数据 =
  fact_lifecycle 的通用化方向）；Generative Agents（谱系根补登记，
  反思能力对应 multi_session_reasoning）。
- **实现**：难度×维度热力表（aggregate 矩阵 + HTML/Markdown 带色表）——
  一眼定位"难度在哪里咬人"（naive 的 hard 档区分/更新/复用全 0）。
- **测试**：89 通过；样例/文档同步。

## 2026-09-04 · 轮次 N+11：逐用例证据查看器 + 演示彩排脚本

- **论文**：Mem0 图记忆已转 Platform 闭源（OSS 移除 Neo4j 等驱动约 4000 行，
  `relations` 字段消失——图记忆产品化信号，OSS 侧实体匹配仅作第三检索信号）；
  HippoRAG 管线形状经官方 README 确认（OpenIE KG + PPR + 单次调用多跳），
  数字待正文；Generative Agents 公式级细节本轮抓取失败，诚实标注未核实。
- **实现**：
  - 逐用例证据查看器 `comparison/evidence.html`：按智能体×用例组织，
    每条探针显示角色/裁决徽章/分数/理由（含证据片段）/回复/检索来源，
    可展开对话轨迹、记忆演变、记忆库终态；主报告加跳转链接；
  - `scripts/rehearse.sh`：按 DEMO_SCRIPT 分镜顺序的彩排脚本
    （doctor→validate→生成器一致性→评测→报告→产物清单）。
- **事故**：cmd_demo 改造漏了 agent_dirs 初始化（NameError，demo 当场炸）
  ——冒烟即修；viewer 测试的 case id 断言写死导致误报，放宽为结构断言。
- **测试**：89→90。

## 2026-09-04 · 轮次 N+12：赛题交付自查矩阵（终版）

- **论文**：HippoRAG 2 正文（factual/sense-making/associative 三任务 +
  passage 节点整合解决"概念-上下文权衡"；vs 最强嵌入基线平均 59.8 F1）；
  Generative Agents 公式逐字核实（三分量 min-max 归一化加权和、反思阈值
  150、洞见引用记忆指针形成反思树）——N+11 挂账关闭；Mem0 Platform 图
  记忆文档（共现边、无类型关系的 schema-free 方案，矛盾处理未文档化）。
- **实现**：docs/DELIVERABLES.md——交付 a–e × 证据物 × 验证方式 × 状态
  的自查矩阵；六维度 × 能力 × 实测证据；参赛者剩余待办 3 项（真机/接
  智能体/录视频）。矩阵中的关键数字（用例数/模板数/子命令数/样例分）
  用脚本逐一核查。
- **测试**：90 通过。

## 2026-09-04 · 轮次 N+13：判别力用例排名 + 报告元数据化

- **论文**：HippoRAG 2 数字（Table 2 全 7 基准 F1、§6.1 消融三组件、§6.3
  实为检索器可换性非持续学习）；mem0.ai/blog 一手 404，诚实降级。
- **实现**：高判别力用例排名（BEAM 风格极差排序）—— 评委问"哪题最有
  区分力"时直接给 Top 10；HTML/MD 报告加表，case_discrimination.json
  单独落盘。Top 1 = upd-01（极差 100，hard 档 lifecycle 扫描全胜 naive）。
- **事故与修复**：判别力逻辑写到 runner.py 错文件位置（auto 撤回 +
  重写）；函数签名误把 summaries 漏进 summarize_agent；调用顺序错位
  （build 在 disc 计算前）；`difficult` 与 `difficulty` 拼写不一致。
  全部发现并修。
- **测试**：91 通过（含新判别力用例测试 + 拼写锁）。
