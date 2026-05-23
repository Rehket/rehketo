"""
Dev server entry point.

    uv run python -m rehketo.cli.serve

Uvicorn creates its event loop inside `asyncio.run()` BEFORE importing the
ASGI app, so setting the policy in `rehketo.main` is too late on Windows —
the loop is already a ProactorEventLoop by then, and psycopg3 async refuses
to run on it. This wrapper sets the policy in the current process BEFORE
importing or starting uvicorn, so the loop uvicorn creates is a
SelectorEventLoop and DB calls in the lifespan + request handlers work.

Use `uv run uvicorn rehketo.main:app ...` directly ONLY on non-Windows.
"""
from __future__ import annotations

import asyncio
import sys


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(
            asyncio.WindowsSelectorEventLoopPolicy()  # type: ignore[attr-defined]
        )
    import uvicorn

    uvicorn.run(
        "rehketo.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
