from __future__ import annotations

import json
from datetime import UTC, datetime

from rehketo.api.runs import _encode_sse_event


def test_encode_sse_event_produces_valid_json_data() -> None:
    event: dict[str, object] = {
        "type": "message.delta",
        "delta": "hello",
        "sequence": 1,
        "run_id": "00000000-0000-0000-0000-000000000001",
    }

    encoded = _encode_sse_event(event)

    assert encoded["event"] == "message.delta"
    roundtrip = json.loads(encoded["data"])
    assert roundtrip == event


def test_encode_sse_event_uses_default_str_for_datetime() -> None:
    when = datetime(2026, 4, 20, 12, 0, 0, tzinfo=UTC)
    event: dict[str, object] = {
        "type": "run.status",
        "status": "running",
        "sequence": 2,
        "started_at": when,
    }

    encoded = _encode_sse_event(event)

    roundtrip = json.loads(encoded["data"])
    assert roundtrip["started_at"] == str(when)


def test_encode_sse_event_is_json_not_python_repr() -> None:
    event: dict[str, object] = {
        "type": "message.delta",
        "delta": "has \"quotes\" and 'apostrophes'",
        "sequence": 3,
    }

    encoded = _encode_sse_event(event)

    assert "'" not in encoded["data"].replace("'apostrophes'", "")
    json.loads(encoded["data"])


def test_encode_sse_event_round_trip_preserves_complete_shape() -> None:
    event: dict[str, object] = {
        "type": "message.complete",
        "message": {
            "id": "msg-1",
            "role": "assistant",
            "content": "ok",
            "run_id": "run-1",
        },
        "sequence": 10,
        "run_id": "run-1",
    }

    encoded = _encode_sse_event(event)

    assert encoded["event"] == "message.complete"
    assert json.loads(encoded["data"]) == event
