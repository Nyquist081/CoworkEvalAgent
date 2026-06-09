import pytest
from pathlib import Path
from src.infrastructure.trace_parser import TraceParser
from src.core.exceptions import IncompleteTraceError, TraceIntegrityError

SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample_data" / "traces"


@pytest.mark.asyncio
async def test_parse_valid_trace():
    parser = TraceParser()
    trace_path = SAMPLE_DIR / "valid_trace.jsonl"
    trace_data = await parser.parse(trace_path)
    assert len(trace_data) == 11
    assert trace_data[0]["type"] == "session_start"
    assert trace_data[-1]["type"] == "result"


@pytest.mark.asyncio
async def test_extract_metrics():
    parser = TraceParser()
    trace_path = SAMPLE_DIR / "valid_trace.jsonl"
    trace_data = await parser.parse(trace_path)
    metrics = parser.extract_metrics(trace_data)
    assert metrics["total_tool_calls"] == 3
    assert metrics["success_tool_calls"] == 2
    assert metrics["failed_tool_calls"] == 1
    assert metrics["tool_success_rate"] == pytest.approx(2 / 3 * 100)
    assert metrics["total_tokens"] == 488250 + 3447
    assert metrics["rounds"] >= 3
    assert metrics["duration_ms"] == 432220
    assert metrics["cost_usd"] == 3.62


@pytest.mark.asyncio
async def test_incomplete_trace_raises_error():
    parser = TraceParser()
    trace_path = SAMPLE_DIR / "incomplete_trace.jsonl"
    with pytest.raises(IncompleteTraceError):
        await parser.parse(trace_path)


@pytest.mark.asyncio
async def test_empty_trace():
    parser = TraceParser()
    trace_data = await parser.parse_lines([])
    assert trace_data == []


@pytest.mark.asyncio
async def test_extract_metrics_zero_calls():
    parser = TraceParser()
    trace_data = [
        {"type": "session_start", "model": "test"},
        {"type": "assistant", "thinking": "...", "text": "No tools needed"},
        {"type": "result", "status": "success", "duration_ms": 1000,
         "input_tokens": 100, "output_tokens": 50, "cost_usd": 0.01},
    ]
    metrics = parser.extract_metrics(trace_data)
    assert metrics["total_tool_calls"] == 0
    assert metrics["success_tool_calls"] == 0
    assert metrics["tool_success_rate"] == 100.0


@pytest.mark.asyncio
async def test_parse_rejects_mismatched_tool_call_ids():
    parser = TraceParser()
    lines = [
        '{"type":"session_start","trace_schema_version":"1.1","model":"test"}',
        '{"type":"tool_call","tool_call_id":"call-1","tool_name":"Read","tool_input":{}}',
        '{"type":"tool_result","tool_call_id":"call-2","tool_result":"ok","tool_error":false}',
        '{"type":"result","status":"success","duration_ms":1,"input_tokens":0,"output_tokens":0,"cost_usd":0.0}',
    ]

    with pytest.raises(TraceIntegrityError):
        await parser.parse_lines(lines)


def test_diagnose_integrity_classifies_missing_result_as_harness_failure():
    parser = TraceParser()
    trace_data = [
        {"type": "session_start", "trace_schema_version": "1.1", "model": "test"},
        {"type": "tool_call", "tool_call_id": "call-1", "tool_name": "Read"},
        {"type": "result", "status": "success"},
    ]

    diagnostic = parser.diagnose_integrity(trace_data)

    assert diagnostic["integrity_status"] == "missing_tool_result"
    assert diagnostic["failure_domain"] == "harness"
    assert diagnostic["affected_tool_call_ids"] == ["call-1"]
    assert diagnostic["scoring_policy"] == "do_not_penalize_agent_tool_accuracy"


def test_extract_metrics_separates_agent_success_from_observability():
    parser = TraceParser()
    trace_data = [
        {"type": "session_start", "trace_schema_version": "1.1", "model": "test"},
        {"type": "tool_call", "tool_call_id": "call-1", "tool_name": "Read"},
        {"type": "tool_result", "tool_call_id": "call-1", "tool_error": False},
        {"type": "tool_call", "tool_call_id": "call-2", "tool_name": "Bash"},
        {"type": "result", "status": "success"},
    ]

    metrics = parser.extract_metrics(trace_data)

    assert metrics["total_tool_calls"] == 2
    assert metrics["observed_tool_results"] == 1
    assert metrics["missing_tool_results"] == 1
    assert metrics["agent_tool_success_rate"] == 100.0
    assert metrics["trace_observability_rate"] == 50.0


def test_extract_metrics_confidence_penalizes_missing_lifecycle_metrics_and_reasoning():
    parser = TraceParser()
    trace_data = [
        {"type": "session_start", "trace_schema_version": "1.1", "model": "test"},
        {"type": "tool_call", "tool_call_id": "call-1", "tool_name": "Read"},
        {"type": "tool_result", "tool_call_id": "call-1", "tool_error": False},
        {"type": "result", "status": "success", "input_tokens": 100, "output_tokens": 20},
    ]

    metrics = parser.extract_metrics(trace_data)

    assert metrics["trace_observability_rate"] == 100.0
    assert metrics["lifecycle_completeness_rate"] == 100.0
    assert metrics["metric_completeness_rate"] == 50.0
    assert metrics["reasoning_visibility_rate"] == 40.0
    assert metrics["critical_event_impact"] == 100.0
    assert metrics["evaluation_confidence"] == 20.0
