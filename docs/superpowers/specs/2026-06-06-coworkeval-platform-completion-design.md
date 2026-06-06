# CoworkEval 平台完善设计

日期: 2026-06-06
范围: Phase 2 平台闭环, 离线评测优先, 边车自动执行预留

## 1. 背景

当前项目已经具备 CoworkEval 的基础骨架: Manifest、TraceParser、BaselineEvaluator、JudgeEvaluator、FusionService、ComparisonEngine、MetaAnalyzer、FastAPI 接口和 Vue 页面均已存在, 后端模块测试通过。

但它距离 `工业报告.md` 描述的工业化评测平台仍有明显差距: T1 文件比对未进入核心评分服务, 批量 Pipeline 未按真实 run 目录读取 trace/output, Judge 与 Fusion 未接入完整流水线, 多版本比较接口仍返回空数据, pass@k/pass^k 与共性问题分析尚未从数据库闭环, agent 边车仍是模拟器。

本设计采用两阶段路线:

1. 先完成离线评测闭环, 让平台能稳定读取评测目录、评分、诊断、融合、对比和分析。
2. 再实现 agent 边车, 用命令模板调起本地 CLI Agent, 自动生成同样的运行输入。

## 2. 核心概念

### 2.1 Manifest

Manifest 是题库定义, 表示一套可回归评测集。它包含题目元数据、prompt 文件、输入文件、参考答案、输出目录规则、期望 Skill、eval_config 和 baseline 指标。

Manifest 是稳定资产, 可被多个 run 复用。

### 2.2 Run

Run 是某个 Agent/模型/Skill 配置在某个 Manifest 上的一次完整评测执行。多版本比较比较的是多个 Run。

Run 需要新增或明确以下展示与追踪字段:

- `run_label`: 展示标签, 如 `baseline-no-skill`, `skill-v2`, `gpt-5-20260606`
- `agent_name`: Agent 名称, 如 `codex-cli`
- `model`: 模型名称
- `skill_version`: Skill 或提示词版本
- `source`: `offline` 或 `sidecar`
- `trace_quality`: run 默认 trace 质量, 可被单题覆盖

### 2.3 Attempt

Attempt 表示同一道题在同一个 run 下的第几次执行, 用于 pass@k/pass^k。

第一版实现可以在数据模型中预留 `attempt_index`, 默认 `1`。当用户把同一题执行多次时, 按 `question_id + attempt_index` 存储多条评分结果。

### 2.4 Version

Version 不是单独实体。平台界面中的“版本”优先使用 `run_label`; 如未设置, 使用 run id 的短 ID。

这避免混淆 Manifest 版本、模型版本、Skill 版本和系统版本。

## 3. 输入模型

平台采用目录约定为主、网页上传为辅。

### 3.1 题库目录

题库资产放在:

```text
evaluations/<benchmark_id>/
  manifest.json
  <question_id>/
    prompt.txt
    输入文件/
    参考答案/
    skills/
```

示例:

```text
evaluations/scene_0328-2/
  manifest.json
  alarm_analysis-0003/
    prompt.txt
    输入文件/
      告警日志_20260601.xlsx
    参考答案/
      告警汇总_answer.xlsx
    skills/
      alarm_analysis/
        SKILL.md
```

### 3.2 运行目录

某次 Agent 执行后的证据放在:

```text
evaluations/<benchmark_id>/runs/<run_label>/
  run_meta.json
  <question_id>/
    attempt-1/
      trace.jsonl
      输出结果/
```

如果暂时不需要多次执行, 可以兼容简化目录:

```text
evaluations/<benchmark_id>/runs/<run_label>/
  <question_id>/
    trace.jsonl
    输出结果/
```

平台扫描时将简化目录视为 `attempt-1`。

### 3.3 run_meta.json

`run_meta.json` 记录 run 级元数据:

```json
{
  "run_label": "skill-v2",
  "agent_name": "codex-cli",
  "model": "gpt-5",
  "skill_version": "v2",
  "source": "offline",
  "created_at": "2026-06-06T12:00:00+08:00",
  "trace_quality": "full"
}
```

### 3.4 网页上传

网页上传保留为单题调试入口。用户可以上传 manifest、trace 和输出文件, 快速验证单题评分逻辑。批量回归不依赖网页多文件上传。

## 4. Trace 质量

平台支持两种 trace:

- `full`: Agent 原生 JSONL trace, 含工具调用、工具结果、assistant thinking、result 指标。
- `degraded`: 边车生成的简化 trace, 只能记录命令开始/结束、stdout/stderr 摘要、退出码、耗时和 result。

评分规则:

- full trace 可完整计算 T2/T3/T4/E/C, Judge 可做 Step 级诊断。
- degraded trace 标记 `is_partial_score=true`; T2/T3/T4 中无法可靠计算的维度应显示为缺失或低置信, 不应伪装成完整评分。
- T1 文件比对仍可正常进行, 因为它依赖输出文件和参考答案。

## 5. 后端闭环

### 5.1 目录扫描服务

新增目录扫描能力:

1. 读取 `evaluations/<benchmark_id>/manifest.json`。
2. 读取 `runs/<run_label>/run_meta.json`。
3. 按 manifest.questions 遍历题目。
4. 为每题定位 trace 和输出目录。
5. 为每个 attempt 构造统一的 `EvaluationInput`。

扫描器只负责发现文件和构造输入, 不做评分。

### 5.2 T1 文件比对下沉

T1 比对应从 API 层移入 `BaselineEvaluator` 或专门的 `TaskCompletionEvaluator`。服务层接收 output files、reference files、eval_config 后计算 `t1_baseline_only`。

API 不再临时覆盖 score, 而是返回已持久化的评分结果。

### 5.3 PipelineRunner

PipelineRunner 应支持完整状态:

```text
PENDING
  -> PARSING_TRACE
  -> EVALUATING_BASELINE
  -> AWAITING_JUDGE
  -> EVALUATING_JUDGE
  -> COMPLETED
```

如果 Judge 未启用, 从 `EVALUATING_BASELINE` 直接进入 `COMPLETED`, 并标记 baseline-only。

如果 Judge 调用失败且 baseline 已成功, run 或 score 标记 `is_partial_score=true`, 不应直接丢弃 baseline 结果。

### 5.4 Judge 与 Fusion

批量 Pipeline 中每个题目 baseline 完成后触发 Judge。Judge 结果落库后, `FusionService` 重算最终 ScoreResult。

Judge LLM 调用受 semaphore 限流, 默认并发 5。

### 5.5 多版本比较

`/compare/*` API 从数据库读取真实 run score:

- `/compare/radar?run_ids=a,b`: 返回每个 run 的六维均分。
- `/compare/heatmap?run_id=a`: 返回题目 x 维度矩阵。
- `/compare/trend?benchmark_id=x`: 返回同一 benchmark 下 run 序列的总分和 pass 率趋势。
- `/compare/pass-rate?run_ids=a,b`: 返回每个 run 的 pass@k/pass^k。

`ComparisonEngine` 保持纯函数, API 层负责查询和组装。

### 5.6 pass@k/pass^k

分制统一为 0-100。默认通过阈值为 60。

规则:

- 单次执行 pass: `t1_completion >= threshold`
- pass@k: 同一 question 的 k 次 attempt 中至少一次 pass
- pass^k: 同一 question 的 k 次 attempt 全部 pass
- 默认 k 为该 run 内同题 attempt 最大数量

如果历史数据仍使用 0-1 分制, 进入 MetaAnalyzer 前统一归一化到 0-100。

### 5.7 共性问题分析

共性分析使用已持久化 JudgeResult 摘要, 不重新读取原始 trace。输入包括 question_id、四维分、conclusion、critical_steps、evolution_suggestions。

LLM 输出:

- 200 字以内 summary
- 3 到 6 条 common_issues
- 3 到 5 条 improvement_suggestions

输出中的 `question_ids` 必须通过白名单校验, 只允许引用本次 run 真实存在的题目。

## 6. Agent 边车预留

第一阶段不实现自动执行, 但数据结构和接口按边车兼容设计。

边车配置:

```yaml
agent:
  name: codex-cli
  command_template: "codex run --cwd {workdir} --prompt-file {prompt_file}"
  trace_path_template: "{workdir}/trace.jsonl"
  output_dir_template: "{workdir}/输出结果"
```

边车职责:

1. 从平台领取任务或读取本地 manifest。
2. 为每道题创建隔离工作目录。
3. 复制 prompt、输入文件和 Skill。
4. 按命令模板启动 CLI Agent。
5. 收集原生 trace; 如不存在则生成 degraded trace。
6. 把输出文件和 trace 写入运行目录或上传后端。

边车不理解评分规则, 也不直接计算分数。

## 7. 前端体验

### 7.1 Dashboard

Dashboard 支持:

- 选择本地已注册 manifest。
- 选择或扫描 run 目录。
- 触发离线批量评测。
- 展示运行状态、总分、trace_quality 和 partial 标记。

### 7.2 版本详情

版本详情显示:

- 六维均分
- 单题列表
- attempt 数量
- trace_quality
- baseline-only 与 fused score 标记
- 单题 Judge 结论和关键步骤

### 7.3 多版本对比

多版本页面显示:

- 雷达图: 多个 run 的六维均分
- 热力图: 单个 run 的题目 x 维度矩阵
- 趋势线: 同一 benchmark 下 run 序列
- pass@k/pass^k 与 pp gap

### 7.4 共性分析

共性分析页面显示:

- run summary
- common issues
- improvement suggestions
- 每条 issue 关联的 question_ids 和示例步骤

## 8. 错误处理

- Manifest 缺失或 schema 不合法: run 不创建或标记 FAILED。
- 题目缺 trace: 该题标记 partial 或 failed, run 继续处理其他题。
- trace 缺 result: full trace 路径下抛 IncompleteTraceError; degraded trace 允许生成 result。
- 输出文件缺失: T1 为 0, 其他 trace 维度可继续评分。
- Judge 失败: baseline 分保留, score 标记 partial。
- 共性分析 LLM 输出引用不存在题目: 删除非法引用; 若 issue 无合法题目引用则丢弃该 issue。

## 9. 测试策略

后端:

- 目录扫描器: 标准目录、简化 attempt 目录、缺失 trace、缺失输出。
- T1 下沉: 有输出/无输出、多 reference、ignore_rules。
- Pipeline: baseline-only、judge-enabled、judge-failure partial、degraded trace。
- Compare API: radar、heatmap、trend、pass-rate 均从真实 repo 数据生成。
- MetaAnalyzer: 0-100 阈值、attempt 聚合、空输入不崩溃。
- Common issues: 白名单校验和持久化。

前端:

- API client 与页面状态渲染。
- 空数据、partial score、trace degraded 的展示。
- 多版本对比图表数据映射。

## 10. 分阶段交付

### Phase 2A: 离线闭环

- 目录扫描服务
- T1 文件比对下沉
- Pipeline 使用真实 run 目录
- Judge/Fusion 接入批量流水线
- ScoreResult 支持 attempt 和 trace_quality

### Phase 2B: 分析与对比

- Compare API 接数据库
- pass@k/pass^k 修正
- 共性问题 LLM 二次分析与持久化
- 前端多版本和共性分析接真实数据

### Phase 2C: 边车执行

- 命令模板配置
- 隔离工作目录
- full/degraded trace 收集
- 本地目录写入或后端上传

## 11. 不做范围

第一轮不做:

- 分布式任务队列
- 生产级对象存储
- 多租户权限
- 在线编辑复杂 manifest
- 自动校准 baseline
- 对所有 Agent CLI 的专用适配器

这些能力等离线评分闭环稳定后再扩展。
