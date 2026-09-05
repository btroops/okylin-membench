# 多 provider 可配置化：OpenAI / Anthropic 双格式（改造方案）

> 状态：**已批准，执行中**（round N+26）。分支 `multi-provider`（基于 master 7189e79 / N+25）。
> 本文是方案留档：为什么改、改哪三层、验收标准是什么。执行结果见 DEVLOG N+26。

## 一、背景与动机

用户决策：LLM 接入格式应**由用户自行配置**，OpenAI 格式与 Anthropic 格式并存，
而不是像现状那样"换一家端点就要动一层"。现状的兼容性短板（均已核实）：

1. **两份重复的 OpenAI-only HTTP 代码**：`membench/judge.py::_post` 与
   `membench/agents/openai_compat.py::_chat` 各写一份 urllib POST +
   Bearer 鉴权 + `choices[0].message.content` 解析；新增一种格式就要改两处。
2. **无 provider 抽象**：工厂按 `kind` if/elif 硬编码分发，智能体配置没有
   api/provider 字段，`--judge` 只有 `heuristic|openai` 两档。
3. **Anthropic 格式只存在于 OpenClaw 容器层**（compose 的 `ANTHROPIC_*` 透传 +
   容器内 `models.providers.anthropic.*` 配置），membench 自身零支持；
   反过来 compose 只透传 `OPENAI_API_KEY`、缺 `OPENAI_BASE_URL`，
   想接 OpenAI 兼容端点连配置面都不完整。

约束：零第三方依赖（urllib + pyyaml）；默认行为完全向后兼容（旧配置零改动可跑）。

## 二、三层设计

### 第 1 层：统一 LLM HTTP 适配（核心去重）

新模块 `membench/llmhttp.py`，单一入口：

```python
llmhttp.chat(base_url, api, model, messages, api_key="", temperature=0.0,
             timeout=120.0, opener=None, max_tokens=None) -> str
```

| | `api="openai"` | `api="anthropic"` |
|---|---|---|
| 端点 | `POST {base}/chat/completions`，base_url 含版本段（`…/v1`） | `POST {base}/v1/messages`，**base_url 不含版本段**，适配器统一补 `/v1/messages` |
| 鉴权 | `Authorization: Bearer`（key 空则不带） | `x-api-key` + `anthropic-version: 2023-06-01` + `Authorization: Bearer` **双发**（官方认 x-api-key，DeepSeek 等 anthropic 兼容网关认 Bearer） |
| system | messages 内 `role:"system"` | 顶层 `system` 字段（适配器拆出）；连续同角色消息合并（协议要求 user 开头且交替） |
| max_tokens | 不发送 | 必填，默认 1024，可配置 |
| 响应解析 | `choices[0].message.content` | `content[].type=="text"` 拼接 |

错误归一为 `LLMHTTPError`（含 HTTP 状态码 + 响应体摘要），网络/HTTP/JSON 异常
统一包装；回环代理绕过继续复用 `httputil.opener_for`（调用方传入 opener）。

`OpenAICompatAgent._chat` 与 `LLMJudge._post` 改为委托 `llmhttp.chat`，
两份重复代码收敛为一份。外层语义不变：agent 侧仍抛 `AgentError`；
judge 侧 JSON 正则提取、votes 众数、失败回退 fallback 全部保留。

### 第 2 层：配置面（默认向后兼容）

- 被测智能体 JSON 新增 `"api": "openai"|"anthropic"`（**默认 openai**，旧配置零改动）、
  可选 `"max_tokens"`；`api_key_env` 缺省值随 api 切换
  （`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`）。
- judge CLI：`--judge {heuristic,openai,anthropic}`（openai/anthropic 都是 LLM
  评分，仅 wire format 不同）；`--judge-base-url`/`--judge-key-env` 未显式给出时
  按格式取默认（openai：`https://api.openai.com/v1` + `OPENAI_API_KEY`；
  anthropic：`https://api.anthropic.com` + `ANTHROPIC_API_KEY`）。
- 新示例 `agents/anthropic-compat.example.json`；README 补 `api` 字段说明。

### 第 3 层：OpenClaw 双 provider 配方

- `docker/openclaw/docker-compose.yml`：gateway 与 cli 两组 env 补
  `OPENAI_BASE_URL`、`OPENAI_MODEL` 透传（`${VAR:-}` 空默认，不影响现状）。
- `docker/openclaw/.env.example`：补 `OPENAI_BASE_URL`/`OPENAI_MODEL` 注释项。
- `docs/OPENCLAW_REAL_INSTANCE.md`：运行步骤改为配方 A（anthropic，原样保留）
  / 配方 B（openai 格式）并列；openai 的 openclaw `api` 取值无法离线确证，
  文档如实标注"待容器内 `openclaw models list` 实测校验"，不臆造。
- 已知局限 #2（openai embedding key 缺失 → 语义检索退化）补解锁条件：
  设 `OPENAI_API_KEY`（端点需支持 `/v1/embeddings`）即恢复。

## 三、验收标准

1. 旧配置（无 `api` 字段）行为与改造前一致；
2. `"api":"anthropic"` 配置经本地 fake 端点全链路走通（工厂 → 适配器 → llmhttp）；
3. `--judge anthropic` 可用；`--judge openai` 行为不变；
4. 单测全绿（`python3 -m unittest discover tests`），零新依赖；
5. 文档/示例齐全，message 能被 `git show --stat` 验证。

## 四、明确不做

- 不动在途的 `n19-stage1` 分支（doctor --strict 等随其分支另行并入）；
- 不引入任何 LLM SDK；
- 不重跑 OpenClaw 稳定性基线——真把被测后端从 anthropic 切到 openai 时，
  按 DEVLOG 口径纪律另行三次重测并归档新数据。

## 五、涉众文件

新增 4：`membench/llmhttp.py`、`tests/test_llmhttp.py`、
`agents/anthropic-compat.example.json`、本文档；
修改 8：`membench/agents/openai_compat.py`、`membench/judge.py`、
`membench/agents/__init__.py`、`membench/cli.py`、
`docker/openclaw/docker-compose.yml`、`docker/openclaw/.env.example`、
`README.md`、`docs/OPENCLAW_REAL_INSTANCE.md`。
