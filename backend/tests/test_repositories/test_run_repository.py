import pytest
import pytest_asyncio
from uuid import uuid4
from src.core.schemas import TaskRun, RunStatus
from src.repositories.run_repository import RunRepositoryImpl
from src.infrastructure.database import init_db, drop_db, async_session


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield
    await drop_db()


@pytest.mark.asyncio
async def test_save_and_get_run():
    repo = RunRepositoryImpl(async_session)
    run = TaskRun(benchmark_id="bench-1", status=RunStatus.PENDING)
    saved = await repo.save(run)
    assert saved.id == run.id
    fetched = await repo.get(run.id)
    assert fetched is not None
    assert fetched.benchmark_id == "bench-1"
    assert fetched.status == RunStatus.PENDING


@pytest.mark.asyncio
async def test_update_status():
    repo = RunRepositoryImpl(async_session)
    run = TaskRun(benchmark_id="bench-1")
    await repo.save(run)
    updated = await repo.update_status(run.id, RunStatus.PARSING_TRACE)
    assert updated.status == RunStatus.PARSING_TRACE


@pytest.mark.asyncio
async def test_update_status_with_error():
    repo = RunRepositoryImpl(async_session)
    run = TaskRun(benchmark_id="bench-1")
    await repo.save(run)
    updated = await repo.update_status(run.id, RunStatus.FAILED, error_stack="Traceback: IncompleteTraceError")
    assert updated.status == RunStatus.FAILED
    assert "IncompleteTraceError" in updated.error_stack


@pytest.mark.asyncio
async def test_list_by_benchmark():
    repo = RunRepositoryImpl(async_session)
    await repo.save(TaskRun(benchmark_id="bench-1"))
    await repo.save(TaskRun(benchmark_id="bench-1"))
    await repo.save(TaskRun(benchmark_id="bench-2"))
    runs = await repo.list_by_benchmark("bench-1")
    assert len(runs) == 2


@pytest.mark.asyncio
async def test_delete():
    repo = RunRepositoryImpl(async_session)
    run = await repo.save(TaskRun(benchmark_id="bench-1"))
    await repo.delete(run.id)
    fetched = await repo.get(run.id)
    assert fetched is None
