from __future__ import annotations

from rehketo.agent.events import transform_chunk


def test_message_delta_chunk_emits_message_delta() -> None:
    # LangGraph's "messages" stream mode yields tuples of (AIMessageChunk, metadata).
    # Shape varies; adapt the transformer and test together.
    class _AIChunk:
        content = "hello "
        id = "msg-1"

    events = list(transform_chunk((_AIChunk(), {"langgraph_node": "agent"})))
    assert len(events) == 1
    assert events[0]["type"] == "message.delta"
    assert events[0]["message_id"] == "msg-1"
    assert events[0]["delta"] == "hello "


def test_empty_chunk_emits_nothing() -> None:
    class _AIChunk:
        content = ""
        id = "msg-1"

    assert list(transform_chunk((_AIChunk(), {}))) == []


def test_list_of_text_blocks_is_concatenated() -> None:
    """LangChain content shape `list[dict]` (Anthropic-native, Responses shim).
    Concatenate the text fields so the UI sees a string, not [object Object]."""

    class _AIChunk:
        content = [
            {"type": "text", "text": "hello "},
            {"type": "text", "text": "world"},
        ]
        id = "msg-2"

    events = list(transform_chunk((_AIChunk(), {})))
    assert len(events) == 1
    assert events[0]["delta"] == "hello world"
    assert events[0]["message_id"] == "msg-2"


def test_list_of_plain_strings_is_concatenated() -> None:
    class _AIChunk:
        content = ["foo", "bar"]
        id = "msg-3"

    events = list(transform_chunk((_AIChunk(), {})))
    assert events[0]["delta"] == "foobar"


def test_list_with_non_text_blocks_is_skipped() -> None:
    class _AIChunk:
        content = [
            {"type": "tool_use", "id": "t1", "input": {}},
            {"type": "text", "text": "after tool"},
        ]
        id = "msg-4"

    events = list(transform_chunk((_AIChunk(), {})))
    assert events[0]["delta"] == "after tool"


def test_empty_list_content_emits_nothing() -> None:
    class _AIChunk:
        content: list[object] = []
        id = "msg-5"

    assert list(transform_chunk((_AIChunk(), {}))) == []
