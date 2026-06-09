from __future__ import annotations
import json
from pathlib import Path
from src.core.exceptions import IncompleteTraceError, TraceIntegrityError


class TraceParser:
    """Parse JSONL agent trace files and extract process metrics."""

    async def parse(self, file_path: Path | str) -> list[dict]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Trace file not found: {file_path}")

        lines = path.read_text(encoding="utf-8").strip().split("\n")
        return await self.parse_lines(lines)

    async def parse_lines(self, lines: list[str]) -> list[dict]:
        events = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))

        if events:
            has_result = any(e.get("type") == "result" for e in events)
            if not has_result:
                raise IncompleteTraceError(
                    "Trace is incomplete: missing 'result' record.",
                    question_id=None,
                )
            self._validate_tool_integrity(events)
        return events

    def _validate_tool_integrity(self, events: list[dict]) -> None:
        tool_calls = [e for e in events if e.get("type") == "tool_call"]
        tool_results = [e for e in events if e.get("type") == "tool_result"]
        ids = [
            self._tool_event_id(e)
            for e in tool_calls + tool_results
            if self._tool_event_id(e)
        ]
        if not ids:
            return

        call_ids = [self._tool_event_id(e) for e in tool_calls]
        result_ids = [self._tool_event_id(e) for e in tool_results]
        if any(not value for value in call_ids):
            raise TraceIntegrityError("Trace mixes identified and unidentified tool_call events.")
        if any(not value for value in result_ids):
            raise TraceIntegrityError("Trace mixes identified and unidentified tool_result events.")
        if len(set(call_ids)) != len(call_ids):
            raise TraceIntegrityError("Trace contains duplicate tool_call_id values.")
        if len(set(result_ids)) != len(result_ids):
            raise TraceIntegrityError("Trace contains duplicate tool_result ids.")
        if set(call_ids) != set(result_ids):
            missing_results = sorted(set(call_ids) - set(result_ids))
            orphan_results = sorted(set(result_ids) - set(call_ids))
            raise TraceIntegrityError(
                "Trace tool_call/tool_result ids do not match. "
                f"missing_results={missing_results}, orphan_results={orphan_results}"
            )

    def _tool_event_id(self, event: dict) -> str:
        return str(event.get("tool_call_id") or event.get("tool_use_id") or "")

    def extract_metrics(self, trace_data: list[dict]) -> dict:
        tool_calls = [e for e in trace_data if e.get("type") == "tool_call"]
        tool_results = [e for e in trace_data if e.get("type") == "tool_result"]
        assistant_msgs = [e for e in trace_data if e.get("type") == "assistant" and "thinking" in e]

        total_tool_calls = len(tool_calls)
        success_tool_calls = sum(1 for r in tool_results if not r.get("tool_error", False))
        failed_tool_calls = total_tool_calls - success_tool_calls

        result_records = [e for e in trace_data if e.get("type") == "result"]
        if result_records:
            result = result_records[-1]
            duration_ms = result.get("duration_ms", 0)
            input_tokens = result.get("input_tokens", 0)
            output_tokens = result.get("output_tokens", 0)
            cost_usd = result.get("cost_usd", 0.0)
        else:
            duration_ms = 0
            input_tokens = 0
            output_tokens = 0
            cost_usd = 0.0

        return {
            "total_tool_calls": total_tool_calls,
            "success_tool_calls": success_tool_calls,
            "failed_tool_calls": failed_tool_calls,
            "tool_success_rate": (
                (success_tool_calls / total_tool_calls * 100)
                if total_tool_calls > 0 else 100.0
            ),
            "total_tokens": input_tokens + output_tokens,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "rounds": len(assistant_msgs),
            "duration_ms": duration_ms,
            "cost_usd": cost_usd,
        }
