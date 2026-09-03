"""membench — openKylin 智能体长期记忆自动化评测基准.

零第三方依赖（可选 PyYAML），Python >= 3.8。
"""

__version__ = "0.1.0"

DIMENSIONS = [
    "retention",                 # 长期保持
    "recall",                    # 记忆调用
    "dynamic_update",            # 动态更新
    "distractor_discrimination", # 相近区分
    "boundary_refusal",          # 边界识别（不应记忆/复用的信息）
    "task_reuse",                # 任务复用
    "temporal_reasoning",        # 时序推理（赛题加分维度，对标 LongMemEval）
    "multi_session_reasoning",   # 多 session 推理（对标 LongMemEval multi-session）
    "causal_reasoning",          # 因果/前置条件推理（对标 AMA-Bench Type B）
]

DIMENSION_LABELS = {
    "retention": "长期保持",
    "recall": "记忆调用",
    "dynamic_update": "动态更新",
    "distractor_discrimination": "相近区分",
    "boundary_refusal": "边界识别",
    "task_reuse": "任务复用",
    "temporal_reasoning": "时序推理",
    "multi_session_reasoning": "多 session 推理",
    "causal_reasoning": "因果推理",
}

# 五类裁决 + 不可评
VERDICT_CORRECT = "correct"                          # 正确记忆/正确拒绝
VERDICT_MISS = "miss"                                # 遗漏（该记的没记住/没用上）
VERDICT_CONFUSION = "confusion"                      # 混淆（记成干扰项/旧值）
VERDICT_IMPROPER_PERSISTENCE = "improper_persistence"  # 错误持久化（不该记却记了）
VERDICT_IMPROPER_REUSE = "improper_reuse"            # 错误复用（复用了过期/禁止的信息）
VERDICT_NOT_EVALUABLE = "not_evaluable"              # 证据不足，无法判定
