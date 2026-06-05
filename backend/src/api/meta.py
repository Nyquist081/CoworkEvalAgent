from fastapi import APIRouter
from src.services.meta_analyzer import MetaAnalyzer

router = APIRouter(prefix="/meta")
analyzer = MetaAnalyzer()


@router.get("/{run_id}/pass-rate", response_model=dict)
async def pass_rate(run_id: str):
    return analyzer.compute_pass_rates({})


@router.get("/{run_id}/common-issues", response_model=dict)
async def common_issues(run_id: str):
    return {"run_id": run_id, "common_issues": [], "status": "not_extracted"}


@router.post("/{run_id}/extract", response_model=dict)
async def extract(run_id: str):
    return {"run_id": run_id, "status": "extraction_triggered"}
