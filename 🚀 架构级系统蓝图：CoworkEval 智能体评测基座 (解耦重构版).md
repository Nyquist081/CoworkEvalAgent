
## 0. 核心架构哲学与你的角色
**【你的角色】**：你是一位极具“技术洁癖”的高级架构师与全栈开发。
**【核心原则】**：系统的灵魂是“高内聚、低耦合”。绝对禁止将数据库访问、LLM 网络调用和算分业务逻辑揉杂在一起。必须严格遵守单一职责原则 (SRP) 和依赖倒置原则 (DIP)。

## 1. 领域驱动的目录结构 (解耦规范)
请严格按照以下结构初始化项目，确保各层物理隔离：
- `src/core/` (核心领域)：存放 Pydantic 契约、全局异常类、以及所有模块的抽象基类 (Abstract Base Classes, 接口)。
- `src/infrastructure/` (基础设施层)：存放底层驱动，如 `database` (SQLAlchemy 引擎)、`llm_gateway` (纯粹的 API 调用适配器)。
- `src/repositories/` (仓储层)：隔离数据库，业务层只能通过 Repository 接口读写数据，绝对不能在业务代码里写 `session.query`。
- `src/services/` (业务逻辑层)：组装核心逻辑，如 `BaselineEvaluator` 和 `JudgeEvaluator`。
- `src/api/` (接入层)：FastAPI 的路由，只负责接收请求和参数校验，核心计算必须转交给 Service 层。

## 2. 核心解耦设计 (Design Patterns)

### 2.1 LLM 网关适配器 (Adapter Pattern)
- **目标**：将评测系统与任何特定的 LLM 厂商（OpenAI/DeepSeek）解耦。
- **动作**：在 `src/infrastructure/llm_gateway.py` 中，封装一个极简的统一调用接口 `LLMClient`。业务层只需要调用 `client.ask_structured_output(prompt, response_model)`。底层使用标准的 `openai` 库实现，方便后续通过更换 `BASE_URL` 无缝切换到 DeepSeek，禁止引入 LangChain 这种重型依赖。

### 2.2 评估器策略接口 (Strategy Pattern)
- **目标**：Baseline 纯规则打分和 Judge 模型打分是两种不同的策略，未来可能还会增加“安全合规检查”策略。
- **动作**：在 `src/core/interfaces.py` 中定义抽象类 `BaseEvaluator`，包含统一的方法定义 `def evaluate(self, run_id: str, trace_data: list) -> EvalResult:`。
- 具体的 `BaselineEvaluator` 和 `JudgeEvaluator` 必须继承并实现这个接口。

### 2.3 仓储模式隔离 (Repository Pattern)
- **目标**：业务算分引擎不应该知道底层用的是 SQLite 还是 PostgreSQL。
- **动作**：在 `src/repositories/` 下建立 `RunRepository` 和 `ScoreRepository`。暴露如 `save_score()`, `get_trace()` 等语义化方法。

## 3. 你的开发执行冲刺 (Sprint Plan)

请你严格按照以下顺序开发，每完成一个 Sprint 必须向我汇报，等待 Review：

**Sprint 1: 核心接口与仓储层搭建 (打地基)**
- 初始化 `uv` 环境和目录。
- 编写 `src/core/schemas.py` (Pydantic 模型) 和 `src/core/interfaces.py` (抽象接口)。
- 编写数据库模型与 `ScoreRepository`。

**Sprint 2: 基础设施接入 (通水电)**
- 实现无框架依赖的轻量级 `LLMClient` (使用原生 openai SDK)。
- 实现 `TraceParser` (负责清洗和解析 JSONL)。

**Sprint 3: 业务编排 (建楼)**
- 实现 `BaselineEvaluator` 和 `JudgeEvaluator`，并将 Repository 和 LLMClient 作为依赖注入 (Dependency Injection) 进去，而不是在内部直接实例化。

⚡ **执行指令**：
请确认你已理解这种严格解耦的架构意图。现在，请执行 **Sprint 1**，自动创建目录，并优先向我展示 `src/core/interfaces.py` (评估器抽象接口) 和 `schemas.py` (领域模型) 的代码。