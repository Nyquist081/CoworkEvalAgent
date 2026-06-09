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
        diagnostic = self.diagnose_integrity(events)
        if diagnostic["integrity_status"] == "ok":
            return
        raise TraceIntegrityError(diagnostic["message"])

    def diagnose_integrity(self, events: list[dict]) -> dict:
        tool_calls = [e for e in events if e.get("type") == "tool_call"]
        tool_results = [e for e in events if e.get("type") == "tool_result"]
        ids = [
            self._tool_event_id(e)
            for e in tool_calls + tool_results
            if self._tool_event_id(e)
        ]
        if not ids:
            return {
                "integrity_status": "ok",
                "failure_domain": "none",
                "affected_tool_call_ids": [],
                "scoring_policy": "normal_scoring",
                "message": "Trace has no tool ids; legacy trace compatibility mode.",
            }

        call_ids = [self._tool_event_id(e) for e in tool_calls]
        result_ids = [self._tool_event_id(e) for e in tool_results]
        if any(not value for value in call_ids):
            return self._integrity_problem(
                "mixed_tool_id",
                [],
                "Trace mixes identified and unidentified tool_call events.",
            )
        if any(not value for value in result_ids):
            return self._integrity_problem(
                "mixed_tool_id",
                [],
                "Trace mixes identified and unidentified tool_result events.",
            )
        if len(set(call_ids)) != len(call_ids):
            return self._integrity_problem(
                "duplicate_tool_id",
                self._duplicates(call_ids),
                "Trace contains duplicate tool_call_id values.",
            )
        if len(set(result_ids)) != len(result_ids):
            return self._integrity_problem(
                "duplicate_tool_id",
                self._duplicates(result_ids),
                "Trace contains duplicate tool_result ids.",
            )
        if set(call_ids) != set(result_ids):
            missing_results = sorted(set(call_ids) - set(result_ids))
            orphan_results = sorted(set(result_ids) - set(call_ids))
            status = "missing_tool_result" if missing_results else "orphan_tool_result"
            return self._integrity_problem(
                status,
                missing_results or orphan_results,
                "Trace tool_call/tool_result ids do not match. "
                f"missing_results={missing_results}, orphan_results={orphan_results}",
            )
        return {
            "integrity_status": "ok",
            "failure_domain": "none",
            "affected_tool_call_ids": [],
            "scoring_policy": "normal_scoring",
            "message": "Every identified tool_call has exactly one matching tool_result.",
        }

    def _tool_event_id(self, event: dict) -> str:
        return str(event.get("tool_call_id") or event.get("tool_use_id") or "")

    def _integrity_problem(
        self, status: str, affected_tool_call_ids: list[str], message: str
    ) -> dict:
        return {
            "integrity_status": status,
            "failure_domain": "harness",
            "affected_tool_call_ids": affected_tool_call_ids,
            "scoring_policy": "do_not_penalize_agent_tool_accuracy",
            "message": message,
        }

    def _duplicates(self, values: list[str]) -> list[str]:
        seen = set()
        duplicates = []
        for value in values:
            if value in seen and value not in duplicates:
                duplicates.append(value)
            seen.add(value)
        return duplicates

    def extract_metrics(self, trace_data: list[dict]) -> dict:
        tool_calls = [e for e in trace_data if e.get("type") == "tool_call"]
        tool_results = [e for e in trace_data if e.get("type") == "tool_result"]
        assistant_msgs = [e for e in trace_data if e.get("type") == "assistant" and "thinking" in e]
        assistant_events = [e for e in trace_data if e.get("type") == "assistant"]

        total_tool_calls = len(tool_calls)
        diagnostic = self.diagnose_integrity(trace_data)
        has_identified_tools = any(
            self._tool_event_id(e) for e in tool_calls + tool_results
        )
        if has_identified_tools:
            call_ids = {self._tool_event_id(e) for e in tool_calls if self._tool_event_id(e)}
            result_ids = {self._tool_event_id(e) for e in tool_results if self._tool_event_id(e)}
            observed_result_ids = call_ids & result_ids
            observed_tool_results = len(observed_result_ids)
            missing_tool_results = len(call_ids - result_ids)
            observed_results = [
                e for e in tool_results if self._tool_event_id(e) in observed_result_ids
            ]
        else:
            observed_tool_results = len(tool_results)
            missing_tool_results = max(0, total_tool_calls - observed_tool_results)
            observed_results = tool_results

        success_tool_calls = sum(1 for r in observed_results if not r.get("tool_error", False))
        failed_tool_calls = observed_tool_results - success_tool_calls
        agent_tool_success_rate = (
            (success_tool_calls / observed_tool_results * 100)
            if observed_tool_results > 0 else 100.0
        )
        trace_observability_rate = (
            (observed_tool_results / total_tool_calls * 100)
            if total_tool_calls > 0 else 100.0
        )

        result_records = [e for e in trace_data if e.get("type") == "result"]
        lifecycle_completeness_rate = self._lifecycle_completeness_rate(trace_data)
        metric_completeness_rate = self._metric_completeness_rate(result_records)
        reasoning_visibility_rate = self._reasoning_visibility_rate(
            assistant_events, total_tool_calls
        )
        critical_event_impact = self._critical_event_impact(diagnostic, tool_calls)
        tool_observability_factor = self._trace_observability_factor(
            trace_observability_rate
        )
        evaluation_confidence = round(
            100.0
            * tool_observability_factor
            * (lifecycle_completeness_rate / 100.0)
            * (metric_completeness_rate / 100.0)
            * (reasoning_visibility_rate / 100.0)
            * (critical_event_impact / 100.0),
            1,
        )
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
            "observed_tool_results": observed_tool_results,
            "missing_tool_results": missing_tool_results,
            "agent_tool_success_rate": agent_tool_success_rate,
            "trace_observability_rate": trace_observability_rate,
            "lifecycle_completeness_rate": lifecycle_completeness_rate,
            "metric_completeness_rate": metric_completeness_rate,
            "reasoning_visibility_rate": reasoning_visibility_rate,
            "critical_event_impact": critical_event_impact,
            "evaluation_confidence": evaluation_confidence,
            "evaluation_validity": (
                "valid"
                if diagnostic["integrity_status"] == "ok" and evaluation_confidence >= 99.9
                else "trace_incomplete"
            ),
            "tool_success_rate": agent_tool_success_rate,
            "total_tokens": input_tokens + output_tokens,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "rounds": len(assistant_msgs),
            "duration_ms": duration_ms,
            "cost_usd": cost_usd,
        }

    def _trace_observability_factor(self, rate_pct: float) -> float:
        rate = rate_pct / 100.0
        if rate >= 0.98:
            return 1.0
        if rate >= 0.80:
            return 0.7 + 0.3 * rate
        return rate

    def _lifecycle_completeness_rate(self, events: list[dict]) -> float:
        has_session = any(e.get("type") == "session_start" for e in events)
        has_result = any(e.get("type") == "result" for e in events)
        if has_session and has_result:
            return 100.0
        if has_result:
            return 70.0
        if has_session:
            return 30.0
        return 0.0

    def _metric_completeness_rate(self, result_records: list[dict]) -> float:
        if not result_records:
            return 50.0
        result = result_records[-1]
        required = ["duration_ms", "input_tokens", "output_tokens", "cost_usd"]
        missing = [field for field in required if result.get(field) is None]
        if not missing:
            return 100.0
        if missing == ["cost_usd"]:
            return 85.0
        if len(missing) == 1:
            return 70.0
        return 50.0

    def _reasoning_visibility_rate(
        self, assistant_events: list[dict], total_tool_calls: int
    ) -> float:
        if any(e.get("thinking") for e in assistant_events):
            return 100.0
        if any(e.get("text") for e in assistant_events):
            return 85.0
        if total_tool_calls > 0:
            return 40.0
        return 60.0

    def _critical_event_impact(self, diagnostic: dict, tool_calls: list[dict]) -> float:
        if diagnostic["integrity_status"] == "ok":
            return 100.0
        affected_ids = set(diagnostic.get("affected_tool_call_ids") or [])
        if not affected_ids:
            return 60.0

        affected_calls = [
            call for call in tool_calls if self._tool_event_id(call) in affected_ids
        ]
        names = {str(call.get("tool_name", "")).lower() for call in affected_calls}
        if any(name in names for name in ("write", "edit", "multiedit", "notebookedit")):
            return 30.0
        if any(name in names for name in ("bash", "skill", "claude_code")):
            return 60.0
        return 85.0
