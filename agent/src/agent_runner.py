from __future__ import annotations
import json
import time
import uuid
from pathlib import Path
from typing import Optional


class AgentRunner:
    """Simulates an agent executing evaluation tasks and producing JSONL traces.

    In production, this would be replaced with actual agent execution logic.
    For now, it generates realistic trace records for testing the eval pipeline.
    """

    def __init__(self, output_dir: str = "/tmp/coworkeval"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_task(
        self,
        question_id: str,
        prompt: str,
        input_files: list[str] | None = None,
        tool_count: int = 5,
        rounds: int = 3,
        duration_ms: int = 30000,
        tokens: int = 100000,
        cost_usd: float = 0.5,
        fail_rate: float = 0.2,
        model: str = "Claude-4-Sonnet",
    ) -> tuple[list[dict], Path]:
        """Run a simulated agent task and produce a JSONL trace.

        Returns (trace_events, trace_file_path).
        """
        run_id = str(uuid.uuid4())[:8]
        trace: list[dict] = []

        # Session start
        trace.append({
            "type": "session_start",
            "model": model,
            "user_question": prompt,
            "run_id": run_id,
        })

        # Tool calls + results (simulated)
        successes = 0
        for i in range(tool_count):
            trace.append({
                "type": "tool_call",
                "tool_name": f"tool_{i % 3}",  # Read, Glob, Shell rotation
                "tool_input": {"arg": f"value_{i}"},
            })

            is_error = (i / tool_count) >= (1.0 - fail_rate) and i > 0
            trace.append({
                "type": "tool_result",
                "tool_result": "Error: something went wrong" if is_error else f"result_{i}",
                "tool_error": is_error,
            })
            if not is_error:
                successes += 1

        # Assistant thinking rounds
        for r in range(rounds):
            trace.append({
                "type": "assistant",
                "thinking": f"This is thinking round {r + 1}. Analyzing results...",
                "text": f"Step {r + 1} completed.",
            })

        # Final result
        trace.append({
            "type": "result",
            "status": "success" if successes > 0 else "error",
            "duration_ms": duration_ms,
            "input_tokens": int(tokens * 0.8),
            "output_tokens": int(tokens * 0.2),
            "cost_usd": cost_usd,
        })

        # Write JSONL
        trace_path = self.output_dir / f"{question_id}_{run_id}.jsonl"
        with open(trace_path, "w", encoding="utf-8") as f:
            for event in trace:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

        return trace, trace_path


    def run_benchmark(
        self,
        manifest: dict,
        tool_counts: list[int] | None = None,
    ) -> dict[str, Path]:
        """Run all questions in a manifest. Returns question_id → trace_path."""
        results = {}
        questions = manifest.get("questions", [])
        for i, q in enumerate(questions):
            tc = tool_counts[i] if tool_counts and i < len(tool_counts) else 5
            _, path = self.run_task(
                question_id=q["question_id"],
                prompt=q.get("prompt_file", f"task_{i}"),
                tool_count=tc,
            )
            results[q["question_id"]] = path
        return results
