from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_skill_ab_experiment_endpoint_returns_paired_runs():
    with patch("src.api.experiments._build_skill_ab_service") as build_service:
        service = build_service.return_value
        service.run_experiment = AsyncMock(
            return_value={
                "experiment_id": "industrial-demo__baseline-no-skill__alarm-with-skill",
                "benchmark_id": "industrial-demo",
                "baseline": {
                    "run_id": "11111111-1111-4111-8111-111111111111",
                    "run_label": "baseline-no-skill",
                    "score_count": 1,
                },
                "skill": {
                    "run_id": "22222222-2222-4222-8222-222222222222",
                    "run_label": "alarm-with-skill",
                    "score_count": 1,
                },
                "compare_run_ids": [
                    "11111111-1111-4111-8111-111111111111",
                    "22222222-2222-4222-8222-222222222222",
                ],
                "compare_url": "/compare?runs=11111111-1111-4111-8111-111111111111,22222222-2222-4222-8222-222222222222",
                "preset": "mock-demo",
                "judge_enabled": False,
            }
        )

        response = client.post(
            "/coworkeval/v1/experiments/skill-ab",
            json={
                "benchmark_root": "../evaluations/industrial-demo",
                "preset": "mock-demo",
                "baseline_run_label": "baseline-no-skill",
                "skill_run_label": "alarm-with-skill",
                "judge_enabled": False,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["baseline"]["run_label"] == "baseline-no-skill"
    assert data["skill"]["run_label"] == "alarm-with-skill"
    assert data["compare_run_ids"] == [
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
    ]
    assert data["compare_url"].startswith("/compare?runs=")
    service.run_experiment.assert_awaited_once()
