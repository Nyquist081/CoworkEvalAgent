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
        pending_tool_ids: list[str] = []

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
                    result_events = self._extract_tool_result_events(d, pending_tool_ids)
                    if result_events:
                        for event in result_events:
                            events.append(event)
                            if not event["tool_error"]:
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
                                tool_call_id = block.get("id", "")
                                if tool_call_id:
                                    pending_tool_ids.append(tool_call_id)
                                events.append({
                                    "type": "tool_call",
                                    "tool_call_id": tool_call_id,
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
            "trace_schema_version": "1.1",
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

    def _extract_tool_result_events(
        self, record: dict, pending_tool_ids: list[str]
    ) -> list[dict]:
        """Extract tool_result blocks and preserve their Claude tool_use id."""
        message = record.get("message", {})
        content = message.get("content", []) if isinstance(message, dict) else []
        result_blocks = [
            block
            for block in content
            if isinstance(block, dict) and block.get("type") == "tool_result"
        ]

        events = []
        for block in result_blocks:
            result = block.get("content", "")
            result_str = (
                json.dumps(result, ensure_ascii=False)
                if isinstance(result, (dict, list))
                else str(result)
            )
            tool_call_id = str(block.get("tool_use_id", "") or "")
            if tool_call_id in pending_tool_ids:
                pending_tool_ids.remove(tool_call_id)
            if not tool_call_id and pending_tool_ids:
                tool_call_id = pending_tool_ids.pop(0)
            events.append({
                "type": "tool_result",
                "tool_call_id": tool_call_id,
                "tool_result": result_str[:500],
                "tool_error": bool(block.get("is_error")) or self._is_error_result(result_str),
            })

        if events:
            return events

        if "toolUseResult" not in record:
            return []

        result = record["toolUseResult"]
        result_str = json.dumps(result, ensure_ascii=False)
        tool_call_id = (
            str(record.get("toolUseID") or record.get("tool_use_id") or "")
            or (pending_tool_ids.pop(0) if pending_tool_ids else "")
        )
        return [{
            "type": "tool_result",
            "tool_call_id": tool_call_id,
            "tool_result": result_str[:500],
            "tool_error": self._is_error_result(result_str),
        }]

    # ── Task Segmentation ─────────────────────────────────

    def list_task_segments(self, session_path: Path | str) -> list[dict]:
        """List all task segments in a session (boundaries = user prompts).

        Returns list of {index, timestamp, summary (first 100 chars of prompt)}.
        """
        path = Path(session_path)
        segments = []
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                d = json.loads(line.strip())
                if d.get("type") == "user" and not d.get("isSidechain"):
                    msg = d.get("message", {})
                    content = ""
                    if isinstance(msg, dict):
                        raw = msg.get("content", "")
                        if isinstance(raw, list):
                            content = " ".join(
                                c.get("text", "")
                                for c in raw
                                if isinstance(c, dict) and c.get("type") == "text"
                            )
                        elif isinstance(raw, str):
                            content = raw
                    if len(content) > 20:
                        segments.append({
                            "segment_index": len(segments),
                            "line_number": i,
                            "timestamp": d.get("timestamp", ""),
                            "summary": content[:150],
                            "full_prompt": content,
                        })
        return segments

    def extract_task_segment(
        self, session_path: Path | str, segment_index: int
    ) -> dict:
        """Extract ONE task segment from a session as a standalone trace.

        A segment = everything from user prompt at segment_index to
        just before the NEXT user prompt (or end of file).

        Returns same format as parse_session(): {events, metrics}.
        """
        path = Path(session_path)
        segments = self.list_task_segments(path)

        if segment_index >= len(segments):
            raise ValueError(
                f"Segment {segment_index} not found. "
                f"Session has {len(segments)} segments (0-{len(segments)-1})."
            )

        start_line = segments[segment_index]["line_number"]
        end_line = (
            segments[segment_index + 1]["line_number"]
            if segment_index + 1 < len(segments)
            else None
        )

        # Parse only the selected segment
        events = []
        tool_calls = 0
        success_calls = 0
        total_input_tokens = 0
        total_output_tokens = 0
        first_ts = None
        last_ts = None
        model = "unknown"
        user_question = segments[segment_index]["full_prompt"][:300]
        pending_tool_ids: list[str] = []

        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i < start_line:
                    continue
                if end_line is not None and i >= end_line:
                    break

                d = json.loads(line.strip())
                ts = d.get("timestamp", "")
                if ts:
                    if not first_ts:
                        first_ts = ts
                    last_ts = ts

                t = d.get("type", "")

                if t == "user" and d.get("toolUseResult"):
                    for event in self._extract_tool_result_events(d, pending_tool_ids):
                        events.append(event)
                        if not event["tool_error"]:
                            success_calls += 1
                elif t == "user":
                    for event in self._extract_tool_result_events(d, pending_tool_ids):
                        events.append(event)
                        if not event["tool_error"]:
                            success_calls += 1

                elif t == "assistant":
                    msg = d.get("message", {})
                    if not isinstance(msg, dict):
                        continue
                    model = msg.get("model", model)
                    usage = msg.get("usage", {})
                    total_input_tokens += usage.get("input_tokens", 0)
                    total_output_tokens += usage.get("output_tokens", 0)
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if not isinstance(block, dict):
                                continue
                            if block.get("type") == "tool_use":
                                tool_calls += 1
                                tool_call_id = block.get("id", "")
                                if tool_call_id:
                                    pending_tool_ids.append(tool_call_id)
                                events.append({
                                    "type": "tool_call",
                                    "tool_call_id": tool_call_id,
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

        # Compute metrics
        duration_ms = 0
        if first_ts and last_ts:
            try:
                t1 = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                duration_ms = int((t2 - t1).total_seconds() * 1000)
            except (ValueError, TypeError):
                pass

        cost_usd = round(
            total_input_tokens / 1_000_000 * 3.0
            + total_output_tokens / 1_000_000 * 15.0,
            4,
        )

        events.insert(0, {
            "type": "session_start",
            "trace_schema_version": "1.1",
            "model": model,
            "user_question": user_question,
        })
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

    # ── Baseline Asset Management ─────────────────────────

    def save_baseline_trace(
        self,
        session_path: Path | str,
        segment_index: int,
        question_id: str,
        output_dir: str = "sample_data/traces",
    ) -> dict:
        """Extract a task segment and save it as a persistent baseline trace.

        The baseline is stored as {output_dir}/{question_id}_baseline.jsonl.
        This becomes the reference for future comparisons.

        Returns the metrics dict that should go into the Manifest's baseline_* fields.
        """
        result = self.extract_task_segment(session_path, segment_index)
        metrics = result["metrics"]

        out_path = Path(output_dir) / f"{question_id}_baseline.jsonl"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with open(out_path, "w", encoding="utf-8") as f:
            for event in result["events"]:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

        return {
            "baseline_trace_file": str(out_path),
            "baseline_tool_count": metrics["total_tool_calls"],
            "baseline_tokens": metrics["total_tokens"],
            "baseline_rounds": metrics["rounds"],
            "baseline_time_ms": metrics["duration_ms"],
            "baseline_cost_usd": metrics["cost_usd"],
            "baseline_model": metrics["model"],
        }
