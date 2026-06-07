import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WRAPPER = ROOT / "scripts" / "claude_sidecar_wrapper.py"


def _write_fake_claude(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

args_path = Path(os.environ["FAKE_CLAUDE_ARGS_PATH"])
args_path.write_text(json.dumps(sys.argv[1:], ensure_ascii=False), encoding="utf-8")
prompt = sys.argv[-1]
print(json.dumps({"type": "assistant", "message": {"usage": {"input_tokens": 11, "output_tokens": 7}, "content": [{"type": "text", "text": "analysis done"}]}}))
print("FINAL REPORT\\n" + prompt[-80:])
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_wrapper_runs_claude_and_writes_platform_trace(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_claude(fake_bin / "claude")

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Inspect the tiny project.", encoding="utf-8")
    output_dir = tmp_path / "out"
    trace_path = tmp_path / "trace.jsonl"
    args_path = tmp_path / "args.json"

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["FAKE_CLAUDE_ARGS_PATH"] = str(args_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(WRAPPER),
            "--prompt-file",
            str(prompt_file),
            "--output-dir",
            str(output_dir),
            "--trace-path",
            str(trace_path),
            "--skill-mode",
            "no_skill",
            "--model",
            "haiku",
            "--max-budget-usd",
            "0.25",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    args = json.loads(args_path.read_text(encoding="utf-8"))
    assert "--model" in args
    assert "haiku" in args
    assert "text" in args
    assert "--max-budget-usd" in args
    assert "0.25" in args
    assert "--append-system-prompt" in args
    system_prompt = args[args.index("--append-system-prompt") + 1]
    assert "Do not use any external skill instructions" in system_prompt

    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert events[0]["type"] == "session_start"
    assert events[0]["skill_mode"] == "no_skill"
    assert events[-1]["type"] == "result"
    assert events[-1]["status"] == "success"
    assert events[-1]["input_tokens"] == 11
    assert events[-1]["output_tokens"] == 7
    assert (output_dir / "claude_response.md").read_text(encoding="utf-8").startswith("FINAL REPORT")


def test_wrapper_uses_claude_default_model_when_model_is_not_set(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_claude(fake_bin / "claude")

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Inspect the tiny project.", encoding="utf-8")
    args_path = tmp_path / "args.json"

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["FAKE_CLAUDE_ARGS_PATH"] = str(args_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(WRAPPER),
            "--prompt-file",
            str(prompt_file),
            "--output-dir",
            str(tmp_path / "out"),
            "--trace-path",
            str(tmp_path / "trace.jsonl"),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    args = json.loads(args_path.read_text(encoding="utf-8"))
    assert "--model" not in args


def test_wrapper_does_not_overwrite_agent_created_response_file(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    script = fake_bin / "claude"
    script.write_text(
        """#!/usr/bin/env python3
from pathlib import Path
import sys
prompt = sys.argv[-1]
marker = "output directory: "
out = Path(prompt.split(marker, 1)[1].split("\\n", 1)[0])
out.mkdir(parents=True, exist_ok=True)
(out / "claude_response.md").write_text("agent-owned report", encoding="utf-8")
print("stdout summary")
""",
        encoding="utf-8",
    )
    script.chmod(0o755)

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Inspect the tiny project.", encoding="utf-8")
    output_dir = tmp_path / "out"
    trace_path = tmp_path / "trace.jsonl"

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

    completed = subprocess.run(
        [
            sys.executable,
            str(WRAPPER),
            "--prompt-file",
            str(prompt_file),
            "--output-dir",
            str(output_dir),
            "--trace-path",
            str(trace_path),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert (output_dir / "claude_response.md").read_text(encoding="utf-8") == "agent-owned report"
    assert (output_dir / "claude_stdout.md").read_text(encoding="utf-8").strip() == "stdout summary"


def test_wrapper_injects_skill_file_for_skill_mode(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_claude(fake_bin / "claude")

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Review app.py.", encoding="utf-8")
    skill_path = tmp_path / "skills" / "security" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text("# Security Skill\nAlways inspect auth boundaries.", encoding="utf-8")
    args_path = tmp_path / "args.json"

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["FAKE_CLAUDE_ARGS_PATH"] = str(args_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(WRAPPER),
            "--prompt-file",
            str(prompt_file),
            "--output-dir",
            str(tmp_path / "out"),
            "--trace-path",
            str(tmp_path / "trace.jsonl"),
            "--skill-mode",
            "with_skill",
            "--skill-path",
            str(skill_path),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    args = json.loads(args_path.read_text(encoding="utf-8"))
    system_prompt = args[args.index("--append-system-prompt") + 1]
    assert "Security Skill" in system_prompt
    assert "Always inspect auth boundaries" in system_prompt
