from __future__ import annotations
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./coworkeval.db")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, checkfirst=True))
        if engine.url.get_backend_name().startswith("sqlite"):
            await _ensure_sqlite_score_columns(conn)


async def drop_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _ensure_sqlite_score_columns(conn) -> None:
    result = await conn.execute(text("PRAGMA table_info(score_results)"))
    existing = {row[1] for row in result.fetchall()}
    columns = {
        "observed_tool_results": "FLOAT DEFAULT 0",
        "missing_tool_results": "FLOAT DEFAULT 0",
        "agent_tool_success_rate": "FLOAT DEFAULT 100.0",
        "trace_observability_rate": "FLOAT DEFAULT 100.0",
        "lifecycle_completeness_rate": "FLOAT DEFAULT 100.0",
        "metric_completeness_rate": "FLOAT DEFAULT 100.0",
        "reasoning_visibility_rate": "FLOAT DEFAULT 100.0",
        "critical_event_impact": "FLOAT DEFAULT 100.0",
        "evaluation_confidence": "FLOAT DEFAULT 100.0",
        "score_with_confidence": "FLOAT",
        "evaluation_validity": "VARCHAR DEFAULT 'valid'",
    }
    for name, definition in columns.items():
        if name not in existing:
            await conn.execute(text(f"ALTER TABLE score_results ADD COLUMN {name} {definition}"))
