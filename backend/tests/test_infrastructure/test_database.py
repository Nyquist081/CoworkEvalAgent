import pytest
from src.infrastructure.database import engine, async_session

@pytest.mark.asyncio
async def test_engine_connects():
    assert engine is not None
    async with async_session() as session:
        assert session is not None
