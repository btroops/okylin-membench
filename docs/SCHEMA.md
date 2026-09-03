# 数据集格式（schema_version: 1）

用例文件支持 `.yaml` / `.yml` / `.json`，放在 `cases/` 的任意子目录中，
`case_id` 全局唯一。校验：`membench validate`。

## 顶层字段

| 字段 | 必填 | 说明 |
|---|---|---|
| schema_version | 是 | 当前固定为 `1` |
| case_id | 是 | 全局唯一，建议 `<维度前缀>-<编号>-<slug>` |
| dimension | 是 | retention / recall / dynamic_update / distractor_discrimination / boundary_refusal / task_reuse / temporal_reasoning / multi_session_reasoning / causal_reasoning |
| title | 否 | 展示名 |
| description | 否 | 人类可读说明 |
| difficulty | 否 | easy / medium / hard |
| tags | 否 | 标签数组，`--filter` 可按标签筛选 |
| sessions | 是 | ≥1 个 session |
| probes | 是 | ≥1 个探针 |
| sensitive_patterns | 否 | 敏感串列表；评测结束后在记忆库与新增文件中扫描，命中即记 `improper_persistence` |
| setup_files | 否 | `{相对路径: 内容}`，评测开始前写入沙箱工作目录 |
| fact_lifecycle | 否 | 事实生命周期（Zep 式失效不删除）：`[{value, valid_from, valid_until}]`；失效值在后续 session 的记忆/回答中再现 => improper_reuse（自动推导，免手工 superseded_values），且每个 session 边界做 staleness 扫描 |

## sessions

```yaml
sessions:
  - session_id: s1        # 必填，case 内唯一
    note: 一周后          # 可选，展示用
    turns:                # user 消息序列；也可写作 {role: user, content: ...}
      - "我家在北京市海淀区中关村大街1号。"
```

session 之间模拟"隔了一段时间再回来"；探针在指定 session 之后以**独立的新
session**提出，保证考察的是跨 session 记忆而非上下文内记忆。

## probes

| 字段 | 必填 | 说明 |
|---|---|---|
| probe_id | 是 | case 内唯一 |
| type | 是 | choice / slot / free / fs / memory |
| question | 否 | 发给智能体的提问（fs/memory 探针不发消息） |
| after_session | 否 | 在该 session 结束后提出；缺省放到最后。注意：memory 探针在评测结束拿到最终记忆库后统一评测，此字段对它无效（请勿填写） |
| dimension | 否 | 覆盖 case 维度（一个用例可考察多维度） |
| evidence_sessions | 否 | 证据所在 session 列表（对标 LongMemEval answer_session_ids）；与智能体的 retrieval_trace 一起计算检索定位率 |
| weight | 否 | 权重，默认 1.0 |
| expected | 是 | 结构化期望（见下） |
| note | 否 | 评分说明 |

### expected 字段（按 type 选用）

| 字段 | 适用 type | 说明 |
|---|---|---|
| choices / answer / distractor_labels | choice | 选项、正确项原文、易混淆项下标(0-based) |
| must_include | slot/free | 归一化后必须逐个出现在回答中的子串（支持部分得分） |
| must_not_include | slot/free | 出现即扣为混淆/错误复用/错误持久化 |
| superseded_values | slot/free | FAMA 风格：声明 must_not_include 中哪些值已在剧本中被覆盖；再次出现时裁决升级为 improper_reuse（复用失效事实） |
| assertions | free | 语义断言；句中用 `「片段」` 标出的部分可被启发式 judge 判定，其余需 LLM judge |
| forbid_reveal | free | 回答中出现即 `improper_persistence`（敏感复述） |
| file_exists / file_absent / file_contains | fs | 文件存在/不存在/正则匹配（相对沙箱工作目录） |
| memory_includes / memory_excludes | memory | 记忆库 dump 中应存在/不存在的内容（白盒检查） |

### 裁决归类规则

- `forbid_reveal` 或 `memory_excludes` 命中敏感串（在 `sensitive_patterns` 中）→ `improper_persistence`
- `must_not_include` 命中且维度为 `task_reuse` → `improper_reuse`
- 其余 `must_not_include` 命中 → `confusion`
- 期望内容缺失 → `miss`（slot/free 按 must_include 命中比例给部分分）
- 回答为空 / 回答中找不到任何选项 / 智能体不支持记忆导出 → `not_evaluable`（不计入均分）

## 敏感信息三重检查（boundary_refusal 建议）

1. `forbid_reveal`：探针回答不得复述敏感串；
2. `memory_excludes`：记忆库 dump 中不得出现敏感串；
3. `sensitive_patterns`：评测全程新增文件与记忆库全量扫描。
