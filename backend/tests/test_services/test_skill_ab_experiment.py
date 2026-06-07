import sys
import json
from datetime import datetime, timezone
from pathlib import Path

from src.services.skill_ab_experiment import SkillABRunSpec
from src.services.skill_ab_experiment import SkillABExperimentService


def test_claude_code_preset_uses_builtin_wrapper_when_env_is_absent(monkeypatch):
    monkeypatch.delenv("COWORKEVAL_AGENT_COMMAND_CLAUDE_CODE", raising=False)
    monkeypatch.delenv("COWORKEVAL_CLAUDE_CODE_COMMAND", raising=False)
    monkeypatch.delenv("COWORKEVAL_CLAUDE_MAX_BUDGET_USD", raising=False)
    monkeypatch.delenv("COWORKEVAL_CLAUDE_MODEL", raising=False)

    service = SkillABExperimentService(pipeline_factory=lambda: object())

    command = service._command_template("claude-code")

    assert command.startswith(sys.executable)
    assert "scripts/claude_sidecar_wrapper.py" in command
    assert "--skill-mode {skill_mode}" in command
    assert "{model_args}" in command
    assert "--max-budget-usd 0.5" in command


def test_claude_code_preset_respects_budget_env(monkeypatch):
    monkeypatch.delenv("COWORKEVAL_AGENT_COMMAND_CLAUDE_CODE", raising=False)
    monkeypatch.delenv("COWORKEVAL_CLAUDE_CODE_COMMAND", raising=False)
    monkeypatch.setenv("COWORKEVAL_CLAUDE_MAX_BUDGET_USD", "0.5")

    service = SkillABExperimentService(pipeline_factory=lambda: object())

    assert "--max-budget-usd 0.5" in service._command_template("claude-code")


def test_claude_code_model_comes_from_backend_env(monkeypatch):
    monkeypatch.setenv("COWORKEVAL_CLAUDE_MODEL", "sonnet")
    service = SkillABExperimentService(pipeline_factory=lambda: object())

    assert service._agent_model("claude-code") == "sonnet"


def test_claude_code_model_defaults_in_backend(monkeypatch):
    monkeypatch.delenv("COWORKEVAL_CLAUDE_MODEL", raising=False)
    service = SkillABExperimentService(pipeline_factory=lambda: object())

    assert service._agent_model("claude-code") == ""
    assert service._agent_model_args("claude-code") == ""


def test_claude_code_model_args_are_only_added_when_env_is_set(monkeypatch):
    monkeypatch.setenv("COWORKEVAL_CLAUDE_MODEL", "sonnet")
    service = SkillABExperimentService(pipeline_factory=lambda: object())

    assert service._agent_model_args("claude-code") == "--model sonnet"


def test_question_command_passes_absolute_paths_when_workdir_changes(tmp_path, monkeypatch):
    benchmark_root = tmp_path / "bench"
    question_dir = benchmark_root / "q-1"
    question_dir.mkdir(parents=True)
    (question_dir / "prompt.txt").write_text("do work", encoding="utf-8")
    (benchmark_root / "manifest.json").write_text(
        json.dumps(
            {
                "benchmark_id": "bench",
                "name": "bench",
                "version": "1.0.0",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "total_questions": 1,
                "questions": [
                    {
                        "question_id": "q-1",
                        "question_name": "Q1",
                        "category": "demo",
                        "difficulty": "easy",
                        "prompt_file": "q-1/prompt.txt",
                        "input_files": [],
                        "reference_files": [],
                        "output_dir": "q-1/输出结果/",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    fake_agent = tmp_path / "fake_agent.py"
    fake_agent.write_text(
        """
import json
import sys
from pathlib import Path

prompt = Path(sys.argv[1])
output_dir = Path(sys.argv[2])
trace_path = Path(sys.argv[3])
assert prompt.exists(), prompt
output_dir.mkdir(parents=True, exist_ok=True)
(output_dir / "ok.txt").write_text(prompt.read_text(encoding="utf-8"), encoding="utf-8")
events = [
    {"type": "session_start", "model": "fake", "user_question": "q-1"},
    {"type": "result", "status": "success", "duration_ms": 1, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
]
trace_path.write_text("\\n".join(json.dumps(event) for event in events) + "\\n", encoding="utf-8")
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    service = SkillABExperimentService(pipeline_factory=lambda: object())
    spec = SkillABRunSpec(
        benchmark_root=Path("bench"),
        preset="fake",
        baseline_run_label="baseline",
        skill_run_label="skill",
    )

    result = service._run_question_command(
        spec=spec,
        run_label="baseline",
        question={
            "question_id": "q-1",
            "question_name": "Q1",
            "prompt_file": "q-1/prompt.txt",
            "input_files": [],
        },
        command_template=f"{sys.executable} {fake_agent} {{prompt_file}} {{output_dir}} {{trace_path}}",
        skill_mode="no_skill",
    )

    assert result == "full"
