# 配置指南：LLM 端点接入与厂商切换

> 面向接入 membench 的开发者。核心原则：**换厂商只改配置，不改代码**。
> 系统里有三个相互独立的 LLM 配置点，先分清你要换的是哪一个：

| # | 你想换谁 | 配置在哪 | 密钥放哪 |
|---|---|---|---|
| 1 | 被测智能体（LLM 型） | `agents/*.json` | shell 环境变量（配置里 `api_key_env` 指路） |
| 2 | judge 评分端 | `--judge*` 命令行参数 | shell 环境变量 |
| 3 | OpenClaw 容器（真实实例） | `docker/openclaw/.env` + 容器内 config 命令 | `.env` 文件（已被 .gitignore） |

注意：membench 本体**不读取任何 `.env` 文件**（零第三方依赖，无 dotenv）；
`.env` 只存在于 OpenClaw 容器那层（docker compose 约定）。

## 0. 两种 wire format 的约定

HTTP 细节（鉴权头、system 拆分、消息合并、max_tokens）由
`membench/llmhttp.py` 统一消化，配置面只做一个选择：

| 格式 | `api` 取值 | base_url 约定 | 举例 |
|---|---|---|---|
| Chat Completions | `"openai"`（缺省） | **含版本段** `/v1` | `https://api.openai.com/v1`、`https://api.deepseek.com/v1`、Ollama `http://127.0.0.1:11434/v1` |
| Messages | `"anthropic"` | **不含版本段**（适配器自动补 `/v1/messages`） | `https://api.anthropic.com`、`https://api.deepseek.com/anthropic` |

绝大多数厂商两种格式至少提供一种；Anthropic 官方走 anthropic 格式，
国内厂商一般提供 OpenAI 兼容端点，DeepSeek 两种都有。

## 1. 被测智能体：改 `agents/*.json`

新建一个配置（示例：DeepSeek OpenAI 兼容端点）：

```json
{
  "name": "deepseek-chat",
  "kind": "openai_compat",
  "api": "openai",
  "base_url": "https://api.deepseek.com/v1",
  "model": "deepseek-chat",
  "api_key_env": "DEEPSEEK_API_KEY",
  "memory": {"strategy": "store"}
}
```

anthropic 格式（示例：Anthropic 官方，key 变量缺省即 `ANTHROPIC_API_KEY`）：

```json
{
  "name": "claude",
  "kind": "openai_compat",
  "api": "anthropic",
  "base_url": "https://api.anthropic.com",
  "model": "claude-sonnet-4-5",
  "memory": {"strategy": "store"}
}
```

字段速查：

| 字段 | 说明 |
|---|---|
| `api` | `openai`（缺省）或 `anthropic`，见上表 |
| `base_url` | 约定见上表（openai 带 `/v1`，anthropic 不带） |
| `model` | 厂商模型名 |
| `api_key_env` | 从哪个环境变量读密钥；缺省 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` |
| `max_tokens` | 仅 anthropic 需要，缺省 1024 |
| `memory` | `{"strategy": "none\|full_log\|store\|store_filter", "top_k": 5}` |

运行：

```bash
export DEEPSEEK_API_KEY=sk-xxx          # 密钥只进环境变量，不进仓库
python3 -m membench.cli run --agent agents/my-agent.json -o results/
```

membench 不读 `.env`。若想统一用 `.env` 文件管理密钥，运行前手动加载：
`set -a; source <你的.env>; set +a`。

## 2. judge 评分端：命令行参数

`free` 探针默认离线启发式判定；接 LLM judge：

```bash
export ANTHROPIC_API_KEY=sk-ant-xxx
python3 -m membench.cli run --agent ... \
  --judge anthropic --judge-model claude-sonnet-4-5
# --judge openai 则缺省端点 https://api.openai.com/v1、key 读 OPENAI_API_KEY
```

`--judge-base-url` / `--judge-key-env` 未显式给出时随格式取默认。
judge 强制 JSON 输出 + votes 多数投票 + 失败自动回退启发式，
judge 故障不会中断评测。

## 3. OpenClaw 容器：`docker/openclaw/.env`

唯一使用 `.env` 的配置点（compose 自动读取；**文件含密钥，已被 .gitignore，
严禁提交**）。按所用格式填一组：

```bash
# anthropic 格式（配方 A，已实测）
ANTHROPIC_AUTH_TOKEN=sk-xxx
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
ANTHROPIC_MODEL=deepseek-v4-flash

# 或 openai 格式（配方 B）
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-v4-flash
```

`.env` 只是密钥与地址的**注入通道**——容器内 openclaw 自身的 provider 注册
（`config set` / `models auth` / `models set` + restart）必须按
[docs/OPENCLAW_REAL_INSTANCE.md](OPENCLAW_REAL_INSTANCE.md) 的配方 A / 配方 B
执行，只改 `.env` 不会生效。

附带效果：设了 `OPENAI_API_KEY` 且端点支持 `/v1/embeddings` 时，
memory-core 的语义检索恢复（否则退化为关键词匹配，见该文档局限 #2）。

## 4. 常见厂商速查

| 厂商/服务 | `api` | base_url | 备注 |
|---|---|---|---|
| OpenAI 官方 | openai | `https://api.openai.com/v1` | |
| Anthropic 官方 | anthropic | `https://api.anthropic.com` | |
| DeepSeek | openai | `https://api.deepseek.com/v1` | model 如 `deepseek-chat` |
| DeepSeek（anthropic 兼容） | anthropic | `https://api.deepseek.com/anthropic` | 配方 A 实测路径 |
| Moonshot Kimi | openai | `https://api.moonshot.cn/v1` | |
| 阿里 Qwen（DashScope 兼容模式） | openai | `https://dashscope.aliyuncs.com/compatible-mode/v1` | |
| 智谱 GLM | openai | `https://open.bigmodel.cn/api/paas/v4` | |
| Ollama 本地 | openai | `http://127.0.0.1:11434/v1` | 无需 key |
| vLLM 自建 | openai | `http://<host>:8000/v1` | |

⚠️ 诚实标注：本仓库实测过的路径只有 DeepSeek anthropic 兼容端点
（配方 A）与 Ollama 式本地端点（单测 fake 端点同构验证）；其余为厂商公开
文档值，以厂商当日文档为准，失效欢迎提 PR。

## 5. 口径纪律（换被测后端必读）

被测智能体的 LLM 一换，该智能体此前的跑分即失效：三次稳定性均值 ± σ
需重测、报告重新生成并在文档标注 provider/模型，**新旧数据不得混用对比**
（详见 docs/DEVLOG.md「口径纪律」）。

## 6. 密钥安全

- 任何密钥不入库：`docker/openclaw/.env` 已被 .gitignore；shell 里的
  export 写进你自己的 `~/.bashrc` 或私有文件，不要写进仓库内任何文件；
- 仓库内的示例配置（`agents/*.example.json`）只放环境变量名，不放真实 key；
- 若在文档/截图/日志中出现真实 key，视为已泄露，立即作废轮换。
