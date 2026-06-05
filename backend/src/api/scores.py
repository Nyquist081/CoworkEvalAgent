from fastapi import APIRouter, HTTPException
from uuid import UUID
from src.core.schemas import ScoreResult

router = APIRouter()

_scores_store: dict[str, list[ScoreResult]] = {}


@router.get("/runs/{run_id}/scores", response_model=list[ScoreResult])
async def list_scores(run_id: UUID):
    return _scores_store.get(str(run_id), [])


@router.get("/runs/{run_id}/scores/{question_id}", response_model=ScoreResult)
async def get_score(run_id: UUID, question_id: str):
    scores = _scores_store.get(str(run_id), [])
    for s in scores:
        if s.question_id == question_id:
            return s
    raise HTTPException(status_code=404, detail="Score not found")


@router.get("/runs/{run_id}/scores/summary", response_model=dict)
async def get_summary(run_id: UUID):
    scores = _scores_store.get(str(run_id), [])
    if not scores:
        return {"run_id": str(run_id), "total_questions": 0, "overall_avg": 0}
    avg = sum(s.overall_score or 0 for s in scores) / len(scores)
    return {
        "run_id": str(run_id),
        "total_questions": len(scores),
        "overall_avg": round(avg, 2),
    }
