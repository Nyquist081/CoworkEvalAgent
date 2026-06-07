import asyncio
import os

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./coworkeval_test.db")

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
