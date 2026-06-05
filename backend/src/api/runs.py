from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from uuid import UUID
from src.core.schemas import TaskRun, RunStatus, Manifest
from src.repositories.run_repository import RunRepositoryImpl
from src.repositories.manifest_repository import ManifestRepository
from src.infrastructure.database import async_session
from src.services.pipeline_runner import PipelineRunner
from src.services.baseline_evaluator import BaselineEvaluator
from src.repositories.score_repository import ScoreRepositoryImpl
from src.evaluator.result_comparator import ResultComparator

router = APIRouter(prefix="/runs")


def _run_repo():
    return RunRepositoryImpl(async_session)


def _build_pipeline():
    return PipelineRunner(
        run_repo=_run_repo(),
        baseline_evaluator=BaselineEvaluator(
            score_repo=ScoreRepositoryImpl(async_session),
            comparator=ResultComparator(),
        ),
    )


@router.post("", response_model=TaskRun, status_code=201)
async def create_run(benchmark_id: str = Form(...), judge_enabled: bool = Form(False)):
    manifest_repo = ManifestRepository(async_session)
    manifest = await manifest_repo.get(benchmark_id)
    if not manifest:
        raise HTTPException(404, f"Manifest not found: {benchmark_id}")

    pipeline = _build_pipeline()
    run = await pipeline.create_run(manifest, judge_enabled=judge_enabled)
    return run


@router.post("/evaluate", response_model=dict)
async def evaluate_run(
    benchmark_id: str = Form(...),
    trace_file: UploadFile = File(...),
    question_id: str = Form(...),
    judge_enabled: bool = Form(False),
):
    """Upload a trace file + manifest, run evaluation, return scores."""
    import json, asyncio
    from src.infrastructure.trace_parser import TraceParser

    # Load manifest
    manifest_repo = ManifestRepository(async_session)
    manifest = await manifest_repo.get(benchmark_id)
    if not manifest:
        raise HTTPException(404, f"Manifest not found: {benchmark_id}")

    # Find question
    question = None
    for q in manifest.questions:
        if q.question_id == question_id:
            question = q
            break
    if not question:
        raise HTTPException(404, f"Question not found: {question_id}")

    # Parse uploaded trace
    content = await trace_file.read()
    lines = [l for l in content.decode("utf-8").strip().split("\n") if l.strip()]
    parser = TraceParser()
    trace_data = await parser.parse_lines(lines)

    # Create run
    pipeline = _build_pipeline()
    run = await pipeline.create_run(manifest, judge_enabled=judge_enabled)

    # Evaluate
    from src.services.fusion_service import FusionService
    evaluator = BaselineEvaluator(
        score_repo=ScoreRepositoryImpl(async_session),
        comparator=ResultComparator(),
    )
    score = await evaluator.evaluate(run_id=run.id, question=question, trace_data=trace_data)

    return {
        "run_id": str(run.id),
        "question_id": question_id,
        "scores": {
            "t1_completion": score.t1_completion,
            "t2_accuracy": score.t2_accuracy,
            "t3_efficiency": score.t3_efficiency,
            "t4_thinking": score.t4_thinking,
            "e_performance": score.e_performance,
            "c_cost": score.c_cost,
            "overall_score": score.overall_score,
        },
        "metrics": {
            "tool_calls": score.actual_tool_calls,
            "success_calls": score.actual_success_calls,
            "tokens": score.actual_tokens,
            "rounds": score.actual_rounds,
            "duration_ms": score.actual_time_ms,
            "cost_usd": score.actual_cost_usd,
        },
    }


@router.get("", response_model=list[TaskRun])
async def list_runs(benchmark_id: str | None = None, status: RunStatus | None = None):
    repo = _run_repo()
    if benchmark_id:
        runs = await repo.list_by_benchmark(benchmark_id)
    else:
        runs = await repo.list_all()
    if status:
        runs = [r for r in runs if r.status == status]
    return runs


@router.get("/{run_id}", response_model=TaskRun)
async def get_run(run_id: UUID):
    run = await _run_repo().get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.delete("/{run_id}", status_code=204)
async def delete_run(run_id: UUID):
    await _run_repo().delete(run_id)
