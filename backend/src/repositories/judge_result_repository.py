from __future__ import annotations
from typing import Optional
from uuid import UUID
import json
from sqlalchemy import Column, String, Integer, Text
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select

from src.infrastructure.database import Base
from src.core.schemas import (
    JudgeResult, CriticalStep, EvolutionSuggestion,
    SkillCompliance, FatalViolation,
)


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
