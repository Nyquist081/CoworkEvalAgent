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
