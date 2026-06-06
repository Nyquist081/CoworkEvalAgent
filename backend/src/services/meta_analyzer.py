from __future__ import annotations
import os
from typing import Optional
from uuid import UUID

from src.core.schemas import ScoreResult, JudgeResult


class MetaAnalyzer:
    """Computes pass@k/pass^k metrics and extracts common issues from judge results."""

    def __init__(self, pass_threshold: float | None = None):
        self.pass_threshold = pass_threshold or float(
            os.getenv("PASS_THRESHOLD", "60")
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
        if not scores_by_question:
            return {
                "pass_at_k": 0,
                "pass_power_k": 0,
                "pass_at_k_pct": 0.0,
                "pass_power_k_pct": 0.0,
                "pp_gap": 0.0,
                "total_questions": 0,
                "k": 0 if k is None else k,
                "threshold": self.pass_threshold,
            }

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

    @staticmethod
    def group_scores_by_question(scores: list[ScoreResult]) -> dict[str, list[ScoreResult]]:
        grouped: dict[str, list[ScoreResult]] = {}
        for score in scores:
            grouped.setdefault(score.question_id, []).append(score)
        for values in grouped.values():
            values.sort(key=lambda s: s.attempt_index)
        return dict(sorted(grouped.items()))

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

    def extract_common_issues(self, judge_results: list[JudgeResult]) -> dict:
        if not judge_results:
            return {
                "status": "not_extracted",
                "summary": "",
                "common_issues": [],
                "improvement_suggestions": [],
            }

        issue_map: dict[tuple[str, str], dict] = {}
        suggestions: dict[tuple[str, str], dict] = {}

        for jr in judge_results:
            for step in jr.critical_steps:
                dimension = self._map_assessment_to_dimension(step.assessment) or "task_completion"
                key = (dimension, step.observation)
                issue = issue_map.setdefault(
                    key,
                    {
                        "dimension": dimension,
                        "issue": step.observation,
                        "frequency": "",
                        "impact": step.context_chain,
                        "question_ids": [],
                        "examples": [],
                    },
                )
                if jr.question_id not in issue["question_ids"]:
                    issue["question_ids"].append(jr.question_id)
                issue["examples"].append(f"{jr.question_id} {step.step_id}: {step.root_cause}")

            for suggestion in jr.evolution_suggestions:
                key = (suggestion.type, suggestion.suggestion)
                suggestions.setdefault(
                    key,
                    {
                        "type": suggestion.type,
                        "priority": "中",
                        "suggestion": suggestion.suggestion,
                        "expected_impact": "基于当前 Judge 结果的确定性归纳",
                    },
                )

        common_issues = list(issue_map.values())
        total = len(judge_results)
        for issue in common_issues:
            count = len(issue["question_ids"])
            issue["frequency"] = f"{count}/{total} 题"

        common_issues.sort(key=lambda item: len(item["question_ids"]), reverse=True)
        summary = (
            f"共分析 {total} 道题的 Judge 结果, "
            f"提取 {len(common_issues)} 类可归因问题。"
        )

        return {
            "status": "extracted",
            "summary": summary,
            "common_issues": common_issues[:6],
            "improvement_suggestions": list(suggestions.values())[:5],
        }
