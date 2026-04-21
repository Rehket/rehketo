"""Integration test — /docs and /openapi.json require an authenticated session."""
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from rehketo.auth.cookies import SESSION_COOKIE
from rehketo.auth.sessions import create_session
from rehketo.db.models import User
from rehketo.main import create_app

if TYPE_CHECKING:
    import pytest
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_docs_anonymous_returns_401(
    settings_env: pytest.MonkeyPatch, db_url: str
) -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/docs")
    assert r.status_code == 401


async def test_openapi_json_anonymous_returns_401(
    settings_env: pytest.MonkeyPatch, db_url: str
) -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/openapi.json")
    assert r.status_code == 401


async def test_docs_authenticated_returns_html(
    settings_env: pytest.MonkeyPatch, db_url: str, db: AsyncSession
) -> None:
    u = User(id=uuid4(), display_name="A", email="a@x")
    db.add(u)
    await db.commit()
    sid = await create_session(
        db,
        user_id=u.id,
        identity_provider="entra",
        refresh_token="rt",
        ttl_minutes=60,
    )

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/docs", cookies={SESSION_COOKIE: str(sid)})
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "swagger-ui" in r.text


async def test_openapi_json_authenticated_returns_schema(
    settings_env: pytest.MonkeyPatch, db_url: str, db: AsyncSession
) -> None:
    u = User(id=uuid4(), display_name="A", email="a@x")
    db.add(u)
    await db.commit()
    sid = await create_session(
        db,
        user_id=u.id,
        identity_provider="entra",
        refresh_token="rt",
        ttl_minutes=60,
    )

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/openapi.json", cookies={SESSION_COOKIE: str(sid)})
    assert r.status_code == 200
    schema = r.json()
    assert schema["info"]["title"] == "Rehketo API"
    assert "paths" in schema
