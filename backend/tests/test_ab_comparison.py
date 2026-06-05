"""A/B Test: No-Skill Baseline vs With-Skill evaluation comparison."""
import json
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock
from pathlib import Path

from src.infrastructure.trace_parser import TraceParser
from src.services.baseline_evaluator import BaselineEvaluator
from src.evaluator.result_comparator import ResultComparator
from src.core.schemas import QuestionItem, EvalConfig


@pytest.fixture
def question():
    return QuestionItem(
        question_id="alarm_analysis-0003",
        question_name="告警日志汇总分析",
        category="日志分析",
        difficulty="中等",
        prompt_file="alarm_analysis-0003/prompt.txt",
        output_dir="alarm_analysis-0003/输出结果/",
        eval_config=EvalConfig(),
        baseline_tool_count=6,
        baseline_tokens=3270,
        baseline_rounds=5,   # 5 assistant thinking rounds in baseline trace
        baseline_time_ms=48500,
        baseline_cost_usd=0.016,
    )


@pytest.mark.asyncio
async def test_baseline_no_skill_scoring(question):
    """Baseline (no skill): 5 tool calls, 2 errors/retries, 48.5s"""
    parser = TraceParser()
    trace = await parser.parse("sample_data/traces/alarm_baseline_no_skill.jsonl")

    repo = AsyncMock(); repo.save = AsyncMock()
    evaluator = BaselineEvaluator(score_repo=repo, comparator=ResultComparator())
    score = await evaluator.evaluate(run_id=uuid4(), question=question, trace_data=trace)

    metrics = parser.extract_metrics(trace)
    assert metrics["total_tool_calls"] == 6  # Glob+Read+Bash×4
    assert metrics["failed_tool_calls"] == 2  # Two errors before success

    # T2: 4 success / 6 total = 66.7%
    assert score.t2_accuracy == pytest.approx(66.7, abs=0.5)
    # T3: 6 calls = baseline 6 → no deduction → 100
    assert score.t3_efficiency == 100.0
    # T4: tokens match baseline
    assert score.t4_thinking == 100.0
    # E: time matches baseline
    assert score.e_performance == 100.0

    print(f"\n📊 Baseline (no-skill):")
    print(f"   T2={score.t2_accuracy:.0f} T3={score.t3_efficiency:.0f} "
          f"T4={score.t4_thinking:.0f} E={score.e_performance:.0f} "
          f"C={score.c_cost:.0f} Overall={score.overall_score:.1f}")


@pytest.mark.asyncio
async def test_with_skill_scoring(question):
    """With skill: 3 tool calls, 0 errors, 18.2s"""
    parser = TraceParser()
    trace = await parser.parse("sample_data/traces/alarm_with_skill.jsonl")

    repo = AsyncMock(); repo.save = AsyncMock()
    evaluator = BaselineEvaluator(score_repo=repo, comparator=ResultComparator())
    score = await evaluator.evaluate(run_id=uuid4(), question=question, trace_data=trace)

    metrics = parser.extract_metrics(trace)
    assert metrics["total_tool_calls"] == 4  # Skill+Glob+Bash×2 (no retries!)
    assert metrics["failed_tool_calls"] == 0  # Zero errors!

    # T2: 4/4 = 100%
    assert score.t2_accuracy == 100.0
    # T3: 4 calls < baseline 5 → better than baseline!
    assert score.t3_efficiency == 100.0
    # Slightly better than baseline in time
    assert score.e_performance > 90.0

    print(f"\n📊 With-Skill:")
    print(f"   T2={score.t2_accuracy:.0f} T3={score.t3_efficiency:.0f} "
          f"T4={score.t4_thinking:.0f} E={score.e_performance:.0f} "
          f"C={score.c_cost:.0f} Overall={score.overall_score:.1f}")


@pytest.mark.asyncio
async def test_skill_improvement_quantified(question):
    """Quantify skill improvement: less tools, less time, no errors."""
    parser = TraceParser()

    baseline_trace = await parser.parse("sample_data/traces/alarm_baseline_no_skill.jsonl")
    skill_trace = await parser.parse("sample_data/traces/alarm_with_skill.jsonl")

    baseline_metrics = parser.extract_metrics(baseline_trace)
    skill_metrics = parser.extract_metrics(skill_trace)

    # Tool calls: 5 → 3 (40% reduction)
    assert skill_metrics["total_tool_calls"] < baseline_metrics["total_tool_calls"]

    # Errors: 2 → 0 (100% reduction)
    assert skill_metrics["failed_tool_calls"] == 0
    assert baseline_metrics["failed_tool_calls"] == 2

    # Time: 48.5s → 18.2s (62% faster)
    assert skill_metrics["duration_ms"] < baseline_metrics["duration_ms"] * 0.5

    # Tokens: 3270 → 1880 (42% less)
    assert skill_metrics["total_tokens"] < baseline_metrics["total_tokens"] * 0.7

    # Cost: $0.016 → $0.008 (50% less)
    assert skill_metrics["cost_usd"] < baseline_metrics["cost_usd"] * 0.6

    improvement = {
        "tool_call_reduction": f"{(1 - skill_metrics['total_tool_calls']/baseline_metrics['total_tool_calls'])*100:.0f}%",
        "error_elimination": "100%",
        "time_speedup": f"{(1 - skill_metrics['duration_ms']/baseline_metrics['duration_ms'])*100:.0f}%",
        "token_reduction": f"{(1 - skill_metrics['total_tokens']/baseline_metrics['total_tokens'])*100:.0f}%",
        "cost_saving": f"{(1 - skill_metrics['cost_usd']/baseline_metrics['cost_usd'])*100:.0f}%",
    }

    print(f"\n🏆 Skill 提升量化:")
    for k, v in improvement.items():
        print(f"   {k}: {v}")
