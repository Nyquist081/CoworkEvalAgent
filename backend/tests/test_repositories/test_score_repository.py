import pytest
import pytest_asyncio
from uuid import uuid4
from src.core.schemas import ScoreResult
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
