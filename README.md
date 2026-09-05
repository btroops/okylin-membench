# membench — openKylin 智能体长期记忆自动化评测基准

面向 openKylin 生态（KylinBot / kylin-agent / OpenClaw / HermesAgent 或任意
OpenAI 兼容服务）的智能体**长期记忆能力**自动化评测工具。零第三方依赖
（仅需 `python3>=3.8` 与 `python3-yaml`），一条命令完成"跑剧本 → 采证据 →
自动评分 → 雷达图报告"。

> 协作/工作台规范（多人或多 agent 换手必读）：[AGENTS.md](AGENTS.md)
> 与 [docs/WORKFLOW.md](docs/WORKFLOW.md)。

## 核心范式

> **证据链驱动的记忆评测**：不只看最终回答，而是从「记忆状态演变 → 检索来源 → 行动产物」的完整证据链评分，
> 能区分"没记住 / 记住没用 / 记错 / 该忘未忘 / 不该记却记"五种失败模式——后两种在终态 QA 范式下完全不可见。
> 详见 [docs/EVIDENCE_CHAIN.md](docs/EVIDENCE_CHAIN.md)。

## 九维指标

| 维度 | 考察点 | 对标 |
|---|---|---|
| retention 长期保持 | 应保留的信息是否被稳定记住 | 赛题基础 |
| recall 记忆调用 | 后续交互中能否正确取用 | 赛题基础 |
| dynamic_update 动态更新 | 新信息能否覆盖旧信息（回答+记忆库双层） | 赛题基础 |
| distractor_discrimination 相近区分 | 相近信息能否分清（两只猫/双 IP/双地址） | 赛题基础 |
| boundary_refusal 边界识别 | 不该记的信息是否被拒绝（密码/验证码/临时数据，三重检查） | 赛题基础 |
| task_reuse 任务复用 | 历史方法/模板/命令能否迁移复用（行动产物 fs 探针） | 赛题基础 |
| temporal_reasoning 时序推理 | 事件排序/时间间隔推理 | LongMemEval (ICLR'25) |
| multi_session_reasoning 多 session 推理 | 跨 session 分散信息的组合/聚合 | LongMemEval multi-session |
| causal_reasoning 因果推理 | 基于已记住前置条件调整行动建议（"我不会 Python"→建议改用 Go） | AMA-Bench (2026) |

## 五分类裁决（自动评分的可解释单元）

`correct` 正确记忆 · `miss` 遗漏 · `confusion` 混淆（记成旧值/干扰项） ·
`improper_persistence` 错误持久化（不该记却记了） · `improper_reuse` 错误复用 ·
`not_evaluable` 证据不足（不计入均分）。

## 快速开始

```bash
# 仓库内直接运行
python3 -m membench.cli doctor          # 环境自检（openKylin 复现前先跑）
python3 -m membench.cli demo            # 三个内置智能体全流程演示
python3 -m membench.cli list            # 查看内置 24 个用例
python3 -m membench.cli validate        # 数据集静态校验
python3 -m membench.cli gen --variants 3  # 按模板批量生成用例（种子可复现）

# 指定智能体评测 3 次（看稳定性）
python3 -m membench.cli run --agent smart --runs 3 -o results/

# 批量对比：--agent 可重复，也可指向包含配置数组的 JSON 文件
membench run --agent agents/openai-compat.example.json \
             --agent agents/echo.agent.json -o results/
membench run --agent batch_agents.json -o results/   # 批量配置见下
membench report results/nomem results/naive results/smart
```

输出：

```
results/
├── <agent>/summary.json            # 六维得分 + 五分类分布 + 稳定性(std)
├── <agent>/runs/runNN/<case>.json  # 每用例证据：完整对话、记忆库dump、文件diff
├── comparison/report.html          # 自包含对比报告（雷达图/热力表/FAMA/bin）
├── comparison/evidence.html        # 逐用例证据查看器（裁决理由/对话/记忆演变）
```

## 接入你的智能体

三种方式（见 `agents/*.json` 示例）：

1. **内置参考智能体**：`{"kind": "builtin", "impl": "nomem|naive|smart"}`
2. **外部程序（stdio-JSONL 协议）**：`{"kind": "subproc", "cmd": ["python3", "your-agent.py"]}`
   协议见 `membench/agents/subproc.py` 注释与 `examples/echo-agent.py` 参考实现。
3. **LLM API（双格式可选）**：`{"kind": "openai_compat", "api": "openai|anthropic", "base_url": "...", "model": "...", "memory": {"strategy": "none|full_log|store|store_filter"}}`
   - `"api": "openai"`（缺省）：Chat Completions 格式，base_url 含版本段
     （vLLM/Ollama/OpenAI 兼容端点），key 缺省读 `OPENAI_API_KEY`；
   - `"api": "anthropic"`：Messages 格式，**base_url 不含版本段**
     （如 `https://api.anthropic.com`、DeepSeek 的 `https://api.deepseek.com/anthropic`），
     可选 `"max_tokens"`（默认 1024），key 缺省读 `ANTHROPIC_API_KEY`；
     示例见 [agents/anthropic-compat.example.json](agents/anthropic-compat.example.json)。
   HTTP 细节（system 拆分、消息合并、鉴权头）由 `membench/llmhttp.py` 统一消化。

   **换厂商 / 三处配置点 / 常见厂商 base_url 速查**：
   [docs/CONFIGURATION.md](docs/CONFIGURATION.md)。

## 数据集格式

每个用例 = 一段"记忆剧本"：多 session 对话 + 探针 + 期望。完整字段说明见
[docs/SCHEMA.md](docs/SCHEMA.md)，评测方案设计见
[docs/DESIGN.md](docs/DESIGN.md)。

```yaml
schema_version: 1
case_id: upd-01-address
dimension: dynamic_update          # 六维之一
sessions:
  - session_id: s1
    turns: ["我家在北京市海淀区中关村大街1号。"]
  - session_id: s2
    turns: ["我搬到上海市浦东新区世纪大道100号了。"]
probes:
  - probe_id: p1
    type: slot                     # choice/slot/free/fs/memory
    after_session: s2
    question: "我现在家在哪里？"
    expected:
      must_include: ["上海市浦东新区世纪大道100号"]
      must_not_include: ["北京市海淀区中关村大街1号"]
```

## 评分设计：确定性优先

- `choice` / `slot` / `fs` / `memory` 四类探针**完全确定性判定**，同一输入 100% 复现；
- `free` 探针默认启发式判定（离线可用），可选 LLM judge：`--judge openai`
  或 `--judge anthropic`（两种 wire format，端点、模型与 key 环境变量缺省随
  格式；强制 JSON 输出 + 多数投票 + 失败回退启发式；judge 调用/失败计数
  汇入 summary 并在报告可见；配置细节见
  [docs/CONFIGURATION.md](docs/CONFIGURATION.md)）；
- 白盒证据：`memory` 探针直接检查智能体导出的记忆库；文件系统快照 diff
  检查行动产物；`sensitive_patterns` 全量扫描敏感信息落盘/落库。

## 安装（openKylin / Debian 系）

```bash
bash packaging/build_deb.sh          # 构建 dist/membench_0.1.0-1_all.deb
sudo dpkg -i dist/membench_0.1.0-1_all.deb
membench demo
```

## 运行测试

```bash
python3 -m unittest discover -s tests   # 107 个单元/端到端测试（35 用例 + 21 模板 / 9 维度；含评分可信度实验、证据查看器、doctor 自检）
```

## 许可证

GPL-2.0-or-later
