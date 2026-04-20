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
