from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002  # fixture annotation

from rehketo.auth.cookies import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from rehketo.auth.csrf import issue_csrf_token
from rehketo.auth.sessions import create_session, get_active_session
from rehketo.db.models import User
from rehketo.main import create_app


@pytest.mark.asyncio
async def test_logout_revokes_session(
    settings_env: pytest.MonkeyPatch, db_url: str, db: AsyncSession
) -> None:
    user = User(id=uuid4(), display_name="Al", email="al@example.com")
    db.add(user)
    await db.commit()
    sid = await create_session(
        db,
        user_id=user.id,
        identity_provider="entra",
        refresh_token="rt",
        ttl_minutes=60,
    )
    csrf = issue_csrf_token(str(sid))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/auth/logout",
            cookies={SESSION_COOKIE: str(sid), CSRF_COOKIE: csrf},
            headers={CSRF_HEADER: csrf},
        )
    assert r.status_code == 204

    assert await get_active_session(db, sid) is None


@pytest.mark.asyncio
async def test_logout_without_csrf_is_forbidden(
    settings_env: pytest.MonkeyPatch, db_url: str, db: AsyncSession
) -> None:
    """Logout must enforce CSRF so a cross-site POST can't silently log the
    user out. Middleware rejects before the handler runs."""
    user = User(id=uuid4(), display_name="Al", email="al@example.com")
    db.add(user)
    await db.commit()
    sid = await create_session(
        db,
        user_id=user.id,
        identity_provider="entra",
        refresh_token="rt",
        ttl_minutes=60,
    )

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/auth/logout", cookies={SESSION_COOKIE: str(sid)})
    assert r.status_code == 403

    # Session still active — logout was blocked.
    assert await get_active_session(db, sid) is not None
