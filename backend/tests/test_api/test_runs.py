from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.core.schemas import RunMetadata, ScoreResult, TaskRun
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
