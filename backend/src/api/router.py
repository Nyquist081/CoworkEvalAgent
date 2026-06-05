from fastapi import APIRouter
from src.api.runs import router as runs_router
from src.api.scores import router as scores_router
from src.api.manifests import router as manifests_router
from src.api.comparison import router as comparison_router
from src.api.meta import router as meta_router
from src.api.websocket import router as websocket_router

api_router = APIRouter(prefix="/coworkeval/v1")

api_router.include_router(runs_router, tags=["runs"])
api_router.include_router(scores_router, tags=["scores"])
api_router.include_router(manifests_router, tags=["manifests"])
api_router.include_router(comparison_router, tags=["comparison"])
api_router.include_router(meta_router, tags=["meta"])
api_router.include_router(websocket_router, tags=["websocket"])
