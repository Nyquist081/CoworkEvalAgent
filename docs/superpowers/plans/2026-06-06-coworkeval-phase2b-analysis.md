# CoworkEval Phase 2B Analysis APIs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect multi-version comparison, pass@k/pass^k, and common issue endpoints to real persisted run, score, and judge data.

**Architecture:** Keep computation in services and repository access in API composition code. `ComparisonEngine` remains a pure chart-data transformer. `MetaAnalyzer` owns pass-rate grouping and deterministic common-issue extraction from persisted `JudgeResult` summaries.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, SQLAlchemy async, pytest/pytest-asyncio, uv.

---

## File Structure

- Modify `backend/src/services/meta_analyzer.py`: default threshold becomes 60, empty input is safe, add `group_scores_by_question()` and deterministic `extract_common_issues()`.
- Modify `backend/src/api/meta.py`: fetch scores/judge results from repositories for pass-rate and common issues.
- Modify `backend/src/api/comparison.py`: parse run ids, fetch run labels and scores, return real radar, heatmap, trend, and pass-rate data.
- Add tests in `backend/tests/test_services/test_meta_analyzer.py`, `backend/tests/test_api/test_meta.py`, and `backend/tests/test_api/test_comparison.py`.

---

## Task 1: Fix MetaAnalyzer Pass Rates and Common Issue Extraction

**Files:**
- Modify: `backend/src/services/meta_analyzer.py`
- Test: `backend/tests/test_services/test_meta_analyzer.py`

- [ ] **Step 1: Add failing tests**

Append these tests to `backend/tests/test_services/test_meta_analyzer.py`:

```python
def test_empty_pass_rates_do_not_crash():
    analyzer = MetaAnalyzer()
    result = analyzer.compute_pass_rates({})
    assert result["total_questions"] == 0
    assert result["pass_at_k_pct"] == 0.0
    assert result["pass_power_k_pct"] == 0.0
    assert result["k"] == 0
    assert result["threshold"] == 60.0


def test_group_scores_by_question_sorts_attempts():
    from uuid import uuid4
    from src.core.schemas import ScoreResult

    run_id = uuid4()
    scores = [
        ScoreResult(run_id=run_id, question_id="q-1", attempt_index=2, t1_completion=30),
        ScoreResult(run_id=run_id, question_id="q-1", attempt_index=1, t1_completion=80),
        ScoreResult(run_id=run_id, question_id="q-2", attempt_index=1, t1_completion=90),
    ]

    grouped = MetaAnalyzer.group_scores_by_question(scores)

    assert [s.attempt_index for s in grouped["q-1"]] == [1, 2]
    assert list(grouped.keys()) == ["q-1", "q-2"]


def test_extract_common_issues_from_judge_results():
    from uuid import uuid4
    from src.core.schemas import CriticalStep, EvolutionSuggestion, JudgeResult

    run_id = uuid4()
    judge_results = [
        JudgeResult(
            run_id=run_id,
            question_id="q-1",
            execution_efficiency=60,
            tool_accuracy=80,
            thinking_efficiency=70,
            task_completion=75,
            conclusion="存在重复读取文件的问题",
            critical_steps=[
                CriticalStep(
                    step_id="Step 3",
                    assessment="REDUNDANT",
                    observation="重复读取同一 Excel 文件",
                    context_chain="前因是未缓存表结构, 后果是多消耗步骤",
                    root_cause="缺少中间结果复用",
                    expected_action="复用已读取的表结构",
                )
            ],
            evolution_suggestions=[
                EvolutionSuggestion(type="execution_path", suggestion="读取文件后缓存列名")
            ],
        )
    ]

    result = MetaAnalyzer().extract_common_issues(judge_results)

    assert result["status"] == "extracted"
    assert result["summary"]
    assert result["common_issues"][0]["question_ids"] == ["q-1"]
    assert result["improvement_suggestions"][0]["suggestion"] == "读取文件后缓存列名"
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd backend && uv run pytest tests/test_services/test_meta_analyzer.py -v
```

Expected: FAIL because empty input still crashes, threshold is 0.6, and new methods do not exist.

- [ ] **Step 3: Implement MetaAnalyzer updates**

In `backend/src/services/meta_analyzer.py`:

- Change default threshold from `"0.6"` to `"60"`.
- Add empty input handling before `max()`.
- Add static `group_scores_by_question(scores)`.
- Add `extract_common_issues(judge_results)` that:
  - Returns `{"status": "not_extracted", "summary": "", "common_issues": [], "improvement_suggestions": []}` for empty input.
  - Builds one issue per critical step assessment dimension, grouped by `(dimension, observation)`.
  - Uses real question ids only from input.
  - Converts `evolution_suggestions` into deduplicated suggestions.

Use this implementation shape:

```python
    @staticmethod
    def group_scores_by_question(scores: list[ScoreResult]) -> dict[str, list[ScoreResult]]:
        grouped: dict[str, list[ScoreResult]] = {}
        for score in scores:
            grouped.setdefault(score.question_id, []).append(score)
        for values in grouped.values():
            values.sort(key=lambda s: s.attempt_index)
        return dict(sorted(grouped.items()))
```

- [ ] **Step 4: Run service tests**

Run:

```bash
cd backend && uv run pytest tests/test_services/test_meta_analyzer.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/meta_analyzer.py backend/tests/test_services/test_meta_analyzer.py
git commit -m "feat: compute pass rates and common issues from persisted results"
```

---

## Task 2: Connect Meta API to Repositories

**Files:**
- Modify: `backend/src/api/meta.py`
- Test: `backend/tests/test_api/test_meta.py`

- [ ] **Step 1: Add failing API tests**

Create `backend/tests/test_api/test_meta.py`:

```python
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
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd backend && uv run pytest tests/test_api/test_meta.py -v
```

Expected: FAIL because API still uses empty data and does not import repositories.

- [ ] **Step 3: Implement Meta API repository integration**

In `backend/src/api/meta.py`:

- Import `UUID`, `async_session`, `ScoreRepositoryImpl`, and `JudgeResultRepositoryImpl`.
- For pass-rate: list scores by run, group with `MetaAnalyzer.group_scores_by_question()`, compute pass rates.
- For common-issues: list judge results by run, call `analyzer.extract_common_issues()`, add `run_id`.
- For extract: return the same extraction result so the endpoint is useful without background jobs.

- [ ] **Step 4: Run API tests**

Run:

```bash
cd backend && uv run pytest tests/test_api/test_meta.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/meta.py backend/tests/test_api/test_meta.py
git commit -m "feat: connect meta api to persisted results"
```

---

## Task 3: Connect Comparison API to Repositories

**Files:**
- Modify: `backend/src/api/comparison.py`
- Test: `backend/tests/test_api/test_comparison.py`

- [ ] **Step 1: Add failing API tests**

Create `backend/tests/test_api/test_comparison.py`:

```python
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
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd backend && uv run pytest tests/test_api/test_comparison.py -v
```

Expected: FAIL because comparison endpoints still return empty arrays.

- [ ] **Step 3: Implement Comparison API repository integration**

In `backend/src/api/comparison.py`:

- Import `UUID`, `HTTPException`, repositories, `async_session`, and `MetaAnalyzer`.
- Add helpers:
  - `_parse_run_ids(run_ids: str) -> list[UUID]`
  - `_run_label(run) -> str`
  - `_load_run_scores(run_ids) -> dict[str, list[ScoreResult]]`
- Implement:
  - `/radar`: load scores keyed by label and call `engine.radar_data()`.
  - `/heatmap`: require one `run_id`; call `engine.heatmap_data()`.
  - `/trend`: list runs by benchmark, sort by `created_at`, compute average overall and pass rates.
  - `/pass-rate`: compute pass rates per run and call `engine.pass_rate_comparison()`.

- [ ] **Step 4: Run comparison API tests**

Run:

```bash
cd backend && uv run pytest tests/test_api/test_comparison.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/comparison.py backend/tests/test_api/test_comparison.py
git commit -m "feat: connect comparison api to persisted scores"
```

---

## Task 4: Full Verification and Push

**Files:**
- No code changes expected.

- [ ] **Step 1: Run backend tests**

Run:

```bash
cd backend && uv run pytest
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: build exits 0. Existing Rolldown annotation and chunk size warnings are acceptable.

- [ ] **Step 3: Merge to main and push**

Run:

```bash
git switch main
git merge codex/phase2b-analysis
git push origin main
```

Expected: push succeeds.

---

## Self-Review Notes

- Spec coverage: covers Phase 2B database-backed compare API, pass@k/pass^k correction, and first useful common issue extraction.
- Deliberate follow-up: LLM-based common issue persistence is left for a later Phase 2B+ task because this plan makes the existing endpoints useful without adding another table and external-model dependency.
- Placeholder scan: no unfinished placeholder markers are present.
- Type consistency: API tests and implementation use existing `TaskRun`, `ScoreResult`, `JudgeResult`, `RunRepositoryImpl`, `ScoreRepositoryImpl`, and `JudgeResultRepositoryImpl`.
