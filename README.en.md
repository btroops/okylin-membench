# membench — An Automated Long-Term Memory Benchmark for openKylin Agents

English | [简体中文](README.md)

An automated evaluation harness for the **long-term memory capabilities** of
AI agents in the openKylin ecosystem (KylinBot / kylin-agent / OpenClaw /
HermesAgent, or any OpenAI-compatible endpoint). Zero third-party
dependencies — all you need is `python3 >= 3.8` and `python3-yaml`. One
command takes you from running scripted sessions to collecting evidence,
scoring automatically, and rendering a radar-chart report.

> Collaboration / workbench conventions (required reading for multi-person
> or multi-agent handoffs): [AGENTS.md](AGENTS.md) and
> [docs/WORKFLOW.md](docs/WORKFLOW.md).

## Core Paradigm

> **Evidence-chain-driven memory evaluation**: instead of grading final
> answers only, membench scores the full evidence chain — *memory-state
> evolution → retrieval sources → action artifacts*. This separates five
> failure modes that a final-answer QA paradigm cannot distinguish:
> *didn't remember*, *remembered but didn't use it*, *remembered wrong*,
> *should have forgotten but didn't*, and *shouldn't have stored it but did*.
> See [docs/EVIDENCE_CHAIN.md](docs/EVIDENCE_CHAIN.md) for details.

## Nine Dimensions

| Dimension | What it measures | Reference |
|---|---|---|
| retention | Is information that should be kept stably remembered? | core |
| recall | Can it be correctly retrieved in later interactions? | core |
| dynamic_update | Does new information overwrite old (both in answers and in the memory store)? | core |
| distractor_discrimination | Are near-duplicate facts kept apart (two cats / two IPs / two addresses)? | core |
| boundary_refusal | Is information that must *not* be stored refused (passwords / OTPs / ephemeral data, triple-checked)? | core |
| task_reuse | Do past methods / templates / commands transfer to new tasks (filesystem probes on action artifacts)? | core |
| temporal_reasoning | Event ordering and interval reasoning | LongMemEval (ICLR'25) |
| multi_session_reasoning | Combining / aggregating facts scattered across sessions | LongMemEval multi-session |
| causal_reasoning | Adjusting advice based on remembered preconditions ("I don't know Python" → suggest Go instead) | AMA-Bench (2026) |

## Verdict Categories (the explainable unit of automatic scoring)

`correct` remembered correctly · `miss` omitted · `confusion` mixed up with
an old value or a distractor · `improper_persistence` stored what should
have been refused · `improper_reuse` reused what shouldn't be reused ·
`not_evaluable` insufficient evidence (excluded from averages).

## Quick Start

```bash
# Run straight from the repo
python3 -m membench.cli doctor          # environment self-check (run before reproducing on openKylin)
python3 -m membench.cli demo            # full-pipeline demo with the three built-in agents
python3 -m membench.cli list            # list the 24 built-in cases
python3 -m membench.cli validate        # static validation of the dataset
python3 -m membench.cli gen --variants 3  # generate cases from templates in bulk (seeded, reproducible)

# Evaluate one agent 3 times (to see stability)
python3 -m membench.cli run --agent smart --runs 3 -o results/

# Batch comparison: --agent is repeatable, and may also point to a JSON file
# holding an array of agent configs
membench run --agent agents/openai-compat.example.json \
             --agent agents/echo.agent.json -o results/
membench run --agent batch_agents.json -o results/   # batch config shown below
membench report results/nomem results/naive results/smart
```

Output layout:

```
results/
├── <agent>/summary.json            # per-dimension scores + verdict distribution + stability (std)
├── <agent>/runs/runNN/<case>.json  # per-case evidence: full dialogue, memory-store dump, file diffs
├── comparison/report.html          # self-contained comparison report (radar / heatmap / FAMA / bin)
├── comparison/evidence.html        # per-case evidence viewer (verdict rationale / dialogue / memory evolution)
```

## Plugging In Your Agent

Three ways (see `agents/*.json` for examples):

1. **Built-in reference agents**: `{"kind": "builtin", "impl": "nomem|naive|smart"}`
2. **External program (stdio-JSONL protocol)**: `{"kind": "subproc", "cmd": ["python3", "your-agent.py"]}`
   The protocol is documented in the comments of `membench/agents/subproc.py`,
   with a reference implementation in `examples/echo-agent.py`.
3. **LLM API (two wire formats)**: `{"kind": "openai_compat", "api": "openai|anthropic", "base_url": "...", "model": "...", "memory": {"strategy": "none|full_log|store|store_filter"}}`
   - `"api": "openai"` (default): Chat Completions format; `base_url` must
     include the version segment (vLLM / Ollama / OpenAI-compatible
     endpoints); the key defaults to `OPENAI_API_KEY`;
   - `"api": "anthropic"`: Messages format; **`base_url` must NOT include
     the version segment** (e.g. `https://api.anthropic.com`, or DeepSeek's
     `https://api.deepseek.com/anthropic`); optional `"max_tokens"`
     (default 1024); the key defaults to `ANTHROPIC_API_KEY`;
     see [agents/anthropic-compat.example.json](agents/anthropic-compat.example.json).
   HTTP details (system-prompt splitting, message merging, auth headers) are
   handled uniformly by `membench/llmhttp.py`.

   **Switching providers / the three configuration points / a base_url
   cheat sheet for common vendors**:
   [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Dataset Format

Each case is a "memory script": multi-session dialogue + probes +
expectations. Full field reference in [docs/SCHEMA.md](docs/SCHEMA.md);
evaluation methodology in [docs/DESIGN.md](docs/DESIGN.md).

```yaml
schema_version: 1
case_id: upd-01-address
dimension: dynamic_update          # one of the nine dimensions
sessions:
  - session_id: s1
    turns: ["I live at 1 Zhongguancun Street, Haidian, Beijing."]
  - session_id: s2
    turns: ["I've moved to 100 Century Avenue, Pudong, Shanghai."]
probes:
  - probe_id: p1
    type: slot                     # choice/slot/free/fs/memory
    after_session: s2
    question: "Where do I live now?"
    expected:
      must_include: ["100 Century Avenue, Pudong, Shanghai"]
      must_not_include: ["1 Zhongguancun Street, Haidian, Beijing"]
```

## Scoring Design: Determinism First

- The `choice` / `slot` / `fs` / `memory` probe types are **fully
  deterministically graded** — identical input reproduces identical scores;
- `free` probes default to heuristic grading (works fully offline), with an
  optional LLM judge: `--judge openai` or `--judge anthropic` (both wire
  formats; endpoint, model, and key environment-variable defaults follow the
  format; forced JSON output + majority voting + fallback to heuristics on
  failure; judge call/failure counts flow into the summary and are visible in
  the report; see [docs/CONFIGURATION.md](docs/CONFIGURATION.md));
- White-box evidence: `memory` probes inspect the agent's exported memory
  store directly; filesystem snapshot diffs check action artifacts;
  `sensitive_patterns` scans everything written to disk or stored in memory
  for sensitive content.

## Installation (openKylin / Debian-based)

```bash
bash packaging/build_deb.sh          # builds dist/membench_0.1.0-1_all.deb
sudo dpkg -i dist/membench_0.1.0-1_all.deb
membench demo
```

## Running the Tests

```bash
python3 -m unittest discover -s tests   # 107 unit / end-to-end tests (35 cases + 21 templates / 9 dimensions; includes scoring-confidence experiments, the evidence viewer, and doctor self-checks)
```

## License

GPL-2.0-or-later
