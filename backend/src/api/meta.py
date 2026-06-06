from fastapi import APIRouter
from uuid import UUID
from src.infrastructure.database import async_session
from src.repositories.judge_result_repository import JudgeResultRepositoryImpl
from src.repositories.score_repository import ScoreRepositoryImpl
from src.services.meta_analyzer import MetaAnalyzer

router = APIRouter(prefix="/meta")
analyzer = MetaAnalyzer()


@router.get("/{run_id}/pass-rate", response_model=dict)
async def pass_rate(run_id: str):
    repo = ScoreRepositoryImpl(async_session)
    scores = await repo.list_by_run(UUID(run_id))
    grouped = analyzer.group_scores_by_question(scores)
    return analyzer.compute_pass_rates(grouped)


@router.get("/{run_id}/common-issues", response_model=dict)
async def common_issues(run_id: str):
    repo = JudgeResultRepositoryImpl(async_session)
    judge_results = await repo.list_by_run(UUID(run_id))
    result = analyzer.extract_common_issues(judge_results)
    return {"run_id": run_id, **result}


@router.post("/{run_id}/extract", response_model=dict)
async def extract(run_id: str):
    repo = JudgeResultRepositoryImpl(async_session)
    judge_results = await repo.list_by_run(UUID(run_id))
    result = analyzer.extract_common_issues(judge_results)
    return {"run_id": run_id, **result}
