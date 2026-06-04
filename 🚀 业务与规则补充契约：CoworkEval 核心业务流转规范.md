
在严格遵守前期架构解耦规范的基础上，请在业务逻辑层（`src/services/` 和 `src/core/`）严格实现以下业务闭环与规则：

## 1. 核心状态机设计 (State Machine)
一个评测任务 (`TaskRun`) 的生命周期必须严格遵循以下状态流转，禁止跳跃：
1. `PENDING`：已创建运行记录，等待解析日志。
2. `PARSING_TRACE`：正在读取并提取 JSONL 过程指标。
3. `EVALUATING_BASELINE`：正在比对规则，计算 Baseline 六维客观分。
4. `AWAITING_JUDGE`：(可选) 等待大模型裁判打分。
5. `EVALUATING_JUDGE`：正在调用 LLM 进行深度语义诊断。
6. `COMPLETED`：50:50 融合算分完毕，结果已落表。
7. `FAILED`：任何环节出现无法恢复的异常（如日志损坏、LLM 持续超时），必须记录错误栈。

## 2. 评测集数据结构契约 (Manifest Schema)
必须在 `src/core/schemas.py` 中定义严格的 `Manifest` Pydantic 模型，系统只能通过该模型摄入评测题：
- `benchmark_id`: str (全局唯一)
- `version`: str
- `questions`: List[QuestionItem]
  - `question_id`: str
  - `expected_skills`: List[str] (期望触发的 Skill 列表，用于合规审计)
  - `baseline_metrics`: Dict (必须包含 `tool_count`, `tokens`, `rounds`, `time_ms`, `cost_usd`)
  - `eval_config`: Dict (比对规则配置，如忽略字段等)

## 3. TTTEC 评分规则数学契约 (Scoring Formulas)
在 `BaselineEvaluator` 中，请严格实现以下惩罚扣分逻辑（非线性映射）：
- **工具效率 ($T3$)**: 
  $Score = \max(0, 100 - 5 \times \max(0, \text{actual\_tools} - \text{baseline\_tools}))$
  *(每多调用一次冗余工具，扣 5 分)*
- **思考效率 ($T4$)**: 
  $Score = \max(0, 100 - (\text{Token超标率} \times 100 \times 0.3 + \text{轮次超标数} \times 5))$
- **E2E 性能 ($E$)**: 
  $Score = \max(0, 100 - \frac{\max(0, \text{actual\_time} - \text{baseline\_time})}{\text{baseline\_time}} \times 100)$

## 4. 容灾与异常处理规范 (Resilience)
- **Trace 日志截断**：如果读取到的 JSONL 缺少完整的结束标志（如 Agent 意外崩溃），`TraceParser` 必须抛出 `IncompleteTraceError`，系统自动将其判定为任务失败，所有六维分记为 0。
- **LLM 裁判限流**：调用裁判模型时，必须实现指数退避重试（Exponential Backoff）。最多重试 3 次，若依然失败，则该题放弃裁判分，系统在 `ScoreResult` 中标记 `is_partial_score=True`（仅含 Baseline 分）。

## 5. 并发与流水线编排 (Pipeline Orchestration)
在 `src/services/pipeline_runner.py` 中实现调度器：
- 接收一个 `benchmark_id` 和对应的一批 JSONL 日志目录。
- 必须使用 Python `asyncio` 并发处理多道题目的解析和算分，但对于裁判模型的 LLM 调用，需要设置并发信号量（Semaphore，默认最大并发数为 5），防止打穿 API 的 Rate Limit。