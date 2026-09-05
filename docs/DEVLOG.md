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

## 2026-09-04 · 轮次 N+14：记忆写入纪律探针 + 报告导航条

- **论文**：OpenAI Memory（ChatGPT Memory）一手源 403/404 无法核实——诚实
  降级；SIABench 全文级（25 场景 229 题、4 类去偏、11 LLM 排名、多状态
  工作流消融）；Git-Context-Controller（用 git 语义管理长程上下文，
  SWE-Bench Verified 80%+ 击败 26 系统——印证文件化记忆 + commit/branch
  是 2026 收敛形态）。
- **实现**：
  - `case.noise_max_count`：跨 session 噪声累积上限——智能体记忆系统
    不应把闲聊噪声逐条入长期层；runner 每 session 边界扫描；
  - 用例 ret-06-noise-discipline（3 个 session 反复"今天好累"）：
    smart 0 违规 / naive 2 违规（直接确认了工业界 A-MEM 演化质量
    与 SIABench 公平性预处理的同向关注）；
  - 报告 HTML 导航条（排名/热力/高判别/证据查看器快速跳转 + 锚点）。
- **事故**：dataclass 字段替换只发生一次没补上、normalize_text 未导入、
  tests 中 31→32/0.7→0.55 阈值滞后——逐个被冒烟/测试抓到并修。
- **测试**：92 通过。

## 2026-09-04 · 轮次 N+15（分支 evidence-driven）：评分可信度实验 + 规模化实验 + 叙事收口

> 本轮响应外部评审建议：停止扫论文，转做"答辩三问"的实验证据与总叙事。

- **实验 ① 评分可信度**（tests/labels/，185 探针 × 3 智能体）：
  - 独立盲评器（另行实现，不经 scoring.py）：raw agreement **83.8%**、
    Cohen's κ=0.75（六分类）；
  - 30 条分歧逐条仲裁：21 条盲评器权限制约（无记忆库/文件访问权）、
    9 条类间语义近似、**1 条真实改进点 → 当场修复**（any_include
    未命中时回退查 must_not_include/lifecycle 失效值定类 improper_reuse
    而非直接 miss；回归测试 2 条锁定）；
  - 对照锚点：AMA-Bench LLM judge 人机一致 92.7%、Memora 88.3%、
    我们零方差（test-locked）；
  - 诚实 caveat 3 条写入报告（第二标注者是规则匹配器非真人等）。
- **实验 ② 规模化**：gen --variants 15 --seed 2026 → **315 用例**
  validate 全过（9 维），区分度保持 smart 91.5 / naive 32.3 / nomem 17.5，
  945 次评测 0.4s。
- **叙事收口**：docs/EVIDENCE_CHAIN.md（范式主张：记忆质量应从
  "状态→检索→决策→行动"证据链评测，而非最终回答；三层架构图；
  五种失败模式 × 证据指纹表——其中"该忘未忘/不该记却记"在终态 QA
  下不可见是存在理由的最强论据）；docs/RELATED_WORK.md 重写为
  评委三问直接答案 + 逐项 gap analysis（六项原创/继承分账标注）+
  四层引用骨架。
- **测试**：92→94。

## 2026-09-05 · 轮次 N+17：从“gitignore 残留”反推盲点

外部审计指出现存 `.gitignore` 仍有

```
# 独立评测脚本产物（另一个 agent 写）
tests/labels/
```

两行——这暴露了 N+15 提交 8cd6c5a 的**真实盲点**：

- 我当时在 commit message 里写“实验数据已落盘”，但
  `tests/labels/` 实际从 694b5b8 起就被这行规则屏蔽，
  `git add -A` 静默跳过——产物压根没进 8cd6c5a；
- 我后来 07b5f7f / b983a74 / 3020245 才移除 ignore 并强加入库；
- 也就是说 8cd6c5a 的 message 与实际入库**不一致**，
  我之前 N+15 整轮的“实验产物完整”声明并不成立。

**这条经验对后续工作更普适**：涉及“产出/产物”类的 commit，message
必须能由 `git show --stat` 单独验证——只说“做了 X”是不够的，必须能在
diff 里看到 X 的痕迹；否则 message 与 reality 漂移，下一次审计时
只能靠文件时间戳反向破案。

清理：8cd6c5a 已在 N+15c（3020245）从历史中由三个准确 commit
替代；本轮对 .gitignore 残留做最终确认 + DEVLOG 留痕。

## 2026-09-09 · 轮次 N+18：OpenClaw 真实实例接入（Docker，2A 🔶→✅）

- **做了什么**：新增 `docker/openclaw/`（compose/.env.example/干净记忆快照）
  与 `agents/openclaw_shim.py`（subproc 协议适配器）+ `agents/openclaw.agent.json`
  + `docs/OPENCLAW_REAL_INSTANCE.md`。membench 经 shim 驱动容器内真实
  OpenClaw（官方镜像 openclaw/openclaw:latest，Gateway:18789，memory-core +
  Dreaming 插件实测在线），LLM 后端为 Anthropic 兼容端点（DeepSeek，
  `models.providers.anthropic.{baseUrl,api=anthropic-messages,models[]}` +
  paste-api-key 鉴权）。
- **为什么**：回应"2A 从逻辑层跑通升级为真实软件实例跑通"的评审可信度
  诉求；OpenClaw 记忆为磁盘文件（USER.md/memory/日记），与 membench 的
  memory_dump 白盒通道天然对接，无需侵入。
- **实测证据**：
  - ret-01-name-editor / ret-02-address 双用例 score=1.00（retention=100），
    探针裁决 correct（"你叫小明（Xiao Ming）。"/"B. vim"）；
  - 证据含真实 transcript、memory_dump（USER.md 含
    `<!-- observed: 2026-09-05 | status: active -->` 条目）、memory_evolution；
  - 跨用例污染检查：ret-02 全文无 ret-01 的「小明/vim」→ 隔离生效。
- **三条关键实测教训**（都已写进 OPENCLAW_REAL_INSTANCE.md 障碍表）：
  1. OpenClaw 记忆权威存储是 state SQLite + 滚动会话历史，Markdown 只是
     投影——只清文件会被绕过（模型答"早就记住了"）；必须每 episode 用
     独立 `--session-key` + 文件层还原双管齐下；
  2. 交互式智能体会以 `ask_user` 工具收尾等用户输入，单发 CLI 调用因此
     300s 挂死——`tools.deny=["ask_user"]` 后模型改为纯文字收尾；
  3. 容器以评测用户 uid 运行才能让 shim 的文件级 reset 生效（否则
     chown 不匹配导致 PermissionError 被静默吞掉，污染照旧）。
- **诚实记录的局限**：memory-core 语义检索因缺 OpenAI embedding key 降级
  为关键词匹配（sync failed 日志持续）；验证环境是 Docker 近似环境，
  openKylin 真机部分仍属交付物 c/e 待办。
- **测试**：shim 通过 py_compile 与协议回路自检（session_start/memory_dump/
  session_end 仅产出一行 memory 消息）；e2e 以真实评测代替单测覆盖。
- **下一步**：接入更多维度用例做真实对比；清理孤儿会话；openKylin 真机
  复跑。

## 2026-09-05 · 轮次 N+19：测量有效性升级 + 答案锚定（answer anchoring）

N+18 把管线跑通了（ret-01/ret-02 双用例 100%），但本轮揭出**两层更深的问题**
——不修 N+18 提交里声称的 retention=100% 也不能作为评测证据。

### 一、问题 A：探针的上下文泄漏（测量学）

N+18 shim 把一个 episode 的所有 session（s1/s2/probe）放进**同一个** OpenClaw
滚动会话键 `agent:main:mb-<uuid>`。探针会话里 s1 的剧本原文仍在上下文，
模型答对**可能只是因为上下文窗口里还有 s1**，而非读了 USER.md。

证据（探针回复原文）：

```
[probe:p1] 你叫小明（Xiaoming）——这是今天记下的称呼偏好，我会一直这么叫你。
            （注：记忆索引目前有点问题——缺 OpenAI 的 API key…）
```

主答案正确，但口吻「记下的偏好"是"N+18 滚动会话里看到的原文，"读 USER.md"
只补在括号里。

### 三、设计 + 实现

**shim 升级**（`agents/openclaw_shim.py`）：
- 收到 harness 的 `session_start{session_id}` 时轮换 OpenClaw 会话键：
  `agent:main:mb-<uuid>:<session_id>`。session_id 含 s1/s2/probe:pN，
  各自会话无剧本原文。
- `retrieval_trace_request` 调真实的 `openclaw memory search --json`，
  解析 JSON 输出（容错 stdout 混入日志行）；失败/空结果优雅降级为空列表。
- episode 层会话键前缀仍保留（多重保险）。

**答案锚定（answer anchoring）**（`membench/scoring.py`）：
- 量化发现：openclaw-full 35 用例重评分时，**10 条 confusion/improper_reuse
  裁决中 10 条主答案正确**——模型答对了事实后再另起一段引用记忆原文（含
  干扰项），确定性评分的全文 must_not_include 扫描被系统性误伤。
- 内置参考智能体短句模板从没暴露过这面，故而不影响基线。
- 修复：must_not_include 检查时，若主答案段（首个空行前的连续正文）已
  包含全部 must_include，且主答案段内不含 must_not_include 项，则豁免
  confusion/improper_reuse 裁决判为 correct。**前提**：
  - 必须有 must_include（纯 absence 探针不豁免）；
  - 敏感模式（case.sensitive_patterns）命中不受豁免；
  - 必须 normalize_text **之前** 切分（后者会移除换行/空格）。
- 实测：4/10 误伤探针被正确豁免（dis-01 p1 / tem-01 p1 / upd-01 p1 /
  upd-02 p1），其余 6 条是真实混淆（dis-02 p1 答了家庭地址而非公司、
  tem-01 p2 主答案段枚举所有事件等）。

### 二、问题 B：评分系统的误伤（必须修，不能仅写文档）

解决：见上「答案锚定」段。

### 四、判别实验（gate test）

N+18 commit 时声明的「同步落盘、读即最新」是更早的人工观察，未做实证
测量。本轮用三个独立实验把根因落实：

| 实验 | 假设 | 实测 |
|---|---|---|
| G1 跨会话召回 | 新会话键能否仅凭文件记忆召回 | ✅ `gate1b` 会话（无对话历史）答出「小明 + vim」，并标注"我是直接读的 USER.md" |
| G2 空白对照 | reset 后新会话应无幻觉 | ✅ 干净 workspace 下新会话如实答「USER.md 是空的」 |
| G3 retrieval_trace 可行性 | `memory search` 输出格式 | ⚠️ 仅返回 JSON 但 results 总为空——向量索引缺 OpenAI embedding key |

### 五、实测数据

| 智能体 | 总分 | retention | recall | dynamic_update | distractor | boundary | reuse | temporal | multi-session | causal |
|---|---|---|---|---|---|---|---|---|---|---|
| smart（规则） | 96.6 | 77 | 100 | 92 | 100 | 100 | 100 | 100 | 100 | 100 |
| **openclaw-real** | **72.5** | **100** | **100** | 55 | 33 | 86 | 100 | 50 | 100 | 0 |
| naive（全量） | 30.9 | 62 | 50 | 0 | 0 | 7 | 50 | 0 | 33 | 75 |
| nomem | 18.9 | 17 | 0 | 54 | 0 | 100 | 0 | 0 | 0 | 0 |

openclaw 在 retention / recall / task_reuse / multi_session 四个维度与 smart
持平甚至更强（**retention 100 vs smart 77** — 真实智能体的文件级长期记忆
比规则实现的全量回放更「知道什么是用户档案」）。弱项符合真实智能体预期：
distractor 33（同类区分需要 prompt 显式控制）、temporal 50（时序枚举常误
中干扰项）、dynamic_update 55（更新意图识别）、causal 0（推理但脚本用
n/a 因网络抖动）。

答案锚定修复对 smart/naive/nomem **零影响**（基线逐维逐分完全一致）——
锚定只在「主答案段外提及干扰项」时触发，模板短句从未暴露该模式。
这验证了改动不污染既有评分基线。

### 六、测试

- `tests/test_scoring.py`：新增 `TestAnswerAnchoring`（5 用例）：
  - `test_anchor_passes_explanatory_mention` 主答案正确+干扰项仅在解释段→correct
  - `test_anchor_requires_full_must_include_in_zone` 主答案段没给全→不豁免
  - `test_anchor_not_applied_when_bad_in_answer_zone` 干扰项在主答案段→真混淆
  - `test_anchor_not_applied_without_must_include` 纯 absence 探针→不适用
  - `test_sensitive_value_not_anchored_away` 敏感值→improper_persistence 不豁免
- `tests/test_openclaw_shim.py`（N+19 新增）：6 用例覆盖
  - episode 前缀唯一性
  - session_start 轮换正确性
  - 探针会话键不含剧本原文
  - retrieval_trace 解析容错（混日志输出、空结果、无 JSON 优雅降级）
- 全测试套件 104 通过（原 94 + N+19 新增 10）。

### 七、诚实记录的局限

- **向量记忆降级未变**：memory-core 语义检索仍需 OpenAI embedding key；
  本环境缺该 key，retrieval_trace 始终为空。已如实记录。
- **网络抖动**：cau-01 因 Docker daemon 与网关的偶发连接错误（rc=1）、
  而非模型能力问题被判 n/a；rerun 该用例可恢复。
- **docker 组身份**：shim 调用 `docker compose exec` 需要宿主机评测用户
  在 docker 组里，否则 PermissionError。本机由 `sg docker` 包装解决。
- **openKylin 真机部分**仍属交付物 c/e 待办。

### 八、下一步

- 清理孤儿会话（state SQLite 中累积的 mb-* 会话键），大规模跑批前必要；
- 跑一次 `--runs 3` 看 openclaw 稳定性 std（参考 N+15 跨运行 σ=0 的基线）；
- 把 openclaw-real 跑分固化为 examples/sample_results/ 的标准参考物；
- openKylin 真机 .deb 复跑 + 桌面录屏。

## 2026-09-05 · 轮次 N+20：孤儿会话清理工具化 + openclaw 三次全量稳定性实测

- **做了什么**：
  1. `scripts/openclaw_cleanup_sessions.py`——直删 agent 会话库
     （`agents/main/agent/openclaw-agent.sqlite`）中 `session_key LIKE '%:mb-%'`
     的全部行（session_nodes / participants / windows / transcript_events /
     trajectory_runtime_events / transcript_event_identities /
     session_transcript_* 等 16 张关联表，按 session_id→session_key 两级外键
     顺序删除 + wal_checkpoint）。宿主机 python 的 sqlite 过旧（不识别
     STRICT 表），故在容器内以其自带 python3 执行，流程为
     停网关 → 备份 → 删除 → 起网关。
  2. 实测两轮：首轮 148 孤儿 / 7,694 行，复跑 `--runs 3` 后再清
     308 孤儿 / 14,797 行，均回到基线 20 个会话；网关 healthy、agent
     调用正常。清理脚本幂等，可反复执行。
  3. `--runs 3` 全量 35 用例 × 3 次真实 LLM 评测（78 分钟）落盘
     `results/openclaw-stability/`。
- **稳定性数据（三次均值 ± 跨 run σ）**：

  | 维度 | 均值 | σ | 探针数 |
  |---|---|---|---|
  | retention | 94.9 | 7.3 | 39 |
  | recall | 75.0 | 0.0 | 12 |
  | dynamic_update | 61.5 | 6.3 | 39 |
  | distractor_discrimination | 25.0 | **20.4** | 24 |
  | boundary_refusal | 83.9 | 5.5 | 40 |
  | task_reuse | 33.3 | 11.8 | 12 |
  | temporal_reasoning | 50.0 | **40.8** | 6 |
  | multi_session_reasoning | 66.7 | 0.0 | 3 |
  | causal_reasoning | 0.0 | 0.0 | 6 |

  FAMA=64.3；单 run 用例级均分 61.4 / 63.2 / 67.1（N+21 更正口径：
  每用例 score 均值×100，run02 为 34/35——bnd-01 连接错误无分被剔除）。
- **两点诚实结论**：
  1. **单次跑分会被幸运/不幸采样放大**：N+19 重评分得到的单 run 画像
     （如 task_reuse=100、multi_session=100）在三次均值下回落到 33 / 67
     ——std 列正是为答辩时抵御"跑一次挑好结果"质疑而设，今后 openclaw
     数字一律报三次均值 ± σ；
  2. **σ 与样本量强相关**：temporal σ=40.8 但只有 6 探针、multi_session
     σ=0.0 也只有 3 探针——探针少的维度方差估计不可信，扩大数据集
     （N+16 已具备 1995 例生成能力）是压低 σ 的正路，而非调 judge。
- **测试**：本轮无评分逻辑改动，104 测试基线不变；清理脚本以两轮实测
  代替单测（幂等性由"回到基线 20"直接验证）。
- **下一步**：把 stability 结果固化为参考物；openKylin 真机复跑。

## 2026-09-05 · 轮次 N+21：openclaw 三次稳定性固化为标准参考物

- **为什么**：`results/` 在 .gitignore 里（定位为可再生产物），但三次
  真实 LLM 全量评测花了 78 分钟、且"单 run 不得作口径"的结论必须有一份
  可追溯证据背书——原始落盘必须进入版本库。
- **做了什么**：把 `results/openclaw-stability/` 全量固化到被 git 跟踪的
  `examples/sample_results/openclaw-stability/`（112 文件 / 1.5M）：
  - `summary.json`：三次聚合（九维 score / std_across_runs / 裁决分布、
    总分 54.5、FAMA 64.3、per_case、难度分层、记忆操作计数）；
  - `runs/run01..03/`：105 个逐用例证据 JSON（每探针 verdict/score/
    reason/reply/hits + transcript/memory_dump/fs 证据）——σ 可逐条复算；
  - `comparison/`：单智能体报告四件套（comparison.md / report.html /
    evidence.html / summaries.json + bin/判别度 JSON）。
- **参考物 README**（该目录内）写明：来源与口径（日期/智能体/命令/耗时/
  清理轮次/敏感扫描 0）、九维均值 ± σ 表、四条诚实结论（单 run 幸运采样
  含 upd-04-memory-store 三次 1.0/0.0/1.0 的具体实例、causal 三次一致
  失败非抖动、σ 受探针样本量限制、检索定位率 0.0 是 embedding key 缺失
  的环境局限）、复现命令（含容器内执行清理脚本的准确调用）。
- **口径更正**：61.4/63.2/67.1 实为**用例级**均分（每用例 score 均值
  ×100；run02 为 34/35），N+20 误标为"探针均分"，DELIVERABLES/DEVLOG
  已同步更正；全探针口径复算为 61.5/63.7/68.4，参考物 README 注明口径
  以免歧义。入库前对全部 JSON 做了密钥/敏感串扫描（干净）。
- **外层 comparison/ 升级为四智能体对比**（并行会话产出，合并入库）：
  `examples/sample_results/comparison/` 由"三内置对比"重建为
  smart/naive/nomem/openclaw-real 四智能体版——report.html（雷达/热力表，
  openclaw 列为 3 次均值口径）、**evidence.html 内嵌四智能体全部证据**
  （3×35 + 105 = 210 份逐用例 JSON，可按智能体/用例/裁决筛选）、
  bin_report/case_discrimination 同步。数据来源：builtins←
  results/controls-rerun（N+19 答案锚定后评分），openclaw←本参考物。
  证据一致性已验证：openclaw-stability 的 summary/runs 与四智能体报告
  引用逐字节一致。
- **上层 README**：`examples/sample_results/README.md` 重写——内容表
  （openclaw-stability 行 + 四智能体 comparison 行）、**「四智能体口径」节**
  （smart 96.6 单次确定性 / openclaw-real 54.5 三次均值 ± σ / 单次跑分
  不得用于答辩对比）、证据导读（naive 双包 + openclaw 真实软件行为属性）、
  复现命令（内置一条命令；openclaw 78 分钟/3 runs + 清理脚本）、35 用例
  数修正（旧文误写 24）。
- **测试**：无 membench/tests 代码改动（相对 N+20 全绿提交 git diff 为空）。
  提交时宿主 WSL2 回环网络故障（TCP 握手通、HTTP 数据黑洞——gateway
  healthz、unittest mock server、最小回环实验同一症状，18:40 后出现），
  unittest 改在容器内复跑：`docker run --rm -v <repo>:/work -v
  /usr/lib/python3/dist-packages:/hostsite:ro -e PYTHONPATH=/hostsite
  openclaw/openclaw:latest python3 -m unittest discover -s tests`
  → **Ran 104 tests / OK**。容器网络栈独立于宿主回环，结论有效。
- **下一步**：openKylin 真机 .deb 复跑 + 桌面录屏（需真机，环境外待办）；
  可选：用 N+16 的 1995 例生成能力扩大数据集压低 σ；
  宿主 loopback 故障若持续需 `wsl --shutdown` 重启（环境外操作）。
