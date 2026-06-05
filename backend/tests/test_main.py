import pytest
import asyncio
from httpx import AsyncClient, ASGITransport


@pytest.fixture(autouse=True)
def setup_db():
    import src.repositories.run_repository  # noqa
    import src.repositories.score_repository  # noqa
    import src.repositories.judge_result_repository  # noqa
    import src.repositories.manifest_repository  # noqa
    from src.infrastructure.database import init_db, drop_db
    async def _setup():
        await drop_db()
        await init_db()
    asyncio.run(_setup())


@pytest.mark.asyncio
async def test_health_endpoint():
    from src.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_runs_endpoint():
    from src.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/coworkeval/v1/runs")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_manifests_endpoint():
    from src.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/coworkeval/v1/manifests")
        assert response.status_code == 200
