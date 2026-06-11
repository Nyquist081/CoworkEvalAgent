from unittest.mock import AsyncMock

import pytest

from src.services.trace_condenser import TraceCondenser, TraceChunkSummary


@pytest.mark.asyncio
async def test_condenser_preserves_critical_raw_evidence_and_summarizes_chunks():
    llm_client = AsyncMock()
    llm_client.ask_structured_output = AsyncMock(
        return_value=TraceChunkSummary(
            step_range="1-6",
            task_progress="普通读取步骤已概括",
            important_raw_steps=[1, 5, 6],
            summary="Read output was summarized without copying long payload.",
        )
    )
    trace = [
        {"type": "session_start", "model": "test"},
        {"type": "tool_call", "tool_call_id": "read-1", "tool_name": "Read"},
        {"type": "tool_result", "tool_call_id": "read-1", "tool_result": "x" * 2000},
        {"type": "tool_call", "tool_call_id": "bash-1", "tool_name": "Bash"},
        {"type": "tool_result", "tool_call_id": "bash-1", "tool_error": True, "tool_result": "failed"},
        {"type": "result", "status": "success", "duration_ms": 1},
    ]

    condenser = TraceCondenser(llm_client, event_threshold=1, chunk_size=10)
    condensed = await condenser.condense(trace)

    assert condensed.judge_input_mode == "condensed_trace"
    assert 1 in condensed.preserved_step_ids
    assert 4 in condensed.preserved_step_ids
    assert 5 in condensed.preserved_step_ids
    assert 6 in condensed.preserved_step_ids
    assert "failed" in condensed.preserved_evidence_text
    assert "x" * 200 not in condensed.preserved_evidence_text
    assert condensed.chunk_summaries[0].summary.startswith("Read output was summarized")
