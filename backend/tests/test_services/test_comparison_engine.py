import pytest
from uuid import uuid4
from src.services.comparison_engine import ComparisonEngine
from src.core.schemas import ScoreResult


@pytest.fixture
def sample_scores():
    return [
        ScoreResult(
            run_id=uuid4(),
            question_id="q-001",
            t1_completion=80.0,
            t2_accuracy=90.0,
            t3_efficiency=85.0,
            t4_thinking=70.0,
            e_performance=95.0,
            c_cost=88.0,
            overall_score=84.7,
        ),
        ScoreResult(
            run_id=uuid4(),
            question_id="q-002",
            t1_completion=60.0,
            t2_accuracy=70.0,
            t3_efficiency=75.0,
            t4_thinking=50.0,
            e_performance=65.0,
            c_cost=78.0,
            overall_score=66.3,
        ),
    ]


class TestRadarData:
    def test_radar_computes_averages(self, sample_scores):
        engine = ComparisonEngine()
        result = engine.radar_data({"v1.0": sample_scores})
        assert len(result["dimensions"]) == 6
        assert len(result["series"]) == 1
        assert result["series"][0]["label"] == "v1.0"
        # T1 avg = (80+60)/2 = 70
        assert result["series"][0]["values"][0] == 70.0


class TestHeatmapData:
    def test_heatmap_structure(self, sample_scores):
        engine = ComparisonEngine()
        result = engine.heatmap_data(sample_scores)
        assert len(result["questions"]) == 2
        assert len(result["data"]) == 2
        assert result["data"][0][0] == 80.0  # q-001 T1


class TestTrendData:
    def test_trend_structure(self):
        engine = ComparisonEngine()
        result = engine.trend_data([
            {
                "label": "v1.0",
                "overall": 75.5,
                "pass_at_k_pct": 80.0,
                "pass_power_k_pct": 60.0,
            },
            {
                "label": "v2.0",
                "overall": 82.0,
                "pass_at_k_pct": 85.0,
                "pass_power_k_pct": 70.0,
            },
        ])
        assert result["labels"] == ["v1.0", "v2.0"]
        assert result["overall_scores"] == [75.5, 82.0]


class TestPassRateComparison:
    def test_pass_rate_comparison(self):
        engine = ComparisonEngine()
        result = engine.pass_rate_comparison({
            "v1.0": {
                "pass_at_k_pct": 75.0,
                "pass_power_k_pct": 50.0,
                "pp_gap": 25.0,
                "k": 3,
            },
        })
        assert len(result["runs"]) == 1
        assert result["runs"][0]["pp_gap"] == 25.0


class TestObservabilityComparison:
    def test_observability_summary_flags_incomplete_runs(self):
        engine = ComparisonEngine()
        complete = ScoreResult(
            run_id=uuid4(),
            question_id="q-1",
            actual_tool_calls=10,
            observed_tool_results=10,
            missing_tool_results=0,
            trace_observability_rate=100.0,
            agent_tool_success_rate=80.0,
            overall_score=80.0,
        )
        incomplete = ScoreResult(
            run_id=uuid4(),
            question_id="q-1",
            actual_tool_calls=10,
            observed_tool_results=8,
            missing_tool_results=2,
            trace_observability_rate=80.0,
            agent_tool_success_rate=100.0,
            evaluation_confidence=60.0,
            score_with_confidence=54.0,
            overall_score=90.0,
        )

        result = engine.observability_comparison({
            "complete": [complete],
            "incomplete": [incomplete],
        })

        assert result["runs"][0]["evaluation_validity"] == "valid"
        assert result["runs"][1]["evaluation_validity"] == "trace_incomplete"
        assert result["runs"][1]["can_claim_winner"] is False
        assert result["runs"][1]["missing_tool_results"] == 2
        assert result["runs"][1]["trace_observability_rate"] == 80.0
        assert result["runs"][1]["score_with_confidence"] == 54.0
