from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002  # fixture annotation

from rehketo.auth.cookies import SESSION_COOKIE
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

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t"
    ) as c:
        r = await c.post("/auth/logout", cookies={SESSION_COOKIE: str(sid)})
    assert r.status_code == 204

    assert await get_active_session(db, sid) is None
