import json
from datetime import datetime, timezone

import pytest

from src.core.schemas import RunSource, TraceQuality
from src.services.evaluation_loader import EvaluationLoader


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
