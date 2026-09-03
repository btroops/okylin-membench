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
