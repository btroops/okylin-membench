# 演示视频录制脚本（对应赛题交付 e：3~5 分钟 openKylin 桌面录屏）

目标：在 openKylin 桌面环境下，对**至少两款不同智能体**运行评测，
产出多维对比雷达图。按本脚本操作 + 照着口播稿念，录屏一次通过。

## 前置准备（录制前 10 分钟完成，不录入视频）

1. openKylin 环境安装包并确认可运行：
   ```bash
   sudo dpkg -i dist/membench_0.1.0-1_all.deb
   membench --version
   ```
2. 准备两份智能体配置（统一命名为 `agents/llm-a.agent.json` 与
   `agents/llm-b.agent.json`，后面镜头直接引用）：
   - 本地大模型：复制 `agents/openai-compat.example.json`，把 `base_url`
     指到本机 Ollama/vLLM（如 `http://127.0.0.1:11434/v1`），改动 `model`
     与 `name` 后存为 `agents/llm-a.agent.json`；
   - 另一款：`cp agents/nomem.agent.json agents/llm-b.agent.json` 或
     放入自行实现的 subproc 协议脚本。
3. 预跑一遍，确认两条命令无报错、报告能打开（避免录制中翻车）：
   ```bash
   membench run --agent <配置A> --agent <配置B> --runs 3 -o ~/video_run
   membench report ~/video_run/<A> ~/video_run/<B>
   ```

## 分镜与口播稿（总时长约 4 分钟）

### 镜头 1（0:00-0:30）背景与问题
- 画面：打开赛题 PPT 或终端里 `membench --help`
- 口播："智能体进入 openKylin 桌面后，谁记性更好，没有工具能回答。
  membench 是我们为 openKylin 生态做的长期记忆自动化评测基准：
  六维指标、五分类裁决、多证据源、一条命令出雷达图。"

### 镜头 2（0:30-1:10）数据集与用例设计
- 画面：`membench list`；再打开 `cases/update/upd-01.yaml` 高亮
  sessions/probes/expected 三段
- 口播："每个用例是一段记忆剧本：前几个 session 交代事实并埋入
  冲突更新、相近干扰或敏感信息；探针在之后的独立 session 提问。
  五类探针里四类完全确定性判定，天然可复现。24 个手写用例
  覆盖六个维度，`membench gen` 还能按模板批量生成。"

### 镜头 3（1:10-2:30）运行两款智能体评测
- 画面：分屏或先后执行：
  ```bash
  membench run --agent agents/llm-a.agent.json --agent agents/llm-b.agent.json \
               --cases cases --runs 3 -o ~/video_run
  ```
  终端滚动显示逐用例得分
- 口播："现在对两款智能体各跑三遍。注意同一输入下分数完全一致——
  这是确定性评分带来的可复现性；每个用例的证据包里保存了完整对话、
  智能体记忆库导出和文件系统变更。"

### 镜头 4（2:30-3:20）自动评分的可解释性
- 画面：打开一个证据 JSON（推荐 `naive` 或真实智能体在某 bnd 用例上的
  结果），高亮 verdict/reason/reply/hits 四个字段；再打开
  `evidence.memory_dump` 展示白盒证据
- 口播："评分不是只给一个总分。每条探针都有一个五分类裁决——
  正确记忆、遗漏、混淆、错误持久化、错误复用，理由里引用了
  回答原文。比如这里，智能体搬家后仍复述旧地址，被判为混淆；
  这条把密码写进了记忆库，被白盒检查当场抓获。"

### 镜头 5（3:20-4:00）雷达图对比与总结
- 画面：`membench report ~/video_run/<A> ~/video_run/<B>`，
  用浏览器打开 `comparison/report.html`，滚到雷达图停留
- 口播："最终雷达图把两款智能体的记忆画像分开：A 检索强但会把
  敏感信息落库，B 全面均衡。所有指标由程序自动产出，零人工审核。
  工具以 deb 包分发，已在 openKylin 上验证。"

## 录制技巧

- 用 KAZAM / OBS 录 1080p，终端字体调大（`export PS1='$ '` 收窄提示符）；
- 每个镜头前把命令**预先敲好**，录屏时只按回车；
- 打开 JSON 用带折叠的编辑器，避免滚动过快；
- 超时保险：镜头 3 若耗时太长，改用 `--filter ret-01,upd-01,bnd-01`
  缩小用例集，口播说明"完整集 24 例约 X 秒"。
