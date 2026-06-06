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
