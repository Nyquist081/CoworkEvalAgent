from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.core.schemas import EvalConfig, Manifest, QuestionItem, RunMetadata, ScoreResult, TaskRun
from src.main import app


client = TestClient(app)


def test_evaluate_offline_run_endpoint():
    run = TaskRun(benchmark_id="bench-1", run_label="skill-v2")
    score = ScoreResult(run_id=run.id, question_id="q-1", overall_score=88.0)
    bundle = SimpleNamespace(
        manifest=SimpleNamespace(benchmark_id="bench-1"),
        run_metadata=RunMetadata(
            run_label="skill-v2",
            agent_name="codex-cli",
            model="gpt-5",
            skill_version="v2",
            source="offline",
            trace_quality="full",
        ),
        inputs=[],
    )

    with patch("src.api.runs.EvaluationLoader") as loader_cls, patch("src.api.runs._build_pipeline") as build_pipeline:
        loader = loader_cls.return_value
        loader.load_run.return_value = bundle

        pipeline = build_pipeline.return_value
        pipeline.create_run = AsyncMock(return_value=run)
        pipeline.execute_offline_run = AsyncMock(return_value=[score])

        response = client.post(
            "/coworkeval/v1/runs/evaluate-offline",
            json={
                "benchmark_root": "/tmp/evaluations/bench-1",
                "run_label": "skill-v2",
                "judge_enabled": False,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == str(run.id)
    assert data["run_label"] == "skill-v2"
    assert data["score_count"] == 1


def test_evaluate_run_delegates_scoring_to_pipeline():
    question = QuestionItem(
        question_id="q-1",
        question_name="Q1",
        category="Excel",
        difficulty="中等",
        prompt_file="q-1/prompt.txt",
        output_dir="q-1/输出结果",
        reference_files=["q-1/参考答案/answer.xlsx"],
        eval_config=EvalConfig(),
    )
    manifest = Manifest(
        benchmark_id="bench-1",
        name="bench",
        version="1.0",
        created_at="2026-06-06T00:00:00Z",
        total_questions=1,
        questions=[question],
    )
    run = TaskRun(benchmark_id="bench-1")
    score = ScoreResult(
        run_id=run.id,
        question_id="q-1",
        actual_tool_calls=1,
        actual_success_calls=1,
        actual_tokens=10,
        actual_rounds=1,
        actual_time_ms=100,
        actual_cost_usd=0.01,
        t1_completion=90.0,
        t1_baseline_only=90.0,
        t2_accuracy=100.0,
        t3_efficiency=100.0,
        t4_thinking=100.0,
        e_performance=100.0,
        c_cost=100.0,
        overall_score=98.0,
    )

    with patch("src.api.runs.ManifestRepository") as manifest_repo_cls, patch("src.api.runs._build_pipeline") as build_pipeline:
        manifest_repo = manifest_repo_cls.return_value
        manifest_repo.get = AsyncMock(return_value=manifest)

        pipeline = build_pipeline.return_value
        pipeline.create_run = AsyncMock(return_value=run)
        pipeline.execute_single_input = AsyncMock(return_value=score)
        pipeline.judge_repo = None

        response = client.post(
            "/coworkeval/v1/runs/evaluate",
            data={
                "benchmark_id": "bench-1",
                "question_id": "q-1",
                "judge_enabled": "true",
            },
            files={
                "trace_file": (
                    "trace.jsonl",
                    b'{"type":"result","status":"success"}\n',
                    "application/jsonl",
                )
            },
        )

    assert response.status_code == 200
    pipeline.execute_single_input.assert_called_once()
    _, evaluation_input, trace_data = pipeline.execute_single_input.call_args.args[:3]
    assert evaluation_input.question_id == "q-1"
    assert trace_data == [{"type": "result", "status": "success"}]
    assert pipeline.execute_single_input.call_args.kwargs["judge_enabled"] is True
    assert response.json()["scores"]["overall_score"] == 98.0


def test_scores_summary_route_is_not_shadowed():
    run = TaskRun(benchmark_id="bench-1")
    score = ScoreResult(run_id=run.id, question_id="q-1", overall_score=88.0)

    with patch("src.api.scores.ScoreRepositoryImpl") as repo_cls:
        repo = repo_cls.return_value
        repo.list_by_run = AsyncMock(return_value=[score])

        response = client.get(f"/coworkeval/v1/runs/{run.id}/scores/summary")

    assert response.status_code == 200
    assert response.json()["overall_avg"] == 88.0
