# openKylin 智能体长期记忆评测报告

## 总分排名

| 排名 | 智能体 | 总分 | FAMA |
|---|---|---|---|
| 1 | openclaw-real | 54.5 | 64.3 |

## 六维对比

| 维度 | openclaw-real |
|---|---|
| 长期保持（retention） | 95 |
| 记忆调用（recall） | 75 |
| 动态更新（dynamic_update） | 62 |
| 相近区分（distractor_discrimination） | 25 |
| 边界识别（boundary_refusal） | 84 |
| 任务复用（task_reuse） | 33 |
| 时序推理（temporal_reasoning） | 50 |
| 多 session 推理（multi_session_reasoning） | 67 |
| 因果推理（causal_reasoning） | 0 |

## 记忆负担分档对比（沿用 BEAM 思路）

| 智能体 | 1-1 sessions | 2-2 sessions | 3-4 sessions | 5+ sessions |
|---|---|---|---|---|
| openclaw-real | 55 | 69 | 72 | - |

## 难度分层得分

| 智能体 | easy | medium | hard |
|---|---|---|---|
| openclaw-real | 74 | 61 | 62 |

## 难度 × 维度热力表

| 智能体 | 难度 | 长期保持 | 记忆调用 | 动态更新 | 相近区分 | 边界识别 | 任务复用 | 时序推理 | 多 session 推理 | 因果推理 |
|---|---|---|---|---|---|---|---|---|---|---|
| openclaw-real | easy | 100 | 100 | 39 | - | - | - | - | - | - |
| openclaw-real | medium | 90 | 50 | - | 22 | 84 | 44 | 50 | - | 0 |
| openclaw-real | hard | 100 | - | 81 | 33 | - | 0 | - | 67 | - |

## 高判别力用例（BEAM 风格：跨智能体极差最大）

| 用例 | 难度 | 判别度 |
|---|---|---|
| upd-01-address | easy | 0 |
| upd-02-phone | easy | 0 |
| upd-03-editor | easy | 0 |
| upd-04-memory-store | hard | 0 |
| upd-05-retract | hard | 0 |
| reuse-01-install | medium | 0 |
| reuse-02-commit-rule | hard | 0 |
| reuse-03-weekly-template | medium | 0 |
| reuse-04-cache-clean | medium | 0 |
| tem-01-events | medium | 0 |

## 五分类裁决分布

### openclaw-real

| 维度 | correct | miss | confusion | improper_persistence | improper_reuse | 不可评 |
|---|---|---|---|---|---|---|
| 长期保持 | 37 | 1 | 0 | 1 | 0 | 0 |
| 记忆调用 | 9 | 3 | 0 | 0 | 0 | 0 |
| 动态更新 | 24 | 0 | 1 | 0 | 14 | 0 |
| 相近区分 | 6 | 4 | 14 | 0 | 0 | 0 |
| 边界识别 | 26 | 2 | 0 | 3 | 0 | 9 |
| 任务复用 | 4 | 8 | 0 | 0 | 0 | 0 |
| 时序推理 | 3 | 0 | 3 | 0 | 0 | 0 |
| 多 session 推理 | 0 | 3 | 0 | 0 | 0 | 0 |
| 因果推理 | 0 | 6 | 0 | 0 | 0 | 0 |

## 稳定性（各维度跨 run 标准差）

| 智能体 | 长期保持 | 记忆调用 | 动态更新 | 相近区分 | 边界识别 | 任务复用 | 时序推理 | 多 session 推理 | 因果推理 |
|---|---|---|---|---|---|---|---|---|---|
| openclaw-real | 0.072 | 0.000 | 0.063 | 0.204 | 0.055 | 0.118 | 0.408 | 0.000 | 0.000 |