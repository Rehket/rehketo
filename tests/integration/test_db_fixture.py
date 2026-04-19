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
