import json
import pytest
from pathlib import Path
from src.agent_runner import AgentRunner


def test_run_task_creates_trace_file(tmp_path):
    runner = AgentRunner(output_dir=str(tmp_path))
    trace, path = runner.run_task(
        question_id="q-001",
        prompt="Test prompt",
        tool_count=3,
        rounds=2,
    )
    assert path.exists()
    assert len(trace) > 0
    assert trace[0]["type"] == "session_start"
    assert trace[-1]["type"] == "result"


def test_trace_is_valid_jsonl(tmp_path):
    runner = AgentRunner(output_dir=str(tmp_path))
    _, path = runner.run_task(question_id="q-002", prompt="Test")
    lines = path.read_text().strip().split("\n")
    for line in lines:
        obj = json.loads(line)
        assert "type" in obj


def test_trace_result_has_metrics(tmp_path):
    runner = AgentRunner(output_dir=str(tmp_path))
    trace, _ = runner.run_task(
        question_id="q-003", prompt="Test",
        tool_count=4, duration_ms=45000, tokens=200000, cost_usd=1.5,
    )
    result = trace[-1]
    assert result["duration_ms"] == 45000
    assert result["input_tokens"] + result["output_tokens"] == 200000
    assert result["cost_usd"] == 1.5


def test_run_benchmark(tmp_path):
    runner = AgentRunner(output_dir=str(tmp_path))
    manifest = {
        "benchmark_id": "bench-1",
        "questions": [
            {"question_id": "q-001", "prompt_file": "prompt1.txt"},
            {"question_id": "q-002", "prompt_file": "prompt2.txt"},
        ],
    }
    results = runner.run_benchmark(manifest, tool_counts=[3, 5])
    assert len(results) == 2
    for path in results.values():
        assert path.exists()
