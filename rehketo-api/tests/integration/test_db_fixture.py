from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_database_is_migrated(settings_env: object, db: AsyncSession) -> None:
    result = await db.execute(
        text(
            "select table_name from information_schema.tables "
            "where table_schema='public' order by table_name"
        )
    )
    tables = {r[0] for r in result}
    # v1 application schema — migrations 0001 + 0002.
    assert {
        "users",
        "identities",
        "sessions",
        "connections",
        "user_roles",
        "conversations",
        "messages",
        "runs",
        "run_events",
    }.issubset(tables)
    # LangGraph checkpointer tables — migration 0003 runs
    # AsyncPostgresSaver.setup() which is expected to create these names.
    # If LangGraph renames tables in a future release, this test fails fast.
    assert {
        "checkpoints",
        "checkpoint_writes",
        "checkpoint_blobs",
        "checkpoint_migrations",
    }.issubset(tables)
