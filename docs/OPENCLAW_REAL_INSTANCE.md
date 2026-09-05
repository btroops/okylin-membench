# OpenClaw 真实实例接入（2A 证据驱动，已实测跑通）

> 状态：**✅ 已在 Docker 容器中跑通真实 OpenClaw 实例并产出真实评分**
> （ret-01 / ret-02 双用例 retention=100，证据含真实 transcript / memory_dump /
> memory_evolution，且经污染检查确认跨用例隔离生效）。
> openKylin 真机验证仍属交付物 c/e 的参赛者待办。

## 一、结论先行

membench 通过 `agents/openclaw_shim.py`（subproc 协议适配器）驱动
**容器内真实运行的 OpenClaw 实例**（官方镜像 `openclaw/openclaw:latest`，
Gateway + memory-core 插件 + Dreaming 定时任务），LLM 后端为
Anthropic 兼容端点（DeepSeek，`api=anthropic-messages`）。
分数与记忆证据全部来自真实软件行为，非模拟。

## 二、架构（实测定型）

```
membench (harness)
   │ stdio-JSONL
   ▼
agents/openclaw_shim.py            每 episode 一个新进程（= 天然的隔离边界）
   │  user        → docker compose exec openclaw-gateway
   │                openclaw agent --agent main
   │                --session-key agent:main:mb-<per-episode-uuid>
   │                --message "..."
   │  memory_dump → 直接读宿主机挂载卷中的 workspace 文件
   ▼
openclaw-gateway 容器（uid=评测用户，端口 18789）
   workspace 卷（宿主机 ./openclaw-workspace）
     USER.md / MEMORY.md / DREAMS.md / memory/<date>.md
```

隔离由两层共同完成（缺一不可，均为实测教训）：
1. **会话层**：每个 episode 使用独立 `--session-key`。OpenClaw 默认把 CLI
   调用全部累积进同一滚动会话，历史轮次会跨 episode 泄漏（实测 ret-01
   第二轮跑分时模型答"这条信息我早就记住了"）。
2. **文件层**：workspace 文件按 agent 共享、跨会话持久，episode 开始时
   用 `docker/openclaw/openclaw-pristine/` 中的干净模板还原 USER.md、
   清空 memory/ 日记、删除 MEMORY.md/DREAMS.md。

## 三、实测过程中排掉的全部障碍（均有对应报错留痕）

| # | 障碍 | 报错/现象 | 处置 |
|---|---|---|---|
| 1 | daemon 权限 | `permission denied ... docker.sock` | 用户加入 docker 组 |
| 2 | ghcr.io 不可达 | `TLS handshake timeout`（daemon 侧） | 给 daemon 配代理 drop-in；镜像源改 Docker Hub（3.32GB 实测拉取成功） |
| 3 | bind-mount 属主 | `EACCES: mkdir '/home/node/.openclaw/state'` | 挂载目录 chown 至容器运行 uid |
| 4 | 镜像未初始化 | `Missing config. Run openclaw setup` | `config set gateway.mode=local` 等 |
| 5 | provider/模型未注册 | `Unknown model: anthropic/deepseek-v4-flash ... no matching models.providers[].models[]` | `models.providers.anthropic.{baseUrl, api=anthropic-messages, models[]}` |
| 6 | provider 无鉴权 | `Auth readiness could not be confirmed` | `models auth paste-api-key --provider anthropic` |
| 7 | 自定义 uid 无 HOME | `EACCES: mkdir '/.openclaw/state'` | compose 显式 `HOME=/home/node` |
| 8 | 缓存目录不可写 | `Unable to create fallback OpenClaw temp dir: /home/node/.cache/openclaw-1001` | bind mount 属主受控的 `./openclaw-cache`（tmpfs 在 restart 后属主不确定，已弃用） |
| 9 | 跨用例记忆污染（方法论） | ret-02 档案出现 ret-01 的「小明/vim」 | 会话层+文件层双重隔离（见上） |
| 10 | 交互工具阻塞 | `blocked_tool_call activeTool=ask_user`（300s 超时） | `tools.deny=["ask_user"]`；无人值守下模型只能以文字收尾 |

## 四、运行步骤（全部实测）

```bash
# 0) 前置：docker daemon 可用；评测用户对 docker socket 有访问权
cd docker/openclaw
cp .env.example .env   # 填 LLM 后端（见五）与 OPENCLAW_UID/GID=id -u/id -g

# 1) 启动网关（首次拉镜像约 3.3GB）
docker compose up -d openclaw-gateway

# 2) 首次初始化（仅需一次）
docker compose run --rm --no-deps --entrypoint node openclaw-gateway \
  dist/index.js config set --batch-json \
  '[{"path":"gateway.mode","value":"local"},{"path":"gateway.bind","value":"lan"}]'
docker compose exec -T openclaw-gateway openclaw config set \
  models.providers.anthropic.baseUrl "https://api.deepseek.com/anthropic"
docker compose exec -T openclaw-gateway openclaw config set \
  models.providers.anthropic.api "anthropic-messages"
docker compose exec -T openclaw-gateway openclaw config set --json \
  models.providers.anthropic.models \
  '[{"id":"deepseek-v4-flash","name":"deepseek-v4-flash"}]'
printf '%s' "$ANTHROPIC_AUTH_TOKEN" | docker compose exec -T openclaw-gateway \
  openclaw models auth paste-api-key --provider anthropic
docker compose exec -T openclaw-gateway openclaw config set --json \
  tools.deny '["ask_user"]'
docker compose exec -T openclaw-gateway openclaw models set anthropic/deepseek-v4-flash
docker compose restart openclaw-gateway

# 3) 评测
cd ../..
python3 -m membench.cli run --agent agents/openclaw.agent.json \
  --cases cases --filter ret-01,ret-02 -o results/openclaw
python3 -m membench.cli report results/openclaw
```

## 五、GATING ITEM 与已知局限（诚实记录）

1. **LLM 后端是硬前提**：无可用模型则 OpenClaw 不产生任何记忆，2A 仍是 🔶。
   当前用 Anthropic 兼容端点（DeepSeek）；`ANTHROPIC_AUTH_TOKEN` 已入库到
   `.env`（被 .gitignore 忽略，严禁提交）。
2. **向量记忆降级**：memory-core 的语义检索默认依赖 OpenAI embedding，
   本环境无 OpenAI key，`[memory] sync failed ... No API key found for
   provider "openai"` 持续出现——语义检索退化为关键词匹配（被测 agent
   自己也会向用户说明这一点）。关键词/文件记忆不受影响。
3. **孤儿会话累积**：每 episode 一个新会话，会在 state 库中累积；
   被中断的会话可能以 `stalled session` 形式滞留（recovery=none），
   大规模跑批前建议清理。
4. **非 openKylin 真机**：本验证在 Docker（近似环境）中完成；
   交付物 c/e 的 openKylin 桌面真机部分仍需参赛者完成。

## 六、与 2B 金标的关系

2B（参考智能体 smart/naive/nomem 与确定性评分）不受影响。本接入只增强
2A 的"真实性"，评测协议与评分逻辑零改动（shim 实现的是既有 subproc 协议）。
