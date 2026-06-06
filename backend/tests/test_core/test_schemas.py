import pytest
from pathlib import Path
from src.core.schemas import Manifest, QuestionItem, EvalConfig, FatalRule, IgnoreRule, RunStatus


def test_manifest_parses_valid_json():
    data = {
        "benchmark_id": "scene_0328-2",
        "name": "scene_0328-2",
        "version": "1.0.9",
        "created_at": "2026-04-02T20:19:19+08:00",
        "created_by": "yue",
        "description": "test benchmark",
        "total_questions": 1,
        "questions": [
            {
                "question_id": "q-0001",
                "question_name": "test question",
                "category": "Excel",
                "difficulty": "中等",
                "prompt_file": "q-0001/prompt.txt",
                "input_files": ["q-0001/input.xlsx"],
                "reference_files": ["q-0001/ref_answer.xlsx"],
                "output_dir": "q-0001/output/",
                "eval_config": {
                    "compare_style": True,
                    "ignore_rules": [
                        {"type": "column", "sheet": "Sheet1", "columns": ["K"]}
                    ],
                    "fatal_rules": [
                        {
                            "rule_id": "FR-001",
                            "description": "禁止根据 identity_type 派生数据",
                            "dimension": "tool_accuracy"
                        }
                    ]
                },
                "scene": "skills",
                "skills": "project_business_analysis",
                "payload_size_kb": 128.0,
                "baseline_tokens": 693592,
                "baseline_rounds": 19,
                "baseline_tool_count": 17,
                "baseline_time_ms": 64000,
                "baseline_cost_usd": 3.58132
            }
        ]
    }
    manifest = Manifest.model_validate(data)
    assert manifest.benchmark_id == "scene_0328-2"
    assert manifest.questions[0].question_id == "q-0001"
    assert manifest.questions[0].baseline_tool_count == 17
    assert manifest.questions[0].payload_size_kb == 128.0
    assert manifest.questions[0].eval_config.fatal_rules[0].rule_id == "FR-001"


def test_task_run_status_enum():
    assert RunStatus.PENDING.value == "PENDING"
    assert RunStatus.COMPLETED.value == "COMPLETED"
    assert RunStatus.FAILED.value == "FAILED"
    valid_order = [
        RunStatus.PENDING,
        RunStatus.PARSING_TRACE,
        RunStatus.EVALUATING_BASELINE,
        RunStatus.AWAITING_JUDGE,
        RunStatus.EVALUATING_JUDGE,
        RunStatus.COMPLETED,
    ]
    for i in range(len(valid_order) - 1):
        assert valid_order[i] != valid_order[i + 1]


def test_base_evaluator_is_abstract():
    from src.core.interfaces import BaseEvaluator
    with pytest.raises(TypeError):
        BaseEvaluator()  # Cannot instantiate ABC directly


def test_concrete_evaluator_must_implement_evaluate():
    from src.core.interfaces import BaseEvaluator

    class BadEvaluator(BaseEvaluator):
        pass  # Missing evaluate method

    with pytest.raises(TypeError):
        BadEvaluator()


def test_incomplete_trace_error():
    from src.core.exceptions import IncompleteTraceError
    err = IncompleteTraceError("missing result record", question_id="q-001")
    assert str(err) == "missing result record"
    assert err.question_id == "q-001"


def test_evaluation_error():
    from src.core.exceptions import EvaluationError
    err = EvaluationError("LLM timeout after 3 retries", run_id="run-123")
    assert err.run_id == "run-123"


def test_state_transition_error():
    from src.core.exceptions import StateTransitionError
    err = StateTransitionError(
        from_status="PENDING",
        to_status="COMPLETED",
        reason="Must go through intermediate states"
    )
    assert err.from_status == "PENDING"
    assert err.to_status == "COMPLETED"


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
