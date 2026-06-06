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
    """Execute a CLI Agent command and write CoworkEval run evidence."""

    def __init__(self, config: SidecarRunConfig):
        self.config = config

    def run(self) -> list[dict]:
        manifest = self._load_manifest()
        self._write_run_meta("full")
        results = []
        for question in manifest.get("questions", []):
            results.append(self.run_question(question))

        aggregate_quality = (
            "degraded"
            if any(r["trace_quality"] == "degraded" for r in results)
            else "full"
        )
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
        manifest_path = self.config.benchmark_root / "manifest.json"
        return json.loads(manifest_path.read_text(encoding="utf-8"))

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
            "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n",
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
        (run_dir / "run_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
