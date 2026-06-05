import pytest
from uuid import uuid4
from src.services.meta_analyzer import MetaAnalyzer
from src.core.schemas import ScoreResult, JudgeResult


class TestPassRates:
    def test_pass_at_k_at_least_one(self):
        analyzer = MetaAnalyzer(pass_threshold=0.6)
        scores = {
            "q-001": [
                ScoreResult(run_id=uuid4(), question_id="q-001", t1_completion=0.8),
                ScoreResult(run_id=uuid4(), question_id="q-001", t1_completion=0.3),
                ScoreResult(run_id=uuid4(), question_id="q-001", t1_completion=0.5),
            ],
            "q-002": [
                ScoreResult(run_id=uuid4(), question_id="q-002", t1_completion=0.2),
            ],
        }
        result = analyzer.compute_pass_rates(scores, k=3)

        # q-001: at least 1 pass among 3 → pass@3 ✓
        # q-002: only 1 execution at 0.2 → pass@3 ✗
        assert result["pass_at_k"] == 1
        assert result["pass_power_k"] == 0
        assert result["pass_at_k_pct"] == 50.0
        assert result["total_questions"] == 2

    def test_pass_power_k_all_pass(self):
        analyzer = MetaAnalyzer(pass_threshold=0.6)
        scores = {
            "q-001": [
                ScoreResult(run_id=uuid4(), question_id="q-001", t1_completion=0.8),
                ScoreResult(run_id=uuid4(), question_id="q-001", t1_completion=0.9),
            ],
        }
        result = analyzer.compute_pass_rates(scores, k=2)
        assert result["pass_at_k"] == 1
        assert result["pass_power_k"] == 1
        assert result["pp_gap"] == 0.0

    def test_empty_scores(self):
        analyzer = MetaAnalyzer()
        result = analyzer.compute_pass_rates({}, k=3)
        assert result["total_questions"] == 0
        assert result["pass_at_k_pct"] == 0.0


class TestCommonIssuesInput:
    def test_build_summaries(self):
        analyzer = MetaAnalyzer()
        judge_results = [
            JudgeResult(
                run_id=uuid4(), question_id="q-001",
                execution_efficiency=65, tool_accuracy=80,
                thinking_efficiency=70, task_completion=75,
                conclusion="Needs better error handling",
            ),
        ]
        summaries = analyzer.build_common_issues_input(judge_results)
        assert len(summaries) == 1
        assert summaries[0]["question_id"] == "q-001"
        assert "execution_efficiency" in summaries[0]["deductions"]
