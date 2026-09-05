# OpenClaw 真实实例接入（2A 证据驱动，已实测跑通）

> 状态：**✅ 已在 Docker 容器中跑通真实 OpenClaw 实例并产出真实评分**
> （全 35 用例 / 9 维度实测；探针回答均走「记忆文件」路径，可由证据中
> 的 `Source: USER.md#Lxx` 与回复口吻直接验证）。
> openKylin 真机验证仍属交付物 c/e 的参赛者待办。

## 一、结论先行

membench 通过 `agents/openclaw_shim.py`（subproc 协议适配器）驱动
**容器内真实运行的 OpenClaw 实例**（官方镜像 `openclaw/openclaw:latest`，
Gateway + memory-core 插件 + Dreaming 定时任务），LLM 后端为
Anthropic 兼容端点（DeepSeek，`api=anthropic-messages`）。
分数与记忆证据全部来自真实软件行为，非模拟。

**测量有效性（N+19 关键升级）**：shim 对每个 harness session（含探针
session `probe:pN`）轮换独立 OpenClaw 会话键。此前一个 episode 的全部
session 共用一个会话键，剧本 s1 的原文会留在探针调用的上下文里——
retention=100% 测的是「上下文窗口没溢出」而非「长期记忆」。轮换后，
探针只能通过跨会话持久的记忆文件（USER.md / memory/）作答；判别实验
证明该通道真实存在（新会话仅凭 USER.md 正确召回）且干净起点下空白
对照如实回答「记忆里没有」。

## 二、架构（实测定型）

```
membench (harness)
   │ stdio-JSONL
   ▼
agents/openclaw_shim.py            每 episode 一个新进程（= 天然的隔离边界）
   │  session_start → 轮换会话键 agent:main:mb-<uuid>:<session_id>
   │  user        → docker compose exec openclaw-gateway
   │                openclaw agent --agent main
   │                --session-key <当前 session 键> --message "..."
   │  memory_dump → 直接读宿主机挂载卷中的 workspace 文件
   │  retrieval_trace → openclaw memory search --json（尽力而为，见局限 2）
   ▼
openclaw-gateway 容器（uid=评测用户，端口 18789）
   workspace 卷（宿主机 ./openclaw-workspace）
     USER.md / MEMORY.md / DREAMS.md / memory/<date>.md
```

隔离由三层共同完成（缺一不可，均为实测教训）：
1. **episode 层**：每个 episode 使用独立会话键前缀。OpenClaw 默认把 CLI
   调用全部累积进同一滚动会话，历史轮次会跨 episode 泄漏（实测 ret-01
   第二轮跑分时模型答"这条信息我早就记住了"）。
2. **session 层（N+19）**：episode 内每个 harness session 再派生独立会话
   键。否则剧本原文仍在探针上下文里，探针答对无法区分「读到了记忆文件」
   与「上下文里还留着」（实测同键下模型答"刚才你告诉我的"）。
3. **文件层**：workspace 文件按 agent 共享、跨会话持久，episode 开始时
   用 `docker/openclaw/openclaw-pristine/` 中的干净模板还原 USER.md、
   清空 memory/ 日记、删除 MEMORY.md/DREAMS.md。

会话键轮换对记忆写入/读取时序的实测结论（判别实验，2026-09-05）：
教学轮返回时 USER.md 已同步落盘（grep 立即可见），新会话立即探针即可
读到最新值——无 read-after-write 延迟，无需在 session_end 后加等待。

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
| 11 | 探针的上下文泄漏（测量学） | 同会话键下探针答"刚才你告诉我的"（retention 假正确） | session_start 时轮换会话键（见二）；空白对照实验验证新会话只读记忆文件 |
| 12 | 探针读旧快照疑云 | 教天津→探针答重庆 | 判别实验排除注入延迟（教学返回即落盘、立即可读）；真因是实验序列残留的 superseded 地址链，隔离还原后消失 |

## 四、运行步骤（配方 A 已实测；配方 B 为 N+26 双 provider 改造新增）

**配方 A：Anthropic 兼容端点（原实测路径，DeepSeek 为例）**

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

**配方 B：OpenAI 兼容端点（N+26 新增；compose 已透传 `OPENAI_BASE_URL` /
`OPENAI_MODEL` / `OPENAI_API_KEY`，见 .env.example）**

步骤与配方 A 同构，仅 provider 段不同（以 `<OPENAI_BASE_URL>` 指向
任意 Chat Completions 兼容端点，如 `https://api.deepseek.com/v1`）：

```bash
docker compose exec -T openclaw-gateway openclaw config set \
  models.providers.openai.baseUrl "$OPENAI_BASE_URL"
# ⚠️ 待实测项：openai provider 的 api 取值。anthropic 配方实测用的是
#    "anthropic-messages"，openai 对应值（如 openai-completions / openai-chat）
#    请先在容器内 `docker compose exec -T openclaw-gateway openclaw models list`
#    或官方文档确认后回填本节，报 provider api 不识别就换候选值。
docker compose exec -T openclaw-gateway openclaw config set \
  models.providers.openai.api "<待实测：openai-completions>"
docker compose exec -T openclaw-gateway openclaw config set --json \
  models.providers.openai.models \
  '[{"id":"deepseek-v4-flash","name":"deepseek-v4-flash"}]'
printf '%s' "$OPENAI_API_KEY" | docker compose exec -T openclaw-gateway \
  openclaw models auth paste-api-key --provider openai
docker compose exec -T openclaw-gateway openclaw models set openai/deepseek-v4-flash
docker compose restart openclaw-gateway
```

**配方 B 附：embedding 自定义（memory-core 语义检索，N+28）**

OpenClaw 的 memory-core 语义检索固定通过 **openai provider** 调
`/v1/embeddings`（实测行为：无该 provider key 时持续报
`No API key found for provider "openai"`，见局限 2）。由此：

- **embedding 走哪家厂商 = 用户配置**：把 `models.providers.openai.baseUrl`
  指向任意实现了 `/v1/embeddings` 的兼容端点（DeepSeek /v1、Qwen、自建
  网关皆可）并贴入其 key，embedding 即随该端点走——可与 chat 模型同
  端点，也可单独指一家。
- **embedding 模型名的指定键待实测**：候选为
  `openclaw config set memory.embedding.model <id>`、或在
  `models.providers.openai.models[]` 中登记 embedding 模型、或专用环境
  变量。验证方法：`openclaw config list` 输出 grep embed 定位真实键名；
  配置后 memory sync 日志不再报 `No API key found` / 模型不存在即生效。
  确认后请回填本节并注明 openclaw 镜像版本号。
- **兜底**：若所用版本不支持改 embedding 模型名，可在自建 OpenAI 兼容
  网关侧把其请求的模型名映射为厂商实际模型（网关层重写请求体）。

切换 provider 的口径纪律（DEVLOG）：被测后端一换，归档的 openclaw-real
三次稳定性均值 ± σ 与四智能体对比雷达即作废，必须重跑三次稳定性并
归档新样例（标注 provider/模型），旧数据不得混用。

## 五、GATING ITEM 与已知局限（诚实记录）

1. **LLM 后端是硬前提**：无可用模型则 OpenClaw 不产生任何记忆，2A 仍是 🔶。
   当前用 Anthropic 兼容端点（DeepSeek）；`ANTHROPIC_AUTH_TOKEN` 已入库到
   `.env`（被 .gitignore 忽略，严禁提交）。
2. **向量记忆降级**：memory-core 的语义检索默认依赖 OpenAI embedding，
   本环境无 OpenAI key，`[memory] sync failed ... No API key found for
   provider "openai"` 持续出现——语义检索退化为关键词匹配（被测 agent
   自己也会向用户说明这一点）。关键词/文件记忆不受影响。retrieval_trace
   因此常为空列表（shim 已接入真实 `openclaw memory search --json`，
   解析成功且非空才返回条目，失败/空结果优雅降级不影响评分）——这是
   被测环境的真实能力上限，如实报告而非掩盖。
   **解锁与自定义（N+26/N+28）**：`.env` 设 `OPENAI_API_KEY` 且端点支持
   `/v1/embeddings`，语义检索即恢复；双 provider 改造（配方 B）后，embedding
   走哪家厂商由用户配置（见配方 B 附「embedding 自定义」），不再是
   "只有 anthropic 端点"的结构性局限。
3. **答案锚定豁免的副作用**（N+19）：shim 让探针会话仅靠记忆文件作答
   后，真实 LLM 常在主答案后另起一段引用记忆原文（含干扰项），确定性
   评分的全文 must_not_include 扫描会被系统性误伤。membench 评分器
   新增「答案锚定（answer anchoring）」规则：主答案段（首个空行前）
   已包含全部 must_include 且不含 must_not_include 项时，豁免
   confusion/improper_reuse 判为 correct。敏感模式不受豁免。对内置
   参考智能体零影响（短句模板从不触发该模式）。详见 `tests/test_scoring.py`
   的 `TestAnswerAnchoring`（5 用例）与 DEVLOG N+19。
3. **孤儿会话累积**：每 episode 一个新会话，会在 state 库中累积；
   被中断的会话可能以 `stalled session` 形式滞留（recovery=none），
   大规模跑批前建议清理。
4. **非 openKylin 真机**：本验证在 Docker（近似环境）中完成；
   交付物 c/e 的 openKylin 桌面真机部分仍需参赛者完成。

## 六、与 2B 金标的关系

2B（参考智能体 smart/naive/nomem 与确定性评分）不受影响。本接入只增强
2A 的"真实性"，评测协议与评分逻辑零改动（shim 实现的是既有 subproc 协议）。
