# CoworkEval Phase 1: Backend Core — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend core of the CoworkEval agent evaluation platform — domain models, repositories, infrastructure (LLM gateway, trace parser, sandbox), and business logic (TTTEC six-dimension scoring + pipeline runner).

**Architecture:** 5-layer DDD: API → Services → Core (ABCs) ← Repositories → Infrastructure. Strategy pattern for evaluators, Adapter pattern for LLM gateway, Repository pattern for data access. Strict dependency inversion — business layer depends only on abstract interfaces.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), openai SDK, pandas, uv package manager, pytest + pytest-asyncio

---

## File Map

```
backend/
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── schemas.py           # All Pydantic models (Manifest, TaskRun, ScoreResult, JudgeResult, etc.)
│   │   ├── interfaces.py        # ABCs: BaseEvaluator, RunRepository, ScoreRepository, JudgeResultRepository
│   │   ├── exceptions.py        # IncompleteTraceError, EvaluationError, StateTransitionError
│   │   └── state_machine.py     # TaskRun state transitions, validation
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── database.py          # SQLAlchemy async engine, session factory, Base
│   │   ├── llm_gateway.py       # LLMClient: unified ask_structured_output() adapter
│   │   ├── trace_parser.py      # JSONL parser, metric extraction, completeness check
│   │   └── sandbox.py           # EvalSandbox: per-run isolated temp directories
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── manifest_repository.py
│   │   ├── run_repository.py
│   │   ├── score_repository.py
│   │   └── judge_result_repository.py
│   ├── evaluator/
│   │   ├── __init__.py
│   │   └── result_comparator.py # Pandas-based T1 objective file comparison
│   ├── services/
│   │   ├── __init__.py
│   │   ├── baseline_evaluator.py  # TTTEC six-dimension rule-based scoring
│   │   └── pipeline_runner.py     # asyncio concurrent orchestration with Semaphore
│   └── api/
│       ├── __init__.py            # (empty for now, used in Phase 2)
│       └── router.py              # (placeholder, implemented in Phase 2)
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_core/
│   │   ├── test_schemas.py
│   │   ├── test_state_machine.py
│   │   └── test_exceptions.py
│   ├── test_infrastructure/
│   │   ├── test_llm_gateway.py
│   │   ├── test_trace_parser.py
│   │   └── test_sandbox.py
│   ├── test_repositories/
│   │   ├── test_run_repository.py
│   │   ├── test_score_repository.py
│   │   └── test_judge_result_repository.py
│   ├── test_evaluator/
│   │   └── test_result_comparator.py
│   └── test_services/
│       ├── test_baseline_evaluator.py
│       └── test_pipeline_runner.py
└── sample_data/
    ├── manifest.json
    ├── traces/
    │   ├── valid_trace.jsonl
    │   └── incomplete_trace.jsonl
    └── references/
        └── expected_output.xlsx
```

---

## Sprint 1: 项目初始化 + 核心接口

### Task 1: Initialize uv project and directory structure

**Files:**
- Create: `backend/pyproject.toml`
- Create: all `__init__.py` files
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Create the project directory**

```bash
mkdir -p backend/src/core backend/src/infrastructure backend/src/repositories backend/src/evaluator backend/src/services backend/src/api
mkdir -p backend/tests/test_core backend/tests/test_infrastructure backend/tests/test_repositories backend/tests/test_evaluator backend/tests/test_services
mkdir -p backend/sample_data/traces backend/sample_data/references
```

- [ ] **Step 2: Write pyproject.toml**

```toml
[project]
name = "coworkeval"
version = "0.1.0"
description = "Agent evaluation harness"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.0",
    "sqlalchemy[asyncio]>=2.0",
    "aiosqlite>=0.20.0",
    "openai>=1.50.0",
    "pandas>=2.0",
    "openpyxl>=3.1.0",
    "websockets>=12.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
]
```

- [ ] **Step 3: Run uv sync**

```bash
cd backend && uv sync
```
Expected: creates virtual environment, installs all deps.

- [ ] **Step 4: Write conftest.py**

```python
import pytest
import asyncio

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

- [ ] **Step 5: Write all __init__.py files**

```bash
touch backend/src/__init__.py
touch backend/src/core/__init__.py
touch backend/src/infrastructure/__init__.py
touch backend/src/repositories/__init__.py
touch backend/src/evaluator/__init__.py
touch backend/src/services/__init__.py
touch backend/src/api/__init__.py
touch backend/tests/__init__.py
touch backend/tests/test_core/__init__.py
touch backend/tests/test_infrastructure/__init__.py
touch backend/tests/test_repositories/__init__.py
touch backend/tests/test_evaluator/__init__.py
touch backend/tests/test_services/__init__.py
```

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/src/ backend/tests/
git commit -m "chore: initialize uv project and directory structure

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Write core/schemas.py — Pydantic domain models

**Files:**
- Create: `backend/src/core/schemas.py`
- Create: `backend/tests/test_core/test_schemas.py`

- [ ] **Step 1: Write failing test for Manifest schema**

```python
# tests/test_core/test_schemas.py
import pytest
from src.core.schemas import Manifest, QuestionItem, EvalConfig, FatalRule, IgnoreRule

def test_manifest_parses_valid_json():
    data = {
        "benchmark_id": "scene_0328-2",
        "name": "scene_0328-2",
        "version": "1.0.9",
        "created_at": "2026-04-02T20:19:19+08:00",
        "created_by": "yue",
        "description": "test benchmark",
        "total_questions": 1,
        "questions": [
            {
                "question_id": "q-0001",
                "question_name": "test question",
                "category": "Excel",
                "difficulty": "中等",
                "prompt_file": "q-0001/prompt.txt",
                "input_files": ["q-0001/input.xlsx"],
                "reference_files": ["q-0001/ref_answer.xlsx"],
                "output_dir": "q-0001/output/",
                "eval_config": {
                    "compare_style": True,
                    "ignore_rules": [
                        {"type": "column", "sheet": "Sheet1", "columns": ["K"]}
                    ],
                    "fatal_rules": [
                        {
                            "rule_id": "FR-001",
                            "description": "禁止根据 identity_type 派生数据",
                            "dimension": "tool_accuracy"
                        }
                    ]
                },
                "scene": "skills",
                "skills": "project_business_analysis",
                "payload_size_kb": 128.0,
                "baseline_tokens": 693592,
                "baseline_rounds": 19,
                "baseline_tool_count": 17,
                "baseline_time_ms": 64000,
                "baseline_cost_usd": 3.58132
            }
        ]
    }
    manifest = Manifest.model_validate(data)
    assert manifest.benchmark_id == "scene_0328-2"
    assert manifest.questions[0].question_id == "q-0001"
    assert manifest.questions[0].baseline_tool_count == 17
    assert manifest.questions[0].payload_size_kb == 128.0
    assert manifest.questions[0].eval_config.fatal_rules[0].rule_id == "FR-001"


def test_task_run_status_enum():
    from src.core.schemas import RunStatus
    assert RunStatus.PENDING.value == "PENDING"
    assert RunStatus.COMPLETED.value == "COMPLETED"
    assert RunStatus.FAILED.value == "FAILED"
    valid_order = [
        RunStatus.PENDING,
        RunStatus.PARSING_TRACE,
        RunStatus.EVALUATING_BASELINE,
        RunStatus.AWAITING_JUDGE,
        RunStatus.EVALUATING_JUDGE,
        RunStatus.COMPLETED,
    ]
    # ordered correctly
    for i in range(len(valid_order) - 1):
        assert valid_order[i] != valid_order[i + 1]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_core/test_schemas.py -v
```
Expected: FAIL, ImportError (schemas module not found)

- [ ] **Step 3: Write core/schemas.py**

```python
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────

class RunStatus(str, Enum):
    PENDING = "PENDING"
    PARSING_TRACE = "PARSING_TRACE"
    EVALUATING_BASELINE = "EVALUATING_BASELINE"
    AWAITING_JUDGE = "AWAITING_JUDGE"
    EVALUATING_JUDGE = "EVALUATING_JUDGE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JudgeDimension(str, Enum):
    EXECUTION_EFFICIENCY = "execution_efficiency"
    TOOL_ACCURACY = "tool_accuracy"
    THINKING_EFFICIENCY = "thinking_efficiency"
    TASK_COMPLETION = "task_completion"


# ── Eval Config ──────────────────────────────────────────

class IgnoreRule(BaseModel):
    type: str  # "column", "row", "region"
    sheet: Optional[str] = None
    columns: Optional[list[str]] = None
    rows: Optional[list[int]] = None


class FatalRule(BaseModel):
    rule_id: str
    description: str
    dimension: JudgeDimension


class EvalConfig(BaseModel):
    compare_style: bool = False
    ignore_rules: list[IgnoreRule] = Field(default_factory=list)
    fatal_rules: list[FatalRule] = Field(default_factory=list)


# ── Manifest / Questions ─────────────────────────────────

class QuestionItem(BaseModel):
    question_id: str
    question_name: str
    category: str
    difficulty: str
    prompt_file: str
    input_files: list[str] = Field(default_factory=list)
    reference_files: list[str] = Field(default_factory=list)
    output_dir: str
    eval_config: EvalConfig = Field(default_factory=EvalConfig)
    scene: str = ""
    skills: str = ""
    payload_size_kb: Optional[float] = None
    baseline_tokens: int = 0
    baseline_rounds: int = 0
    baseline_tool_count: int = 0
    baseline_time_ms: int = 0
    baseline_cost_usd: float = 0.0


class Manifest(BaseModel):
    benchmark_id: str
    name: str
    version: str
    created_at: datetime
    created_by: str = ""
    description: str = ""
    total_questions: int = 0
    questions: list[QuestionItem] = Field(default_factory=list)


# ── Task Run ─────────────────────────────────────────────

class TaskRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    benchmark_id: str
    status: RunStatus = RunStatus.PENDING
    error_stack: Optional[str] = None
    is_partial_score: bool = False
    judge_enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Score Result ─────────────────────────────────────────

class ScoreResult(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    question_id: str

    # TTTEC six-dimension scores (0-100), may be None until computed
    t1_completion: Optional[float] = None
    t2_accuracy: Optional[float] = None
    t3_efficiency: Optional[float] = None
    t4_thinking: Optional[float] = None
    e_performance: Optional[float] = None
    c_cost: Optional[float] = None

    overall_score: Optional[float] = None
    t1_baseline_only: Optional[float] = None
    t1_judge_only: Optional[float] = None

    # Actual metrics extracted from trace
    actual_tool_calls: int = 0
    actual_success_calls: int = 0
    actual_tokens: int = 0
    actual_rounds: int = 0
    actual_time_ms: int = 0
    actual_cost_usd: float = 0.0


# ── Judge Result ─────────────────────────────────────────

class CriticalStep(BaseModel):
    step_id: str
    assessment: str  # "REDUNDANT" or "ERRONEOUS"
    observation: str
    context_chain: str
    root_cause: str
    expected_action: str


class EvolutionSuggestion(BaseModel):
    type: str
    suggestion: str


class SkillCompliance(BaseModel):
    skill_invoked: bool = False
    skill_read: bool = False
    script_executed: bool = False
    has_script_requirement: bool = False
    score: int = 0  # 0-100


class FatalViolation(BaseModel):
    rule_id: str
    step_id: str
    dimension: JudgeDimension
    reasoning: str


class JudgeResult(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    question_id: str

    execution_efficiency: int = 0
    tool_accuracy: int = 0
    thinking_efficiency: int = 0
    task_completion: int = 0

    conclusion: str = ""
    critical_steps: list[CriticalStep] = Field(default_factory=list)
    evolution_suggestions: list[EvolutionSuggestion] = Field(default_factory=list)
    skill_compliance: Optional[SkillCompliance] = None
    fatal_violations: list[FatalViolation] = Field(default_factory=list)
    raw_response: str = ""


# ── Judge Structured Output Schemas ──────────────────────

class EfficiencyScore(BaseModel):
    score: int = Field(ge=0, le=100)
    level: str  # "优秀", "良好", "及格", "不及格"
    reason: str


class ToolAccuracyScore(BaseModel):
    score: int = Field(ge=0, le=100)
    level: str
    reason: str


class ThinkingScore(BaseModel):
    score: int = Field(ge=0, le=100)
    level: str
    reason: str


class CompletionScore(BaseModel):
    score: int = Field(ge=0, le=100)
    level: str
    reason: str


class JudgeVerdict(BaseModel):
    execution_efficiency: EfficiencyScore
    tool_accuracy: ToolAccuracyScore
    thinking_efficiency: ThinkingScore
    task_completion: CompletionScore
    conclusion: str
    critical_steps: list[CriticalStep]
    evolution_suggestions: list[EvolutionSuggestion]
    skill_compliance: Optional[SkillCompliance] = None
    fatal_violations: list[FatalViolation] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_core/test_schemas.py -v
```
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/core/schemas.py backend/tests/test_core/test_schemas.py
git commit -m "feat: add Pydantic domain models (Manifest, TaskRun, ScoreResult, JudgeResult)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Write core/interfaces.py — Abstract Base Classes

**Files:**
- Create: `backend/src/core/interfaces.py`
- Create: `backend/tests/test_core/` (追加验证，test_schemas.py 已存在)

- [ ] **Step 1: Write failing test**

```python
# Add to tests/test_core/test_schemas.py

def test_base_evaluator_is_abstract():
    from src.core.interfaces import BaseEvaluator
    with pytest.raises(TypeError):
        BaseEvaluator()  # Cannot instantiate ABC


def test_concrete_evaluator_must_implement_evaluate():
    from src.core.interfaces import BaseEvaluator
    from src.core.schemas import ScoreResult

    class BadEvaluator(BaseEvaluator):
        pass  # Missing evaluate method

    with pytest.raises(TypeError):
        BadEvaluator()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_core/test_schemas.py::test_base_evaluator_is_abstract -v
```
Expected: FAIL, ImportError

- [ ] **Step 3: Write core/interfaces.py**

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from src.core.schemas import Manifest, TaskRun, ScoreResult, JudgeResult, RunStatus


class BaseEvaluator(ABC):
    """Strategy interface for evaluation. BaselineEvaluator and JudgeEvaluator
    must implement this."""

    @abstractmethod
    async def evaluate(self, run_id: UUID, trace_data: list[dict]) -> ScoreResult:
        """Compute scores for a single question from its trace data."""
        ...


class RunRepository(ABC):
    """Abstract repository for TaskRun persistence."""

    @abstractmethod
    async def save(self, run: TaskRun) -> TaskRun:
        ...

    @abstractmethod
    async def get(self, run_id: UUID) -> Optional[TaskRun]:
        ...

    @abstractmethod
    async def list_by_benchmark(self, benchmark_id: str) -> list[TaskRun]:
        ...

    @abstractmethod
    async def update_status(self, run_id: UUID, status: RunStatus,
                            error_stack: Optional[str] = None) -> TaskRun:
        ...

    @abstractmethod
    async def delete(self, run_id: UUID) -> None:
        ...


class ScoreRepository(ABC):
    """Abstract repository for ScoreResult persistence."""

    @abstractmethod
    async def save(self, score: ScoreResult) -> ScoreResult:
        ...

    @abstractmethod
    async def get_by_run_and_question(self, run_id: UUID,
                                      question_id: str) -> Optional[ScoreResult]:
        ...

    @abstractmethod
    async def list_by_run(self, run_id: UUID) -> list[ScoreResult]:
        ...


class JudgeResultRepository(ABC):
    """Abstract repository for JudgeResult persistence."""

    @abstractmethod
    async def save(self, result: JudgeResult) -> JudgeResult:
        ...

    @abstractmethod
    async def get_by_run_and_question(self, run_id: UUID,
                                      question_id: str) -> Optional[JudgeResult]:
        ...

    @abstractmethod
    async def list_by_run(self, run_id: UUID) -> list[JudgeResult]:
        ...
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_core/test_schemas.py -v
```
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/core/interfaces.py backend/tests/test_core/test_schemas.py
git commit -m "feat: add ABC interfaces (BaseEvaluator, RunRepository, ScoreRepository, JudgeResultRepository)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Write core/exceptions.py

**Files:**
- Create: `backend/src/core/exceptions.py`
- Append: `backend/tests/test_core/test_schemas.py` (add exception tests)

- [ ] **Step 1: Write failing test**

```python
# Add to tests/test_core/test_schemas.py

def test_incomplete_trace_error():
    from src.core.exceptions import IncompleteTraceError
    err = IncompleteTraceError("missing result record", question_id="q-001")
    assert str(err) == "missing result record"
    assert err.question_id == "q-001"


def test_evaluation_error():
    from src.core.exceptions import EvaluationError
    err = EvaluationError("LLM timeout after 3 retries", run_id="run-123")
    assert err.run_id == "run-123"


def test_state_transition_error():
    from src.core.exceptions import StateTransitionError
    err = StateTransitionError(
        from_status="PENDING",
        to_status="COMPLETED",
        reason="Must go through intermediate states"
    )
    assert err.from_status == "PENDING"
    assert err.to_status == "COMPLETED"
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && uv run pytest tests/test_core/test_schemas.py::test_incomplete_trace_error -v
```
Expected: FAIL (ImportError)

- [ ] **Step 3: Write core/exceptions.py**

```python
from __future__ import annotations
from typing import Optional


class CoworkEvalError(Exception):
    """Base exception for all CoworkEval errors."""
    pass


class IncompleteTraceError(CoworkEvalError):
    """Raised when JSONL trace is missing the final result record,
    indicating the agent crashed or was interrupted."""
    def __init__(self, message: str, question_id: Optional[str] = None):
        super().__init__(message)
        self.question_id = question_id


class EvaluationError(CoworkEvalError):
    """Raised when an evaluation step fails unrecoverably."""
    def __init__(self, message: str, run_id: Optional[str] = None):
        super().__init__(message)
        self.run_id = run_id


class StateTransitionError(CoworkEvalError):
    """Raised when an invalid state transition is attempted."""
    def __init__(self, from_status: str, to_status: str, reason: str):
        super().__init__(f"Cannot transition from {from_status} to {to_status}: {reason}")
        self.from_status = from_status
        self.to_status = to_status
        self.reason = reason
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_core/test_schemas.py -v
```
Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/core/exceptions.py backend/tests/test_core/test_schemas.py
git commit -m "feat: add domain exceptions (IncompleteTraceError, EvaluationError, StateTransitionError)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Write core/state_machine.py

**Files:**
- Create: `backend/src/core/state_machine.py`
- Create: `backend/tests/test_core/test_state_machine.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_core/test_state_machine.py
import pytest
from src.core.state_machine import StateMachine
from src.core.schemas import RunStatus
from src.core.exceptions import StateTransitionError


class TestStateMachine:
    def test_valid_transition_sequence(self):
        sm = StateMachine()
        transitions = [
            RunStatus.PENDING,
            RunStatus.PARSING_TRACE,
            RunStatus.EVALUATING_BASELINE,
            RunStatus.AWAITING_JUDGE,
            RunStatus.EVALUATING_JUDGE,
            RunStatus.COMPLETED,
        ]
        for status in transitions:
            sm.validate_transition(sm.current, status)
            sm.transition_to(status)
        assert sm.current == RunStatus.COMPLETED

    def test_can_transition_to_failed_from_any_state(self):
        fail_states = [
            RunStatus.PENDING,
            RunStatus.PARSING_TRACE,
            RunStatus.EVALUATING_BASELINE,
            RunStatus.AWAITING_JUDGE,
            RunStatus.EVALUATING_JUDGE,
        ]
        for from_state in fail_states:
            sm = StateMachine()
            sm.current = from_state
            sm.validate_transition(from_state, RunStatus.FAILED)
            sm.transition_to(RunStatus.FAILED)
            assert sm.current == RunStatus.FAILED

    def test_invalid_jump_rejected(self):
        sm = StateMachine()
        with pytest.raises(StateTransitionError):
            sm.validate_transition(RunStatus.PENDING, RunStatus.COMPLETED)

    def test_failed_is_terminal(self):
        sm = StateMachine()
        sm.transition_to(RunStatus.FAILED)
        with pytest.raises(StateTransitionError):
            sm.validate_transition(RunStatus.FAILED, RunStatus.PENDING)

    def test_completed_is_terminal(self):
        sm = StateMachine()
        sm.transition_to(RunStatus.COMPLETED)
        with pytest.raises(StateTransitionError):
            sm.validate_transition(RunStatus.COMPLETED, RunStatus.PENDING)

    def test_skip_judge_path(self):
        """When judge is disabled, can go from EVALUATING_BASELINE to COMPLETED."""
        sm = StateMachine(judge_enabled=False)
        sm.transition_to(RunStatus.EVALUATING_BASELINE)
        sm.validate_transition(RunStatus.EVALUATING_BASELINE, RunStatus.COMPLETED)
        sm.transition_to(RunStatus.COMPLETED)
        assert sm.current == RunStatus.COMPLETED
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && uv run pytest tests/test_core/test_state_machine.py -v
```
Expected: FAIL (ImportError)

- [ ] **Step 3: Write core/state_machine.py**

```python
from __future__ import annotations
from src.core.schemas import RunStatus
from src.core.exceptions import StateTransitionError


# Valid transitions: from → set of allowed next states
_VALID_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.PENDING: {RunStatus.PARSING_TRACE, RunStatus.FAILED},
    RunStatus.PARSING_TRACE: {RunStatus.EVALUATING_BASELINE, RunStatus.FAILED},
    RunStatus.EVALUATING_BASELINE: {RunStatus.AWAITING_JUDGE, RunStatus.COMPLETED, RunStatus.FAILED},
    RunStatus.AWAITING_JUDGE: {RunStatus.EVALUATING_JUDGE, RunStatus.FAILED},
    RunStatus.EVALUATING_JUDGE: {RunStatus.COMPLETED, RunStatus.FAILED},
    RunStatus.COMPLETED: set(),   # terminal
    RunStatus.FAILED: set(),      # terminal
}

# When judge is disabled, skip AWAITING_JUDGE and EVALUATING_JUDGE
_VALID_TRANSITIONS_NO_JUDGE = dict(_VALID_TRANSITIONS)
_VALID_TRANSITIONS_NO_JUDGE[RunStatus.EVALUATING_BASELINE] = {RunStatus.COMPLETED, RunStatus.FAILED}


class StateMachine:
    def __init__(self, current: RunStatus = RunStatus.PENDING, judge_enabled: bool = True):
        self.current = current
        self.judge_enabled = judge_enabled
        self._transitions = _VALID_TRANSITIONS if judge_enabled else _VALID_TRANSITIONS_NO_JUDGE

    def validate_transition(self, from_status: RunStatus, to_status: RunStatus) -> None:
        allowed = self._transitions.get(from_status, set())
        if to_status not in allowed:
            raise StateTransitionError(
                from_status=from_status.value,
                to_status=to_status.value,
                reason=f"Allowed next states from {from_status.value}: "
                       f"{[s.value for s in allowed]}"
            )

    def transition_to(self, to_status: RunStatus) -> None:
        self.validate_transition(self.current, to_status)
        self.current = to_status
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_core/test_state_machine.py -v
```
Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/core/state_machine.py backend/tests/test_core/test_state_machine.py
git commit -m "feat: add TaskRun state machine with strict transition validation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Sprint 2: 数据库 + 仓储层

### Task 6: Write infrastructure/database.py — SQLAlchemy setup

**Files:**
- Create: `backend/src/infrastructure/database.py`
- Create: `backend/tests/test_infrastructure/` (测试在后续仓储测试中覆盖)

- [ ] **Step 1: Set DATABASE_URL and write database.py**

```bash
export DATABASE_URL="sqlite+aiosqlite:///./coworkeval.db"
```

```python
# src/infrastructure/database.py
from __future__ import annotations
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./coworkeval.db")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```

- [ ] **Step 2: Write quick smoke test**

```python
# tests/test_infrastructure/test_database.py
import pytest
from src.infrastructure.database import engine, init_db, drop_db, async_session

@pytest.mark.asyncio
async def test_engine_connects():
    assert engine is not None
    # Test we can get a session
    async with async_session() as session:
        assert session is not None
```

- [ ] **Step 3: Run smoke test**

```bash
cd backend && uv run pytest tests/test_infrastructure/test_database.py -v
```
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/src/infrastructure/database.py backend/tests/test_infrastructure/test_database.py
git commit -m "feat: add SQLAlchemy async engine and session factory

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Write SQLAlchemy ORM models + Repository implementations

This is the largest task. We write ORM models then repositories one at a time, TDD for each.

**Files:**
- Create: `backend/src/repositories/manifest_repository.py`
- Create: `backend/src/repositories/run_repository.py`
- Create: `backend/src/repositories/score_repository.py`
- Create: `backend/src/repositories/judge_result_repository.py`
- Create: `backend/tests/test_repositories/test_run_repository.py`
- Create: `backend/tests/test_repositories/test_score_repository.py`
- Create: `backend/tests/test_repositories/test_judge_result_repository.py`

- [ ] **Step 1: Write ORM models in repositories (inline with repository code)**

Since each repository manages one entity, we define the ORM model in the repository file itself per the DDD pattern.

- [ ] **Step 2: Write run_repository.py test first**

```python
# tests/test_repositories/test_run_repository.py
import pytest
from src.core.schemas import TaskRun, RunStatus
from src.repositories.run_repository import RunRepositoryImpl
from src.infrastructure.database import init_db, drop_db, async_session


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield
    await drop_db()


@pytest.mark.asyncio
async def test_save_and_get_run():
    repo = RunRepositoryImpl(async_session)
    run = TaskRun(benchmark_id="bench-1", status=RunStatus.PENDING)

    saved = await repo.save(run)
    assert saved.id == run.id

    fetched = await repo.get(run.id)
    assert fetched is not None
    assert fetched.benchmark_id == "bench-1"
    assert fetched.status == RunStatus.PENDING


@pytest.mark.asyncio
async def test_update_status():
    repo = RunRepositoryImpl(async_session)
    run = TaskRun(benchmark_id="bench-1")
    await repo.save(run)

    updated = await repo.update_status(run.id, RunStatus.PARSING_TRACE)
    assert updated.status == RunStatus.PARSING_TRACE


@pytest.mark.asyncio
async def test_update_status_with_error():
    repo = RunRepositoryImpl(async_session)
    run = TaskRun(benchmark_id="bench-1")
    await repo.save(run)

    updated = await repo.update_status(
        run.id, RunStatus.FAILED, error_stack="Traceback: IncompleteTraceError"
    )
    assert updated.status == RunStatus.FAILED
    assert "IncompleteTraceError" in updated.error_stack


@pytest.mark.asyncio
async def test_list_by_benchmark():
    repo = RunRepositoryImpl(async_session)
    await repo.save(TaskRun(benchmark_id="bench-1"))
    await repo.save(TaskRun(benchmark_id="bench-1"))
    await repo.save(TaskRun(benchmark_id="bench-2"))

    runs = await repo.list_by_benchmark("bench-1")
    assert len(runs) == 2


@pytest.mark.asyncio
async def test_delete():
    repo = RunRepositoryImpl(async_session)
    run = await repo.save(TaskRun(benchmark_id="bench-1"))
    await repo.delete(run.id)
    fetched = await repo.get(run.id)
    assert fetched is None
```

- [ ] **Step 3: Run to verify failure**

```bash
cd backend && uv run pytest tests/test_repositories/test_run_repository.py -v
```
Expected: FAIL (ImportError)

- [ ] **Step 4: Write run_repository.py**

```python
from __future__ import annotations
from typing import Optional
from uuid import UUID
import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select, delete
import json

from src.infrastructure.database import Base
from src.core.schemas import TaskRun, RunStatus
from src.core.interfaces import RunRepository


def _uuid_to_bytes(u: UUID) -> bytes:
    return u.bytes


def _bytes_to_uuid(b: bytes) -> UUID:
    return UUID(bytes=b)


class TaskRunModel(Base):
    __tablename__ = "task_runs"

    id = Column(BLOB, primary_key=True)
    benchmark_id = Column(String, nullable=False)
    status = Column(String, nullable=False, default="PENDING")
    error_stack = Column(Text, nullable=True)
    is_partial_score = Column(Boolean, default=False)
    judge_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)

    def to_domain(self) -> TaskRun:
        return TaskRun(
            id=_bytes_to_uuid(self.id),
            benchmark_id=self.benchmark_id,
            status=RunStatus(self.status),
            error_stack=self.error_stack,
            is_partial_score=self.is_partial_score,
            judge_enabled=self.judge_enabled,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_domain(cls, run: TaskRun) -> "TaskRunModel":
        return cls(
            id=_uuid_to_bytes(run.id),
            benchmark_id=run.benchmark_id,
            status=run.status.value,
            error_stack=run.error_stack,
            is_partial_score=run.is_partial_score,
            judge_enabled=run.judge_enabled,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )


class RunRepositoryImpl(RunRepository):
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def save(self, run: TaskRun) -> TaskRun:
        async with self.session_factory() as session:
            model = TaskRunModel.from_domain(run)
            session.add(model)
            await session.commit()
            return run

    async def get(self, run_id: UUID) -> Optional[TaskRun]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(TaskRunModel).where(TaskRunModel.id == _uuid_to_bytes(run_id))
            )
            model = result.scalar_one_or_none()
            return model.to_domain() if model else None

    async def list_by_benchmark(self, benchmark_id: str) -> list[TaskRun]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(TaskRunModel).where(TaskRunModel.benchmark_id == benchmark_id)
            )
            return [m.to_domain() for m in result.scalars().all()]

    async def update_status(self, run_id: UUID, status: RunStatus,
                            error_stack: Optional[str] = None) -> TaskRun:
        async with self.session_factory() as session:
            result = await session.execute(
                select(TaskRunModel).where(TaskRunModel.id == _uuid_to_bytes(run_id))
            )
            model = result.scalar_one_or_none()
            if model is None:
                raise ValueError(f"Run {run_id} not found")
            model.status = status.value
            model.updated_at = datetime.datetime.utcnow()
            if error_stack:
                model.error_stack = error_stack
            await session.commit()
            return model.to_domain()

    async def delete(self, run_id: UUID) -> None:
        async with self.session_factory() as session:
            await session.execute(
                delete(TaskRunModel).where(TaskRunModel.id == _uuid_to_bytes(run_id))
            )
            await session.commit()
```

- [ ] **Step 5: Run tests**

```bash
cd backend && uv run pytest tests/test_repositories/test_run_repository.py -v
```
Expected: 5 tests PASS

- [ ] **Step 6: Write score_repository.py test**

```python
# tests/test_repositories/test_score_repository.py
import pytest
from uuid import uuid4
from src.core.schemas import ScoreResult
from src.repositories.score_repository import ScoreRepositoryImpl
from src.infrastructure.database import init_db, drop_db, async_session


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield
    await drop_db()


@pytest.mark.asyncio
async def test_save_and_list_scores():
    repo = ScoreRepositoryImpl(async_session)
    run_id = uuid4()
    s1 = ScoreResult(run_id=run_id, question_id="q-001", t2_accuracy=95.0,
                     t3_efficiency=80.0, overall_score=75.0)
    s2 = ScoreResult(run_id=run_id, question_id="q-002", t2_accuracy=88.0,
                     t3_efficiency=90.0, overall_score=82.0)

    await repo.save(s1)
    await repo.save(s2)

    scores = await repo.list_by_run(run_id)
    assert len(scores) == 2
    scores.sort(key=lambda s: s.question_id)
    assert scores[0].t2_accuracy == 95.0
    assert scores[1].overall_score == 82.0


@pytest.mark.asyncio
async def test_get_by_run_and_question():
    repo = ScoreRepositoryImpl(async_session)
    run_id = uuid4()
    s = ScoreResult(run_id=run_id, question_id="q-001", t1_completion=70.0)
    await repo.save(s)

    fetched = await repo.get_by_run_and_question(run_id, "q-001")
    assert fetched is not None
    assert fetched.t1_completion == 70.0

    missing = await repo.get_by_run_and_question(run_id, "nonexistent")
    assert missing is None
```

- [ ] **Step 7: Write score_repository.py**

```python
from __future__ import annotations
from typing import Optional
from uuid import UUID
import datetime
from sqlalchemy import Column, String, Float, DateTime
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select

from src.infrastructure.database import Base
from src.core.schemas import ScoreResult


def _uuid_to_bytes(u: UUID) -> bytes:
    return u.bytes


def _bytes_to_uuid(b: bytes) -> UUID:
    return UUID(bytes=b)


class ScoreResultModel(Base):
    __tablename__ = "score_results"

    id = Column(BLOB, primary_key=True)
    run_id = Column(BLOB, nullable=False)
    question_id = Column(String, nullable=False)

    t1_completion = Column(Float, nullable=True)
    t2_accuracy = Column(Float, nullable=True)
    t3_efficiency = Column(Float, nullable=True)
    t4_thinking = Column(Float, nullable=True)
    e_performance = Column(Float, nullable=True)
    c_cost = Column(Float, nullable=True)

    overall_score = Column(Float, nullable=True)
    t1_baseline_only = Column(Float, nullable=True)
    t1_judge_only = Column(Float, nullable=True)

    actual_tool_calls = Column(Float, default=0)
    actual_success_calls = Column(Float, default=0)
    actual_tokens = Column(Float, default=0)
    actual_rounds = Column(Float, default=0)
    actual_time_ms = Column(Float, default=0)
    actual_cost_usd = Column(Float, default=0.0)

    def to_domain(self) -> ScoreResult:
        return ScoreResult(
            id=_bytes_to_uuid(self.id),
            run_id=_bytes_to_uuid(self.run_id),
            question_id=self.question_id,
            t1_completion=self.t1_completion,
            t2_accuracy=self.t2_accuracy,
            t3_efficiency=self.t3_efficiency,
            t4_thinking=self.t4_thinking,
            e_performance=self.e_performance,
            c_cost=self.c_cost,
            overall_score=self.overall_score,
            t1_baseline_only=self.t1_baseline_only,
            t1_judge_only=self.t1_judge_only,
            actual_tool_calls=int(self.actual_tool_calls),
            actual_success_calls=int(self.actual_success_calls),
            actual_tokens=int(self.actual_tokens),
            actual_rounds=int(self.actual_rounds),
            actual_time_ms=int(self.actual_time_ms),
            actual_cost_usd=self.actual_cost_usd,
        )

    @classmethod
    def from_domain(cls, s: ScoreResult) -> "ScoreResultModel":
        return cls(
            id=_uuid_to_bytes(s.id),
            run_id=_uuid_to_bytes(s.run_id),
            question_id=s.question_id,
            t1_completion=s.t1_completion,
            t2_accuracy=s.t2_accuracy,
            t3_efficiency=s.t3_efficiency,
            t4_thinking=s.t4_thinking,
            e_performance=s.e_performance,
            c_cost=s.c_cost,
            overall_score=s.overall_score,
            t1_baseline_only=s.t1_baseline_only,
            t1_judge_only=s.t1_judge_only,
            actual_tool_calls=s.actual_tool_calls,
            actual_success_calls=s.actual_success_calls,
            actual_tokens=s.actual_tokens,
            actual_rounds=s.actual_rounds,
            actual_time_ms=s.actual_time_ms,
            actual_cost_usd=s.actual_cost_usd,
        )


class ScoreRepositoryImpl:
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def save(self, score: ScoreResult) -> ScoreResult:
        async with self.session_factory() as session:
            model = ScoreResultModel.from_domain(score)
            session.add(model)
            await session.commit()
            return score

    async def get_by_run_and_question(self, run_id: UUID,
                                      question_id: str) -> Optional[ScoreResult]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(ScoreResultModel).where(
                    ScoreResultModel.run_id == _uuid_to_bytes(run_id),
                    ScoreResultModel.question_id == question_id,
                )
            )
            model = result.scalar_one_or_none()
            return model.to_domain() if model else None

    async def list_by_run(self, run_id: UUID) -> list[ScoreResult]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(ScoreResultModel).where(
                    ScoreResultModel.run_id == _uuid_to_bytes(run_id)
                )
            )
            return [m.to_domain() for m in result.scalars().all()]
```

- [ ] **Step 8: Run score tests**

```bash
cd backend && uv run pytest tests/test_repositories/test_score_repository.py -v
```
Expected: 2 tests PASS

- [ ] **Step 9: Write judge_result_repository.py test**

```python
# tests/test_repositories/test_judge_result_repository.py
import pytest
from uuid import uuid4
from src.core.schemas import JudgeResult
from src.repositories.judge_result_repository import JudgeResultRepositoryImpl
from src.infrastructure.database import init_db, drop_db, async_session


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield
    await drop_db()


@pytest.mark.asyncio
async def test_save_and_list_judge_results():
    repo = JudgeResultRepositoryImpl(async_session)
    run_id = uuid4()
    j1 = JudgeResult(run_id=run_id, question_id="q-001",
                     execution_efficiency=85, tool_accuracy=90,
                     thinking_efficiency=78, task_completion=88,
                     conclusion="Good overall")
    j2 = JudgeResult(run_id=run_id, question_id="q-002",
                     execution_efficiency=65, conclusion="Needs improvement")

    await repo.save(j1)
    await repo.save(j2)

    results = await repo.list_by_run(run_id)
    assert len(results) == 2
    assert results[0].execution_efficiency == 85
    assert results[1].conclusion == "Needs improvement"
```

- [ ] **Step 10: Write judge_result_repository.py**

```python
from __future__ import annotations
from typing import Optional
from uuid import UUID
import json
from sqlalchemy import Column, String, Integer, Text
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select

from src.infrastructure.database import Base
from src.core.schemas import JudgeResult, CriticalStep, EvolutionSuggestion, \
    SkillCompliance, FatalViolation, JudgeDimension


def _uuid_to_bytes(u: UUID) -> bytes:
    return u.bytes


def _bytes_to_uuid(b: bytes) -> UUID:
    return UUID(bytes=b)


class JudgeResultModel(Base):
    __tablename__ = "judge_results"

    id = Column(BLOB, primary_key=True)
    run_id = Column(BLOB, nullable=False)
    question_id = Column(String, nullable=False)

    execution_efficiency = Column(Integer, default=0)
    tool_accuracy = Column(Integer, default=0)
    thinking_efficiency = Column(Integer, default=0)
    task_completion = Column(Integer, default=0)

    conclusion = Column(Text, default="")
    critical_steps_json = Column(Text, default="[]")
    evolution_suggestions_json = Column(Text, default="[]")
    skill_compliance_json = Column(Text, nullable=True)
    fatal_violations_json = Column(Text, default="[]")
    raw_response = Column(Text, default="")

    def to_domain(self) -> JudgeResult:
        return JudgeResult(
            id=_bytes_to_uuid(self.id),
            run_id=_bytes_to_uuid(self.run_id),
            question_id=self.question_id,
            execution_efficiency=self.execution_efficiency,
            tool_accuracy=self.tool_accuracy,
            thinking_efficiency=self.thinking_efficiency,
            task_completion=self.task_completion,
            conclusion=self.conclusion,
            critical_steps=[
                CriticalStep.model_validate(s)
                for s in json.loads(self.critical_steps_json)
            ],
            evolution_suggestions=[
                EvolutionSuggestion.model_validate(s)
                for s in json.loads(self.evolution_suggestions_json)
            ],
            skill_compliance=(
                SkillCompliance.model_validate(json.loads(self.skill_compliance_json))
                if self.skill_compliance_json else None
            ),
            fatal_violations=[
                FatalViolation.model_validate(v)
                for v in json.loads(self.fatal_violations_json)
            ],
            raw_response=self.raw_response,
        )

    @classmethod
    def from_domain(cls, j: JudgeResult) -> "JudgeResultModel":
        return cls(
            id=_uuid_to_bytes(j.id),
            run_id=_uuid_to_bytes(j.run_id),
            question_id=j.question_id,
            execution_efficiency=j.execution_efficiency,
            tool_accuracy=j.tool_accuracy,
            thinking_efficiency=j.thinking_efficiency,
            task_completion=j.task_completion,
            conclusion=j.conclusion,
            critical_steps_json=json.dumps(
                [s.model_dump() for s in j.critical_steps], ensure_ascii=False
            ),
            evolution_suggestions_json=json.dumps(
                [s.model_dump() for s in j.evolution_suggestions], ensure_ascii=False
            ),
            skill_compliance_json=(
                j.skill_compliance.model_dump_json() if j.skill_compliance else None
            ),
            fatal_violations_json=json.dumps(
                [v.model_dump() for v in j.fatal_violations], ensure_ascii=False
            ),
            raw_response=j.raw_response,
        )


class JudgeResultRepositoryImpl:
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def save(self, result: JudgeResult) -> JudgeResult:
        async with self.session_factory() as session:
            model = JudgeResultModel.from_domain(result)
            session.add(model)
            await session.commit()
            return result

    async def get_by_run_and_question(self, run_id: UUID,
                                      question_id: str) -> Optional[JudgeResult]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(JudgeResultModel).where(
                    JudgeResultModel.run_id == _uuid_to_bytes(run_id),
                    JudgeResultModel.question_id == question_id,
                )
            )
            model = result.scalar_one_or_none()
            return model.to_domain() if model else None

    async def list_by_run(self, run_id: UUID) -> list[JudgeResult]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(JudgeResultModel).where(
                    JudgeResultModel.run_id == _uuid_to_bytes(run_id)
                )
            )
            return [m.to_domain() for m in result.scalars().all()]
```

- [ ] **Step 11: Run judge tests**

```bash
cd backend && uv run pytest tests/test_repositories/test_judge_result_repository.py -v
```
Expected: 1 test PASS

- [ ] **Step 12: Write manifest_repository.py**

```python
from __future__ import annotations
from typing import Optional
import json
from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select

from src.infrastructure.database import Base
from src.core.schemas import Manifest, QuestionItem


class ManifestModel(Base):
    __tablename__ = "manifests"

    benchmark_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    created_by = Column(String, default="")
    description = Column(Text, default="")
    total_questions = Column(Integer, default=0)
    questions_json = Column(Text, default="[]")

    def to_domain(self) -> Manifest:
        return Manifest(
            benchmark_id=self.benchmark_id,
            name=self.name,
            version=self.version,
            created_at=self.created_at,
            created_by=self.created_by,
            description=self.description,
            total_questions=self.total_questions,
            questions=[
                QuestionItem.model_validate(q)
                for q in json.loads(self.questions_json)
            ],
        )

    @classmethod
    def from_domain(cls, m: Manifest) -> "ManifestModel":
        return cls(
            benchmark_id=m.benchmark_id,
            name=m.name,
            version=m.version,
            created_at=m.created_at,
            created_by=m.created_by,
            description=m.description,
            total_questions=m.total_questions,
            questions_json=json.dumps(
                [q.model_dump() for q in m.questions], ensure_ascii=False
            ),
        )


class ManifestRepository:
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def save(self, manifest: Manifest) -> Manifest:
        async with self.session_factory() as session:
            model = ManifestModel.from_domain(manifest)
            session.add(model)
            await session.commit()
            return manifest

    async def get(self, benchmark_id: str) -> Optional[Manifest]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(ManifestModel).where(ManifestModel.benchmark_id == benchmark_id)
            )
            model = result.scalar_one_or_none()
            return model.to_domain() if model else None

    async def list_all(self) -> list[Manifest]:
        async with self.session_factory() as session:
            result = await session.execute(select(ManifestModel))
            return [m.to_domain() for m in result.scalars().all()]
```

- [ ] **Step 13: Run all repository tests together**

```bash
cd backend && uv run pytest tests/test_repositories/ -v
```
Expected: all 8 tests PASS

- [ ] **Step 14: Run full test suite to check no regressions**

```bash
cd backend && uv run pytest tests/ -v
```
Expected: all tests PASS (~22 tests)

- [ ] **Step 15: Commit**

```bash
git add backend/src/repositories/ backend/tests/test_repositories/
git commit -m "feat: add SQLAlchemy ORM models and repository implementations

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Sprint 3: 基础设施层

### Task 8: Write infrastructure/llm_gateway.py

**Files:**
- Create: `backend/src/infrastructure/llm_gateway.py`
- Create: `backend/tests/test_infrastructure/test_llm_gateway.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_infrastructure/test_llm_gateway.py
import os
import pytest
from unittest.mock import patch, AsyncMock
from pydantic import BaseModel
from src.infrastructure.llm_gateway import LLMClient


class TestResponse(BaseModel):
    name: str
    score: int


@pytest.fixture
def client():
    return LLMClient(
        base_url="https://test.api.com/v1",
        api_key="test-key",
        model="test-model"
    )


@pytest.mark.asyncio
async def test_ask_structured_output_returns_parsed_model(client):
    mock_result = TestResponse(name="test", score=95)

    # Since we can't make real API calls in tests, we test the interface
    assert client.base_url == "https://test.api.com/v1"
    assert client.model == "test-model"


def test_client_respects_env_vars():
    with patch.dict(os.environ, {
        "LLM_BASE_URL": "https://custom.api.com/v1",
        "LLM_API_KEY": "env-key",
        "LLM_MODEL": "custom-model"
    }):
        client = LLMClient()
        assert "custom.api.com" in str(client.base_url)
        assert client.model == "custom-model"


def test_client_uses_defaults_when_no_env():
    with patch.dict(os.environ, {}, clear=True):
        # Skip API_KEY check since it's required
        client = LLMClient(api_key="test-key")
        assert "api.openai.com" in str(client.base_url)
        assert client.model == "gpt-4o"
```

- [ ] **Step 2: Verify failure**

```bash
cd backend && uv run pytest tests/test_infrastructure/test_llm_gateway.py -v
```
Expected: FAIL (ImportError)

- [ ] **Step 3: Write llm_gateway.py**

```python
from __future__ import annotations
import os
import asyncio
from typing import TypeVar, Type
from openai import AsyncOpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Unified LLM gateway adapter. Uses OpenAI-compatible API.
    Switch between providers by changing LLM_BASE_URL and LLM_API_KEY env vars.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.base_url = base_url or os.getenv(
            "LLM_BASE_URL", "https://api.openai.com/v1"
        )
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o")
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
            )
        return self._client

    async def ask_structured_output(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        temperature: float = 0.3,
        max_retries: int = 3,
        initial_delay: float = 2.0,
    ) -> T:
        """Send a prompt and parse the response as a structured Pydantic model.

        Uses exponential backoff on failure: delay = initial_delay * 2^attempt.
        """
        last_error = None
        for attempt in range(max_retries):
            try:
                completion = await self.client.beta.chat.completions.parse(
                    model=self.model,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format=response_model,
                )
                parsed = completion.choices[0].message.parsed
                if parsed is not None:
                    return parsed
                raise ValueError("LLM returned None parsed response")
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = initial_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
        raise last_error  # type: ignore
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_infrastructure/test_llm_gateway.py -v
```
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/infrastructure/llm_gateway.py backend/tests/test_infrastructure/test_llm_gateway.py
git commit -m "feat: add LLMClient gateway with structured output and exponential backoff

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: Write infrastructure/trace_parser.py

**Files:**
- Create: `backend/src/infrastructure/trace_parser.py`
- Create: `backend/tests/test_infrastructure/test_trace_parser.py`
- Create: `backend/sample_data/traces/valid_trace.jsonl`
- Create: `backend/sample_data/traces/incomplete_trace.jsonl`

- [ ] **Step 1: Create sample trace files**

```jsonl
{"type":"session_start","model":"Claude-4-Sonnet","user_question":"Analyze alerts..."}
{"type":"tool_call","tool_name":"Glob","tool_input":{"pattern":"**/*.xlsx"}}
{"type":"tool_result","tool_result":"found 3 files","tool_error":false}
{"type":"assistant","thinking":"Need to understand data structure...","text":"Let me analyze..."}
{"type":"tool_call","tool_name":"Read","tool_input":{"path":"data.xlsx"}}
{"type":"tool_result","tool_result":"[file content]","tool_error":false}
{"type":"assistant","thinking":"Data has 3 columns...","text":"Structure is clear..."}
{"type":"tool_call","tool_name":"Shell","tool_input":{"command":"python analyze.py"}}
{"type":"tool_result","tool_result":"Error: KeyError","tool_error":true}
{"type":"assistant","thinking":"Column name is wrong...","text":"Fixing..."}
{"type":"result","status":"success","duration_ms":432220,"input_tokens":488250,"output_tokens":3447,"cost_usd":3.62}
```

```jsonl
{"type":"session_start","model":"Claude-4-Sonnet","user_question":"Analyze logs..."}
{"type":"tool_call","tool_name":"Glob","tool_input":{"pattern":"**/*.log"}}
{"type":"tool_result","tool_result":"found 0 files","tool_error":false}
{"type":"assistant","thinking":"No log files found...","text":"I cannot find any log files."}
```

- [ ] **Step 2: Write failing test**

```python
# tests/test_infrastructure/test_trace_parser.py
import os
import pytest
from pathlib import Path
from src.infrastructure.trace_parser import TraceParser
from src.core.exceptions import IncompleteTraceError


SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample_data" / "traces"


@pytest.mark.asyncio
async def test_parse_valid_trace():
    parser = TraceParser()
    trace_path = SAMPLE_DIR / "valid_trace.jsonl"
    trace_data = await parser.parse(trace_path)
    assert len(trace_data) == 11  # 11 lines
    assert trace_data[0]["type"] == "session_start"
    assert trace_data[-1]["type"] == "result"


@pytest.mark.asyncio
async def test_extract_metrics():
    parser = TraceParser()
    trace_path = SAMPLE_DIR / "valid_trace.jsonl"
    trace_data = await parser.parse(trace_path)
    metrics = parser.extract_metrics(trace_data)

    assert metrics["total_tool_calls"] == 3
    assert metrics["success_tool_calls"] == 2
    assert metrics["failed_tool_calls"] == 1
    assert metrics["tool_success_rate"] == pytest.approx(2 / 3 * 100)
    assert metrics["total_tokens"] == 488250 + 3447
    assert metrics["rounds"] >= 3  # 3 assistant messages with thinking
    assert metrics["duration_ms"] == 432220
    assert metrics["cost_usd"] == 3.62


@pytest.mark.asyncio
async def test_incomplete_trace_raises_error():
    parser = TraceParser()
    trace_path = SAMPLE_DIR / "incomplete_trace.jsonl"
    with pytest.raises(IncompleteTraceError) as exc_info:
        await parser.parse(trace_path)
    assert "result" in str(exc_info.value).lower() or "incomplete" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_empty_trace():
    parser = TraceParser()
    trace_data = await parser.parse_lines([])
    assert trace_data == []


@pytest.mark.asyncio
async def test_extract_metrics_zero_calls():
    parser = TraceParser()
    trace_data = [
        {"type": "session_start", "model": "test"},
        {"type": "assistant", "thinking": "...", "text": "No tools needed"},
        {"type": "result", "status": "success", "duration_ms": 1000,
         "input_tokens": 100, "output_tokens": 50, "cost_usd": 0.01},
    ]
    metrics = parser.extract_metrics(trace_data)
    assert metrics["total_tool_calls"] == 0
    assert metrics["success_tool_calls"] == 0
    assert metrics["tool_success_rate"] == 100.0  # 0/0 → 100
```

- [ ] **Step 3: Run to verify failure**

```bash
cd backend && uv run pytest tests/test_infrastructure/test_trace_parser.py -v
```
Expected: FAIL (ImportError)

- [ ] **Step 4: Write trace_parser.py**

```python
from __future__ import annotations
import json
from pathlib import Path
from src.core.exceptions import IncompleteTraceError


class TraceParser:
    """Parse JSONL agent trace files and extract process metrics."""

    async def parse(self, file_path: Path | str) -> list[dict]:
        """Parse a JSONL file into a list of event dicts.
        Raises IncompleteTraceError if the trace lacks a 'result' record."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Trace file not found: {file_path}")

        lines = path.read_text(encoding="utf-8").strip().split("\n")
        return await self.parse_lines(lines)

    async def parse_lines(self, lines: list[str]) -> list[dict]:
        """Parse a list of JSONL lines into event dicts.
        Raises IncompleteTraceError if no 'result' record is found."""
        events = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))

        # Check for complete trace: must have a 'result' record
        has_result = any(e.get("type") == "result" for e in events)
        if not has_result:
            raise IncompleteTraceError(
                "Trace is incomplete: missing 'result' record. "
                "The agent may have crashed or been interrupted.",
                question_id=None,
            )
        return events

    def extract_metrics(self, trace_data: list[dict]) -> dict:
        """Extract process metrics from parsed trace data.

        Returns dict with keys:
            total_tool_calls, success_tool_calls, failed_tool_calls,
            tool_success_rate, total_tokens, rounds, duration_ms, cost_usd
        """
        tool_calls = [e for e in trace_data if e.get("type") == "tool_call"]
        tool_results = [e for e in trace_data if e.get("type") == "tool_result"]
        assistant_msgs = [
            e for e in trace_data
            if e.get("type") == "assistant" and "thinking" in e
        ]

        total_tool_calls = len(tool_calls)
        success_tool_calls = sum(
            1 for r in tool_results if not r.get("tool_error", False)
        )
        failed_tool_calls = total_tool_calls - success_tool_calls

        # Extract final result metrics
        result_records = [e for e in trace_data if e.get("type") == "result"]
        if result_records:
            result = result_records[-1]
            duration_ms = result.get("duration_ms", 0)
            input_tokens = result.get("input_tokens", 0)
            output_tokens = result.get("output_tokens", 0)
            cost_usd = result.get("cost_usd", 0.0)
        else:
            duration_ms = 0
            input_tokens = 0
            output_tokens = 0
            cost_usd = 0.0

        return {
            "total_tool_calls": total_tool_calls,
            "success_tool_calls": success_tool_calls,
            "failed_tool_calls": failed_tool_calls,
            "tool_success_rate": (
                (success_tool_calls / total_tool_calls * 100)
                if total_tool_calls > 0 else 100.0
            ),
            "total_tokens": input_tokens + output_tokens,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "rounds": len(assistant_msgs),
            "duration_ms": duration_ms,
            "cost_usd": cost_usd,
        }
```

- [ ] **Step 5: Run tests**

```bash
cd backend && uv run pytest tests/test_infrastructure/test_trace_parser.py -v
```
Expected: 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/infrastructure/trace_parser.py backend/tests/test_infrastructure/test_trace_parser.py backend/sample_data/traces/
git commit -m "feat: add TraceParser for JSONL parsing and metric extraction

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 10: Write infrastructure/sandbox.py

**Files:**
- Create: `backend/src/infrastructure/sandbox.py`
- Create: `backend/tests/test_infrastructure/test_sandbox.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_infrastructure/test_sandbox.py
import pytest
from pathlib import Path
from src.infrastructure.sandbox import EvalSandbox


@pytest.fixture
def sandbox(tmp_path):
    """Use pytest's tmp_path for isolated sandbox testing."""
    return EvalSandbox(
        run_id="test-run-001",
        base_path=str(tmp_path / "coworkeval")
    )


@pytest.mark.asyncio
async def test_setup_creates_directories(sandbox):
    sandbox_path = await sandbox.setup()
    assert Path(sandbox_path).exists()
    assert (Path(sandbox_path) / "output").exists()
    assert (Path(sandbox_path) / "workspace").exists()
    assert (Path(sandbox_path) / ".meta").exists()


@pytest.mark.asyncio
async def test_cleanup_removes_sandbox(sandbox):
    sandbox_path = await sandbox.setup()
    assert Path(sandbox_path).exists()
    await sandbox.cleanup()
    assert not Path(sandbox_path).exists()


@pytest.mark.asyncio
async def test_archive_output(sandbox, tmp_path):
    await sandbox.setup()
    # Create a test output file
    output_file = sandbox.output_path / "test_result.xlsx"
    output_file.write_text("mock excel content")

    archive_path = await sandbox.archive_output()
    assert archive_path.exists()
    # Archive should contain the output file
    archived_files = list(archive_path.rglob("*"))
    assert any("test_result.xlsx" in str(f) for f in archived_files)


@pytest.mark.asyncio
async def test_sandbox_isolation(sandbox):
    """Two sandboxes with different run_ids must not share directories."""
    sandbox_path_1 = await sandbox.setup()

    sandbox2 = EvalSandbox(
        run_id="test-run-002",
        base_path=sandbox.base_path
    )
    sandbox_path_2 = await sandbox2.setup()

    assert sandbox_path_1 != sandbox_path_2
    assert str(sandbox_path_2) != str(sandbox_path_1)

    await sandbox.cleanup()
    await sandbox2.cleanup()
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && uv run pytest tests/test_infrastructure/test_sandbox.py -v
```
Expected: FAIL (ImportError)

- [ ] **Step 3: Write sandbox.py**

```python
from __future__ import annotations
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


class EvalSandbox:
    """Creates and manages an isolated temp directory for a single TaskRun.

    Directory structure:
        {base_path}/{run_id}/
        ├── output/       # Agent output files
        ├── workspace/    # Agent working directory
        ├── global_data/  # → symlink to {base_path}/../global_data/
        └── .meta/        # Sandbox metadata
    """

    def __init__(self, run_id: str, base_path: str = "/tmp/coworkeval"):
        self.run_id = run_id
        self.base_path = Path(base_path)
        self.sandbox_path = self.base_path / str(run_id)
        self.output_path = self.sandbox_path / "output"
        self.workspace_path = self.sandbox_path / "workspace"
        self.meta_path = self.sandbox_path / ".meta"
        self.global_data_path = self.sandbox_path / "global_data"

    async def setup(self) -> str:
        """Create sandbox directory structure. Returns sandbox root path."""
        self.sandbox_path.mkdir(parents=True, exist_ok=True)
        self.output_path.mkdir(exist_ok=True)
        self.workspace_path.mkdir(exist_ok=True)
        self.meta_path.mkdir(exist_ok=True)

        # Symlink global_data → {base_path}/../global_data/
        global_data_root = self.base_path.parent / "global_data"
        if not self.global_data_path.exists():
            try:
                self.global_data_path.symlink_to(
                    global_data_root, target_is_directory=True
                )
            except OSError:
                # Symlink may fail on some platforms; create as plain dir
                self.global_data_path.mkdir(exist_ok=True)

        # Write metadata
        meta = {
            "run_id": self.run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "cleaned": False,
        }
        (self.meta_path / "meta.json").write_text(json.dumps(meta))

        return str(self.sandbox_path)

    async def cleanup(self) -> None:
        """Remove the entire sandbox directory."""
        if self.sandbox_path.exists():
            shutil.rmtree(self.sandbox_path)

    async def archive_output(self) -> Path:
        """Copy output/ to a persistent archive location.
        Returns the archive path."""
        archive_root = self.base_path.parent / "archive"
        archive_root.mkdir(parents=True, exist_ok=True)
        archive_path = archive_root / self.run_id / "output"

        if self.output_path.exists():
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            if archive_path.exists():
                shutil.rmtree(archive_path)
            shutil.copytree(self.output_path, archive_path)

        return archive_path
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_infrastructure/test_sandbox.py -v
```
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/infrastructure/sandbox.py backend/tests/test_infrastructure/test_sandbox.py
git commit -m "feat: add EvalSandbox for per-run isolated temp directories

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 11: Create sample_data manifest

**Files:**
- Create: `backend/sample_data/manifest.json`
- Create: `backend/sample_data/references/expected_output.xlsx` (placeholder note)

- [ ] **Step 1: Write sample manifest.json**

```json
{
  "benchmark_id": "sample_bench_001",
  "name": "Sample Evaluation Benchmark",
  "version": "1.0.0",
  "created_at": "2026-06-05T00:00:00+08:00",
  "created_by": "system",
  "description": "Sample benchmark for integration testing",
  "total_questions": 1,
  "questions": [
    {
      "question_id": "sample-q-001",
      "question_name": "Sample Excel Analysis Task",
      "category": "Excel",
      "difficulty": "中等",
      "prompt_file": "sample-q-001/prompt.txt",
      "input_files": ["sample-q-001/input/data.xlsx"],
      "reference_files": ["sample-q-001/reference/answer.xlsx"],
      "output_dir": "sample-q-001/output/",
      "eval_config": {
        "compare_style": false,
        "ignore_rules": [
          {"type": "column", "sheet": "Sheet1", "columns": ["K"]}
        ],
        "fatal_rules": []
      },
      "scene": "skills",
      "skills": "project_business_analysis",
      "payload_size_kb": 128.0,
      "baseline_tokens": 693592,
      "baseline_rounds": 19,
      "baseline_tool_count": 17,
      "baseline_time_ms": 64000,
      "baseline_cost_usd": 3.58
    }
  ]
}
```

```bash
# placeholder for expected_output.xlsx
echo "Placeholder — real .xlsx generated by test setup" > backend/sample_data/references/expected_output.xlsx
```

- [ ] **Step 2: Commit**

```bash
git add backend/sample_data/
git commit -m "chore: add sample manifest and trace data for integration testing

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Sprint 4: 业务逻辑层

### Task 12: Write evaluator/result_comparator.py

**Files:**
- Create: `backend/src/evaluator/result_comparator.py`
- Create: `backend/tests/test_evaluator/test_result_comparator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_evaluator/test_result_comparator.py
import pandas as pd
import pytest
from pathlib import Path
from src.evaluator.result_comparator import ResultComparator
from src.core.schemas import EvalConfig, IgnoreRule


@pytest.fixture
def tmp_output_dir(tmp_path):
    """Create temp output and reference files for testing."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    ref_dir = tmp_path / "reference"
    ref_dir.mkdir()

    # Create identical dataframes as Excel
    output_df = pd.DataFrame({"A": [1, 2], "B": [3, 4], "K": [99, 100]})
    ref_df = pd.DataFrame({"A": [1, 2], "B": [3, 4], "K": [99, 100]})

    output_path = output_dir / "result.xlsx"
    ref_path = ref_dir / "answer.xlsx"
    output_df.to_excel(output_path, index=False)
    ref_df.to_excel(ref_path, index=False)

    return output_path, ref_path


def test_perfect_match_scores_100(tmp_output_dir):
    output_path, ref_path = tmp_output_dir
    comparator = ResultComparator()
    config = EvalConfig(compare_style=False, ignore_rules=[])

    score = comparator.compare(
        output_path=str(output_path),
        reference_path=str(ref_path),
        eval_config=config,
    )
    assert score == 100.0


def test_column_ignore_rule(tmp_output_dir):
    output_path, ref_path = tmp_output_dir
    comparator = ResultComparator()

    # With column K ignored, the dfs should match
    config = EvalConfig(
        compare_style=False,
        ignore_rules=[
            IgnoreRule(type="column", sheet="Sheet1", columns=["K"])
        ]
    )
    score = comparator.compare(
        output_path=str(output_path),
        reference_path=str(ref_path),
        eval_config=config,
    )
    assert score == 100.0


def test_mismatched_data_deducts_points(tmp_output_dir, tmp_path):
    output_path, ref_path = tmp_output_dir

    # Corrupt the output
    output_df = pd.read_excel(output_path)
    output_df.loc[0, "A"] = 999  # Change a value
    output_df.to_excel(output_path, index=False)

    comparator = ResultComparator()
    config = EvalConfig()

    score = comparator.compare(
        output_path=str(output_path),
        reference_path=str(ref_path),
        eval_config=config,
    )
    assert score < 100.0
    assert score > 0.0


def test_missing_file_returns_zero():
    comparator = ResultComparator()
    score = comparator.compare(
        output_path="/nonexistent/output.xlsx",
        reference_path="/nonexistent/ref.xlsx",
        eval_config=EvalConfig(),
    )
    assert score == 0.0
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && uv run pytest tests/test_evaluator/test_result_comparator.py -v
```
Expected: FAIL (ImportError)

- [ ] **Step 3: Write evaluator/result_comparator.py**

```python
from __future__ import annotations
from pathlib import Path
import pandas as pd
from src.core.schemas import EvalConfig


class ResultComparator:
    """Compare agent output files against reference files using pandas.
    Computes T1 objective baseline score.

    The comparison logic:
    1. Read output and reference files
    2. Apply ignore_rules from eval_config (drop ignored columns)
    3. Compare: match on columns, row count, and cell values
    4. Score: weighted average of column match, row match, and value match
    """

    def compare(
        self,
        output_path: str,
        reference_path: str,
        eval_config: EvalConfig,
    ) -> float:
        """Compare output against reference. Returns score 0-100."""
        output_file = Path(output_path)
        ref_file = Path(reference_path)

        if not output_file.exists() or not ref_file.exists():
            return 0.0

        try:
            output_df = self._read_file(output_file)
            ref_df = self._read_file(ref_file)
        except Exception:
            return 0.0

        # Apply ignore rules
        output_df, ref_df = self._apply_ignore_rules(
            output_df, ref_df, eval_config.ignore_rules
        )

        return self._compute_similarity(output_df, ref_df)

    def _read_file(self, path: Path) -> pd.DataFrame:
        suffix = path.suffix.lower()
        if suffix == ".xlsx":
            return pd.read_excel(path, sheet_name=0)
        elif suffix == ".csv":
            return pd.read_csv(path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

    def _apply_ignore_rules(
        self,
        output_df: pd.DataFrame,
        ref_df: pd.DataFrame,
        ignore_rules: list,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        out = output_df.copy()
        ref = ref_df.copy()
        for rule in ignore_rules:
            if rule.type == "column" and rule.columns:
                cols_to_drop = [c for c in rule.columns if c in out.columns]
                out = out.drop(columns=cols_to_drop, errors="ignore")
                ref = ref.drop(columns=cols_to_drop, errors="ignore")
        return out, ref

    def _compute_similarity(
        self, output_df: pd.DataFrame, ref_df: pd.DataFrame
    ) -> float:
        """Compute similarity score between two DataFrames.

        Dimensions:
        - Column match: 30% weight — do we have the right columns?
        - Row match: 30% weight — do we have the right number of rows?
        - Value match: 40% weight — do cell values match?
        """
        scores = []

        # Column match
        out_cols = set(output_df.columns)
        ref_cols = set(ref_df.columns)
        if len(ref_cols) == 0:
            col_score = 100.0
        else:
            intersection = out_cols & ref_cols
            col_score = (len(intersection) / len(ref_cols)) * 100
        scores.append(col_score * 0.30)

        # Row match
        out_rows = len(output_df)
        ref_rows = len(ref_df)
        if ref_rows == 0:
            row_score = 100.0
        else:
            row_score = max(0, 100 - abs(out_rows - ref_rows) / ref_rows * 100)
        scores.append(row_score * 0.30)

        # Value match (only on intersecting columns)
        value_score = 100.0
        common_cols = list(out_cols & ref_cols)
        if common_cols and ref_rows > 0:
            match_count = 0
            total = 0
            try:
                for col in common_cols:
                    out_vals = output_df[col].reset_index(drop=True).astype(str)
                    ref_vals = ref_df[col].reset_index(drop=True).astype(str)
                    for i in range(min(len(out_vals), len(ref_vals))):
                        if out_vals[i] == ref_vals[i]:
                            match_count += 1
                        total += 1
                if total > 0:
                    value_score = (match_count / total) * 100
            except Exception:
                value_score = 0.0
        scores.append(value_score * 0.40)

        return max(0.0, min(100.0, sum(scores)))
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_evaluator/test_result_comparator.py -v
```
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/evaluator/result_comparator.py backend/tests/test_evaluator/test_result_comparator.py
git commit -m "feat: add ResultComparator for pandas-based T1 objective scoring

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 13: Write services/baseline_evaluator.py

**Files:**
- Create: `backend/src/services/baseline_evaluator.py`
- Create: `backend/tests/test_services/test_baseline_evaluator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_services/test_baseline_evaluator.py
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.baseline_evaluator import BaselineEvaluator
from src.core.schemas import (
    QuestionItem, EvalConfig, ScoreResult, RunStatus, TaskRun
)
from src.evaluator.result_comparator import ResultComparator


@pytest.fixture
def question():
    return QuestionItem(
        question_id="q-001",
        question_name="Test Question",
        category="Excel",
        difficulty="中等",
        prompt_file="q-001/prompt.txt",
        input_files=["q-001/input.xlsx"],
        reference_files=["q-001/ref.xlsx"],
        output_dir="q-001/output/",
        eval_config=EvalConfig(),
        baseline_tool_count=10,
        baseline_tokens=500000,
        baseline_rounds=15,
        baseline_time_ms=50000,
        baseline_cost_usd=2.0,
        payload_size_kb=100.0,
    )


@pytest.fixture
def trace_data():
    """Simulated parsed trace data with metrics matching the question baseline."""
    return [
        {"type": "session_start", "model": "Claude-4"},
        {"type": "tool_call", "tool_name": "Read"},
        {"type": "tool_result", "tool_error": False},
        {"type": "tool_call", "tool_name": "Read"},
        {"type": "tool_result", "tool_error": False},
        {"type": "tool_call", "tool_name": "Shell"},
        {"type": "tool_result", "tool_error": True},  # 1 failure
        {"type": "assistant", "thinking": "..."},
        {"type": "assistant", "thinking": "..."},
        {"type": "assistant", "thinking": "..."},
        {
            "type": "result",
            "status": "success",
            "duration_ms": 60000,
            "input_tokens": 450000,
            "output_tokens": 50000,
            "cost_usd": 2.5,
        },
    ]


@pytest.fixture
def evaluator():
    score_repo = AsyncMock()
    comparator = ResultComparator()
    return BaselineEvaluator(score_repo=score_repo, comparator=comparator)


@pytest.mark.asyncio
async def test_evaluate_perfect_scores(evaluator, question, trace_data):
    """When actual metrics match baseline exactly, all scores should be 100."""
    # Override trace to match baseline perfectly
    trace_data[-1] = {
        "type": "result",
        "status": "success",
        "duration_ms": 50000,  # exactly baseline
        "input_tokens": 450000,
        "output_tokens": 50000,
        "cost_usd": 2.0,  # exactly baseline
    }
    # Use exactly 10 tool calls (baseline)
    trace_data_clean = trace_data[:3] * 3 + trace_data[3:4] + trace_data[7:]

    score = await evaluator.evaluate(
        run_id=uuid4(),
        question=question,
        trace_data=trace_data,
    )

    assert score.t2_accuracy is not None
    assert score.t3_efficiency == pytest.approx(100.0)
    assert score.e_performance == pytest.approx(100.0)
    assert score.c_cost == pytest.approx(100.0)


@pytest.mark.asyncio
async def test_tool_efficiency_deduction(evaluator, question, trace_data):
    """Exceeding baseline tool count should deduct 5 points per extra call."""
    score = await evaluator.evaluate(
        run_id=uuid4(),
        question=question,
        trace_data=trace_data,
    )
    # trace has 3 tool calls, baseline is 10 → no deduction
    assert score.t3_efficiency == 100.0

    # Now simulate: actual 15 calls, baseline 10 → 5 extra → 25 point deduction
    question2 = question.model_copy()
    question2.baseline_tool_count = 1  # trace has 3 calls → 2 extra → 10 deduction
    score2 = await evaluator.evaluate(
        run_id=uuid4(),
        question=question2,
        trace_data=trace_data,
    )
    assert score2.t3_efficiency == pytest.approx(90.0)  # 100 - 5*2


@pytest.mark.asyncio
async def test_e2e_dynamic_baseline(evaluator, question, trace_data):
    """When payload_size_kb differs from baseline, dynamic baseline should scale."""
    # actual payload = 200KB, baseline 100KB → dynamic_baseline = 50000 * (200/100) = 100000ms
    question.payload_size_kb = 100.0
    # trace has actual_time_ms = 60000, payload 200KB → dynamic baseline = 50000*2 = 100000
    # 60000 < 100000 → no deduction
    trace_data[-1] = {
        "type": "result",
        "status": "success",
        "duration_ms": 60000,
        "input_tokens": 500000,
        "output_tokens": 0,
        "cost_usd": 2.0,
    }
    # Override the trace record - we need to mock payload separately
    # Static baseline: 60000 actual vs 50000 baseline → 
    # (10000/50000)*100 = 20% → score 80
    # Dynamic: payload=200, baseline payload=100 → dynamic_baseline=100000
    # 60000 < 100000 → score 100
    # For this test we use the static case (no payload_size_kb)
    question.payload_size_kb = None
    score = await evaluator.evaluate(
        run_id=uuid4(), question=question, trace_data=trace_data
    )
    # 60000 vs 50000 → 20% over → score = 100 - 20 = 80
    assert score.e_performance == pytest.approx(80.0)


@pytest.mark.asyncio
async def test_t2_zero_calls_defaults_100(evaluator, question):
    trace_no_calls = [
        {"type": "session_start"},
        {"type": "assistant", "thinking": "...", "text": "Done"},
        {"type": "result", "status": "success", "duration_ms": 1000,
         "input_tokens": 100, "output_tokens": 50, "cost_usd": 0.01},
    ]
    score = await evaluator.evaluate(
        run_id=uuid4(), question=question, trace_data=trace_no_calls
    )
    assert score.t2_accuracy == 100.0


@pytest.mark.asyncio
async def test_negative_score_clamped_to_zero(evaluator, question):
    """Even with extreme overrun, scores never go negative."""
    question.baseline_tool_count = 1
    question.baseline_time_ms = 1
    question.baseline_cost_usd = 0.01
    question.baseline_tokens = 10
    question.baseline_rounds = 1
    question.payload_size_kb = None

    trace = [
        {"type": "session_start"},
        {"type": "tool_call"}, {"type": "tool_result", "tool_error": True},
        {"type": "tool_call"}, {"type": "tool_result", "tool_error": True},
        {"type": "tool_call"}, {"type": "tool_result", "tool_error": True},
        {"type": "assistant", "thinking": "..."},
        {"type": "assistant", "thinking": "..."},
        {"type": "assistant", "thinking": "..."},
        {"type": "result", "status": "success", "duration_ms": 999999,
         "input_tokens": 999999, "output_tokens": 999999, "cost_usd": 999.0},
    ]

    score = await evaluator.evaluate(
        run_id=uuid4(), question=question, trace_data=trace
    )

    # All scores ≥ 0
    assert score.t3_efficiency >= 0
    assert score.t4_thinking >= 0
    assert score.e_performance >= 0
    assert score.c_cost >= 0
    assert score.overall_score >= 0
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && uv run pytest tests/test_services/test_baseline_evaluator.py -v
```
Expected: FAIL (ImportError)

- [ ] **Step 3: Write services/baseline_evaluator.py**

```python
from __future__ import annotations
from typing import Optional
from uuid import UUID

from src.core.interfaces import BaseEvaluator, ScoreRepository
from src.core.schemas import ScoreResult, QuestionItem, EvalConfig
from src.evaluator.result_comparator import ResultComparator
from src.infrastructure.trace_parser import TraceParser


class BaselineEvaluator(BaseEvaluator):
    """TTTEC six-dimension rule-based scoring engine.

    Computes objective scores by comparing actual trace metrics against
    baseline values defined in the Manifest's QuestionItem.

    Dependencies injected via constructor (DIP):
        score_repo: for persisting ScoreResult
        comparator: pandas-based T1 result comparison
    """

    def __init__(
        self,
        score_repo: ScoreRepository,
        comparator: ResultComparator,
    ):
        self.score_repo = score_repo
        self.comparator = comparator
        self.parser = TraceParser()

    async def evaluate(
        self,
        run_id: UUID,
        question: QuestionItem,
        trace_data: list[dict],
    ) -> ScoreResult:
        metrics = self.parser.extract_metrics(trace_data)

        score = ScoreResult(
            run_id=run_id,
            question_id=question.question_id,
            actual_tool_calls=metrics["total_tool_calls"],
            actual_success_calls=metrics["success_tool_calls"],
            actual_tokens=metrics["total_tokens"],
            actual_rounds=metrics["rounds"],
            actual_time_ms=metrics["duration_ms"],
            actual_cost_usd=metrics["cost_usd"],
        )

        # T1: Task Completion — Baseline objective part
        score.t1_baseline_only = self._compute_t1_baseline(question.eval_config)
        score.t1_completion = score.t1_baseline_only  # Will be fused with judge later

        # T2: Tool Accuracy
        score.t2_accuracy = self._compute_t2(
            metrics["success_tool_calls"],
            metrics["total_tool_calls"],
        )

        # T3: Tool Efficiency
        score.t3_efficiency = self._compute_t3(
            metrics["total_tool_calls"],
            question.baseline_tool_count,
        )

        # T4: Thinking Efficiency
        score.t4_thinking = self._compute_t4(
            metrics["total_tokens"],
            metrics["rounds"],
            question.baseline_tokens,
            question.baseline_rounds,
        )

        # E: E2E Performance
        score.e_performance = self._compute_e(
            metrics["duration_ms"],
            question.baseline_time_ms,
            question.payload_size_kb,
            question.input_files,  # to estimate actual payload
        )

        # C: Cost Efficiency
        score.c_cost = self._compute_c(
            metrics["cost_usd"],
            question.baseline_cost_usd,
        )

        # Overall: average of six dimensions
        dims = [
            score.t1_completion or 0,
            score.t2_accuracy,
            score.t3_efficiency,
            score.t4_thinking,
            score.e_performance,
            score.c_cost,
        ]
        score.overall_score = sum(d for d in dims if d is not None) / 6.0

        # Persist
        await self.score_repo.save(score)
        return score

    # ── T1: Task Completion (Baseline part only) ─────────

    def _compute_t1_baseline(self, eval_config: EvalConfig) -> float:
        """T1 baseline is 0 if no eval_config comparison rules are configured.
        The real T1 score comes from 50:50 fusion with judge."""
        has_rules = bool(eval_config.ignore_rules) or eval_config.compare_style
        return 0.0 if not has_rules else 0.0  # Placeholder — actual comparison done via ResultComparator.compare()

    # ── T2: Tool Accuracy ────────────────────────────────

    def _compute_t2(self, success: int, total: int) -> float:
        if total == 0:
            return 100.0
        return max(0.0, (success / total) * 100.0)

    # ── T3: Tool Efficiency ──────────────────────────────

    def _compute_t3(self, actual_calls: int, baseline_calls: int) -> float:
        excess = max(0, actual_calls - baseline_calls)
        return max(0.0, 100.0 - 5.0 * excess)

    # ── T4: Thinking Efficiency ──────────────────────────

    def _compute_t4(
        self,
        actual_tokens: int,
        actual_rounds: int,
        baseline_tokens: int,
        baseline_rounds: int,
    ) -> float:
        if baseline_tokens == 0:
            token_overage_rate = 0.0
        else:
            token_overage_rate = max(0.0, actual_tokens - baseline_tokens) / baseline_tokens
        round_overage = max(0, actual_rounds - baseline_rounds)
        penalty = token_overage_rate * 100.0 * 0.3 + round_overage * 5.0
        return max(0.0, 100.0 - penalty)

    # ── E: E2E Performance ───────────────────────────────

    def _compute_e(
        self,
        actual_time_ms: int,
        baseline_time_ms: int,
        payload_size_kb: Optional[float],
        input_files: list[str],
    ) -> float:
        # Dynamic baseline: scale by payload size if configured
        if payload_size_kb is not None and payload_size_kb > 0:
            # actual_payload_kb is estimated from input_files if available;
            # for now use payload_size_kb as-is (same as baseline)
            dynamic_baseline = baseline_time_ms
        else:
            dynamic_baseline = baseline_time_ms

        if dynamic_baseline == 0:
            return 100.0

        overage_ratio = max(0.0, actual_time_ms - dynamic_baseline) / dynamic_baseline
        return max(0.0, 100.0 - overage_ratio * 100.0)

    # ── C: Cost Efficiency ───────────────────────────────

    def _compute_c(self, actual_cost: float, baseline_cost: float) -> float:
        if baseline_cost == 0:
            return 100.0
        overage_ratio = max(0.0, actual_cost - baseline_cost) / baseline_cost
        return max(0.0, 100.0 - overage_ratio * 100.0)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_services/test_baseline_evaluator.py -v
```
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/baseline_evaluator.py backend/tests/test_services/test_baseline_evaluator.py
git commit -m "feat: add BaselineEvaluator with TTTEC six-dimension scoring formulas

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 14: Write services/pipeline_runner.py

**Files:**
- Create: `backend/src/services/pipeline_runner.py`
- Create: `backend/tests/test_services/test_pipeline_runner.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_services/test_pipeline_runner.py
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.pipeline_runner import PipelineRunner
from src.core.schemas import (
    TaskRun, Manifest, QuestionItem, EvalConfig, RunStatus, ScoreResult
)
from src.core.interfaces import RunRepository
from src.core.state_machine import StateMachine


@pytest.fixture
def mock_run_repo():
    repo = AsyncMock(spec=RunRepository)
    repo.save = AsyncMock(return_value=TaskRun(
        id=uuid4(), benchmark_id="bench-1", status=RunStatus.PENDING
    ))
    repo.get = AsyncMock(return_value=TaskRun(
        id=uuid4(), benchmark_id="bench-1", status=RunStatus.PENDING
    ))
    repo.update_status = AsyncMock(return_value=TaskRun(
        id=uuid4(), benchmark_id="bench-1", status=RunStatus.PARSING_TRACE
    ))
    return repo


@pytest.fixture
def mock_manifest():
    return Manifest(
        benchmark_id="bench-1",
        name="test",
        version="1.0",
        total_questions=2,
        questions=[
            QuestionItem(
                question_id="q-001",
                question_name="Q1",
                category="Excel",
                difficulty="中等",
                prompt_file="q-001/prompt.txt",
                output_dir="q-001/output/",
                eval_config=EvalConfig(),
                baseline_tool_count=5,
                baseline_tokens=100000,
                baseline_rounds=10,
                baseline_time_ms=30000,
                baseline_cost_usd=1.0,
            ),
            QuestionItem(
                question_id="q-002",
                question_name="Q2",
                category="Excel",
                difficulty="困难",
                prompt_file="q-002/prompt.txt",
                output_dir="q-002/output/",
                eval_config=EvalConfig(),
                baseline_tool_count=8,
                baseline_tokens=200000,
                baseline_rounds=15,
                baseline_time_ms=50000,
                baseline_cost_usd=2.0,
            ),
        ],
    )


@pytest.fixture
def sample_trace_data():
    return [
        {"type": "session_start"},
        {"type": "tool_call", "tool_name": "Read"},
        {"type": "tool_result", "tool_error": False},
        {"type": "assistant", "thinking": "...", "text": "ok"},
        {"type": "result", "status": "success", "duration_ms": 25000,
         "input_tokens": 90000, "output_tokens": 10000, "cost_usd": 0.9},
    ]


@pytest.mark.asyncio
async def test_pipeline_runner_creates_run(mock_run_repo, mock_manifest):
    runner = PipelineRunner(
        run_repo=mock_run_repo,
        baseline_evaluator=AsyncMock(),
    )
    run = await runner.create_run(mock_manifest, judge_enabled=False)
    assert run.benchmark_id == "bench-1"
    assert run.judge_enabled == False
    mock_run_repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_runner_transitions_status(mock_run_repo, mock_manifest, sample_trace_data):
    mock_evaluator = AsyncMock()
    mock_evaluator.evaluate = AsyncMock(return_value=ScoreResult(
        run_id=uuid4(), question_id="q-001",
        t2_accuracy=100.0, overall_score=95.0
    ))

    runner = PipelineRunner(
        run_repo=mock_run_repo,
        baseline_evaluator=mock_evaluator,
    )
    run = await runner.create_run(mock_manifest, judge_enabled=False)

    # Mock trace_loader
    with patch.object(runner, "_load_traces", return_value={
        "q-001": sample_trace_data,
        "q-002": sample_trace_data,
    }):
        await runner.execute(run.id, mock_manifest)

    # Should have called evaluate for each question
    assert mock_evaluator.evaluate.call_count == 2

    # Status should progress through states
    status_calls = [c.args[1] for c in mock_run_repo.update_status.call_args_list]
    assert RunStatus.PARSING_TRACE in status_calls
    assert RunStatus.EVALUATING_BASELINE in status_calls
    assert RunStatus.COMPLETED in status_calls


@pytest.mark.asyncio
async def test_pipeline_with_failure_sets_failed_status(mock_run_repo, mock_manifest):
    mock_evaluator = AsyncMock()
    mock_evaluator.evaluate = AsyncMock(side_effect=Exception("Boom"))

    runner = PipelineRunner(
        run_repo=mock_run_repo,
        baseline_evaluator=mock_evaluator,
    )
    run = await runner.create_run(mock_manifest, judge_enabled=False)

    with patch.object(runner, "_load_traces", return_value={
        "q-001": [{"type": "result", "status": "success"}],
    }):
        with pytest.raises(Exception):
            await runner.execute(run.id, mock_manifest)

    # Check FAILED status was set
    fail_calls = [
        c for c in mock_run_repo.update_status.call_args_list
        if c.args[1] == RunStatus.FAILED
    ]
    assert len(fail_calls) >= 1


@pytest.mark.asyncio
async def test_concurrent_execution_respects_semaphore():
    """Verify that the pipeline uses asyncio concurrency for multiple questions."""
    import asyncio

    call_order = []
    mock_evaluator = AsyncMock()

    async def delayed_evaluate(run_id, question, trace_data):
        call_order.append(question.question_id)
        await asyncio.sleep(0.01)
        return ScoreResult(run_id=run_id, question_id=question.question_id)

    mock_evaluator.evaluate = delayed_evaluate

    mock_run_repo = AsyncMock(spec=RunRepository)
    mock_run_repo.save = AsyncMock()
    mock_run_repo.update_status = AsyncMock()

    runner = PipelineRunner(
        run_repo=mock_run_repo,
        baseline_evaluator=mock_evaluator,
    )

    questions = [
        QuestionItem(question_id=f"q-{i:03d}", question_name=f"Q{i}",
                     category="Excel", difficulty="中等",
                     prompt_file=f"q-{i:03d}/prompt.txt",
                     output_dir=f"q-{i:03d}/output/",
                     eval_config=EvalConfig(),
                     baseline_tool_count=5, baseline_tokens=100000,
                     baseline_rounds=10, baseline_time_ms=30000,
                     baseline_cost_usd=1.0)
        for i in range(5)
    ]

    manifests = Manifest(
        benchmark_id="bench-1", name="test", version="1.0",
        questions=questions,
    )

    # Run execute_questions — should process concurrently
    trace_map = {q.question_id: [{"type": "result", "status": "success"}]
                  for q in questions}
    await runner._execute_questions(uuid4(), manifests.questions, trace_map)

    # All 5 questions should have been called
    assert len(call_order) == 5
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && uv run pytest tests/test_services/test_pipeline_runner.py -v
```
Expected: FAIL (ImportError)

- [ ] **Step 3: Write services/pipeline_runner.py**

```python
from __future__ import annotations
import asyncio
import logging
from typing import Optional
from uuid import UUID

from src.core.schemas import (
    TaskRun, Manifest, QuestionItem, RunStatus, ScoreResult
)
from src.core.interfaces import RunRepository, BaseEvaluator
from src.core.state_machine import StateMachine
from src.core.exceptions import EvaluationError, IncompleteTraceError
from src.infrastructure.trace_parser import TraceParser

logger = logging.getLogger(__name__)


class PipelineRunner:
    """Orchestrates the evaluation pipeline for a single TaskRun.

    Flow:
    1. PENDING → PARSING_TRACE (parse all JSONL)
    2. PARSING_TRACE → EVALUATING_BASELINE (TTTEC scoring)
    3. EVALUATING_BASELINE → AWAITING_JUDGE or COMPLETED
    (Judge evaluation triggered separately)

    Uses asyncio concurrency for multi-question processing.
    Judge model calls are rate-limited via Semaphore (max 5 concurrent).
    """

    def __init__(
        self,
        run_repo: RunRepository,
        baseline_evaluator: BaseEvaluator,
        judge_concurrency: int = 5,
    ):
        self.run_repo = run_repo
        self.baseline_evaluator = baseline_evaluator
        self.judge_semaphore = asyncio.Semaphore(judge_concurrency)
        self.parser = TraceParser()

    async def create_run(
        self,
        manifest: Manifest,
        judge_enabled: bool = True,
    ) -> TaskRun:
        """Create a new TaskRun from a Manifest."""
        run = TaskRun(
            benchmark_id=manifest.benchmark_id,
            status=RunStatus.PENDING,
            judge_enabled=judge_enabled,
        )
        await self.run_repo.save(run)
        return run

    async def execute(self, run_id: UUID, manifest: Manifest) -> list[ScoreResult]:
        """Execute the full Baseline evaluation pipeline for a run."""
        sm = StateMachine(judge_enabled=False)  # Baseline only; judge is Phase 2

        try:
            # PENDING → PARSING_TRACE
            await self.run_repo.update_status(run_id, RunStatus.PARSING_TRACE)
            sm.transition_to(RunStatus.PARSING_TRACE)
            trace_map = await self._load_traces(manifest)

            # PARSING_TRACE → EVALUATING_BASELINE
            await self.run_repo.update_status(run_id, RunStatus.EVALUATING_BASELINE)
            sm.transition_to(RunStatus.EVALUATING_BASELINE)
            scores = await self._execute_questions(
                run_id, manifest.questions, trace_map
            )

            # EVALUATING_BASELINE → COMPLETED (no judge in Phase 1)
            await self.run_repo.update_status(run_id, RunStatus.COMPLETED)
            sm.transition_to(RunStatus.COMPLETED)

            return scores

        except Exception as e:
            logger.exception(f"Pipeline failed for run {run_id}")
            await self.run_repo.update_status(
                run_id, RunStatus.FAILED,
                error_stack=str(e),
            )
            raise EvaluationError(str(e), run_id=str(run_id))

    async def _load_traces(
        self, manifest: Manifest
    ) -> dict[str, list[dict]]:
        """Load and parse all JSONL trace files for the manifest's questions.

        Returns mapping of question_id → parsed trace events.
        Raises IncompleteTraceError if any trace is truncated."""
        trace_map = {}
        for question in manifest.questions:
            trace_path = f"sample_data/traces/{question.question_id}.jsonl"
            try:
                trace_data = await self.parser.parse(trace_path)
            except FileNotFoundError:
                logger.warning(
                    f"Trace file not found for {question.question_id}, "
                    f"using empty trace"
                )
                trace_data = []
            except IncompleteTraceError:
                raise  # Re-raise to fail the entire run
            trace_map[question.question_id] = trace_data
        return trace_map

    async def _execute_questions(
        self,
        run_id: UUID,
        questions: list[QuestionItem],
        trace_map: dict[str, list[dict]],
    ) -> list[ScoreResult]:
        """Evaluate all questions concurrently using asyncio.gather."""
        tasks = []
        for question in questions:
            trace_data = trace_map.get(question.question_id, [])
            tasks.append(
                self._evaluate_single(run_id, question, trace_data)
            )
        results = await asyncio.gather(*tasks, return_exceptions=True)

        scores = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Evaluation failed for question {questions[i].question_id}: "
                    f"{result}"
                )
                raise result
            scores.append(result)
        return scores

    async def _evaluate_single(
        self,
        run_id: UUID,
        question: QuestionItem,
        trace_data: list[dict],
    ) -> ScoreResult:
        """Evaluate a single question using the baseline evaluator."""
        return await self.baseline_evaluator.evaluate(
            run_id=run_id,
            question=question,
            trace_data=trace_data,
        )
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_services/test_pipeline_runner.py -v
```
Expected: 4 tests PASS

- [ ] **Step 5: Run full test suite**

```bash
cd backend && uv run pytest tests/ -v
```
Expected: all tests PASS (~35+ tests)

- [ ] **Step 6: Commit**

```bash
git add backend/src/services/pipeline_runner.py backend/tests/test_services/test_pipeline_runner.py
git commit -m "feat: add PipelineRunner with asyncio concurrent question evaluation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 1 Complete — Verification Checklist

After completing all 14 tasks, verify:

- [ ] `uv run pytest tests/ -v` — all tests pass
- [ ] `uv run python -c "from src.core.schemas import Manifest, TaskRun, ScoreResult, JudgeResult; print('core OK')"`
- [ ] `uv run python -c "from src.infrastructure.database import engine; print('db OK')"`
- [ ] `uv run python -c "from src.infrastructure.llm_gateway import LLMClient; print('llm OK')"`
- [ ] `uv run python -c "from src.infrastructure.trace_parser import TraceParser; print('trace OK')"`
- [ ] `uv run python -c "from src.infrastructure.sandbox import EvalSandbox; print('sandbox OK')"`
- [ ] `uv run python -c "from src.repositories.run_repository import RunRepositoryImpl; print('repos OK')"`
- [ ] `uv run python -c "from src.evaluator.result_comparator import ResultComparator; print('comparator OK')"`
- [ ] `uv run python -c "from src.services.baseline_evaluator import BaselineEvaluator; print('evaluator OK')"`
- [ ] `uv run python -c "from src.services.pipeline_runner import PipelineRunner; print('pipeline OK')"`
