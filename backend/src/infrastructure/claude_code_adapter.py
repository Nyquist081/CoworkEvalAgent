"""Adapter: Convert Claude Code native session JSONL to CoworkEval trace format.

Claude Code writes sessions to:
    ~/.claude/projects/<project-slug>/<session-id>.jsonl

Format mapping:
    Claude Code assistant[content: tool_use]   → tool_call
    Claude Code user[toolUseResult]            → tool_result
    Claude Code assistant[content: text]       → assistant (thinking)
    Claude Code assistant[usage]               → token extraction
    Timestamps (first → last)                  → duration_ms
"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class ClaudeCodeAdapter:
    """Parse Claude Code's native session JSONL into CoworkEval trace format."""

    def parse_session(self, session_path: Path | str) -> dict:
        """Parse a Claude Code session JSONL file.

        Returns:
            {
                "events": list of standardized trace events,
                "metrics": {total_tool_calls, success_tool_calls, failed_tool_calls,
                            total_tokens, input_tokens, output_tokens,
                            rounds, duration_ms, cost_usd}
            }
        """
        path = Path(session_path)
        if not path.exists():
            raise FileNotFoundError(f"Session file not found: {session_path}")

        events = []
        tool_calls = 0
        success_calls = 0
        total_input_tokens = 0
        total_output_tokens = 0
        first_ts = None
        last_ts = None
        model = "unknown"
        user_question = ""

        with open(path, encoding="utf-8") as f:
            for line in f:
                d = json.loads(line.strip())
                ts = d.get("timestamp", "")
                if ts:
                    if not first_ts:
                        first_ts = ts
                    last_ts = ts

                t = d.get("type", "")

                # ── User messages ──────────────────────────
                if t == "user" and not d.get("isSidechain"):
                    # Tool results
                    if d.get("toolUseResult"):
                        result = d["toolUseResult"]
                        result_str = json.dumps(result, ensure_ascii=False)
                        is_error = self._is_error_result(result_str)
                        events.append({
                            "type": "tool_result",
                            "tool_result": result_str[:500],
                            "tool_error": is_error,
                        })
                        if not is_error:
                            success_calls += 1
                    else:
                        # User prompt
                        msg = d.get("message", {})
                        if isinstance(msg, dict):
                            content = msg.get("content", "")
                            if isinstance(content, list):
                                text_parts = [
                                    c.get("text", "")
                                    for c in content
                                    if isinstance(c, dict) and c.get("type") == "text"
                                ]
                                content = " ".join(text_parts)
                            if isinstance(content, str) and len(content) > 5:
                                if not user_question:
                                    user_question = content[:500]

                # ── Assistant messages ─────────────────────
                elif t == "assistant":
                    msg = d.get("message", {})
                    if not isinstance(msg, dict):
                        continue

                    # Model
                    model = msg.get("model", model)

                    # Usage
                    usage = msg.get("usage", {})
                    total_input_tokens += usage.get("input_tokens", 0)
                    total_output_tokens += usage.get("output_tokens", 0)

                    # Content blocks
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if not isinstance(block, dict):
                                continue
                            if block.get("type") == "tool_use":
                                tool_calls += 1
                                events.append({
                                    "type": "tool_call",
                                    "tool_name": block.get("name", "unknown"),
                                    "tool_input": block.get("input", {}),
                                })
                            elif block.get("type") == "text":
                                text = block.get("text", "")
                                events.append({
                                    "type": "assistant",
                                    "thinking": text[:300],
                                    "text": text[:300],
                                })

        # ── Compute session metrics ────────────────────────
        duration_ms = 0
        if first_ts and last_ts:
            try:
                t1 = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                duration_ms = int((t2 - t1).total_seconds() * 1000)
            except (ValueError, TypeError):
                pass

        # Cost estimate: Claude Sonnet pricing
        cost_usd = round(
            total_input_tokens / 1_000_000 * 3.0
            + total_output_tokens / 1_000_000 * 15.0,
            4,
        )

        # Add session_start event at the beginning
        events.insert(0, {
            "type": "session_start",
            "model": model,
            "user_question": user_question[:300] if user_question else "",
        })

        # Add result event at the end
        events.append({
            "type": "result",
            "status": "success",
            "duration_ms": duration_ms,
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "cost_usd": cost_usd,
        })

        rounds = len([e for e in events if e["type"] == "assistant"])

        return {
            "events": events,
            "metrics": {
                "total_tool_calls": tool_calls,
                "success_tool_calls": success_calls,
                "failed_tool_calls": tool_calls - success_calls,
                "tool_success_rate": (
                    (success_calls / tool_calls * 100) if tool_calls > 0 else 100.0
                ),
                "total_tokens": total_input_tokens + total_output_tokens,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "rounds": rounds,
                "duration_ms": duration_ms,
                "cost_usd": cost_usd,
                "model": model,
            },
        }

    def find_sessions_for_project(self, project_dir: str) -> list[Path]:
        """Find all Claude Code session JSONL files for a project."""
        import hashlib

        project_path = str(Path(project_dir).resolve())
        slug = (
            "-"
            + project_path.lstrip("/")
            .replace("/", "-")
            .replace(" ", "-")
        )

        sessions_dir = Path.home() / ".claude" / "projects" / slug
        if not sessions_dir.exists():
            return []

        sessions = sorted(
            sessions_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        # Filter out subagent sessions
        return [s for s in sessions if "subagents" not in str(s)]

    def _is_error_result(self, result_str: str) -> bool:
        """Heuristic: detect error/tool failure in result."""
        lower = result_str.lower()
        error_markers = [
            "error", "denied", "failed", "traceback",
            "permission denied", "not found",
        ]
        return any(m in lower for m in error_markers)
