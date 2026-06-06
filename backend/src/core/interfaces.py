from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from src.core.schemas import Manifest, TaskRun, ScoreResult, JudgeResult, RunStatus, QuestionItem


class BaseEvaluator(ABC):
    """Strategy interface for evaluation. BaselineEvaluator and JudgeEvaluator
    must implement this."""

    @abstractmethod
    async def evaluate(self, run_id: UUID, question: QuestionItem, trace_data: list[dict]) -> ScoreResult:
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
    async def get_by_run_question_attempt(
        self, run_id: UUID, question_id: str, attempt_index: int
    ) -> Optional[ScoreResult]:
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
