import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from src.services.pipeline_runner import PipelineRunner
from src.core.schemas import TaskRun, Manifest, QuestionItem, EvalConfig, RunStatus, ScoreResult
from src.core.interfaces import RunRepository
from src.core.exceptions import EvaluationError


@pytest.fixture
def mock_run_repo():
    repo = AsyncMock(spec=RunRepository)
    repo.save = AsyncMock()
    repo.update_status = AsyncMock()
    return repo


@pytest.fixture
def manifest():
    return Manifest(
        benchmark_id="bench-1", name="test", version="1.0",
        created_at=datetime.now(timezone.utc),
        total_questions=2,
        questions=[
            QuestionItem(question_id="q-001", question_name="Q1", category="Excel",
                         difficulty="中等", prompt_file="q-001/prompt.txt",
                         output_dir="q-001/output/", eval_config=EvalConfig(),
                         baseline_tool_count=5, baseline_tokens=100000,
                         baseline_rounds=10, baseline_time_ms=30000, baseline_cost_usd=1.0),
            QuestionItem(question_id="q-002", question_name="Q2", category="Excel",
                         difficulty="困难", prompt_file="q-002/prompt.txt",
                         output_dir="q-002/output/", eval_config=EvalConfig(),
                         baseline_tool_count=8, baseline_tokens=200000,
                         baseline_rounds=15, baseline_time_ms=50000, baseline_cost_usd=2.0),
        ],
    )


@pytest.mark.asyncio
async def test_create_run(mock_run_repo, manifest):
    runner = PipelineRunner(run_repo=mock_run_repo, baseline_evaluator=AsyncMock())
    run = await runner.create_run(manifest, judge_enabled=False)
    assert run.benchmark_id == "bench-1"
    assert run.judge_enabled == False
    mock_run_repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_status_transitions(mock_run_repo, manifest):
    mock_evaluator = AsyncMock()
    mock_evaluator.evaluate = AsyncMock(return_value=ScoreResult(
        run_id=uuid4(), question_id="q-001", t2_accuracy=100.0, overall_score=95.0
    ))
    runner = PipelineRunner(run_repo=mock_run_repo, baseline_evaluator=mock_evaluator)
    run = await runner.create_run(manifest, judge_enabled=False)

    with patch.object(runner, "_load_traces", return_value={
        "q-001": [{"type": "result", "status": "success"}],
        "q-002": [{"type": "result", "status": "success"}],
    }):
        await runner.execute(run.id, manifest)

    status_calls = [c.args[1] for c in mock_run_repo.update_status.call_args_list]
    assert RunStatus.PARSING_TRACE in status_calls
    assert RunStatus.EVALUATING_BASELINE in status_calls
    assert RunStatus.COMPLETED in status_calls


@pytest.mark.asyncio
async def test_pipeline_failure_sets_failed(mock_run_repo, manifest):
    mock_evaluator = AsyncMock()
    mock_evaluator.evaluate = AsyncMock(side_effect=Exception("Boom"))
    runner = PipelineRunner(run_repo=mock_run_repo, baseline_evaluator=mock_evaluator)
    run = await runner.create_run(manifest, judge_enabled=False)

    with patch.object(runner, "_load_traces", return_value={
        "q-001": [{"type": "result", "status": "success"}],
    }):
        with pytest.raises(EvaluationError):
            await runner.execute(run.id, manifest)

    fail_calls = [c for c in mock_run_repo.update_status.call_args_list if c.args[1] == RunStatus.FAILED]
    assert len(fail_calls) >= 1


@pytest.mark.asyncio
async def test_concurrent_question_processing(mock_run_repo):
    import asyncio
    call_order = []
    mock_evaluator = AsyncMock()

    async def delayed(run_id, question, trace_data):
        call_order.append(question.question_id)
        await asyncio.sleep(0.01)
        return ScoreResult(run_id=run_id, question_id=question.question_id)

    mock_evaluator.evaluate = delayed
    runner = PipelineRunner(run_repo=mock_run_repo, baseline_evaluator=mock_evaluator)

    questions = [
        QuestionItem(question_id=f"q-{i:03d}", question_name=f"Q{i}",
                     category="Excel", difficulty="中等",
                     prompt_file=f"q-{i:03d}/prompt.txt",
                     output_dir=f"q-{i:03d}/output/", eval_config=EvalConfig(),
                     baseline_tool_count=5, baseline_tokens=100000,
                     baseline_rounds=10, baseline_time_ms=30000, baseline_cost_usd=1.0)
        for i in range(5)
    ]
    trace_map = {q.question_id: [{"type": "result", "status": "success"}] for q in questions}
    await runner._execute_questions(uuid4(), questions, trace_map)
    assert len(call_order) == 5
