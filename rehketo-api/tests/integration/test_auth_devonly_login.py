from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002  # fixture annotation

from rehketo.auth.cookies import SESSION_COOKIE
from rehketo.db.models import Session, User
from rehketo.main import create_app


@pytest.mark.asyncio
async def test_devonly_login_creates_session(
    settings_env: pytest.MonkeyPatch, db_url: str, db: AsyncSession
) -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/auth/devonly/login",
            json={"email": "al@example.com", "display_name": "Al", "roles": ["User"]},
        )
    assert r.status_code == 200
    assert SESSION_COOKIE in r.headers.get("set-cookie", "")

    users = (await db.execute(select(User))).scalars().all()
    assert len(users) == 1
    sessions = (await db.execute(select(Session))).scalars().all()
    assert len(sessions) == 1


@pytest.mark.asyncio
async def test_devonly_login_returns_404_when_disabled(
    settings_env: pytest.MonkeyPatch, db_url: str
) -> None:
    settings_env.setenv("DEVONLY_LOGIN_ENABLED", "false")
    from rehketo.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/auth/devonly/login",
            json={"email": "al@example.com"},
        )
    assert r.status_code == 404
