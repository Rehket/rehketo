from __future__ import annotations

import asyncio

from rehketo.runs.event_bus import InProcessEventBus, RunEventBus


async def _collect(
    bus: RunEventBus,
    run_id: str,
    n: int,
    *,
    from_sequence: int | None = None,
) -> list[dict]:
    events: list[dict] = []
    async for e in bus.subscribe(run_id, from_sequence=from_sequence):
        events.append(e)
        if len(events) >= n:
            break
    return events


async def test_publish_and_subscribe_roundtrip() -> None:
    bus = InProcessEventBus()

    async def publisher() -> None:
        for i in range(3):
            await bus.publish("r1", {"type": "tick", "i": i})

    task = asyncio.create_task(publisher())
    events = await _collect(bus, "r1", 3)
    await task
    assert [e["i"] for e in events] == [0, 1, 2]
    assert all("sequence" in e for e in events)


async def test_late_subscriber_reads_from_ring_buffer() -> None:
    bus = InProcessEventBus(buffer_size=16)
    for i in range(5):
        await bus.publish("r1", {"type": "tick", "i": i})
    # Subscribe AFTER publish — the ring buffer replays.
    events = await _collect(bus, "r1", 5)
    assert [e["i"] for e in events] == [0, 1, 2, 3, 4]


async def test_subscribe_from_sequence_resumes() -> None:
    bus = InProcessEventBus(buffer_size=16)
    for i in range(5):
        await bus.publish("r1", {"type": "tick", "i": i})
    events = await _collect(bus, "r1", 2, from_sequence=3)  # skip first 3 (seq 0,1,2)
    assert [e["i"] for e in events] == [3, 4]


async def test_isolation_between_run_ids() -> None:
    bus = InProcessEventBus()
    await bus.publish("r1", {"type": "tick"})
    await bus.publish("r2", {"type": "tock"})
    r1 = await _collect(bus, "r1", 1)
    r2 = await _collect(bus, "r2", 1)
    assert r1[0]["type"] == "tick"
    assert r2[0]["type"] == "tock"
