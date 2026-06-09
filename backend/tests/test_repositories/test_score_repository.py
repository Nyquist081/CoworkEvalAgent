import pytest
import pytest_asyncio
from uuid import uuid4
from src.core.schemas import ScoreResult, TraceQuality
from src.repositories.score_repository import ScoreRepositoryImpl
from src.infrastructure.database import init_db, drop_db, async_session


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield
    await drop_db()


@pytest.mark.asyncio
async def test_save_and_list_scores():
    repo = ScoreRepositoryImpl(async_session)
    run_id = uuid4()
    s1 = ScoreResult(run_id=run_id, question_id="q-001", t2_accuracy=95.0, t3_efficiency=80.0, overall_score=75.0)
    s2 = ScoreResult(run_id=run_id, question_id="q-002", t2_accuracy=88.0, t3_efficiency=90.0, overall_score=82.0)
    await repo.save(s1)
    await repo.save(s2)
    scores = await repo.list_by_run(run_id)
    assert len(scores) == 2
    scores.sort(key=lambda s: s.question_id)
    assert scores[0].t2_accuracy == 95.0
    assert scores[1].overall_score == 82.0


@pytest.mark.asyncio
async def test_get_by_run_and_question():
    repo = ScoreRepositoryImpl(async_session)
    run_id = uuid4()
    s = ScoreResult(run_id=run_id, question_id="q-001", t1_completion=70.0)
    await repo.save(s)
    fetched = await repo.get_by_run_and_question(run_id, "q-001")
    assert fetched is not None
    assert fetched.t1_completion == 70.0
    missing = await repo.get_by_run_and_question(run_id, "nonexistent")
    assert missing is None


@pytest.mark.asyncio
async def test_score_repository_round_trips_attempt_metadata():
    repo = ScoreRepositoryImpl(async_session)
    run_id = uuid4()
    score = ScoreResult(
        run_id=run_id,
        question_id="q-1",
        attempt_index=2,
        trace_quality=TraceQuality.DEGRADED,
        is_partial_score=True,
        t1_completion=75.0,
        overall_score=70.0,
        observed_tool_results=8,
        missing_tool_results=2,
        agent_tool_success_rate=87.5,
        trace_observability_rate=80.0,
        lifecycle_completeness_rate=100.0,
        metric_completeness_rate=70.0,
        reasoning_visibility_rate=85.0,
        critical_event_impact=60.0,
        evaluation_confidence=42.8,
        score_with_confidence=36.5,
        evaluation_validity="trace_incomplete",
    )

    await repo.save(score)
    loaded = await repo.get_by_run_question_attempt(run_id, "q-1", 2)

    assert loaded is not None
    assert loaded.attempt_index == 2
    assert loaded.trace_quality == TraceQuality.DEGRADED
    assert loaded.is_partial_score is True
    assert loaded.t1_completion == 75.0
    assert loaded.observed_tool_results == 8
    assert loaded.missing_tool_results == 2
    assert loaded.agent_tool_success_rate == 87.5
    assert loaded.trace_observability_rate == 80.0
    assert loaded.lifecycle_completeness_rate == 100.0
    assert loaded.metric_completeness_rate == 70.0
    assert loaded.reasoning_visibility_rate == 85.0
    assert loaded.critical_event_impact == 60.0
    assert loaded.evaluation_confidence == 42.8
    assert loaded.score_with_confidence == 36.5
    assert loaded.evaluation_validity == "trace_incomplete"
