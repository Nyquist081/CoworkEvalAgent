from fastapi import APIRouter, HTTPException
from uuid import UUID
from src.core.schemas import ScoreResult
from src.repositories.score_repository import ScoreRepositoryImpl
from src.infrastructure.database import async_session

router = APIRouter()

def _repo():
    return ScoreRepositoryImpl(async_session)


@router.get("/runs/{run_id}/scores", response_model=list[ScoreResult])
async def list_scores(run_id: UUID):
    return await _repo().list_by_run(run_id)


@router.get("/runs/{run_id}/scores/summary", response_model=dict)
async def get_summary(run_id: UUID):
    scores = await _repo().list_by_run(run_id)
    if not scores:
        return {"run_id": str(run_id), "total_questions": 0, "overall_avg": 0}
    avg = sum(s.overall_score or 0 for s in scores) / len(scores)
    return {
        "run_id": str(run_id),
        "total_questions": len(scores),
        "overall_avg": round(avg, 2),
    }


@router.get("/runs/{run_id}/scores/{question_id}", response_model=ScoreResult)
async def get_score(run_id: UUID, question_id: str):
    s = await _repo().get_by_run_and_question(run_id, question_id)
    if not s:
        raise HTTPException(status_code=404, detail="Score not found")
    return s
