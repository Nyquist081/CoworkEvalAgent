from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from uuid import UUID
from src.core.schemas import TaskRun, RunStatus, Manifest
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

    # Baseline evaluation
    evaluator = BaselineEvaluator(
        score_repo=ScoreRepositoryImpl(async_session),
        comparator=ResultComparator(),
    )
    score = await evaluator.evaluate(run_id=run.id, question=question, trace_data=trace_data)

    # T1: Actually compare output vs reference (ResultComparator)
    t1_comparison = None
    if question.reference_files and question.output_dir:
        from pathlib import Path
        sample_base = Path("sample_data")
        for ref_file in question.reference_files:
            ref_path = sample_base / ref_file
            # Try to find corresponding output
            out_path = sample_base / question.output_dir
            if out_path.exists():
                candidates = list(out_path.glob("*.xlsx"))
                if candidates:
                    t1_obj_score = evaluator.comparator.compare(
                        output_path=str(candidates[0]),
                        reference_path=str(ref_path),
                        eval_config=question.eval_config,
                    )
                    t1_comparison = {
                        "reference": str(ref_file),
                        "output": str(candidates[0].relative_to(sample_base)),
                        "score": round(t1_obj_score, 1),
                        "note": "Pandas DataFrame 逐行逐列比对" if t1_obj_score > 0 else "输出与参考答案不匹配",
                    }
                    # Override T1 baseline_only with actual comparison
                    score.t1_baseline_only = t1_obj_score
                    if not judge_enabled:
                        score.t1_completion = t1_obj_score
                    break
        if not t1_comparison:
            t1_comparison = {"note": "未找到输出文件，无法比对"}

    # Judge evaluation (if enabled)
    judge_result = None
    if judge_enabled:
        try:
            from src.infrastructure.llm_gateway import LLMClient
            from src.services.judge_evaluator import JudgeEvaluator
            from src.repositories.judge_result_repository import JudgeResultRepositoryImpl
            from src.services.fusion_service import FusionService

            llm = LLMClient()
            jrepo = JudgeResultRepositoryImpl(async_session)
            judge_eval = JudgeEvaluator(judge_repo=jrepo, llm_client=llm)
            await judge_eval.evaluate(run_id=run.id, question=question, trace_data=trace_data)

            # Get the persisted judge result
            jr = await jrepo.get_by_run_and_question(run.id, question_id)
            if jr:
                judge_result = {
                    "execution_efficiency": jr.execution_efficiency,
                    "tool_accuracy": jr.tool_accuracy,
                    "thinking_efficiency": jr.thinking_efficiency,
                    "task_completion": jr.task_completion,
                    "conclusion": jr.conclusion,
                    "skill_compliance": jr.skill_compliance.model_dump() if jr.skill_compliance else None,
                    "fatal_violations": [fv.model_dump() for fv in jr.fatal_violations],
                }
                # Fuse scores
                fusion = FusionService()
                fused = await fusion.fuse(score, jr)
                score = fused
        except Exception as e:
            judge_result = {"error": str(e)}

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
