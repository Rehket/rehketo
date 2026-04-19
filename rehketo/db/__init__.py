from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from rehketo.config import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_engine_singleton: AsyncEngine | None = None
_sessionmaker_singleton: async_sessionmaker[AsyncSession] | None = None


def _make_engine() -> AsyncEngine:
    return create_async_engine(
        get_settings().database_url, pool_pre_ping=True, future=True
    )


def engine() -> AsyncEngine:
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = _make_engine()
    return _engine_singleton


def sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker_singleton
    if _sessionmaker_singleton is None:
        _sessionmaker_singleton = async_sessionmaker(engine(), expire_on_commit=False)
    return _sessionmaker_singleton


async def get_session() -> AsyncIterator[AsyncSession]:
    async with sessionmaker()() as s:
        yield s


def reset_engine_for_tests() -> None:
    """Clear cached engine/sessionmaker so tests can switch DATABASE_URL."""
    global _engine_singleton, _sessionmaker_singleton
    _engine_singleton = None
    _sessionmaker_singleton = None
