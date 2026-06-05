from __future__ import annotations
from typing import Optional
from uuid import UUID

from src.core.schemas import ScoreResult, JudgeResult


class FusionService:
    """Fuses Baseline (rule-based) and Judge (LLM semantic) scores.

    T1-T4 use 50:50 fusion.
    E and C are pure Baseline (no judge component — physical metrics).
    """

    async def fuse(
        self,
        baseline: ScoreResult,
        judge: Optional[JudgeResult],
    ) -> ScoreResult:
        if judge is None:
            # No judge result — Baseline-only scores stand
            baseline.t1_judge_only = None
            baseline.t1_completion = baseline.t1_baseline_only
            self._recompute_overall(baseline)
            return baseline

        # T1-T4: 50:50 fusion
        baseline.t1_completion = self._blend(
            baseline.t1_baseline_only, judge.task_completion
        )
        baseline.t2_accuracy = self._blend(
            baseline.t2_accuracy, judge.tool_accuracy
        )
        baseline.t3_efficiency = self._blend(
            baseline.t3_efficiency, judge.execution_efficiency
        )
        baseline.t4_thinking = self._blend(
            baseline.t4_thinking, judge.thinking_efficiency
        )

        # E and C: pure Baseline (no fusion)
        # Already set from BaselineEvaluator

        # Store judge-only T1 for reference
        baseline.t1_judge_only = float(judge.task_completion)

        self._recompute_overall(baseline)
        return baseline

    def _blend(self, baseline_val: Optional[float], judge_val: int | float) -> float:
        b = baseline_val if baseline_val is not None else 0.0
        j = float(judge_val)
        return max(0.0, min(100.0, b * 0.5 + j * 0.5))

    def _recompute_overall(self, score: ScoreResult) -> None:
        dims = [
            score.t1_completion or 0,
            score.t2_accuracy or 0,
            score.t3_efficiency or 0,
            score.t4_thinking or 0,
            score.e_performance or 0,
            score.c_cost or 0,
        ]
        score.overall_score = sum(dims) / 6.0
