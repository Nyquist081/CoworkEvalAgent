from __future__ import annotations

import json
import os
import sys
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from src.core.schemas import TaskRun
from src.services.evaluation_loader import EvaluationLoader


PipelineFactory = Callable[[], object]


@dataclass(frozen=True)
class SkillABRunSpec:
    benchmark_root: Path
    preset: str
    baseline_run_label: str
    skill_run_label: str
    judge_enabled: bool = False
    skill_version: str = ""


class SkillABExperimentService:
    """Run a paired no-skill / with-skill experiment and evaluate both runs."""

    def __init__(self, pipeline_factory: PipelineFactory):
        self.pipeline_factory = pipeline_factory

    async def run_experiment(self, spec: SkillABRunSpec) -> dict:
        self._validate_spec(spec)
        if spec.preset == "mock-demo":
            self._materialize_mock_demo(spec)
        else:
            self._run_command_preset_pair(spec)

        baseline = await self._evaluate_label(
            spec.benchmark_root,
            spec.baseline_run_label,
            judge_enabled=spec.judge_enabled,
        )
        skill = await self._evaluate_label(
            spec.benchmark_root,
            spec.skill_run_label,
            judge_enabled=spec.judge_enabled,
        )
        compare_run_ids = [str(baseline["run_id"]), str(skill["run_id"])]
        return {
            "experiment_id": (
                f"{baseline['benchmark_id']}__{spec.baseline_run_label}"
                f"__{spec.skill_run_label}"
            ),
            "benchmark_id": baseline["benchmark_id"],
            "baseline": baseline,
            "skill": skill,
            "compare_run_ids": compare_run_ids,
            "compare_url": f"/compare?runs={','.join(compare_run_ids)}",
            "preset": spec.preset,
            "judge_enabled": spec.judge_enabled,
        }

    def _validate_spec(self, spec: SkillABRunSpec) -> None:
        if spec.baseline_run_label == spec.skill_run_label:
            raise ValueError("baseline_run_label and skill_run_label must be different")
        for label in (spec.baseline_run_label, spec.skill_run_label):
            if not label or "/" in label or "\\" in label or ".." in label:
                raise ValueError(f"Invalid run label: {label}")
        if not (spec.benchmark_root / "manifest.json").exists():
            raise ValueError(f"manifest.json not found in {spec.benchmark_root}")

    async def _evaluate_label(
        self,
        benchmark_root: Path,
        run_label: str,
        judge_enabled: bool,
    ) -> dict:
        loader = EvaluationLoader(benchmark_root)
        bundle = loader.load_run(run_label)
        pipeline = self.pipeline_factory()
        run: TaskRun = await pipeline.create_run(
            bundle.manifest,
            judge_enabled=judge_enabled,
            run_metadata=bundle.run_metadata,
        )
        scores = await pipeline.execute_offline_run(
            run.id,
            bundle.inputs,
            judge_enabled=judge_enabled,
        )
        overall = (
            sum(score.overall_score or 0 for score in scores) / len(scores)
            if scores else 0.0
        )
        return {
            "run_id": str(run.id),
            "benchmark_id": bundle.manifest.benchmark_id,
            "run_label": bundle.run_metadata.run_label,
            "score_count": len(scores),
            "overall_score": round(overall, 2),
        }

    def _materialize_mock_demo(self, spec: SkillABRunSpec) -> None:
        root = spec.benchmark_root
        demo_source = self._demo_source_root()
        question_id = "alarm_analysis-0003"
        self._copy_demo_run(
            root=root,
            run_label=spec.baseline_run_label,
            question_id=question_id,
            trace_source=demo_source / "traces" / "alarm_baseline_no_skill.jsonl",
            output_source=(
                demo_source
                / question_id
                / "输出结果"
                / "告警汇总_no_skill.xlsx"
            ),
            meta={
                "agent_name": "mock-claude",
                "model": "demo-baseline",
                "skill_version": "none",
                "source": "sidecar",
            },
        )
        self._copy_demo_run(
            root=root,
            run_label=spec.skill_run_label,
            question_id=question_id,
            trace_source=demo_source / "traces" / "alarm_with_skill.jsonl",
            output_source=(
                demo_source
                / question_id
                / "输出结果"
                / "告警汇总_with_skill.xlsx"
            ),
            meta={
                "agent_name": "mock-claude",
                "model": "demo-with-skill",
                "skill_version": spec.skill_version or "alarm_analysis@demo",
                "source": "sidecar",
            },
        )

    def _demo_source_root(self) -> Path:
        for candidate in (Path("sample_data"), Path("backend/sample_data")):
            if (candidate / "traces" / "alarm_with_skill.jsonl").exists():
                return candidate
        raise ValueError("mock demo source data not found")

    def _copy_demo_run(
        self,
        root: Path,
        run_label: str,
        question_id: str,
        trace_source: Path,
        output_source: Path,
        meta: dict,
    ) -> None:
        attempt_dir = root / "runs" / run_label / question_id / "attempt-1"
        output_dir = attempt_dir / "输出结果"
        output_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(trace_source, attempt_dir / "trace.jsonl")
        shutil.copy2(output_source, output_dir / output_source.name)
        self._write_run_meta(root, run_label, meta, trace_quality="full")

    def _run_command_preset_pair(self, spec: SkillABRunSpec) -> None:
        command_template = self._command_template(spec.preset)
        manifest = json.loads((spec.benchmark_root / "manifest.json").read_text(encoding="utf-8"))
        self._run_command_label(
            spec=spec,
            manifest=manifest,
            run_label=spec.baseline_run_label,
            command_template=command_template,
            skill_mode="no_skill",
        )
        self._run_command_label(
            spec=spec,
            manifest=manifest,
            run_label=spec.skill_run_label,
            command_template=command_template,
            skill_mode="with_skill",
        )

    def _command_template(self, preset: str) -> str:
        env_name = f"COWORKEVAL_AGENT_COMMAND_{preset.upper().replace('-', '_')}"
        command = os.getenv(env_name)
        if command:
            return command
        if preset == "claude-code":
            command = os.getenv("COWORKEVAL_CLAUDE_CODE_COMMAND")
            if command:
                return command
            budget = os.getenv("COWORKEVAL_CLAUDE_MAX_BUDGET_USD", "0.5")
            wrapper = Path(__file__).resolve().parents[3] / "scripts" / "claude_sidecar_wrapper.py"
            if wrapper.exists():
                return (
                    f"{shlex.quote(sys.executable)} {shlex.quote(str(wrapper))} "
                    "--prompt-file {prompt_file} "
                    "--output-dir {output_dir} "
                    "--trace-path {trace_path} "
                    "--skill-mode {skill_mode} "
                    "--skill-path {skill_path} "
                    "--model {model} "
                    f"--max-budget-usd {shlex.quote(budget)}"
                )
        raise ValueError(
            f"Agent preset '{preset}' is not configured. Set {env_name} in backend .env."
        )

    def _agent_model(self, preset: str) -> str:
        if preset == "claude-code":
            return os.getenv("COWORKEVAL_CLAUDE_MODEL", "haiku")
        if preset == "mock-demo":
            return "demo"
        return os.getenv(f"COWORKEVAL_{preset.upper().replace('-', '_')}_MODEL", preset)

    def _run_command_label(
        self,
        spec: SkillABRunSpec,
        manifest: dict,
        run_label: str,
        command_template: str,
        skill_mode: str,
    ) -> None:
        trace_quality = "full"
        for question in manifest.get("questions", []):
            result = self._run_question_command(
                spec=spec,
                run_label=run_label,
                question=question,
                command_template=command_template,
                skill_mode=skill_mode,
            )
            if result == "degraded":
                trace_quality = "degraded"

        self._write_run_meta(
            spec.benchmark_root,
            run_label,
            {
                "agent_name": spec.preset,
                "model": self._agent_model(spec.preset),
                "skill_version": "none" if skill_mode == "no_skill" else spec.skill_version,
                "source": "sidecar",
            },
            trace_quality=trace_quality,
        )

    def _run_question_command(
        self,
        spec: SkillABRunSpec,
        run_label: str,
        question: dict,
        command_template: str,
        skill_mode: str,
    ) -> str:
        question_id = question["question_id"]
        attempt_dir = spec.benchmark_root / "runs" / run_label / question_id / "attempt-1"
        workdir = attempt_dir / "workdir"
        output_dir = workdir / "输出结果"
        trace_path = workdir / "trace.jsonl"
        prompt_file = spec.benchmark_root / question["prompt_file"]
        skill_path = spec.benchmark_root / "skills" / question.get("skills", "") / "SKILL.md"

        if attempt_dir.exists():
            shutil.rmtree(attempt_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        workdir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(prompt_file, workdir / "prompt.txt")
        for input_file in question.get("input_files", []):
            src = spec.benchmark_root / input_file
            dst = workdir / input_file
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.exists():
                shutil.copy2(src, dst)

        command = command_template.format(
            workdir=str(workdir.resolve()),
            prompt_file=str(prompt_file.resolve()),
            output_dir=str(output_dir.resolve()),
            trace_path=str(trace_path.resolve()),
            skill_mode=skill_mode,
            skill_path=str(skill_path.resolve()),
            model=self._agent_model(spec.preset),
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
        if output_dir.exists():
            shutil.copytree(output_dir, final_output_dir, dirs_exist_ok=True)
        else:
            final_output_dir.mkdir(parents=True, exist_ok=True)

        final_trace = attempt_dir / "trace.jsonl"
        if trace_path.exists():
            shutil.copy2(trace_path, final_trace)
            return "full"

        self._write_degraded_trace(
            final_trace,
            question=question,
            completed=completed,
            duration_ms=duration_ms,
            agent_name=spec.preset,
        )
        return "degraded"

    def _write_degraded_trace(
        self,
        trace_path: Path,
        question: dict,
        completed: subprocess.CompletedProcess,
        duration_ms: int,
        agent_name: str,
    ) -> None:
        events = [
            {
                "type": "session_start",
                "model": agent_name,
                "user_question": question.get("question_name", question["question_id"]),
                "trace_quality": "degraded",
            },
            {
                "type": "tool_call",
                "tool_name": "sidecar_command",
                "tool_input": {"agent": agent_name},
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
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(
            "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n",
            encoding="utf-8",
        )

    def _write_run_meta(
        self,
        root: Path,
        run_label: str,
        meta: dict,
        trace_quality: str,
    ) -> None:
        run_dir = root / "runs" / run_label
        run_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_label": run_label,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "trace_quality": trace_quality,
            **meta,
        }
        (run_dir / "run_meta.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
