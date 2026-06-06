# CoworkEval E2E Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an end-to-end smoke path that proves sidecar execution output can be consumed by the backend offline evaluator.

**Architecture:** Keep the demo deterministic and local. A small script creates a temporary benchmark, writes a fake CLI Agent, runs `SidecarRunner`, then evaluates the generated run directory through backend `EvaluationLoader` and `PipelineRunner` with in-memory repositories. No web server or external LLM is required.

**Tech Stack:** Python 3.13, pandas/openpyxl for test XLSX fixtures, pytest, uv.

---

## File Structure

- Create `scripts/e2e_sidecar_offline_eval.py`: runnable smoke demo.
- Create `tests/test_e2e_sidecar_offline_eval.py`: repo-level pytest that runs the script and asserts success output.
- Add no new production dependencies.

---

## Task 1: Add E2E Demo Script

**Files:**
- Create: `scripts/e2e_sidecar_offline_eval.py`
- Test: `tests/test_e2e_sidecar_offline_eval.py`

- [ ] **Step 1: Write failing e2e test**

Create `tests/test_e2e_sidecar_offline_eval.py`:

```python
import subprocess
import sys
from pathlib import Path


def test_e2e_sidecar_offline_eval_script_runs():
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "e2e_sidecar_offline_eval.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "E2E_OK" in result.stdout
    assert "overall_score" in result.stdout
```

- [ ] **Step 2: Run failing test**

Run:

```bash
uv run pytest tests/test_e2e_sidecar_offline_eval.py -v
```

Expected: FAIL because the script does not exist or root project has no pytest environment. If root has no uv project, run with system pytest only if available; otherwise run the script directly after implementation and keep this test as documentation.

- [ ] **Step 3: Implement demo script**

Create `scripts/e2e_sidecar_offline_eval.py`:

```python
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "backend"))

from src.sidecar_config import AgentCommandConfig, SidecarRunConfig  # noqa: E402
from src.sidecar_runner import SidecarRunner  # noqa: E402
from backend.src.evaluator.result_comparator import ResultComparator  # noqa: E402
from backend.src.services.baseline_evaluator import BaselineEvaluator  # noqa: E402
from backend.src.services.evaluation_loader import EvaluationLoader  # noqa: E402


def write_benchmark(root: Path) -> None:
    qroot = root / "q-1"
    (qroot / "输入文件").mkdir(parents=True)
    (qroot / "参考答案").mkdir(parents=True)
    pd.DataFrame({"A": [1], "B": ["ok"]}).to_excel(qroot / "参考答案" / "answer.xlsx", index=False)
    (qroot / "输入文件" / "input.txt").write_text("input", encoding="utf-8")
    (qroot / "prompt.txt").write_text("create result.xlsx matching answer", encoding="utf-8")
    manifest = {
        "benchmark_id": "e2e-demo",
        "name": "e2e-demo",
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
                "input_files": ["q-1/输入文件/input.txt"],
                "reference_files": ["q-1/参考答案/answer.xlsx"],
                "output_dir": "q-1/输出结果/",
                "baseline_tokens": 100,
                "baseline_rounds": 1,
                "baseline_tool_count": 1,
                "baseline_time_ms": 1000,
                "baseline_cost_usd": 0.1,
            }
        ],
    }
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


def write_fake_agent_script(path: Path) -> None:
    path.write_text(
        '''
import json
import sys
from pathlib import Path
import pandas as pd

out = Path(sys.argv[1])
trace = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
pd.DataFrame({"A": [1], "B": ["ok"]}).to_excel(out / "result.xlsx", index=False)
events = [
    {"type": "session_start", "model": "fake-cli", "user_question": "create result"},
    {"type": "tool_call", "tool_name": "Write"},
    {"type": "tool_result", "tool_error": False, "tool_result": "wrote result.xlsx"},
    {"type": "assistant", "thinking": "done", "text": "done"},
    {"type": "result", "status": "success", "duration_ms": 10, "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.01},
]
trace.write_text("\\n".join(json.dumps(e) for e in events) + "\\n", encoding="utf-8")
''',
        encoding="utf-8",
    )


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        benchmark_root = Path(tmp) / "evaluations" / "e2e-demo"
        benchmark_root.mkdir(parents=True)
        write_benchmark(benchmark_root)
        fake_agent = Path(tmp) / "fake_agent.py"
        write_fake_agent_script(fake_agent)

        sidecar = SidecarRunner(
            SidecarRunConfig(
                benchmark_root=benchmark_root,
                run_label="fake-run",
                agent=AgentCommandConfig(
                    name="fake-cli",
                    command_template=f"{sys.executable} {fake_agent} {{output_dir}} {{trace_path}}",
                ),
            )
        )
        sidecar_results = sidecar.run()

        bundle = EvaluationLoader(benchmark_root).load_run("fake-run")
        parser = __import__("backend.src.infrastructure.trace_parser", fromlist=["TraceParser"]).TraceParser()
        repo = AsyncMock()
        repo.save = AsyncMock()
        evaluator = BaselineEvaluator(score_repo=repo, comparator=ResultComparator())
        item = bundle.inputs[0]
        trace_data = await parser.parse(item.trace_path)
        score = await evaluator.evaluate_input(uuid4(), item, trace_data)

        print(json.dumps({
            "status": "E2E_OK",
            "sidecar_trace_quality": sidecar_results[0]["trace_quality"],
            "t1_completion": score.t1_completion,
            "overall_score": score.overall_score,
        }, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run script directly**

Run:

```bash
python scripts/e2e_sidecar_offline_eval.py
```

Expected: prints JSON with `"status": "E2E_OK"` and non-zero `"overall_score"`.

- [ ] **Step 5: Run backend/agent tests**

Run:

```bash
cd agent && uv run pytest
cd ../backend && uv run pytest
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/e2e_sidecar_offline_eval.py tests/test_e2e_sidecar_offline_eval.py
git commit -m "test: add sidecar offline evaluation e2e demo"
```

---

## Self-Review Notes

- Spec coverage: proves the Phase 2A/2C integration path without needing a running server or external LLM.
- Deliberate follow-up: a true API/server e2e can be added later once frontend workflows are wired.
- Placeholder scan: no unfinished placeholder markers are present.
