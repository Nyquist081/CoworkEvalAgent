import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from src.services.judge_evaluator import JudgeEvaluator
from src.core.schemas import (
    QuestionItem, EvalConfig, FatalRule, JudgeDimension,
    JudgeVerdict, EfficiencyScore, ToolAccuracyScore, ThinkingScore,
    CompletionScore, FatalViolation, SkillCompliance,
)


@pytest.fixture
def question():
    return QuestionItem(
        question_id="q-001", question_name="Test",
        category="Excel", difficulty="中等",
        prompt_file="q-001/prompt.txt",
        output_dir="q-001/output/",
        eval_config=EvalConfig(fatal_rules=[
            FatalRule(rule_id="FR-001", description="No identity_type derivation",
                      dimension=JudgeDimension.TOOL_ACCURACY)
        ]),
        skills="test_skill",
    )


@pytest.fixture
def trace_data():
    return [
        {"type": "session_start", "model": "Claude-4"},
        {"type": "tool_call", "tool_name": "Read"},
        {"type": "tool_result", "tool_error": False},
        {"type": "assistant", "thinking": "...", "text": "ok"},
        {"type": "result", "status": "success", "duration_ms": 1000,
         "input_tokens": 100, "output_tokens": 50, "cost_usd": 0.01},
    ]


@pytest.fixture
def mock_verdict():
    return JudgeVerdict(
        execution_efficiency=EfficiencyScore(score=85, level="良好", reason="Good path"),
        tool_accuracy=ToolAccuracyScore(score=90, level="优秀", reason="Correct tools"),
        thinking_efficiency=ThinkingScore(score=78, level="良好", reason="Minor oversight"),
        task_completion=CompletionScore(score=88, level="良好", reason="Core task done"),
        conclusion="Overall good performance",
        critical_steps=[],
        evolution_suggestions=[],
        skill_compliance=None,
        fatal_violations=[],
    )


@pytest.mark.asyncio
async def test_judge_evaluator_returns_score(question, trace_data, mock_verdict):
    judge_repo = AsyncMock()
    judge_repo.save = AsyncMock()
    llm_client = AsyncMock()
    llm_client.ask_structured_output = AsyncMock(return_value=mock_verdict)

    evaluator = JudgeEvaluator(judge_repo=judge_repo, llm_client=llm_client)
    score = await evaluator.evaluate(run_id=uuid4(), question=question, trace_data=trace_data)

    assert score.t1_judge_only == 88.0  # task_completion score
    judge_repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_fatal_violation_sets_dimension_to_zero(question, trace_data):
    judge_repo = AsyncMock()
    judge_repo.save = AsyncMock()
    llm_client = AsyncMock()

    verdict_with_fatal = JudgeVerdict(
        execution_efficiency=EfficiencyScore(score=85, level="良好", reason="Good"),
        tool_accuracy=ToolAccuracyScore(score=90, level="优秀", reason="Correct"),
        thinking_efficiency=ThinkingScore(score=78, level="良好", reason="Fine"),
        task_completion=CompletionScore(score=88, level="良好", reason="Done"),
        conclusion="Violated fatal rule",
        critical_steps=[],
        evolution_suggestions=[],
        skill_compliance=None,
        fatal_violations=[
            FatalViolation(rule_id="FR-001", step_id="Step 3",
                           dimension=JudgeDimension.TOOL_ACCURACY,
                           reasoning="Agent derived from identity_type")
        ],
    )
    llm_client.ask_structured_output = AsyncMock(return_value=verdict_with_fatal)

    evaluator = JudgeEvaluator(judge_repo=judge_repo, llm_client=llm_client)
    score = await evaluator.evaluate(run_id=uuid4(), question=question, trace_data=trace_data)

    # The saved JudgeResult should have tool_accuracy=0 due to fatal violation
    saved_result = judge_repo.save.call_args[0][0]
    assert saved_result.tool_accuracy == 0


@pytest.mark.asyncio
async def test_trace_formatting():
    evaluator = JudgeEvaluator(judge_repo=AsyncMock(), llm_client=AsyncMock())
    trace = [{"type": "session_start"}, {"type": "result", "status": "success"}]
    formatted = evaluator._format_trace(trace)

    assert "共 2 个步骤" in formatted
    assert "### Step 1" in formatted
    assert "### Step 2" in formatted
    assert '"type": "session_start"' in formatted


@pytest.mark.asyncio
async def test_llm_failure_returns_zero_scores(question, trace_data):
    judge_repo = AsyncMock()
    judge_repo.save = AsyncMock()
    llm_client = AsyncMock()
    llm_client.ask_structured_output = AsyncMock(side_effect=Exception("API error"))

    evaluator = JudgeEvaluator(judge_repo=judge_repo, llm_client=llm_client, max_retries=1)
    score = await evaluator.evaluate(run_id=uuid4(), question=question, trace_data=trace_data)

    assert score.t1_completion == 0.0
    assert score.t1_judge_only == 0.0
