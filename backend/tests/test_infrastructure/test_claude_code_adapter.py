import json

from src.infrastructure.claude_code_adapter import ClaudeCodeAdapter


def test_adapter_preserves_claude_tool_use_ids(tmp_path):
    session = tmp_path / "session.jsonl"
    records = [
        {
            "type": "user",
            "isSidechain": False,
            "timestamp": "2026-06-10T00:00:00Z",
            "message": {"role": "user", "content": "Read the file."},
        },
        {
            "type": "assistant",
            "timestamp": "2026-06-10T00:00:01Z",
            "message": {
                "model": "claude-test",
                "usage": {"input_tokens": 10, "output_tokens": 4},
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_123",
                        "name": "Read",
                        "input": {"file_path": "a.txt"},
                    }
                ],
            },
        },
        {
            "type": "user",
            "isSidechain": False,
            "timestamp": "2026-06-10T00:00:02Z",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_123",
                        "content": "hello",
                    }
                ],
            },
        },
    ]
    session.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    result = ClaudeCodeAdapter().parse_session(session)

    tool_call = next(e for e in result["events"] if e["type"] == "tool_call")
    tool_result = next(e for e in result["events"] if e["type"] == "tool_result")
    assert tool_call["tool_call_id"] == "toolu_123"
    assert tool_result["tool_call_id"] == "toolu_123"
    assert result["metrics"]["success_tool_calls"] == 1
