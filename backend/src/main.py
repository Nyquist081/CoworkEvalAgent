from __future__ import annotations
import json
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.router import api_router
from src.api.websocket import router as ws_router
from src.infrastructure.database import init_db, async_session
from src.repositories.manifest_repository import ManifestRepository
from src.core.schemas import Manifest


# Import all models so Base.metadata knows about them
import src.repositories.run_repository  # noqa
import src.repositories.score_repository  # noqa
import src.repositories.judge_result_repository  # noqa
import src.repositories.manifest_repository  # noqa


async def seed_sample_data():
    """Auto-load sample manifest on startup if DB is empty."""
    repo = ManifestRepository(async_session)
    existing = await repo.list_all()
    if existing:
        return

    manifest_path = Path(__file__).parent.parent / "sample_data" / "manifest.json"
    if manifest_path.exists():
        data = json.loads(manifest_path.read_text())
        manifest = Manifest.model_validate(data)
        await repo.save(manifest)
        print(f"✅ Auto-loaded sample manifest: {manifest.benchmark_id} ({manifest.total_questions} questions)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_sample_data()
    yield


app = FastAPI(
    title="CoworkEval",
    description="Agent Evaluation Harness — upload traces, get TTTEC scores, compare versions",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
