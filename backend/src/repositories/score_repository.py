from __future__ import annotations
from typing import Optional
from uuid import UUID
from sqlalchemy import Column, String, Float, Boolean
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select

from src.infrastructure.database import Base
from src.core.schemas import ScoreResult, TraceQuality


def _uuid_to_bytes(u: UUID) -> bytes:
    return u.bytes


def _bytes_to_uuid(b: bytes) -> UUID:
    return UUID(bytes=b)


class ScoreResultModel(Base):
    __tablename__ = "score_results"

    id = Column(BLOB, primary_key=True)
    run_id = Column(BLOB, nullable=False)
    question_id = Column(String, nullable=False)
    attempt_index = Column(Float, default=1)
    trace_quality = Column(String, nullable=False, default="full")
    is_partial_score = Column(Boolean, default=False)

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
    observed_tool_results = Column(Float, default=0)
    missing_tool_results = Column(Float, default=0)
    agent_tool_success_rate = Column(Float, default=100.0)
    trace_observability_rate = Column(Float, default=100.0)
    lifecycle_completeness_rate = Column(Float, default=100.0)
    metric_completeness_rate = Column(Float, default=100.0)
    reasoning_visibility_rate = Column(Float, default=100.0)
    critical_event_impact = Column(Float, default=100.0)
    evaluation_confidence = Column(Float, default=100.0)
    score_with_confidence = Column(Float, nullable=True)
    evaluation_validity = Column(String, default="valid")
    actual_tokens = Column(Float, default=0)
    actual_rounds = Column(Float, default=0)
    actual_time_ms = Column(Float, default=0)
    actual_cost_usd = Column(Float, default=0.0)

    def to_domain(self) -> ScoreResult:
        return ScoreResult(
            id=_bytes_to_uuid(self.id),
            run_id=_bytes_to_uuid(self.run_id),
            question_id=self.question_id,
            attempt_index=int(self.attempt_index or 1),
            trace_quality=TraceQuality(self.trace_quality or "full"),
            is_partial_score=bool(self.is_partial_score),
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
            observed_tool_results=int(self.observed_tool_results or self.actual_tool_calls or 0),
            missing_tool_results=int(self.missing_tool_results or 0),
            agent_tool_success_rate=float(self.agent_tool_success_rate or 100.0),
            trace_observability_rate=float(self.trace_observability_rate or 100.0),
            lifecycle_completeness_rate=float(self.lifecycle_completeness_rate or 100.0),
            metric_completeness_rate=float(self.metric_completeness_rate or 100.0),
            reasoning_visibility_rate=float(self.reasoning_visibility_rate or 100.0),
            critical_event_impact=float(self.critical_event_impact or 100.0),
            evaluation_confidence=float(self.evaluation_confidence or 100.0),
            score_with_confidence=self.score_with_confidence,
            evaluation_validity=self.evaluation_validity or "valid",
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
            attempt_index=s.attempt_index,
            trace_quality=s.trace_quality.value,
            is_partial_score=s.is_partial_score,
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
            observed_tool_results=s.observed_tool_results,
            missing_tool_results=s.missing_tool_results,
            agent_tool_success_rate=s.agent_tool_success_rate,
            trace_observability_rate=s.trace_observability_rate,
            lifecycle_completeness_rate=s.lifecycle_completeness_rate,
            metric_completeness_rate=s.metric_completeness_rate,
            reasoning_visibility_rate=s.reasoning_visibility_rate,
            critical_event_impact=s.critical_event_impact,
            evaluation_confidence=s.evaluation_confidence,
            score_with_confidence=s.score_with_confidence,
            evaluation_validity=s.evaluation_validity,
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

    async def get_by_run_question_attempt(
        self, run_id: UUID, question_id: str, attempt_index: int
    ) -> Optional[ScoreResult]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(ScoreResultModel).where(
                    ScoreResultModel.run_id == _uuid_to_bytes(run_id),
                    ScoreResultModel.question_id == question_id,
                    ScoreResultModel.attempt_index == attempt_index,
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
