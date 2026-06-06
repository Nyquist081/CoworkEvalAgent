from __future__ import annotations
import asyncio
import logging
from uuid import UUID

from src.core.schemas import TaskRun, Manifest, QuestionItem, RunMetadata, RunStatus, ScoreResult
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
        judge_evaluator: BaseEvaluator | None = None,
        fusion_service=None,
        judge_repo=None,
        judge_concurrency: int = 5,
    ):
        self.run_repo = run_repo
        self.baseline_evaluator = baseline_evaluator
        self.judge_evaluator = judge_evaluator
        self.fusion_service = fusion_service
        self.judge_repo = judge_repo
        self.judge_semaphore = asyncio.Semaphore(judge_concurrency)
        self.parser = TraceParser()

    async def create_run(
        self,
        manifest: Manifest,
        judge_enabled: bool = True,
        run_metadata: RunMetadata | None = None,
    ) -> TaskRun:
        run = TaskRun(
            benchmark_id=manifest.benchmark_id,
            status=RunStatus.PENDING,
            judge_enabled=judge_enabled,
        )
        if run_metadata is not None:
            run.run_label = run_metadata.run_label
            run.agent_name = run_metadata.agent_name
            run.model = run_metadata.model
            run.skill_version = run_metadata.skill_version
            run.source = run_metadata.source
            run.trace_quality = run_metadata.trace_quality
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

    async def execute_offline_run(
        self,
        run_id: UUID,
        evaluation_inputs: list,
        judge_enabled: bool = False,
    ) -> list[ScoreResult]:
        sm = StateMachine(judge_enabled=judge_enabled)

        try:
            await self.run_repo.update_status(run_id, RunStatus.PARSING_TRACE)
            sm.transition_to(RunStatus.PARSING_TRACE)
            trace_map = await self._load_input_traces(evaluation_inputs)

            await self.run_repo.update_status(run_id, RunStatus.EVALUATING_BASELINE)
            sm.transition_to(RunStatus.EVALUATING_BASELINE)
            baseline_scores = await self._execute_evaluation_inputs(
                run_id, evaluation_inputs, trace_map
            )

            if not judge_enabled or self.judge_evaluator is None:
                await self.run_repo.update_status(run_id, RunStatus.COMPLETED)
                sm.transition_to(RunStatus.COMPLETED)
                return baseline_scores

            await self.run_repo.update_status(run_id, RunStatus.AWAITING_JUDGE)
            sm.transition_to(RunStatus.AWAITING_JUDGE)
            await self.run_repo.update_status(run_id, RunStatus.EVALUATING_JUDGE)
            sm.transition_to(RunStatus.EVALUATING_JUDGE)
            fused_scores = await self._execute_judge_and_fusion(
                run_id, evaluation_inputs, trace_map, baseline_scores
            )

            await self.run_repo.update_status(run_id, RunStatus.COMPLETED)
            sm.transition_to(RunStatus.COMPLETED)
            return fused_scores

        except Exception as e:
            logger.exception(f"Offline pipeline failed for run {run_id}")
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

    async def _load_input_traces(
        self, evaluation_inputs: list
    ) -> dict[tuple[str, int], list[dict]]:
        trace_map = {}
        for item in evaluation_inputs:
            trace_map[(item.question_id, item.attempt_index)] = await self.parser.parse(
                item.trace_path
            )
        return trace_map

    async def _execute_evaluation_inputs(
        self,
        run_id: UUID,
        evaluation_inputs: list,
        trace_map: dict[tuple[str, int], list[dict]],
    ) -> list[ScoreResult]:
        tasks = []
        for item in evaluation_inputs:
            trace_data = trace_map[(item.question_id, item.attempt_index)]
            tasks.append(self.baseline_evaluator.evaluate_input(run_id, item, trace_data))
        results = await asyncio.gather(*tasks, return_exceptions=True)

        scores = []
        for result in results:
            if isinstance(result, Exception):
                raise result
            scores.append(result)
        return scores

    async def _execute_judge_and_fusion(
        self,
        run_id: UUID,
        evaluation_inputs: list,
        trace_map: dict,
        baseline_scores: list[ScoreResult],
    ) -> list[ScoreResult]:
        baseline_by_key = {
            (score.question_id, score.attempt_index): score
            for score in baseline_scores
        }
        tasks = []
        for item in evaluation_inputs:
            tasks.append(
                self._judge_and_fuse_single(run_id, item, trace_map, baseline_by_key)
            )
        results = await asyncio.gather(*tasks, return_exceptions=True)

        scores: list[ScoreResult] = []
        for result in results:
            if isinstance(result, Exception):
                raise result
            scores.append(result)
        return scores

    async def _judge_and_fuse_single(
        self,
        run_id: UUID,
        item,
        trace_map: dict,
        baseline_by_key: dict,
    ) -> ScoreResult:
        key = (item.question_id, item.attempt_index)
        baseline = baseline_by_key[key]

        async with self.judge_semaphore:
            await self.judge_evaluator.evaluate(
                run_id=run_id,
                question=item.question,
                trace_data=trace_map[key],
            )

        judge_result = await self.judge_repo.get_by_run_and_question(
            run_id, item.question_id
        )
        if judge_result is None or self.fusion_service is None:
            baseline.is_partial_score = True
            return baseline

        return await self.fusion_service.fuse(baseline, judge_result)
