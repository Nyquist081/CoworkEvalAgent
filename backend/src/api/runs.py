from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from pathlib import Path
from uuid import UUID
from src.core.schemas import EvaluationInput, TaskRun, RunStatus, Manifest
from src.repositories.run_repository import RunRepositoryImpl
from src.repositories.manifest_repository import ManifestRepository
from src.infrastructure.database import async_session
from src.services.pipeline_runner import PipelineRunner
from src.services.baseline_evaluator import BaselineEvaluator
from src.services.evaluation_loader import EvaluationLoader
from src.services.fusion_service import FusionService
from src.services.judge_evaluator import JudgeEvaluator
from src.infrastructure.llm_gateway import LLMClient
from src.repositories.judge_result_repository import JudgeResultRepositoryImpl
from src.repositories.score_repository import ScoreRepositoryImpl
from src.evaluator.result_comparator import ResultComparator

router = APIRouter(prefix="/runs")


class OfflineEvaluateRequest(BaseModel):
    benchmark_root: str
    run_label: str
    judge_enabled: bool = False


def _sample_data_root() -> Path:
    for candidate in (Path("backend/sample_data"), Path("sample_data")):
        if candidate.exists():
            return candidate
    return Path("backend/sample_data")


def _build_single_trace_input(question) -> EvaluationInput:
    sample_base = _sample_data_root()
    return EvaluationInput(
        question=question,
        trace_path=Path("uploaded-trace.jsonl"),
        output_dir=sample_base / question.output_dir,
        reference_paths=[sample_base / ref for ref in question.reference_files],
        attempt_index=1,
    )


def _build_t1_comparison(evaluation_input: EvaluationInput, score) -> dict | None:
    if not evaluation_input.reference_paths:
        return None
    output_dir = evaluation_input.output_dir
    if not output_dir.exists():
        return {"note": "未找到输出文件，无法比对"}

    candidates = sorted(output_dir.glob("*.xlsx"))
    if not candidates:
        return {"note": "未找到输出文件，无法比对"}

    sample_base = _sample_data_root()
    output = candidates[0]
    reference = evaluation_input.reference_paths[0]
    return {
        "reference": str(reference.relative_to(sample_base)) if reference.is_relative_to(sample_base) else str(reference),
        "output": str(output.relative_to(sample_base)) if output.is_relative_to(sample_base) else str(output),
        "score": round(score.t1_baseline_only or 0.0, 1),
        "note": "Pandas DataFrame 逐行逐列比对" if (score.t1_baseline_only or 0) > 0 else "输出与参考答案不匹配",
    }


async def _load_judge_payload(pipeline: PipelineRunner, run_id: UUID, question_id: str) -> dict | None:
    judge_repo = getattr(pipeline, "judge_repo", None)
    if judge_repo is None:
        return None
    judge_result = await judge_repo.get_by_run_and_question(run_id, question_id)
    if judge_result is None:
        return None
    return {
        "execution_efficiency": judge_result.execution_efficiency,
        "tool_accuracy": judge_result.tool_accuracy,
        "thinking_efficiency": judge_result.thinking_efficiency,
        "task_completion": judge_result.task_completion,
        "conclusion": judge_result.conclusion,
        "skill_compliance": (
            judge_result.skill_compliance.model_dump()
            if judge_result.skill_compliance else None
        ),
        "fatal_violations": [
            violation.model_dump() for violation in judge_result.fatal_violations
        ],
    }


def _run_repo():
    return RunRepositoryImpl(async_session)


def _build_pipeline():
    judge_repo = JudgeResultRepositoryImpl(async_session)
    return PipelineRunner(
        run_repo=_run_repo(),
        baseline_evaluator=BaselineEvaluator(
            score_repo=ScoreRepositoryImpl(async_session),
            comparator=ResultComparator(),
        ),
        judge_evaluator=JudgeEvaluator(
            judge_repo=judge_repo,
            llm_client=LLMClient(),
        ),
        fusion_service=FusionService(),
        judge_repo=judge_repo,
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


@router.post("/evaluate-offline", response_model=dict)
async def evaluate_offline_run(request: OfflineEvaluateRequest):
    loader = EvaluationLoader(request.benchmark_root)
    bundle = loader.load_run(request.run_label)
    pipeline = _build_pipeline()
    run = await pipeline.create_run(
        bundle.manifest,
        judge_enabled=request.judge_enabled,
        run_metadata=bundle.run_metadata,
    )
    scores = await pipeline.execute_offline_run(
        run.id,
        bundle.inputs,
        judge_enabled=request.judge_enabled,
    )
    return {
        "run_id": str(run.id),
        "benchmark_id": bundle.manifest.benchmark_id,
        "run_label": bundle.run_metadata.run_label,
        "score_count": len(scores),
        "judge_enabled": request.judge_enabled,
    }


@router.post("/evaluate", response_model=dict)
async def evaluate_run(
    benchmark_id: str = Form(...),
    trace_file: UploadFile = File(...),
    question_id: str = Form(...),
    judge_enabled: bool = Form(False),
):
    """Upload a trace file + manifest, run evaluation, return scores."""
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

    evaluation_input = _build_single_trace_input(question)
    score = await pipeline.execute_single_input(
        run.id,
        evaluation_input,
        trace_data,
        judge_enabled=judge_enabled,
    )
    t1_comparison = _build_t1_comparison(evaluation_input, score)
    judge_result = await _load_judge_payload(pipeline, run.id, question_id) if judge_enabled else None

    return {
        "run_id": str(run.id),
        "question_id": question_id,
        "question_name": question.question_name,
        "difficulty": question.difficulty,
        "skills": question.skills,
        "baseline": {
            "tool_count": question.baseline_tool_count,
            "tokens": question.baseline_tokens,
            "rounds": question.baseline_rounds,
            "time_ms": question.baseline_time_ms,
            "cost_usd": question.baseline_cost_usd,
        },
        "actual": {
            "tool_calls": score.actual_tool_calls,
            "success_calls": score.actual_success_calls,
            "tokens": score.actual_tokens,
            "rounds": score.actual_rounds,
            "duration_ms": score.actual_time_ms,
            "cost_usd": score.actual_cost_usd,
        },
        "scores": {
            "t1_completion": score.t1_completion,
            "t2_accuracy": score.t2_accuracy,
            "t3_efficiency": score.t3_efficiency,
            "t4_thinking": score.t4_thinking,
            "e_performance": score.e_performance,
            "c_cost": score.c_cost,
            "overall_score": score.overall_score,
        },
        "t1_comparison": t1_comparison,
        "judge": judge_result,
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
