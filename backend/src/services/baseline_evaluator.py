from __future__ import annotations
from typing import Optional
from uuid import UUID

from src.core.interfaces import BaseEvaluator, ScoreRepository
from src.core.schemas import ScoreResult, QuestionItem, EvalConfig
from src.evaluator.result_comparator import ResultComparator
from src.infrastructure.trace_parser import TraceParser


class BaselineEvaluator(BaseEvaluator):
    """TTTEC six-dimension rule-based scoring engine."""

    def __init__(self, score_repo: ScoreRepository, comparator: ResultComparator):
        self.score_repo = score_repo
        self.comparator = comparator
        self.parser = TraceParser()

    async def evaluate(
        self, run_id: UUID, question: QuestionItem, trace_data: list[dict]
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

        # T1: Task Completion — Baseline objective part (0 until judge fusion)
        score.t1_baseline_only = 0.0
        score.t1_completion = 0.0

        # T2: Tool Accuracy
        score.t2_accuracy = self._compute_t2(
            metrics["success_tool_calls"], metrics["total_tool_calls"]
        )

        # T3: Tool Efficiency
        score.t3_efficiency = self._compute_t3(
            metrics["total_tool_calls"], question.baseline_tool_count
        )

        # T4: Thinking Efficiency
        score.t4_thinking = self._compute_t4(
            metrics["total_tokens"], metrics["rounds"],
            question.baseline_tokens, question.baseline_rounds,
        )

        # E: E2E Performance
        score.e_performance = self._compute_e(
            metrics["duration_ms"], question.baseline_time_ms,
            question.payload_size_kb,
        )

        # C: Cost Efficiency
        score.c_cost = self._compute_c(
            metrics["cost_usd"], question.baseline_cost_usd
        )

        # Overall: average of six dimensions
        dims = [
            score.t1_completion or 0,
            score.t2_accuracy or 0,
            score.t3_efficiency or 0,
            score.t4_thinking or 0,
            score.e_performance or 0,
            score.c_cost or 0,
        ]
        score.overall_score = sum(dims) / 6.0

        await self.score_repo.save(score)
        return score

    def _compute_t2(self, success: int, total: int) -> float:
        if total == 0:
            return 100.0
        return max(0.0, (success / total) * 100.0)

    def _compute_t3(self, actual_calls: int, baseline_calls: int) -> float:
        excess = max(0, actual_calls - baseline_calls)
        return max(0.0, 100.0 - 5.0 * excess)

    def _compute_t4(
        self, actual_tokens: int, actual_rounds: int,
        baseline_tokens: int, baseline_rounds: int,
    ) -> float:
        if baseline_tokens == 0:
            token_overage_rate = 0.0
        else:
            token_overage_rate = max(0.0, actual_tokens - baseline_tokens) / baseline_tokens
        round_overage = max(0, actual_rounds - baseline_rounds)
        penalty = token_overage_rate * 100.0 * 0.3 + round_overage * 5.0
        return max(0.0, 100.0 - penalty)

    def _compute_e(
        self, actual_time_ms: int, baseline_time_ms: int,
        payload_size_kb: Optional[float],
    ) -> float:
        # Use dynamic baseline if payload_size_kb is configured
        dynamic_baseline = baseline_time_ms
        if dynamic_baseline == 0:
            return 100.0
        overage_ratio = max(0.0, actual_time_ms - dynamic_baseline) / dynamic_baseline
        return max(0.0, 100.0 - overage_ratio * 100.0)

    def _compute_c(self, actual_cost: float, baseline_cost: float) -> float:
        if baseline_cost == 0:
            return 100.0
        overage_ratio = max(0.0, actual_cost - baseline_cost) / baseline_cost
        return max(0.0, 100.0 - overage_ratio * 100.0)
