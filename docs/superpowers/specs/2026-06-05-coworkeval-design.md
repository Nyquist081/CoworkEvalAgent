# CoworkEval 智能体评测平台 — 设计规格书

**日期**: 2026-06-05  
**范围**: 全栈（后端优先，分 3 个 Phase 推进）  
**来源**: 架构级系统蓝图 + 业务与规则补充契约 + 工业报告

---

## 1. 概述

CoworkEval 是一个智能体（Agent）评测基座平台，用于对 LLM Agent 的任务执行质量进行系统化、可回归的量化评测。平台提供从 Trace 数据采集 → Baseline 规则评分 → LLM 裁判语义诊断 → 融合评分 → 共性分析 → 多版本对比的完整评测闭环。

### 1.1 核心设计哲学

- **高内聚、低耦合**: 严格遵循单一职责原则 (SRP) 和依赖倒置原则 (DIP)
- **对照实验**: 以持久化评测集（Manifest）中的 baseline 基准值为锚点
- **规则 + 语义互补**: Baseline 纯规则打分（稳定、可复现）与 Judge LLM 语义诊断（深度、理解过程）50:50 融合
- **数据驱动改进**: 每层产出可持久化、可查询、可对比的结构化数据

---

## 2. 技术栈

| 层 | 技术选型 |
|---|---------|
| 后端框架 | FastAPI + Pydantic |
| ORM | SQLAlchemy (async) |
| 数据库 | SQLite (开发) / PostgreSQL (生产) |
| LLM 网关 | openai SDK (兼容 OpenAI/DeepSeek) |
| 数据处理 | pandas (T1 结果比对) |
| 包管理 | uv |
| 前端框架 | Vue 3 + TypeScript |
| UI 组件库 | Element Plus |
| 图表 | ECharts |
| 状态管理 | Pinia |
| Agent 边车 | Python asyncio |

---

## 3. 目录结构

```
evaluate-harness/
├── backend/
│   ├── src/
│   │   ├── core/                    # 领域层
│   │   │   ├── schemas.py           # Pydantic: Manifest, TaskRun, ScoreResult, JudgeResult
│   │   │   ├── interfaces.py        # ABC: BaseEvaluator, Repositories
│   │   │   ├── exceptions.py        # IncompleteTraceError, EvaluationError
│   │   │   └── state_machine.py     # TaskRun 状态机
│   │   ├── infrastructure/          # 基础设施层
│   │   │   ├── database.py          # SQLAlchemy engine + session
│   │   │   ├── llm_gateway.py       # LLMClient 适配器
│   │   │   ├── trace_parser.py      # JSONL 解析 + 指标提取
│   │   │   └── sandbox.py            # 评测沙箱管理（隔离目录+清理回调）
│   │   ├── repositories/            # 仓储层
│   │   │   ├── manifest_repository.py
│   │   │   ├── run_repository.py
│   │   │   ├── score_repository.py
│   │   │   └── judge_result_repository.py
│   │   ├── services/                # 业务逻辑层
│   │   │   ├── baseline_evaluator.py   # TTTEC 六维规则打分
│   │   │   ├── judge_evaluator.py      # LLM 四维语义诊断
│   │   │   ├── fusion_service.py       # 50:50 融合
│   │   │   ├── meta_analyzer.py        # pass@k/pass^k + 共性分析
│   │   │   ├── comparison_engine.py    # 多版本横向对比
│   │   │   └── pipeline_runner.py      # asyncio 并发调度器
│   │   ├── evaluator/               # T1 客观分校验
│   │   │   └── result_comparator.py    # Pandas DataFrame 比对
│   │   └── api/                     # 接入层
│   │       ├── router.py            # 统一路由注册
│   │       ├── runs.py              # /coworkeval/v1/runs
│   │       ├── scores.py            # /coworkeval/v1/scores
│   │       ├── comparison.py        # /coworkeval/v1/compare
│   │       ├── meta.py              # /coworkeval/v1/meta
│   │       └── websocket.py         # WebSocket
│   ├── tests/
│   ├── pyproject.toml
│   └── sample_data/                 # Mock 样例数据
│       ├── manifest.json
│       ├── traces/                  # JSONL 日志
│       └── references/              # 参考输出文件
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── Dashboard.vue
│   │   │   ├── VersionDetail.vue
│   │   │   ├── MultiVersion.vue
│   │   │   └── MetaAnalysis.vue
│   │   ├── components/
│   │   │   ├── RadarChart.vue
│   │   │   ├── Heatmap.vue
│   │   │   ├── TrendLine.vue
│   │   │   ├── PassRateCard.vue
│   │   │   ├── ScoreBreakdown.vue
│   │   │   └── StateTimeline.vue
│   │   ├── api/
│   │   ├── router/
│   │   └── stores/
│   └── package.json
└── agent/
    ├── src/
    │   ├── agent_runner.py
    │   └── trace_reporter.py
    └── pyproject.toml
```

---

## 4. 核心架构模式

### 4.1 依赖方向（自上而下）

```
API 层 → Services 层 → Core 接口 (ABC) ← Repositories 层 → Infrastructure 层
                                      ← Infrastructure 层 (LLMClient)
```

业务层只依赖抽象接口，不直接依赖具体实现。

### 4.2 设计模式

| 模式 | 应用位置 | 说明 |
|------|---------|------|
| Strategy | `BaseEvaluator` → `BaselineEvaluator`, `JudgeEvaluator` | 不同评分策略可互换 |
| Adapter | `LLMClient` | 封装 OpenAI/DeepSeek 差异，统一接口 `ask_structured_output()` |
| Repository | `RunRepository`, `ScoreRepository`, `JudgeResultRepository` | 业务层不直接写 SQL |

### 4.3 依赖注入

所有 Evaluator 和 Service 通过构造函数注入依赖：

```python
evaluator = BaselineEvaluator(
    score_repo=score_repo,
    comparator=ResultComparator()
)
```

---

## 5. 数据模型

### 5.1 TaskRun（评测任务）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID (PK) | 主键 |
| benchmark_id | str (FK) | 关联 Manifest |
| status | Enum | PENDING → PARSING_TRACE → EVALUATING_BASELINE → AWAITING_JUDGE → EVALUATING_JUDGE → COMPLETED / FAILED |
| error_stack | str? | FAILED 时记录 |
| is_partial_score | bool | 仅含 Baseline 分时为 True |
| judge_enabled | bool | 是否启用裁判模型 |
| created_at | datetime | |
| updated_at | datetime | |

### 5.2 ScoreResult（单题评分）

TTTEC 六维字段 (0-100) + 实际指标值。T1 字段区分融合后 (`t1_completion`)、纯 Baseline (`t1_baseline_only`)、纯 Judge (`t1_judge_only`)。

### 5.3 JudgeResult（裁判诊断）

四维打分 (execution_efficiency, tool_accuracy, thinking_efficiency, task_completion) + 结论 + 关键步骤因果链 + 改进建议 + Skill 合规审计 + fatal_violations（致命违规列表）。

### 5.4 Manifest（评测集）

benchmark_id (PK) + 版本元数据 + questions (JSON 数组，每道题含 prompt_file、input_files、reference_files、output_dir、eval_config（含 fatal_rules 致命规则）、payload_size_kb、baseline_* 基准值、skills 期望触发列表)。

### 5.5 状态机规则

- 状态流转严格单向，禁止跳跃
- 任意环节异常 → FAILED（记录 error_stack）
- 事件驱动融合：Baseline 完成 → 自动触发 Judge → Judge 完成 → 自动融合重算

---

## 6. API 设计

**前缀**: `/coworkeval/v1/`

### 6.1 评测任务

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/runs` | 创建评测任务 |
| GET | `/runs` | 列出所有任务 |
| GET | `/runs/{run_id}` | 任务详情 + 状态 |
| POST | `/runs/{run_id}/trigger-judge` | 手动触发裁判评测 |
| DELETE | `/runs/{run_id}` | 删除任务 |

### 6.2 评分

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/runs/{run_id}/scores` | 题目评分列表 |
| GET | `/runs/{run_id}/scores/{question_id}` | 单题详情 |
| GET | `/runs/{run_id}/scores/summary` | 任务级聚合 |

### 6.3 评测集

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/manifests` | 列出评测集 |
| POST | `/manifests` | 注册评测集 |

### 6.4 多版本对比

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/compare/radar?run_ids=` | 雷达图数据 |
| GET | `/compare/heatmap?run_ids=` | 热力图数据 |
| GET | `/compare/trend?benchmark_id=` | 趋势数据 |
| GET | `/compare/pass-rate?run_ids=` | pass@k/pass^k 对比 |

### 6.5 高级分析

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/meta/{run_id}/pass-rate` | pass@k/pass^k |
| GET | `/meta/{run_id}/common-issues` | 共性分析结果 |
| POST | `/meta/{run_id}/extract` | 触发共性分析 |

### 6.6 WebSocket

| 路径 | 说明 |
|------|------|
| `/ws/v1/runs/{run_id}` | 实时状态推送 |

---

## 7. TTTEC 六维评分公式

### T1 — 任务完成度
- Pandas 客观比对 (50%): DataFrame diff → 行/列/值匹配度
- LLM 意图分 (50%): Judge 模型 task_completion 维度
- Baseline 阶段若未配置 eval_config 规则，客观分置 0

### T2 — 工具准确率
```
Score = (success_tool_calls / total_tool_calls) × 100
若 total_tool_calls = 0，默认 100
```

### T3 — 工具效率
```
Score = max(0, 100 − 5 × max(0, actual_calls − baseline_calls))
```

### T4 — 思考效率
```
Token超标率 = max(0, actual_tokens − baseline_tokens) / baseline_tokens
轮次超标数 = max(0, actual_rounds − baseline_rounds)
Score = max(0, 100 − (Token超标率 × 100 × 0.3 + 轮次超标数 × 5))
```

### E — E2E 性能

**动态基线**: 当 `payload_size_kb` 存在时，基准时间按输入大小线性缩放，避免固定毫秒数在异构数据上失效：

```
dynamic_baseline_ms = baseline_time_ms × (actual_payload_kb / payload_size_kb)
Score = max(0, 100 − (max(0, actual_time − dynamic_baseline_ms) / dynamic_baseline_ms) × 100)
```

若 `payload_size_kb` 未配置，退化为静态基准（直接使用 `baseline_time_ms`）。

### C — 成本效率
```
Score = max(0, 100 − (max(0, actual_cost − baseline_cost) / baseline_cost) × 100)
```

所有维度结果由 `max(0, score)` 兜底，绝不出现负数。

---

## 8. 裁判模型设计

### 8.1 输入
JSONL Trace → 结构化 Step 编号文本（Step 1, Step 2, ...）

### 8.2 四维评分体系

| 维度 | 评估目标 | 分级标准摘要 |
|------|---------|-------------|
| execution_efficiency | 动作精简度与试错成本 | 90+: 路径极致精简; 60-74: 明显绕路; <60: 死循环 |
| tool_accuracy | 工具选择合理性与参数精准度 | 90+: 精准选用最优工具; 60-74: 多次参数构造失败; <60: 完全选错 |
| thinking_efficiency | 上下文理解与推理效率 | 90+: 完美结合上下文; 60-74: 产生幻觉; <60: 完全无视报错 |
| task_completion | 最终结果与用户意图契合度 | 90+: 完美解决含边界; 60-74: 表面完成但引入新Bug; <60: 完全偏离 |

### 8.3 关键步骤分析
仅标注 REDUNDANT / ERRONEOUS 步骤，含因果链（前因→现象→后果→根因→正确做法）。

### 8.4 Skill 合规审计

**线性计分**: 调用 Skill (+3) + 读取内容 (+3) + 执行脚本 (+4)，线性映射至 0-100。
```
tool_accuracy_final = 0.3 × 原工具分 + 0.7 × Skill合规子分
```

### 8.5 致命规则一票否决 (Fatal Rules)

企业级合规中存在不可妥协的底线规则。在 Manifest 的 `eval_config.fatal_rules` 中可配置致命规则列表，每条规则包含 `rule_id`、`description`、`dimension`（影响的评分维度）。

裁判模型在评测时逐条检查致命规则：

- **触发判定**: 裁判模型判定 Agent 行为违反了 `fatal_rules` 中任意一条 → 该规则命中
- **一票否决**: 命中的致命规则对应的 `dimension` 得分强制置为 **0**，覆盖原有评分
- **不可恢复**: 即使该维度其他方面表现完美，致命违规导致的 0 分不被融合公式稀释

```python
# Manifest eval_config 中的致命规则定义
"fatal_rules": [
    {
        "rule_id": "FR-001",
        "description": "禁止根据 identity_type 派生数据，必须优先使用自定义 trust_level 字段",
        "dimension": "tool_accuracy"
    },
    {
        "rule_id": "FR-002",
        "description": "禁止将原始用户数据发送到外部 API",
        "dimension": "task_completion"
    }
]
```

裁判结果中新增 `fatal_violations` 字段，记录所有命中的致命规则及其对应步骤：

```python
class FatalViolation(BaseModel):
    rule_id: str
    step_id: str          # 违规发生的 Step
    dimension: str        # 被置零的维度
    reasoning: str        # 裁判模型的违规判定依据
```

### 8.6 容灾

### 8.5 容灾
- 指数退避重试: 最多 3 次，初始延迟 2s，倍增因子 2
- 全部失败 → `is_partial_score=True`，仅保留 Baseline 分

---

## 9. 融合评分

E 和 C 维度不参与融合（纯客观物理量），T1-T4 50:50 融合：

```
T1_final = T1_baseline × 0.5 + T1_judge × 0.5
T2_final = T2_baseline × 0.5 + T2_judge × 0.5
T3_final = T3_baseline × 0.5 + T3_judge × 0.5
T4_final = T4_baseline × 0.5 + T4_judge × 0.5
E_final = E_baseline (不融合)
C_final = C_baseline (不融合)
overall = avg(T1_final, T2_final, T3_final, T4_final, E_final, C_final)
```

---

## 10. pass@k 与 pass^k

- **pass@k**: k 次执行中至少 1 次 T1 ≥ 阈值 → 该题通过
- **pass^k**: k 次执行中全部 T1 ≥ 阈值 → 该题通过
- 默认阈值: 多次执行 = 0.6，单次执行 = 1.0（向后兼容严格判定）
- 聚合: 按 `question_id` 折叠，跨任务聚合
- 输出: pass@k 百分比、pass^k 百分比、PP 差值

---

## 11. 共性分析

版本内所有裁判结果的摘要作为输入，LLM 二次分析输出:
1. **整体概述** (summary): ≤200 字版本能力画像
2. **共性问题** (common_issues): 3-6 条高频问题模式，含 question_ids 白名单校验
3. **改进建议** (improvement_suggestions): 3-5 条可落地优化方向

---

## 12. 容灾与异常处理

| 场景 | 处理策略 |
|------|---------|
| JSONL 截断/无结束标志 | `IncompleteTraceError` → 任务 FAILED，六维全 0 |
| LLM 调用超时/失败 | 指数退避重试 ×3，仍失败 → `is_partial_score=True` |
| LLM 并发限流 | asyncio Semaphore，默认最大并发 5 |
| 裁判模型返回解析失败 | 保留 `raw_response`，人工排查 |
| 致命规则触发 | `fatal_violations` 记录违规步骤，对应维度直接置 0 |
| 沙箱清理失败 | 记录告警日志，不影响任务终态 |

---

## 13. 评测沙箱隔离规范

### 13.1 隔离原则

每个评测任务运行时产生的中间文件（Agent 输出、临时脚本、日志缓存等）必须与宿主文件系统和其它并发任务**物理隔离**，防止并发冲突和跨任务污染。

### 13.2 沙箱目录结构

评测基座为每个 `TaskRun` 创建独立的沙箱目录：

```
/tmp/coworkeval/{run_id}/
├── output/          # Agent 产出文件（对应 Manifest 中的 output_dir）
├── workspace/       # Agent 工作目录（脚本执行、临时文件）
├── global_data/     # → 实际路径为 /tmp/coworkeval/global_data/（只读）
└── .meta/           # 沙箱元数据（创建时间、所属任务、清理标记）
```

- `global_data/` 指向沙箱根路径向上两层的 `/tmp/coworkeval/global_data/`，通过符号链接或只读挂载暴露到沙箱内
- `output/` 在评测完成后由 Pipeline 归档到持久化存储

### 13.3 沙箱生命周期

在 `src/infrastructure/sandbox.py` 中实现 `EvalSandbox`：

```python
class EvalSandbox:
    def __init__(self, run_id: str, base_path: str = "/tmp/coworkeval"):
        self.run_id = run_id
        self.sandbox_path = Path(base_path) / str(run_id)

    async def setup(self) -> str:
        """创建 output/ workspace/ global_data→ 符号链接，返回沙箱根路径"""

    async def cleanup(self) -> None:
        """删除沙箱全部内容"""

    async def archive_output(self) -> Path:
        """将 output/ 归档到持久化存储"""
```

### 13.4 清理回调

Pipeline 在状态流转到终态后强制执行清理：

| 终态 | 清理策略 |
|------|---------|
| COMPLETED | 先 `archive_output()` 归档产出，再 `cleanup()` |
| FAILED | 保留沙箱 24 小时（人工排查窗口），超时后自动清理 |

---

## 14. 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_BASE_URL` | LLM API 地址 | `https://api.openai.com/v1` |
| `LLM_API_KEY` | LLM API Key | (启用 Judge 时必填) |
| `LLM_MODEL` | 模型名称 | `gpt-4o` |
| `JUDGE_CONCURRENCY` | 裁判并发数 | `5` |
| `DATABASE_URL` | 数据库连接 | `sqlite:///coworkeval.db` |
| `PASS_THRESHOLD` | pass@k 及格阈值 | `0.6` |

---

## 15. 实施计划

### Phase 1 — 后端核心 (Sprint 1-4)

| Sprint | 内容 | 产出 |
|--------|------|------|
| S1 | 项目初始化 + 核心接口 | uv 环境、schemas、interfaces、exceptions、state_machine |
| S2 | 数据库 + 仓储层 | SQLAlchemy 模型、RunRepository、ScoreRepository、JudgeResultRepository |
| S3 | 基础设施层 | LLMClient、TraceParser、EvalSandbox、Mock 样例数据 |
| S4 | 业务逻辑层 | BaselineEvaluator、ResultComparator、PipelineRunner |

### Phase 2 — 后端高级功能 (Sprint 5-6)

| Sprint | 内容 | 产出 |
|--------|------|------|
| S5 | 裁判模型 + 融合 | JudgeEvaluator、FusionService |
| S6 | 高级分析 + API | MetaAnalyzer、ComparisonEngine、全部 API 路由 + WebSocket |

### Phase 3 — 前端 (Sprint 7-9)

| Sprint | 内容 | 产出 |
|--------|------|------|
| S7 | 前端基础 | Vue 3 脚手架、Element Plus、路由、API 封装、Dashboard |
| S8 | 前端详情页 | VersionDetail、MetaAnalysis 面板 |
| S9 | 前端对比页 | MultiVersion（雷达图/热力图/趋势线/pass@k 卡片） |

### Phase 4 — Agent 边车 + 集成 (Sprint 10)

| Sprint | 内容 | 产出 |
|--------|------|------|
| S10 | Agent 边车 | 任务领取、执行、Trace 上报、端到端集成测试 |

---

## 16. 测试策略

- **单元测试**: 每个 Evaluator 独立测试，Mock Repository 和 LLMClient
- **评分公式测试**: 边界值测试（0 调用、超标、负数兜底）
- **状态机测试**: 验证所有合法流转，拒绝非法跳跃
- **Pipeline 集成测试**: 使用 sample_data 端到端跑通
- **API 测试**: FastAPI TestClient 覆盖所有端点
- **致命规则测试**: 验证 fatal_rules 触发后对应维度强制置 0，且不被融合稀释
- **沙箱测试**: 验证隔离目录创建/清理、并发不冲突、FAILED 保留 24h

---

## 17. 关键设计决策记录

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| LLM 厂商 | OpenAI / DeepSeek / 双支持 | 双支持 | 环境变量切换，符合 Adapter 解耦哲学 |
| 前端范围 | 全栈 SPA / 后端优先 / 后端+轻量前端 | 后端优先分阶段 | 先扎实后端 API，前端 Phase 3 构建 |
| API 前缀 | /api/v1/ / /cwe/v1/ / /coworkeval/v1/ | /coworkeval/v1/ | 语义清晰，有品牌标识 |
| 数据库 | SQLite / PostgreSQL | SQLite 开发, PostgreSQL 生产 | SQLAlchemy 抽象切换 |
| E2E 基线 | 固定毫秒 / payload动态缩放 | payload动态缩放 | 异构数据下固定基线失效，KB级精确度才有说服力 |
| 合规红线 | 累加扣分 / 一票否决 | 一票否决 | 企业合规底线不可妥协，fatal_rules 触发直接置零 |
| 文件隔离 | 无隔离 / 沙箱隔离 | 沙箱隔离 | 并发评测必须物理隔离，防止跨任务污染 |
