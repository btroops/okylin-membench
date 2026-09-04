# N+15 踩坑档案

> 与 `DEVLOG.md` 的区别：
> - `DEVLOG.md`：高层决策摘要（每轮一段），供答辩/读者；
> - `ARCHIVE_N+15.md`：本轮**所有踩坑与错误**，按时间序，给未来的我/读者一份"避坑指南"。

## 踩坑 1：选了错误的 worktree 目录位置

- **发生**：用户给指令"使用 git worktree 进行开发"，我把 worktree 目录放在 `/home/btroops/membench-eval-wt/`（主目录外）
- **症状**：用户 `cd okylin-membench && git checkout membench-evaluator` 报"已检出"
- **修正**：用 `git worktree add .worktrees/membench-evaluator -b membench-evaluator` 把 worktree 放在仓内子目录；现在主仓仍可直接 checkout 该分支
- **教训**：worktree 默认应放仓内子目录（如 `.worktrees/xxx`），而非用户的 `~` 根目录

## 踩坑 2：分支基线选错（最严重）

- **发生**：从 `evidence-driven` 分支独有的 commit `694b5b8`（"ignore tests/labels"）起 membench-evaluator
- **症状**：用户提示"你的工作和 evidence-driven 没关系，你是承接 master 分支的"
- **根因**：`694b5b8` 实际是 evidence-driven 分支独有（master 上不存在），我误以为是"自己之前提交的"——commit message 看不出分支归属
- **修正**：`git reset --hard d5fc143`（master HEAD）→ 重新应用 N+15 代码改动
- **教训**：**任何"我的工作"必须 `git log --graph --oneline --all` 验证拓扑，而不是凭 commit message 自报家门**

## 踩坑 3：用 `git branch -D` 强删带 N+15 提交的分支

- **发生**：worktree 整改时，执行 `git branch -D membench-evaluator`，以为 worktree 已经分离就安全了
- **症状**：分支删除时，e4d5b17 + 6d89783 两个 commit 一起丢失（reflog 中可查，但不在分支上）
- **修正**：在 worktree 上重新应用 N+15 代码（5 个 Python 脚本连续运行）→ 新 commit 在 master 基线正确分叉
- **教训**：**`git branch -D` 是破坏性操作**；删除分支前应 `git reflog | grep <sha>` 确认是否还有保留价值，或 `git checkout <sha> && git branch new-branch-name` 抢救

## 踩坑 4：重复造轮——另一 agent 已做 N+15a 关系感知

- **发生**：调查时发现 `evidence-driven` 上已有 `9c864fb docs: evidence-driven narrative + relation-aware related work (N+15a)`，明确做了"关系感知"
- **现状**：
  - 对方是 **docs only**（EVIDENCE_CHAIN.md + RELATED_WORK.md 改写 + 样例重生成）
  - 我做的是 **代码 + 用例**（probe.relation 字段 + 3 个手写 YAML + runner/aggregate/report 接入）
  - **结论互补**——我的代码改动是对对方文档框架的工程落地
- **教训**：**开始工作前先 `git log --all --oneline | head -30` 看近期有没有人在做同类工作**——尤其是在多 agent 并行场景下

## 踩坑 5（次要）：用户给的论文清单忘记迭代记录

- **发生**：用户把 ATM-Bench / SubtleMemory / PAST-Bench / 等十几个工作发给我，我读完后只更新了 RESEARCH.md，没把"哪些处理了 / 哪些挂账"单独记档
- **修正**：本轮补 `docs/ARCHIVE_N+15.md`（过程档案）+ `DEVLOG.md` 段落（决策摘要）
- **教训**：**用户给外部资料 → 立即建档"读/挂账矩阵"**——这是研发诚信的基础

## 教训汇总（轮次 N+15 自我评估）

| 踩坑 | 严重性 | 是否修复 | 防再发生措施 |
|---|---|---|---|
| worktree 目录放错位置 | 低 | ✅ 移到 `.worktrees/` | 默认 `git worktree add .worktrees/xxx` |
| 分支基线选错 | 高 | ✅ `git reset --hard master` | `git log --graph --oneline --all` 必做 |
| 强删带 commit 的分支 | 中 | ✅ 重新应用 | 删分支前 `git checkout <sha>` 抢救 |
| 重复造轮 | 中 | ✅ 互补非重复 | 开工前 `git log --all` 扫一遍 |
| 资料未即时归档 | 低 | ✅ ARCHIVE | 收到外部资料立即建档 |

## 流程改进（给未来轮次）

1. **开工流程**：
   - `git fetch --all` → `git log --graph --oneline --all -n 20` 看最近工作
   - 检查 `git worktree list` 决定从主仓还是 worktree 起步
   - 选定 base 后 `git log master..<start-point>` 确认"相对 master 我多加了什么"
2. **worktree 选址**：
   - 默认 `.worktrees/<branch>`（仓内子目录）
   - 避开 `~` 根目录与 `/tmp`（另一 agent 容易踩）
3. **删分支前**：
   - `git reflog | grep <branch>` 看是否有孤立 commit
   - 抢救式：`git checkout <last-sha> && git branch <new-name> <last-sha>`
4. **收到外部资料**：
   - 立即在 ARCHIVE 建"读/挂账矩阵"
   - 同步在 RESEARCH.md 写"按 论文内容 → membench 借鉴/局限"双列表
5. **多 agent 协调**：
   - `git log --all --oneline` 每轮开头扫一遍
   - 自己的分支名要有专属性（如 `membench-evaluator` vs `evidence-driven`）便于分辨

## 用户给的论文清单（最终状态表）

| 名称 | 处理状态 | membench 借鉴 |
|---|---|---|
| AMA-Bench (ICML'26) | 已读（之前轮次） | 4 任务类型已对照 |
| ATM-Bench (剑桥) | **本轮已读** | 加入 RESEARCH 系列七；多模态盲点已承认 |
| **SubtleMemory** | **本轮重点吸收** | probe.relation 字段 + 3 用例 + 报告表 + 实测复现论文发现 |
| Mem2ActBench (ACL'26) | 挂账下轮 | 主动工具调用——新维度候选 |
| MemoryAgentBench (ICLR'26) | 已读 | 4 能力对照 |
| LongMemEval (ICLR'25) | 已读 | 5 能力对照 |
| AgentMemBench | 挂账下轮 | "开/关保留"评估范式 |
| PAST-Bench (Princeton) | **本轮已读** | 4 能力自进化 + 配对实验设计 |
| RHELM (微软) | 挂账 | 10 虚拟角色生成可用 |
| Memora | 已读（FAMA 已实现） | 双清单判据 |
| MemEye | 挂账 | 多模态路线 |
| WorldMemArena | 挂账 | 动作-世界交互 |
| IFCMemoryBench | **降级** | BIM 域不在赛题 |
| agent-memory-bench | 已参考 | 7 标准任务 |
| AgentEval.Memory | 已参考 | HTML 报告 |
| MemLens | 挂账 | 256K 长上下文 |
| AgentTrove | 挂账 | 169 万行数据扩规模 |
