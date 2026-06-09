from fastapi import APIRouter, HTTPException
from uuid import UUID
from src.core.schemas import ScoreResult, TaskRun
from src.infrastructure.database import async_session
from src.repositories.run_repository import RunRepositoryImpl
from src.repositories.score_repository import ScoreRepositoryImpl
from src.services.comparison_engine import ComparisonEngine
from src.services.meta_analyzer import MetaAnalyzer

router = APIRouter(prefix="/compare")
engine = ComparisonEngine()
analyzer = MetaAnalyzer()


def _parse_run_ids(run_ids: str) -> list[UUID]:
    if not run_ids.strip():
        raise HTTPException(status_code=400, detail="run_ids is required")
    try:
        return [UUID(part.strip()) for part in run_ids.split(",") if part.strip()]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid run_ids") from exc


def _run_label(run: TaskRun | None, run_id: UUID) -> str:
    if run and run.run_label:
        return run.run_label
    return str(run_id)[:8]


async def _load_run_scores(run_ids: list[UUID]) -> tuple[dict[str, list[ScoreResult]], dict[str, dict]]:
    run_repo = RunRepositoryImpl(async_session)
    score_repo = ScoreRepositoryImpl(async_session)
    scores_by_label: dict[str, list[ScoreResult]] = {}
    pass_rates_by_label: dict[str, dict] = {}

    for run_id in run_ids:
        run = await run_repo.get(run_id)
        label = _run_label(run, run_id)
        scores = await score_repo.list_by_run(run_id)
        scores_by_label[label] = scores
        grouped = analyzer.group_scores_by_question(scores)
        pass_rates_by_label[label] = analyzer.compute_pass_rates(grouped)

    return scores_by_label, pass_rates_by_label


@router.get("/radar", response_model=dict)
async def radar(run_ids: str = ""):
    ids = _parse_run_ids(run_ids)
    scores_by_label, _ = await _load_run_scores(ids)
    return engine.radar_data(scores_by_label)


@router.get("/heatmap", response_model=dict)
async def heatmap(run_ids: str = ""):
    ids = _parse_run_ids(run_ids)
    if len(ids) != 1:
        raise HTTPException(status_code=400, detail="heatmap requires exactly one run_id")
    score_repo = ScoreRepositoryImpl(async_session)
    scores = await score_repo.list_by_run(ids[0])
    return engine.heatmap_data(scores)


@router.get("/trend", response_model=dict)
async def trend(benchmark_id: str = ""):
    if not benchmark_id:
        raise HTTPException(status_code=400, detail="benchmark_id is required")
    run_repo = RunRepositoryImpl(async_session)
    score_repo = ScoreRepositoryImpl(async_session)
    runs = await run_repo.list_by_benchmark(benchmark_id)
    runs.sort(key=lambda r: r.created_at)

    sequence = []
    for run in runs:
        scores = await score_repo.list_by_run(run.id)
        overall = (
            sum(score.overall_score or 0 for score in scores) / len(scores)
            if scores else 0
        )
        pass_rate = analyzer.compute_pass_rates(
            analyzer.group_scores_by_question(scores)
        )
        sequence.append({
            "label": _run_label(run, run.id),
            "overall": round(overall, 2),
            "pass_at_k_pct": pass_rate["pass_at_k_pct"],
            "pass_power_k_pct": pass_rate["pass_power_k_pct"],
        })
    return engine.trend_data(sequence)


@router.get("/pass-rate", response_model=dict)
async def pass_rate(run_ids: str = ""):
    ids = _parse_run_ids(run_ids)
    _, pass_rates_by_label = await _load_run_scores(ids)
    return engine.pass_rate_comparison(pass_rates_by_label)


@router.get("/observability", response_model=dict)
async def observability(run_ids: str = ""):
    ids = _parse_run_ids(run_ids)
    scores_by_label, _ = await _load_run_scores(ids)
    return engine.observability_comparison(scores_by_label)
