from __future__ import annotations

import asyncio
import base64
import pathlib
import secrets
import sys
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command

if TYPE_CHECKING:
    from collections.abc import Generator, Iterator

    from testcontainers.postgres import PostgresContainer


API_ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy | None:
    """Use SelectorEventLoop on Windows — ProactorEventLoop breaks psycopg async."""
    if sys.platform == "win32":
        return asyncio.windows_events._WindowsSelectorEventLoopPolicy()  # type: ignore[attr-defined]
    return None


@pytest.fixture
def settings_env(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[pytest.MonkeyPatch]:
    """Minimal env for building an app that does not touch the DB."""
    key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/d")
    monkeypatch.setenv("SESSION_ENCRYPTION_KEY", key)
    monkeypatch.setenv("CSRF_SIGNING_KEY", "x" * 64)
    monkeypatch.setenv("ENTRA_TENANT_ID", "tid")
    monkeypatch.setenv("ENTRA_CLIENT_ID", "cid")
    monkeypatch.setenv("ENTRA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("ENTRA_REDIRECT_URI", "http://localhost:8000/auth/callback")
    monkeypatch.setenv("UI_POST_LOGIN_URL", "http://localhost:5173/")
    monkeypatch.setenv("DEVONLY_LOGIN_ENABLED", "true")
    from rehketo.config import get_settings

    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def _pg() -> Iterator[PostgresContainer]:
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:17", driver=None) as c:
        yield c


def _sa_url(pg: PostgresContainer) -> str:
    raw = pg.get_connection_url()
    # testcontainers may return 'postgresql+psycopg2://...' — normalize to psycopg
    if "+psycopg2" in raw:
        raw = raw.replace("+psycopg2", "+psycopg")
    if raw.startswith("postgresql://"):
        raw = raw.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw


@pytest.fixture
def db_url(
    _pg: PostgresContainer, monkeypatch: pytest.MonkeyPatch
) -> Generator[str]:
    url = _sa_url(_pg)
    monkeypatch.setenv("DATABASE_URL", url)
    from rehketo.config import get_settings

    get_settings.cache_clear()
    # Fresh schema per test: drop all + upgrade to head
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield url
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def db(db_url: str) -> AsyncSession:
    engine = create_async_engine(db_url, future=True)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s  # type: ignore[misc]
    await engine.dispose()
