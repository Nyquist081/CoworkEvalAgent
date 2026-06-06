# CoworkEval Phase 2C Agent Sidecar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local command-template sidecar that prepares question workspaces, executes a CLI Agent command, and writes CoworkEval-compatible run evidence directories.

**Architecture:** Keep the existing simulated `AgentRunner` intact for tests and demos. Add focused sidecar modules under `agent/src`: config parsing, workspace preparation, command execution, and trace collection. The sidecar writes the same `evaluations/<benchmark_id>/runs/<run_label>/<question_id>/attempt-N/` layout consumed by Phase 2A.

**Tech Stack:** Python 3.13, Pydantic v2, stdlib `subprocess`/`shlex`/`shutil`, pytest, uv.

---

## File Structure

- Create `agent/src/sidecar_config.py`: Pydantic config objects for command templates and run metadata.
- Create `agent/src/sidecar_runner.py`: `SidecarRunner` that loads manifest questions, prepares attempt directories, renders command templates, runs commands, copies outputs, and writes full or degraded traces.
- Modify `agent/src/__init__.py`: export new sidecar classes.
- Add tests in `agent/tests/test_sidecar_config.py` and `agent/tests/test_sidecar_runner.py`.
- Keep `agent/src/agent_runner.py` unchanged.

---

## Task 1: Add Sidecar Configuration Models

**Files:**
- Create: `agent/src/sidecar_config.py`
- Modify: `agent/src/__init__.py`
- Test: `agent/tests/test_sidecar_config.py`

- [ ] **Step 1: Write failing config tests**

Create `agent/tests/test_sidecar_config.py`:

```python
from pathlib import Path

from src.sidecar_config import AgentCommandConfig, SidecarRunConfig


def test_agent_command_config_renders_template(tmp_path):
    config = AgentCommandConfig(
        name="fake-cli",
        command_template="python {prompt_file} --cwd {workdir} --out {output_dir}",
        trace_path_template="{workdir}/trace.jsonl",
        output_dir_template="{workdir}/输出结果",
    )

    rendered = config.render_command(
        workdir=tmp_path,
        prompt_file=tmp_path / "prompt.txt",
        output_dir=tmp_path / "输出结果",
        trace_path=tmp_path / "trace.jsonl",
    )

    assert str(tmp_path / "prompt.txt") in rendered
    assert str(tmp_path / "输出结果") in rendered


def test_sidecar_run_config_defaults():
    config = SidecarRunConfig(
        benchmark_root=Path("/tmp/evaluations/bench-1"),
        run_label="skill-v2",
        agent=AgentCommandConfig(
            name="fake-cli",
            command_template="echo ok",
        ),
    )

    assert config.attempt_index == 1
    assert config.agent.trace_path_template == "{workdir}/trace.jsonl"
    assert config.agent.output_dir_template == "{workdir}/输出结果"
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd agent && uv run pytest tests/test_sidecar_config.py -v
```

Expected: FAIL because `src.sidecar_config` does not exist.

- [ ] **Step 3: Implement config models**

Create `agent/src/sidecar_config.py`:

```python
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class AgentCommandConfig(BaseModel):
    name: str
    command_template: str
    trace_path_template: str = "{workdir}/trace.jsonl"
    output_dir_template: str = "{workdir}/输出结果"

    def render_command(
        self,
        workdir: Path,
        prompt_file: Path,
        output_dir: Path,
        trace_path: Path,
    ) -> str:
        return self.command_template.format(
            workdir=str(workdir),
            prompt_file=str(prompt_file),
            output_dir=str(output_dir),
            trace_path=str(trace_path),
        )

    def render_trace_path(self, workdir: Path) -> Path:
        return Path(self.trace_path_template.format(workdir=str(workdir)))

    def render_output_dir(self, workdir: Path) -> Path:
        return Path(self.output_dir_template.format(workdir=str(workdir)))


class SidecarRunConfig(BaseModel):
    benchmark_root: Path
    run_label: str
    agent: AgentCommandConfig
    attempt_index: int = 1
    model: str = ""
    skill_version: str = ""
```

Modify `agent/src/__init__.py`:

```python
from src.sidecar_config import AgentCommandConfig, SidecarRunConfig
from src.sidecar_runner import SidecarRunner

__all__ = ["AgentCommandConfig", "SidecarRunConfig", "SidecarRunner"]
```

Only add `SidecarRunner` export after Task 2 creates it; for Task 1 export just config models:

```python
from src.sidecar_config import AgentCommandConfig, SidecarRunConfig

__all__ = ["AgentCommandConfig", "SidecarRunConfig"]
```

- [ ] **Step 4: Run config tests**

Run:

```bash
cd agent && uv run pytest tests/test_sidecar_config.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/src/sidecar_config.py agent/src/__init__.py agent/tests/test_sidecar_config.py
git commit -m "feat: add sidecar command configuration"
```

---

## Task 2: Implement Sidecar Runner for Full Trace

**Files:**
- Create: `agent/src/sidecar_runner.py`
- Modify: `agent/src/__init__.py`
- Test: `agent/tests/test_sidecar_runner.py`

- [ ] **Step 1: Write failing full-trace sidecar test**

Create `agent/tests/test_sidecar_runner.py`:

```python
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.sidecar_config import AgentCommandConfig, SidecarRunConfig
from src.sidecar_runner import SidecarRunner


def write_manifest(root: Path):
    manifest = {
        "benchmark_id": "bench-1",
        "name": "bench-1",
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
                "reference_files": [],
                "output_dir": "q-1/输出结果/",
            }
        ],
    }
    (root / "q-1" / "输入文件").mkdir(parents=True)
    (root / "q-1" / "prompt.txt").write_text("do work", encoding="utf-8")
    (root / "q-1" / "输入文件" / "input.txt").write_text("input", encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_sidecar_runs_command_and_preserves_full_trace(tmp_path):
    benchmark_root = tmp_path / "evaluations" / "bench-1"
    benchmark_root.mkdir(parents=True)
    write_manifest(benchmark_root)

    script = tmp_path / "fake_agent.py"
    script.write_text(
        """
import json
from pathlib import Path
import sys
workdir = Path(sys.argv[1])
out = Path(sys.argv[2])
trace = Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
(out / "result.txt").write_text("done", encoding="utf-8")
events = [
    {"type": "session_start", "model": "fake", "user_question": "do work"},
    {"type": "result", "status": "success", "duration_ms": 1, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
]
trace.write_text("\\n".join(json.dumps(e) for e in events) + "\\n", encoding="utf-8")
""",
        encoding="utf-8",
    )

    config = SidecarRunConfig(
        benchmark_root=benchmark_root,
        run_label="fake-run",
        agent=AgentCommandConfig(
            name="fake-cli",
            command_template=f"{sys.executable} {script} {{workdir}} {{output_dir}} {{trace_path}}",
        ),
    )

    results = SidecarRunner(config).run()

    assert results[0]["question_id"] == "q-1"
    assert results[0]["trace_quality"] == "full"
    attempt_dir = benchmark_root / "runs" / "fake-run" / "q-1" / "attempt-1"
    assert (attempt_dir / "trace.jsonl").exists()
    assert (attempt_dir / "输出结果" / "result.txt").read_text(encoding="utf-8") == "done"
    meta = json.loads((benchmark_root / "runs" / "fake-run" / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["agent_name"] == "fake-cli"
    assert meta["trace_quality"] == "full"
```

- [ ] **Step 2: Run failing sidecar runner test**

Run:

```bash
cd agent && uv run pytest tests/test_sidecar_runner.py -v
```

Expected: FAIL because `SidecarRunner` does not exist.

- [ ] **Step 3: Implement sidecar runner**

Create `agent/src/sidecar_runner.py`:

```python
from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from src.sidecar_config import SidecarRunConfig


class SidecarRunner:
    def __init__(self, config: SidecarRunConfig):
        self.config = config

    def run(self) -> list[dict]:
        manifest = self._load_manifest()
        self._write_run_meta("full")
        results = []
        for question in manifest.get("questions", []):
            results.append(self.run_question(question))
        aggregate_quality = "degraded" if any(r["trace_quality"] == "degraded" for r in results) else "full"
        self._write_run_meta(aggregate_quality)
        return results

    def run_question(self, question: dict) -> dict:
        question_id = question["question_id"]
        attempt_dir = self._attempt_dir(question_id)
        workdir = attempt_dir / "workdir"
        output_dir = self.config.agent.render_output_dir(workdir)
        trace_path = self.config.agent.render_trace_path(workdir)
        prompt_file = self.config.benchmark_root / question["prompt_file"]
        attempt_dir.mkdir(parents=True, exist_ok=True)
        workdir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        self._prepare_workspace(question, workdir)
        command = self.config.agent.render_command(
            workdir=workdir,
            prompt_file=prompt_file,
            output_dir=output_dir,
            trace_path=trace_path,
        )
        started = time.monotonic()
        completed = subprocess.run(
            shlex.split(command),
            cwd=str(workdir),
            capture_output=True,
            text=True,
            check=False,
        )
        duration_ms = int((time.monotonic() - started) * 1000)

        final_output_dir = attempt_dir / "输出结果"
        if final_output_dir.exists():
            shutil.rmtree(final_output_dir)
        if output_dir.exists():
            shutil.copytree(output_dir, final_output_dir)
        else:
            final_output_dir.mkdir(parents=True, exist_ok=True)

        final_trace = attempt_dir / "trace.jsonl"
        trace_quality = "full"
        if trace_path.exists():
            shutil.copy2(trace_path, final_trace)
        else:
            trace_quality = "degraded"
            self._write_degraded_trace(
                final_trace,
                question=question,
                completed=completed,
                duration_ms=duration_ms,
            )

        return {
            "question_id": question_id,
            "attempt_index": self.config.attempt_index,
            "trace_quality": trace_quality,
            "returncode": completed.returncode,
            "trace_path": str(final_trace),
            "output_dir": str(final_output_dir),
        }

    def _load_manifest(self) -> dict:
        return json.loads((self.config.benchmark_root / "manifest.json").read_text(encoding="utf-8"))

    def _attempt_dir(self, question_id: str) -> Path:
        return (
            self.config.benchmark_root
            / "runs"
            / self.config.run_label
            / question_id
            / f"attempt-{self.config.attempt_index}"
        )

    def _prepare_workspace(self, question: dict, workdir: Path) -> None:
        prompt_src = self.config.benchmark_root / question["prompt_file"]
        shutil.copy2(prompt_src, workdir / "prompt.txt")
        for input_file in question.get("input_files", []):
            src = self.config.benchmark_root / input_file
            dst = workdir / input_file
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.exists():
                shutil.copy2(src, dst)

    def _write_degraded_trace(
        self,
        trace_path: Path,
        question: dict,
        completed: subprocess.CompletedProcess,
        duration_ms: int,
    ) -> None:
        events = [
            {
                "type": "session_start",
                "model": self.config.model or self.config.agent.name,
                "user_question": question.get("question_name", question["question_id"]),
                "trace_quality": "degraded",
            },
            {
                "type": "tool_call",
                "tool_name": "sidecar_command",
                "tool_input": {"agent": self.config.agent.name},
            },
            {
                "type": "tool_result",
                "tool_result": (completed.stdout + completed.stderr)[-4000:],
                "tool_error": completed.returncode != 0,
            },
            {
                "type": "result",
                "status": "success" if completed.returncode == 0 else "error",
                "duration_ms": duration_ms,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
            },
        ]
        trace_path.write_text(
            "\\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\\n",
            encoding="utf-8",
        )

    def _write_run_meta(self, trace_quality: str) -> None:
        run_dir = self.config.benchmark_root / "runs" / self.config.run_label
        run_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "run_label": self.config.run_label,
            "agent_name": self.config.agent.name,
            "model": self.config.model,
            "skill_version": self.config.skill_version,
            "source": "sidecar",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "trace_quality": trace_quality,
        }
        (run_dir / "run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
```

Modify `agent/src/__init__.py`:

```python
from src.sidecar_config import AgentCommandConfig, SidecarRunConfig
from src.sidecar_runner import SidecarRunner

__all__ = ["AgentCommandConfig", "SidecarRunConfig", "SidecarRunner"]
```

- [ ] **Step 4: Run sidecar runner tests**

Run:

```bash
cd agent && uv run pytest tests/test_sidecar_runner.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/src/sidecar_runner.py agent/src/__init__.py agent/tests/test_sidecar_runner.py
git commit -m "feat: run cli agent through sidecar"
```

---

## Task 3: Add Degraded Trace Coverage and Full Verification

**Files:**
- Modify: `agent/tests/test_sidecar_runner.py`

- [ ] **Step 1: Add degraded trace test**

Append to `agent/tests/test_sidecar_runner.py`:

```python
def test_sidecar_writes_degraded_trace_when_agent_trace_missing(tmp_path):
    benchmark_root = tmp_path / "evaluations" / "bench-1"
    benchmark_root.mkdir(parents=True)
    write_manifest(benchmark_root)

    script = tmp_path / "fake_agent_no_trace.py"
    script.write_text(
        """
from pathlib import Path
import sys
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
(out / "result.txt").write_text("done without trace", encoding="utf-8")
print("completed")
""",
        encoding="utf-8",
    )

    config = SidecarRunConfig(
        benchmark_root=benchmark_root,
        run_label="degraded-run",
        agent=AgentCommandConfig(
            name="fake-cli",
            command_template=f"{sys.executable} {script} {{output_dir}}",
        ),
    )

    results = SidecarRunner(config).run()

    assert results[0]["trace_quality"] == "degraded"
    trace_path = benchmark_root / "runs" / "degraded-run" / "q-1" / "attempt-1" / "trace.jsonl"
    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert events[0]["trace_quality"] == "degraded"
    assert events[-1]["status"] == "success"
    meta = json.loads((benchmark_root / "runs" / "degraded-run" / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["trace_quality"] == "degraded"
```

- [ ] **Step 2: Run agent tests**

Run:

```bash
cd agent && uv run pytest
```

Expected: all agent tests pass.

- [ ] **Step 3: Run backend tests**

Run:

```bash
cd backend && uv run pytest
```

Expected: all backend tests pass.

- [ ] **Step 4: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: build exits 0. Existing Rolldown warnings are acceptable.

- [ ] **Step 5: Merge to main and push**

Run:

```bash
git switch main
git merge codex/phase2c-sidecar
git push origin main
```

Expected: push succeeds.

---

## Self-Review Notes

- Spec coverage: covers Phase 2C command templates, isolated workdir, output capture, full/degraded trace collection, and run directory writing.
- Deliberate follow-up: API-based task leasing and upload are not included. This first sidecar writes local evidence directories consumed by Phase 2A.
- Placeholder scan: no unfinished placeholder markers are present.
- Type consistency: config classes are `AgentCommandConfig` and `SidecarRunConfig`; runner class is `SidecarRunner`.
