# CoworkEval Phase 2A Offline Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the offline evaluation loop that reads real evaluation run directories, computes T1 plus TTTEC baseline scores, optionally runs Judge, fuses scores, and persists complete per-attempt results.

**Architecture:** Keep the existing layered FastAPI/Service/Repository structure. Add a focused directory scanner that converts filesystem evidence into `EvaluationInput`, then extend evaluators and pipeline orchestration without moving database access into services. Preserve current single-trace APIs while adding run-directory execution.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, SQLAlchemy async, pandas/openpyxl, pytest/pytest-asyncio, uv.

---

## File Structure

- Modify `backend/src/core/schemas.py`: add `TraceQuality`, `RunSource`, `EvaluationInput`, `RunMetadata`; extend `TaskRun` and `ScoreResult` with run labels, attempt metadata, trace quality, and partial flags.
- Modify `backend/src/repositories/run_repository.py`: persist run metadata fields.
- Modify `backend/src/repositories/score_repository.py`: persist attempt metadata, trace quality, partial flags, and support attempt-specific lookup.
- Modify `backend/src/core/interfaces.py`: add optional repository methods for attempt-aware score lookup.
- Create `backend/src/services/evaluation_loader.py`: scan `evaluations/<benchmark_id>/runs/<run_label>` into `EvaluationInput` objects.
- Modify `backend/src/evaluator/result_comparator.py`: add `compare_many()` for output directories and multiple references.
- Modify `backend/src/services/baseline_evaluator.py`: add `evaluate_input()` that computes T1 from output/reference files, keeps `evaluate()` backward compatible.
- Modify `backend/src/services/pipeline_runner.py`: add `execute_offline_run()` using real `EvaluationInput`, optional Judge/Fusion, and correct status transitions.
- Modify `backend/src/api/runs.py`: add an offline directory evaluation endpoint.
- Add/modify tests under `backend/tests/test_core`, `backend/tests/test_repositories`, `backend/tests/test_services`, `backend/tests/test_api`.

---

## Task 1: Extend Core Schemas for Offline Runs

**Files:**
- Modify: `backend/src/core/schemas.py`
- Test: `backend/tests/test_core/test_schemas.py`

- [ ] **Step 1: Write failing schema tests**

Append these tests to `backend/tests/test_core/test_schemas.py`:

```python
from pathlib import Path


def test_evaluation_input_defaults_to_first_attempt():
    from src.core.schemas import EvaluationInput, QuestionItem, EvalConfig, TraceQuality

    question = QuestionItem(
        question_id="alarm_analysis-0003",
        question_name="告警分析",
        category="Excel",
        difficulty="中等",
        prompt_file="alarm_analysis-0003/prompt.txt",
        input_files=["alarm_analysis-0003/输入文件/告警日志.xlsx"],
        reference_files=["alarm_analysis-0003/参考答案/告警汇总_answer.xlsx"],
        output_dir="alarm_analysis-0003/输出结果/",
        eval_config=EvalConfig(),
        baseline_tool_count=5,
        baseline_tokens=1000,
        baseline_rounds=3,
        baseline_time_ms=10000,
        baseline_cost_usd=0.2,
    )

    item = EvaluationInput(
        question=question,
        trace_path=Path("/tmp/run/alarm_analysis-0003/trace.jsonl"),
        output_dir=Path("/tmp/run/alarm_analysis-0003/输出结果"),
        reference_paths=[Path("/tmp/eval/alarm_analysis-0003/参考答案/告警汇总_answer.xlsx")],
    )

    assert item.question_id == "alarm_analysis-0003"
    assert item.attempt_index == 1
    assert item.trace_quality == TraceQuality.FULL
    assert item.is_partial_score is False


def test_task_run_accepts_run_metadata():
    from src.core.schemas import TaskRun, RunSource, TraceQuality

    run = TaskRun(
        benchmark_id="scene_0328-2",
        run_label="skill-v2",
        agent_name="codex-cli",
        model="gpt-5",
        skill_version="v2",
        source=RunSource.OFFLINE,
        trace_quality=TraceQuality.FULL,
    )

    assert run.run_label == "skill-v2"
    assert run.source == RunSource.OFFLINE
    assert run.trace_quality == TraceQuality.FULL


def test_score_result_accepts_attempt_metadata():
    from uuid import uuid4
    from src.core.schemas import ScoreResult, TraceQuality

    score = ScoreResult(
        run_id=uuid4(),
        question_id="q-1",
        attempt_index=2,
        trace_quality=TraceQuality.DEGRADED,
        is_partial_score=True,
    )

    assert score.attempt_index == 2
    assert score.trace_quality == TraceQuality.DEGRADED
    assert score.is_partial_score is True
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend && uv run pytest tests/test_core/test_schemas.py -v
```

Expected: FAIL because `EvaluationInput`, `RunSource`, `TraceQuality`, and new fields do not exist.

- [ ] **Step 3: Implement schema additions**

Modify `backend/src/core/schemas.py`:

```python
from pathlib import Path
```

Add after `JudgeDimension`:

```python
class TraceQuality(str, Enum):
    FULL = "full"
    DEGRADED = "degraded"


class RunSource(str, Enum):
    OFFLINE = "offline"
    SIDECAR = "sidecar"
```

Extend `TaskRun` with:

```python
    run_label: str = ""
    agent_name: str = ""
    model: str = ""
    skill_version: str = ""
    source: RunSource = RunSource.OFFLINE
    trace_quality: TraceQuality = TraceQuality.FULL
```

Extend `ScoreResult` with:

```python
    attempt_index: int = 1
    trace_quality: TraceQuality = TraceQuality.FULL
    is_partial_score: bool = False
```

Add after `Manifest`:

```python
class RunMetadata(BaseModel):
    run_label: str
    agent_name: str = ""
    model: str = ""
    skill_version: str = ""
    source: RunSource = RunSource.OFFLINE
    created_at: Optional[datetime] = None
    trace_quality: TraceQuality = TraceQuality.FULL


class EvaluationInput(BaseModel):
    question: QuestionItem
    trace_path: Path
    output_dir: Path
    reference_paths: list[Path] = Field(default_factory=list)
    attempt_index: int = 1
    trace_quality: TraceQuality = TraceQuality.FULL
    is_partial_score: bool = False

    @property
    def question_id(self) -> str:
        return self.question.question_id
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
cd backend && uv run pytest tests/test_core/test_schemas.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/core/schemas.py backend/tests/test_core/test_schemas.py
git commit -m "feat: add offline evaluation schemas"
```

---

## Task 2: Persist Run and Score Metadata

**Files:**
- Modify: `backend/src/repositories/run_repository.py`
- Modify: `backend/src/repositories/score_repository.py`
- Modify: `backend/src/core/interfaces.py`
- Test: `backend/tests/test_repositories/test_run_repository.py`
- Test: `backend/tests/test_repositories/test_score_repository.py`

- [ ] **Step 1: Write failing repository tests**

Append to `backend/tests/test_repositories/test_run_repository.py`:

```python
@pytest.mark.asyncio
async def test_run_repository_round_trips_metadata(run_repo):
    from src.core.schemas import TaskRun, RunSource, TraceQuality

    run = TaskRun(
        benchmark_id="bench-meta",
        run_label="skill-v2",
        agent_name="codex-cli",
        model="gpt-5",
        skill_version="v2",
        source=RunSource.OFFLINE,
        trace_quality=TraceQuality.DEGRADED,
        is_partial_score=True,
    )

    await run_repo.save(run)
    loaded = await run_repo.get(run.id)

    assert loaded is not None
    assert loaded.run_label == "skill-v2"
    assert loaded.agent_name == "codex-cli"
    assert loaded.model == "gpt-5"
    assert loaded.skill_version == "v2"
    assert loaded.source == RunSource.OFFLINE
    assert loaded.trace_quality == TraceQuality.DEGRADED
    assert loaded.is_partial_score is True
```

Append to `backend/tests/test_repositories/test_score_repository.py`:

```python
@pytest.mark.asyncio
async def test_score_repository_round_trips_attempt_metadata(score_repo):
    from uuid import uuid4
    from src.core.schemas import ScoreResult, TraceQuality

    run_id = uuid4()
    score = ScoreResult(
        run_id=run_id,
        question_id="q-1",
        attempt_index=2,
        trace_quality=TraceQuality.DEGRADED,
        is_partial_score=True,
        t1_completion=75.0,
        overall_score=70.0,
    )

    await score_repo.save(score)
    loaded = await score_repo.get_by_run_question_attempt(run_id, "q-1", 2)

    assert loaded is not None
    assert loaded.attempt_index == 2
    assert loaded.trace_quality == TraceQuality.DEGRADED
    assert loaded.is_partial_score is True
    assert loaded.t1_completion == 75.0
```

- [ ] **Step 2: Run repository tests to verify failure**

Run:

```bash
cd backend && uv run pytest tests/test_repositories/test_run_repository.py tests/test_repositories/test_score_repository.py -v
```

Expected: FAIL because columns and `get_by_run_question_attempt()` do not exist.

- [ ] **Step 3: Add interface method**

Modify `backend/src/core/interfaces.py` inside `ScoreRepository`:

```python
    @abstractmethod
    async def get_by_run_question_attempt(
        self, run_id: UUID, question_id: str, attempt_index: int
    ) -> Optional[ScoreResult]:
        ...
```

- [ ] **Step 4: Persist TaskRun metadata**

Modify imports in `backend/src/repositories/run_repository.py`:

```python
from src.core.schemas import TaskRun, RunStatus, RunSource, TraceQuality
```

Add columns to `TaskRunModel`:

```python
    run_label = Column(String, nullable=False, default="")
    agent_name = Column(String, nullable=False, default="")
    model = Column(String, nullable=False, default="")
    skill_version = Column(String, nullable=False, default="")
    source = Column(String, nullable=False, default="offline")
    trace_quality = Column(String, nullable=False, default="full")
```

Add fields in `to_domain()`:

```python
            run_label=self.run_label or "",
            agent_name=self.agent_name or "",
            model=self.model or "",
            skill_version=self.skill_version or "",
            source=RunSource(self.source or "offline"),
            trace_quality=TraceQuality(self.trace_quality or "full"),
```

Add fields in `from_domain()`:

```python
            run_label=run.run_label,
            agent_name=run.agent_name,
            model=run.model,
            skill_version=run.skill_version,
            source=run.source.value,
            trace_quality=run.trace_quality.value,
```

- [ ] **Step 5: Persist ScoreResult metadata**

Modify imports in `backend/src/repositories/score_repository.py`:

```python
from sqlalchemy import Column, String, Float, Boolean
from src.core.schemas import ScoreResult, TraceQuality
```

Add columns to `ScoreResultModel`:

```python
    attempt_index = Column(Float, default=1)
    trace_quality = Column(String, nullable=False, default="full")
    is_partial_score = Column(Boolean, default=False)
```

Add fields in `to_domain()`:

```python
            attempt_index=int(self.attempt_index or 1),
            trace_quality=TraceQuality(self.trace_quality or "full"),
            is_partial_score=bool(self.is_partial_score),
```

Add fields in `from_domain()`:

```python
            attempt_index=s.attempt_index,
            trace_quality=s.trace_quality.value,
            is_partial_score=s.is_partial_score,
```

Add method to `ScoreRepositoryImpl`:

```python
    async def get_by_run_question_attempt(
        self, run_id: UUID, question_id: str, attempt_index: int
    ) -> Optional[ScoreResult]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(ScoreResultModel).where(
                    ScoreResultModel.run_id == _uuid_to_bytes(run_id),
                    ScoreResultModel.question_id == question_id,
                    ScoreResultModel.attempt_index == attempt_index,
                )
            )
            model = result.scalar_one_or_none()
            return model.to_domain() if model else None
```

- [ ] **Step 6: Run repository tests**

Run:

```bash
cd backend && uv run pytest tests/test_repositories/test_run_repository.py tests/test_repositories/test_score_repository.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/src/core/interfaces.py backend/src/repositories/run_repository.py backend/src/repositories/score_repository.py backend/tests/test_repositories/test_run_repository.py backend/tests/test_repositories/test_score_repository.py
git commit -m "feat: persist offline run metadata"
```

---

## Task 3: Add Evaluation Directory Loader

**Files:**
- Create: `backend/src/services/evaluation_loader.py`
- Test: `backend/tests/test_services/test_evaluation_loader.py`

- [ ] **Step 1: Write failing loader tests**

Create `backend/tests/test_services/test_evaluation_loader.py`:

```python
import json
from datetime import datetime, timezone

import pytest

from src.services.evaluation_loader import EvaluationLoader
from src.core.schemas import TraceQuality, RunSource


def write_jsonl(path, events):
    path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n",
        encoding="utf-8",
    )


@pytest.fixture
def evaluation_tree(tmp_path):
    root = tmp_path / "evaluations" / "scene_0328-2"
    qroot = root / "alarm_analysis-0003"
    run = root / "runs" / "skill-v2"

    (qroot / "输入文件").mkdir(parents=True)
    (qroot / "参考答案").mkdir(parents=True)
    (run / "alarm_analysis-0003" / "attempt-1" / "输出结果").mkdir(parents=True)

    manifest = {
        "benchmark_id": "scene_0328-2",
        "name": "scene_0328-2",
        "version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total_questions": 1,
        "questions": [
            {
                "question_id": "alarm_analysis-0003",
                "question_name": "告警分析",
                "category": "Excel",
                "difficulty": "中等",
                "prompt_file": "alarm_analysis-0003/prompt.txt",
                "input_files": ["alarm_analysis-0003/输入文件/告警日志.xlsx"],
                "reference_files": ["alarm_analysis-0003/参考答案/告警汇总_answer.xlsx"],
                "output_dir": "alarm_analysis-0003/输出结果/",
                "eval_config": {"compare_style": False, "ignore_rules": []},
                "scene": "skills",
                "skills": "alarm_analysis",
                "baseline_tokens": 1000,
                "baseline_rounds": 3,
                "baseline_tool_count": 5,
                "baseline_time_ms": 10000,
                "baseline_cost_usd": 0.2,
            }
        ],
    }
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (run / "run_meta.json").write_text(
        json.dumps(
            {
                "run_label": "skill-v2",
                "agent_name": "codex-cli",
                "model": "gpt-5",
                "skill_version": "v2",
                "source": "offline",
                "trace_quality": "full",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_jsonl(
        run / "alarm_analysis-0003" / "attempt-1" / "trace.jsonl",
        [{"type": "result", "status": "success", "duration_ms": 1000}],
    )
    (run / "alarm_analysis-0003" / "attempt-1" / "输出结果" / "result.xlsx").write_bytes(b"not-a-real-xlsx")
    (qroot / "参考答案" / "告警汇总_answer.xlsx").write_bytes(b"not-a-real-xlsx")
    return root


def test_loads_manifest_run_metadata_and_attempts(evaluation_tree):
    loader = EvaluationLoader(evaluation_tree)

    bundle = loader.load_run("skill-v2")

    assert bundle.manifest.benchmark_id == "scene_0328-2"
    assert bundle.run_metadata.run_label == "skill-v2"
    assert bundle.run_metadata.source == RunSource.OFFLINE
    assert len(bundle.inputs) == 1
    item = bundle.inputs[0]
    assert item.question_id == "alarm_analysis-0003"
    assert item.attempt_index == 1
    assert item.trace_quality == TraceQuality.FULL
    assert item.trace_path.name == "trace.jsonl"
    assert item.output_dir.name == "输出结果"
    assert len(item.reference_paths) == 1


def test_simplified_question_directory_is_attempt_one(tmp_path):
    root = tmp_path / "evaluations" / "bench-simple"
    qroot = root / "q-1"
    run = root / "runs" / "v1" / "q-1"
    (qroot / "参考答案").mkdir(parents=True)
    (run / "输出结果").mkdir(parents=True)

    manifest = {
        "benchmark_id": "bench-simple",
        "name": "bench-simple",
        "version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total_questions": 1,
        "questions": [
            {
                "question_id": "q-1",
                "question_name": "Q1",
                "category": "Excel",
                "difficulty": "中等",
                "prompt_file": "q-1/prompt.txt",
                "reference_files": ["q-1/参考答案/ref.xlsx"],
                "output_dir": "q-1/输出结果/",
            }
        ],
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    write_jsonl(run / "trace.jsonl", [{"type": "result", "status": "success"}])
    (qroot / "参考答案" / "ref.xlsx").write_bytes(b"x")

    bundle = EvaluationLoader(root).load_run("v1")

    assert bundle.inputs[0].attempt_index == 1
    assert bundle.inputs[0].trace_path == run / "trace.jsonl"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend && uv run pytest tests/test_services/test_evaluation_loader.py -v
```

Expected: FAIL because `EvaluationLoader` does not exist.

- [ ] **Step 3: Implement loader**

Create `backend/src/services/evaluation_loader.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from src.core.schemas import EvaluationInput, Manifest, RunMetadata, TraceQuality


class EvaluationRunBundle(BaseModel):
    manifest: Manifest
    run_metadata: RunMetadata
    inputs: list[EvaluationInput]


class EvaluationLoader:
    def __init__(self, benchmark_root: str | Path):
        self.benchmark_root = Path(benchmark_root)

    def load_manifest(self) -> Manifest:
        manifest_path = self.benchmark_root / "manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return Manifest.model_validate(data)

    def load_run(self, run_label: str) -> EvaluationRunBundle:
        manifest = self.load_manifest()
        run_dir = self.benchmark_root / "runs" / run_label
        metadata = self._load_run_metadata(run_dir, run_label)
        inputs: list[EvaluationInput] = []

        for question in manifest.questions:
            q_run_dir = run_dir / question.question_id
            attempt_dirs = self._discover_attempt_dirs(q_run_dir)
            for attempt_index, attempt_dir in attempt_dirs:
                trace_path = attempt_dir / "trace.jsonl"
                output_dir = attempt_dir / "输出结果"
                inputs.append(
                    EvaluationInput(
                        question=question,
                        trace_path=trace_path,
                        output_dir=output_dir,
                        reference_paths=[
                            self.benchmark_root / ref for ref in question.reference_files
                        ],
                        attempt_index=attempt_index,
                        trace_quality=metadata.trace_quality,
                        is_partial_score=metadata.trace_quality == TraceQuality.DEGRADED,
                    )
                )

        return EvaluationRunBundle(
            manifest=manifest,
            run_metadata=metadata,
            inputs=inputs,
        )

    def _load_run_metadata(self, run_dir: Path, run_label: str) -> RunMetadata:
        meta_path = run_dir / "run_meta.json"
        if not meta_path.exists():
            return RunMetadata(run_label=run_label)
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        data.setdefault("run_label", run_label)
        return RunMetadata.model_validate(data)

    def _discover_attempt_dirs(self, question_run_dir: Path) -> list[tuple[int, Path]]:
        if not question_run_dir.exists():
            return [(1, question_run_dir)]

        attempt_dirs: list[tuple[int, Path]] = []
        for child in sorted(question_run_dir.iterdir()):
            if not child.is_dir() or not child.name.startswith("attempt-"):
                continue
            suffix = child.name.removeprefix("attempt-")
            if suffix.isdigit():
                attempt_dirs.append((int(suffix), child))

        if attempt_dirs:
            return attempt_dirs

        return [(1, question_run_dir)]
```

- [ ] **Step 4: Run loader tests**

Run:

```bash
cd backend && uv run pytest tests/test_services/test_evaluation_loader.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/evaluation_loader.py backend/tests/test_services/test_evaluation_loader.py
git commit -m "feat: load offline evaluation directories"
```

---

## Task 4: Move T1 File Comparison into Baseline Evaluation

**Files:**
- Modify: `backend/src/evaluator/result_comparator.py`
- Modify: `backend/src/services/baseline_evaluator.py`
- Test: `backend/tests/test_evaluator/test_result_comparator.py`
- Test: `backend/tests/test_services/test_baseline_evaluator.py`

- [ ] **Step 1: Write failing comparator test**

Append to `backend/tests/test_evaluator/test_result_comparator.py`:

```python
def test_compare_many_uses_best_output_reference_pair(tmp_path):
    import pandas as pd
    from src.evaluator.result_comparator import ResultComparator
    from src.core.schemas import EvalConfig

    output_dir = tmp_path / "输出结果"
    output_dir.mkdir()
    reference = tmp_path / "answer.xlsx"

    pd.DataFrame({"A": [1, 2], "B": ["x", "y"]}).to_excel(output_dir / "result.xlsx", index=False)
    pd.DataFrame({"A": [1, 2], "B": ["x", "y"]}).to_excel(reference, index=False)

    score = ResultComparator().compare_many(
        output_dir=output_dir,
        reference_paths=[reference],
        eval_config=EvalConfig(),
    )

    assert score == 100.0
```

Append to `backend/tests/test_services/test_baseline_evaluator.py`:

```python
@pytest.mark.asyncio
async def test_evaluate_input_computes_t1_from_output_files(tmp_path):
    import pandas as pd
    from uuid import uuid4
    from src.core.schemas import EvaluationInput, QuestionItem, EvalConfig
    from src.services.baseline_evaluator import BaselineEvaluator
    from src.evaluator.result_comparator import ResultComparator

    output_dir = tmp_path / "输出结果"
    output_dir.mkdir()
    reference = tmp_path / "answer.xlsx"
    pd.DataFrame({"A": [1]}).to_excel(output_dir / "result.xlsx", index=False)
    pd.DataFrame({"A": [1]}).to_excel(reference, index=False)

    question = QuestionItem(
        question_id="q-t1",
        question_name="T1",
        category="Excel",
        difficulty="中等",
        prompt_file="q-t1/prompt.txt",
        output_dir="q-t1/输出结果/",
        reference_files=["q-t1/参考答案/answer.xlsx"],
        eval_config=EvalConfig(),
        baseline_tool_count=1,
        baseline_tokens=100,
        baseline_rounds=1,
        baseline_time_ms=1000,
        baseline_cost_usd=0.1,
    )
    trace_data = [
        {"type": "tool_call", "tool_name": "Read"},
        {"type": "tool_result", "tool_error": False},
        {"type": "assistant", "thinking": "done"},
        {"type": "result", "duration_ms": 500, "input_tokens": 30, "output_tokens": 10, "cost_usd": 0.01},
    ]
    item = EvaluationInput(
        question=question,
        trace_path=tmp_path / "trace.jsonl",
        output_dir=output_dir,
        reference_paths=[reference],
    )
    repo = AsyncMock()
    repo.save = AsyncMock()
    evaluator = BaselineEvaluator(score_repo=repo, comparator=ResultComparator())

    score = await evaluator.evaluate_input(uuid4(), item, trace_data)

    assert score.t1_baseline_only == 100.0
    assert score.t1_completion == 100.0
    assert score.overall_score > 0
    repo.save.assert_called_once()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend && uv run pytest tests/test_evaluator/test_result_comparator.py tests/test_services/test_baseline_evaluator.py -v
```

Expected: FAIL because `compare_many()` and `evaluate_input()` do not exist.

- [ ] **Step 3: Implement `compare_many()`**

Add to `ResultComparator` in `backend/src/evaluator/result_comparator.py`:

```python
    def compare_many(
        self,
        output_dir: str | Path,
        reference_paths: list[str | Path],
        eval_config: EvalConfig,
    ) -> float:
        out_dir = Path(output_dir)
        if not out_dir.exists() or not out_dir.is_dir():
            return 0.0

        output_files = [
            p for p in sorted(out_dir.iterdir())
            if p.suffix.lower() in {".xlsx", ".csv"}
        ]
        if not output_files or not reference_paths:
            return 0.0

        best = 0.0
        for output_file in output_files:
            for reference_path in reference_paths:
                best = max(
                    best,
                    self.compare(str(output_file), str(reference_path), eval_config),
                )
        return best
```

- [ ] **Step 4: Implement `evaluate_input()`**

Modify imports in `backend/src/services/baseline_evaluator.py`:

```python
from src.core.schemas import ScoreResult, QuestionItem, EvalConfig, EvaluationInput
```

Add method to `BaselineEvaluator`:

```python
    async def evaluate_input(
        self, run_id: UUID, evaluation_input: EvaluationInput, trace_data: list[dict]
    ) -> ScoreResult:
        score = await self._evaluate_core(
            run_id=run_id,
            question=evaluation_input.question,
            trace_data=trace_data,
            t1_baseline_only=self.comparator.compare_many(
                output_dir=evaluation_input.output_dir,
                reference_paths=evaluation_input.reference_paths,
                eval_config=evaluation_input.question.eval_config,
            ),
            attempt_index=evaluation_input.attempt_index,
            trace_quality=evaluation_input.trace_quality,
            is_partial_score=evaluation_input.is_partial_score,
        )
        return score
```

Replace the body of existing `evaluate()` with:

```python
        return await self._evaluate_core(
            run_id=run_id,
            question=question,
            trace_data=trace_data,
            t1_baseline_only=0.0,
        )
```

Add private core method by moving the current scoring body into:

```python
    async def _evaluate_core(
        self,
        run_id: UUID,
        question: QuestionItem,
        trace_data: list[dict],
        t1_baseline_only: float = 0.0,
        attempt_index: int = 1,
        trace_quality=None,
        is_partial_score: bool = False,
    ) -> ScoreResult:
        metrics = self.parser.extract_metrics(trace_data)
        score = ScoreResult(
            run_id=run_id,
            question_id=question.question_id,
            attempt_index=attempt_index,
            trace_quality=trace_quality or ScoreResult.model_fields["trace_quality"].default,
            is_partial_score=is_partial_score,
            actual_tool_calls=metrics["total_tool_calls"],
            actual_success_calls=metrics["success_tool_calls"],
            actual_tokens=metrics["total_tokens"],
            actual_rounds=metrics["rounds"],
            actual_time_ms=metrics["duration_ms"],
            actual_cost_usd=metrics["cost_usd"],
        )
        score.t1_baseline_only = t1_baseline_only
        score.t1_completion = t1_baseline_only
        score.t2_accuracy = self._compute_t2(metrics["success_tool_calls"], metrics["total_tool_calls"])
        score.t3_efficiency = self._compute_t3(metrics["total_tool_calls"], question.baseline_tool_count)
        score.t4_thinking = self._compute_t4(
            metrics["total_tokens"], metrics["rounds"], question.baseline_tokens, question.baseline_rounds
        )
        score.e_performance = self._compute_e(metrics["duration_ms"], question.baseline_time_ms, question.payload_size_kb)
        score.c_cost = self._compute_c(metrics["cost_usd"], question.baseline_cost_usd)
        dims = [
            score.t1_completion or 0,
            score.t2_accuracy or 0,
            score.t3_efficiency or 0,
            score.t4_thinking or 0,
            score.e_performance or 0,
            score.c_cost or 0,
        ]
        score.overall_score = sum(dims) / 6.0
        await self.score_repo.save(score)
        return score
```

- [ ] **Step 5: Run evaluator tests**

Run:

```bash
cd backend && uv run pytest tests/test_evaluator/test_result_comparator.py tests/test_services/test_baseline_evaluator.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/evaluator/result_comparator.py backend/src/services/baseline_evaluator.py backend/tests/test_evaluator/test_result_comparator.py backend/tests/test_services/test_baseline_evaluator.py
git commit -m "feat: score task completion from output files"
```

---

## Task 5: Execute Offline Runs Through Pipeline

**Files:**
- Modify: `backend/src/services/pipeline_runner.py`
- Test: `backend/tests/test_services/test_pipeline_runner.py`

- [ ] **Step 1: Write failing offline pipeline tests**

Append to `backend/tests/test_services/test_pipeline_runner.py`:

```python
@pytest.mark.asyncio
async def test_execute_offline_run_uses_evaluation_inputs(mock_run_repo, manifest, tmp_path):
    from src.core.schemas import EvaluationInput, TraceQuality

    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text('{"type":"result","status":"success"}\n', encoding="utf-8")
    item = EvaluationInput(
        question=manifest.questions[0],
        trace_path=trace_path,
        output_dir=tmp_path / "输出结果",
        reference_paths=[],
        attempt_index=1,
        trace_quality=TraceQuality.FULL,
    )

    evaluator = AsyncMock()
    evaluator.evaluate_input = AsyncMock(return_value=ScoreResult(
        run_id=uuid4(),
        question_id=manifest.questions[0].question_id,
        attempt_index=1,
        overall_score=80.0,
    ))
    runner = PipelineRunner(run_repo=mock_run_repo, baseline_evaluator=evaluator)
    run = TaskRun(benchmark_id=manifest.benchmark_id, judge_enabled=False)

    scores = await runner.execute_offline_run(run.id, [item], judge_enabled=False)

    assert len(scores) == 1
    evaluator.evaluate_input.assert_called_once()
    status_calls = [c.args[1] for c in mock_run_repo.update_status.call_args_list]
    assert RunStatus.PARSING_TRACE in status_calls
    assert RunStatus.EVALUATING_BASELINE in status_calls
    assert RunStatus.COMPLETED in status_calls
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd backend && uv run pytest tests/test_services/test_pipeline_runner.py::test_execute_offline_run_uses_evaluation_inputs -v
```

Expected: FAIL because `execute_offline_run()` does not exist.

- [ ] **Step 3: Implement offline execution without Judge**

Modify `PipelineRunner.__init__()` signature:

```python
        judge_evaluator: BaseEvaluator | None = None,
        fusion_service=None,
        judge_repo=None,
```

Store fields:

```python
        self.judge_evaluator = judge_evaluator
        self.fusion_service = fusion_service
        self.judge_repo = judge_repo
```

Add method:

```python
    async def execute_offline_run(
        self,
        run_id: UUID,
        evaluation_inputs: list,
        judge_enabled: bool = False,
    ) -> list[ScoreResult]:
        sm = StateMachine(judge_enabled=judge_enabled)
        try:
            await self.run_repo.update_status(run_id, RunStatus.PARSING_TRACE)
            sm.transition_to(RunStatus.PARSING_TRACE)
            trace_map = await self._load_input_traces(evaluation_inputs)

            await self.run_repo.update_status(run_id, RunStatus.EVALUATING_BASELINE)
            sm.transition_to(RunStatus.EVALUATING_BASELINE)
            baseline_scores = await self._execute_evaluation_inputs(run_id, evaluation_inputs, trace_map)

            if not judge_enabled or self.judge_evaluator is None:
                await self.run_repo.update_status(run_id, RunStatus.COMPLETED)
                sm.transition_to(RunStatus.COMPLETED)
                return baseline_scores

            await self.run_repo.update_status(run_id, RunStatus.AWAITING_JUDGE)
            sm.transition_to(RunStatus.AWAITING_JUDGE)
            await self.run_repo.update_status(run_id, RunStatus.EVALUATING_JUDGE)
            sm.transition_to(RunStatus.EVALUATING_JUDGE)
            fused_scores = await self._execute_judge_and_fusion(run_id, evaluation_inputs, trace_map, baseline_scores)

            await self.run_repo.update_status(run_id, RunStatus.COMPLETED)
            sm.transition_to(RunStatus.COMPLETED)
            return fused_scores
        except Exception as e:
            logger.exception(f"Offline pipeline failed for run {run_id}")
            await self.run_repo.update_status(run_id, RunStatus.FAILED, error_stack=str(e))
            raise EvaluationError(str(e), run_id=str(run_id))
```

Add helpers:

```python
    async def _load_input_traces(self, evaluation_inputs: list) -> dict[tuple[str, int], list[dict]]:
        trace_map = {}
        for item in evaluation_inputs:
            trace_map[(item.question_id, item.attempt_index)] = await self.parser.parse(item.trace_path)
        return trace_map

    async def _execute_evaluation_inputs(
        self, run_id: UUID, evaluation_inputs: list, trace_map: dict[tuple[str, int], list[dict]]
    ) -> list[ScoreResult]:
        tasks = []
        for item in evaluation_inputs:
            trace_data = trace_map[(item.question_id, item.attempt_index)]
            tasks.append(self.baseline_evaluator.evaluate_input(run_id, item, trace_data))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        scores = []
        for result in results:
            if isinstance(result, Exception):
                raise result
            scores.append(result)
        return scores
```

Add judge helper stub for Task 6:

```python
    async def _execute_judge_and_fusion(
        self, run_id: UUID, evaluation_inputs: list, trace_map: dict, baseline_scores: list[ScoreResult]
    ) -> list[ScoreResult]:
        return baseline_scores
```

- [ ] **Step 4: Run pipeline test**

Run:

```bash
cd backend && uv run pytest tests/test_services/test_pipeline_runner.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/pipeline_runner.py backend/tests/test_services/test_pipeline_runner.py
git commit -m "feat: execute offline evaluation inputs"
```

---

## Task 6: Wire Judge and Fusion into Offline Pipeline

**Files:**
- Modify: `backend/src/services/pipeline_runner.py`
- Test: `backend/tests/test_services/test_pipeline_runner.py`

- [ ] **Step 1: Write failing Judge/Fusion pipeline test**

Append to `backend/tests/test_services/test_pipeline_runner.py`:

```python
@pytest.mark.asyncio
async def test_execute_offline_run_invokes_judge_and_fusion(mock_run_repo, manifest, tmp_path):
    from src.core.schemas import EvaluationInput, JudgeResult

    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text('{"type":"result","status":"success"}\n', encoding="utf-8")
    item = EvaluationInput(
        question=manifest.questions[0],
        trace_path=trace_path,
        output_dir=tmp_path / "输出结果",
        reference_paths=[],
    )
    run_id = uuid4()
    baseline_score = ScoreResult(run_id=run_id, question_id=item.question_id, overall_score=50.0)
    fused_score = ScoreResult(run_id=run_id, question_id=item.question_id, overall_score=85.0)
    judge_result = JudgeResult(run_id=run_id, question_id=item.question_id, task_completion=90)

    baseline = AsyncMock()
    baseline.evaluate_input = AsyncMock(return_value=baseline_score)
    judge = AsyncMock()
    judge.evaluate = AsyncMock(return_value=ScoreResult(run_id=run_id, question_id=item.question_id))
    judge_repo = AsyncMock()
    judge_repo.get_by_run_and_question = AsyncMock(return_value=judge_result)
    fusion = AsyncMock()
    fusion.fuse = AsyncMock(return_value=fused_score)

    runner = PipelineRunner(
        run_repo=mock_run_repo,
        baseline_evaluator=baseline,
        judge_evaluator=judge,
        fusion_service=fusion,
        judge_repo=judge_repo,
    )

    scores = await runner.execute_offline_run(run_id, [item], judge_enabled=True)

    assert scores == [fused_score]
    judge.evaluate.assert_called_once()
    fusion.fuse.assert_called_once_with(baseline_score, judge_result)
    status_calls = [c.args[1] for c in mock_run_repo.update_status.call_args_list]
    assert RunStatus.AWAITING_JUDGE in status_calls
    assert RunStatus.EVALUATING_JUDGE in status_calls
    assert RunStatus.COMPLETED in status_calls
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd backend && uv run pytest tests/test_services/test_pipeline_runner.py::test_execute_offline_run_invokes_judge_and_fusion -v
```

Expected: FAIL because `_execute_judge_and_fusion()` returns baseline scores.

- [ ] **Step 3: Implement Judge/Fusion helper**

Replace `_execute_judge_and_fusion()` in `backend/src/services/pipeline_runner.py`:

```python
    async def _execute_judge_and_fusion(
        self,
        run_id: UUID,
        evaluation_inputs: list,
        trace_map: dict,
        baseline_scores: list[ScoreResult],
    ) -> list[ScoreResult]:
        baseline_by_key = {
            (score.question_id, score.attempt_index): score for score in baseline_scores
        }
        tasks = []
        for item in evaluation_inputs:
            tasks.append(self._judge_and_fuse_single(run_id, item, trace_map, baseline_by_key))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        scores: list[ScoreResult] = []
        for result in results:
            if isinstance(result, Exception):
                raise result
            scores.append(result)
        return scores

    async def _judge_and_fuse_single(
        self, run_id: UUID, item, trace_map: dict, baseline_by_key: dict
    ) -> ScoreResult:
        key = (item.question_id, item.attempt_index)
        baseline = baseline_by_key[key]
        async with self.judge_semaphore:
            await self.judge_evaluator.evaluate(
                run_id=run_id,
                question=item.question,
                trace_data=trace_map[key],
            )
        judge_result = await self.judge_repo.get_by_run_and_question(run_id, item.question_id)
        if judge_result is None or self.fusion_service is None:
            baseline.is_partial_score = True
            return baseline
        fused = await self.fusion_service.fuse(baseline, judge_result)
        return fused
```

- [ ] **Step 4: Run pipeline tests**

Run:

```bash
cd backend && uv run pytest tests/test_services/test_pipeline_runner.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/pipeline_runner.py backend/tests/test_services/test_pipeline_runner.py
git commit -m "feat: fuse judge results in offline pipeline"
```

---

## Task 7: Add Offline Run API Endpoint

**Files:**
- Modify: `backend/src/api/runs.py`
- Test: `backend/tests/test_api/test_runs.py`

- [ ] **Step 1: Write failing API test**

Create `backend/tests/test_api/test_runs.py`:

```python
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app
from src.core.schemas import TaskRun, ScoreResult


client = TestClient(app)


def test_evaluate_offline_run_endpoint():
    run = TaskRun(benchmark_id="bench-1", run_label="skill-v2")
    score = ScoreResult(run_id=run.id, question_id="q-1", overall_score=88.0)

    with patch("src.api.runs.EvaluationLoader") as loader_cls, patch("src.api.runs._build_pipeline") as build_pipeline:
        loader = loader_cls.return_value
        loader.load_run.return_value.manifest.benchmark_id = "bench-1"
        loader.load_run.return_value.run_metadata.run_label = "skill-v2"
        loader.load_run.return_value.run_metadata.agent_name = "codex-cli"
        loader.load_run.return_value.run_metadata.model = "gpt-5"
        loader.load_run.return_value.run_metadata.skill_version = "v2"
        loader.load_run.return_value.run_metadata.source.value = "offline"
        loader.load_run.return_value.run_metadata.trace_quality.value = "full"
        loader.load_run.return_value.inputs = []

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
```

- [ ] **Step 2: Run API test to verify failure**

Run:

```bash
cd backend && uv run pytest tests/test_api/test_runs.py -v
```

Expected: FAIL because endpoint and `EvaluationLoader` import do not exist.

- [ ] **Step 3: Implement request model and endpoint**

Modify imports in `backend/src/api/runs.py`:

```python
from pydantic import BaseModel
from src.services.evaluation_loader import EvaluationLoader
from src.core.schemas import RunSource, TraceQuality
```

Add request model near top:

```python
class OfflineEvaluateRequest(BaseModel):
    benchmark_root: str
    run_label: str
    judge_enabled: bool = False
```

Add endpoint before `@router.post("/evaluate")`:

```python
@router.post("/evaluate-offline", response_model=dict)
async def evaluate_offline_run(request: OfflineEvaluateRequest):
    loader = EvaluationLoader(request.benchmark_root)
    bundle = loader.load_run(request.run_label)
    pipeline = _build_pipeline()
    run = await pipeline.create_run(bundle.manifest, judge_enabled=request.judge_enabled)
    run.run_label = bundle.run_metadata.run_label
    run.agent_name = bundle.run_metadata.agent_name
    run.model = bundle.run_metadata.model
    run.skill_version = bundle.run_metadata.skill_version
    run.source = bundle.run_metadata.source
    run.trace_quality = bundle.run_metadata.trace_quality
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
```

- [ ] **Step 4: Run API tests**

Run:

```bash
cd backend && uv run pytest tests/test_api/test_runs.py tests/test_api/test_router.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/runs.py backend/tests/test_api/test_runs.py
git commit -m "feat: add offline run evaluation endpoint"
```

---

## Task 8: Full Verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Run backend test suite**

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

Expected: build succeeds. Existing Vite/Rolldown annotation and chunk-size warnings are acceptable if the command exits 0.

- [ ] **Step 3: Check git status**

Run:

```bash
git status --short
```

Expected: only unrelated `.DS_Store` files may remain dirty.

- [ ] **Step 4: Commit any verification-only doc updates if made**

If no files changed, do not commit. If a test fixture or README was updated during verification:

```bash
git add <changed-files>
git commit -m "test: verify offline evaluation flow"
```

---

## Self-Review Notes

- Spec coverage: this plan covers Phase 2A from the approved design: directory scanner, run metadata, attempt metadata, T1 downshift into service, real trace loading, optional Judge/Fusion in Pipeline, and an offline API endpoint.
- Out of scope for this plan: Phase 2B compare API, corrected pass@k/pass^k API, common issue persistence, and Phase 2C sidecar execution. Those should get separate plans after Phase 2A lands.
- Placeholder scan: no unfinished placeholder markers are present.
- Type consistency: new types are `TraceQuality`, `RunSource`, `RunMetadata`, and `EvaluationInput`; repository and pipeline tasks use the same names.
