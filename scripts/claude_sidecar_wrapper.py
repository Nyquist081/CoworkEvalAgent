#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Claude Code once and write CoworkEval-compatible evidence."
    )
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--trace-path", required=True)
    parser.add_argument("--skill-mode", choices=("no_skill", "with_skill"), default="no_skill")
    parser.add_argument("--skill-path", default="")
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--max-budget-usd", default="0.5")
    parser.add_argument("--claude-bin", default="claude")
    return parser.parse_args()


def build_system_prompt(skill_mode: str, skill_path: str) -> str:
    if skill_mode == "no_skill":
        return (
            "You are running as the baseline arm of a CoworkEval experiment. "
            "Do not use any external skill instructions, named skills, or workflow plugins. "
            "Solve only from the user prompt and files in the working directory."
        )

    path = Path(skill_path) if skill_path else None
    if not path or not path.exists():
        return (
            "You are running as the skill-enabled arm of a CoworkEval experiment, "
            "but no SKILL.md file was found. State that the skill file is unavailable "
            "and proceed carefully."
        )
    skill_text = path.read_text(encoding="utf-8")
    return (
        "You are running as the skill-enabled arm of a CoworkEval experiment. "
        "Follow the skill instructions below when they are relevant.\n\n"
        f"--- SKILL.md ---\n{skill_text}\n--- END SKILL.md ---"
    )


def build_user_prompt(prompt_file: Path, output_dir: Path) -> str:
    prompt = prompt_file.read_text(encoding="utf-8")
    return (
        f"{prompt}\n\n"
        "CoworkEval execution contract:\n"
        f"- Write any final artifacts into this output directory: {output_dir}\n"
        "- If the task is analysis-only, still write a concise final report named "
        "`claude_response.md` in that output directory.\n"
        "- Keep the final answer concise and include the exact files you created."
    )


def maybe_json(line: str) -> dict | None:
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def collect_usage(stdout: str) -> tuple[int, int]:
    input_tokens = 0
    output_tokens = 0
    for line in stdout.splitlines():
        payload = maybe_json(line)
        if not payload:
            continue
        message = payload.get("message")
        if isinstance(message, dict):
            usage = message.get("usage")
            if isinstance(usage, dict):
                input_tokens += int(usage.get("input_tokens") or 0)
                output_tokens += int(usage.get("output_tokens") or 0)
        usage = payload.get("usage")
        if isinstance(usage, dict):
            input_tokens += int(usage.get("input_tokens") or 0)
            output_tokens += int(usage.get("output_tokens") or 0)
    return input_tokens, output_tokens


def plain_response(stdout: str) -> str:
    lines: list[str] = []
    for line in stdout.splitlines():
        if maybe_json(line):
            continue
        if line.strip():
            lines.append(line)
    return "\n".join(lines).strip() or stdout.strip()


def write_trace(
    trace_path: Path,
    *,
    status: str,
    skill_mode: str,
    model: str,
    prompt_file: Path,
    stdout: str,
    stderr: str,
    returncode: int,
    duration_ms: int,
) -> None:
    input_tokens, output_tokens = collect_usage(stdout)
    response = plain_response(stdout)
    events = [
        {
            "type": "session_start",
            "model": model,
            "user_question": prompt_file.name,
            "skill_mode": skill_mode,
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "type": "tool_call",
            "tool_name": "claude_code",
            "tool_input": {
                "skill_mode": skill_mode,
                "prompt_file": str(prompt_file),
            },
        },
        {
            "type": "tool_result",
            "tool_result": (stdout + stderr)[-4000:],
            "tool_error": returncode != 0,
        },
    ]
    if response:
        events.append(
            {
                "type": "assistant",
                "text": response[-4000:],
                "thinking": response[-1000:],
            }
        )
    events.append(
        {
            "type": "result",
            "status": status,
            "duration_ms": duration_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": 0.0,
        }
    )
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(
        "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    prompt_file = Path(args.prompt_file)
    output_dir = Path(args.output_dir)
    trace_path = Path(args.trace_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    system_prompt = build_system_prompt(args.skill_mode, args.skill_path)
    user_prompt = build_user_prompt(prompt_file, output_dir)
    command = [
        args.claude_bin,
        "-p",
        "--model",
        args.model,
        "--output-format",
        "text",
        "--no-session-persistence",
        "--permission-mode",
        "acceptEdits",
        "--max-budget-usd",
        args.max_budget_usd,
        "--append-system-prompt",
        system_prompt,
        user_prompt,
    ]

    started = time.monotonic()
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    duration_ms = int((time.monotonic() - started) * 1000)

    report_path = output_dir / "claude_response.md"
    stdout_path = output_dir / "claude_stdout.md"
    response = plain_response(completed.stdout)
    report_text = (
        response
        or completed.stderr[-4000:]
        or "Claude produced no text output."
    )
    if report_path.exists():
        stdout_path.write_text(report_text + "\n", encoding="utf-8")
    else:
        report_path.write_text(report_text + "\n", encoding="utf-8")

    write_trace(
        trace_path,
        status="success" if completed.returncode == 0 else "error",
        skill_mode=args.skill_mode,
        model=args.model,
        prompt_file=prompt_file,
        stdout=completed.stdout,
        stderr=completed.stderr,
        returncode=completed.returncode,
        duration_ms=duration_ms,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
