import pytest
from uuid import uuid4
from unittest.mock import AsyncMock
from src.services.baseline_evaluator import BaselineEvaluator
from src.core.schemas import EvaluationInput, QuestionItem, EvalConfig
from src.evaluator.result_comparator import ResultComparator


@pytest.fixture
def question():
    return QuestionItem(
        question_id="q-001",
        question_name="Test",
        category="Excel",
        difficulty="中等",
        prompt_file="q-001/prompt.txt",
        output_dir="q-001/output/",
        eval_config=EvalConfig(),
        baseline_tool_count=10,
        baseline_tokens=500000,
        baseline_rounds=15,
        baseline_time_ms=50000,
        baseline_cost_usd=2.0,
    )


def make_trace(tool_count=10, success_count=10, tokens=500000, rounds=15,
               duration_ms=50000, cost_usd=2.0):
    trace = [{"type": "session_start"}]
    for i in range(tool_count):
        trace.append({"type": "tool_call", "tool_name": f"tool_{i}"})
        trace.append({"type": "tool_result", "tool_error": i >= success_count})
    for i in range(rounds):
        trace.append({"type": "assistant", "thinking": f"thought {i}", "text": "ok"})
    trace.append({
        "type": "result", "status": "success",
        "duration_ms": duration_ms, "input_tokens": tokens // 2,
        "output_tokens": tokens // 2, "cost_usd": cost_usd,
    })
    return trace


@pytest.fixture
def evaluator():
    score_repo = AsyncMock()
    score_repo.save = AsyncMock()
    comparator = ResultComparator()
    return BaselineEvaluator(score_repo=score_repo, comparator=comparator)


@pytest.mark.asyncio
async def test_perfect_scores_all_100(evaluator, question):
    trace = make_trace()
    score = await evaluator.evaluate(run_id=uuid4(), question=question, trace_data=trace)
    assert score.t2_accuracy == 100.0
    assert score.t3_efficiency == 100.0
    assert score.t4_thinking == 100.0
    assert score.e_performance == 100.0
    assert score.c_cost == 100.0


@pytest.mark.asyncio
async def test_t3_deducts_5_per_extra_call(evaluator, question):
    question.baseline_tool_count = 1
    trace = make_trace(tool_count=3, success_count=2)
    score = await evaluator.evaluate(run_id=uuid4(), question=question, trace_data=trace)
    # 3 calls, baseline 1 → excess 2 → deduction 10 → score 90
    assert score.t3_efficiency == 90.0


@pytest.mark.asyncio
async def test_e_performance_deduction(evaluator, question):
    # actual 60000, baseline 50000 → 20% over → score 80
    trace = make_trace(duration_ms=60000)
    score = await evaluator.evaluate(run_id=uuid4(), question=question, trace_data=trace)
    assert score.e_performance == pytest.approx(80.0)


@pytest.mark.asyncio
async def test_t2_zero_calls_defaults_100(evaluator, question):
    trace = make_trace(tool_count=0, tokens=100, rounds=1, duration_ms=1000, cost_usd=0.01)
    score = await evaluator.evaluate(run_id=uuid4(), question=question, trace_data=trace)
    assert score.t2_accuracy == 100.0


@pytest.mark.asyncio
async def test_score_with_confidence_uses_trace_confidence(evaluator, question):
    trace = [
        {"type": "session_start", "trace_schema_version": "1.1", "model": "test"},
        {"type": "tool_call", "tool_call_id": "call-1", "tool_name": "Read"},
        {"type": "tool_result", "tool_call_id": "call-1", "tool_error": False},
        {"type": "result", "status": "success", "input_tokens": 100, "output_tokens": 20},
    ]

    score = await evaluator.evaluate(run_id=uuid4(), question=question, trace_data=trace)

    assert score.evaluation_confidence == 20.0
    assert score.score_with_confidence == round((score.overall_score or 0) * 0.2, 1)


@pytest.mark.asyncio
async def test_no_negative_scores(evaluator, question):
    question.baseline_tool_count = 1
    question.baseline_time_ms = 1
    question.baseline_cost_usd = 0.01
    question.baseline_tokens = 10
    question.baseline_rounds = 1
    question.payload_size_kb = None
    trace = make_trace(tool_count=100, tokens=999999, rounds=100, duration_ms=999999, cost_usd=999.0)
    score = await evaluator.evaluate(run_id=uuid4(), question=question, trace_data=trace)
    assert score.t3_efficiency >= 0
    assert score.t4_thinking >= 0
    assert score.e_performance >= 0
    assert score.c_cost >= 0
    assert score.overall_score >= 0


@pytest.mark.asyncio
async def test_evaluate_input_computes_t1_from_output_files(tmp_path):
    import pandas as pd

    output_dir = tmp_path / "输出结果"
    output_dir.mkdir()
    reference = tmp_path / "answer.xlsx"
    pd.DataFrame({"A": [1]}).to_excel(output_dir / "result.xlsx", index=False)
    pd.DataFrame({"A": [1]}).to_excel(reference, index=False)

    question = QuestionItem(
        question_id="q-t1",
        question_name="T1",
        category="Excel",
        difficulty="中等",
        prompt_file="q-t1/prompt.txt",
        output_dir="q-t1/输出结果/",
        reference_files=["q-t1/参考答案/answer.xlsx"],
        eval_config=EvalConfig(),
        baseline_tool_count=1,
        baseline_tokens=100,
        baseline_rounds=1,
        baseline_time_ms=1000,
        baseline_cost_usd=0.1,
    )
    trace_data = [
        {"type": "tool_call", "tool_name": "Read"},
        {"type": "tool_result", "tool_error": False},
        {"type": "assistant", "thinking": "done"},
        {"type": "result", "duration_ms": 500, "input_tokens": 30, "output_tokens": 10, "cost_usd": 0.01},
    ]
    item = EvaluationInput(
        question=question,
        trace_path=tmp_path / "trace.jsonl",
        output_dir=output_dir,
        reference_paths=[reference],
    )
    repo = AsyncMock()
    repo.save = AsyncMock()
    evaluator = BaselineEvaluator(score_repo=repo, comparator=ResultComparator())

    score = await evaluator.evaluate_input(uuid4(), item, trace_data)

    assert score.t1_baseline_only == 100.0
    assert score.t1_completion == 100.0
    assert score.overall_score > 0
    repo.save.assert_called_once()
