from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator


def transform_chunk(chunk: tuple[Any, dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """Convert a LangGraph `stream_mode='messages'` chunk into zero or more
    events in our stable schema. Yields nothing for empty / metadata-only chunks."""
    msg, _metadata = chunk
    delta = getattr(msg, "content", None)
    if not delta:
        return
    yield {
        "type": "message.delta",
        "message_id": getattr(msg, "id", None),
        "delta": delta,
    }
