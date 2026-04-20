from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class RunEventBus(Protocol):
    async def publish(self, run_id: str, event: dict[str, object]) -> None: ...
    def subscribe(
        self,
        run_id: str,
        *,
        from_sequence: int | None = None,
    ) -> AsyncIterator[dict[str, object]]: ...


class InProcessEventBus:
    """asyncio.Queue-per-run bus with a bounded ring buffer for late subscribers.

    Single-process only. The postgres LISTEN/NOTIFY implementation (fast-follow)
    will be a drop-in replacement satisfying the same contract.
    """

    def __init__(self, *, buffer_size: int = 1024) -> None:
        self._buffer_size = buffer_size
        self._seq: dict[str, int] = defaultdict(int)
        self._history: dict[str, deque[dict[str, object]]] = defaultdict(
            lambda: deque(maxlen=self._buffer_size)
        )
        self._queues: dict[str, list[asyncio.Queue[dict[str, object]]]] = defaultdict(
            list
        )
        self._lock = asyncio.Lock()

    async def publish(self, run_id: str, event: dict[str, object]) -> None:
        async with self._lock:
            seq = self._seq[run_id]
            self._seq[run_id] = seq + 1
            enriched = {**event, "sequence": seq, "run_id": run_id}
            self._history[run_id].append(enriched)
            for q in list(self._queues[run_id]):
                q.put_nowait(enriched)

    async def subscribe(
        self,
        run_id: str,
        *,
        from_sequence: int | None = None,
    ) -> AsyncIterator[dict[str, object]]:
        q: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        async with self._lock:
            # Replay buffered history from from_sequence onward
            if self._history.get(run_id):
                for e in self._history[run_id]:
                    seq = cast("int", e["sequence"])
                    if from_sequence is None or seq >= from_sequence:
                        q.put_nowait(e)
            self._queues[run_id].append(q)
        try:
            while True:
                event = await q.get()
                yield event
        finally:
            async with self._lock:
                if q in self._queues[run_id]:
                    self._queues[run_id].remove(q)
