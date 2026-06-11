from __future__ import annotations

import json
import os
from typing import Iterable

from pydantic import BaseModel, Field

from src.infrastructure.llm_gateway import LLMClient


class TraceChunkSummary(BaseModel):
    step_range: str
    task_progress: str = ""
    key_actions: list[str] = Field(default_factory=list)
    tool_failures: list[str] = Field(default_factory=list)
    possible_harness_gaps: list[str] = Field(default_factory=list)
    created_or_modified_files: list[str] = Field(default_factory=list)
    fatal_rule_evidence: list[str] = Field(default_factory=list)
    skill_evidence: list[str] = Field(default_factory=list)
    important_raw_steps: list[int] = Field(default_factory=list)
    summary: str = ""


class CondensedTraceView(BaseModel):
    judge_input_mode: str = "condensed_trace"
    original_event_count: int
    original_char_count: int
    condensed_char_count: int
    compression_ratio: float
    preserved_step_ids: list[int]
    preserved_evidence_text: str
    chunk_summaries: list[TraceChunkSummary]


class TraceCondenser:
    """Builds a Judge-only compressed trace view without changing raw scoring inputs."""

    def __init__(
        self,
        llm_client: LLMClient,
        event_threshold: int | None = None,
        char_threshold: int | None = None,
        chunk_size: int | None = None,
    ):
        self.llm_client = llm_client
        self.event_threshold = event_threshold or int(os.getenv("JUDGE_TRACE_CONDENSE_EVENT_THRESHOLD", "120"))
        self.char_threshold = char_threshold or int(os.getenv("JUDGE_TRACE_CONDENSE_CHAR_THRESHOLD", "120000"))
        self.chunk_size = chunk_size or int(os.getenv("JUDGE_TRACE_CONDENSE_CHUNK_EVENTS", "50"))

    def should_condense(self, trace_data: list[dict]) -> bool:
        return (
            len(trace_data) > self.event_threshold
            or self._trace_char_count(trace_data) > self.char_threshold
        )

    async def condense(
        self,
        trace_data: list[dict],
        *,
        fatal_rules: list | None = None,
        skills_expected: str = "",
    ) -> CondensedTraceView:
        original_text = self._format_events(trace_data)
        preserved_steps = self._preserved_step_ids(
            trace_data,
            fatal_rules=fatal_rules or [],
            skills_expected=skills_expected,
        )
        summaries = []
        for start, chunk in self._chunk_events(trace_data):
            summaries.append(
                await self._summarize_chunk(
                    start_step=start,
                    events=chunk,
                    preserved_steps=preserved_steps,
                    fatal_rules=fatal_rules or [],
                    skills_expected=skills_expected,
                )
            )

        evidence_text = self._format_events(
            [event for i, event in enumerate(trace_data, 1) if i in preserved_steps],
            start_steps=[i for i in range(1, len(trace_data) + 1) if i in preserved_steps],
        )
        condensed_text = evidence_text + "\n" + "\n".join(
            summary.model_dump_json() for summary in summaries
        )
        original_chars = len(original_text)
        condensed_chars = len(condensed_text)
        return CondensedTraceView(
            original_event_count=len(trace_data),
            original_char_count=original_chars,
            condensed_char_count=condensed_chars,
            compression_ratio=round(condensed_chars / original_chars, 3)
            if original_chars else 1.0,
            preserved_step_ids=preserved_steps,
            preserved_evidence_text=evidence_text,
            chunk_summaries=summaries,
        )

    async def _summarize_chunk(
        self,
        *,
        start_step: int,
        events: list[dict],
        preserved_steps: list[int],
        fatal_rules: list,
        skills_expected: str,
    ) -> TraceChunkSummary:
        end_step = start_step + len(events) - 1
        system_prompt = (
            "You summarize agent trace chunks for a later Judge. "
            "Do not score the agent. Preserve facts relevant to task_completion, "
            "tool_accuracy, execution_efficiency, thinking_efficiency, fatal rules, "
            "skill evidence, created files, tool failures, and harness gaps. "
            "Do not omit references to important Step numbers."
        )
        fatal_text = "\n".join(
            f"- {getattr(rule, 'rule_id', '')}: {getattr(rule, 'description', '')}"
            for rule in fatal_rules
        )
        user_prompt = (
            f"Step range: {start_step}-{end_step}\n"
            f"Expected skill: {skills_expected or 'none'}\n"
            f"Fatal rules:\n{fatal_text or 'none'}\n"
            "Steps already preserved as raw evidence must still be referenced if important: "
            f"{[step for step in preserved_steps if start_step <= step <= end_step]}\n\n"
            "Trace chunk:\n"
            + self._format_events(events, start_step=start_step)
        )
        return await self.llm_client.ask_structured_output(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=TraceChunkSummary,
            temperature=0.1,
        )

    def _preserved_step_ids(
        self,
        trace_data: list[dict],
        *,
        fatal_rules: list,
        skills_expected: str,
    ) -> list[int]:
        preserved = set()
        tool_call_by_id = {
            self._tool_id(event): i
            for i, event in enumerate(trace_data, 1)
            if event.get("type") == "tool_call" and self._tool_id(event)
        }
        result_ids = {
            self._tool_id(event)
            for event in trace_data
            if event.get("type") == "tool_result" and self._tool_id(event)
        }

        for i, event in enumerate(trace_data, 1):
            event_type = event.get("type")
            event_text = json.dumps(event, ensure_ascii=False)
            tool_name = str(event.get("tool_name", "")).lower()

            if event_type in {"session_start", "result"}:
                preserved.add(i)
            if event_type == "tool_result" and event.get("tool_error", False):
                preserved.add(i)
                call_step = tool_call_by_id.get(self._tool_id(event))
                if call_step:
                    preserved.add(call_step)
            if event_type == "tool_call" and tool_name in {
                "write", "edit", "multiedit", "notebookedit", "bash", "skill", "claude_code"
            }:
                preserved.add(i)
            if event_type == "tool_call" and self._tool_id(event) and self._tool_id(event) not in result_ids:
                preserved.add(i)
            if event_type == "assistant" and i >= max(1, len(trace_data) - 3):
                preserved.add(i)
            if skills_expected and skills_expected in event_text:
                preserved.add(i)
            for rule in fatal_rules:
                if getattr(rule, "description", "") and getattr(rule, "description") in event_text:
                    preserved.add(i)

        return sorted(preserved)

    def _chunk_events(self, trace_data: list[dict]) -> Iterable[tuple[int, list[dict]]]:
        index = 0
        while index < len(trace_data):
            start = index
            end = min(index + self.chunk_size, len(trace_data))
            if end < len(trace_data):
                last = trace_data[end - 1]
                next_event = trace_data[end]
                if (
                    last.get("type") == "tool_call"
                    and next_event.get("type") == "tool_result"
                    and self._tool_id(last)
                    and self._tool_id(last) == self._tool_id(next_event)
                ):
                    end += 1
            yield start + 1, trace_data[start:end]
            index = end

    def _format_events(
        self,
        events: list[dict],
        *,
        start_step: int = 1,
        start_steps: list[int] | None = None,
    ) -> str:
        lines = []
        for offset, event in enumerate(events):
            step = start_steps[offset] if start_steps else start_step + offset
            lines.append(f"### Step {step}")
            lines.append(json.dumps(event, ensure_ascii=False))
            lines.append("")
        return "\n".join(lines)

    def _trace_char_count(self, trace_data: list[dict]) -> int:
        return sum(len(json.dumps(event, ensure_ascii=False)) for event in trace_data)

    def _tool_id(self, event: dict) -> str:
        return str(event.get("tool_call_id") or event.get("tool_use_id") or "")
