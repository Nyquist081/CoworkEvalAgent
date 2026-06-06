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

from src.sidecar_config import AgentCommandConfig, SidecarRunConfig  # noqa: E402
from src.sidecar_runner import SidecarRunner  # noqa: E402

sys.path.remove(str(ROOT / "agent"))
for module_name in list(sys.modules):
    if module_name == "src" or module_name.startswith("src."):
        del sys.modules[module_name]

sys.path.insert(0, str(ROOT / "backend"))
from src.evaluator.result_comparator import ResultComparator  # noqa: E402
from src.infrastructure.trace_parser import TraceParser  # noqa: E402
from src.services.baseline_evaluator import BaselineEvaluator  # noqa: E402
from src.services.evaluation_loader import EvaluationLoader  # noqa: E402


def write_benchmark(root: Path) -> None:
    qroot = root / "q-1"
    (qroot / "输入文件").mkdir(parents=True)
    (qroot / "参考答案").mkdir(parents=True)
    pd.DataFrame({"A": [1], "B": ["ok"]}).to_excel(
        qroot / "参考答案" / "answer.xlsx", index=False
    )
    (qroot / "输入文件" / "input.txt").write_text("input", encoding="utf-8")
    (qroot / "prompt.txt").write_text(
        "create result.xlsx matching answer", encoding="utf-8"
    )
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
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )


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
                    command_template=(
                        f"{sys.executable} {fake_agent} "
                        "{output_dir} {trace_path}"
                    ),
                ),
            )
        )
        sidecar_results = sidecar.run()

        bundle = EvaluationLoader(benchmark_root).load_run("fake-run")
        parser = TraceParser()
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
