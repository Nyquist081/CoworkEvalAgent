# CoworkEvalAgent

CoworkEvalAgent 是一个面向本地 Agent 工作流的评测工程，用来回答一个很实际的问题：

> 给同一个任务，Agent 在“无 Skill / 有 Skill”两种条件下表现到底有没有差异？差异体现在哪里？能不能形成可复现、可比较、可回归的证据？

项目当前重点不是做一个多租户线上平台，而是搭建一套可在本机运行的 Agent 评测闭环：本地调用 Claude Code，采集执行 trace 和输出产物，再通过规则评分、可选 Judge、版本对比和共性分析来量化 Agent/Skill 的效果。

## 工程意义

LLM Agent 的效果经常难以稳定评估：一次回答看起来不错，不代表流程可靠；一个 Skill 看起来有用，也不代表它真的提升了任务完成度、工具使用质量或成本效率。CoworkEvalAgent 把这件事工程化：

- **从主观体验变成可复现实验**：同一评测目录、同一任务、同一输入，可以重复生成 baseline 与 skill 版本。
- **从单次结果变成版本对比**：所有运行结果落到 `runs/{label}/{qid}/attempt-1/`，可以在前端做多版本对比。
- **从“答案好不好”扩展到“执行过程好不好”**：评分不只看最终产物，也看工具调用成功率、耗时、轮次、token、成本等过程指标。
- **支持真实本地 Agent**：前端触发后端，后端调用本机 Claude Code CLI；浏览器不接触模型 Key。
- **可扩展到 Judge 语义诊断**：规则评分稳定可复现，Judge 负责补充语义判断，例如任务完成度、关键步骤、Skill 遵循度和问题建议。

## 当前能力

- 本地 Claude Code sidecar A/B 实验：同一任务自动跑无 Skill 与有 Skill 两个版本。
- 离线评测：读取已有 `runs/` 目录，不再调用 Agent，只重新评分。
- 单 Trace 调试：上传单个 `.jsonl` trace 进行快速检查。
- 六维评分：T1/T2/T3/T4/E/C，对应任务完成、工具准确、执行效率、思考效率、性能和成本。
- 多版本对比：通过率、六维雷达、题目维度热力图、趋势视图。
- Judge 可选：后端通过 OpenAI-compatible API 调用 DeepSeek 或其他模型。
- 前端操作台：面向非专业用户，隐藏模型 Key 和执行命令细节。

## 项目结构

```text
.
├── backend/                 # FastAPI 后端、评分流水线、Judge、数据库、API
├── frontend/                # Vue 3 + Element Plus 前端操作台
├── agent/                   # Agent sidecar 基础模块
├── scripts/
│   └── claude_sidecar_wrapper.py
│                              # 调用本机 Claude Code 并写入 CoworkEval trace
├── evaluations/
│   ├── industrial-demo/       # 离线工业样例
│   └── skill-demo-pack/       # Claude Code 安全审计 A/B demo
├── docs/                    # 设计与计划文档
└── 工业报告.md               # 平台设计来源报告
```

## 评测目录约定

CoworkEvalAgent 使用可落盘、可复现的离线评测结构：

```text
evaluations/<benchmark_id>/
├── manifest.json
├── <question_id>/
│   ├── prompt.txt
│   ├── 输入文件/
│   └── 参考答案/
├── skills/
│   └── <skill_name>/SKILL.md
└── runs/
    └── <run_label>/
        ├── run_meta.json
        └── <question_id>/
            └── attempt-1/
                ├── trace.jsonl
                └── 输出结果/
```

其中：

- `manifest.json` 描述评测集、题目、输入文件、参考答案、基准 token/耗时/工具数等。
- `skills/<skill_name>/SKILL.md` 是有 Skill 版本运行时注入给 Agent 的技能说明。
- `runs/<run_label>/.../trace.jsonl` 是 Agent 执行过程证据。
- `输出结果/` 存放 Agent 生成的报告、表格或其他产物。

## 快速开始

### 1. 启动后端

```bash
cd backend
uv sync
cp .env.example .env
uv run uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

后端默认会读取 `backend/.env`。如果只跑规则评分，可以先不配置 Judge Key。

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5176
```

浏览器打开：

```text
http://127.0.0.1:5176/
```

### 3. 运行本地 Claude Code A/B demo

确保本机 `claude` CLI 已可用：

```bash
claude --version
```

然后在前端执行：

```text
运行本地 Agent -> 填入安全审计 Demo -> 开始评测
```

该 demo 位于：

```text
evaluations/skill-demo-pack/
```

后端会自动做两次运行：

- `security-baseline-no-skill`：不注入 Skill。
- `security-with-skill`：注入 `skills/security_review/SKILL.md`。

运行完成后可以进入版本详情或版本对比查看结果。

## 模型与 Key 怎么配置

本项目是本地评测工具，不要求用户在前端配置模型或 Key。

### Claude Code Agent

Claude sidecar 通过本机 `claude` CLI 调用：

- 默认使用你本机 Claude Code 已经配置好的登录态和默认模型。
- 前端不会接触 Claude Key。
- 如果需要覆盖 Claude 模型，可以在 `backend/.env` 里设置：

```env
COWORKEVAL_CLAUDE_MODEL=sonnet
```

不设置时，后端不会传 `--model`，由本机 Claude Code 自己决定模型。

可选预算上限：

```env
COWORKEVAL_CLAUDE_MAX_BUDGET_USD=0.5
```

### Judge 模型

Judge 使用后端 OpenAI-compatible 配置，例如 DeepSeek：

```env
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-your-key-here
LLM_MODEL=deepseek-chat
```

前端只提供“是否启用 Judge”的开关，不提供 Key 输入。

## API 示例

### 评测已有 runs 目录

```bash
curl -X POST http://127.0.0.1:8000/coworkeval/v1/runs/evaluate-offline \
  -H "Content-Type: application/json" \
  -d '{
    "benchmark_root": "../evaluations/industrial-demo",
    "run_label": "alarm-with-skill",
    "judge_enabled": false
  }'
```

### 运行 Skill A/B 实验

```bash
curl -X POST http://127.0.0.1:8000/coworkeval/v1/experiments/skill-ab \
  -H "Content-Type: application/json" \
  -d '{
    "benchmark_root": "../evaluations/skill-demo-pack",
    "preset": "claude-code",
    "baseline_run_label": "security-baseline-no-skill",
    "skill_run_label": "security-with-skill",
    "judge_enabled": false,
    "skill_version": "security_review@v1"
  }'
```

## 评分维度

| 维度 | 含义 |
| --- | --- |
| T1 | 任务完成度，关注最终产物与参考答案或任务要求的匹配程度 |
| T2 | 工具准确性，关注工具调用成功率和错误情况 |
| T3 | 执行效率，关注工具调用数量相对基准是否膨胀 |
| T4 | 思考效率，关注轮次、token 等推理过程成本 |
| E | 执行性能，关注耗时与数据规模下的表现 |
| C | 成本效率，关注实际成本相对基准的偏离 |

规则评分适合稳定回归；Judge 适合判断报告质量、关键步骤、失败原因和 Skill 遵循度。

## 测试

后端：

```bash
cd backend
uv run pytest
```

前端：

```bash
cd frontend
npm run build
```

Agent sidecar：

```bash
cd agent
uv run pytest
```

## 适用场景

- 评估某个 Claude/Codex Skill 是否真的提升了 Agent 输出质量。
- 对比不同 prompt、不同 Skill 版本、不同 Agent 配置的效果。
- 为 Agent 工作流建立可回归的本地 benchmark。
- 研究 Agent 执行过程中的工具错误、轮次膨胀、成本膨胀和失败模式。
- 将人工经验沉淀为可验证的 Skill，再通过 A/B 实验检验价值。

## 当前定位与边界

CoworkEvalAgent 当前更像一个本地工程实验台，而不是 SaaS 平台：

- 不做多用户登录、权限、租户隔离。
- 不在浏览器保存或传输模型 Key。
- 不强制绑定某个模型供应商。
- 不假设评测只能用于 Claude；sidecar 命令和 trace 结构可以继续扩展到其他 Agent。

## 后续方向

- 增加报告类任务的结构化评分，让 Skill A/B 的内容质量差异更直接体现在分数上。
- 将 Judge 诊断和规则评分更细粒度地融合到版本对比页。
- 支持更多真实任务 demo，例如 TDD、代码审查、数据分析、前端可用性检查。
- 增加运行产物清理、归档和导出能力。
- 进一步标准化 Agent sidecar 接口，接入更多本地 Agent CLI。
