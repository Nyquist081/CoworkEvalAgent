from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal, Optional
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


class TraceQuality(str, Enum):
    FULL = "full"
    DEGRADED = "degraded"


class RunSource(str, Enum):
    OFFLINE = "offline"
    SIDECAR = "sidecar"


# ── Eval Config ──────────────────────────────────────────

class IgnoreRule(BaseModel):
    type: Literal["column", "row", "region"]
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


class RunMetadata(BaseModel):
    run_label: str
    agent_name: str = ""
    model: str = ""
    skill_version: str = ""
    source: RunSource = RunSource.OFFLINE
    created_at: Optional[datetime] = None
    trace_quality: TraceQuality = TraceQuality.FULL


class EvaluationInput(BaseModel):
    question: QuestionItem
    trace_path: Path
    output_dir: Path
    reference_paths: list[Path] = Field(default_factory=list)
    attempt_index: int = 1
    trace_quality: TraceQuality = TraceQuality.FULL
    is_partial_score: bool = False

    @property
    def question_id(self) -> str:
        return self.question.question_id


# ── Task Run ─────────────────────────────────────────────

class TaskRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    benchmark_id: str
    run_label: str = ""
    agent_name: str = ""
    model: str = ""
    skill_version: str = ""
    source: RunSource = RunSource.OFFLINE
    trace_quality: TraceQuality = TraceQuality.FULL
    status: RunStatus = RunStatus.PENDING
    error_stack: Optional[str] = None
    is_partial_score: bool = False
    judge_enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Score Result ─────────────────────────────────────────

class ScoreResult(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    question_id: str
    attempt_index: int = 1
    trace_quality: TraceQuality = TraceQuality.FULL
    is_partial_score: bool = False

    t1_completion: Optional[float] = None
    t2_accuracy: Optional[float] = None
    t3_efficiency: Optional[float] = None
    t4_thinking: Optional[float] = None
    e_performance: Optional[float] = None
    c_cost: Optional[float] = None

    overall_score: Optional[float] = None
    t1_baseline_only: Optional[float] = None
    t1_judge_only: Optional[float] = None

    actual_tool_calls: int = 0
    actual_success_calls: int = 0
    observed_tool_results: int = 0
    missing_tool_results: int = 0
    agent_tool_success_rate: float = 100.0
    trace_observability_rate: float = 100.0
    lifecycle_completeness_rate: float = 100.0
    metric_completeness_rate: float = 100.0
    reasoning_visibility_rate: float = 100.0
    critical_event_impact: float = 100.0
    evaluation_confidence: float = 100.0
    score_with_confidence: Optional[float] = None
    evaluation_validity: str = "valid"
    actual_tokens: int = 0
    actual_rounds: int = 0
    actual_time_ms: int = 0
    actual_cost_usd: float = 0.0


# ── Judge Result ─────────────────────────────────────────

class CriticalStep(BaseModel):
    step_id: str
    assessment: Literal["REDUNDANT", "ERRONEOUS"]
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
    score: int = 0


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
    level: str
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
