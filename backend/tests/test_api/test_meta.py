from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from src.core.schemas import ScoreResult
from src.main import app


client = TestClient(app)


def test_meta_pass_rate_uses_scores_from_repository():
    run_id = uuid4()
    scores = [
        ScoreResult(run_id=run_id, question_id="q-1", attempt_index=1, t1_completion=80),
        ScoreResult(run_id=run_id, question_id="q-1", attempt_index=2, t1_completion=30),
        ScoreResult(run_id=run_id, question_id="q-2", attempt_index=1, t1_completion=90),
    ]

    with patch("src.api.meta.ScoreRepositoryImpl") as repo_cls:
        repo = repo_cls.return_value
        repo.list_by_run = AsyncMock(return_value=scores)
        response = client.get(f"/coworkeval/v1/meta/{run_id}/pass-rate")

    assert response.status_code == 200
    data = response.json()
    assert data["total_questions"] == 2
    assert data["pass_at_k_pct"] == 100.0
    assert data["threshold"] == 60.0


def test_common_issues_uses_judge_repository():
    from src.core.schemas import CriticalStep, JudgeResult

    run_id = uuid4()
    judge = JudgeResult(
        run_id=run_id,
        question_id="q-1",
        critical_steps=[
            CriticalStep(
                step_id="Step 2",
                assessment="ERRONEOUS",
                observation="工具参数错误",
                context_chain="参数构造错误导致失败",
                root_cause="未读取文件名",
                expected_action="先确认路径",
            )
        ],
    )

    with patch("src.api.meta.JudgeResultRepositoryImpl") as repo_cls:
        repo = repo_cls.return_value
        repo.list_by_run = AsyncMock(return_value=[judge])
        response = client.get(f"/coworkeval/v1/meta/{run_id}/common-issues")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "extracted"
    assert data["common_issues"][0]["question_ids"] == ["q-1"]
