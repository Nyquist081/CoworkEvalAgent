from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from src.core.schemas import ScoreResult, TaskRun
from src.main import app


client = TestClient(app)


def test_compare_radar_returns_real_series():
    run_id = uuid4()
    run = TaskRun(id=run_id, benchmark_id="bench-1", run_label="skill-v2")
    score = ScoreResult(
        run_id=run_id,
        question_id="q-1",
        t1_completion=80,
        t2_accuracy=90,
        t3_efficiency=70,
        t4_thinking=60,
        e_performance=100,
        c_cost=95,
    )

    with patch("src.api.comparison.RunRepositoryImpl") as run_repo_cls, patch("src.api.comparison.ScoreRepositoryImpl") as score_repo_cls:
        run_repo_cls.return_value.get = AsyncMock(return_value=run)
        score_repo_cls.return_value.list_by_run = AsyncMock(return_value=[score])
        response = client.get(f"/coworkeval/v1/compare/radar?run_ids={run_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["series"][0]["label"] == "skill-v2"
    assert data["series"][0]["values"] == [80.0, 90.0, 70.0, 60.0, 100.0, 95.0]


def test_compare_pass_rate_returns_real_runs():
    run_id = uuid4()
    run = TaskRun(id=run_id, benchmark_id="bench-1", run_label="skill-v2")
    scores = [ScoreResult(run_id=run_id, question_id="q-1", attempt_index=1, t1_completion=80)]

    with patch("src.api.comparison.RunRepositoryImpl") as run_repo_cls, patch("src.api.comparison.ScoreRepositoryImpl") as score_repo_cls:
        run_repo_cls.return_value.get = AsyncMock(return_value=run)
        score_repo_cls.return_value.list_by_run = AsyncMock(return_value=scores)
        response = client.get(f"/coworkeval/v1/compare/pass-rate?run_ids={run_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["runs"][0]["label"] == "skill-v2"
    assert data["runs"][0]["pass_at_k_pct"] == 100.0
