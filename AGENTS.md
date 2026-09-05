# AGENTS.md — agent 须知

本仓库采用 worktree 多工作台协作。**开工前必读 [docs/WORKFLOW.md](docs/WORKFLOW.md)**
（随本仓库分发的完整协作规范），本机布局另见仓库父目录
`okylin-membench.worktrees/README.md`（不入库的状态快照）。

硬性规则速记：

1. 主检出（master）只做合并/审计，**不开发**；开发去工作台。
2. 工作台目录 = `<仓库父目录>/okylin-membench.worktrees/<分支名>`，
   目录名 = 分支名；**禁止放 /tmp 或主检出内部**。
3. 接手先跑 `git status` + `git log --oneline -5` + `git worktree list`；
   未提交内容**未查清归属不动、未获授权不丢**。
4. 收工前 status 清零；未完成事项写进 `docs/DEVLOG.md`。
5. 一条分支同时只能有一个工作台（git 强制）；迁移工作台用
   `git worktree move`，不用 shell mv。
