# 工作区协作规范（worktree 工作规范）

> 本文是**仓库级规范，随 clone 分发**，对所有人（含 AI agent 会话）生效。
> 各工作机器的本地布局快照放在仓库父目录的 `<仓库名>.worktrees/README.md`
> （不入库），换手时先读它。
> agent 入口速记见根目录 `AGENTS.md`；本文是完整版。

## 0. 心智模型

一个仓库，多个工作台：**worktree = 给一条分支开一个独立目录**。
目录之间互不干扰、可并行干活；分支、提交、stash 由所有工作台共享。
删除工作台不等于删除分支；分支历史永远在仓库里。

## 1. 目录布局（机器本地，不入库）

```
<仓库父目录>/
├── okylin-membench/            # 主检出 = master：稳定参照
└── okylin-membench.worktrees/  # 工作台根目录（命名固定：<仓库名>.worktrees）
    ├── README.md               # 本机状态快照（不入库，随状态更新）
    └── <分支名>/               # 一个工作台；目录名必须 = 分支名
```

- 工作台根目录必须与主检出**同级**，命名 `<仓库名>.worktrees/`。
- **禁止**放在 `/tmp`（重启即失，分支虽在但工作台目录会丢）。
- **禁止**放在主检出内部（会污染 master 的 status，本仓库曾为此打过排除补丁）。
- 该目录不属于 git 仓库，clone 不会得到它——所以**规范入库（本文），
  布局入快照（`<仓库名>.worktrees/README.md`）**，两者缺一不可。

## 2. 生命周期：开工与收工

```bash
cd <主检出>                                        # 固定在主检出里操作
git worktree list                                          # 先看全局
git worktree add ../okylin-membench.worktrees/<分支名> <分支名>   # 开工台
git worktree remove ../okylin-membench.worktrees/<分支名>         # 收工台（分支保留）
```

- **一条分支同一时间只能有一个工作台**（git 强制约束，报"already checked
  out"就是被占了，先 `git worktree list` 找占用者）。
- **收工三步**：status 清零 → 提交 → remove。不活跃的分支只保留分支，
  不占目录。
- 迁移工作台用 `git worktree move`，**不要用 shell mv**（会产生失效残留，
  本仓库的 okylin-membench-eval 事故即由此而来）。

## 3. 工作台纪律

1. **master 主检出保持干净**：只在主检出做合并、发布、审计，不开发。
   发现主检出有未提交内容 → 先按 §5 查归属，再处置。
2. **脏台不过夜**：收手（会话结束/换人）前 status 必须清零——要么提交，
   要么按 §5 留档，要么获授权丢弃。
3. **分支与工作台一一对应**：目录名 = 分支名，禁止一个目录挂多条分支。

## 4. 提交纪律

- 提交信息格式：`<type>: <中文摘要> (round N+x)`，
  type ∈ feat / fix / docs / chore / exp。轮次编号全局递增。
- **message 必须能被 `git show --stat` 单独验证**（DEVLOG N+17 教训，
  "message-vs-reality"规则）：声称产出 X，diff 里必须能看到 X 的痕迹。
- **未完成事项必须留档 `docs/DEVLOG.md`**（先例：00a95e4 收尾清点），
  让下一个接手者能从文档而不是考古中恢复上下文。
- master 只进"收尾验证过"的工作：feature 分支干活，收尾后并回主线。
- **禁止改写已声明完成的历史**（force-push / rebase 已收尾分支）。
  当前无远程，master 是唯一权威主线。

## 5. 换手协议（agent ↔ agent / 人 ↔ agent）

接手任何工作台前的**三件套**：

```bash
git status            # 脏不脏，有没有前人残留
git log --oneline -5  # 最新一轮在干什么
git worktree list     # 全局有哪些台、谁占着哪条分支
```

发现未提交内容时，按此顺序处置：

1. 读 `docs/DEVLOG.md` 最后一轮 + `git stash list`，判断归属与意图；
2. **有明确授权**（用户明说"丢弃"）→ 可丢弃，且丢弃前记录丢了什么；
3. **无授权 → 不动**，留档 DEVLOG 或询问。安全网次序：
   stash > DEVLOG 留档 > 直接丢弃（仅限明确授权后）。

## 6. 常见异常处置

| 症状 | 处置 |
|---|---|
| worktree 目录被手动删除 | `git worktree prune` 清注册；分支仍在，需要时重新 add |
| "branch already checked out" | `git worktree list` 找占用台：去那里干活，或先 remove |
| /tmp 里的工作台丢了 | 分支无恙，按 §2 add 回规范位置 |
| 主检出 status 出现陌生未提交内容 | 按 §5 处置，不擅自丢弃 |
| stash 里有"foreign WIP" | 那是安全网备份，清点确认前不清 |

## 7. 本机状态快照

当前机器有哪些工作台、哪些分支休眠、有没有待并入/待收尾的事项——
记在 `<仓库名>.worktrees/README.md`（不入库）。**换手时先读它**，
状态变化时随手更新它。
