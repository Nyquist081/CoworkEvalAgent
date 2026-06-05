import pytest
from uuid import uuid4
from src.services.fusion_service import FusionService
from src.core.schemas import ScoreResult, JudgeResult


@pytest.fixture
def baseline():
    return ScoreResult(
        run_id=uuid4(), question_id="q-001",
        t1_baseline_only=0.0, t1_completion=0.0,
        t2_accuracy=80.0, t3_efficiency=90.0, t4_thinking=70.0,
        e_performance=85.0, c_cost=95.0, overall_score=70.0,
    )


@pytest.fixture
def judge():
    return JudgeResult(
        run_id=uuid4(), question_id="q-001",
        execution_efficiency=60, tool_accuracy=100,
        thinking_efficiency=80, task_completion=90,
        conclusion="Good",
    )


@pytest.mark.asyncio
async def test_fusion_blends_correctly(baseline, judge):
    service = FusionService()
    result = await service.fuse(baseline, judge)

    assert result.t1_completion == pytest.approx(45.0)  # (0 + 90) / 2
    assert result.t2_accuracy == pytest.approx(90.0)     # (80 + 100) / 2
    assert result.t3_efficiency == pytest.approx(75.0)   # (90 + 60) / 2
    assert result.t4_thinking == pytest.approx(75.0)     # (70 + 80) / 2
    assert result.e_performance == 85.0                   # NOT fused
    assert result.c_cost == 95.0                          # NOT fused


@pytest.mark.asyncio
async def test_fusion_without_judge(baseline):
    service = FusionService()
    result = await service.fuse(baseline, None)

    # T1 stays at baseline
    assert result.t1_completion == 0.0
    # T2-T4 unchanged
    assert result.t2_accuracy == 80.0


@pytest.mark.asyncio
async def test_fusion_clamps_to_0_100(baseline, judge):
    baseline.t2_accuracy = 200.0  # impossible but test clamping
    judge.tool_accuracy = 200
    service = FusionService()
    result = await service.fuse(baseline, judge)
    assert result.t2_accuracy <= 100.0
    assert result.t2_accuracy >= 0.0
