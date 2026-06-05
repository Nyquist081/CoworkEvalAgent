from fastapi import APIRouter
from src.services.comparison_engine import ComparisonEngine

router = APIRouter(prefix="/compare")
engine = ComparisonEngine()


@router.get("/radar", response_model=dict)
async def radar(run_ids: str = ""):
    return {"dimensions": ["T1", "T2", "T3", "T4", "E", "C"], "series": [], "message": "Provide run_ids"}


@router.get("/heatmap", response_model=dict)
async def heatmap(run_ids: str = ""):
    return {"questions": [], "dimensions": ["T1", "T2", "T3", "T4", "E", "C"], "data": []}


@router.get("/trend", response_model=dict)
async def trend(benchmark_id: str = ""):
    return {"labels": [], "overall_scores": [], "pass_at_k_pcts": [], "pass_power_k_pcts": []}


@router.get("/pass-rate", response_model=dict)
async def pass_rate(run_ids: str = ""):
    return {"runs": []}
