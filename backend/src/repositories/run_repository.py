from __future__ import annotations
from typing import Optional
from uuid import UUID
import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select, delete

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
