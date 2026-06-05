from __future__ import annotations
import asyncio
import logging
from uuid import UUID

from src.core.schemas import TaskRun, Manifest, QuestionItem, RunStatus, ScoreResult
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
    3. EVALUATING_BASELINE → COMPLETED (or AWAITING_JUDGE in Phase 2)

    Uses asyncio.gather for concurrent multi-question processing.
    Judge calls are rate-limited via Semaphore (reserved for Phase 2).
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

    async def create_run(self, manifest: Manifest, judge_enabled: bool = True) -> TaskRun:
        run = TaskRun(
            benchmark_id=manifest.benchmark_id,
            status=RunStatus.PENDING,
            judge_enabled=judge_enabled,
        )
        await self.run_repo.save(run)
        return run

    async def execute(self, run_id: UUID, manifest: Manifest) -> list[ScoreResult]:
        sm = StateMachine(judge_enabled=False)

        try:
            # PENDING → PARSING_TRACE
            await self.run_repo.update_status(run_id, RunStatus.PARSING_TRACE)
            sm.transition_to(RunStatus.PARSING_TRACE)
            trace_map = await self._load_traces(manifest)

            # PARSING_TRACE → EVALUATING_BASELINE
            await self.run_repo.update_status(run_id, RunStatus.EVALUATING_BASELINE)
            sm.transition_to(RunStatus.EVALUATING_BASELINE)
            scores = await self._execute_questions(run_id, manifest.questions, trace_map)

            # EVALUATING_BASELINE → COMPLETED
            await self.run_repo.update_status(run_id, RunStatus.COMPLETED)
            sm.transition_to(RunStatus.COMPLETED)

            return scores

        except Exception as e:
            logger.exception(f"Pipeline failed for run {run_id}")
            await self.run_repo.update_status(
                run_id, RunStatus.FAILED, error_stack=str(e)
            )
            raise EvaluationError(str(e), run_id=str(run_id))

    async def _load_traces(self, manifest: Manifest) -> dict[str, list[dict]]:
        trace_map = {}
        for question in manifest.questions:
            trace_path = f"backend/sample_data/traces/valid_trace.jsonl"
            try:
                trace_data = await self.parser.parse(trace_path)
            except FileNotFoundError:
                logger.warning(f"Trace file not found for {question.question_id}, using empty trace")
                trace_data = []
            except IncompleteTraceError:
                raise
            trace_map[question.question_id] = trace_data
        return trace_map

    async def _execute_questions(
        self, run_id: UUID, questions: list[QuestionItem],
        trace_map: dict[str, list[dict]],
    ) -> list[ScoreResult]:
        tasks = []
        for question in questions:
            trace_data = trace_map.get(question.question_id, [])
            tasks.append(self._evaluate_single(run_id, question, trace_data))
        results = await asyncio.gather(*tasks, return_exceptions=True)

        scores = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Evaluation failed for {questions[i].question_id}: {result}")
                raise result
            scores.append(result)
        return scores

    async def _evaluate_single(
        self, run_id: UUID, question: QuestionItem, trace_data: list[dict],
    ) -> ScoreResult:
        return await self.baseline_evaluator.evaluate(
            run_id=run_id, question=question, trace_data=trace_data,
        )
