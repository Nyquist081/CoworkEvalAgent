from __future__ import annotations
import os
from typing import Optional
from uuid import UUID

from src.core.schemas import ScoreResult, JudgeResult


class MetaAnalyzer:
    """Computes pass@k/pass^k metrics and extracts common issues from judge results."""

    def __init__(self, pass_threshold: float | None = None):
        self.pass_threshold = pass_threshold or float(
            os.getenv("PASS_THRESHOLD", "0.6")
        )

    def compute_pass_rates(
        self,
        scores_by_question: dict[str, list[ScoreResult]],
        k: int | None = None,
    ) -> dict:
        """Compute pass@k and pass^k for a set of questions.

        Args:
            scores_by_question: question_id → list of ScoreResults from k executions
            k: number of executions (auto-detected if None)

        Returns:
            dict with pass_at_k, pass_power_k, pass_at_k_pct, pass_power_k_pct,
            pp_gap, total_questions, threshold
        """
        if k is None:
            k = max(len(scores) for scores in scores_by_question.values())

        total = len(scores_by_question)
        pass_at_k_count = 0
        pass_power_k_count = 0

        for question_id, scores in scores_by_question.items():
            # Determine pass/fail per execution
            passes = [
                (s.t1_completion or 0) >= self.pass_threshold
                for s in scores
            ]

            if any(passes):  # at least 1 pass → pass@k
                pass_at_k_count += 1

            if len(passes) >= k and all(passes[:k]):  # all k pass → pass^k
                pass_power_k_count += 1

        pass_at_k_pct = (pass_at_k_count / total * 100) if total > 0 else 0.0
        pass_power_k_pct = (pass_power_k_count / total * 100) if total > 0 else 0.0

        return {
            "pass_at_k": pass_at_k_count,
            "pass_power_k": pass_power_k_count,
            "pass_at_k_pct": round(pass_at_k_pct, 2),
            "pass_power_k_pct": round(pass_power_k_pct, 2),
            "pp_gap": round(pass_at_k_pct - pass_power_k_pct, 2),
            "total_questions": total,
            "k": k,
            "threshold": self.pass_threshold,
        }

    def build_common_issues_input(
        self, judge_results: list[JudgeResult]
    ) -> list[dict]:
        """Build summary input for LLM common-issue extraction.

        Each judge result is condensed to: question_id, question_name (from scoring),
        conclusion, deductions per dimension, and evolution_suggestions.
        """
        summaries = []
        for jr in judge_results:
            summary = {
                "question_id": jr.question_id,
                "overall_score": self._avg_judge_score(jr),
                "conclusion": jr.conclusion,
                "deductions": {
                    "execution_efficiency": {
                        "score": jr.execution_efficiency,
                        "reason": "",
                    },
                    "tool_accuracy": {
                        "score": jr.tool_accuracy,
                        "reason": "",
                    },
                    "thinking_efficiency": {
                        "score": jr.thinking_efficiency,
                        "reason": "",
                    },
                    "task_completion": {
                        "score": jr.task_completion,
                        "reason": "",
                    },
                },
                "evolution_suggestions": [
                    {"type": s.type, "suggestion": s.suggestion}
                    for s in jr.evolution_suggestions
                ],
            }

            # Add reasons from critical steps
            for cs in jr.critical_steps:
                dim = self._map_assessment_to_dimension(cs.assessment)
                if dim and summary["deductions"][dim]["reason"]:
                    summary["deductions"][dim]["reason"] += "; "
                if dim:
                    summary["deductions"][dim]["reason"] += cs.observation[:100]

            summaries.append(summary)
        return summaries

    def _avg_judge_score(self, jr: JudgeResult) -> float:
        dims = [
            jr.execution_efficiency,
            jr.tool_accuracy,
            jr.thinking_efficiency,
            jr.task_completion,
        ]
        return sum(dims) / 4.0

    def _map_assessment_to_dimension(self, assessment: str) -> Optional[str]:
        mapping = {
            "REDUNDANT": "execution_efficiency",
            "ERRONEOUS": "tool_accuracy",
        }
        return mapping.get(assessment)
