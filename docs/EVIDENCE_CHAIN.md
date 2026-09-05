# 证据链驱动的智能体长期记忆评测（Evidence-Driven Agent Memory Evaluation）

> 本文档是方案的核心叙事：不是"我们做了九个维度"，而是一个范式主张。
> 所有表格的依据见 RESEARCH.md（31 项精读）；所有数字可由本仓库命令复现。

## 一、范式主张（一句话）

> **记忆质量应当从"记忆状态 → 检索 → 决策 → 行动"的证据链来评测，而不是只看最终回答。**

现有长期记忆 benchmark（LoCoMo / LongMemEval / BEAM / Memora / AMA-Bench）
的评测对象是最终答案：Question → Answer → LLM Judge。这条路径只能告诉
你"答对没有"，无法区分失败发生在哪一环。

## 二、三层证据链架构

```
                ┌─────────────────────────┐
                │    Task / Scenario       │  剧本：多 session 对话 + 冲突/
                │  （记忆剧本+探针+期望）    │  干扰/敏感/生命周期声明
                └───────────┬─────────────┘
                            ▼
                ┌─────────────────────────┐
                │    Agent Execution       │  可插拔智能体（内置/stdio JSONL/
                │                         │  OpenAI 兼容/openKylin 生态）
                └───────────┬─────────────┘
                ┌───────────┼───────────────┬───────────────┐
                ▼           ▼               ▼               ▼
         ┌───────────┐ ┌───────────┐  ┌───────────┐  ┌───────────┐
         │ 对话证据   │ │ 记忆状态   │  │ 检索证据    │  │ 文件/行动  │
         │ transcript│ │ 演变轨迹   │  │ retrieval │  │ 产物快照   │
         │           │ │ added/−   │  │ _trace     │  │ fs diff   │
         └─────┬─────┘ └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
               └─────────────┴──────┬──────┴──────────────┘
                                    ▼
                        ┌──────────────────────┐
                        │ Evidence-based       │  五分类裁决 + FAMA +
                        │ Evaluator            │  定位率 + staleness +
                        │（确定性优先）         │  判别力排名
                        └──────────┬───────────┘
             ┌──────────┬──────────┼──────────┬──────────┐
             ▼          ▼          ▼          ▼          ▼
          Recall     Update      Refusal    Reuse     Retrieval
          (ret/rec)  (upd/dis)   (bnd/noise)(reuse/cau)(localization)
```

与传统的 `Question → Answer → LLM Judge` 是两个范式：我们把**内部状态
（记忆库快照、逐 session diff）、检索过程（哪个 session 的记忆被取用）、
外部产物（文件系统变更）** 全部变成可验证证据。

## 三、证据链如何区分五种失败模式（核心价值）

终态 QA 无法区分的五种失败，在证据链上各有独立指纹：

| 失败模式 | 终态 QA 所见 | 证据链指纹（可自动判定） | 对应指标 |
|---|---|---|---|
| **没记住**（写失败） | 答错/不知道 | 演变轨迹全程 `+0`：记忆库从未出现该事实 | memory_evolution |
| **记住但没用**（检索失败） | 答错 | 演变轨迹有写入，但 `retrieval_trace` 为空或来源错误 session | retrieval_localization |
| **记错/记旧**（混淆） | 答错 | 回复命中 `must_not_include`（旧值/干扰值） | verdict=confusion |
| **该忘未忘**（遗忘失败） | *终态可能答对* | 失效值仍在记忆库（lifecycle 边界扫描发现） | staleness_scan → improper_reuse |
| **不该记却记了**（边界失败） | *终态可能正常* | 敏感串出现在记忆库/新增文件（终态 QA 完全不可见） | sensitive_scan + memory probe |

**后两种失败在终态 QA 范式下不可见**——这是本方案存在理由的最强论据：
一个把用户密码存进长期记忆的智能体，答题可以是满分的。

## 四、评分可信度（实验数据，非口号）

实验：185 条探针裁决 × 独立盲评器（按规则文本另行实现，不经
scoring.py）→ 分歧仲裁 → 指标。数据与脚本在 `tests/labels/`。

- **Raw agreement 83.8%，Cohen's κ=0.75**（六分类）
- 30 条分歧仲裁：21 条为盲评器权限制约（无记忆库/文件系统访问权）、
  9 条为类间语义近似；**1 条真实改进点已转化为引擎修复**（any_include
  未命中时回退查失效值定类，回归测试锁定）
- **跨运行方差 = 0**（确定性引擎，测试锁定 `test_stability_deterministic`）
- 对照：AMA-Bench 的 LLM judge 人机一致率 92.7%（其报告值）；Memora
  三 judge 投票 88.3%。我们的确定性路径在参考智能体上达到仲裁后
  100% 且零方差；LLM judge 仅作为 free 探针的可选兜底（带自检接口）
- **诚实口径**：第二标注者是独立实现的规则匹配器而非真人；参考智能体
  行为确定性，真实 LLM 上需 `--judge openai` 联测复做

## 五、规模化（实验数据）

```
membench gen --variants 15 --seed 2026
→ 315 用例（9 维度全覆盖），validate 全过，生成 <1s
→ 三智能体区分度保持：smart 91.5 / naive 32.3 / nomem 17.5

membench gen --variants 95 --seed 2026   # BEAM 同级规模实测
→ 1995 用例（≈BEAM 2000 题），生成+校验 3.2s
→ 三智能体 5985 次评测 2.3s，区分度保持：91.2 / 32.5 / 17.5
```

扩展公式：`21 模板 × variants × 种子`，难度由干扰项最小对/链长/session
距离三个旋钮参数化（RULER 式），同种子输出逐字节一致（测试锁定）。
BEAM 用双人工标注 2000 题；我们用"模板+期望同源计算"达到零标注成本
的按需扩展——**题量不再是瓶颈，诚实地说瓶颈在人工校验深度**
（见 RELATED_WORK.md 差距清单），人工标注应优先投向盲评载荷
（tests/labels/blind_payload.json，185 条现成待标）。

## 六、与六项开源工作的逐项 gap analysis（论文级）

> 完整引用关系见 RESEARCH.md；本表只回答三件事：**它们覆盖什么、
> 我们新增什么、我们不能声称原创什么。**

| 能力 | LoCoMo | LongMemEval | BEAM | Memora | AMA-Bench | MemGym | **membench** | 我们是否原创 |
|---|---|---|---|---|---|---|---|---|
| 跨 session 记忆 QA | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ 非原创（继承） |
| 拒答/abstention | ✅ 24.9% | ✅ _abs | ✅ | △ | ❌ | ❌ | ✅ any_include | ❌ 非原创（继承+工程化） |
| 选择性遗忘评测 | ❌ | △ knowledge-update | ✅ | ✅ FAMA | ✅ StateUpdate | ❌ | ✅ lifecycle+扫描 | △ 语义继承，**扫描机制原创** |
| 时序/多跳/因果 | △ temporal | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ 非原创（继承） |
| **记忆状态过程评测**（演变轨迹） | ❌ | ❌ | ❌ | ❌ | ❌ | △ condensation 记录但非评测 | ✅ | ✅ **原创**（可对比 MemGym 的记录侧） |
| **检索证据定位率** | ❌ | ✅ session-level recall | ❌ | ❌ | ❌ | ❌ | ✅ | △ 继承 LongMemEval 思想，扩展到智能体协议 |
| **文件/行动产物证据** | ❌ | ❌ | ❌ | ❌ | ❌ | △ 轨迹 | ✅ fs 探针 | ✅ **原创** |
| **五分类失败模式裁决** | ❌ 对/错 | ❌ | ❌ | △ FAMA 惩罚项 | ❌ | ❌ | ✅ 五类+理由引用 | ✅ **原创**（FAMA 公式已引用归属） |
| 记忆卫生（去重/噪声） | ❌ | ❌ | ❌ | ❌ | △ Abstraction | ❌ | ✅ memory_max_count/noise | ✅ **原创** |
| 智能体可插拔（非纯 LLM） | ❌ | ❌ | ❌ | ❌ | △ agentic | ✅ gym 接入 | ✅ 三通道 | △ 与 MemGym 同向 |
| 确定性优先评分 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ MemRM | ✅ 4/5 探针零 LLM | ✅ **立场原创**（IFEval 已引用归属） |
| OS 集成（.deb/doctor） | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ 工程原创（AIOS/OpenClaw 引用归属） |

**可以声称原创的六项**：①记忆状态演变轨迹作为评测对象；②文件/行动
产物证据通道；③五分类失败模式裁决（含理由引用）；④记忆卫生探针；
⑤"该忘未忘"的过程级 staleness 扫描；⑥确定性优先的评分立场在记忆
评测上的系统化落地。

**不能声称原创的**：跨 session QA、拒答、时序/多跳/因果、FAMA 公式、
session 级检索定位思想、VT 链式更新——全部已在 RESEARCH.md 标注出处。

## 七、四层引用骨架（答辩 PPT 的引用页）

1. **Benchmark foundation**：LoCoMo → LongMemEval → MemoryAgentBench
   ——"长期记忆评测必须跨 session、含拒答与选择性遗忘"
2. **Memory mechanism**：MemGPT → Mem0 → A-MEM → Zep/Graphiti
   ——"真实记忆系统本身是 add/update/delete/evolve，不是 KV cache"
   （演变轨迹的 added/removed 正对应 Mem0 的 ADD/DELETE）
3. **Agentic benchmark**：BEAM → AMA-Bench → MemGym
   ——"评测正从 QA 走向轨迹、状态更新、因果行动与记忆隔离打分"
4. **OS / system integration**：AIOS + Letta MemFS + OpenClaw
   ——"为什么这套方案天然适配 openKylin：生态智能体的记忆就是磁盘
   文件，fs 证据通道无需侵入即可直读"

## 八、openKylin 落地（为什么不是纯 Python benchmark）

- 生态智能体（OpenClaw 等官方文档核实）记忆 = 工作区 Markdown 文件
  → 我们的文件快照通道**无需侵入**即可捕获其记忆写入，~50 行协议
  shim 即可接入白盒评测；
- `.deb` 分发 + `membench doctor` 8 项环境自检 + 零第三方依赖
  （python3+python3-yaml 系统预装）；
- Letta MemFS / GCC（SWE-Bench 80%+）证明"文件化记忆 + commit/branch"
  是 2026 收敛形态——我们的证据设计押中的正是这个形态。
