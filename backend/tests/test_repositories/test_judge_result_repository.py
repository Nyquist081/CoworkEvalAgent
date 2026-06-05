import pytest
import pytest_asyncio
from uuid import uuid4
from src.core.schemas import JudgeResult
from src.repositories.judge_result_repository import JudgeResultRepositoryImpl
from src.infrastructure.database import init_db, drop_db, async_session


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield
    await drop_db()


@pytest.mark.asyncio
async def test_save_and_list_judge_results():
    repo = JudgeResultRepositoryImpl(async_session)
    run_id = uuid4()
    j1 = JudgeResult(run_id=run_id, question_id="q-001", execution_efficiency=85, tool_accuracy=90, thinking_efficiency=78, task_completion=88, conclusion="Good overall")
    j2 = JudgeResult(run_id=run_id, question_id="q-002", execution_efficiency=65, conclusion="Needs improvement")
    await repo.save(j1)
    await repo.save(j2)
    results = await repo.list_by_run(run_id)
    assert len(results) == 2
    assert results[0].execution_efficiency == 85
    assert results[1].conclusion == "Needs improvement"
