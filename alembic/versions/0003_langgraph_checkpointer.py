"""langgraph checkpointer tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-20 00:00:00.000000
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import sys
from collections.abc import Sequence

from alembic import op
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from rehketo.config import get_settings

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


async def _setup() -> None:
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        await saver.setup()


def _run_setup_in_thread() -> None:
    """Run _setup() in a fresh thread with its own event loop.

    Alembic's env.py already drives an asyncio event loop; calling
    asyncio.run() from within it raises RuntimeError. Running in a
    separate thread gives us a clean event loop context.
    """
    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop()
    else:
        loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_setup())
    finally:
        loop.close()


def upgrade() -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run_setup_in_thread)
        future.result()


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS checkpoint_writes CASCADE")
    op.execute("DROP TABLE IF EXISTS checkpoint_blobs CASCADE")
    op.execute("DROP TABLE IF EXISTS checkpoints CASCADE")
    op.execute("DROP TABLE IF EXISTS checkpoint_migrations CASCADE")
