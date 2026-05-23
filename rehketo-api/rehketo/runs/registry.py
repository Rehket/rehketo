from __future__ import annotations

import asyncio  # noqa: TC003
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class RunTaskRegistry:
    def __init__(self) -> None:
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    def register(self, run_id: UUID, task: asyncio.Task[None]) -> None:
        self._tasks[run_id] = task
        rid = run_id

        def _on_done(_t: asyncio.Task[None]) -> None:
            self._tasks.pop(rid, None)

        task.add_done_callback(_on_done)

    def cancel(self, run_id: UUID) -> bool:
        task = self._tasks.get(run_id)
        if task is None:
            return False
        return task.cancel()

    def has(self, run_id: UUID) -> bool:
        return run_id in self._tasks


_registry_singleton: RunTaskRegistry | None = None


def get_registry() -> RunTaskRegistry:
    global _registry_singleton
    if _registry_singleton is None:
        _registry_singleton = RunTaskRegistry()
    return _registry_singleton


def reset_registry_for_tests() -> None:
    global _registry_singleton
    _registry_singleton = None
